"""Durable SSM observation jobs for a trusted, IAM-only student controller.

This is not an HTTP authorizer. The controller must resolve the current approved
Lab, verify its five EC2 tags/SSM readiness, and supply the fixed command builder.
No browser-provided command, target, report, score, password or key is accepted.

SSM SendCommand has no idempotency token. Record dispatch intent first, disable
SDK retries, and never send again after an ambiguous result. Recovery searches
the original Comment, exact instance and public command-parameter digest. An
observation timeout does not create a second command or overwrite a grade.

Report persistence is an outbox only. Submission through the existing assessment
service and its exact-request receipt is a separate controller step. No grade,
EC2 lifecycle, identity, credential, or IAM operation is performed here.
"""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re
import time
import uuid

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.config import Config

from registry import CONTRACT_SHA256, TASKS, validate_report

SER, DE = TypeSerializer(), TypeDeserializer()
ROLES = {'bastion', 'web', 'dns', 'db', 'repo'}
PHASES = {'queued', 'dispatching', 'observing', 'report_ready', 'failed'}
UUID = re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\Z')
HEX = re.compile(r'[a-f0-9]{64}\Z')
SPEC_KEYS = {'job_id', 'owner_hash', 'account', 'lab_id', 'deployment_id',
             'release_id', 'instances', 'task_id', 'run_id', 'contract_sha256'}


class JobDenied(ValueError):
    pass


class JobBusy(JobDenied):
    pass


def native(value):
    if isinstance(value, Decimal):
        if not value.is_finite() or value != int(value):
            raise JobDenied('Unexpected non-integer persisted value')
        return int(value)
    if isinstance(value, dict):
        return {k: native(v) for k, v in value.items()}
    if isinstance(value, list):
        return [native(v) for v in value]
    return value


def canonical(value):
    return json.dumps(native(value), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def encoded(row):
    return {k: SER.serialize(v) for k, v in row.items()}


def key(pk, sk):
    return encoded({'pk': pk, 'sk': sk})


def checked_spec(value):
    if (type(value) is not dict or set(value) not in (SPEC_KEYS,SPEC_KEYS|{'check_mode'})
            or value.get('check_mode','read_only') not in ('read_only','storage','functional','storage_prepare','functional_prepare')
            or value.get('check_mode','read_only').startswith('storage') and value.get('task_id') not in ('P3','M3')
            or value.get('check_mode','read_only').startswith('functional') and value.get('task_id') not in ('P5','M5','P6','M6')
            or any(not isinstance(value[k], str) or not UUID.fullmatch(value[k])
                   or uuid.UUID(value[k]).version != 4 for k in ('job_id', 'deployment_id', 'run_id'))
            or not isinstance(value['owner_hash'], str) or not HEX.fullmatch(value['owner_hash'])
            or not isinstance(value['account'], str) or not re.fullmatch(r'[0-9]{12}', value['account'])
            or not isinstance(value['lab_id'], str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', value['lab_id'])
            or not isinstance(value['release_id'], str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,64}', value['release_id'])
            or not isinstance(value['task_id'], str) or value['task_id'] not in TASKS
            or value['contract_sha256'] != CONTRACT_SHA256
            or type(value['instances']) is not dict or set(value['instances']) != ROLES
            or any(not isinstance(v, str) or not re.fullmatch(r'i-[a-f0-9]{17}', v) for v in value['instances'].values())
            or len(set(value['instances'].values())) != 5):
        raise JobDenied('Invalid trusted assessment job')
    return json.loads(canonical(value))


def report_mode(spec):
    return 'functional' if spec.get('check_mode')=='functional' else 'read_only'


def no_retry_ssm(session):
    return session.client('ssm', region_name='us-east-1', config=Config(
        connect_timeout=3, read_timeout=8, retries={'total_max_attempts': 1}))


def public_job(row):
    """A bounded UI projection: no command, instance ID, identity or report."""
    phase = row.get('phase')
    if phase not in PHASES:
        raise JobDenied('Invalid persisted job')
    result = {k: row['spec'][k] for k in ('job_id', 'task_id')}
    result.update(phase=phase, created_at=int(row['created_at']), updated_at=int(row['updated_at']))
    if phase == 'failed':
        result['reason'] = 'observation_unavailable'
    # report_ready means observation captured, never submission/points earned.
    return result


class CommandJobs:
    def __init__(self, db, table, ssm, build_command, preflight, *, clock=time.time,
                 finish_observation=None):
        if not isinstance(table, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,255}', table):
            raise JobDenied('Invalid job store')
        retries = ssm.meta.config.retries or {}
        if retries.get('total_max_attempts') != 1:
            raise JobDenied('SendCommand must not retry automatically')
        self.db, self.table, self.ssm = db, table, ssm
        self.build_command, self.preflight, self.clock = build_command, preflight, clock
        self.finish_observation = finish_observation or (lambda spec, text: json.loads(text))

    def get(self, spec):
        answer = self.db.get_item(TableName=self.table,
            Key=key('CHECK#' + spec['job_id'], 'JOB'), ConsistentRead=True).get('Item')
        row = native({k: DE.deserialize(v) for k, v in answer.items()}) if answer else None
        if row and (row.get('spec') != spec or row.get('spec_sha256') != sha(spec)):
            raise JobDenied('Job belongs to a different operation')
        return row

    def lock_key(self, spec):
        return key('CHECK-LAB#' + spec['lab_id'], 'ACTIVE')

    def parameters(self, spec):
        command = self.build_command(json.loads(canonical(spec)))
        if not isinstance(command, str) or not 1 <= len(command.encode()) <= 65536:
            raise JobDenied('Invalid fixed command')
        return {'commands': [command], 'executionTimeout': ['600']}

    def enqueue(self, trusted_spec):
        spec = checked_spec(trusted_spec)
        old = self.get(spec)
        if old:
            return public_job(old)
        # Readiness never starts EC2, opens access or turns unavailability into 0.
        if self.preflight(spec) is not True:
            raise JobDenied('Lab or required servers unavailable')
        now = int(self.clock())
        row = {'pk': 'CHECK#' + spec['job_id'], 'sk': 'JOB', 'spec': spec,
               'spec_sha256': sha(spec), 'command_sha256': sha(self.parameters(spec)),
               'phase': 'queued', 'version': 0, 'created_at': now, 'updated_at': now}
        lock = {'pk': 'CHECK-LAB#' + spec['lab_id'], 'sk': 'ACTIVE',
                'job_id': spec['job_id'], 'spec_sha256': sha(spec), 'active': True}
        try:
            self.db.transact_write_items(TransactItems=[
                {'Put': {'TableName': self.table, 'Item': encoded(row),
                         'ConditionExpression': 'attribute_not_exists(pk)'}},
                {'Put': {'TableName': self.table, 'Item': encoded(lock),
                         'ConditionExpression': 'attribute_not_exists(pk) OR #active=:no',
                         'ExpressionAttributeNames': {'#active': 'active'},
                         'ExpressionAttributeValues': encoded({':no': False})}}])
        except self.db.exceptions.TransactionCanceledException:
            old = self.get(spec)
            if old:
                return public_job(old)
            raise JobBusy('Another check is active for this Lab') from None
        return public_job(row)

    def transition(self, spec, row, phase, **values):
        if phase not in PHASES:
            raise JobDenied('Invalid job transition')
        new = {**row, **values, 'phase': phase, 'version': int(row['version']) + 1,
               'updated_at': int(self.clock())}
        write = {'Put': {'TableName': self.table, 'Item': encoded(new),
            'ConditionExpression': '#version=:version AND #phase=:phase AND #digest=:digest',
            'ExpressionAttributeNames': {'#version': 'version', '#phase': 'phase', '#digest': 'spec_sha256'},
            'ExpressionAttributeValues': encoded({':version': row['version'], ':phase': row['phase'], ':digest': sha(spec)})}}
        lock = {'Update': {'TableName': self.table, 'Key': self.lock_key(spec),
            'UpdateExpression': 'SET #active=:active',
            'ConditionExpression': '#job=:job AND #digest=:digest AND #active=:yes',
            'ExpressionAttributeNames': {'#active': 'active', '#job': 'job_id', '#digest': 'spec_sha256'},
            'ExpressionAttributeValues': encoded({':active': phase not in ('report_ready', 'failed'),
                                                  ':yes': True, ':job': spec['job_id'], ':digest': sha(spec)})}}
        try:
            self.db.transact_write_items(TransactItems=[write, lock])
        except self.db.exceptions.TransactionCanceledException:
            return None
        return new

    def current(self, trusted_spec):
        spec = checked_spec(trusted_spec)
        row = self.get(spec)
        if not row:
            raise JobDenied('Unknown job')
        return public_job(row)

    def advance(self, trusted_spec):
        """One bounded worker tick; never sleeps or submits a grade."""
        spec = checked_spec(trusted_spec)
        row = self.get(spec)
        if not row:
            raise JobDenied('Unknown job')
        if row['phase'] in ('report_ready', 'failed'):
            return public_job(row)
        # Re-check current authoritative context before every AWS observation.
        if self.preflight(spec) is not True:
            raise JobDenied('Lab or required servers unavailable')
        if row['phase'] in ('queued', 'dispatching'):
            parameters = self.parameters(spec)
            if sha(parameters) != row['command_sha256']:
                raise JobDenied('Trusted command version changed; retained original job')
        # Once AWS's exact command ID is retained, only read that invocation.
        # Recompiling public source cannot make its already-finished output
        # more authoritative and must not prevent recovery after an update.
        if row['phase'] == 'queued':
            claimed = self.transition(spec, row, 'dispatching', dispatch_started_at=int(self.clock()))
            if not claimed:
                return self.current(spec)
            row = claimed
            try:
                answer = self.ssm.send_command(InstanceIds=[spec['instances']['bastion']],
                    DocumentName='AWS-RunShellScript', Parameters=parameters, TimeoutSeconds=30,
                    Comment='JDU-check-' + spec['job_id'],
                    CloudWatchOutputConfig={'CloudWatchOutputEnabled': False})
                command_id = answer['Command']['CommandId']
                if not isinstance(command_id, str) or not UUID.fullmatch(command_id):
                    raise ValueError('Invalid command receipt')
            except Exception:
                # Includes a network timeout after AWS may already have accepted.
                # The persisted intent remains live and can only be reconciled.
                return public_job(row)
            row = self.transition(spec, row, 'observing', command_id=command_id)
            return public_job(row) if row else self.current(spec)
        if row['phase'] == 'dispatching':
            return self.reconcile(spec, row, parameters)
        if row['phase'] != 'observing':
            raise JobDenied('Unexpected worker state')
        try:
            result = self.ssm.get_command_invocation(CommandId=row['command_id'],
                InstanceId=spec['instances']['bastion'])
        except Exception:
            # Eventual consistency or expired Lab access is not a second launch.
            return public_job(row)
        if (result.get('CommandId') != row['command_id']
                or result.get('InstanceId') != spec['instances']['bastion']):
            # A mismatched response cannot prove that our command has ended.
            return public_job(row)
        if result.get('Status') in ('Pending', 'InProgress', 'Delayed', 'Cancelling'):
            return public_job(row)
        if result.get('Status') != 'Success':
            if result.get('Status') not in ('Failed', 'Cancelled', 'TimedOut'):
                return public_job(row)
            new = self.transition(spec, row, 'failed')
            return public_job(new) if new else self.current(spec)
        try:
            if type(result.get('ResponseCode')) is not int or result['ResponseCode'] != 0:
                raise ValueError('Wrong command result')
            output = result.get('StandardOutputContent')
            if not isinstance(output, str) or len(output.encode()) > 24000:
                raise ValueError('Observer result unavailable')
            # The optional fixed controller adapter adds the external HTTP
            # observations used by the original CLI. Never a browser callback.
            observed = self.finish_observation(spec, output)
            if type(observed) is not dict or not {'report'} <= set(observed) or set(observed) - {'report', 'storage_evidence','functional_recipient'}:
                raise ValueError('Invalid observer envelope')
            report = observed['report']
            validate_report(report, spec['instances'])
            if (any(report[k] != spec[k] for k in ('lab_id', 'deployment_id', 'release_id', 'run_id'))
                    or report['mission_id'] != spec['task_id'] or report['mode'] != report_mode(spec)):
                raise ValueError('Observer belongs to another task or mode')
        except Exception:
            new = self.transition(spec, row, 'failed')
            return public_job(new) if new else self.current(spec)
        # Keep the first validated canonical report with its original request ID.
        # No browser may supply or replace this body; retries read this outbox.
        metadata={k:v for k,v in observed.items() if k!='report'}
        new = self.transition(spec, row, 'report_ready', report=report, report_sha256=sha(report),observation_metadata=metadata)
        return public_job(new) if new else self.current(spec)

    def reconcile(self, spec, row, parameters):
        found, token, pages = set(), None, 0
        stamp = datetime.fromtimestamp(int(row['dispatch_started_at']) - 30, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        while True:
            args = {'InstanceId': spec['instances']['bastion'], 'MaxResults': 50,
                    'Filters': [{'key': 'InvokedAfter', 'value': stamp}]}
            if token:
                args['NextToken'] = token
            try:
                answer = self.ssm.list_commands(**args)
            except Exception:
                return public_job(row)
            for command in answer.get('Commands', []):
                if command.get('Comment') != 'JDU-check-' + spec['job_id']:
                    continue
                if (command.get('InstanceIds') != [spec['instances']['bastion']]
                        or command.get('Targets') not in (None, [])
                        or command.get('DocumentName') != 'AWS-RunShellScript'
                        or sha(command.get('Parameters')) != sha(parameters)
                        or not isinstance(command.get('CommandId'), str) or not UUID.fullmatch(command['CommandId'])):
                    raise JobDenied('Ambiguous command context; do not resend')
                found.add(command['CommandId'])
            token = answer.get('NextToken')
            pages += 1
            if not token:
                break
            if pages >= 20:
                raise JobDenied('Command search incomplete; do not resend')
        if len(found) > 1:
            raise JobDenied('Duplicate command evidence; operator review required')
        if not found:
            # Absence in an eventually consistent list is not proof of no send.
            return public_job(row)
        new = self.transition(spec, row, 'observing', command_id=next(iter(found)))
        return public_job(new) if new else self.current(spec)

    def retained_report(self, trusted_spec):
        spec = checked_spec(trusted_spec)
        row = self.get(spec)
        if not row or row.get('phase') != 'report_ready' or sha(row.get('report')) != row.get('report_sha256'):
            raise JobDenied('Original report unavailable')
        validate_report(row['report'], spec['instances'])
        if (any(row['report'][k] != spec[k] for k in ('lab_id', 'deployment_id', 'release_id', 'run_id'))
                or row['report']['mission_id'] != spec['task_id'] or row['report']['mode'] != report_mode(spec)):
            raise JobDenied('Original report context changed')
        return json.loads(canonical(row['report']))
