"""Save the IAM-fetched original checker report through canonical D11 writes.

No Bearer token is recovered, exported or reissued. The trusted owner binding
and teacher approval are condition-checked with the original grade transaction.
The browser cannot provide a report, score, account, Lab or resource target.
"""
import re

import progress_api as legacy
from progress_api_v2 import assessment_attempt
from assessment_command_jobs import checked_spec, native
from registry import validate_report, score


class PortalSubmissions:
    def __init__(self, bindings, grades):
        self.bindings, self.grades = bindings, grades

    def guards(self, spec, meta):
        owner = 'SUBJECT#' + spec['owner_hash']
        person = self.bindings.get(owner, 'BINDING')
        wanted = {k: spec[k] for k in ('account', 'lab_id', 'deployment_id')}
        if (not person or person.get('active') is not True
                or any(person.get(k) != v for k, v in wanted.items())
                or person.get('token_hash') != meta['token_hash']
                or not re.fullmatch(r'APPROVAL#[a-f0-9]{64}', person.get('approval_pk', ''))):
            raise legacy.ApiError(401, 'unauthorized')
        wanted['connector'] = person['connector']
        approval = self.bindings.get(person['approval_pk'], 'LAB')
        if (not approval or approval.get('active') is not True or approval.get('bound_subject') != owner
                or not isinstance(approval.get('grant'), dict) or approval['grant'].get('account') != spec['account']
                or any(approval['grant'].get(k) != meta.get(k) for k in ('lab_id', 'deployment_id', 'token_hash', 'instances'))):
            raise legacy.ApiError(401, 'unauthorized')
        rows = [(owner, 'BINDING', {**wanted, 'active': True, 'token_hash': meta['token_hash'], 'approval_pk': person['approval_pk']}),
            ('LAB#' + spec['lab_id'], 'SUBJECT', {'subject_pk': owner}),
            ('LAB#' + spec['lab_id'], 'BINDING', wanted),
            ('ACCOUNT#' + spec['account'], 'BINDING', wanted),
            (person['approval_pk'], 'LAB', {'active': True, 'bound_subject': owner, 'grant': approval['grant']})]
        guards = []
        for pk, sk, fields in rows:
            names = {f'#f{i}': name for i, name in enumerate(fields)}
            values = {f':v{i}': value for i, value in enumerate(fields.values())}
            guards.append({'ConditionCheck': {'TableName': self.bindings.table,
                'Key': self.grades.pack({'pk': pk, 'sk': sk}),
                'ConditionExpression': ' AND '.join(f'#f{i}=:v{i}' for i in range(len(fields))),
                'ExpressionAttributeNames': names, 'ExpressionAttributeValues': self.grades.pack(values)}})
        return guards

    def context(self, spec, meta, report):
        checked_spec(spec)
        validate_report(report, spec['instances'])
        if (meta.get('active') is not True or meta.get('pk') != 'LAB#' + spec['lab_id']
                or any(meta.get(k) != spec[k] for k in ('lab_id', 'release_id', 'deployment_id', 'instances'))
                or any(report.get(k) != spec[k] for k in ('lab_id', 'deployment_id', 'release_id', 'run_id'))
                or report['mission_id'] != spec['task_id'] or report['mode'] != 'read_only'):
            raise legacy.ApiError(401, 'unauthorized')

    def same_attempt(self, row, spec, report):
        return (row and row.get('portal_job_id') == spec['job_id'] and row.get('portal_owner_hash') == spec['owner_hash']
            and row.get('body_sha256') == legacy.digest(legacy.encoded(report)) and native(row.get('report')) == report)

    def meta_condition(self, spec, meta):
        return {'ConditionCheck': {'TableName': self.grades.table,
            'Key': self.grades.pack({'pk': meta['pk'], 'sk': 'META'}),
            'ConditionExpression': '#active=:yes AND token_hash=:token AND deployment_id=:deployment AND #instances=:instances AND release_id=:release',
            'ExpressionAttributeNames': {'#active': 'active', '#instances': 'instances'},
            'ExpressionAttributeValues': self.grades.pack({':yes': True, ':token': meta['token_hash'],
                ':deployment': spec['deployment_id'], ':instances': spec['instances'], ':release': spec['release_id']})}}

    def save(self, trusted_spec, meta, original_report):
        spec, report = checked_spec(trusted_spec), native(original_report)
        self.context(spec, meta, report)
        guards = self.guards(spec, meta)
        attempt, summary = assessment_attempt(meta, report)
        attempt.update(portal_job_id=spec['job_id'], portal_owner_hash=spec['owner_hash'])
        existing = self.grades.get(attempt['pk'], attempt['sk'])
        if existing:
            if not self.same_attempt(existing, spec, report):
                raise legacy.ApiError(409, 'request conflict')
            # Retry acknowledgments require current authorization too. These
            # condition checks mutate no rows and never reorder a saved grade.
            self.grades.client.transact_write_items(TransactItems=guards + [self.meta_condition(spec, meta)])
            return self.public(existing, report)
        writes = self.grades.submission_writes(meta, attempt, summary)
        update = next(w['Update'] for w in writes if 'Update' in w)
        update['ConditionExpression'] += ' AND #instances=:instances AND release_id=:release'
        update['ExpressionAttributeNames']['#instances'] = 'instances'
        update['ExpressionAttributeValues'].update(self.grades.pack({':instances': spec['instances'], ':release': spec['release_id']}))
        try:
            self.grades.client.transact_write_items(TransactItems=writes + guards)
        except self.grades.client.exceptions.TransactionCanceledException:
            existing = self.grades.get(attempt['pk'], attempt['sk'])
            if not self.same_attempt(existing, spec, report):
                raise legacy.ApiError(409, 'request conflict or authorization changed') from None
            self.grades.client.transact_write_items(TransactItems=guards + [self.meta_condition(spec, meta)])
            return self.public(existing, report)
        return self.public(attempt, report)

    def lookup(self, spec, meta, request_id):
        row = self.grades.get(meta['pk'], 'REQUEST#' + request_id)
        if not row:
            return {'status': 'pending'}
        report = native(row.get('report'))
        self.context(spec, meta, report)
        if not self.same_attempt(row, spec, report) or report['request_id'] != request_id:
            raise legacy.ApiError(409, 'request conflict')
        return self.public(row, report)

    @staticmethod
    def public(row, report):
        receipt = row['receipt']
        if receipt.get('stored') is not True or receipt.get('request_id') != report['request_id']:
            raise legacy.ApiError(409, 'invalid receipt')
        result = score(report)
        return {'status': 'saved', 'request_id': report['request_id'], 'received_at': receipt['received_at'],
            'counts_toward_assessment': result['counts_toward_assessment'], 'evaluable': result['evaluable']}
