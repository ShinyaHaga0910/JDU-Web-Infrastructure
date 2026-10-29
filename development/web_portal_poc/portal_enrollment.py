"""Atomic enrollment for a verified Google identity and approved AWS Lab.

This is an internal service primitive, not an HTTP identity authorizer. Only
the trusted teacher process may call approve(). begin()/status() must receive
identity claims already verified by the portal, never browser JSON claims.
complete() accepts only a fresh nonce-bound STS proof from the approved AWS
account. No original grade item, EC2 instance, credential or IAM policy is
written. Proof URLs must never be logged.
"""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
import json
import re
import time

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
import identity_proof
from identity_keys import subject_key

HEX = re.compile(r'[a-f0-9]{64}\Z')
SUBJECT = re.compile(r'SUBJECT#[a-f0-9]{64}\Z')
ROLES = {'bastion', 'web', 'dns', 'db', 'repo'}
PAIR_SECONDS = 300
SERIALIZER, DESERIALIZER = TypeSerializer(), TypeDeserializer()


class EnrollmentDenied(ValueError):
    pass


def digest(text):
    return hashlib.sha256(text.encode('ascii')).hexdigest()


def email_key(email, pepper):
    if (not isinstance(email, str) or not email.isascii()
            or not re.fullmatch(r'[^@\s]{1,64}@jdu\.uz', email, flags=re.I)
            or not isinstance(pepper, bytes) or len(pepper) < 32):
        raise EnrollmentDenied('Invalid verified identity')
    return 'APPROVAL#' + hmac.new(pepper, b'email-v1\0' + email.casefold().encode('ascii'), hashlib.sha256).hexdigest()


def checked_grant(grant):
    if (type(grant) is not dict or set(grant) != {'account', 'lab_id', 'deployment_id', 'token_hash', 'instances'}
            or not isinstance(grant['account'], str) or not re.fullmatch(r'[0-9]{12}', grant['account'])
            or not isinstance(grant['lab_id'], str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', grant['lab_id'])
            or not isinstance(grant['deployment_id'], str) or not re.fullmatch(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', grant['deployment_id'])
            or not isinstance(grant['token_hash'], str) or not HEX.fullmatch(grant['token_hash'])
            or type(grant['instances']) is not dict or set(grant['instances']) != ROLES
            or any(not isinstance(v, str) or not re.fullmatch(r'i-[0-9a-f]{17}', v) for v in grant['instances'].values())
            or len(set(grant['instances'].values())) != 5):
        raise EnrollmentDenied('Invalid approved Lab')
    # Detach the trusted snapshot from callers before storing it.
    return json.loads(json.dumps(grant))


def grant_digest(grant):
    return digest(json.dumps(grant, sort_keys=True, separators=(',', ':')))


def encoded(row):
    return {k: SERIALIZER.serialize(v) for k, v in row.items()}


def key(pk, sk):
    return {'pk': {'S': pk}, 'sk': {'S': sk}}


class PortalEnrollment:
    def __init__(self, client, binding_table, grade_table, pepper, *, clock=time.time,
                 fetch=identity_proof.fetch_sts):
        if (not isinstance(pepper, bytes) or len(pepper) < 32
                or binding_table == grade_table
                or any(not isinstance(t, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,255}', t)
                       for t in (binding_table, grade_table))):
            raise EnrollmentDenied('Invalid enrollment configuration')
        self.client, self.table, self.grades, self.pepper = client, binding_table, grade_table, pepper
        self.clock, self.fetch = clock, fetch

    def get(self, table, pk, sk):
        item = self.client.get_item(TableName=table, Key=key(pk, sk), ConsistentRead=True).get('Item')
        return {k: DESERIALIZER.deserialize(v) for k, v in item.items()} if item else None

    def meta_condition(self, grant):
        return {'ConditionCheck': {'TableName': self.grades, 'Key': key('LAB#' + grant['lab_id'], 'META'),
            'ConditionExpression': '#active=:yes AND #lab=:lab AND #deployment=:deployment AND #token=:token AND #nodes=:nodes',
            'ExpressionAttributeNames': {'#active': 'active', '#lab': 'lab_id', '#deployment': 'deployment_id', '#token': 'token_hash', '#nodes': 'instances'},
            'ExpressionAttributeValues': encoded({':yes': True, ':lab': grant['lab_id'], ':deployment': grant['deployment_id'],
                                                 ':token': grant['token_hash'], ':nodes': grant['instances']})}}

    def check_meta(self, grant):
        meta = self.get(self.grades, 'LAB#' + grant['lab_id'], 'META')
        if (not meta or meta.get('active') is not True
                or any(meta.get(k) != grant[k] for k in ('lab_id', 'deployment_id', 'token_hash', 'instances'))):
            raise EnrollmentDenied('Approval context changed')

    def approve(self, email, grant, lifetime=604800):
        """Trusted teacher only: create a non-overwriting, email-scoped approval.

        No public route may call this based only on a self-declared teacher or
        Lab. The email remains an HMAC; the deadline is not DynamoDB TTL, so
        approval audit data does not disappear when registration closes.
        """
        grant = checked_grant(grant)
        if type(lifetime) is not int or not 60 <= lifetime <= 2592000:
            raise EnrollmentDenied('Invalid approval deadline')
        pk = email_key(email, self.pepper)
        now = int(self.clock())
        row = {'pk': pk, 'sk': 'LAB', 'active': True, 'grant': grant,
               'grant_digest': grant_digest(grant), 'enrollment_deadline': now + lifetime, 'created_at': now}
        try:
            self.client.transact_write_items(TransactItems=[self.meta_condition(grant),
                {'Put': {'TableName': self.table, 'Item': encoded(row), 'ConditionExpression': 'attribute_not_exists(pk)'}}])
        except self.client.exceptions.TransactionCanceledException:
            raise EnrollmentDenied('Approval conflicts or original Lab changed') from None
        return {'approved': True, 'lab_id': grant['lab_id']}

    def session(self, session_pk, token_hash):
        if (not isinstance(session_pk, str) or not re.fullmatch(r'SESSION#[a-f0-9]{64}', session_pk)
                or not isinstance(token_hash, str) or not HEX.fullmatch(token_hash)):
            raise EnrollmentDenied('Session unavailable')
        row = self.get(self.table, session_pk, 'PORTAL')
        if (not row or row.get('active') is not True or row.get('token_hash') != token_hash
                or isinstance(row.get('expires_at'), bool) or not isinstance(row.get('expires_at'), (int, Decimal))
                or row['expires_at'] <= int(self.clock())):
            raise EnrollmentDenied('Session unavailable')

    def session_condition(self, pair, now):
        return {'ConditionCheck': {'TableName': self.table, 'Key': key(pair['session_pk'], 'PORTAL'),
            'ConditionExpression': '#active=:yes AND #expiry>:now AND #token=:token',
            'ExpressionAttributeNames': {'#active': 'active', '#expiry': 'expires_at', '#token': 'token_hash'},
            'ExpressionAttributeValues': encoded({':yes': True, ':now': now, ':token': pair['session_token_hash']})}}

    def approval(self, approval_pk):
        if not isinstance(approval_pk, str) or not re.fullmatch(r'APPROVAL#[a-f0-9]{64}', approval_pk):
            raise EnrollmentDenied('Approval unavailable')
        row = self.get(self.table, approval_pk, 'LAB')
        if not row or row.get('active') is not True:
            raise EnrollmentDenied('Approval unavailable')
        grant = checked_grant(row.get('grant'))
        if row.get('grant_digest') != grant_digest(grant):
            raise EnrollmentDenied('Approval context changed')
        self.check_meta(grant)
        return row, grant

    def registered(self, subject_pk, grant, approval_pk):
        """A success receipt never substitutes for the existing reader checks."""
        connector = f'arn:aws:lambda:us-east-1:{grant["account"]}:function:jdu-web-status-{grant["lab_id"]}'
        context = {k: grant[k] for k in ('account', 'lab_id', 'deployment_id')}
        context['connector'] = digest(connector)
        person = self.get(self.table, subject_pk, 'BINDING')
        if (not person or person.get('active') is not True or person.get('token_hash') != grant['token_hash']
                or person.get('approval_pk') != approval_pk or any(person.get(k) != v for k, v in context.items())):
            return False
        mirror = self.get(self.table, 'LAB#' + grant['lab_id'], 'SUBJECT')
        if not mirror or mirror.get('subject_pk') != subject_pk:
            return False
        for pk in ('LAB#' + grant['lab_id'], 'ACCOUNT#' + grant['account']):
            row = self.get(self.table, pk, 'BINDING')
            if not row or any(row.get(k) != v for k, v in context.items()):
                return False
        row = self.get(self.table, 'CONNECTOR#' + context['connector'], 'META')
        return bool(row and row.get('active') is True and row.get('arn') == connector
                    and all(row.get(k) == v for k, v in context.items() if k != 'connector'))

    def pair_nonce(self, subject_pk, session_pk, request_hash):
        return hmac.new(self.pepper, ('pair-v2|' + subject_pk + '|' + session_pk + '|' + request_hash).encode('ascii'), hashlib.sha256).hexdigest()

    def pending(self, subject_pk, approval_pk, session_pk, token_hash, grant):
        pointer = self.get(self.table, session_pk, 'ENROLLMENT')
        if not pointer or pointer.get('expires_at', 0) <= int(self.clock()):
            return None
        context = {'subject_pk': subject_pk, 'approval_pk': approval_pk, 'session_pk': session_pk,
                   'session_token_hash': token_hash, 'grant_digest': grant_digest(grant)}
        if (any(pointer.get(k) != v for k, v in context.items()) or pointer.get('used') is not False
                or not isinstance(pointer.get('request_hash'), str) or not HEX.fullmatch(pointer['request_hash'])):
            raise EnrollmentDenied('Pending registration changed')
        nonce = self.pair_nonce(subject_pk, session_pk, pointer['request_hash'])
        pair = self.get(self.table, 'PAIR#' + digest(nonce), 'IDENTITY')
        if (not pair or pointer.get('pair_pk') != pair.get('pk')
                or pair.get('request_hash') != pointer['request_hash'] or pair.get('used') is not False
                or pair.get('expires_at') != pointer['expires_at']
                or any(pair.get(k) != v for k, v in context.items())):
            raise EnrollmentDenied('Pending registration unavailable')
        return nonce, pair

    def begin(self, subject, email, session_id, token_hash, request_id):
        if (not isinstance(session_id, str) or not HEX.fullmatch(session_id)
                or not isinstance(request_id, str) or not HEX.fullmatch(request_id)):
            raise EnrollmentDenied('Invalid registration request')
        subject_pk = subject_key(subject, self.pepper)
        approval_pk = email_key(email, self.pepper)
        session_pk = 'SESSION#' + digest(session_id)
        self.session(session_pk, token_hash)
        approval, grant = self.approval(approval_pk)
        if approval.get('bound_subject') == subject_pk and self.registered(subject_pk, grant, approval_pk):
            return {'registered': True, 'lab_id': grant['lab_id'], 'account': grant['account']}
        if approval.get('bound_subject') is not None or approval.get('enrollment_deadline', 0) <= int(self.clock()):
            raise EnrollmentDenied('Approval already used or expired')
        existing = self.pending(subject_pk, approval_pk, session_pk, token_hash, grant)
        if existing:
            return self.pair_response(*existing, grant)
        request_hash = digest(request_id)
        nonce = self.pair_nonce(subject_pk, session_pk, request_hash)
        pk = 'PAIR#' + digest(nonce)
        old = self.get(self.table, pk, 'IDENTITY')
        context = {'subject_pk': subject_pk, 'approval_pk': approval_pk, 'session_pk': session_pk,
                   'session_token_hash': token_hash, 'grant_digest': grant_digest(grant)}
        if old:
            # A complete attempt must also have its atomically stored session
            # pointer. Missing/expired pointers never revive an old operation.
            raise EnrollmentDenied('Registration attempt expired or changed')
        now = int(self.clock())
        pair = {'pk': pk, 'sk': 'IDENTITY', **context, 'grant': grant, 'used': False,
                'request_hash': request_hash, 'expires_at': now + PAIR_SECONDS}
        pointer = {'pk': session_pk, 'sk': 'ENROLLMENT', **context, 'pair_pk': pk,
                   'request_hash': request_hash, 'used': False, 'expires_at': pair['expires_at']}
        pointer_put = {'Put': {'TableName': self.table, 'Item': encoded(pointer),
            'ConditionExpression': 'attribute_not_exists(pk) OR #expiry<=:now',
            'ExpressionAttributeNames': {'#expiry': 'expires_at'}, 'ExpressionAttributeValues': encoded({':now': now})}}
        approval_check = {'ConditionCheck': {'TableName': self.table, 'Key': key(approval_pk, 'LAB'),
            'ConditionExpression': '#active=:yes AND #deadline>:now AND #digest=:digest AND attribute_not_exists(#bound)',
            'ExpressionAttributeNames': {'#active': 'active', '#deadline': 'enrollment_deadline', '#digest': 'grant_digest', '#bound': 'bound_subject'},
            'ExpressionAttributeValues': encoded({':yes': True, ':now': now, ':digest': context['grant_digest']})}}
        try:
            self.client.transact_write_items(TransactItems=[self.meta_condition(grant), approval_check,
                self.session_condition(pair, now), {'Put': {'TableName': self.table, 'Item': encoded(pair),
                                                            'ConditionExpression': 'attribute_not_exists(pk)'}}, pointer_put])
        except self.client.exceptions.TransactionCanceledException:
            # Concurrent forms in the same session return the one committed
            # attempt. Never issue another operation after an unknown result.
            self.session(session_pk, token_hash)
            latest, current = self.approval(approval_pk)
            if current == grant:
                if latest.get('bound_subject') == subject_pk and self.registered(subject_pk, grant, approval_pk):
                    return {'registered': True, 'lab_id': grant['lab_id'], 'account': grant['account']}
                if latest.get('bound_subject') is None:
                    existing = self.pending(subject_pk, approval_pk, session_pk, token_hash, grant)
                    if existing:
                        return self.pair_response(*existing, grant)
            raise EnrollmentDenied('Registration is pending or context changed') from None
        return self.pair_response(nonce, pair, grant)

    @staticmethod
    def pair_response(nonce, pair, grant):
        return {'registered': False, 'pair_id': nonce, 'expires_at': int(pair['expires_at']),
                'lab_id': grant['lab_id'], 'account': grant['account']}

    def status(self, subject, email, session_id, token_hash):
        if not isinstance(session_id, str) or not HEX.fullmatch(session_id):
            raise EnrollmentDenied('Session unavailable')
        self.session('SESSION#' + digest(session_id), token_hash)
        subject_pk, approval_pk = subject_key(subject, self.pepper), email_key(email, self.pepper)
        approval, grant = self.approval(approval_pk)
        bound = approval.get('bound_subject') == subject_pk and self.registered(subject_pk, grant, approval_pk)
        if approval.get('bound_subject') is not None and not bound:
            raise EnrollmentDenied('Approval already bound or registration changed')
        if not bound and approval.get('enrollment_deadline', 0) > int(self.clock()):
            existing = self.pending(subject_pk, approval_pk, 'SESSION#' + digest(session_id), token_hash, grant)
            if existing:
                return self.pair_response(*existing, grant)
        return {'registered': bound, 'lab_id': grant['lab_id'], 'account': grant['account']}

    def complete(self, nonce, proof_url):
        if not isinstance(nonce, str) or not HEX.fullmatch(nonce):
            raise EnrollmentDenied('Registration unavailable')
        pair = self.get(self.table, 'PAIR#' + digest(nonce), 'IDENTITY')
        if (not pair or pair.get('expires_at', 0) <= int(self.clock())
                or not isinstance(pair.get('subject_pk'), str) or not SUBJECT.fullmatch(pair['subject_pk'])):
            raise EnrollmentDenied('Registration unavailable')
        grant = checked_grant(pair.get('grant'))
        approval, current = self.approval(pair['approval_pk'])
        if current != grant or pair.get('grant_digest') != grant_digest(grant):
            raise EnrollmentDenied('Approval context changed')
        self.session(pair['session_pk'], pair['session_token_hash'])
        if not isinstance(pair.get('request_hash'), str) or not HEX.fullmatch(pair['request_hash']):
            raise EnrollmentDenied('Registration unavailable')
        # Validation happens before network access; the only possible target is
        # the fixed STS host and the signature must bind this exact nonce.
        path = identity_proof.validate(proof_url, nonce, datetime.fromtimestamp(self.clock(), timezone.utc))
        if self.fetch(path, nonce) != grant['account']:
            raise EnrollmentDenied('Wrong AWS account')
        self.session(pair['session_pk'], pair['session_token_hash'])
        approval, current = self.approval(pair['approval_pk'])
        if current != grant or pair['expires_at'] <= int(self.clock()):
            raise EnrollmentDenied('Registration expired or context changed')
        if approval.get('bound_subject') == pair['subject_pk'] and self.registered(pair['subject_pk'], grant, pair['approval_pk']):
            return {'registered': True, 'lab_id': grant['lab_id'], 'reused': True}
        now = int(self.clock())
        if pair.get('used') is not False or approval.get('bound_subject') is not None:
            raise EnrollmentDenied('Registration conflict')
        connector = f'arn:aws:lambda:us-east-1:{grant["account"]}:function:jdu-web-status-{grant["lab_id"]}'
        context = {k: grant[k] for k in ('account', 'lab_id', 'deployment_id')}
        context['connector'] = digest(connector)
        records = [
            {'pk': 'LAB#' + grant['lab_id'], 'sk': 'BINDING', **context},
            {'pk': 'ACCOUNT#' + grant['account'], 'sk': 'BINDING', **context},
            {'pk': 'CONNECTOR#' + context['connector'], 'sk': 'META', 'arn': connector,
             'active': True, **{k: grant[k] for k in ('account', 'lab_id', 'deployment_id')}},
            {'pk': pair['subject_pk'], 'sk': 'BINDING', **context, 'token_hash': grant['token_hash'],
             'active': True, 'approval_pk': pair['approval_pk']},
            {'pk': 'LAB#' + grant['lab_id'], 'sk': 'SUBJECT', 'subject_pk': pair['subject_pk']}]
        approval_update = {'Update': {'TableName': self.table, 'Key': key(pair['approval_pk'], 'LAB'),
            'UpdateExpression': 'SET #bound=:subject',
            'ConditionExpression': '#active=:yes AND #deadline>:now AND #digest=:digest AND attribute_not_exists(#bound)',
            'ExpressionAttributeNames': {'#bound': 'bound_subject', '#active': 'active', '#deadline': 'enrollment_deadline', '#digest': 'grant_digest'},
            'ExpressionAttributeValues': encoded({':subject': pair['subject_pk'], ':yes': True, ':now': now, ':digest': pair['grant_digest']})}}
        pair_update = {'Update': {'TableName': self.table, 'Key': key(pair['pk'], 'IDENTITY'),
            'UpdateExpression': 'SET #used=:yes',
            'ConditionExpression': '#used=:no AND #expiry>:now AND #subject=:subject AND #approval=:approval AND #session=:session AND #digest=:digest',
            'ExpressionAttributeNames': {'#used': 'used', '#expiry': 'expires_at', '#subject': 'subject_pk', '#approval': 'approval_pk', '#session': 'session_pk', '#digest': 'grant_digest'},
            'ExpressionAttributeValues': encoded({':yes': True, ':no': False, ':now': now, ':subject': pair['subject_pk'],
                ':approval': pair['approval_pk'], ':session': pair['session_pk'], ':digest': pair['grant_digest']})}}
        pending_update = {'Update': {'TableName': self.table, 'Key': key(pair['session_pk'], 'ENROLLMENT'),
            'UpdateExpression': 'SET #used=:yes',
            'ConditionExpression': '#used=:no AND #expiry>:now AND #pair=:pair AND #subject=:subject AND #request=:request AND #token=:token',
            'ExpressionAttributeNames': {'#used': 'used', '#expiry': 'expires_at', '#pair': 'pair_pk',
                                         '#subject': 'subject_pk', '#request': 'request_hash', '#token': 'session_token_hash'},
            'ExpressionAttributeValues': encoded({':yes': True, ':no': False, ':now': now, ':pair': pair['pk'],
                ':subject': pair['subject_pk'], ':request': pair['request_hash'], ':token': pair['session_token_hash']})}}
        try:
            self.client.transact_write_items(TransactItems=[self.meta_condition(grant), self.session_condition(pair, now),
                approval_update, pair_update, pending_update, *[{'Put': {'TableName': self.table, 'Item': encoded(row),
                    'ConditionExpression': 'attribute_not_exists(pk)'}} for row in records]])
        except self.client.exceptions.TransactionCanceledException:
            # Another request may have committed the same scoped operation.
            # Re-read the receipt instead of creating another set of bindings.
            approval, _ = self.approval(pair['approval_pk'])
            if approval.get('bound_subject') == pair['subject_pk'] and self.registered(pair['subject_pk'], grant, pair['approval_pk']):
                self.session(pair['session_pk'], pair['session_token_hash'])
                return {'registered': True, 'lab_id': grant['lab_id'], 'reused': True}
            raise EnrollmentDenied('Registration conflict or original context changed') from None
        return {'registered': True, 'lab_id': grant['lab_id'], 'reused': False}
