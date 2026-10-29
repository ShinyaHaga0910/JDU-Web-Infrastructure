"""IAM-only fixed D11 checks on the student's retained five servers.

The teacher service supplies the resolved owner/spec. No URL, arbitrary shell,
password, key, score, lifecycle operation or grade write is accepted here.
"""
import copy
import json
import os

from assessment_command_jobs import CommandJobs, JobBusy, JobDenied, checked_spec, encoded, key, native, DE, no_retry_ssm, sha
from assessment_observation import Observation
from registry import score, validate_report


class StudentChecker:
    def __init__(self, config, db, table, sts, cfn, ec2, ssm):
        self.config, self.db, self.table = config, db, table
        self.sts, self.cfn, self.ec2, self.ssm = sts, cfn, ec2, ssm

    def scope(self, spec):
        spec = checked_spec(spec)
        state, baseline = self.config['state'], self.config['baseline']
        if (any(spec[k] != state[k] for k in ('account', 'lab_id', 'deployment_id', 'release_id'))
                or spec['instances'] != {r: n['instance_id'] for r, n in baseline['nodes'].items()}):
            raise JobDenied('Wrong retained Lab')
        return spec

    def snapshot(self, spec):
        from setup_internal_ssh import current_nodes
        from aws_readiness import verify
        state, baseline = self.config['state'], self.config['baseline']
        if self.sts.get_caller_identity()['Account'] != spec['account']:
            raise JobDenied('Wrong AWS account')
        # Same retained template, tags, IDs, root volumes and teaching phase as
        # the installed CLI. No start/stop/create fallback on an unavailable Lab.
        nodes = current_nodes(self.ec2, self.cfn, state, baseline)
        infos = self.ssm.describe_instance_information(Filters=[{'Key': 'InstanceIds',
            'Values': list(spec['instances'].values())}])['InstanceInformationList']
        if (len(infos) != 5 or {i['InstanceId'] for i in infos} != set(spec['instances'].values())
                or any(i.get('PingStatus') != 'Online' for i in infos)):
            raise JobDenied('Required servers unavailable')
        template = self.cfn.get_template(StackName=state['stack_id'], TemplateStage='Original')['TemplateBody']
        if isinstance(template, str):
            template = json.loads(template)
        network = verify(self.ec2, self.cfn, self.ssm, state, template, nodes)
        web = self.ec2.describe_instances(InstanceIds=[spec['instances']['web']])['Reservations'][0]['Instances'][0]
        return {'spec_sha256': sha(spec), 'private_ips': {r: n['private_ip'] for r, n in nodes.items()},
            'root_volumes': {r: n['root_volumes'] for r, n in nodes.items()},
            'expected_public_key': self.config['public_key'], 'network_baseline': network,
            'public_web_ipv4': web.get('PublicIpAddress')}

    def serve(self, event):
        if (type(event) is not dict or set(event) != {'operation', 'spec'}
                or event['operation'] not in ('start', 'advance', 'result')):
            return {'status': 'unauthorized'}
        try:
            spec = self.scope(event['spec'])
            item = self.db.get_item(TableName=self.table, Key=key('CHECK#' + spec['job_id'], 'SNAPSHOT'),
                ConsistentRead=True).get('Item')
            saved = native({k: DE.deserialize(v) for k, v in item.items()}) if item else None
            if saved and saved.get('spec') != spec:
                raise JobDenied('Wrong job owner')
            if not saved:
                if event['operation'] != 'start':
                    raise JobDenied('Unknown check')
                snapshot = self.snapshot(spec)
                Observation(spec, snapshot)  # Validate before persisting.
                row = {'pk': 'CHECK#' + spec['job_id'], 'sk': 'SNAPSHOT', 'spec': spec, 'snapshot': snapshot}
                try:
                    self.db.put_item(TableName=self.table, Item=encoded(row), ConditionExpression='attribute_not_exists(pk)')
                    saved = row
                except self.db.exceptions.ConditionalCheckFailedException:
                    return self.serve(event)
            snapshot = saved['snapshot']
            observer = Observation(spec, snapshot)
            def ready(value):
                # A changed public IP must never send an HTTP probe to the old
                # address. Fixed command inputs are retained for this job.
                return self.snapshot(value) == snapshot
            jobs = CommandJobs(self.db, self.table, self.ssm, observer.command, ready,
                finish_observation=observer.finish)
            if event['operation'] == 'start':
                view = jobs.enqueue(spec)
                view = jobs.advance(spec)
            elif event['operation'] == 'advance':
                view = jobs.advance(spec)
            else:
                view = jobs.current(spec)  # Viewing cannot launch a command.
            answer = {'status': 'ok', 'job': view}
            if view['phase'] == 'report_ready':
                report = jobs.retained_report(spec)
                validate_report(report, spec['instances'])
                answer['result'] = {'task_id': spec['task_id'], 'checked_at': report['checked_at'],
                    'request_id': report['request_id'], 'checks': [{'id': c['id'], 'status': c['status']} for c in report['checks']],
                    'score': score(report), 'saved_grade_changed': False}
            return answer
        except JobBusy:
            return {'status': 'busy'}
        except JobDenied:
            return {'status': 'unavailable'}
        except Exception:
            return {'status': 'unavailable'}


def handler(event, context):
    try:
        import boto3
        session = boto3.session.Session(region_name='us-east-1')
        return StudentChecker(json.loads(os.environ['CHECK_CONFIG']), session.client('dynamodb'),
            os.environ['CHECK_TABLE'], *(session.client(n) for n in ('sts', 'cloudformation', 'ec2')),
            no_retry_ssm(session)).serve(event)
    except Exception:
        return {'status': 'unavailable'}
