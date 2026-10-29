import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock
from zipfile import ZipFile

from test_grade_reader import GradeTest
from test_status_gateway import GatewayTest
from teacher_probe_handler import serve
import build_teacher_probe as package


class ProbeTest(unittest.TestCase):
    def setUp(self):
        self.f = GradeTest('test_saved_score_and_unknown_current_use_existing_projection')
        self.f.setUp()
        self.env = {'LAB_ID': 'test-lab', 'STUDENT_ACCOUNT': '123456789012', 'DEPLOYMENT_ID': 'same'}
        self.client = Mock()

    def test_grade_survives_unreachable_student_and_preserves_unknown(self):
        self.client.invoke.side_effect = RuntimeError('student offline')
        before = copy.deepcopy(self.f.row)
        result = serve({'operation': 'grade'}, self.env, self.f.store, self.client)
        self.assertEqual(result['grade']['raw_earned'], 62)
        self.assertIn('M5', result['grade']['current_unresolved'])
        self.assertNotIn('token_hash', json.dumps(result))
        self.assertEqual(self.f.row, before)
        self.client.invoke.assert_not_called()

    def test_status_checks_retained_ids_in_actual_connector_shape(self):
        gateway = GatewayTest('test_registered_identity_invokes_only_fixed_function_and_reads_five')
        gateway.setUp()
        self.f.row['instances'] = gateway.instances
        payload = json.dumps({'status': 'ok', 'observation': gateway.observation}).encode()
        self.client.invoke.return_value = {'StatusCode': 200, 'Payload': io.BytesIO(payload)}
        result = serve({'operation': 'status'}, self.env, self.f.store, self.client)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(len(result['observation']['instances']), 5)
        self.assertEqual(self.client.invoke.call_args.kwargs['FunctionName'], gateway.arn)

    def test_browser_supplied_lab_or_start_is_never_accepted(self):
        for request in ({'operation': 'start'}, {'operation': 'grade', 'lab_id': 'other'}, {'subject': '1234'}):
            self.assertEqual(serve(request, self.env, self.f.store, self.client), {'status': 'unauthorized'})
        self.assertEqual(self.f.store.labs_calls, [])
        self.client.invoke.assert_not_called()

    def test_wrong_deployment_never_invokes_or_projects(self):
        self.env['DEPLOYMENT_ID'] = 'other'
        self.assertEqual(serve({'operation': 'grade'}, self.env, self.f.store, self.client), {'status': 'unavailable'})
        self.assertEqual(self.f.store.labs_calls, [])
        self.client.invoke.assert_not_called()

    def test_probe_package_is_reproducible_loadable_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory)/'a.zip', Path(directory)/'b.zip'
            self.assertEqual(package.build(a), package.build(b))
            with self.assertRaises(FileExistsError): package.build(a)
            with ZipFile(a) as archive:
                self.assertEqual(archive.read('assessment-registry.json'), package.FILES['assessment-registry.json'].read_bytes())
                archive.extractall(Path(directory)/'contents')
            subprocess.run([sys.executable, '-B', '-c', 'import teacher_probe_handler'], cwd=Path(directory)/'contents',
                           capture_output=True, text=True, check=True)
        template = json.loads((package.HERE/'teacher-probe.template.json').read_text())
        self.assertEqual([v['Type'] for v in template['Resources'].values()], ['AWS::Lambda::Function'])
        self.assertNotIn('Permission', json.dumps(template))
