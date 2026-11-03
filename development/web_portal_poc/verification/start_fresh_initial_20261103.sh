#!/usr/bin/env bash
# Fixed acceptance runner for the approved Class193548 retest, not a cohort installer.
# apply is initiated by the human and requests the RDP password through the signed core.
set -euo pipefail
umask 077
WORK="$HOME/jdu-web-renewal-20261103-r3"
KIT="$WORK/jdu-web-course"
CORE="$KIT/foundation/core/jdu-web-lab"
STATE="$WORK/fresh-state.private.json"
PLAN="$WORK/fresh-create-plan.private.json"
DELIVERY="$WORK/fresh-delivery"
LAB_ID='class193548-retest1'
FP='65EC6784750CCFA703BA7179519284E45155EC2A'

[[ "$(aws sts get-caller-identity --query Account --output text)" == '965244652544' ]]
python3 -B "$KIT/student.py" verify --trusted-fingerprint "$FP"
python3 -B - "$PLAN" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))
assert p['account']=='965244652544' and p['lab_id']=='class193548-retest1'
assert p['deployment_id']=='1e757ad7-b719-49d6-be80-209c24df052f'
assert p['manifest_sha256']=='cdeaace960c8cae0328cbc360be542baeeb3889366989481f7bc9d3623a683dc'
assert p['stack_name']=='jdu-web-class193548-retest1'
print('FRESH_INITIAL_REVIEW_READY; original five must already be retired with roots retained')
PY
if [[ "${1:-review}" == 'review' ]]; then exit 0; fi
[[ "${1:-}" == 'apply' ]]
[[ ! -e "$STATE" ]] || { echo 'Existing state retained. Inspect status; never repeat initial create.'; exit 2; }
RECIPIENT_SHA='62560599cee0a2f606af4f96ad3db656b7f8ebd7314ad22ad81f52178e0847c8'
CIPHER_SHA=$(python3 -B - "$WORK/fresh-delivery.public.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d['lab_id']=='class193548-retest1' and d['student_account']=='965244652544'
print(d['ciphertext_sha256'])
PY
)
if [[ ! -d "$DELIVERY/received" ]]; then
  python3 -B "$KIT/foundation/distribution.py" receive --trusted-fingerprint "$FP" \
    --workspace "$DELIVERY" --ciphertext "$WORK/fresh-student-delivery.encrypted.cms" \
    --recipient-sha256 "$RECIPIENT_SHA" --ciphertext-sha256 "$CIPHER_SHA" --confirmed-access
fi
OWN="$DELIVERY/received/own-student.credentials.json"
bash "$CORE" create --plan "$PLAN" --state "$STATE" --confirmed-access \
  --bootstrap-url-file "$DELIVERY/received/bootstrap-url.private.txt"
aws cloudformation wait stack-create-complete --region us-east-1 --stack-name "jdu-web-$LAB_ID"

wait_phase() {
  local expected="$1"
  for attempt in $(seq 1 24); do
    if bash "$CORE" status --state "$STATE"; then
      phase=$(python3 -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["phase"])' "$STATE")
      [[ "$phase" == "$expected" ]] && return 0
    fi
    echo "Waiting for observed $expected ($attempt/24); create is not repeated."
    sleep 15
  done
  echo "Initial state retained; inspect the existing stack and state."
  return 2
}
wait_phase BASE_READY
bash "$CORE" lock-prepare --state "$STATE"
CHANGE=$(python3 -B -c 'import json,sys;print(json.load(open(sys.argv[1]))["change_set_id"])' "$STATE.closure.json")
aws cloudformation wait change-set-create-complete --region us-east-1 --stack-name "jdu-web-$LAB_ID" --change-set-name "$CHANGE"
bash "$CORE" lock-review --state "$STATE"
bash "$CORE" lock-apply --state "$STATE"
aws cloudformation wait stack-update-complete --region us-east-1 --stack-name "jdu-web-$LAB_ID"
wait_phase INFRA_READY
bash "$CORE" ssh-plan --state "$STATE"
bash "$CORE" ssh-apply --state "$STATE"
# The original verifier waits for temporary EIC keys to expire before its check.
for part in 1 2 3; do sleep 21; done
bash "$CORE" ssh-verify --state "$STATE"
bash "$CORE" register-plan --state "$STATE" --student-config "$OWN"
bash "$CORE" register-apply --state "$STATE" --student-config "$OWN"
bash "$CORE" register-verify --state "$STATE" --student-config "$OWN"
bash "$CORE" install-commands --state "$STATE" --student-config "$OWN" \
  --bin-directory "$WORK/fresh-foundation-bin"
COMMAND_STATE="$HOME/.jdu-web-student/$LAB_ID/command-state.json"
python3 -B "$KIT/student.py" install --trusted-fingerprint "$FP" --command-state "$COMMAND_STATE"
INSTALL="$HOME/.local/share/jdu-web/courses/web-course-class193548-20261103-r3/$LAB_ID"
python3 -B "$WORK/resources/stage_resources.py" --installation "$INSTALL"
echo 'FRESH_INITIAL_BASELINE_COMPLETE; GUI and browser enrollment/task acceptance follow.'
