"""Experimental DynamoDB one-time challenge storage; no AWS resources created.

The caller must obtain the session, account, lab and connector identifiers from
an already authenticated and authorized enrollment flow, never a browser claim.
"""
import hashlib
import re
import secrets
import time

import identity_proof


def _hash(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 512:
        raise ValueError('invalid challenge context')
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class ChallengeStore:
    def __init__(self, client, table, lab_id, connector_id, *, clock=time.time):
        if not isinstance(lab_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', lab_id):
            raise ValueError('invalid lab')
        self.client, self.table, self.clock = client, table, clock
        self.lab_id, self.connector_digest = lab_id, _hash(connector_id)

    def issue(self, session, account, lifetime=60):
        if not isinstance(account, str) or not identity_proof.ACCOUNT.fullmatch(account):
            raise ValueError('invalid account')
        if type(lifetime) is not int or not 1 <= lifetime <= 60:
            raise ValueError('invalid lifetime')
        nonce = secrets.token_hex(32)
        item = {'pk': {'S': 'CHALLENGE#' + _hash(nonce)}, 'sk': {'S': 'IDENTITY'},
                'session': {'S': _hash(session)}, 'account': {'S': account},
                'lab': {'S': self.lab_id}, 'connector': {'S': self.connector_digest},
                'expires_at': {'N': str(int(self.clock()) + lifetime)}, 'used': {'BOOL': False}}
        self.client.put_item(TableName=self.table, Item=item, ConditionExpression='attribute_not_exists(pk)')
        return nonce

    def _key(self, nonce):
        if not isinstance(nonce, str) or not identity_proof.NONCE.fullmatch(nonce):
            raise ValueError('invalid challenge')
        return {'pk': {'S': 'CHALLENGE#' + _hash(nonce)}, 'sk': {'S': 'IDENTITY'}}

    def is_pending(self, nonce, session, account):
        row = self.client.get_item(TableName=self.table, Key=self._key(nonce), ConsistentRead=True).get('Item', {})
        try:
            return (row['session']['S'] == _hash(session) and row['account']['S'] == account
                    and row['lab']['S'] == self.lab_id and row['connector']['S'] == self.connector_digest
                    and row['used']['BOOL'] is False and int(row['expires_at']['N']) > int(self.clock()))
        except (KeyError, TypeError, ValueError):
            return False

    def consume(self, nonce, session, account):
        try:
            self.client.update_item(
                TableName=self.table, Key=self._key(nonce),
                UpdateExpression='SET #used=:true',
                ConditionExpression=('#used=:false AND #expires>:now AND #session=:session '
                                     'AND #account=:account AND #lab=:lab AND #connector=:connector'),
                ExpressionAttributeNames={'#used': 'used', '#expires': 'expires_at', '#session': 'session',
                                          '#account': 'account', '#lab': 'lab', '#connector': 'connector'},
                ExpressionAttributeValues={':true': {'BOOL': True}, ':false': {'BOOL': False},
                    ':now': {'N': str(int(self.clock()))}, ':session': {'S': _hash(session)},
                    ':account': {'S': account}, ':lab': {'S': self.lab_id},
                    ':connector': {'S': self.connector_digest}})
            return True
        except self.client.exceptions.ConditionalCheckFailedException:
            return False
