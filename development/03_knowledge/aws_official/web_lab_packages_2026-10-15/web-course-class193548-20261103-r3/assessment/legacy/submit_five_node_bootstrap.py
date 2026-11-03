"""Submit observed guest checks and verify their exact storage in the teacher table."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

ROLES = {'bastion', 'web', 'dns', 'db', 'repo'}


def build_report(evidence, state, nodes, request_id):
    if (evidence['scope'] != 'fresh_post_stop_start_guest_acceptance'
            or evidence['lab_id'] != state['lab_id'] or evidence['deployment_id'] != state['deployment_id']
            or set(evidence['nodes']) != ROLES):
        raise ValueError('Guest evidence belongs to another deployment')
    checks = []
    for role in sorted(ROLES):
        node = evidence['nodes'][role]
        if node['role'] != role or node['instance_id'] != nodes[role]['instance_id']:
            raise ValueError('Observed node differs from live deployment')
        for group, prefix in [('checks', 'GUEST_'), ('network', 'NET_')]:
            for name, value in sorted(node[group].items()):
                if value is not None and type(value) is not bool:
                    raise ValueError('Evidence must be boolean or unknown')
                checks.append(dict(id=prefix + name.upper(), role=role, instance_id=node['instance_id'],
                                   status='UNKNOWN' if value is None else 'PASS' if value else 'FAIL'))
    return dict(schema_version=1, kind='bootstrap', lab_id=state['lab_id'], release_id='web-2026-10-r1',
                deployment_id=state['deployment_id'], request_id=request_id, checks=checks)


def main():
    import boto3
    from boto3.dynamodb.types import TypeDeserializer
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('state', 'baseline-plan', 'evidence', 'pending', 'output', 'bootstrap-tools'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    os.umask(0o077)
    sys.path.insert(0, a.bootstrap_tools)
    from setup_internal_ssh import current_nodes, remote, save_new
    state = json.loads(Path(a.state).read_text())
    baseline = json.loads(Path(a.baseline_plan).read_text())
    if (boto3.client('sts').get_caller_identity()['Account'] != state['account']
            or any(state[k] != baseline[k] for k in ('account', 'stack_id', 'deployment_id'))):
        raise ValueError('Wrong account or deployment')
    cfn = boto3.client('cloudformation', region_name='us-east-1')
    nodes = current_nodes(boto3.client('ec2', region_name='us-east-1'), cfn, state, baseline)
    evidence_bytes = Path(a.evidence).read_bytes()
    evidence = json.loads(evidence_bytes)
    pending = Path(a.pending)
    previous = json.loads(pending.read_text()) if pending.exists() else None
    report = build_report(evidence, state, nodes, previous['request_id'] if previous else str(uuid.uuid4()))
    if previous is not None and previous != report:
        raise ValueError('Existing pending report differs; retained without transmission')
    if previous is None:
        save_new(pending, report)
    source = Path(__file__).with_name('bootstrap_submission_guest.py').read_bytes()
    ack = remote(boto3.client('ssm', region_name='us-east-1'), nodes['bastion']['instance_id'], source, {'report': report})
    outputs = {x['OutputKey']: x['OutputValue'] for x in cfn.describe_stacks(StackName='jdu-web-progress-2026')['Stacks'][0]['Outputs']}
    db = boto3.client('dynamodb', region_name='us-east-1')
    decode = TypeDeserializer()
    def read(sk, fields):
        raw = db.get_item(TableName=outputs['TableName'],
            Key={'pk': {'S': 'LAB#' + state['lab_id']}, 'sk': {'S': sk}}, ConsistentRead=True,
            ProjectionExpression=', '.join('#f' + str(i) for i in range(len(fields))),
            ExpressionAttributeNames={'#f' + str(i): f for i, f in enumerate(fields)})['Item']
        return {k: decode.deserialize(v) for k, v in raw.items()}
    stored = read('REQUEST#' + report['request_id'], ['report', 'receipt', 'body_sha256'])
    meta = read('META', ['lab_id', 'release_id', 'deployment_id', 'instances', 'last_result'])
    canonical = json.dumps(report, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    if (stored['report'] != report or stored['receipt'] != ack['receipt']
            or stored['body_sha256'] != hashlib.sha256(canonical.encode()).hexdigest()
            or meta['last_result']['request_id'] != report['request_id']
            or meta['instances'] != {r: n['instance_id'] for r, n in nodes.items()}
            or int(meta['last_result']['passed']) != ack['passed']
            or int(meta['last_result']['total']) != len(report['checks'])):
        raise ValueError('Teacher persisted report, receipt or summary differs')
    public = dict(ack, teacher_storage_exact_match=True, teacher_latest_summary_matches=True,
                  report_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
                  evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest(),
                  observed_at=evidence['checked_at'], checked_at=datetime.now(timezone.utc).isoformat(),
                  scope='observed_guest_foundation_checks_not_app_or_class_acceptance')
    save_new(a.output, public)
    print('FIVE_NODE_BOOTSTRAP_SUBMISSION=' + json.dumps(public, separators=(',', ':')))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('FIVE_NODE_BOOTSTRAP_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
