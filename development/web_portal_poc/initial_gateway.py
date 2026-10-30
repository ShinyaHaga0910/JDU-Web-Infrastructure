"""Teacher IAM service -> the assigned student initial worker only."""
import json

from portal_enrollment import EnrollmentDenied, grant_digest
from portal_preparation import checked_assignment

INITIAL_FIELDS = {'stage', 'stack_id', 'stack_status', 'stack_created', 'resources_created', 'lab_ready',
    'plan_digest', 'planned_at', 'account', 'lab_id', 'deployment_id', 'resource_budget', 'root_gib',
    'new_nodes', 'availability_zone', 'instance_types', 'compute_hourly_usd',
    'price_includes_disks_ipv4_endpoints', 'initial_state'}


class InitialGateway:
    def __init__(self, client):
        self.client = client

    def __call__(self, grant, operation, **fields):
        grant = checked_assignment(grant)
        required = {'plan_digest', 'password', 'confirmation'} if operation == 'create' else set()
        if operation not in ('plan', 'observe', 'create') or set(fields) != required:
            raise EnrollmentDenied('Invalid initial operation')
        arn = f'arn:aws:lambda:us-east-1:{grant["account"]}:function:jdu-web-initial-{grant["lab_id"]}'
        result = self.client.invoke(FunctionName=arn, InvocationType='RequestResponse', Payload=json.dumps({
            'operation': operation, 'grant_digest': grant_digest(grant), **fields}).encode('utf-8'))
        body = result.get('Payload')
        try:
            data = body.read(16385) if body else b''
        finally:
            if hasattr(body, 'close'):
                body.close()
        if result.get('StatusCode') != 200 or result.get('FunctionError') or len(data) > 16384:
            raise RuntimeError('Initial worker unavailable')
        value = json.loads(data)
        if value.get('status') == 'resource_budget':
            budget = value.get('resource_budget')
            allowed = {'existing_nonterminated', 'new_nodes', 'pilot_ceiling', 'projected', 'within_pilot_budget'}
            if (type(budget) is not dict or set(budget) != allowed
                    or any(type(budget[k]) is not int or not 0 <= budget[k] <= 1000 for k in allowed - {'within_pilot_budget'})
                    or budget['within_pilot_budget'] is not False):
                raise RuntimeError('Initial worker unavailable')
            return {'stage': 'RESOURCE_BUDGET', 'resource_budget': budget}
        initial = value.get('initial')
        if value.get('status') != 'ok' or type(initial) is not dict or not isinstance(initial.get('stage'), str):
            raise RuntimeError('Initial worker unavailable')
        # This is a projection, never a passthrough of arbitrary Lambda output.
        return {k: v for k, v in initial.items() if k in INITIAL_FIELDS}
