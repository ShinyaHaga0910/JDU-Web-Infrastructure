"""Pre-provisioning assignment and AWS proof, before a Lab has any nodes.

This is the first part of R1, not a deployment worker. A confirmed request is
durable input for that worker; it does not mean EC2 has been created. Reuse the
existing session, HMAC and STS validation. Never replace existing bindings or
grade META, and never store raw school identity, proof URLs or passwords.
"""
from datetime import datetime, timezone
from decimal import Decimal
import hmac
import hashlib
import re
import uuid

import identity_proof
from identity_keys import subject_key
from portal_enrollment import EnrollmentDenied, digest, email_key, encoded, key, grant_digest, HEX


def checked_release(value):
    fields = {'release_id', 'manifest_sha256', 'template_sha256', 'expires_at'}
    if (type(value) is not dict or set(value) != fields
            or not isinstance(value['release_id'], str)
            or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,95}', value['release_id'])
            or any(not isinstance(value[k], str) or not HEX.fullmatch(value[k])
                   for k in ('manifest_sha256', 'template_sha256'))
            or not (type(value['expires_at']) is int or
                    isinstance(value['expires_at'], Decimal) and value['expires_at'] == value['expires_at'].to_integral_value())
            or value['expires_at'] <= 0):
        raise EnrollmentDenied('Invalid reviewed release')
    # These facts must come from verified signed artifacts in the teacher
    # publisher, never a browser form. This function does not verify GPG.
    return dict(value, expires_at=int(value['expires_at']))


def checked_assignment(grant):
    if (type(grant) is not dict or set(grant) != {'account', 'lab_id', 'deployment_id', 'release'}
            or not isinstance(grant['account'], str) or not re.fullmatch(r'[0-9]{12}', grant['account'])
            or not isinstance(grant['lab_id'], str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', grant['lab_id'])
            or not isinstance(grant['deployment_id'], str)
            or not re.fullmatch(r'[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}', grant['deployment_id'])):
        raise EnrollmentDenied('Invalid reviewed assignment')
    return dict(grant, release=checked_release(grant['release']))


class PortalPreparation:
    def __init__(self, enrollment, initial=None):
        self.auth = enrollment
        self.client, self.table = enrollment.client, enrollment.table
        self.initial = initial

    def get(self, pk, sk):
        return self.auth.get(self.table, pk, sk)

    def absent(self, pk, sk, table=None):
        return {'ConditionCheck': {'TableName': table or self.table, 'Key': key(pk, sk),
                                  'ConditionExpression': 'attribute_not_exists(pk)'}}

    def context_guards(self, assignment, subject=None):
        grant = assignment['grant']
        checks = [self.absent('ACCOUNT#' + grant['account'], 'BINDING'),
                  self.absent('LAB#' + grant['lab_id'], 'BINDING'),
                  self.absent('LAB#' + grant['lab_id'], 'META', self.auth.grades),
                  self.absent(assignment['pk'], 'LAB')]
        if subject is not None:
            checks.append(self.absent(subject, 'BINDING'))
        # Reservations belong to this exact immutable assignment. Checking
        # them in the same transaction closes the read/write race.
        for pk in ('ACCOUNT#' + grant['account'], 'LAB#' + grant['lab_id']):
            checks.append({'ConditionCheck': {'TableName': self.table, 'Key': key(pk, 'PREPARATION'),
                'ConditionExpression': '#owner=:owner AND #digest=:digest',
                'ExpressionAttributeNames': {'#owner': 'assignment_pk', '#digest': 'grant_digest'},
                'ExpressionAttributeValues': encoded({':owner': assignment['pk'], ':digest': assignment['grant_digest']})}})
        return checks

    def approve(self, email, account, lab_id, release, *, lifetime=604800):
        """Trusted teacher publisher only; no HTTP/IAM student approve route."""
        if (not isinstance(account, str) or not re.fullmatch(r'[0-9]{12}', account)
                or not isinstance(lab_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}', lab_id)
                or type(lifetime) is not int or not 60 <= lifetime <= 2592000):
            raise EnrollmentDenied('Invalid assignment')
        now = int(self.auth.clock())
        release = checked_release(release)
        if release['expires_at'] <= now + 60:
            raise EnrollmentDenied('Release must still be valid')
        grant = {'account': account, 'lab_id': lab_id, 'deployment_id': str(uuid.uuid4()), 'release': release}
        row = {'pk': email_key(email, self.auth.pepper), 'sk': 'PREPARATION',
               'active': True, 'stage': 'APPROVED', 'grant': grant, 'grant_digest': grant_digest(grant),
               'deadline': min(now + lifetime, release['expires_at']), 'created_at': now}
        reservations = [{'pk': pk, 'sk': 'PREPARATION', 'assignment_pk': row['pk'],
                         'grant_digest': row['grant_digest']} for pk in ('ACCOUNT#' + account, 'LAB#' + lab_id)]
        checks = [self.absent('ACCOUNT#' + account, 'BINDING'), self.absent('LAB#' + lab_id, 'BINDING'),
                  self.absent('LAB#' + lab_id, 'META', self.auth.grades), self.absent(row['pk'], 'LAB')]
        try:
            self.client.transact_write_items(TransactItems=[*checks, *[
                {'Put': {'TableName': self.table, 'Item': encoded(item),
                         'ConditionExpression': 'attribute_not_exists(pk)'}} for item in [row, *reservations]]])
        except self.client.exceptions.TransactionCanceledException:
            raise EnrollmentDenied('Existing assignment or Lab retained') from None
        return {'assigned': True, **self.view(row)}

    def assignment(self, pk):
        row = self.get(pk, 'PREPARATION')
        if (not row or row.get('active') is not True or row.get('stage') not in
                ('APPROVED', 'AWS_CONFIRMED', 'CREATE_REQUESTED')):
            raise EnrollmentDenied('Preparation unavailable')
        row['grant'] = checked_assignment(row.get('grant'))
        if row.get('grant_digest') != grant_digest(row['grant']):
            raise EnrollmentDenied('Preparation context changed')
        return row

    def current(self, subject, email, session_id, token_hash):
        if not isinstance(session_id, str) or not HEX.fullmatch(session_id):
            raise EnrollmentDenied('Session unavailable')
        session_pk = 'SESSION#' + digest(session_id)
        self.auth.session(session_pk, token_hash)
        subject_pk = subject_key(subject, self.auth.pepper)
        row = self.assignment(email_key(email, self.auth.pepper))
        if row.get('bound_subject') not in (None, subject_pk):
            raise EnrollmentDenied('Assignment belongs to another identity')
        meta=self.auth.get(self.auth.grades,'LAB#'+row['grant']['lab_id'],'META')
        bindings=[self.get(subject_pk,'BINDING'),self.get('ACCOUNT#'+row['grant']['account'],'BINDING'),
                  self.get('LAB#'+row['grant']['lab_id'],'BINDING'),self.get(row['pk'],'LAB')]
        if row.get('registration'):
            from initial_registration import checked_registration
            saved=checked_registration(row['registration'],row['grant']);grant=saved['grant']
            if (row.get('bound_subject')!=subject_pk or not meta or meta.get('active') is not True
                    or meta.get('release_id')!=saved['release_id']
                    or any(meta.get(k)!=grant[k] for k in ('lab_id','deployment_id','token_hash','instances'))):
                raise EnrollmentDenied('Original registration changed')
            if row.get('registration_complete') is True:
                if not self.auth.registered(subject_pk,grant,row['pk']):raise EnrollmentDenied('Original binding changed')
                approval,approved_grant=self.auth.approval(row['pk'])
                if approval.get('bound_subject')!=subject_pk or approved_grant!=grant:
                    raise EnrollmentDenied('Original approval changed')
            elif any(bindings):raise EnrollmentDenied('Existing binding retained')
        elif meta or any(bindings):
            raise EnrollmentDenied('Existing Lab retained or assignment changed')
        return row, subject_pk, session_pk

    def view(self, row):
        grant = row['grant']
        return {'stage': row['stage'], 'account': grant['account'], 'lab_id': grant['lab_id'],
                'deployment_id': grant['deployment_id'], 'release_id': grant['release']['release_id'],
                'manifest_sha256': grant['release']['manifest_sha256'],
                'deadline': int(row['deadline']), 'resources_created': False,
                'registration_complete': row.get('registration_complete') is True,
                'can_continue': min(row['deadline'], grant['release']['expires_at']) > self.auth.clock()}

    def live(self, row):
        now = int(self.auth.clock())
        if min(row['deadline'], row['grant']['release']['expires_at']) <= now:
            raise EnrollmentDenied('Assignment or release expired')

    def status(self, subject, email, session_id, token_hash):
        row, person, session = self.current(subject, email, session_id, token_hash)
        result = self.view(row)
        if row['stage'] == 'APPROVED' and result['can_continue']:
            pointer = self.get(session, 'PREPARATION_PAIR')
            if pointer and pointer.get('expires_at', 0) > self.auth.clock():
                if (pointer.get('grant_digest') != row['grant_digest'] or pointer.get('subject_pk') != person
                        or pointer.get('session_token_hash') != token_hash):
                    raise EnrollmentDenied('Preparation context changed')
                nonce = self.nonce(row, person, session, pointer['request_hash'])
                pair = self.get('PREPARE-PAIR#' + digest(nonce), 'IDENTITY')
                if (not pair or pair.get('used') is not False or pair.get('expires_at') != pointer['expires_at']
                        or pair.get('subject_pk') != person or pair.get('session_pk') != session
                        or pair.get('grant_digest') != row['grant_digest']):
                    raise EnrollmentDenied('Preparation confirmation unavailable')
                result.update(pair_id=nonce, expires_at=int(pair['expires_at']))
        if row['stage'] == 'CREATE_REQUESTED' and self.initial is not None:
            result['initial'] = self.initial(row['grant'], 'observe')
            result['resources_created'] = result['initial'].get('resources_created', False)
        return result

    def nonce(self, row, person, session, request_hash):
        context = '|'.join(('preparation-v1', row['grant_digest'], person, session, request_hash))
        return hmac.new(self.auth.pepper, context.encode('ascii'), hashlib.sha256).hexdigest()

    def assignment_check(self, row):
        return {'ConditionCheck': {'TableName': self.table, 'Key': key(row['pk'], 'PREPARATION'),
            'ConditionExpression': '#active=:yes AND #deadline>:now AND #digest=:digest AND #stage=:stage',
            'ExpressionAttributeNames': {'#active': 'active', '#deadline': 'deadline',
                                         '#digest': 'grant_digest', '#stage': 'stage'},
            'ExpressionAttributeValues': encoded({':yes': True, ':now': int(self.auth.clock()),
                                                  ':digest': row['grant_digest'], ':stage': row['stage']})}}

    def begin(self, subject, email, session_id, token_hash, request_id, *, _observe=False):
        if not isinstance(request_id, str) or not HEX.fullmatch(request_id):
            raise EnrollmentDenied('Invalid preparation request')
        row, person, session = self.current(subject, email, session_id, token_hash)
        self.live(row)
        if row['stage'] != 'APPROVED':
            return self.view(row)
        # A live session pointer makes different concurrent/reloaded forms
        # converge. After expiry a new form can obtain a fresh nonce without
        # forcing another Google login or reviving the expired proof.
        pointer = self.get(session, 'PREPARATION_PAIR')
        if pointer and pointer.get('expires_at', 0) > self.auth.clock():
            if (pointer.get('grant_digest') != row['grant_digest'] or pointer.get('subject_pk') != person
                    or pointer.get('session_token_hash') != token_hash):
                raise EnrollmentDenied('Preparation context changed')
            request_hash = pointer['request_hash']
        else:
            request_hash = digest(request_id)
        nonce = self.nonce(row, person, session, request_hash)
        pk = 'PREPARE-PAIR#' + digest(nonce)
        old = self.get(pk, 'IDENTITY')
        if old:
            if old.get('used') is not False or old.get('expires_at', 0) <= self.auth.clock():
                raise EnrollmentDenied('Use a new form for a fresh AWS confirmation')
            if old.get('session_token_hash') != token_hash or old.get('grant_digest') != row['grant_digest']:
                raise EnrollmentDenied('Preparation context changed')
            return dict(self.view(row), pair_id=nonce, expires_at=int(old['expires_at']))
        if _observe:
            raise EnrollmentDenied('Preparation changed; reload its status')
        pair = {'pk': pk, 'sk': 'IDENTITY', 'assignment_pk': row['pk'], 'grant_digest': row['grant_digest'],
                'subject_pk': person, 'session_pk': session, 'session_token_hash': token_hash,
                'expires_at': min(int(self.auth.clock()) + 300, int(row['deadline'])), 'used': False}
        pointer = {'pk': session, 'sk': 'PREPARATION_PAIR', 'grant_digest': row['grant_digest'],
                   'subject_pk': person, 'session_token_hash': token_hash,
                   'request_hash': request_hash, 'expires_at': pair['expires_at']}
        try:
            self.client.transact_write_items(TransactItems=[self.assignment_check(row),
                self.auth.session_condition(pair, int(self.auth.clock())), *self.context_guards(row, person),
                {'Put': {'TableName': self.table, 'Item': encoded(pair),
                         'ConditionExpression': 'attribute_not_exists(pk)'}},
                {'Put': {'TableName': self.table, 'Item': encoded(pointer),
                    'ConditionExpression': 'attribute_not_exists(pk) OR #expiry<=:now',
                    'ExpressionAttributeNames': {'#expiry': 'expires_at'},
                    'ExpressionAttributeValues': encoded({':now': int(self.auth.clock())})}}])
        except self.client.exceptions.TransactionCanceledException:
            # Observe a concurrent successful form once; never issue a second
            # challenge or perform an external operation after uncertain writes.
            committed = self.get(session, 'PREPARATION_PAIR')
            if committed and committed.get('expires_at', 0) > self.auth.clock():
                return self.begin(subject, email, session_id, token_hash, request_id, _observe=True)
            raise EnrollmentDenied('Preparation changed; reload its status') from None
        return dict(self.view(row), pair_id=nonce, expires_at=int(pair['expires_at']))

    def complete(self, pair_id, proof_url):
        if not isinstance(pair_id, str) or not HEX.fullmatch(pair_id):
            raise EnrollmentDenied('Preparation confirmation unavailable')
        pair = self.get('PREPARE-PAIR#' + digest(pair_id), 'IDENTITY')
        if not pair or pair.get('expires_at', 0) <= self.auth.clock():
            raise EnrollmentDenied('Preparation confirmation expired')
        row = self.assignment(pair['assignment_pk'])
        self.live(row)
        self.auth.session(pair['session_pk'], pair['session_token_hash'])
        if pair.get('grant_digest') != row['grant_digest']:
            raise EnrollmentDenied('Preparation context changed')
        path = identity_proof.validate(proof_url, pair_id,
            datetime.fromtimestamp(self.auth.clock(), timezone.utc))
        if self.auth.fetch(path, pair_id) != row['grant']['account']:
            raise EnrollmentDenied('Wrong AWS account')
        row = self.assignment(pair['assignment_pk'])
        self.live(row)
        if row['grant_digest'] != pair['grant_digest']:
            raise EnrollmentDenied('Preparation context changed')
        if row.get('bound_subject') == pair['subject_pk'] and row['stage'] in ('AWS_CONFIRMED', 'CREATE_REQUESTED'):
            self.auth.session(pair['session_pk'], pair['session_token_hash'])
            return {'aws_confirmed': True, **self.view(row)}
        if row['stage'] != 'APPROVED' or pair.get('used') is not False:
            raise EnrollmentDenied('Preparation already confirmed by another identity')
        update = self.assignment_check(row)['ConditionCheck']
        update['UpdateExpression'] = 'SET #stage=:confirmed, bound_subject=:subject'
        update['ExpressionAttributeValues'].update(encoded({':confirmed': 'AWS_CONFIRMED', ':subject': pair['subject_pk']}))
        try:
            self.client.transact_write_items(TransactItems=[{'Update': update},
                self.auth.session_condition(pair, int(self.auth.clock())), *self.context_guards(row, pair['subject_pk']),
                {'Update': {'TableName': self.table, 'Key': key(pair['pk'], 'IDENTITY'),
                    'UpdateExpression': 'SET #used=:yes', 'ConditionExpression': '#used=:no AND #expiry>:now',
                    'ExpressionAttributeNames': {'#used': 'used', '#expiry': 'expires_at'},
                    'ExpressionAttributeValues': encoded({':yes': True, ':no': False, ':now': int(self.auth.clock())})}}])
        except self.client.exceptions.TransactionCanceledException:
            latest = self.assignment(row['pk'])
            self.auth.session(pair['session_pk'], pair['session_token_hash'])
            if (latest.get('bound_subject') != pair['subject_pk'] or latest['stage'] != 'AWS_CONFIRMED'
                    or latest['grant_digest'] != pair['grant_digest']):
                raise EnrollmentDenied('Preparation changed; reload its status') from None
            return {'aws_confirmed': True, **self.view(latest)}
        return {'aws_confirmed': True, **self.view(dict(row, stage='AWS_CONFIRMED'))}

    def confirm(self, subject, email, session_id, token_hash):
        """Explicit POST only. Persist one request; never create/start EC2 here."""
        row, person, session = self.current(subject, email, session_id, token_hash)
        self.live(row)
        if row.get('bound_subject') != person or row['stage'] not in ('AWS_CONFIRMED', 'CREATE_REQUESTED'):
            raise EnrollmentDenied('Confirm your assigned AWS account first')
        pk = 'PREPARATION#' + row['grant']['deployment_id']
        if row['stage'] == 'CREATE_REQUESTED':
            saved = self.get(pk, 'REQUEST')
            if not saved or saved.get('grant_digest') != row['grant_digest'] or saved.get('subject_pk') != person:
                raise EnrollmentDenied('Existing request retained for review')
            return self.view(row)
        request = {'pk': pk, 'sk': 'REQUEST', 'assignment_pk': row['pk'], 'subject_pk': person,
                   'grant': row['grant'], 'grant_digest': row['grant_digest'],
                   'stage': 'REQUESTED', 'created_at': int(self.auth.clock()), 'initial_state': 'foundation_only'}
        update = self.assignment_check(row)['ConditionCheck']
        update['UpdateExpression'] = 'SET #stage=:requested'
        update['ConditionExpression'] += ' AND bound_subject=:subject'
        update['ExpressionAttributeValues'].update(encoded({':requested': 'CREATE_REQUESTED', ':subject': person}))
        session_row = {'session_pk': session, 'session_token_hash': token_hash}
        try:
            self.client.transact_write_items(TransactItems=[{'Update': update},
                self.auth.session_condition(session_row, int(self.auth.clock())), *self.context_guards(row, person),
                {'Put': {'TableName': self.table, 'Item': encoded(request),
                         'ConditionExpression': 'attribute_not_exists(pk)'}}])
        except self.client.exceptions.TransactionCanceledException:
            latest = self.assignment(row['pk'])
            if latest['stage'] == 'CREATE_REQUESTED' and latest['grant_digest'] == row['grant_digest']:
                return self.confirm(subject, email, session_id, token_hash)
            raise EnrollmentDenied('Preparation changed; reload its status') from None
        return self.view(dict(row, stage='CREATE_REQUESTED'))

    def plan(self, subject, email, session_id, token_hash):
        if self.initial is None:
            raise RuntimeError('Initial worker unavailable')
        self.confirm(subject, email, session_id, token_hash)
        row, _, _ = self.current(subject, email, session_id, token_hash)
        initial = self.initial(row['grant'], 'plan')
        return {**self.view(row), 'initial': initial, 'resources_created': initial.get('resources_created', False)}

    def create(self, subject, email, session_id, token_hash, plan_digest, password, confirmation):
        row, person, _ = self.current(subject, email, session_id, token_hash)
        self.live(row)
        if (self.initial is None or row.get('bound_subject') != person or row['stage'] != 'CREATE_REQUESTED'
                or not isinstance(plan_digest, str) or not HEX.fullmatch(plan_digest)):
            raise EnrollmentDenied('Review your own initial plan first')
        initial = self.initial(row['grant'], 'create', plan_digest=plan_digest, password=password, confirmation=confirmation)
        return {**self.view(row), 'initial': initial, 'resources_created': initial.get('resources_created', False)}

    def advance(self, subject, email, session_id, token_hash):
        row,person,_=self.current(subject,email,session_id,token_hash)
        self.live(row)
        if self.initial is None or row.get('bound_subject')!=person or row['stage']!='CREATE_REQUESTED':
            raise EnrollmentDenied('Own confirmed setup request required')
        if row.get('registration') and row.get('registration_complete') is not True:
            raise EnrollmentDenied('Complete own grading registration first')
        initial=self.initial(row['grant'],'advance')
        return {**self.view(row),'initial':initial,'resources_created':initial.get('resources_created',False)}

    def registration_context(self,**claims):
        from initial_registration import InitialRegistration
        return InitialRegistration(self).context(**claims)

    def register(self,delivery=None,**claims):
        from initial_registration import InitialRegistration
        return InitialRegistration(self).register(delivery=delivery,**claims)
