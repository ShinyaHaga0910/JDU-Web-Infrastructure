"""Schedule the signed-app/offline-wheel test on the existing Web through SSM.

Only public artifacts enter SSM history. No app/DB credentials are generated.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shlex
import sys


def main():
    import boto3
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=('start','poll'))
    for n in ('job','payload-root','app-signature','command-state','expected-deployment'):p.add_argument('--'+n,required=True)
    a=p.parse_args();sys.dont_write_bytecode=True;config_path=Path(a.command_state)
    config=json.loads(config_path.read_text())
    sys.path.insert(0,config['bootstrap_tools'])
    from setup_internal_ssh import current_nodes,save_new
    state=json.loads(Path(config['state']).read_text());baseline=json.loads(Path(config['baseline_plan']).read_text())
    if state['deployment_id']!=a.expected_deployment or baseline['deployment_id']!=a.expected_deployment:
        raise ValueError('Explicitly selected deployment differs; no runtime job scheduled')
    if boto3.client('sts').get_caller_identity()['Account']!=state['account']:raise ValueError('Wrong account')
    nodes=current_nodes(boto3.client('ec2',region_name='us-east-1'),boto3.client('cloudformation',region_name='us-east-1'),state,baseline)
    ssm=boto3.client('ssm',region_name='us-east-1');job=Path(a.job)
    if a.operation=='poll':
        j=json.loads(job.read_text())
        if j['deployment_id']!=state['deployment_id']:raise ValueError('Wrong job deployment')
        v=ssm.get_command_invocation(CommandId=j['command_id'],InstanceId=nodes['bastion']['instance_id'])
        print('CATALOG_RUNTIME_JOB='+v['Status'])
        if v['Status']=='Success':
            result=json.loads(v['StandardOutputContent']);out=Path(str(job)+'.public.json')
            if not out.exists():save_new(out,result)
            print(json.dumps(result,separators=(',',':')))
        elif v['Status'] in ('Failed','TimedOut','Cancelled'):
            print(v['StandardOutputContent'][-1000:]);raise SystemExit(2)
        return
    if job.exists():raise ValueError('Existing runtime job retained; poll it')
    root=Path(a.payload_root)
    from payload_runtime import verify_tree
    verify_tree(root,root/'artifacts/bootstrap/archive-key.asc','65EC6784750CCFA703BA7179519284E45155EC2A','web-2026-10-r1')
    archive=(root/'artifacts/app/jdu-catalog.tar.gz').read_bytes();source=Path(__file__).with_name('verify_catalog_runtime_guest.py').read_bytes()
    request=dict(lab_id=state['lab_id'],deployment_id=state['deployment_id'],instance_id=nodes['web']['instance_id'],
        library_sha256={n:hashlib.sha256((root/'artifacts/bootstrap'/n).read_bytes()).hexdigest() for n in ('payload_runtime.py','release_validation.py')},
        archive_b64=base64.b64encode(archive).decode(),archive_sha256=hashlib.sha256(archive).hexdigest(),
        signature_b64=base64.b64encode(Path(a.app_signature).read_bytes()).decode())
    wrapped="import base64,json,subprocess,shlex\nfrom pathlib import Path\nb=json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())\nassert b['instance_id']=='"+nodes['bastion']['instance_id']+"' and b['deployment_id']=='"+state['deployment_id']+"'\ncode=\"import base64;exec(base64.b64decode('"+base64.b64encode(source).decode()+"'))\"\nr=subprocess.run(['sudo','-n','-u','labuser','ssh','-F','/home/labuser/.ssh/jdu-web-internal/config','web','sudo -n python3 -c '+shlex.quote(code)],input="+repr(json.dumps(request))+",text=True,capture_output=True,timeout=850)\nprint(r.stdout.strip())\nraise SystemExit(r.returncode)"
    cmd='python3 -c '+shlex.quote('import base64;exec(base64.b64decode('+repr(base64.b64encode(wrapped.encode()).decode())+'))')
    if len(cmd)>64000:raise ValueError('Public runtime command exceeds reviewed bound')
    response=ssm.send_command(InstanceIds=[nodes['bastion']['instance_id']],DocumentName='AWS-RunShellScript',
        Parameters={'commands':[cmd],'executionTimeout':['900']},TimeoutSeconds=30)
    save_new(job,dict(deployment_id=state['deployment_id'],command_id=response['Command']['CommandId']))
    print('CATALOG_RUNTIME_JOB_SCHEDULED; public artifacts only; no classroom credentials/service')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('CATALOG_RUNTIME_CONTROLLER_STOPPED='+type(exc).__name__);raise SystemExit(2)
