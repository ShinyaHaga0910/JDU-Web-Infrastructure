import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import build_status_package as package


class StatusPackageTest(unittest.TestCase):
    def test_reproducible_package_loads_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'a.zip', Path(directory) / 'b.zip'
            self.assertEqual(package.build(first), package.build(second))
            with self.assertRaises(FileExistsError): package.build(first)
            with ZipFile(first) as archive:
                self.assertEqual(set(archive.namelist()), set(package.FILES))
                archive.extractall(Path(directory) / 'contents')
            subprocess.run([sys.executable, '-B', '-c', 'import student_status_handler'],
                           cwd=Path(directory) / 'contents', capture_output=True, text=True, check=True)

    def test_only_teacher_role_may_invoke_the_new_function(self):
        template = json.loads((package.HERE / 'student-status.template.json').read_text(encoding='utf-8'))
        resources = template['Resources']
        self.assertEqual({v['Type'] for v in resources.values()}, {'AWS::Lambda::Function', 'AWS::Lambda::Permission'})
        permission = resources['TeacherInvokePermission']['Properties']
        self.assertEqual(permission['Action'], 'lambda:InvokeFunction')
        self.assertEqual(permission['Principal'], {'Ref': 'TeacherRoleArn'})
        self.assertNotIn('FunctionUrlAuthType', permission)
        self.assertIn('role/LabRole', template['Parameters']['TeacherRoleArn']['AllowedPattern'])
