from datetime import datetime, timedelta, timezone
import unittest

from build_student_tools import payload_location, teacher_endpoint


class TeacherEndpointBindingTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,20,8,tzinfo=timezone.utc)
        self.facts=dict(scope='teacher_endpoint_public_facts',account='123456789012',
            class_id=193548,region='us-east-1',checked_at=self.now.isoformat(),
            api_base_url='https://abcdefghij.execute-api.us-east-1.amazonaws.com',
            fixed_ingress_ipv4='1.1.1.1',https_health_verified=True)

    def check(self,facts):
        return teacher_endpoint(facts,'123456789012',193548,self.now)

    def test_reviewed_endpoint_replaces_previous_class(self):
        self.assertEqual(self.check(self.facts),dict(ipv4='1.1.1.1',
            fqdn='abcdefghij.execute-api.us-east-1.amazonaws.com',submit_path='/api/web/submit'))

    def test_other_account_class_or_unverified_health_rejected(self):
        for key,value in [('account','144753397193'),('class_id',188571),
                          ('https_health_verified',False),('region','us-west-2')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.check(dict(self.facts,**{key:value}))

    def test_expired_future_or_undated_facts_rejected(self):
        for value in [(self.now-timedelta(hours=25)).isoformat(),
                      (self.now+timedelta(seconds=1)).isoformat(),'2026-10-20T08:00:00']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.check(dict(self.facts,checked_at=value))

    def test_wrong_destinations_or_private_ip_rejected(self):
        for value in ['https://example.com','http://abcdefghij.execute-api.us-east-1.amazonaws.com',
                      self.facts['api_base_url']+'/path',self.facts['api_base_url']+'?token=fixture',
                      'https://user@abcdefghij.execute-api.us-east-1.amazonaws.com',
                      'https://abcdefghij.execute-api.us-east-1.amazonaws.com:443']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.check(dict(self.facts,api_base_url=value))
        with self.assertRaises(ValueError):
            self.check(dict(self.facts,fixed_ingress_ipv4='10.20.1.10'))

    def test_payload_relocation_preserves_accepted_bytes_and_account(self):
        accepted=dict(bundle_sha256='a'*64,bundle_size_bytes=741180532)
        facts=dict(scope='teacher_payload_public_facts',account='123456789012',class_id=193548,
            region='us-east-1',checked_at=self.now.isoformat(),private_bucket='reviewed-teacher-payload',
            object_key='candidate/v7/repo-bundle.tar.gz',signed_tree_verified=True,**accepted)
        def verify(value):
            return payload_location(value,'123456789012',193548,self.now,accepted)
        self.assertEqual(verify(facts)['private_bucket'],'reviewed-teacher-payload')
        for key,value in [('account','144753397193'),('class_id',188571),
                          ('bundle_sha256','b'*64),('bundle_size_bytes',1),
                          ('signed_tree_verified',False),('object_key','../repo-bundle.tar.gz'),
                          ('object_key','candidate//repo-bundle.tar.gz'),
                          ('private_bucket','https://example.com'),
                          ('checked_at',(self.now-timedelta(days=2)).isoformat())]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                verify(dict(facts,**{key:value}))


if __name__=='__main__':unittest.main()
