"""R1 package and narrow gateway checks; fixture release is not GPG-signed."""
import io
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile
from datetime import datetime,timezone

import test_initial_stack as fixtures
import build_initial_worker as builder
from build_controller_bundle import bundle
from initial_worker import runtime_files
from initial_gateway import InitialGateway
from portal_enrollment import EnrollmentDenied


class InitialPackageTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.InitialStackTest(methodName='test_double_click_and_status_only_observe_same_stack')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.initialize_sources()

    def initialize_sources(self):
        f = self.f
        root = f.path.parent
        self.manifest = root/'deployment-manifest.json'
        self.manifest.write_bytes((json.dumps(f.manifest)+'\n').encode())
        digest = hashlib.sha256(self.manifest.read_bytes()).hexdigest()
        f.grant['release']['manifest_sha256'] = f.verified['manifest_sha256'] = digest
        archive = root/'controller.tar.gz'
        archive.write_bytes(bundle(builder.BOOTSTRAP)[0])
        price = root/'prices.json'
        price.write_bytes(b'{"fixture":true}\n')
        f.verified.update(trusted_fingerprint=builder.FINGERPRINT)
        f.verified['files'].update(controller_bundle=archive, price_catalog=price,
            wrapper=builder.BOOTSTRAP/'web_lab.py', selector=builder.BOOTSTRAP.parent/'web_lab_instance_selector/select_instances.py')
        self.origin = 'https://abcdefghijklmnop.gpb.lambda-web.us-east-1.on.aws'
        self.teacher = '111111111111'
        self.code = {'S3Bucket':'jdu-web-portal-initial-'+self.teacher+'-'+'a'*12,
                     'S3Key':'worker/'+'a'*64+'/initial-worker.zip', 'S3ObjectVersion':'immutable-version-1'}
        sys.path.insert(0,str(builder.BOOTSTRAP.parent/'web_lab_assessment'))
        from candidate_install import checked_archive
        # Preserve the accepted archive's exact bytes. gzip OS headers differ
        # on Windows even when all app files and the tar payload are identical.
        accepted=builder.HERE.parent/'03_knowledge/aws_official/web_lab_packages_2026-10-15/web-course-class193548-20261023-r2/assessment.tar.gz'
        raw=accepted.read_bytes();assessment,manifest=checked_archive(raw)
        (root/'assessment.tar.gz').write_bytes(raw)
        course={'distribution_id':'synthetic-course-r3','core_manifest_sha256':digest,
            'expires_at':datetime.fromtimestamp(f.grant['release']['expires_at'],timezone.utc).isoformat(),
            'assessment_archive_sha256':hashlib.sha256(raw).hexdigest(),
            'assessment_manifest_sha256':hashlib.sha256(assessment['D11-MANIFEST.json']).hexdigest(),
            'contract_sha256':manifest['contract_sha256'],'raw_maximum':62,'distribution_ready':True,'class_ready':False}
        public=json.dumps(course).encode();(root/'course-release.json').write_bytes(public)
        self.course={'root':root,'release':course,'sha256':hashlib.sha256(public).hexdigest(),
            'fingerprint':builder.FINGERPRINT,'foundation':{'core':{'manifest_sha256':digest}}}

    def build(self, target):
        return builder.build_verified(target,self.manifest,self.f.verified,self.f.grant,self.course)

    def test_package_is_reproducible_uses_signed_controller_and_imports_on_linux_layout(self):
        root = self.f.path.parent
        a,b = root/'a.zip',root/'b.zip'
        self.assertEqual(self.build(a),self.build(b))
        with self.assertRaises(FileExistsError):self.build(a)
        with ZipFile(a) as archive:
            self.assertEqual(archive.read('student_controller.py'),(builder.BOOTSTRAP/'student_controller.py').read_bytes())
            self.assertEqual(archive.read('foundation.template.json'),self.f.path.read_bytes())
            self.assertNotIn('.env',archive.namelist())
            package=root/'package';archive.extractall(package)
        env={'STUDENT_ACCOUNT':self.f.grant['account'],'LAB_ID':self.f.grant['lab_id'],
             'INITIAL_DEPLOYMENT_ID':self.f.grant['deployment_id'],
             'INITIAL_PROGRESS_TABLE':'jdu-web-initial-'+self.f.grant['lab_id']+'-progress'}
        verified,grant=runtime_files(package,env)
        self.assertEqual(grant,self.f.grant)
        self.assertEqual(verified['files']['template'].read_bytes(),self.f.path.read_bytes())
        # The imported helpers need Linux fcntl, not an actual filesystem lock
        # in this import-only Windows check. No crypt/AWS call is made.
        code="import sys,types;sys.modules['fcntl']=types.SimpleNamespace();sys.modules['pwd']=types.SimpleNamespace();import initial_worker,initial_stack,initial_setup,initial_ssm,initial_registration_guest,initial_context,initial_teaching,initial_status_handler,initial_checker_handler,student_controller,web_lab,student_checker_handler;print('INITIAL_PACKAGE_IMPORT_OK')"
        result=subprocess.run([sys.executable,'-B','-c',code],cwd=package,capture_output=True,text=True,check=True)
        self.assertEqual(result.stdout.strip(),'INITIAL_PACKAGE_IMPORT_OK')

    def test_changed_manifest_template_runtime_files_and_assignment_are_rejected(self):
        f=self.f;root=f.path.parent
        original=self.manifest.read_bytes()
        self.manifest.write_bytes(original+b' ')
        with self.assertRaises(ValueError):self.build(root/'bad.zip')
        self.manifest.write_bytes(original)
        f.verified['trusted_fingerprint']='F'*40
        with self.assertRaises(ValueError):self.build(root/'bad.zip')
        f.verified['trusted_fingerprint']=builder.FINGERPRINT
        self.build(root/'good.zip')
        with ZipFile(root/'good.zip') as archive:archive.extractall(root/'package')
        env={'STUDENT_ACCOUNT':f.grant['account'],'LAB_ID':f.grant['lab_id'],'INITIAL_DEPLOYMENT_ID':f.grant['deployment_id'],
             'INITIAL_PROGRESS_TABLE':'jdu-web-initial-'+f.grant['lab_id']+'-progress'}
        (root/'package/teacher-price-catalog.json').write_text('{"changed":true}')
        with self.assertRaises(EnrollmentDenied):runtime_files(root/'package',env)

    def test_old_controller_without_bounded_sdk_collector_is_not_packaged(self):
        from controller_runtime import controller_files
        files=controller_files(self.f.verified['files']['controller_bundle'].read_bytes())
        files['inspect_teacher_probe.py']=b'def collect(state_path,template_path):\n    return {}\n'
        with patch.object(builder,'controller_files',return_value=files):
            with self.assertRaisesRegex(ValueError,'SDK collector contract'):
                self.build(self.f.path.parent/'old-controller.zip')
        self.assertFalse((self.f.path.parent/'old-controller.zip').exists())

    def test_missing_expired_or_mixed_signed_course_inputs_are_rejected(self):
        from datetime import timedelta
        with self.assertRaises(ValueError):builder.build_verified(self.f.path.parent/'missing.zip',self.manifest,self.f.verified,self.f.grant)
        import copy
        original=copy.deepcopy(self.course)
        for fields in ({'expires_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()},
                       {'core_manifest_sha256':'0'*64}):
            course=copy.deepcopy(original);course['release'].update(fields)
            raw=json.dumps(course['release']).encode();(self.f.path.parent/'course-release.json').write_bytes(raw)
            course['sha256']=hashlib.sha256(raw).hexdigest()
            with self.assertRaises(ValueError):builder.build_verified(self.f.path.parent/'rejected.zip',self.manifest,self.f.verified,self.f.grant,course)
        self.assertFalse((self.f.path.parent/'rejected.zip').exists())

    def test_template_has_fixed_three_functions_and_one_teacher_role_no_public_url(self):
        value=builder.template(self.f.grant,self.origin,self.teacher,self.code)
        self.assertEqual(len(value['Resources']),12)
        self.assertFalse(any(v['Type'].startswith('AWS::EC2') or v['Type'].startswith('AWS::IAM') for v in value['Resources'].values()))
        fn=value['Resources']['AccountLink']['Properties']
        self.assertEqual(fn['Runtime'],'python3.11')
        self.assertEqual(fn['Handler'],'initial_worker.handler')
        self.assertEqual(fn['Code'],self.code)
        self.assertEqual(value['Resources']['TeacherInitialInvoke']['Properties']['Principal'],'arn:aws:iam::'+self.teacher+':role/LabRole')
        self.assertNotIn('SourceAccount',value['Resources']['TeacherInitialInvoke']['Properties'])
        self.assertEqual(value['Parameters']['ExpectedAccount']['AllowedValues'],[self.f.grant['account']])
        self.assertEqual(value['Resources']['InitialProgress']['DeletionPolicy'],'Retain')
        self.assertEqual(value['Resources']['StudentStatus']['Properties']['Handler'],'initial_status_handler.handler')
        self.assertEqual(value['Resources']['StudentChecker']['Properties']['Handler'],'initial_checker_handler.handler')
        self.assertEqual(value['Resources']['CheckResults']['DeletionPolicy'],'Retain')
        for resource in value['Resources'].values():
            if resource['Type']=='AWS::Lambda::Permission':
                self.assertEqual(resource['Properties']['Principal'],'arn:aws:iam::'+self.teacher+':role/LabRole')
        self.assertNotIn('Password',json.dumps(value['Parameters']))
        for change in ({'S3ObjectVersion':'null'},{'S3Bucket':'another-owner'},{'S3Key':'mutable.zip'}):
            with self.assertRaises(ValueError):builder.template(self.f.grant,self.origin,self.teacher,{**self.code,**change})

    def test_gateway_selects_assigned_arn_only_and_projects_away_extra_fields(self):
        client=Mock()
        def reply():return {'StatusCode':200,'Payload':io.BytesIO(json.dumps({'status':'ok','initial':{
            'stage':'CREATE_REQUESTED','private_canary':'never-forward'}}).encode())}
        client.invoke.side_effect=lambda **kw:reply()
        gateway=InitialGateway(client)
        result=gateway(self.f.grant,'create',plan_digest='f'*64,password='DisposableFixtureOnly23',confirmation='DisposableFixtureOnly23')
        self.assertEqual(result,{'stage':'CREATE_REQUESTED'})
        self.assertEqual(client.invoke.call_args.kwargs['FunctionName'],'arn:aws:lambda:us-east-1:123456789012:function:jdu-web-initial-new-student')
        with self.assertRaises(EnrollmentDenied):gateway(self.f.grant,'terminate')
        client.invoke.return_value={}
        client.invoke.side_effect=lambda **kw:{'StatusCode':200,'FunctionError':'Unhandled','Payload':io.BytesIO(b'private-error-canary')}
        with self.assertRaisesRegex(RuntimeError,'^Initial worker unavailable$'):gateway(self.f.grant,'observe')


if __name__=='__main__':unittest.main()
