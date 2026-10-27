from datetime import datetime, timezone
from urllib.parse import urlencode
import unittest

import identity_proof as proof

NOW = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
NONCE = 'a' * 64
ACCOUNT = '123456789012'


def url(**overrides):
    params = {'Action': 'GetCallerIdentity', 'Version': '2011-06-15',
              'X-Amz-Algorithm': 'AWS4-HMAC-SHA256',
              'X-Amz-Credential': 'EXAMPLE/20261027/us-east-1/sts/aws4_request',
              'X-Amz-Date': '20261027T100000Z', 'X-Amz-Expires': '60',
              'X-Amz-SignedHeaders': 'host;x-jdu-nonce', 'X-Amz-Signature': 'b' * 64}
    params.update(overrides)
    return 'https://' + proof.HOST + '/?' + urlencode(params)


class Store:
    def __init__(self):
        self.pending = True

    def is_pending(self, nonce, session, account):
        return self.pending and (nonce, session, account) == (NONCE, 'session', ACCOUNT)

    def consume(self, nonce, session, account):
        valid = self.is_pending(nonce, session, account)
        self.pending = False
        return valid


class IdentityProofTests(unittest.TestCase):
    def test_one_time_identity_verification(self):
        store = Store()
        observed = []
        def fetch(path, nonce):
            observed.append((path, nonce))
            return ACCOUNT
        self.assertEqual(proof.verify(url(), NONCE, 'session', ACCOUNT, store, now=NOW, fetch=fetch), ACCOUNT)
        self.assertEqual(len(observed), 1)
        with self.assertRaises(proof.ProofError):
            proof.verify(url(), NONCE, 'session', ACCOUNT, store, now=NOW, fetch=fetch)
        self.assertEqual(len(observed), 1)

    def test_wrong_account_does_not_consume(self):
        store = Store()
        with self.assertRaises(proof.ProofError):
            proof.verify(url(), NONCE, 'session', ACCOUNT, store, now=NOW, fetch=lambda *_: '999999999999')
        self.assertTrue(store.pending)

    def test_rejects_bad_endpoint_parameters_and_expiry(self):
        cases = [url().replace(proof.HOST, 'evil.example'),
                 url().replace(proof.HOST, proof.HOST + '@evil.example'),
                 url().replace('https://', 'http://'),
                 url() + '&Action=GetCallerIdentity',
                 url(**{'X-Amz-SignedHeaders': 'host'}),
                 url(**{'X-Amz-Expires': '61'}),
                 url(**{'X-Amz-Credential': 'EXAMPLE/20261027/us-west-2/sts/aws4_request'}),
                 url(**{'Action': 'AssumeRole'}),
                 url(**{'X-Amz-Date': '20261027T095800Z'})]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(proof.ProofError):
                    proof.validate(case, NONCE, NOW)

    def test_wrong_session_does_not_call_sts(self):
        with self.assertRaises(proof.ProofError):
            proof.verify(url(), NONCE, 'another-session', ACCOUNT, Store(), now=NOW,
                         fetch=lambda *_: self.fail('unexpected network call'))


if __name__ == '__main__':
    unittest.main()
