"""CloudShell teacher fixture scheduler; public requests and bounded polling."""
import argparse
import base64
import json
from pathlib import Path
import shlex
import sys
import uuid


def main():
    import boto3
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=('install','practice','mission','wrong','loopback','normal','restore','poll'))
    p.add_argument('--job',required=True)
    p.add_argument('--command-state',required=True)
    p.add_argument('--expected-deployment',required=True)
    a=p.parse_args();sys.dont_write_bytecode=True;c=json.loads(Path(a.command_state).read_text())
    sys.path.insert(0,c['bootstrap_tools'])
    from setup_internal_ssh import current_nodes,save_new
    state=json.loads(Path(c['state']).read_text());baseline=json.loads(Path(c['baseline_plan']).read_text())
    if state['deployment_id']!=a.expected_deployment or baseline['deployment_id']!=a.expected_deployment:
        raise ValueError('Explicitly selected deployment differs; no fixture scheduled')
    if boto3.client('sts').get_caller_identity()['Account']!=state['account']:raise ValueError('Wrong account')
    nodes=current_nodes(boto3.client('ec2',region_name='us-east-1'),boto3.client('cloudformation',region_name='us-east-1'),state,baseline)
    ssm=boto3.client('ssm',region_name='us-east-1');job=Path(a.job)
    if a.operation=='poll':
        info=json.loads(job.read_text())
        if info['deployment_id']!=state['deployment_id']:raise ValueError('Wrong job deployment')
        result=ssm.get_command_invocation(CommandId=info['command_id'],InstanceId=nodes['bastion']['instance_id'])
        print('FIXTURE_JOB='+result['Status'])
        if result['Status']=='Success':
            public=json.loads(result['StandardOutputContent'])
            output=Path(str(job)+'.public.json')
            if not output.exists():save_new(output,public)
            print(json.dumps(public,separators=(',',':')))
        elif result['Status'] in ('Failed','TimedOut','Cancelled'):
            print(result['StandardOutputContent'][-1000:]);raise SystemExit(2)
        return
    source=Path(__file__).with_name('http_fixture_guest.py').read_bytes()
    request=dict(lab_id=state['lab_id'],deployment_id=state['deployment_id'],instance_id=nodes['web']['instance_id'],operation=a.operation)
    wrapped="import base64,json,subprocess,shlex\nfrom pathlib import Path\nb=json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())\nassert b['instance_id']=='"+nodes['bastion']['instance_id']+"' and b['deployment_id']=='"+state['deployment_id']+"'\ncode=\"import base64;exec(base64.b64decode('"+base64.b64encode(source).decode()+"'))\"\nr=subprocess.run(['sudo','-n','-u','labuser','ssh','-F','/home/labuser/.ssh/jdu-web-internal/config','web','sudo -n python3 -c '+shlex.quote(code)],input="+repr(json.dumps(request))+",text=True,capture_output=True,timeout=700)\nprint(r.stdout.strip())\nraise SystemExit(r.returncode)"
    cmd='python3 -c '+shlex.quote('import base64;exec(base64.b64decode('+repr(base64.b64encode(wrapped.encode()).decode())+'))')
    if job.exists():raise ValueError('Existing job retained')
    answer=ssm.send_command(InstanceIds=[nodes['bastion']['instance_id']],DocumentName='AWS-RunShellScript',
        Parameters={'commands':[cmd],'executionTimeout':['900']},TimeoutSeconds=30)
    save_new(job,dict(deployment_id=state['deployment_id'],operation=a.operation,command_id=answer['Command']['CommandId']))
    print('FIXTURE_JOB_SCHEDULED='+a.operation)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('WEB_FIXTURE_SCHEDULER_STOPPED='+type(exc).__name__);raise SystemExit(2)
