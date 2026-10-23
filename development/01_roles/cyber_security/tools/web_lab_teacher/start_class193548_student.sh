#!/usr/bin/env bash
# Class193548's reviewed first deployment only. Run apply yourself in student CloudShell.
set -euo pipefail
umask 077
mode="${1:-review}"
case "$mode" in
  review) ;;
  apply) [[ "${2:-}" == --confirmed-access && -t 0 && -t 1 ]] || exit 2 ;;
  *) exit 2 ;;
esac

python3 -B - <<'PY'
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import boto3

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

delivery.identity(boto3.Session(region_name='us-east-1'), delivery.STUDENT)
tools = delivery.verified_tools(base / 'student-software-v7/student-tools')
assert tools['manifest_sha256'] == 'a00239fa1cb8efc09d8cad214c6e97f5c99f1436c9549c3f66bf09ea9ee4a3d2'
plan = json.loads(delivery.read(base / 'student-v7-plan-20261020.private.json', private=True))
assert plan['account'] == delivery.STUDENT
assert plan['lab_id'] == 'class193548-test1'
assert plan['stack_name'] == 'jdu-web-class193548-test1'
assert plan['deployment_id'] == '340ae393-3536-42db-94a3-6bbdb89bdc41'
assert plan['manifest_sha256'] == tools['manifest_sha256']
assert not plan['resources_created']
assert not (base / 'student-v7.private.json').exists()
workspace = base / 'student-delivery-v7'
assert not (workspace / 'received').exists()
request = json.loads(delivery.read(workspace / 'recipient-request.public.json', private=True))
delivery.validate_request(request, 'c32786b2e64646a6acc65c8d758ee4e4724fe0d326d0f0fbe3e734ccf794c228', datetime.now(timezone.utc))
ciphertext = delivery.read(workspace / 'student-delivery-v7.encrypted.cms', private=True)
assert len(ciphertext) == 2943
assert hashlib.sha256(ciphertext).hexdigest() == '5e98abb15e4d182d94ba4854511484e5597255a89de654bead9fdc7333abb26f'
print('CLASS193548_STUDENT_FIRST_CREATE_REVIEW_PASSED; no credential received or resources created')
PY

[[ "$mode" == apply ]] || exit 0
base="$HOME/jdu-web-class193548"
python3 -B "$base/cross-account-delivery-v1/class_student_delivery.py" receive \
  --workspace "$base/student-delivery-v7" \
  --recipient-sha256 c32786b2e64646a6acc65c8d758ee4e4724fe0d326d0f0fbe3e734ccf794c228 \
  --ciphertext "$base/student-delivery-v7/student-delivery-v7.encrypted.cms" \
  --tools "$base/student-software-v7/student-tools" --confirmed-access
exec bash "$base/student-software-v7/student-tools/jdu-web-lab" create \
  --plan "$base/student-v7-plan-20261020.private.json" \
  --state "$base/student-v7.private.json" \
  --bootstrap-url-file "$base/student-delivery-v7/received/bootstrap-url.private.txt" \
  --confirmed-access
