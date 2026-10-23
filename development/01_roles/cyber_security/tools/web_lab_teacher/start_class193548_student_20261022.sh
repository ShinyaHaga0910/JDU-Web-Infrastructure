#!/usr/bin/env bash
# Reviewed Class193548 deployment using the preserved credential and fresh delivery.
set -euo pipefail
umask 077
mode="${1:-review}"
case "$mode" in
  review) ;;
  apply) [[ "${2:-}" == --confirmed-access && -t 0 && -t 1 ]] || exit 2 ;;
  *) exit 2 ;;
esac

python3 -B - <<'PY'
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import boto3
from botocore.exceptions import ClientError

base = Path.home() / 'jdu-web-class193548'
kit = base / 'cross-account-delivery-v1'
pins = {
    'class_student_delivery.py': '1bbaf46daa1eed027e17e422e64ff0af5e8f24791d36df2f2379a57ff652a184',
    'web_progress.py': 'a966bbe49eefdb4fc6f9ca1dc39d930532992490923fde155caf3ed5a5aed6a4',
    'release_validation.py': 'e9aebc2f1ed3d54df70e862e5a9aabe8e08970004106c8a89a6260da9e34096c',
}
for name, pin in pins.items():
    assert hashlib.sha256((kit / name).read_bytes()).hexdigest() == pin
sys.path.insert(0, str(kit))
import class_student_delivery as delivery

session = boto3.Session(region_name='us-east-1')
delivery.identity(session, delivery.STUDENT)
tools = delivery.verified_tools(base / 'student-software-v7/student-tools')
assert tools['manifest_sha256'] == 'a00239fa1cb8efc09d8cad214c6e97f5c99f1436c9549c3f66bf09ea9ee4a3d2'
plan = json.loads(delivery.read(base / 'student-v7-plan-20261022.private.json', private=True))
assert plan['account'] == delivery.STUDENT
assert plan['lab_id'] == 'class193548-test1'
assert plan['stack_name'] == 'jdu-web-class193548-test1'
assert plan['deployment_id'] == '3ab82943-031d-4806-b4c0-c0b0e4554006'
assert plan['manifest_sha256'] == tools['manifest_sha256']
assert not plan['resources_created']
now = datetime.now(timezone.utc)
planned = datetime.fromisoformat(plan['planned_at'])
assert planned <= now < planned + timedelta(days=1)
assert not (base / 'student-v7.private.json').exists()
assert not (base / 'student-delivery-v7/received').exists()
workspace = base / 'student-delivery-renewal-20261022'
assert not (workspace / 'received').exists()
recipient = '725f91c0b5243aa7cda56f0ca77ebcb176c8cc4a42297e639cb255b28a39008b'
request = json.loads(delivery.read(workspace / 'recipient-request.public.json', private=True))
delivery.validate_request(request, recipient, now)
assert request['lab_id'] == plan['lab_id']
receipt = json.loads(delivery.read(workspace / 'refresh.public.json', private=True))
assert receipt['scope'] == 'existing_student_credential_repackaged'
assert receipt['existing_credential_preserved'] is True
assert receipt['new_credential_issued'] is False
assert receipt['teacher_admin_transferred'] is False
assert receipt['student_account'] == delivery.STUDENT
assert receipt['teacher_account'] == delivery.TEACHER
assert receipt['manifest_sha256'] == tools['manifest_sha256']
assert receipt['lab_id'] == plan['lab_id']
assert receipt['recipient_sha256'] == recipient
assert receipt['bound_deployment_id'] is None
assert datetime.fromisoformat(receipt['created_at']) <= now < datetime.fromisoformat(receipt['expires_at'])
ciphertext = delivery.read(workspace / 'student-delivery-20261022.encrypted.cms', private=True)
assert len(ciphertext) == 2981
assert hashlib.sha256(ciphertext).hexdigest() == receipt['ciphertext_sha256'] == '237e5bb1feb368378a0803a6c123ff342d00bff6093e7ea03766e0c8d97c8bdd'
assert hashlib.sha256((base / 'teacher-price-catalog-20261022.json').read_bytes()).hexdigest() == '0c9d6660d7bedab96d2f4b94d1ec801094033bfa59c789f5e6ba587d1fe8ab0d'
instances = session.client('ec2').describe_instances(Filters=[{'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped']}])
assert not any(r['Instances'] for r in instances['Reservations'])
try:
    session.client('cloudformation').describe_stacks(StackName=plan['stack_name'])
except ClientError as exc:
    assert exc.response['Error']['Code'] == 'ValidationError'
    assert 'does not exist' in exc.response['Error']['Message']
else:
    raise ValueError('Student stack already exists; inspect partial progress')
print('CLASS193548_STUDENT_20261022_REVIEW_PASSED; no credential received or resources created')
PY

[[ "$mode" == apply ]] || exit 0
base="$HOME/jdu-web-class193548"
python3 -B "$base/cross-account-delivery-v1/class_student_delivery.py" receive \
  --workspace "$base/student-delivery-renewal-20261022" \
  --recipient-sha256 725f91c0b5243aa7cda56f0ca77ebcb176c8cc4a42297e639cb255b28a39008b \
  --ciphertext "$base/student-delivery-renewal-20261022/student-delivery-20261022.encrypted.cms" \
  --tools "$base/student-software-v7/student-tools" --confirmed-access
exec bash "$base/student-software-v7/student-tools/jdu-web-lab" create \
  --plan "$base/student-v7-plan-20261022.private.json" \
  --state "$base/student-v7.private.json" \
  --bootstrap-url-file "$base/student-delivery-renewal-20261022/received/bootstrap-url.private.txt" \
  --confirmed-access
