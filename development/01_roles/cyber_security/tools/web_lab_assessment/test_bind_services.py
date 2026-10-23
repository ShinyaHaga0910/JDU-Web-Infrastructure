"""Actual captured BIND9 on loopback/high port. No host DNS or AWS changes."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import network_checks as dns
REAL_DIG = dns.dig

CACHE = Path.home() / '.cache/jdu-web-builds/2026-10-15'
TOOLS = CACHE / 'd11-bind-tools'
ENV = dict(os.environ, LD_LIBRARY_PATH=str(TOOLS / 'usr/lib/x86_64-linux-gnu'))
PORT = 55453


class BindIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (TOOLS / 'usr/sbin/named').is_file():
            raise RuntimeError('Extract the captured official Ubuntu BIND packages first')
        cls.temp = tempfile.TemporaryDirectory(prefix='jdu-d11-bind-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.config = cls.root / 'named.conf'
        zone = cls.root / 'lab.test.zone'
        zone.write_text('''$TTL 60
@ IN SOA dns.lab.test. hostmaster.lab.test. (1 60 60 3600 60)
@ IN NS dns.lab.test.
dns IN A 10.20.2.10
web IN A 10.20.1.20
admin IN A 10.20.1.20
db IN A 10.20.2.20
''')
        cls.config.write_text('acl "clients" { localhost; 10.20.1.10; 10.20.1.20; };\n'
            'options { directory "' + str(cls.root) + '"; listen-on port ' + str(PORT) + ' { 127.0.0.1; }; '
            'listen-on-v6 { none; }; allow-query { clients; }; allow-recursion { clients; }; '
            'allow-query-cache { clients; }; recursion yes; dnssec-validation no; '
            'forward only; forwarders { 10.20.0.2; }; pid-file "' + str(cls.root / 'pid') + '"; };\n'
            'controls {}; zone "lab.test" { type primary; file "' + str(zone) + '"; allow-transfer { none; }; };\n')
        subprocess.run([str(TOOLS / 'usr/bin/named-checkconf'), '-z', str(cls.config)], env=ENV,
            capture_output=True, check=True, timeout=10)
        cls.log = (cls.root / 'log').open('w')
        cls.process = subprocess.Popen([str(TOOLS / 'usr/sbin/named'), '-g', '-n', '1', '-4', '-c', str(cls.config)],
            env=ENV, stdout=cls.log, stderr=cls.log)
        cls.addClassCleanup(cls.close)
        for _ in range(40):
            answer = cls.query('web.lab.test')
            if answer and answer['status'] == 'NOERROR':
                break
            if cls.process.poll() is not None:
                raise RuntimeError('Local BIND exited before acceptance')
            time.sleep(.05)
        else:
            raise RuntimeError('Local BIND did not become ready')

    @classmethod
    def close(cls):
        if cls.process.poll() is None:
            cls.process.terminate()
            cls.process.wait(timeout=10)
        cls.log.close()

    @staticmethod
    def query(name, kind='A', **kwargs):
        def run(args, **options):
            return subprocess.run([str(TOOLS / 'usr/bin/dig'), *args[1:]], env=ENV,
                capture_output=True, text=True, timeout=8)
        with patch.object(dns, 'command', run):
            return REAL_DIG(name, kind, server='127.0.0.1', port=PORT, **kwargs)

    def test_udp_tcp_authoritative_records_and_wrong_answer(self):
        for tcp in (False, True):
            answer = self.query('web.lab.test', tcp=tcp)
            self.assertTrue(answer['authoritative'])
            self.assertEqual([r[4] for r in answer['answers'] if r[3] == 'A'], ['10.20.1.20'])
            with patch.object(dns, 'dig', side_effect=lambda name, **kw: self.query(name, tcp=kw['tcp'])):
                self.assertTrue(dns.required_records({'web.lab.test': '10.20.1.20', 'db.lab.test': '10.20.2.20'}, tcp=tcp))
                self.assertFalse(dns.required_records({'web.lab.test': '10.20.2.20'}, tcp=tcp))

    def test_zone_authority_and_authoritative_nxdomain(self):
        soa, ns, absent = self.query('lab.test', 'SOA'), self.query('lab.test', 'NS'), self.query('absent-d11.lab.test')
        self.assertTrue(soa['authoritative'] and ns['authoritative'] and absent['authoritative'])
        self.assertEqual(soa['answers'][0][4].split()[0], 'dns.lab.test.')
        self.assertEqual(ns['answers'][0][4], 'dns.lab.test.')
        self.assertEqual(absent['status'], 'NXDOMAIN')

    def test_transfer_is_explicitly_refused_by_actual_bind(self):
        self.assertIs(dns.axfr_refused('127.0.0.1', PORT), True)

    def test_policy_parser_accepts_real_normalized_named_output(self):
        result = subprocess.run([str(TOOLS / 'usr/bin/named-checkconf'), '-p', '-x', str(self.config)],
            env=ENV, capture_output=True, text=True, check=True, timeout=10)
        self.assertEqual(dns.named_policy(dns.named_blocks(result.stdout)), (True, True))

    def test_server_side_observations_use_localhost_without_expanding_client_acl(self):
        def run(args, **kwargs):
            if args[0] == 'dig':
                return subprocess.run([str(TOOLS / 'usr/bin/dig'), *args[1:]], env=ENV,
                    capture_output=True, text=True, timeout=8)
            return subprocess.run([str(TOOLS / 'usr/bin/named-checkconf'), *args[1:], str(self.config)],
                env=ENV, capture_output=True, text=True, timeout=10)
        real = dns.dig
        def query(name, kind='A', **kwargs):
            self.assertEqual(kwargs['server'], '127.0.0.1')
            # The rootless fixture has no AWS DNS upstream; all other traffic is real BIND.
            if name == 'aws.amazon.com':
                return None
            return real(name, kind, **kwargs)
        with patch.object(dns, 'command', run), patch.object(dns, 'dig', side_effect=query), \
                patch.object(dns, 'active', return_value=self.process.poll() is None):
            observed = dns.dns_server({'web.lab.test': '10.20.1.20', 'db.lab.test': '10.20.2.20'}, 'd11-nonce', port=PORT)
        self.assertIsNone(observed.pop('WEB03_FORWARD_ONLY'))
        self.assertTrue(all(v is True for v in observed.values()), observed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
