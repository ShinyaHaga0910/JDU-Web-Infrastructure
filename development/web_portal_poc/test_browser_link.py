from contextlib import redirect_stdout,redirect_stderr
import copy
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

import boto3
import identity_proof
import browser_link_handler as link
import build_browser_link_template as builder


class BrowserLinkTest(unittest.TestCase):
    def setUp(self):
        self.account='123456789012'
        self.stack=f'arn:aws:cloudformation:us-east-1:{self.account}:stack/jdu-web-link-test-lab-aaaaaaaaaaaa/12345678-1234-1234-1234-123456789012'
        self.origin='https://abcdefghijklmnop.gpb.lambda-web.us-east-1.on.aws'
        self.env={'STUDENT_ACCOUNT':self.account,'LAB_ID':'test-lab','BOOTSTRAP_STACK_ID':self.stack,'PORTAL_ORIGIN':self.origin}
        self.event={'RequestType':'Create','StackId':self.stack,'RequestId':'synthetic-request-id',
            'LogicalResourceId':'LinkAccount','ResourceType':'Custom::JduPortalAccountLink',
            'ResponseURL':'https://cloudformation-custom-resource-response-useast1.s3.us-east-1.amazonaws.com/callback?X-Amz-Signature=private-callback-canary',
            'ResourceProperties':{'ServiceToken':'private-helper-arn','PairId':'a'*64,'ExpectedAccount':self.account,'LabId':'test-lab','ServiceTimeout':'60'}}
        self.session=Mock()
        self.session.client.return_value.get_caller_identity.return_value={'Account':self.account}
        self.sign=Mock(return_value='private-sts-proof-canary')
        self.post,self.reply=Mock(),Mock()

    def serve(self,event=None,**options):
        return link.serve(event or self.event,self.env,self.session,sign=self.sign,post=self.post,reply=self.reply,**options)

    def test_create_uses_signed_body_and_only_sends_generic_cloudformation_receipt(self):
        out,err=io.StringIO(),io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):result=self.serve()
        self.assertEqual(result,{'status':'ok'})
        self.post.assert_called_once_with(self.origin,'a'*64,'private-sts-proof-canary')
        body=self.reply.call_args.args[1]
        self.assertEqual(body['Status'],'SUCCESS')
        self.assertTrue(body['NoEcho'])
        self.assertEqual(body['Data'],{})
        for canary in ('private-sts-proof-canary','private-callback-canary','a'*64):
            self.assertNotIn(canary,json.dumps(body)+out.getvalue()+err.getvalue())
        self.assertEqual(self.session.client.call_args.args,('sts',))
        self.assertEqual(self.session.client.call_args.kwargs['config'].read_timeout,5)

    def test_delete_and_update_never_reenroll_revoke_or_touch_aws_resources(self):
        for operation in ('Delete','Update'):
            event={**self.event,'RequestType':operation,'ResourceProperties':{'PairId':'expired'}}
            self.assertEqual(self.serve(event),{'status':'ok'})
            self.assertEqual(self.reply.call_args.args[1]['Status'],'SUCCESS')
        self.session.client.assert_not_called()
        self.sign.assert_not_called()
        self.post.assert_not_called()

    def test_wrong_account_and_failed_transport_are_generic_failures_without_proof_replay(self):
        self.session.client.return_value.get_caller_identity.return_value={'Account':'987654321098'}
        self.assertEqual(self.serve(),{'status':'unavailable'})
        self.sign.assert_not_called();self.post.assert_not_called()
        self.assertEqual(self.reply.call_args.args[1]['Status'],'FAILED')
        self.session.client.return_value.get_caller_identity.return_value={'Account':self.account}
        self.post.side_effect=RuntimeError('private-upstream-canary')
        self.assertEqual(self.serve(),{'status':'unavailable'})
        self.assertNotIn('private-upstream-canary',json.dumps(self.reply.call_args.args[1]))

    def test_bad_envelopes_and_ssrf_callbacks_have_no_network_or_aws_calls(self):
        for changes in ({'StackId':self.stack+'x'},{'ResourceType':'Custom::Other'},{'LogicalResourceId':'Other'},
                        {'ResponseURL':'https://evil.example/callback?credential=canary'},
                        {'ResponseURL':self.event['ResponseURL'].replace('https:','http:')},
                        {'ResponseURL':self.event['ResponseURL'].replace('.com/','.com.evil.example/')},
                        {'ResponseURL':'https://cloudformation-custom-resource-response-useast1.s3.amazonaws.com:443/path?x=1'}):
            self.assertEqual(self.serve({**self.event,**changes}),{'status':'unauthorized'})
        self.session.client.assert_not_called();self.reply.assert_not_called();self.post.assert_not_called()

    def test_invalid_resource_properties_are_rejected_before_identity_signature(self):
        for changes in ({'PairId':'invalid'},{'ExpectedAccount':'987654321098'},{'LabId':'other-lab'},
                        {'ServiceTimeout':'3600'},{'proof_url':'private-canary'}):
            event=copy.deepcopy(self.event);event['ResourceProperties'].update(changes)
            self.assertEqual(self.serve(event),{'status':'unavailable'})
        self.sign.assert_not_called();self.post.assert_not_called()

    def test_https_posts_never_redirect_and_keep_proof_out_of_url_and_cf_response(self):
        connection=Mock()
        response=connection.getresponse.return_value
        response.status=200;response.read.return_value=b'{"registered":true}'
        with patch.object(link.http.client,'HTTPSConnection',return_value=connection) as factory:
            link.post_proof(self.origin,'a'*64,'proof-canary')
            args=connection.request.call_args
            self.assertEqual(args.args,('POST','/api/enrollment/complete'))
            self.assertEqual(json.loads(args.kwargs['body']),{'pair_id':'a'*64,'proof_url':'proof-canary'})
            self.assertEqual(factory.call_args.args,('abcdefghijklmnop.gpb.lambda-web.us-east-1.on.aws',))
            response.status=302
            with self.assertRaises(ValueError):link.post_proof(self.origin,'a'*64,'proof-canary')
            self.assertEqual(factory.call_count,2) # One connection per call; no redirect request.
        for origin in ('https://evil.example',self.origin+'/path',self.origin+'?secret=canary'):
            with self.assertRaises(ValueError):link.portal_origin(origin)

    def test_inline_bundle_uses_the_real_existing_sdk_signer_and_preserves_nonce_protocol(self):
        source=builder.inline_source()
        scope={'__name__':'index'}
        exec(compile(source,'index.py','exec'),scope)
        session=boto3.Session(aws_access_key_id='EXAMPLE',aws_secret_access_key='synthetic-secret-only',
                             aws_session_token='synthetic-session-token',region_name='us-east-1')
        proof=scope['create_proof'](session,'a'*64)
        path=identity_proof.validate(proof,'a'*64,datetime.now(timezone.utc))
        self.assertIn('X-Amz-SignedHeaders=host%3Bx-jdu-nonce',path)
        self.assertIn('X-Amz-Expires=60',path)
        self.assertNotIn('synthetic-secret-only',proof)
        event=self.event
        result=scope['serve'](event,self.env,self.session,sign=self.sign,post=self.post,reply=self.reply)
        self.assertEqual(result,{'status':'ok'})

    def test_template_is_reproducible_read_only_and_has_no_credential_parameters(self):
        template=builder.template(self.origin)
        self.assertEqual({v['Type'] for v in template['Resources'].values()},
            {'AWS::Lambda::Function','AWS::Logs::LogGroup','Custom::JduPortalAccountLink'})
        self.assertEqual(set(template['Parameters']),{'PairId','ExpectedAccount','LabId'})
        self.assertEqual(template['Resources']['AccountLink']['Properties']['Role'],{'Fn::Sub':'arn:aws:iam::${ExpectedAccount}:role/LabRole'})
        source=template['Resources']['AccountLink']['Properties']['Code']['ZipFile']
        self.assertEqual(template['Metadata']['JduSourceSHA256'],hashlib.sha256(source.encode()).hexdigest())
        self.assertFalse(any(s in source for s in ('start_instances(', 'stop_instances(', 'send_command(', 'put_item(')))
        with tempfile.TemporaryDirectory() as directory:
            a,b=Path(directory)/'a.json',Path(directory)/'b.json'
            self.assertEqual(builder.build(a,self.origin),builder.build(b,self.origin))
            self.assertLess(a.stat().st_size,51200)
            with self.assertRaises(FileExistsError):builder.build(a,self.origin)

    def test_artifact_policy_is_read_only_for_one_account_one_hash_and_no_public_grant(self):
        template=json.loads((builder.HERE/'browser-link-artifacts.template.json').read_text())
        bucket=template['Resources']['BootstrapBucket']['Properties']
        self.assertTrue(all(bucket['PublicAccessBlockConfiguration'].values()))
        self.assertEqual(bucket['VersioningConfiguration']['Status'],'Enabled')
        policy=template['Resources']['AssignedStudentRead']['Properties']['PolicyDocument']['Statement'][0]
        self.assertEqual(policy['Principal'],{'AWS':{'Fn::Sub':'arn:aws:iam::${StudentAccount}:root'}})
        self.assertEqual(set(policy['Action']),{'s3:GetObject','s3:GetObjectVersion'})
        self.assertEqual(policy['Resource'],{'Fn::Sub':'${BootstrapBucket.Arn}/bootstrap/${TemplateDigest}/account-link.template.json'})
        self.assertEqual(policy['Condition'],{'Bool':{'aws:SecureTransport':'true'}})


if __name__=='__main__':unittest.main()
