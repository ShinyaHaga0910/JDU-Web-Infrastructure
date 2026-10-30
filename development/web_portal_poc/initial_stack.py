"""R1 student-side five-node create adapter (not yet publicly enabled).

The future IAM worker constructs this with signature-verified deployment files
and the teacher-confirmed assignment. Neither is taken from a browser body.
Reuse the CLI parameter builder/AMI/budget checks. Password hashing and the
post-create SSM/SSH/grading stages are separate, still-required R1 work.
"""
from datetime import datetime, timezone
import hashlib
import json
import re
from types import SimpleNamespace

from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from portal_enrollment import EnrollmentDenied, encoded, key, grant_digest
from portal_preparation import checked_assignment


class InitialStack:
    def __init__(self, verified, assignment, db, table, cfn, ec2, sts, iam, s3, *, clock):
        self.verified, self.grant = verified, checked_assignment(assignment)
        self.db, self.table, self.cfn, self.ec2 = db, table, cfn, ec2
        self.sts, self.iam, self.s3, self.clock = sts, iam, s3, clock
        self.name = 'jdu-web-' + self.grant['lab_id']
        self.pk = 'INITIAL#' + self.grant['deployment_id']
        # A lost CreateStack response must not trigger a silent SDK retry.
        retries = cfn.meta.config.retries or {}
        if retries.get('total_max_attempts') != 1 and retries.get('max_attempts') != 0:
            raise EnrollmentDenied('Create client must disable automatic retries')

    def checked_files(self):
        release, manifest = self.grant['release'], self.verified['manifest']
        template = self.verified['files']['template'].read_bytes()
        expires = datetime.fromisoformat(manifest['expires_at'].replace('Z', '+00:00'))
        if (expires.tzinfo is None or self.clock() >= min(expires.timestamp(), release['expires_at'])
                or manifest['region'] != 'us-east-1' or manifest['release_id'] != release['release_id']
                or self.verified['manifest_sha256'] != release['manifest_sha256']
                or hashlib.sha256(template).hexdigest() != release['template_sha256']):
            raise EnrollmentDenied('Assigned signed release changed or expired')
        parsed = json.loads(template)
        instances = {k: r for k, r in parsed['Resources'].items() if r['Type'] == 'AWS::EC2::Instance'}
        if set(instances) != {r + 'Instance' for r in ('Bastion', 'Web', 'Dns', 'Db', 'Repo')}:
            raise EnrollmentDenied('Exactly the reviewed five-node foundation is required')
        roots = []
        for resource in instances.values():
            props = resource['Properties']
            volumes = props.get('BlockDeviceMappings', [])
            if (props.get('IamInstanceProfile') != 'LabInstanceProfile' or len(volumes) != 1
                    or volumes[0].get('Ebs', {}).get('Encrypted') is not True):
                raise EnrollmentDenied('All-five SSM and encrypted original roots required')
            roots.append(volumes[0]['Ebs']['VolumeSize'])
        if sorted(roots) != [8, 16, 16, 24, 32]:
            raise EnrollmentDenied('Reviewed 96 GiB foundation required')
        return template

    def saved(self):
        item = self.db.get_item(TableName=self.table, Key=key(self.pk, 'CREATE'), ConsistentRead=True).get('Item')
        row = {k: TypeDeserializer().deserialize(v) for k, v in item.items()} if item else None
        if row and (row.get('grant_digest') != grant_digest(self.grant) or row.get('stack_name') != self.name):
            raise EnrollmentDenied('Existing create request retained')
        return row

    def stack(self):
        try:
            stacks = self.cfn.describe_stacks(StackName=self.name)['Stacks']
        except ClientError as exc:
            error = exc.response.get('Error', {})
            if error.get('Code') == 'ValidationError' and error.get('Message') == f'Stack with id {self.name} does not exist':
                return None
            raise EnrollmentDenied('Stack observation unavailable') from None
        if len(stacks) != 1:
            raise EnrollmentDenied('Stack observation unavailable')
        return stacks[0]

    def current(self):
        """Read only. No absent-stack observation can issue another create."""
        row = self.saved()
        if not row:
            return {'stage': 'NOT_REQUESTED', 'resources_created': False}
        actual = self.stack()
        if not actual:
            return {'stage': 'CREATE_OBSERVATION_REQUIRED', 'resources_created': None}
        expected = {'LabId': self.grant['lab_id'], 'DeploymentId': self.grant['deployment_id'],
                    'JduPortalManifestSHA256': self.grant['release']['manifest_sha256']}
        tags = {t['Key']: t['Value'] for t in actual.get('Tags', [])}
        params = {p['ParameterKey']: p.get('ParameterValue') for p in actual.get('Parameters', [])}
        stack_id = actual.get('StackId', '')
        if (not re.fullmatch(r'arn:aws:cloudformation:us-east-1:' + self.grant['account']
                            + ':stack/' + self.name + r'/[a-f0-9-]{36}', stack_id)
                or any(tags.get(k) != v for k, v in expected.items())
                or params.get('LabId') != self.grant['lab_id']
                or params.get('DeploymentId') != self.grant['deployment_id']):
            raise EnrollmentDenied('Existing stack identity differs; retain it')
        template = self.cfn.get_template(StackName=stack_id, TemplateStage='Original')['TemplateBody']
        if isinstance(template, str):
            template = json.loads(template)
        if template != json.loads(self.verified['files']['template'].read_bytes()):
            raise EnrollmentDenied('Existing stack template differs; retain it')
        return {'stage': 'STACK_OBSERVED', 'stack_id': stack_id, 'stack_status': actual['StackStatus'],
                'stack_created': True, 'resources_created': None, 'lab_ready': False}

    def create(self, plan, password_hash):
        """One explicit confirmed request, using an ephemeral SHA512-crypt hash.

        This private worker primitive never hashes/stores a plaintext password,
        never overwrites a stack, and never repairs/deletes existing resources.
        """
        if self.saved():
            return self.current()
        template = self.checked_files()
        if (not isinstance(password_hash, str)
                or not re.fullmatch(r'\$6\$[A-Za-z0-9./]{1,16}\$[A-Za-z0-9./]{86}', password_hash)):
            raise EnrollmentDenied('RDP password hash required')
        expected = {k: self.grant[k] for k in ('account', 'lab_id', 'deployment_id')}
        expected.update(stack_name=self.name, region='us-east-1', release_id=self.grant['release']['release_id'],
                        manifest_sha256=self.grant['release']['manifest_sha256'],
                        template_sha256=self.grant['release']['template_sha256'])
        age = self.clock() - datetime.fromisoformat(plan['planned_at']).timestamp()
        if (any(plan.get(k) != v for k, v in expected.items()) or not 0 <= age <= 86400
                or self.sts.get_caller_identity()['Account'] != self.grant['account']):
            raise EnrollmentDenied('Plan or student account changed')
        if self.stack() is not None:
            raise EnrollmentDenied('Existing stack retained')
        # These are the actual existing CLI functions, not a second set of
        # five-node parameters. The worker package must include this controller.
        from student_controller import existing_nodes, budget_check, deployment_parameters, bootstrap_url
        from web_lab import check_ami
        if not budget_check(existing_nodes(self.ec2))['within_pilot_budget']:
            raise EnrollmentDenied('Existing servers retained; resource budget exceeded')
        check_ami(self.verified['manifest'], self.ec2.describe_images(ImageIds=[self.verified['manifest']['ami']['id']]))
        keys = self.ec2.describe_key_pairs(KeyNames=[plan['key_name']], IncludePublicKey=True)['KeyPairs']
        if len(keys) != 1 or ' '.join(keys[0]['PublicKey'].split()[:2]) != plan['student_public_key']:
            raise EnrollmentDenied('Academy public key changed')
        profile = self.iam.get_instance_profile(InstanceProfileName='LabInstanceProfile')['InstanceProfile']
        if profile['InstanceProfileName'] != 'LabInstanceProfile' or len(profile['Roles']) != 1:
            raise EnrollmentDenied('Existing Academy instance profile required')
        from prepare_teacher_probe import tls_control
        manifest = self.verified['manifest']
        tls_control(plan['s3_probe_ipv4'], 's3.us-east-1.amazonaws.com', '/')
        tls_control(plan['direct_api_probe_ipv4'], manifest['grading']['fqdn'], '/healthz', True)
        tls_control(manifest['grading']['ipv4'], manifest['grading']['fqdn'], '/healthz', True)
        url = bootstrap_url(self.verified, SimpleNamespace(bootstrap_url_file=None), self.s3)
        values = deployment_parameters(self.verified, plan, template, url)
        values['RdpPasswordHash'] = password_hash
        if not budget_check(existing_nodes(self.ec2))['within_pilot_budget']:
            raise EnrollmentDenied('Resource budget changed; existing servers retained')
        # Only public facts go to the durable journal. No password/hash, signed
        # bundle URL, template UserData or raw SDK exception is persisted.
        row = {'pk': self.pk, 'sk': 'CREATE', 'stage': 'CREATE_INTENT', 'stack_name': self.name,
               'grant_digest': grant_digest(self.grant), 'created_at': int(self.clock()),
               'client_request_token': 'portal-' + self.grant['deployment_id'], 'initial_state': 'foundation_only'}
        try:
            self.db.put_item(TableName=self.table, Item=encoded(row), ConditionExpression='attribute_not_exists(pk)')
        except self.db.exceptions.ConditionalCheckFailedException:
            return self.current()
        try:
            response = self.cfn.create_stack(StackName=self.name, TemplateBody=template.decode('utf-8'),
                Parameters=[{'ParameterKey': k, 'ParameterValue': v} for k, v in values.items()],
                DisableRollback=True, ClientRequestToken=row['client_request_token'],
                Tags=[{'Key': k, 'Value': v} for k, v in {
                    'LabId': self.grant['lab_id'], 'DeploymentId': self.grant['deployment_id'],
                    'JduPortalManifestSHA256': self.grant['release']['manifest_sha256']}.items()])
        except Exception:
            # The intent is retained even if AWS's acceptance is unknown.
            # The browser can observe the same stack; it cannot create another.
            return {'stage': 'CREATE_OBSERVATION_REQUIRED', 'resources_created': None}
        finally:
            password_hash = url = values = None
        return {'stage': 'CREATE_REQUESTED', 'stack_id': response['StackId'], 'resources_created': None, 'lab_ready': False}
