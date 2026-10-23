"""Fresh, deployment-bound public evidence over existing SSM permissions."""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import time
import uuid


def validate(value, request):
    if (any(value.get(k) != request[k] for k in ('nonce', 'lab_id', 'deployment_id', 'role', 'instance_id'))
            or value.get('all_fresh_checks_passed') is not True or value.get('private_data_exported') is not False
            or value.get('class_ready') is not False or not value.get('fresh_checks')
            or any(v is not True for v in value['fresh_checks'].values())):
        raise ValueError('Fresh SSM identity/checks differ')
    stamp = datetime.fromisoformat(value['fresh_checked_at'])
    if stamp.tzinfo is None or not -5 <= (datetime.now(timezone.utc) - stamp).total_seconds() <= 120:
        raise ValueError('Fresh SSM result expired')
    return value


def collect(ssm, state, role, instance_id, phase):
    here = Path(__file__).resolve().parent
    request = {k: state[k] for k in ('lab_id', 'deployment_id')}
    request['expected_scope']=state.get('expected_scope','package_only_candidate')
    request.update(role=role, instance_id=instance_id, release_id=state['release_id'], phase=phase,
        nonce=uuid.uuid4().hex, network_source_sha256=hashlib.sha256((here / 'network_probe.py').read_bytes()).hexdigest())
    source = base64.b64encode((here / 'node_evidence_guest.py').read_bytes()).decode()
    payload = base64.b64encode(json.dumps(request).encode()).decode()
    code = ("import base64,io,sys;sys.stdin=io.StringIO(base64.b64decode('" + payload
        + "').decode());exec(base64.b64decode('" + source + "'))")
    job = ssm.send_command(InstanceIds=[instance_id], DocumentName='AWS-RunShellScript',
        Parameters=dict(commands=['python3 -c ' + shlex.quote(code)], executionTimeout=['90']))['Command']['CommandId']
    for _ in range(45):
        try: response = ssm.get_command_invocation(CommandId=job, InstanceId=instance_id)
        except ssm.exceptions.InvocationDoesNotExist:
            time.sleep(1); continue
        if response['Status'] == 'Success': return validate(json.loads(response['StandardOutputContent']), request)
        if response['Status'] in ('Failed', 'TimedOut', 'Cancelled', 'Cancelling'):
            raise ValueError('Fresh SSM check failed; no private output exported')
        time.sleep(2)
    raise ValueError('Fresh SSM check pending; do not invent acceptance')
