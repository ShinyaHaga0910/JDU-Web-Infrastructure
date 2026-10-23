"""Teacher-only actual c5 deployment acceptance, with reversible WEB-02 fixtures.

No credential issuance or key changes. All reports remain separate from the old
deployment. Restore the repository service and the fixture package state on exit.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

DEPLOYMENT='fc335855-7034-427c-8494-6d7a0491ddf1'
MANIFEST='660a2a14031097079621fe3675a0666e68a0a5aec09aa248e95d761ba40b9c4e'
FINGERPRINT='65EC6784750CCFA703BA7179519284E45155EC2A'


def main():
    import boto3
    from boto3.dynamodb.types import TypeDeserializer
    sys.dont_write_bytecode=True
    home=Path.home();root=Path(__file__).resolve().parent
    config_path=home/'.jdu-web-student/teacher-c4-probe/command-state.json'
    config=json.loads(config_path.read_text());state=json.loads(Path(config['state']).read_text())
    if state['deployment_id']!=DEPLOYMENT or state['manifest_sha256']!=MANIFEST:
        raise ValueError('Only the reviewed c5 deployment is allowed')
    tools=home/'jdu-web-student-tools-c5-v5';sys.path.insert(0,str(tools))
    from release_validation import verify_release
    from controller_runtime import install_controller
    verified=verify_release(tools/'deployment-manifest.json',str(tools/'deployment-manifest.json')+'.asc',
        tools/'package-signing-public.asc',FINGERPRINT,tools,include_bundle=False)
    if verified['manifest_sha256']!=MANIFEST:raise ValueError('Wrong signed release')
    data=verified['files']['controller_bundle'].read_bytes()
    installed=install_controller(data,home/'.local/share/jdu-web/controllers'/hashlib.sha256(data).hexdigest())
    if Path(config['bootstrap_tools']).resolve()!=installed.resolve():raise ValueError('Wrong checker installation')
    sys.path.insert(0,str(installed))
    from setup_internal_ssh import current_nodes, remote, save_new
    from apply_candidate_registration import require_context
    import student_controller as controller
    nodes=current_nodes(boto3.client('ec2',region_name='us-east-1'),boto3.client('cloudformation',region_name='us-east-1'),
        state,json.loads(Path(config['baseline_plan']).read_text()))
    require_context(state,verified['manifest'],controller.private(home/'.jdu-web-teacher/teacher.credentials.json'),nodes)
    checker=home/'.local/share/jdu-web/c5-v5-bin/jdu-web-check'
    cfn=boto3.client('cloudformation',region_name='us-east-1')
    outputs={x['OutputKey']:x['OutputValue'] for x in cfn.describe_stacks(StackName='jdu-web-progress-2026')['Stacks'][0]['Outputs']}
    db=boto3.client('dynamodb',region_name='us-east-1');deserialize=TypeDeserializer()
    def stored(sk):
        row=db.get_item(TableName=outputs['TableName'],Key={'pk':{'S':'LAB#'+state['lab_id']},'sk':{'S':sk}},ConsistentRead=True)['Item']
        return {k:deserialize.deserialize(v) for k,v in row.items()}
    pending=Path(config['pending_directory'])
    def verify_foundation(rid,latest=False):
        report=json.loads((pending/(rid+'.report.json')).read_text());receipt=json.loads((pending/(rid+'.receipt.json')).read_text())
        if any(report[k]!=state[k] for k in ('lab_id','release_id','deployment_id')):raise ValueError('Wrong report identity')
        if len(report['checks'])!=47 or any(c['status']!='PASS' for c in report['checks']):raise ValueError('Fresh foundation incomplete')
        saved=stored('REQUEST#'+rid);body=json.dumps(report,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        if (saved['report']!=report or saved['receipt']!=receipt['receipt']
                or saved['body_sha256']!=hashlib.sha256(body).hexdigest() or not receipt['exact_retry_same_receipt']):
            raise ValueError('Teacher foundation storage differs')
        if latest and stored('LATEST#BOOTSTRAP')['request_id']!=rid:raise ValueError('Teacher foundation latest differs')
        return dict(request_id=rid,passed=47,total=47,teacher_exact_body_and_receipt=True,
            exact_retry_same_receipt=True,latest_verified=latest,body_sha256=hashlib.sha256(body).hexdigest())
    gui_log=(home/'jdu-web-capture-20261015/persistent-ssm-20261020/preflight-gui-confirmed.log').read_text()
    gui_result=json.loads(gui_log.strip().splitlines()[-1])
    if not gui_result['current_foundation_passed'] or not gui_result['gui_confirmed']:raise ValueError('GUI-bound preflight incomplete')
    rid=re.findall(r'^SUBMISSION STORED request_id=([0-9a-f-]{36})$',gui_log,re.M)[-1]
    retry=subprocess.run([str(checker),'bootstrap','--retry',rid],capture_output=True,text=True,timeout=120)
    if retry.returncode or 'SUBMISSION STORED request_id='+rid not in retry.stdout:raise ValueError('Foundation retry failed')
    foundation=dict(deployment_id=DEPLOYMENT,checked_at=datetime.now(timezone.utc).isoformat(),gui_confirmed=True,
        results=[verify_foundation('43169ba1-086b-4337-997d-bdd4899ee5e1'),verify_foundation(rid,True)],class_ready=False)
    save_new(root/'foundation-storage.public.json',foundation)
    print('FOUNDATION_STORED_AND_GUI_CONFIRMED=47/47',flush=True)
    common=['--command-state',str(config_path),'--expected-deployment',DEPLOYMENT]
    stages=[];fixture_installed=False;repo_stopped=False
    def fixture(operation):
        job=root/('fixture-'+operation+'.job.json')
        subprocess.run(['python3',str(root/'run_web_fixture.py'),operation,'--job',str(job),*common],check=True,timeout=60)
        for _ in range(100):
            r=subprocess.run(['python3',str(root/'run_web_fixture.py'),'poll','--job',str(job),*common],capture_output=True,text=True,timeout=60)
            if r.returncode:raise ValueError('Fixture '+operation+' failed: '+r.stdout[-500:])
            if 'FIXTURE_JOB=Success' in r.stdout:
                print('FIXTURE_COMPLETE='+operation,flush=True);return
            time.sleep(5)
        raise ValueError('Fixture '+operation+' still pending; retain job')
    def assess(stage):
        out=root/('web02-'+stage+'.public.json')
        subprocess.run(['python3',str(root/'acceptance_web02_stage.py'),stage,*common,
            '--checker-command',str(checker),'--output',str(out)],check=True,timeout=290)
        j=json.loads(out.read_text());stages.append(j)
    ssm=boto3.client('ssm',region_name='us-east-1')
    def repo_service(operation):
        source=("import json,subprocess\nfrom pathlib import Path\n"
            "c=json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())\n"
            "assert c['deployment_id']=="+repr(DEPLOYMENT)+" and c['instance_id']=="+repr(nodes['repo']['instance_id'])+" and c['role']=='repo'\n"
            "subprocess.run(['systemctl',"+repr(operation)+",'nginx'],check=True)\n"
            "active=subprocess.run(['systemctl','is-active','--quiet','nginx']).returncode==0\n"
            "assert active is "+str(operation=='start')+"\nprint(json.dumps({'operation':"+repr(operation)+",'expected_state_verified':True}))\n")
        result=remote(ssm,nodes['repo']['instance_id'],source.encode(),{})
        if result['expected_state_verified'] is not True:raise ValueError('Repository state differs')
    try:
        assess('initial');fixture('install');fixture_installed=True
        fixture('practice');assess('practice')
        fixture('wrong');assess('wrong')
        fixture('mission');assess('mission')
        fixture('loopback');assess('loopback')
        fixture('normal');assess('normal')
        repo_stopped=True
        try:repo_service('stop');assess('repo_unavailable')
        finally:repo_service('start');repo_stopped=False
        assess('signed_command')
    finally:
        if repo_stopped:repo_service('start')
        if fixture_installed:fixture('restore')
    assess('restored')
    result=dict(deployment_id=DEPLOYMENT,checked_at=datetime.now(timezone.utc).isoformat(),
        scope='new_five_node_signed_checker_integration',stage_count=len(stages),
        assessment_count=sum(len(s['results']) for s in stages),all_fixture_expectations_passed=True,
        repository_service_restored=True,fixture_package_inventory_restored=True,stages=stages,class_ready=False)
    save_new(root/'web02-integration.public.json',result)
    print('C5_WEB02_ALL_STAGES_ACCEPTED=9 stages / 13 assessments',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as e:
        print('C5_ACCEPTANCE_STOPPED='+type(e).__name__+': '+str(e),flush=True)
        raise SystemExit(2)
