"""Teacher-only metadata migration for the c5-v5 checker bytecode fix.

No AWS mutation, credential issuance or key rotation. Both signed releases and
the exact two source changes are verified. Old state, launchers and reports stay.
"""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

OLD='660a2a14031097079621fe3675a0666e68a0a5aec09aa248e95d761ba40b9c4e'
NEW='d9d61ffcebb9d2e8c9fe874563a6f292b902d15e70dad86e604c006d0fc545f5'
DEPLOYMENT='fc335855-7034-427c-8494-6d7a0491ddf1'
FP='65EC6784750CCFA703BA7179519284E45155EC2A'


def permitted_change(old,new,old_files,new_files):
    a=copy.deepcopy(old);b=copy.deepcopy(new)
    for m in (a,b):
        for n in ('created_at','expires_at'):m.pop(n)
        m['artifacts'].pop('controller_bundle')
    if a!=b or set(old_files)!=set(new_files):raise ValueError('Signed infrastructure or inventory changed')
    changed={n for n in old_files if old_files[n]!=new_files[n]}
    if changed!={'student_controller.py','check_dispatch.py','CONTROLLER-MANIFEST.json'}:
        raise ValueError('Only reviewed bytecode fixes permitted')
    if old_files['student_controller.py'].replace(b'exec python3 ',b'exec python3 -B ')!=new_files['student_controller.py']:
        raise ValueError('Controller change exceeds Python bytecode flags')
    if old_files['check_dispatch.py'].replace(b'import sys\n',b'import sys\nsys.dont_write_bytecode = True\n',1)!=new_files['check_dispatch.py']:
        raise ValueError('Checker change exceeds bytecode suppression')


def verify(root):
    spec=importlib.util.spec_from_file_location('cache_migration_validator_'+root.name,root/'release_validation.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.verify_release(root/'deployment-manifest.json',str(root/'deployment-manifest.json')+'.asc',
        root/'package-signing-public.asc',FP,root,include_bundle=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=('review','apply'));a=p.parse_args()
    sys.dont_write_bytecode=True;os.umask(0o077);home=Path.home();work=home/'jdu-web-capture-20261015/c5-acceptance-20261020'
    old=verify(home/'jdu-web-student-tools-c5-v5');new=verify(home/'jdu-web-student-tools-c5-v6')
    if (old['manifest_sha256'],new['manifest_sha256'])!=(OLD,NEW):raise ValueError('Reviewed signatures required')
    sys.path.insert(0,str(home/'jdu-web-student-tools-c5-v6'))
    from controller_runtime import controller_files,install_controller
    old_data=old['files']['controller_bundle'].read_bytes();data=new['files']['controller_bundle'].read_bytes()
    permitted_change(old['manifest'],new['manifest'],controller_files(old_data),controller_files(data))
    old_installed=install_controller(old_data,home/'.local/share/jdu-web/controllers'/hashlib.sha256(old_data).hexdigest())
    installed=install_controller(data,home/'.local/share/jdu-web/controllers'/hashlib.sha256(data).hexdigest())
    sys.path.insert(0,str(installed));sys.path.insert(0,str(work))
    import student_controller as controller
    from setup_internal_ssh import current_nodes
    from apply_candidate_registration import require_context
    import boto3
    path=home/'jdu-web-capture-20261015/student-c5-v5.private.json';state=controller.private(path)
    if state['manifest_sha256']!=OLD or state['deployment_id']!=DEPLOYMENT:raise ValueError('Original state differs')
    if boto3.client('sts').get_caller_identity()['Account']!=state['account']:raise ValueError('Wrong account')
    nodes=current_nodes(boto3.client('ec2',region_name='us-east-1'),boto3.client('cloudformation',region_name='us-east-1'),
        state,controller.private(str(path)+'.baseline.json'))
    require_context(state,old['manifest'],controller.private(home/'.jdu-web-teacher/teacher.credentials.json'),nodes)
    old_config=Path(state['command_config']);config=controller.private(old_config)
    if (Path(config['bootstrap_tools'])!=old_installed or config['state']!=str(path)
            or old_config!=home/'.jdu-web-student/teacher-c4-probe/command-state.json'):
        raise ValueError('Existing command binding differs')
    target=home/'jdu-web-capture-20261015/student-c5-v6.private.json'
    config_path=old_config.with_name('command-state-c5-v6.json');bin_path=home/'.local/share/jdu-web/c5-v6-bin'
    suffixes=('.baseline.json','.ssh.json','.ssh.json.enrolled.public.json','.ssh.json.verified.public.json',
        '.registration.json','.registration.json.accepted.json')
    snapshots={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [path,old_config,*[Path(str(path)+s) for s in suffixes]]}
    launchers={}
    for name in ('jdu-web-check','jdu-web-my-progress','jdu-web-register','jdu-web-progress'):
        before=(home/'.local/share/jdu-web/c5-v5-bin'/name).read_text()
        if str(old_installed) not in before or 'exec python3 ' not in before:raise ValueError('Old launcher differs')
        launchers[name]=before.replace(str(old_installed),str(installed)).replace(str(old_config),str(config_path)).replace('exec python3 ','exec python3 -B ')
    public=dict(deployment_id=DEPLOYMENT,old_manifest_sha256=OLD,new_manifest_sha256=NEW,same_five_nodes_and_roots=True,
        aws_mutations=0,credentials_created=0,private_key_changed=False,old_bindings_preserved=True,class_ready=False)
    print('BYTECODE_FIX_REVIEW='+json.dumps(public),flush=True)
    plan=work/'bytecode-fix-migration.private.json'
    if a.operation=='review':
        controller.save_new(plan,dict(public,snapshots=snapshots));return
    saved=controller.private(plan)
    if saved!=dict(public,snapshots=snapshots):raise ValueError('Reviewed inputs changed')
    for dest in [target,config_path,bin_path,*[Path(str(target)+s) for s in suffixes]]:
        if dest.exists() or dest.is_symlink():raise ValueError('Existing migration output retained')
    c=dict(config,state=str(target),baseline_plan=str(target)+'.baseline.json',bootstrap_tools=str(installed),
        ssh_enrollment=str(target)+'.ssh.json.enrolled.public.json')
    for key,name in [('guest_source','post_restart_guest.py'),('submission_source','bootstrap_submission_guest.py')]:
        c[key]=str(installed/name);c[key+'_sha256']=hashlib.sha256((installed/name).read_bytes()).hexdigest()
    updated=dict(state,manifest_sha256=NEW,command_config=str(config_path),
        tool_migration=dict(kind='bytecode-suppression-only',previous_state=str(path),previous_manifest_sha256=OLD))
    for suffix in suffixes:controller.save_new(str(target)+suffix,controller.private(str(path)+suffix))
    controller.save_new(config_path,c);bin_path.mkdir(mode=0o700)
    for name,body in launchers.items():
        with os.fdopen(os.open(bin_path/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o700),'w') as f:f.write(body)
    controller.save_new(target,updated)
    controller.save_new(work/'bytecode-fix-migration.public.json',dict(public,checked_at=datetime.now(timezone.utc).isoformat(),
        migration_complete=True,run_fresh_acceptance_next=True))
    print('SIGNED_BYTECODE_FIX_BINDING_ADOPTED; run fresh checks',flush=True)


if __name__=='__main__':main()
