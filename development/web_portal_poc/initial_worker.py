"""Private student worker: plan/observe/create only, never solve exercises.

The publisher must build the Lambda from a verified signed release and a fixed
teacher assignment. This module is not an arbitrary command/manifest runner.
Python 3.11 is used for its SHA512-crypt support; validate it on AWS before use.
"""
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import time

from portal_enrollment import EnrollmentDenied, digest, encoded, key, grant_digest
from initial_plan import make_plan, InitialBudgetExceeded
from initial_stack import InitialStack
from portal_preparation import checked_assignment


def native(value):
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise EnrollmentDenied('Invalid saved plan')
        return int(value)
    if isinstance(value, dict):
        return {k: native(v) for k, v in value.items()}
    if isinstance(value, list):
        return [native(v) for v in value]
    return value


def plan_digest(plan):
    return digest(json.dumps(native(plan), sort_keys=True, separators=(',', ':')))


def hash_password(password, confirmation):
    if (not isinstance(password, str) or not isinstance(confirmation, str) or password != confirmation
            or not 12 <= len(password) <= 128 or any(c in password for c in '\r\n\x00')):
        raise EnrollmentDenied('Invalid RDP password confirmation')
    import crypt
    result = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
    if not isinstance(result, str) or not re.fullmatch(r'\$6\$[A-Za-z0-9./]{1,16}\$[A-Za-z0-9./]{86}', result):
        raise EnrollmentDenied('RDP password hashing unavailable')
    return result


class InitialWorker:
    def __init__(self, stack, *, planner=make_plan, password_hasher=hash_password, setup=None):
        self.stack, self.planner, self.password_hasher = stack, planner, password_hasher
        self.setup = setup

    def saved_plan(self):
        from boto3.dynamodb.types import TypeDeserializer
        s = self.stack
        item = s.db.get_item(TableName=s.table, Key=key(s.pk, 'PLAN'), ConsistentRead=True).get('Item')
        if not item:
            return None
        row = native({k: TypeDeserializer().deserialize(v) for k, v in item.items()})
        if (row.get('grant_digest') != grant_digest(s.grant) or type(row.get('plan')) is not dict
                or row.get('plan_digest') != plan_digest(row['plan'])):
            raise EnrollmentDenied('Saved plan changed')
        return row

    def plan_current(self, row):
        return 0 <= self.stack.clock() - datetime.fromisoformat(row['plan']['planned_at']).timestamp() <= 86400

    @staticmethod
    def view_plan(row):
        plan = row['plan']
        selection = plan['selection']
        # Do not copy private URL, key, discovery IPs or arbitrary SDK output.
        return {'plan_digest': row['plan_digest'], 'planned_at': plan['planned_at'],
            'account': plan['account'], 'lab_id': plan['lab_id'], 'deployment_id': plan['deployment_id'],
            'resource_budget': plan['resource_budget'], 'root_gib': 96, 'new_nodes': 5,
            'availability_zone': selection['availability_zone'],
            'instance_types': {r: x['instance_type'] for r, x in selection['roles'].items()},
            'compute_hourly_usd': selection['compute_hourly_usd'],
            'price_includes_disks_ipv4_endpoints': False, 'initial_state': 'foundation_only'}

    def plan(self):
        s = self.stack
        if s.saved():
            return {'status': 'ok', 'initial': s.current()}
        old = self.saved_plan()
        if old and self.plan_current(old):
            s.checked_files()
            return {'status': 'ok', 'initial': {'stage': 'PLAN_READY', **self.view_plan(old)}}
        value = self.planner(s)
        row = {'pk': s.pk, 'sk': 'PLAN', 'grant_digest': grant_digest(s.grant),
               'plan': value, 'plan_digest': plan_digest(value)}
        put = {'TableName': s.table, 'Item': encoded(row), 'ConditionExpression': 'attribute_not_exists(pk)'}
        if old:
            put.update(ConditionExpression='#digest=:old', ExpressionAttributeNames={'#digest': 'plan_digest'},
                       ExpressionAttributeValues=encoded({':old': old['plan_digest']}))
        try:
            s.db.transact_write_items(TransactItems=[
                {'ConditionCheck': {'TableName': s.table, 'Key': key(s.pk, 'CREATE'),
                                    'ConditionExpression': 'attribute_not_exists(pk)'}}, {'Put': put}])
        except s.db.exceptions.TransactionCanceledException:
            current = self.saved_plan()
            if s.saved():
                return {'status': 'ok', 'initial': s.current()}
            if not current or not self.plan_current(current):
                raise EnrollmentDenied('Plan changed; inspect the saved plan') from None
            return {'status': 'ok', 'initial': {'stage': 'PLAN_READY', **self.view_plan(current)}}
        return {'status': 'ok', 'initial': {'stage': 'PLAN_READY', **self.view_plan(row)}}

    def serve(self, event):
        if type(event) is not dict or event.get('grant_digest') != grant_digest(self.stack.grant):
            return {'status': 'unauthorized'}
        operation = event.get('operation')
        fields = {'operation', 'grant_digest'} | ({'plan_digest', 'password', 'confirmation'} if operation == 'create' else set())
        if operation not in ('plan', 'observe', 'create', 'advance') or set(event) != fields:
            return {'status': 'unauthorized'}
        try:
            if self.stack.sts.get_caller_identity()['Account'] != self.stack.grant['account']:
                raise EnrollmentDenied('Wrong student AWS account')
            if operation == 'observe':
                initial = self.setup.current() if self.setup is not None else self.stack.current()
                saved = self.saved_plan()
                if saved and initial['stage'] == 'NOT_REQUESTED':
                    initial = {'stage': 'PLAN_READY' if self.plan_current(saved) else 'PLAN_EXPIRED', **self.view_plan(saved)}
                return {'status': 'ok', 'initial': initial}
            if operation == 'advance':
                if self.setup is None:
                    raise EnrollmentDenied('Setup adapter unavailable')
                self.stack.checked_files()
                return {'status':'ok','initial':self.setup.advance()}
            if operation == 'plan':
                return self.plan()
            if self.stack.saved():
                return {'status': 'ok', 'initial': self.stack.current()}
            row = self.saved_plan()
            if not row or not self.plan_current(row) or event['plan_digest'] != row['plan_digest']:
                raise EnrollmentDenied('Review the current plan first')
            password_hash = self.password_hasher(event['password'], event['confirmation'])
            try:
                return {'status': 'ok', 'initial': self.stack.create(row['plan'], password_hash)}
            finally:
                password_hash = None
        except InitialBudgetExceeded as error:
            return {'status': 'resource_budget', 'resource_budget': error.budget}
        except EnrollmentDenied:
            return {'status': 'unauthorized'}
        except Exception:
            # No event/exception/SDK request logging: a password may be in memory.
            return {'status': 'unavailable'}


def runtime_files(root, env):
    """Load only the fixed, publisher-reviewed source/data package."""
    root = Path(root)
    config = json.loads((root/'initial-assignment.json').read_bytes())
    grant = checked_assignment(config['assignment'])
    if (config.get('schema_version') != 1 or config.get('initial_state') != 'foundation_only'
            or env.get('STUDENT_ACCOUNT') != grant['account'] or env.get('LAB_ID') != grant['lab_id']
            or env.get('INITIAL_DEPLOYMENT_ID') != grant['deployment_id']
            or env.get('INITIAL_PROGRESS_TABLE') != 'jdu-web-initial-' + grant['lab_id'] + '-progress'):
        raise EnrollmentDenied('Wrong initial worker configuration')
    for name, expected in config['files'].items():
        if Path(name).name != name or not re.fullmatch(r'[a-f0-9]{64}', expected):
            raise EnrollmentDenied('Wrong worker package')
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != expected:
            raise EnrollmentDenied('Worker package changed')
    manifest_data = (root/'deployment-manifest.json').read_bytes()
    if hashlib.sha256(manifest_data).hexdigest() != grant['release']['manifest_sha256']:
        raise EnrollmentDenied('Assigned manifest changed')
    verified = {'manifest': json.loads(manifest_data), 'manifest_sha256': grant['release']['manifest_sha256'],
        'trusted_fingerprint': config['trusted_fingerprint'], 'files': {
            'template': root/'foundation.template.json', 'price_catalog': root/'teacher-price-catalog.json'}}
    return verified, grant


def handler(event, context):
    try:
        import boto3
        import os
        from botocore.config import Config
        verified, grant = runtime_files(Path(__file__).resolve().parent, os.environ)
        session = boto3.Session(region_name='us-east-1')
        if type(event) is dict and 'RequestType' in event:
            # The initial CloudFormation helper only confirms the AWS account.
            # Actual creation requires a later explicit, authenticated POST.
            from browser_link_handler import serve
            return serve(event, os.environ, session)
        s = InitialStack(verified, grant, session.client('dynamodb'), os.environ['INITIAL_PROGRESS_TABLE'],
            session.client('cloudformation', config=Config(connect_timeout=3, read_timeout=20,
                                                          retries={'total_max_attempts':1})),
            session.client('ec2'), session.client('sts'), session.client('iam'), session.client('s3'), clock=time.time)
        from initial_setup import InitialSetup
        worker=InitialWorker(s)
        worker.setup=InitialSetup(s,worker.saved_plan,
            session.client('ssm',config=Config(connect_timeout=3,read_timeout=5,retries={'total_max_attempts':1})),
            session.client('ec2-instance-connect',config=Config(connect_timeout=3,read_timeout=5,retries={'total_max_attempts':1})),
            remaining=context.get_remaining_time_in_millis)
        return worker.serve(event)
    except Exception:
        return {'status': 'unavailable'}
