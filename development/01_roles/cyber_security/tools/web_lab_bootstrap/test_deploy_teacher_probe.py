"""CloudShell-only mocked SDK tests; no real requests or credentials."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,MagicMock

from botocore.exceptions import ClientError
import deploy_teacher_probe as deploy


class DeploymentSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.state=self.root/'state.json';self.template=self.root/'template.json';self.template.write_bytes(b'{"test":"fixture"}')
        self.plan={'stack_name':deploy.STACK,'region':'us-east-1','scope':'teacher_package_probe_only','account':'000000000000',
            'template_sha256':hashlib.sha256(self.template.read_bytes()).hexdigest(),'template_bytes':self.template.stat().st_size,
            'key_name':'fixture-key','student_public_key':'ssh-ed25519 AAAAFIXTURE','s3_probe_ipv4':'52.216.0.1','direct_api_probe_ipv4':'44.200.0.1',
            'availability_zone':'us-east-1a','lab_id':'teacher-fixture','deployment_id':'20a8c4ad-dc96-4e3a-bc90-249a498229fd','s3_prefix_list':'pl-0123456789abcdef0'}
        self.candidate={'scope':'signed_candidate_reassembled_not_os_acceptance','student_release_ready':False,
            'bucket':'jdu-web-capture-20261015-bf04d16eb603','key':'teacher-candidates/web-2026-10-r1/c2/repo-bundle.tar.gz',
            'bundle_size_bytes':100,'bundle_sha256':'b'*64}
        self.cfn=MagicMock();self.cfn.describe_stacks.side_effect=ClientError({'Error':{'Code':'ValidationError','Message':f'Stack with id {deploy.STACK} does not exist'}},'DescribeStacks')
        self.cfn.create_stack.return_value={'StackId':'fixture-stack-id'}
        self.ec2=MagicMock();self.ec2.describe_key_pairs.return_value={'KeyPairs':[{'PublicKey':self.plan['student_public_key']}]}
        self.s3=MagicMock();self.s3.head_object.return_value={'ContentLength':100,'Metadata':{'sha256':'b'*64}}
        self.s3.generate_presigned_url.return_value='https://fixture.invalid/?sensitive-signature'
        self.sts=MagicMock();self.sts.get_caller_identity.return_value={'Account':'000000000000'}
        self.clients={'sts':self.sts,'cloudformation':self.cfn,'ec2':self.ec2,'s3':self.s3}

    def invoke(self,passwords=None):
        (self.root/'plan.json').write_text(json.dumps(self.plan));(self.root/'candidate.json').write_text(json.dumps(self.candidate))
        argv=['deploy','--plan',str(self.root/'plan.json'),'--candidate',str(self.root/'candidate.json'),'--template',str(self.template),'--state',str(self.state),'--confirmed-public-access']
        stream=io.StringIO()
        with patch.object(deploy.sys,'argv',argv),patch.object(deploy.sys.stdin,'isatty',return_value=True),\
             patch.object(deploy.boto3,'client',side_effect=lambda name,**kw:self.clients[name]),\
             patch.object(deploy.getpass,'getpass',side_effect=passwords or ['fixture-password-2026']*2),\
             patch.object(deploy.subprocess,'run',return_value=MagicMock(stdout=b'$6$fixture$HASH\n')),\
             patch.object(deploy,'tls_control',return_value=200),contextlib.redirect_stdout(stream):
            deploy.main()
        return stream.getvalue()

    def test_password_mismatch_never_creates_or_saves(self):
        with self.assertRaises(ValueError):self.invoke(['fixture-password-A','fixture-password-B'])
        self.cfn.create_stack.assert_not_called();self.assertFalse(self.state.exists())

    def test_success_keeps_secrets_out_of_state_and_output(self):
        output=self.invoke();state=self.state.read_text()
        self.assertEqual(self.state.stat().st_mode&0o777,0o600)
        for secret in ('fixture-password-2026','$6$fixture$HASH','sensitive-signature'):
            self.assertNotIn(secret,output);self.assertNotIn(secret,state)
        parameters={v['ParameterKey']:v['ParameterValue'] for v in self.cfn.create_stack.call_args.kwargs['Parameters']}
        self.assertEqual(parameters['RdpPasswordHash'],'$6$fixture$HASH')
        self.assertEqual(parameters['ExpectedPayloadScope'],'package_only_candidate')
        self.assertFalse(json.loads(state)['class_ready'])

    def test_existing_state_never_repeats_creation(self):
        self.state.write_text('fixture-preserved')
        with self.assertRaises(ValueError):self.invoke()
        self.cfn.create_stack.assert_not_called();self.assertEqual(self.state.read_text(),'fixture-preserved')

    def test_template_change_never_creates(self):
        self.plan['template_sha256']='c'*64
        with self.assertRaises(ValueError):self.invoke()
        self.cfn.create_stack.assert_not_called()

    def test_denied_create_keeps_pending_state_for_diagnosis(self):
        self.cfn.create_stack.side_effect=ClientError({'Error':{'Code':'AccessDenied','Message':'fixture'}},'CreateStack')
        with self.assertRaises(ClientError):self.invoke()
        self.assertEqual(json.loads(self.state.read_text())['phase'],'CREATE_REQUEST_PENDING')


if __name__=='__main__':unittest.main()
