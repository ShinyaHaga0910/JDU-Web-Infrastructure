"""CloudShell-only, read-only comparison with the deployed RDP password hash.

Never changes a password, prints a hash, or stores the entered password.
This verifies the deployment input, not the guest shadow file or PAM status.
"""
import argparse
import base64
import getpass
import hmac
import json
from pathlib import Path
import re
import subprocess
import sys


def matches(password,password_hash):
    parts=password_hash.split('$')
    if not re.fullmatch(r'\$6\$[A-Za-z0-9./]{1,16}\$[A-Za-z0-9./]{86}',password_hash):
        raise ValueError('Unexpected password hash format')
    if any(c in password for c in '\r\n\x00'):
        return False
    result=subprocess.run(['openssl','passwd','-6','-salt',parts[2],'-stdin'],
        input=(password+'\n').encode(),capture_output=True,check=True)
    return hmac.compare_digest(result.stdout.decode().strip(),password_hash)


def main():
    import boto3
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',required=True)
    args=parser.parse_args()
    if not sys.stdin.isatty():raise ValueError('Use the interactive CloudShell terminal')
    state=json.loads(Path(args.state).read_text())
    if state['stack_name']!='jdu-web-five-node-probe-20261015':raise ValueError('Wrong probe state')
    if state['account']!=boto3.client('sts').get_caller_identity()['Account']:raise ValueError('Wrong AWS environment')
    cfn=boto3.client('cloudformation',region_name='us-east-1')
    ec2=boto3.client('ec2',region_name='us-east-1')
    refs={r['LogicalResourceId']:r.get('PhysicalResourceId') for r in cfn.list_stack_resources(StackName=state['stack_id'])['StackResourceSummaries']}
    instance=refs['BastionInstance']
    node=ec2.describe_instances(InstanceIds=[instance])['Reservations'][0]['Instances'][0]
    if instance!='i-0561e59b67914f372' or node['PrivateIpAddress']!='10.20.1.10' or node['State']['Name']!='running':
        raise ValueError('Wrong running bastion')
    raw=base64.b64decode(ec2.describe_instance_attribute(InstanceId=instance,Attribute='userData')['UserData']['Value']).decode()
    if not raw.startswith('#cloud-config\n'):raise ValueError('Unexpected user data format')
    cloud=json.loads(raw.split('\n',1)[1])
    file=next(x for x in cloud['write_files'] if x['path']=='/var/lib/jdu-web/initial/private.json')
    cfg=json.loads(file['content'])
    if cfg['role']!='bastion' or cfg['deployment_id']!=state['deployment_id'] or cfg['lab_id']!=state['lab_id']:
        raise ValueError('Deployment identity differs')
    print('READ_ONLY_CHECK: deployed input only; no password change or saved value.',flush=True)
    password=getpass.getpass('Existing RDP password (hidden): ')
    result=matches(password,cfg['rdp_hash'])
    del password,raw,cloud,file,cfg
    print('RDP_PASSWORD_MATCHES_BOOTSTRAP='+str(result),flush=True)
    print('This result does not yet verify the guest account or PAM.',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('RDP_PASSWORD_CHECK_FAILED='+type(exc).__name__,flush=True)
        if hasattr(exc,'response'):print('AWS_ERROR_CODE='+exc.response['Error']['Code'],flush=True)
        raise SystemExit(2)
