"""Prototype atomic association between an authorized Lab and an AWS account.

Not a public API. All grant fields must come from a previously authenticated,
authorized server-side enrollment, never directly from browser-supplied JSON.
The connector identifier is a pre-approved opaque identifier, not a URL.
"""
import re

import identity_proof
from challenge_store import ChallengeStore, _hash

ROLES = {'bastion', 'web', 'dns', 'db', 'repo'}
INSTANCE = re.compile(r'i-[0-9a-f]{17}\Z')


class EnrollmentError(ValueError):
    pass


def enroll(client, challenge, grade_table, grant, session, nonce, proof_url, *, now=None,
           fetch=identity_proof.fetch_sts):
    """Verify STS and atomically consume the challenge and establish a binding.

    Existing grade metadata is condition-checked only. All binding writes are
    to the separate challenge/binding table. This does not authorize connector
    URLs or establish an authenticated browser session.
    """
    account, lab = grant['account'], grant['lab_id']
    deployment, token_hash, nodes = grant['deployment_id'], grant['token_hash'], grant['instances']
    if (not isinstance(challenge, ChallengeStore) or challenge.lab_id != lab
            or not isinstance(account, str) or not identity_proof.ACCOUNT.fullmatch(account)
            or not isinstance(deployment, str) or not deployment
            or not isinstance(token_hash, str) or not re.fullmatch(r'[a-f0-9]{64}', token_hash)
            or not isinstance(nodes, dict) or set(nodes) != ROLES
            or any(not isinstance(v, str) or not INSTANCE.fullmatch(v) for v in nodes.values())
            or len(set(nodes.values())) != 5):
        raise EnrollmentError('invalid authorized context')
    path = identity_proof.validate(proof_url, nonce, now)
    if not challenge.is_pending(nonce, session, account):
        raise EnrollmentError('challenge unavailable')
    if fetch(path, nonce) != account:
        raise EnrollmentError('wrong AWS account')
    values = {':false': {'BOOL': False}, ':true': {'BOOL': True},
              ':now': {'N': str(int(challenge.clock()))}, ':session': {'S': _hash(session)},
              ':account': {'S': account}, ':lab': {'S': lab},
              ':connector': {'S': challenge.connector_digest}}
    context = {'account': {'S': account}, 'lab_id': {'S': lab}, 'deployment_id': {'S': deployment},
               'connector': {'S': challenge.connector_digest}}
    writes = [
        {'ConditionCheck': {
            'TableName': grade_table, 'Key': {'pk': {'S': 'LAB#' + lab}, 'sk': {'S': 'META'}},
            'ConditionExpression': '#active=:yes AND token_hash=:token AND deployment_id=:deployment AND #instances=:instances',
            'ExpressionAttributeNames': {'#active': 'active', '#instances': 'instances'},
            'ExpressionAttributeValues': {':yes': {'BOOL': True}, ':token': {'S': token_hash},
                ':deployment': {'S': deployment}, ':instances': {'M': {k: {'S': v} for k, v in nodes.items()}}}}},
        {'Update': {
            'TableName': challenge.table, 'Key': challenge._key(nonce),
            'UpdateExpression': 'SET #used=:true',
            'ConditionExpression': ('#used=:false AND #expires>:now AND #session=:session '
                                    'AND #account=:account AND #lab=:lab AND #connector=:connector'),
            'ExpressionAttributeNames': {'#used': 'used', '#expires': 'expires_at', '#session': 'session',
                                         '#account': 'account', '#lab': 'lab', '#connector': 'connector'},
            'ExpressionAttributeValues': values}},
        {'Put': {'TableName': challenge.table,
                 'Item': {'pk': {'S': 'LAB#' + lab}, 'sk': {'S': 'BINDING'}, **context},
                 'ConditionExpression': 'attribute_not_exists(pk)'}},
        {'Put': {'TableName': challenge.table,
                 'Item': {'pk': {'S': 'ACCOUNT#' + account}, 'sk': {'S': 'BINDING'}, **context},
                 'ConditionExpression': 'attribute_not_exists(pk)'}}]
    try:
        client.transact_write_items(TransactItems=writes)
    except client.exceptions.TransactionCanceledException:
        raise EnrollmentError('enrollment conflict or challenge expired') from None
    return {'lab_id': lab, 'account': account, 'deployment_id': deployment, 'bound': True}
