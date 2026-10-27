import copy
import unittest
from unittest.mock import Mock
from challenge_store import ChallengeStore


class ConditionalError(Exception):
    pass


class ChallengeStoreTest(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.exceptions.ConditionalCheckFailedException = ConditionalError
        self.store = ChallengeStore(self.client, 'test-table', 'test-lab', 'known-connector', clock=lambda: 1000)
        self.nonce = self.store.issue('session', '123456789012', 60)
        self.item = self.client.put_item.call_args.kwargs['Item']
        self.client.get_item.return_value = {'Item': copy.deepcopy(self.item)}

    def test_challenge_is_hashed_scoped_and_expires(self):
        self.assertNotIn(self.nonce, str(self.item))
        self.assertTrue(self.store.is_pending(self.nonce, 'session', '123456789012'))
        self.assertFalse(self.store.is_pending(self.nonce, 'another', '123456789012'))
        self.assertFalse(self.store.is_pending(self.nonce, 'session', '999999999999'))
        different_lab = ChallengeStore(self.client, 'test-table', 'other-lab', 'known-connector', clock=lambda: 1000)
        self.assertFalse(different_lab.is_pending(self.nonce, 'session', '123456789012'))
        self.store.clock = lambda: 1060
        self.assertFalse(self.store.is_pending(self.nonce, 'session', '123456789012'))

    def test_consume_uses_conditional_update_and_rejects_collision(self):
        self.assertTrue(self.store.consume(self.nonce, 'session', '123456789012'))
        request = self.client.update_item.call_args.kwargs
        for part in ('#used=:false', '#expires>:now', '#session=:session',
                     '#account=:account', '#lab=:lab', '#connector=:connector'):
            self.assertIn(part, request['ConditionExpression'])
        self.client.update_item.side_effect = ConditionalError()
        self.assertFalse(self.store.consume(self.nonce, 'session', '123456789012'))

    def test_context_and_lifetime_are_bounded(self):
        for lifetime in (0, 61, True):
            with self.assertRaises(ValueError):
                self.store.issue('session', '123456789012', lifetime)


if __name__ == '__main__':
    unittest.main()
