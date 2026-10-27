import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import build_grade_package as package


class PackageTest(unittest.TestCase):
    def test_package_is_reproducible_and_preserves_existing_grade_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'a.zip', Path(directory) / 'b.zip'
            self.assertEqual(package.build(first), package.build(second))
            with self.assertRaises(FileExistsError): package.build(first)
            with ZipFile(first) as archive:
                self.assertEqual(set(archive.namelist()), set(package.FILES))
                expected = package.FILES['assessment-registry.json'].read_bytes()
                self.assertEqual(archive.read('assessment-registry.json'), expected)
                archive.extractall(Path(directory) / 'contents')
            p = subprocess.run([sys.executable, '-B', '-c',
                'import identity_grade_handler,registry; print(registry.MAXIMUM,registry.CONTRACT_SHA256)'],
                cwd=Path(directory) / 'contents', capture_output=True, text=True, check=True)
            self.assertEqual(p.stdout.strip(), '62 ' + hashlib.sha256(expected).hexdigest())

    def test_template_has_no_public_endpoint_or_permission_change(self):
        template = json.loads((package.HERE / 'internal-grade.template.json').read_text(encoding='utf-8'))
        resources = template['Resources']
        self.assertEqual([value['Type'] for value in resources.values()], ['AWS::Lambda::Function'])
        self.assertEqual(resources['GradeReader']['Properties']['Handler'], 'identity_grade_handler.handler')
        self.assertNotIn('FunctionName', resources['GradeReader']['Properties'])
        self.assertNotIn('TracingConfig', resources['GradeReader']['Properties'])
