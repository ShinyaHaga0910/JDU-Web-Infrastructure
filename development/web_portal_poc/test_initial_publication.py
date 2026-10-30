import copy
import json
from pathlib import Path
import unittest

import prepare_initial_publication as publication
import test_initial_package as packages
import build_initial_worker as builder


class InitialPublicationTest(unittest.TestCase):
    def setUp(self):
        self.base=json.loads((Path(publication.__file__).parent/'browser-link-artifacts.template.json').read_bytes())
        self.parameters={'StudentAccount':publication.STUDENT,'TemplateDigest':'b'*64,'PublicationId':'b'*12}

    def test_only_existing_policy_gains_one_exact_worker_read(self):
        proposed=publication.proposal(self.base,self.parameters,'a'*64)
        self.assertEqual(proposed['Resources']['BootstrapBucket'],self.base['Resources']['BootstrapBucket'])
        expected=copy.deepcopy(self.base)
        expected['Parameters']['WorkerDigest']=proposed['Parameters']['WorkerDigest']
        expected['Resources']['AssignedStudentRead']['Properties']['PolicyDocument']['Statement'].append(
            proposed['Resources']['AssignedStudentRead']['Properties']['PolicyDocument']['Statement'][-1])
        self.assertEqual(proposed,expected)
        grant=publication.statement('same-private-bucket',worker='a'*64)
        self.assertEqual(grant['Resource'],'arn:aws:s3:::same-private-bucket/worker/'+'a'*64+'/initial-worker.zip')
        self.assertEqual(grant['Action'],['s3:GetObject','s3:GetObjectVersion'])
        self.assertEqual(grant['Principal'],{'AWS':'arn:aws:iam::'+publication.STUDENT+':root'})
        self.assertEqual(len(self.base['Resources']['AssignedStudentRead']['Properties']['PolicyDocument']['Statement']),1)

    def test_other_account_or_source_policy_change_cannot_be_overwritten(self):
        for changes in ({'StudentAccount':'123456789012'},{'PublicationId':'c'*12},{'TemplateDigest':'not-a-digest'}):
            with self.assertRaises(ValueError):publication.proposal(self.base,{**self.parameters,**changes},'a'*64)
        modified=copy.deepcopy(self.base)
        modified['Resources']['AssignedStudentRead']['Properties']['PolicyDocument']['Statement'][0]['Action'].append('s3:PutObject')
        with self.assertRaises(ValueError):publication.proposal(modified,self.parameters,'a'*64)

    def test_change_set_cannot_add_resources_or_modify_other_properties(self):
        row={'Action':'Modify','LogicalResourceId':'AssignedStudentRead','ResourceType':'AWS::S3::BucketPolicy',
             'Replacement':'False','Details':[{'Target':{'Name':'PolicyDocument'}}]}
        def value():return {'Status':'CREATE_COMPLETE','ExecutionStatus':'AVAILABLE','Changes':[{'ResourceChange':copy.deepcopy(row)}]}
        publication.inspect(value())
        for changes in ({'Action':'Add'},{'LogicalResourceId':'BootstrapBucket'},{'Replacement':'True'},
                        {'Details':[{'Target':{'Name':'Bucket'}}]},{'Details':[]}):
            v=value();v['Changes'][0]['ResourceChange'].update(changes)
            with self.assertRaises(ValueError):publication.inspect(v)
        v=value();v['Changes']*=2
        with self.assertRaises(ValueError):publication.inspect(v)

    def test_worker_template_accepts_existing_same_owner_versioned_bucket_only(self):
        fixture=packages.InitialPackageTest('test_template_has_fixed_three_functions_and_one_teacher_role_no_public_url')
        fixture.setUp();self.addCleanup(fixture.doCleanups)
        code={**fixture.code,'S3Bucket':'jdu-web-portal-bootstrap-'+fixture.teacher+'-'+'b'*12}
        result=builder.template(fixture.f.grant,fixture.origin,fixture.teacher,code)
        self.assertEqual(result['Resources']['AccountLink']['Properties']['Code'],code)
        for changes in ({'S3Bucket':'jdu-web-portal-bootstrap-222222222222-'+'b'*12},{'S3ObjectVersion':'null'}):
            with self.assertRaises(ValueError):builder.template(fixture.f.grant,fixture.origin,fixture.teacher,{**code,**changes})


if __name__=='__main__':unittest.main()
