"""Teacher pilot only: one human-run SSH/individual grading setup for signed v5.

Review is read-only. Apply creates credentials and MUST be executed by the human
in CloudShell. Teacher admin credentials never enter student nodes or SSM logs.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time

DEPLOYMENT='fc335855-7034-427c-8494-6d7a0491ddf1'
MANIFEST='660a2a14031097079621fe3675a0666e68a0a5aec09aa248e95d761ba40b9c4e'
FINGERPRINT='65EC6784750CCFA703BA7179519284E45155EC2A'
OLD_IDS={'i-0561e59b67914f372','i-02e6b0b8e67647a26','i-035dfbeb43f5118da','i-0b0e29eb789a3b1a8','i-06b2bb81ce309a610','i-0040d8f349c83f2dd'}
NEW_NODES={'bastion':('i-049b9086584a4e6df','vol-049a034a1cf207d09'),
    'web':('i-08012a39f3101c7db','vol-0e5036e079ff31201'),
    'dns':('i-06eb7eea745fa53d3','vol-05cce5e0e1c6dbc6c'),
    'db':('i-01ef765664432f107','vol-064682fc1cdd0a66b'),
    'repo':('i-004fb2b85da079a6a','vol-075858fb44913965f')}


def require_context(state,manifest,teacher,nodes):
    if (state['lab_id']!='teacher-c4-probe' or state['deployment_id']!=DEPLOYMENT or state['manifest_sha256']!=MANIFEST
            or state['release_id']!=manifest['release_id'] or teacher['release_id']!=manifest['release_id']
            or teacher['api_base_url']!='https://'+manifest['grading']['fqdn']
            or teacher['fixed_ingress_ipv4']!=manifest['grading']['ipv4'] or not isinstance(teacher.get('admin_key'),str)
            or not teacher['admin_key'] or set(nodes)!={'bastion','web','dns','db','repo'}):
        raise ValueError('Only the reviewed new candidate and existing teacher are allowed')
    ids={n['instance_id'] for n in nodes.values()}
    if len(ids)!=5 or ids&OLD_IDS or any(len(n['root_volumes'])!=1 for n in nodes.values()):
        raise ValueError('Five distinct new nodes with original single roots required')
    if any((nodes[r]['instance_id'],nodes[r]['root_volumes'][0])!=v for r,v in NEW_NODES.items()):
        raise ValueError('Exactly the reviewed five IDs and original roots required')


def require_preflight(output):
    result=json.loads(output.strip().splitlines()[-1])
    if (result.get('stage')!='PREFLIGHT_OBSERVED' or result.get('current_foundation_passed') is not True
            or not re.search(r'^SUBMISSION STORED request_id=[0-9a-f-]{36}$',output,re.M)):
        raise ValueError('Fresh foundation PASS and stored submission required; retain existing credentials')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=('review','apply'));a=p.parse_args()
    os.umask(0o077);sys.dont_write_bytecode=True;home=Path.home();tools=home/'jdu-web-student-tools-c5-v5'
    sys.path.insert(0,str(tools))
    from release_validation import verify_release
    from controller_runtime import install_controller
    verified=verify_release(tools/'deployment-manifest.json',str(tools/'deployment-manifest.json')+'.asc',
        tools/'package-signing-public.asc',FINGERPRINT,tools,include_bundle=False)
    if verified['manifest_sha256']!=MANIFEST:raise ValueError('Reviewed signed manifest required')
    data=verified['files']['controller_bundle'].read_bytes()
    installed=install_controller(data,home/'.local/share/jdu-web/controllers'/hashlib.sha256(data).hexdigest());sys.path.insert(0,str(installed))
    import student_controller as controller
    import web_progress
    import boto3
    from setup_internal_ssh import current_nodes
    path=home/'jdu-web-capture-20261015/student-c5-v5.private.json';state=controller.private(path);controller.identity(verified,state)
    nodes=current_nodes(boto3.client('ec2',region_name='us-east-1'),boto3.client('cloudformation',region_name='us-east-1'),
        state,controller.private(str(path)+'.baseline.json'))
    teacher_path=home/'.jdu-web-teacher/teacher.credentials.json';teacher=controller.private(teacher_path)
    require_context(state,verified['manifest'],teacher,nodes);del teacher
    credential=home/'.jdu-web-teacher/private/teacher-c4-probe.credentials.json'
    if credential.exists():controller.student_credential(verified,state,credential)
    ssh_plan=controller.private(str(path)+'.ssh.json')
    if ssh_plan['deployment_id']!=DEPLOYMENT:raise ValueError('Reviewed internal SSH plan required')
    review=dict(lab_id=state['lab_id'],deployment_id=DEPLOYMENT,instance_count=5,private_key_location='own bastion only',
        teacher_admin_copied=False,student_credential_destination='own CloudShell and own bastion root only',class_ready=False)
    print('NEW_CANDIDATE_ENROLLMENT_REVIEW='+json.dumps(review),flush=True)
    if a.operation=='review':return
    def run(operation,*extra):
        command=['bash',str(tools/'jdu-web-lab'),operation,'--state',str(path),*map(str,extra)]
        if operation=='preflight':
            observed=subprocess.run(command,check=True,capture_output=True,text=True)
            print(observed.stdout,end='',flush=True);require_preflight(observed.stdout)
        else:subprocess.run(command,check=True)
    enrolled=Path(str(path)+'.ssh.json.enrolled.public.json');ssh_verified=Path(str(path)+'.ssh.json.verified.public.json')
    if not enrolled.exists():run('ssh-apply')
    enrollment=controller.private(enrolled)
    if enrollment['deployment_id']!=DEPLOYMENT or enrollment['private_key_exported'] is not False:raise ValueError('Wrong SSH enrollment')
    if not ssh_verified.exists():
        seconds=max(0,63-(time.time()-enrollment['last_ephemeral_key_at']))
        if seconds:print('WAITING_FOR_EPHEMERAL_PUBLIC_KEY_EXPIRY',flush=True);time.sleep(seconds)
        run('ssh-verify')
    # Credential creation occurs only in the human-run apply, never in review.
    web_progress.issue(web_progress.private_json(teacher_path),state['lab_id'],credential)
    registration=Path(str(path)+'.registration.json');accepted=Path(str(registration)+'.accepted.json')
    if not registration.exists():run('register-plan','--student-config',credential)
    if not accepted.exists():run('register-apply','--student-config',credential)
    run('register-verify','--student-config',credential)
    state=controller.private(path)
    if not state.get('command_config'):
        run('install-commands','--student-config',credential,'--bin-directory',home/'.local/share/jdu-web/c5-v5-bin')
    elif state['command_config']!=str(home/'.jdu-web-student/teacher-c4-probe/command-state.json'):
        raise ValueError('Existing command config retained for inspection')
    run('preflight')
    receipt=dict(review,checked_at=datetime.now(timezone.utc).isoformat(),persistent_internal_ssh_verified=True,
        own_lab_registration_verified=True,credentials_exported_to_windows=False,foundation_checked_and_submitted=True)
    result=home/'jdu-web-capture-20261015/student-c5-v5-enrollment.public.json'
    if result.exists():raise ValueError('Existing completed acceptance retained')
    controller.save_new(result,receipt)
    print('NEW_CANDIDATE_ENROLLMENT_COMPLETE',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as e:
        print('CANDIDATE_ENROLLMENT_STOPPED='+type(e).__name__+'; preserve all state and credentials',flush=True)
        raise SystemExit(2)
