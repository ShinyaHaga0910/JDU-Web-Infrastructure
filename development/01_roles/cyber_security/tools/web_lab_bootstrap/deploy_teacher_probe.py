"""Create only the reviewed teacher five-node package probe after user input.

The operator enters a new RDP password twice in the terminal. Plaintext is never
saved; the resulting hash and temporary S3 URL are not logged or put in state.
"""
import argparse
from datetime import datetime,timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import boto3
from botocore.exceptions import ClientError
from prepare_teacher_probe import STACK,API,EIP,tls_control


def private_save(path,data):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as stream:
        json.dump(data,stream,indent=2);stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('plan','candidate','template','state'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--confirmed-public-access',action='store_true',required=True)
    args=parser.parse_args();os.umask(0o077)
    if not sys.stdin.isatty():raise ValueError('Use an interactive terminal for the RDP password')
    state_path=Path(args.state)
    if state_path.exists():raise ValueError('Existing probe state retained; inspect instead of creating again')
    plan=json.loads(Path(args.plan).read_text());candidate=json.loads(Path(args.candidate).read_text())
    template=Path(args.template).read_bytes()
    if (plan['stack_name']!=STACK or plan['region']!='us-east-1' or plan['scope']!='teacher_package_probe_only'
            or hashlib.sha256(template).hexdigest()!=plan['template_sha256']
            or len(template)!=plan['template_bytes']):raise ValueError('Reviewed plan/template differ')
    if (candidate['scope']!='signed_candidate_reassembled_not_os_acceptance' or candidate['student_release_ready'] is not False
            or candidate['key']!='teacher-candidates/web-2026-10-r1/c2/repo-bundle.tar.gz'
            or candidate['bucket']!='jdu-web-capture-20261015-bf04d16eb603'):raise ValueError('Expected exact teacher c2 candidate')
    account=boto3.client('sts').get_caller_identity()['Account']
    if plan['account']!=account:raise ValueError('Wrong AWS environment')
    cfn=boto3.client('cloudformation',region_name='us-east-1');ec2=boto3.client('ec2',region_name='us-east-1');s3=boto3.client('s3',region_name='us-east-1')
    try:cfn.describe_stacks(StackName=STACK)
    except ClientError as exc:
        if exc.response['Error']['Code']!='ValidationError' or exc.response['Error']['Message']!=f'Stack with id {STACK} does not exist':raise
    else:raise ValueError('Existing five-node probe retained')
    key=ec2.describe_key_pairs(KeyNames=[plan['key_name']],IncludePublicKey=True)['KeyPairs'][0]
    if ' '.join(key['PublicKey'].split()[:2])!=plan['student_public_key']:raise ValueError('EC2 public key changed')
    cfn.validate_template(TemplateBody=template.decode())
    head=s3.head_object(Bucket=candidate['bucket'],Key=candidate['key'])
    if head['ContentLength']!=candidate['bundle_size_bytes'] or head['Metadata'].get('sha256')!=candidate['bundle_sha256']:
        raise ValueError('Immutable candidate metadata differ')
    print('REVIEWED: five isolated teacher probe nodes, 96 GiB encrypted EBS.',flush=True)
    print('PUBLIC: Web TCP 80; RDP TCP 3389 from the reviewed 50 ISP CIDRs only.',flush=True)
    print('SSH: bastion to private role addresses only. Existing Linux stacks untouched.',flush=True)
    print('This package probe is not a student release or CLASS_READY.',flush=True)
    print('Enter a new probe RDP password below. Input is hidden; do not send it in chat.',flush=True)
    password=getpass.getpass('RDP password (12-128 characters): ')
    again=getpass.getpass('Confirm RDP password: ')
    if password!=again or not 12<=len(password)<=128 or any(c in password for c in '\r\n\x00'):
        raise ValueError('Password confirmation/length differs; no resources created')
    result=subprocess.run(['openssl','passwd','-6','-stdin'],input=(password+'\n').encode(),capture_output=True,check=True)
    del password,again
    password_hash=result.stdout.decode().strip();del result
    # Verify the exact live controls again immediately before the new deployment.
    tls_control(plan['s3_probe_ipv4'],'s3.us-east-1.amazonaws.com','/')
    tls_control(plan['direct_api_probe_ipv4'],API,'/healthz',True);tls_control(EIP,API,'/healthz',True)
    url=s3.generate_presigned_url('get_object',Params={'Bucket':candidate['bucket'],'Key':candidate['key']},ExpiresIn=7200)
    values={'AvailabilityZone':plan['availability_zone'],'StudentKeyName':plan['key_name'],'StudentPublicKey':plan['student_public_key'],
        'RdpPasswordHash':password_hash,'LabId':plan['lab_id'],'DeploymentId':plan['deployment_id'],
        'ReleaseId':'web-2026-10-r1','DeploymentPhase':'bootstrap','ExpectedPayloadScope':'package_only_candidate',
        'S3PrefixListId':plan['s3_prefix_list'],'BootstrapBucket':candidate['bucket'],'BootstrapPrefix':candidate['key'].rsplit('/',1)[0]+'/',
        'BundleUrl':url,'BundleSha256':candidate['bundle_sha256'],'GradingApiUrl':'https://'+API,'GradingIpv4':EIP,
        'S3ProbeIpv4':plan['s3_probe_ipv4'],'DirectApiProbeIpv4':plan['direct_api_probe_ipv4'],
        'BastionInstanceType':'t3a.medium','SmallInstanceType':'t3a.small','DnsInstanceType':'t3a.micro'}
    state={'schema_version':1,'scope':'teacher_package_probe_only','account':account,'region':'us-east-1','stack_name':STACK,
        'deployment_id':plan['deployment_id'],'lab_id':plan['lab_id'],'template_sha256':plan['template_sha256'],
        'bundle_sha256':candidate['bundle_sha256'],'phase':'CREATE_REQUEST_PENDING','requested_at':datetime.now(timezone.utc).isoformat(),
        'private_key_possession_verified':False,'student_release_ready':False,'class_ready':False}
    private_save(state_path,state)
    response=cfn.create_stack(StackName=STACK,TemplateBody=template.decode(),
        Parameters=[{'ParameterKey':k,'ParameterValue':v} for k,v in values.items()],DisableRollback=True)
    del values,url,password_hash
    state.update(stack_id=response['StackId'],phase='CREATE_IN_PROGRESS')
    pending=state_path.with_suffix('.pending');private_save(pending,state);os.replace(pending,state_path)
    print('FIVE_NODE_CREATE_ACCEPTED='+json.dumps({'stack_name':STACK,'scope':state['scope'],'phase':state['phase'],'class_ready':False}),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('FIVE_NODE_CREATE_FAILED='+type(exc).__name__,flush=True)
        if isinstance(exc,ClientError):print('AWS_ERROR_CODE='+exc.response['Error']['Code'],flush=True)
        elif isinstance(exc,ValueError):print('PUBLIC_REASON='+str(exc),flush=True)
        raise SystemExit(2)
