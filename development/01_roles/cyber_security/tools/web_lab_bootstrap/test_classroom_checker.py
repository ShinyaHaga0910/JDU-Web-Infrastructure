import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from classroom_checker import checker_archive, provision

ROOT = Path(__file__).resolve().parents[5]


class CheckerSetupTests(unittest.TestCase):
    def test_archive_contains_canonical_student_handler_and_entry_point(self):
        archive = checker_archive(lambda path: (ROOT / path).read_bytes())
        with ZipFile(BytesIO(archive)) as package:
            for name, source in (('index.py', 'student_checker_entry.py'),
                                 ('student_checker_handler.py', 'student_checker_handler.py')):
                self.assertEqual(package.read(name), (ROOT / 'development/web_portal_poc' / source).read_bytes())

    def test_creates_checker_then_refuses_to_rebind_it_to_another_teacher(self):
        cfn, ec2, functions = Mock(), Mock(), Mock()
        session = Mock()
        session.client.side_effect = {'cloudformation': cfn, 'ec2': ec2, 'lambda': functions}.__getitem__
        ec2.describe_instances.return_value = {'Reservations': [{'Instances': [
            {'PrivateIpAddress': '10.20.1.20', 'BlockDeviceMappings': [{'Ebs': {'VolumeId': 'vol-web'}}]}]}]}
        stack = {'StackId': 'checker', 'StackStatus': 'CREATE_COMPLETE'}

        def create(**values):
            stack['Parameters'] = values['Parameters']
            stack['Template'] = values['TemplateBody']
            return {'StackId': stack['StackId']}

        cfn.create_stack.side_effect = create
        cfn.describe_stacks.return_value = {'Stacks': [stack]}
        cfn.get_template.side_effect = lambda **value: {'TemplateBody':
            stack['Template'] if value['StackName'] == 'checker' else {'Resources': {}}}
        cfn.describe_stack_resource.return_value = {'StackResourceDetail': {
            'ResourceType': 'AWS::Lambda::Function', 'PhysicalResourceId': 'jdu-web-check-lab-demo'}}
        archive = b'example zip'
        code_hash = base64.b64encode(hashlib.sha256(archive).digest()).decode()
        functions.get_function_configuration.side_effect = [
            {'CodeSha256': 'old', 'RevisionId': 'revision-1'},
            {'CodeSha256': code_hash, 'Handler': 'index.handler'}]
        functions.invoke.return_value = {'Payload': BytesIO(b'{"status":"ready"}')}
        state = {'lab_id': 'lab-demo', 'stack_id': 'foundation'}
        source = lambda path: (ROOT / path).read_bytes()
        with patch('classroom_checker.checker_archive', return_value=archive):
            provision(session, Mock(return_value=None), source, state, {'web': 'i-web'}, 'key', '123456789012')
            with self.assertRaisesRegex(ValueError, 'CHECKER_STACK_IDENTITY'):
                provision(session, Mock(return_value=stack), source, state, {'web': 'i-web'}, 'key', '222222222222')
        functions.update_function_code.assert_called_once_with(
            FunctionName='jdu-web-check-lab-demo', ZipFile=archive, RevisionId='revision-1')
        cfn.create_stack.assert_called_once()
        self.assertNotIn('ArtifactBucket', json.loads(stack['Template'])['Parameters'])
