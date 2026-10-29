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
                "await import('./router.mjs'); await import('./grade-client.mjs'); await import('./secrets.mjs')"],
                cwd=Path(directory) / 'contents', capture_output=True, text=True, check=True)

    def test_template_defaults_closed_and_keeps_secret_out_of_outputs(self):
        template = json.loads((package.HERE / 'portal-web.template.json').read_text(encoding='utf-8'))
        self.assertEqual(template['Parameters']['PortalMode']['Default'], 'closed')
        self.assertNotIn('GoogleClientSecret', template['Parameters'])
        variables = template['Resources']['Revision']['Properties']['ServiceConfig']['EnvironmentVariables']
        self.assertNotIn('GOOGLE_CLIENT_SECRET', variables)
        self.assertEqual(variables['PORTAL_GOOGLE_OAUTH_SECRET_ARN'], {'Ref': 'GoogleOAuthSecretArn'})
        self.assertEqual(template['Resources']['Endpoint']['Properties']['AuthType'], 'ApplicationManaged')
        self.assertEqual(template['Resources']['Portal']['Properties']['FunctionName'], {'Ref': 'WebFunctionName'})
        endpoint = template['Resources']['Endpoint']['Properties']
        # AWS provider's deployed schema requires at least two environments;
        # the supported positive request-rate values start at 100.
        self.assertEqual(endpoint['ScalingConfig']['MaxEnvironments'], 2)
        self.assertEqual(endpoint['ThrottleConfig']['RateLimit'], 100)
        self.assertFalse(any(r['Type'].startswith('AWS::IAM::') for r in template['Resources'].values()))

    def test_artifact_service_grant_is_scoped_to_one_same_account_function(self):
        template = json.loads((package.HERE / 'web-artifacts.template.json').read_text(encoding='utf-8'))
        resources = template['Resources']
        self.assertEqual({v['Type'] for v in resources.values()}, {'AWS::S3::Bucket', 'AWS::S3::BucketPolicy'})
        props = resources['ArtifactBucket']['Properties']
        self.assertTrue(all(props['PublicAccessBlockConfiguration'].values()))
        self.assertEqual(props['VersioningConfiguration']['Status'], 'Enabled')
        statement = resources['LambdaCodeReadPolicy']['Properties']['PolicyDocument']['Statement'][0]
        self.assertEqual(statement['Principal'], {'Service':'lambda.amazonaws.com'})
        self.assertEqual(set(statement['Action']), {'s3:GetObject','s3:GetObjectVersion'})
        self.assertEqual(statement['Resource'], {'Fn::Sub':'${ArtifactBucket.Arn}/portal/*'})
        self.assertEqual(statement['Condition']['StringEquals']['aws:SourceAccount'], {'Ref':'AWS::AccountId'})
        self.assertTrue(statement['Condition']['ArnLike']['aws:SourceArn']['Fn::Sub'].endswith('web-function/${WebFunctionName}/revision/*'))


if __name__ == '__main__':
    unittest.main()
