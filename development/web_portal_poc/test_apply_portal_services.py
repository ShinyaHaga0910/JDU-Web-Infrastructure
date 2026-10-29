import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from apply_portal_services import apply
from prepare_portal_services import ACCOUNT, STACK, ADDITIONS


class ApplyTest(unittest.TestCase):
    def fixture(self, directory):
        root=Path(directory)
        template=(Path(__file__).parent/'portal-services.template.json').read_bytes()
        (root/'portal-services.template.json').write_bytes(template)
        code=b'synthetic-source-only-package'
        parameters={'ArtifactBucket':'synthetic-bucket','ArtifactKey':'private/code.zip','ArtifactVersion':'v1'}
        plan={'account':ACCOUNT,'stack_name':STACK,'phase':'change-set-ready-not-executed','stack_id':'stack-id',
            'change_set_id':'change-id','parameters':parameters,'template_sha256':hashlib.sha256(template).hexdigest(),
            'code_sha256':hashlib.sha256(code).hexdigest()}
        receipt=root/'services.private.ready.json'
        receipt.write_text(json.dumps(plan),encoding='utf-8')
        sts,cfn,s3,lam=[Mock() for _ in range(4)]
        sts.get_caller_identity.return_value={'Account':ACCOUNT}
        change={'Status':'CREATE_COMPLETE','ExecutionStatus':'AVAILABLE','StackId':'stack-id',
            'Parameters':[{'ParameterKey':k,'ParameterValue':v} for k,v in parameters.items()],
            'Changes':[{'ResourceChange':{'Action':'Add','LogicalResourceId':k,'ResourceType':v}} for k,v in ADDITIONS.items()]}
        cfn.describe_change_set.return_value=change
        cfn.get_template.return_value={'TemplateBody':json.loads(template)}
        cfn.describe_stacks.return_value={'Stacks':[{'Outputs':[{'OutputKey':k,'OutputValue':v} for k,v in
            {'EnrollmentArn':'private-enroller','GradeReaderArn':'private-reader','SubjectKeySecretArn':'secret-arn-only'}.items()]}]}
        s3.get_object.return_value={'Body':io.BytesIO(code)}
        lam.get_function_configuration.return_value={'State':'Active','Role':f'arn:aws:iam::{ACCOUNT}:role/LabRole',
            'CodeSha256':base64.b64encode(hashlib.sha256(code).digest()).decode()}
        return receipt,[sts,cfn,s3,lam],change

    def test_final_execution_is_single_use_and_does_not_read_or_disclose_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt,clients,_=self.fixture(directory)
            apply(receipt,clients)
            clients[1].execute_change_set.assert_called_once()
            self.assertEqual(clients[3].get_function_configuration.call_count,2)
            outcome=json.loads((Path(directory)/'services-created.private.json').read_text())
            self.assertFalse(outcome['web_enrollment_enabled'])
            self.assertFalse(outcome['student_approvals_created'])
            with self.assertRaises(ValueError): apply(receipt,clients)
            clients[1].execute_change_set.assert_called_once()

    def test_changed_template_parameters_or_code_prevent_execution(self):
        for target in ('template','parameters','code'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as directory:
                receipt,clients,change=self.fixture(directory)
                if target=='template': (Path(directory)/'portal-services.template.json').write_text('{}')
                if target=='parameters': change['Parameters'].append({'ParameterKey':'unexpected','ParameterValue':'other'})
                if target=='code': clients[2].get_object.return_value={'Body':io.BytesIO(b'changed')}
                with self.assertRaises(ValueError): apply(receipt,clients)
                clients[1].execute_change_set.assert_not_called()
                self.assertFalse((Path(directory)/'apply-requested.private.json').exists())


if __name__=='__main__': unittest.main()
