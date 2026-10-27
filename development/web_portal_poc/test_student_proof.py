import importlib.util
import unittest
from urllib.parse import parse_qs, urlsplit

import identity_proof
import student_proof

HAS_BOTOCORE = importlib.util.find_spec('botocore') is not None


@unittest.skipUnless(HAS_BOTOCORE, 'botocore required for actual signing test')
class SignerTests(unittest.TestCase):
    def test_real_botocore_signer_produces_valid_short_lived_proof(self):
        from botocore.credentials import Credentials
        class Session:
            def get_credentials(self):
                return Credentials('EXAMPLE', 'synthetic-secret', 'synthetic-token')
        nonce = 'a' * 64
        url = student_proof.create_proof(Session(), nonce)
        parsed = urlsplit(url)
        values = parse_qs(parsed.query)
        self.assertEqual(parsed.hostname, identity_proof.HOST)
        self.assertEqual(values['X-Amz-SignedHeaders'], ['host;x-jdu-nonce'])
        self.assertEqual(values['X-Amz-Expires'], ['60'])
        self.assertTrue(identity_proof.validate(url, nonce).startswith('/?'))
        self.assertNotIn('synthetic-secret', url)

    def test_no_credentials_rejected(self):
        class Session:
            def get_credentials(self):
                return None
        with self.assertRaises(ValueError):
            student_proof.create_proof(Session(), 'a' * 64)


class InputTests(unittest.TestCase):
    def test_invalid_nonce_rejected_before_request(self):
        with self.assertRaises(ValueError):
            student_proof.create_proof(None, 'bad-nonce')


if __name__ == '__main__':
    unittest.main()
