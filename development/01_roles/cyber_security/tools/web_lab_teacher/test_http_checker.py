import copy
import gzip
import http.server
import io
import json
from pathlib import Path
import tarfile
import threading
import unittest
import uuid

from bootstrap_submission_guest import validate
from build_checker_bundle import bundle
from http_task import CHECKS, build_report, contract, http_probe
from install_checker_bundle import checked_archive


class HTTPFixture(http.server.BaseHTTPRequestHandler):
    mode = 'correct'
    def do_GET(self):
        task = 'P1' if self.path.startswith('/practice.txt?') else 'M1'
        if self.mode == 'practice_only' and task == 'M1':
            self.send_response(404); self.end_headers(); return
        self.send_response(302 if self.mode == 'redirect' else 200)
        if self.mode == 'redirect': self.send_header('Location', '/practice.txt')
        self.end_headers()
        self.wfile.write(('wrong\n' if self.mode == 'wrong' else contract(task)['body']).encode())
    def log_message(self, *_): pass


class HTTPCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), HTTPFixture)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
    def probe(self, task, mode):
        HTTPFixture.mode = mode; spec = contract(task)
        return http_probe('127.0.0.1', spec['path'], spec['body'], uuid.uuid4().hex, self.server.server_port)
    def test_real_http_accepts_exact_response(self):
        self.assertTrue(self.probe('P1', 'correct')); self.assertTrue(self.probe('M1', 'correct'))
    def test_wrong_body_and_redirect_fail(self):
        self.assertIs(self.probe('M1', 'wrong'), False); self.assertIs(self.probe('P1', 'redirect'), False)
    def test_practice_success_does_not_complete_mission(self):
        self.assertTrue(self.probe('P1', 'practice_only')); self.assertIs(self.probe('M1', 'practice_only'), False)
    def test_report_scope_unknown_and_prerequisite_failure(self):
        state = dict(lab_id='fixture', deployment_id=str(uuid.uuid4()), release_id='web-2026-10-r1')
        nodes = {r: dict(instance_id='i-' + str(i)*17) for i,r in enumerate(['bastion','web','dns','db','repo'],1)}
        observed = dict(state, mission_id='M1', instance_id=nodes['web']['instance_id'], checks=dict.fromkeys(CHECKS, True))
        observed['checks']['WEB02_PUBLIC_HTTP'] = None
        observed['checks']['WEB02_REPO_PREREQUISITE'] = False
        report = build_report(observed, state, nodes, str(uuid.uuid4()))
        validate(report, dict(state, role='bastion', instances={r:n['instance_id'] for r,n in nodes.items()}))
        self.assertEqual([c['status'] for c in report['checks']].count('UNKNOWN'),1)
        self.assertEqual([c['status'] for c in report['checks']].count('FAIL'),1)
        self.assertNotIn('points', report)
        report['mission_id']='M2'
        with self.assertRaises(ValueError): validate(report, dict(state, role='bastion'))
    def test_foreign_node_and_missing_checks_rejected(self):
        s=dict(lab_id='fixture',deployment_id=str(uuid.uuid4()),release_id='web-2026-10-r1')
        n={'web':{'instance_id':'i-'+'1'*17}}
        o=dict(s,mission_id='P1',instance_id='i-'+'2'*17,checks=dict.fromkeys(CHECKS,True))
        with self.assertRaises(ValueError): build_report(o,s,n,str(uuid.uuid4()))
        o['instance_id']=n['web']['instance_id'];o['checks'].pop('WEB02_CONFIG_VALID')
        with self.assertRaises(ValueError): build_report(o,s,n,str(uuid.uuid4()))


class CheckerBundleTests(unittest.TestCase):
    def test_deterministic_exact_public_inventory(self):
        a,m=bundle(Path(__file__).resolve().parent); b,_=bundle(Path(__file__).resolve().parent)
        self.assertEqual(a,b); files,actual=checked_archive(a); self.assertEqual(m,actual)
        self.assertEqual(files['fixtures/mission.txt'],contract('M1')['body'].encode())
        self.assertFalse(any('credentials' in n or 'private' in n for n in files))
    def bad_archive(self,name,link=False):
        out=io.BytesIO()
        with tarfile.open(fileobj=out,mode='w') as tar:
            i=tarfile.TarInfo(name);i.size=1
            if link:i.type=tarfile.SYMTYPE;i.linkname='/tmp/escape'
            tar.addfile(i,io.BytesIO(b'x'))
        return gzip.compress(out.getvalue(),mtime=0)
    def test_traversal_links_and_duplicates_rejected(self):
        for name,link in [('jdu-web-checker/../escape',False),('/tmp/escape',False),('jdu-web-checker/link',True)]:
            with self.subTest(name=name), self.assertRaises(ValueError):checked_archive(self.bad_archive(name,link))
        a,_=bundle(Path(__file__).resolve().parent);out=io.BytesIO()
        with tarfile.open(fileobj=out,mode='w') as dest,tarfile.open(fileobj=io.BytesIO(a),mode='r:gz') as src:
            entries=src.getmembers()
            for m in entries+[entries[0]]: dest.addfile(m,src.extractfile(m))
        with self.assertRaises(ValueError):checked_archive(gzip.compress(out.getvalue(),mtime=0))
    def test_modified_file_rejected(self):
        a,_=bundle(Path(__file__).resolve().parent);out=io.BytesIO()
        with tarfile.open(fileobj=out,mode='w') as dest,tarfile.open(fileobj=io.BytesIO(a),mode='r:gz') as src:
            for m in src:
                raw=src.extractfile(m).read()
                if m.name.endswith('/http_task.py'):raw+=b'\n# tamper\n'
                m.size=len(raw);dest.addfile(m,io.BytesIO(raw))
        with self.assertRaises(ValueError):checked_archive(gzip.compress(out.getvalue(),mtime=0))


if __name__ == '__main__':unittest.main()
