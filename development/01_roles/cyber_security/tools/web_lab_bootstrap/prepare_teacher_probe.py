"""Read-only AWS preflight for a named five-node teacher package probe.

Saves a private plan. Does not create resources or generate/set credentials.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
import uuid

import boto3
from botocore.exceptions import ClientError

STACK='jdu-web-five-node-probe-20261015'
API='7eg7nm5oe2.execute-api.us-east-1.amazonaws.com'
EIP='44.216.176.215'


def tls_control(address,host,path,health=False):
    connection=socket.create_connection((address,443),timeout=10)
    with ssl.create_default_context().wrap_socket(connection,server_hostname=host) as stream:
        stream.sendall(('GET '+path+' HTTP/1.1\r\nHost: '+host+'\r\nConnection: close\r\n\r\n').encode())
        response=http.client.HTTPResponse(stream);response.begin();data=response.read(65536)
        if health and (response.status!=200 or json.loads(data).get('service')!='jdu-web-progress'):
            raise ValueError('Teacher health control failed')
        if not health and response.status not in (200,301,302,307,400,403,404):
            raise ValueError('S3 HTTPS control failed')
        return response.status


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();os.umask(0o077)
    output=Path(args.output)
    if output.exists(): raise ValueError('Existing private probe plan retained')
    template=Path(args.template).read_bytes()
    if len(template)>51200: raise ValueError('Template exceeds direct input bound')
    account=boto3.client('sts').get_caller_identity()['Account']
    teacher=json.loads((Path.home()/'.jdu-web-teacher/identity.json').read_text())
    if teacher!={'account':account,'region':'us-east-1','stack_name':'jdu-web-progress-2026'}:
        raise ValueError('Wrong AWS environment')
    cfn=boto3.client('cloudformation',region_name='us-east-1');ec2=boto3.client('ec2',region_name='us-east-1')
    try: cfn.describe_stacks(StackName=STACK)
    except ClientError as exc:
        if exc.response['Error']['Code']!='ValidationError' or exc.response['Error']['Message']!=f'Stack with id {STACK} does not exist': raise
    else: raise ValueError('Existing five-node stack retained')
    cfn.validate_template(TemplateBody=template.decode())
    keys=ec2.describe_key_pairs(IncludePublicKey=True)['KeyPairs']
    if len(keys)!=1: raise ValueError('Select an explicit existing key; expected one teacher probe key')
    key=keys[0];public=' '.join(key['PublicKey'].split()[:2])
    if public.split()[0] not in ('ssh-rsa','ssh-ed25519'): raise ValueError('Unsupported probe public key')
    prefix_lists=ec2.describe_prefix_lists(Filters=[{'Name':'prefix-list-name','Values':['com.amazonaws.us-east-1.s3']}])['PrefixLists']
    if len(prefix_lists)!=1: raise ValueError('Expected regional AWS S3 prefix list')
    prefix=prefix_lists[0];networks=[ipaddress.IPv4Network(v) for v in prefix['Cidrs']]
    def addresses(host): return sorted({v[4][0] for v in socket.getaddrinfo(host,443,family=socket.AF_INET,type=socket.SOCK_STREAM)})
    s3=[v for v in addresses('s3.us-east-1.amazonaws.com') if any(ipaddress.IPv4Address(v) in n for n in networks)]
    api=[v for v in addresses(API) if v!=EIP and not any(ipaddress.IPv4Address(v) in n for n in networks)]
    if not s3 or not api: raise ValueError('Missing disjoint live network control addresses')
    controls={'s3':tls_control(s3[0],'s3.us-east-1.amazonaws.com','/'),
        'direct_api':tls_control(api[0],API,'/healthz',True),'teacher_eip':tls_control(EIP,API,'/healthz',True)}
    offers=ec2.describe_instance_type_offerings(LocationType='availability-zone',Filters=[{'Name':'instance-type','Values':['t3a.micro','t3a.small','t3a.medium']},{'Name':'location','Values':['us-east-1a']}])['InstanceTypeOfferings']
    if {v['InstanceType'] for v in offers}!={'t3a.micro','t3a.small','t3a.medium'}: raise ValueError('Expected three sizes in the same AZ')
    plan={'scope':'teacher_package_probe_only','checked_at':datetime.now(timezone.utc).isoformat(),'account':account,
        'region':'us-east-1','stack_name':STACK,'lab_id':'teacher-five-probe','deployment_id':str(uuid.uuid4()),
        'template_sha256':hashlib.sha256(template).hexdigest(),'template_bytes':len(template),
        'key_name':key['KeyName'],'student_public_key':public,'private_key_possession_verified':False,
        's3_prefix_list':prefix['PrefixListId'],'s3_probe_ipv4':s3[0],'direct_api_probe_ipv4':api[0],
        'availability_zone':'us-east-1a','https_controls':controls,
        'requires_user_rdp_password_entry':True,'requires_public_access_confirmation':True,'student_release_ready':False}
    with output.open('x') as stream: json.dump(plan,stream,indent=2);stream.write('\n')
    print('FIVE_NODE_PREFLIGHT='+json.dumps({k:plan[k] for k in ('scope','checked_at','stack_name','template_sha256','template_bytes','private_key_possession_verified','https_controls','requires_user_rdp_password_entry','requires_public_access_confirmation','student_release_ready')}))


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('FIVE_NODE_PREFLIGHT_FAILED='+type(exc).__name__)
        if isinstance(exc,ClientError): print('AWS_ERROR_CODE='+exc.response['Error']['Code'])
        elif isinstance(exc,ValueError): print('PUBLIC_REASON='+str(exc))
        raise SystemExit(2)
