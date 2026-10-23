import json
from pathlib import Path
import tempfile
import unittest
from diagnose_rdp_login import inspect_root,userdata


class RdpReportSafetyTests(unittest.TestCase):
    def test_report_categorizes_auth_failure_without_exporting_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            files={'etc/passwd':'labuser:x:1001:1001::/home/labuser:/bin/bash\n',
                'etc/shadow':'labuser:$6$FixtureSalt$'+'A'*86+':20000:0:99999:7:::\n',
                'etc/group':'labuser:x:1001:\n',
                'etc/xrdp/sesman.ini':'[Security]\nAlwaysGroupCheck=false\nTerminalServerUsers=tsusers\n',
                'etc/pam.d/xrdp-sesman':'@include common-auth\n@include common-account\n@include common-session\n',
                'var/lib/jdu-web/initial/private.json':json.dumps({'rdp_hash':'$6$FixtureSalt$'+'A'*86,'token':'FAKE-SENSITIVE-TOKEN'}),
                'home/labuser/.xsession':'exec dbus-run-session -- startxfce4\n',
                'var/log/xrdp-sesman.log':'[20261016-10:01:02] pam_authenticate failed: 7 FAKE-SENSITIVE-TOKEN\n[20261016-10:01:03] login failed for user labuser\n'}
            for name,value in files.items():
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(value)
            report=inspect_root(root);encoded=json.dumps(report)
            self.assertTrue(report['shadow_matches_bootstrap']);self.assertFalse(report['shadow_locked'])
            self.assertFalse(report['account_expired']);self.assertFalse(report['password_expired'])
            self.assertEqual(report['logs']['var/log/xrdp-sesman.log']['counts'],{'pam_authentication_failed':1,'login_failed':1})
            self.assertEqual(report['logs']['var/log/xrdp-sesman.log']['last_events'][0]['pam_error_code'],7)
            for secret in ['FAKE-SENSITIVE-TOKEN','FixtureSalt','A'*86,'pam_authenticate failed']:
                self.assertNotIn(secret,encoded)

    def test_guest_requires_unmounted_explicit_clone_and_read_only_no_journal(self):
        import base64,gzip,re
        text=userdata('vol-0123456789abcdef0').decode()
        encoded=re.search(r"b64decode\('([^']+)'\)",text)[1]
        source=gzip.decompress(base64.b64decode(encoded)).decode()
        compile(source,'fixture-guest','exec')
        self.assertIn("'ro,noload'",source)
        self.assertIn("raise ValueError('Target clone already mounted')",source)
        self.assertIn("CLONE='vol-0123456789abcdef0'",source)
        self.assertNotIn('chpasswd',source)


if __name__=='__main__':unittest.main()
