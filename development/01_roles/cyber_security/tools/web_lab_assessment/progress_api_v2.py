"""D11 additive API. v1 reports remain immutable progress, never implicit grades."""
import hmac
import time

import progress_api as legacy
from dashboard import render
from grading import export_labs, grade_key, current_key
from registry import CONTRACT_ID, score, validate_report


class AssessmentStore(legacy.DynamoStore):
    def submission_writes(self, meta, attempt, summary):
        """Canonical v2 writes, also used by the private portal authorizer."""
        contract = summary['contract_sha256']
        latest = dict(summary, pk=meta['pk'], sk=current_key(attempt['report']['mission_id'], contract),
                      checks=attempt['report']['checks'])
        writes = [
            {'Put': {'TableName': self.table, 'Item': self.pack(attempt), 'ConditionExpression': 'attribute_not_exists(pk)'}},
            {'Put': {'TableName': self.table, 'Item': self.pack(latest),
                     'ConditionExpression': 'attribute_not_exists(received_at) OR received_at<=:now',
                     'ExpressionAttributeValues': self.pack({':now': attempt['received_at']})}},
            {'Update': {'TableName': self.table, 'Key': self.pack({'pk': meta['pk'], 'sk': 'META'}),
                        'UpdateExpression': 'SET last_result=:summary, updated_at=:now',
                        'ConditionExpression': 'token_hash=:token AND deployment_id=:deployment AND #active=:active AND updated_at<=:now',
                        'ExpressionAttributeNames': {'#active': 'active'},
                        'ExpressionAttributeValues': self.pack({':summary': summary, ':now': attempt['received_at'],
                            ':token': meta['token_hash'], ':deployment': meta['deployment_id'], ':active': True})}}]
        if summary['counts_toward_assessment'] and summary['evaluable']:
            grade = dict(latest, sk=grade_key(attempt['report']['mission_id'], contract))
            writes.append({'Put': {'TableName': self.table, 'Item': self.pack(grade),
                                   'ConditionExpression': 'attribute_not_exists(received_at) OR received_at<=:now',
                                   'ExpressionAttributeValues': self.pack({':now': attempt['received_at']})}})
        return writes

    def submit(self, meta, attempt, summary):
        if attempt['report']['schema_version'] == 1:
            return super().submit(meta, attempt, summary)
        writes = self.submission_writes(meta, attempt, summary)
        try:
            self.client.transact_write_items(TransactItems=writes)
        except self.client.exceptions.TransactionCanceledException:
            existing = self.get(attempt['pk'], attempt['sk'])
            if existing and existing['body_sha256'] == attempt['body_sha256']:
                return existing['receipt']
            raise legacy.ApiError(409, 'request conflict or credentials changed')
        return attempt['receipt']

    def classify(self, meta, context):
        self.client.update_item(TableName=self.table, Key=self.pack({'pk': meta['pk'], 'sk': 'META'}),
            UpdateExpression='SET assessment_context=:context',
            ConditionExpression='deployment_id=:deployment AND #active=:active',
            ExpressionAttributeNames={'#active': 'active'},
            ExpressionAttributeValues=self.pack({':context': context, ':deployment': meta['deployment_id'], ':active': True}))

    def labs(self, only_lab=None):
        # Existing store keeps current records; add selected eligible snapshots.
        labs = super().labs(only_lab)
        for lab in labs:
            cursor = None
            while True:
                args = dict(TableName=self.table, KeyConditionExpression='pk=:pk AND begins_with(sk,:prefix)',
                            ExpressionAttributeValues=self.pack({':pk': lab['pk'], ':prefix': 'GRADE#'}),
                            ConsistentRead=True)
                if cursor:
                    args['ExclusiveStartKey'] = cursor
                answer = self.client.query(**args)
                lab['results'].extend({k: self.deserializer.deserialize(v) for k, v in item.items()} for item in answer.get('Items', []))
                cursor = answer.get('LastEvaluatedKey')
                if not cursor:
                    break
        return labs


def assessment_attempt(row, body):
    """Prepare one canonical report, after the caller has authorized its Lab.

    This function is not authentication and does not write anything. HTTP uses
    the existing Bearer authorizer; the private portal uses its approved owner
    binding and checks that binding in the same transaction as these writes.
    """
    if row.get('deployment_id') != body.get('deployment_id') or body.get('release_id') != row['release_id']:
        raise legacy.ApiError(409, 'unregistered or mismatched deployment')
    try:
        validate_report(body, row['instances'])
    except (ValueError, TypeError, KeyError, AttributeError):
        raise legacy.ApiError(400, 'invalid canonical assessment report')
    stamp = legacy.now_iso()
    summary = dict(kind='assessment', mission_id=body['mission_id'], request_id=body['request_id'],
                       deployment_id=body['deployment_id'], received_at=stamp, checked_at=body['checked_at'],
                       contract_id=body['contract_id'], contract_sha256=body['contract_sha256'],
                       passed=sum(c['status'] == 'PASS' for c in body['checks']), total=len(body['checks']),
                       unknown=sum(c['status'] not in ('PASS', 'FAIL') for c in body['checks']), **score(body))
    receipt = dict(ok=True, stored=True, lab_id=row['lab_id'], deployment_id=body['deployment_id'],
                       release_id=row['release_id'], request_id=body['request_id'], received_at=stamp,
                       kind='assessment', contract_id=body['contract_id'], contract_sha256=body['contract_sha256'])
    attempt = dict(pk=row['pk'], sk='REQUEST#' + body['request_id'], report=body, receipt=receipt,
                       received_at=stamp, body_sha256=legacy.digest(legacy.encoded(body)))
    return attempt, summary


class AssessmentService(legacy.ProgressService):
    def submit(self, event):
        body = legacy.parse_body(event)
        if body.get('schema_version') == 1:
            return super().submit(event)
        row = self.lab(event, body)
        attempt, summary = assessment_attempt(row, body)
        return legacy.response(200, self.store.submit(row, attempt, summary))

    def classify(self, event):
        self.admin(event)
        body = legacy.parse_body(event)
        legacy.require_keys(body, ('lab_id', 'deployment_id', 'context', 'contract_id'))
        lab_id = legacy.field(body, 'lab_id', legacy.LAB_RE, maximum=32)
        if body['context'] not in ('course', 'verification') or body['contract_id'] != CONTRACT_ID:
            raise legacy.ApiError(400, 'invalid assessment context')
        meta = self.store.get('LAB#' + lab_id, 'META')
        if not meta or not meta.get('active') or meta.get('deployment_id') != legacy.uuid_field(body, 'deployment_id'):
            raise legacy.ApiError(409, 'wrong registered deployment')
        self.store.classify(meta, body['context'])
        return legacy.response(200, dict(ok=True, lab_id=lab_id, context=body['context']))

    def dashboard(self, event):
        query = event.get('queryStringParameters') or {}
        token = query.get('session', '')
        if type(token) is not str or not 40 <= len(token) <= 128:
            raise legacy.ApiError(401, 'session expired')
        session = self.store.get('SESSION#' + legacy.digest(token), 'SESSION')
        if not session or session['expires_at'] <= int(time.time()) or session['role'] not in ('teacher', 'student'):
            raise legacy.ApiError(401, 'session expired')
        if session['role'] == 'student':
            meta = self.store.get('LAB#' + session['lab_id'], 'META')
            if not meta or not meta.get('active') or not hmac.compare_digest(meta['token_hash'], session['token_hash']):
                raise legacy.ApiError(401, 'session expired')
        labs = self.store.labs(session['lab_id'] if session['role'] == 'student' else None)
        return legacy.response(200, render(labs, session['role'], token, query.get('lang', 'ja'), query.get('pause') == '1',
                                           current_curriculum=bool(self.enrollment_hash)),
                               'text/html; charset=utf-8')

    def handle(self, event):
        try:
            if event.get('routeKey') == 'POST /api/web/admin/assessment-context':
                return self.classify(event)
            if event.get('routeKey') == 'POST /api/web/admin/grades':
                self.admin(event)
                body = legacy.parse_body(event)
                legacy.require_keys(body, (), ('after',))
                after = legacy.field(body, 'after', legacy.LAB_RE, maximum=32) if 'after' in body else ''
                return legacy.response(200, export_labs(self.store.labs(), after, current_curriculum=bool(self.enrollment_hash)))
            return super().handle(event)
        except legacy.ApiError as exc:
            return legacy.response(exc.status, {'error': exc.message})
        except Exception:
            return legacy.response(503, {'error': 'service unavailable'})


_service = None


def handler(event, context):
    global _service
    if _service is None:
        import os
        _service = AssessmentService(AssessmentStore(os.environ['TABLE_NAME']), os.environ['ADMIN_KEY_HASH'],
                                     os.environ['API_BASE_URL'], os.environ.get('ENROLLMENT_KEY_HASH', ''))
    return _service.handle(event)
