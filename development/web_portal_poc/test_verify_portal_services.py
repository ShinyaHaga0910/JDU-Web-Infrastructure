import base64
import hashlib
import io
import json
import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError
from prepare_portal_services import ACCOUNT,ADDITIONS
from verify_portal_services import verify


class VerifyTest(unittest.TestCase):
    def fixture(self):
        clients=[Mock() for _ in range(6)]
        sts,cfn,lam,secrets,db,ec2=clients
        sts.get_caller_identity.return_value={'Account':ACCOUNT}
        outputs={k:f'arn:aws:lambda:us-east-1:{ACCOUNT}:function:{k}' for k in ('EnrollmentArn','GradeReaderArn')}
        outputs['SubjectKeySecretArn']='synthetic-secret-arn'
        created={'phase':'private-services-created','stack_id':'synthetic-stack','outputs':outputs,'code_sha256':'a'*64}
        cfn.describe_stacks.return_value={'Stacks':[{'StackStatus':'CREATE_COMPLETE','Outputs':[
            {'OutputKey':k,'OutputValue':v} for k,v in outputs.items()]}]}
        cfn.list_stack_resources.return_value={'StackResourceSummaries':[
            {'LogicalResourceId':k,'ResourceType':v} for k,v in ADDITIONS.items()]}
        lam.get_function_configuration.return_value={'State':'Active','Role':f'arn:aws:iam::{ACCOUNT}:role/LabRole',
            'CodeSha256':base64.b64encode(bytes.fromhex('a'*64)).decode(),
            'Environment':{'Variables':{'GRADE_TABLE':'synthetic-grades','LAB_ID':'synthetic-lab'}}}
        error=ClientError({'Error':{'Code':'ResourceNotFoundException','Message':'synthetic'}},'GetFunctionUrlConfig')
        lam.get_function_url_config.side_effect=error
        lam.get_policy.side_effect=error
        secrets.describe_secret.return_value={'ARN':outputs['SubjectKeySecretArn'],'Name':'jdu/web-portal/class193548-20261029/subject-key'}
        baseline={'function_arn':'synthetic-probe','grade':{'raw_earned':62,'raw_maximum':62},
                  'partition_sha256':hashlib.sha256(b'[]').hexdigest()}
        db.get_paginator.return_value.paginate.return_value=[{'Items':[]}]
        def invoke(**kwargs):
            data={'status':'ok','grade':baseline['grade']} if kwargs['FunctionName']=='synthetic-probe' else {'status':'unauthorized'}
            return {'StatusCode':200,'Payload':io.BytesIO(json.dumps(data).encode())}
        lam.invoke.side_effect=invoke
        ec2.describe_instances.return_value={'Reservations':[{'Instances':[{'State':{'Name':'stopped'}}]}]}
        return created,baseline,clients

    def test_metadata_and_denials_are_verified_without_reading_secret_or_writing_grades(self):
        created,baseline,clients=self.fixture()
        result=verify(created,baseline,clients)
        self.assertTrue(result['whole_lab_partition_unchanged'])
        self.assertTrue(result['no_function_urls_or_resource_policies'])
        self.assertFalse(result['real_identity_enrollment_tested'])
        clients[3].get_secret_value.assert_not_called()
        clients[4].put_item.assert_not_called()
        clients[4].update_item.assert_not_called()

    def test_code_public_access_original_partition_and_denial_mismatch_fail(self):
        for field in ('code','policy','partition','denial'):
            with self.subTest(field=field):
                created,baseline,clients=self.fixture()
                if field=='code':created['code_sha256']='b'*64
                if field=='policy':clients[2].get_policy.side_effect=None
                if field=='partition':baseline['partition_sha256']='c'*64
                if field=='denial':clients[2].invoke.side_effect=lambda **_: {'StatusCode':200,'Payload':io.BytesIO(b'{"status":"ok"}')}
                with self.assertRaises(ValueError):verify(created,baseline,clients)
                clients[3].get_secret_value.assert_not_called()


if __name__=='__main__':unittest.main()
