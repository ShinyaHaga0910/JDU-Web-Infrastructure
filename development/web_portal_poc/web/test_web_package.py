import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import build_web_package as package


class WebPackageTest(unittest.TestCase):
    def test_reproducible_package_loads_and_excludes_tests_and_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'a.zip', Path(directory) / 'b.zip'
            self.assertEqual(package.build(first), package.build(second))
            with self.assertRaises(FileExistsError): package.build(first)
            with ZipFile(first) as archive:
                names = set(archive.namelist())
                self.assertTrue(set(package.SOURCE) <= names)
                self.assertIn('node_modules/jose/package.json', names)
                self.assertIn('node_modules/@aws-sdk/client-lambda/package.json', names)
                self.assertFalse(any(name.startswith('.env') or name.endswith('.test.mjs') for name in names))
                archive.extractall(Path(directory) / 'contents')
            subprocess.run(['node', '--input-type=module', '-e',
                "await import('./router.mjs'); await import('./grade-client.mjs')"],
                cwd=Path(directory) / 'contents', capture_output=True, text=True, check=True)

    def test_template_defaults_closed_and_keeps_secret_out_of_outputs(self):
        template = json.loads((package.HERE / 'portal-web.template.json').read_text(encoding='utf-8'))
        self.assertEqual(template['Parameters']['PortalMode']['Default'], 'closed')
        self.assertTrue(template['Parameters']['GoogleClientSecret']['NoEcho'])
        self.assertNotIn('GoogleClientSecret', json.dumps(template['Outputs']))
        self.assertEqual(template['Resources']['Endpoint']['Properties']['AuthType'], 'ApplicationManaged')
        self.assertFalse(any(r['Type'].startswith('AWS::IAM::') for r in template['Resources'].values()))


if __name__ == '__main__':
    unittest.main()
