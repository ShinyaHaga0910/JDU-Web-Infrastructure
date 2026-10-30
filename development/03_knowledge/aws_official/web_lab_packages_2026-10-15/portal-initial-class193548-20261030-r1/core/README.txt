Web Lab student tools - CANDIDATE
Not a formal release. CLASS_READY remains false pending fresh acceptance.
Verify this archive signature with the independently supplied full fingerprint before extraction.
Never download a private SSH key to Windows. Run in your individual Academy CloudShell.

Plan only (no resources or credentials are created):
./jdu-web-lab plan --lab-id YOUR-LAB-ID --output PRIVATE-PLAN.json --price-catalog ./teacher-price-catalog.json

Human-run create requires reviewed access and a resource plan, then hidden RDP password input:
./jdu-web-lab create --plan PRIVATE-PLAN.json --state PRIVATE-STATE.json --confirmed-access
For another account's private S3, the teacher supplies a short-lived URL directly into an individual 0600 CloudShell file; use --bootstrap-url-file FILE.
Teacher admin credentials are never given to students.

Use the same --state thereafter. status/diagnose use AWS reads and bounded public guest checks through existing SSM.
status --output NEW-PUBLIC-REPORT.json
lock-prepare, lock-review, lock-apply; status
ssm --role bastion|web|dns|db|repo (interactive ssm-user; signed template must enable that role; no PEM)
ssh-plan, ssh-apply (human-run), wait at least 62 seconds, ssh-verify
register-plan, register-apply (human-run), register-verify: each requires --student-config OWN-LAB-CREDENTIAL.json
install-commands --student-config OWN-LAB-CREDENTIAL.json [--bin-directory PERSONAL-NEW-BIN]
preflight [--gui-confirmed after checking RDP desktop and Firefox yourself]

New create never overwrites existing state and is blocked above the conservative nine-instance pilot budget.
A failed or unknown create retains state: inspect status; never launch duplicate stacks.
Closure changes only the bootstrap SG and S3 policy; all other parameters remain previous values.
Private SSM endpoints stay available after S3 closure; internal SSH remains a separate exercise path.
P1/M1 are a WEB-02 candidate pair, with no course points.
