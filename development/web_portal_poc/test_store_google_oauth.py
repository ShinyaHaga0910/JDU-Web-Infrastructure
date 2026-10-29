import json
import unittest
from types import SimpleNamespace

from store_google_oauth import preflight, store, StorageError

ACCOUNT = '123456789012'
CLIENT = '123456789012-example.apps.googleusercontent.com'
ORIGIN = 'https://example.on.aws'
NAME = 'jdu/web-portal/class-test/google-oauth'
SECRET = 'GOCSPX-' + 'a' * 32
TOKEN = 'b' * 32


class Missing(Exception):
    pass


class Secrets:
    exceptions = SimpleNamespace(ResourceNotFoundException=Missing)
    def __init__(self, exists=False):
        self.exists, self.writes, self.reads = exists, [], []
    def describe_secret(self, **kwargs):
        if not self.exists:
            raise Missing()
        return {'Name': NAME}
    def create_secret(self, **kwargs):
        self.writes.append(kwargs)
        return {'ARN': f'arn:aws:secretsmanager:us-east-1:{ACCOUNT}:secret:{NAME}-abc123', 'VersionId': TOKEN}
    def get_secret_value(self, **kwargs):
        self.reads.append(kwargs)
        return {'VersionId': TOKEN, 'SecretString': self.writes[-1]['SecretString']}


class StoreTest(unittest.TestCase):
    def test_owner_check_and_existing_secret_never_overwrite(self):
        for account, exists in [('000000000000', False), (ACCOUNT, True)]:
            api = Secrets(exists)
            sts = SimpleNamespace(get_caller_identity=lambda: {'Account': account})
            with self.assertRaises(StorageError):
                preflight(sts, api, ACCOUNT, CLIENT, ORIGIN, NAME)
            self.assertEqual(api.writes, [])

    def test_new_secret_roundtrip_receipt_excludes_values_and_uses_exact_version(self):
        api = Secrets()
        preflight(SimpleNamespace(get_caller_identity=lambda: {'Account': ACCOUNT}), api, ACCOUNT, CLIENT, ORIGIN, NAME)
        receipt = store(api, ACCOUNT, CLIENT, ORIGIN, NAME, SECRET, TOKEN)
        self.assertTrue(receipt['readback_verified'])
        self.assertNotIn(SECRET, json.dumps(receipt))
        self.assertNotIn('ResourcePolicy', api.writes[0])
        self.assertNotIn('KmsKeyId', api.writes[0])
        self.assertEqual(api.reads[0]['VersionId'], TOKEN)
        self.assertEqual(json.loads(api.writes[0]['SecretString'])['redirect_uri'], ORIGIN + '/auth/callback')

    def test_invalid_target_or_secret_is_rejected_without_write(self):
        for origin, secret in [('http://example.on.aws', SECRET), (ORIGIN + '/x', SECRET),
                               (ORIGIN + '?token=x', SECRET), (ORIGIN, SECRET + '\n')]:
            api = Secrets()
            with self.assertRaises(StorageError):
                store(api, ACCOUNT, CLIENT, origin, NAME, secret, TOKEN)
            self.assertEqual(api.writes, [])

    def test_wrong_readback_is_rejected_without_second_write(self):
        api = Secrets()
        api.get_secret_value = lambda **kwargs: {'VersionId': TOKEN, 'SecretString': '{}'}
        with self.assertRaises(StorageError):
            store(api, ACCOUNT, CLIENT, ORIGIN, NAME, SECRET, TOKEN)
        self.assertEqual(len(api.writes), 1)


if __name__ == '__main__':
    unittest.main()
