"""Internal registration primitive for a teacher-approved portal identity.

The surrounding service MUST authenticate the teacher, obtain explicit
approval for the student/Lab, and verify the student's Google identity before
calling this function. The supplied context must come from trusted server-side
records. This module is not an HTTP handler and does not provide those checks.
"""
import re

import progress_api as legacy
from identity_grade import subject_key


class SubjectBindingError(ValueError):
    pass


def bind_subject(client, binding_table, grade_table, verified_subject, pepper, context):
    """Create a one-to-one subject/Lab mapping if both prior bindings match.

    Teacher approval and identity verification are external prerequisites. The
    transaction checks that the active grade metadata and account/Lab binding
    have not changed; it never writes to the original grade table.
    """
    try:
        pk = subject_key(verified_subject, pepper)
        lab, account = context['lab_id'], context['account']
        deployment, token, connector = context['deployment_id'], context['token_hash'], context['connector']
        if (not isinstance(lab, str) or not legacy.LAB_RE.fullmatch(lab)
                or not isinstance(account, str) or not re.fullmatch(r'[0-9]{12}', account)
                or not isinstance(deployment, str) or not deployment
                or not isinstance(token, str) or not re.fullmatch(r'[a-f0-9]{64}', token)
                or not isinstance(connector, str) or not re.fullmatch(r'[a-f0-9]{64}', connector)):
            raise ValueError('invalid context')
    except (ValueError, KeyError, TypeError):
        raise SubjectBindingError('invalid approved context') from None

    def key(p, s):
        return {'pk': {'S': p}, 'sk': {'S': s}}
    values = {':lab': {'S': lab}, ':account': {'S': account},
              ':deployment': {'S': deployment}, ':connector': {'S': connector}}
    condition = '#lab=:lab AND #account=:account AND #deployment=:deployment AND #connector=:connector'
    names = {'#lab': 'lab_id', '#account': 'account', '#deployment': 'deployment_id', '#connector': 'connector'}
    writes = [
        {'ConditionCheck': {'TableName': grade_table, 'Key': key('LAB#' + lab, 'META'),
            'ConditionExpression': '#active=:yes AND #lab=:lab AND #deployment=:deployment AND #token=:token',
            'ExpressionAttributeNames': {'#active': 'active', '#lab': 'lab_id', '#deployment': 'deployment_id', '#token': 'token_hash'},
            'ExpressionAttributeValues': {':yes': {'BOOL': True}, ':lab': {'S': lab},
                                          ':deployment': {'S': deployment}, ':token': {'S': token}}}},
        *[{'ConditionCheck': {'TableName': binding_table, 'Key': key(p, 'BINDING'),
            'ConditionExpression': condition, 'ExpressionAttributeNames': names,
            'ExpressionAttributeValues': values}} for p in ('LAB#' + lab, 'ACCOUNT#' + account)],
        {'Put': {'TableName': binding_table, 'Item': {**key(pk, 'BINDING'),
            'lab_id': {'S': lab}, 'account': {'S': account}, 'deployment_id': {'S': deployment},
            'token_hash': {'S': token}, 'connector': {'S': connector}, 'active': {'BOOL': True}},
            'ConditionExpression': 'attribute_not_exists(pk)'}},
        {'Put': {'TableName': binding_table, 'Item': {**key('LAB#' + lab, 'SUBJECT'), 'subject_pk': {'S': pk}},
            'ConditionExpression': 'attribute_not_exists(pk)'}}]
    try:
        client.transact_write_items(TransactItems=writes)
    except client.exceptions.TransactionCanceledException:
        raise SubjectBindingError('binding conflict or approval context changed') from None
    return {'bound': True, 'lab_id': lab}
