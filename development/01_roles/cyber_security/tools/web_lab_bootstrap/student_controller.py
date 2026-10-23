"""Signature-bound CloudShell entrypoint for an individual five-node candidate.

Never receives a private SSH key. New RDP/SSH/registration credentials are set
only by explicit human-run commands. Every result remains candidate-only until
fresh deployment acceptance is complete.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import base64
import fcntl
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import socket
import stat
import subprocess
import sys
import tempfile
import uuid


def save_new(path,value):
    path=Path(path)
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'w') as f:
        json.dump(value,f,indent=2);f.write('\n')


def private(path):
    path=Path(path);s=path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o077 or s.st_nlink!=1:
        raise ValueError('Individual private file required')
    return json.loads(path.read_text())


def update(path,value):
    path=Path(path);private(path)
    with tempfile.NamedTemporaryFile('w',dir=path.parent,prefix='.jdu-state-',delete=False) as f:
        os.chmod(f.name,0o600);json.dump(value,f,indent=2);f.write('\n');temporary=Path(f.name)
    os.replace(temporary,path)


@contextmanager
def locked(path):
    path=Path(str(path)+'.lock');s=path.parent.stat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o022:
        raise ValueError('State parent must be an individual non-writable directory')
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);yield
    finally:os.close(fd)


def identity(verified,state):
    import boto3
    m=verified['manifest']
    if (state['account']!=boto3.client('sts').get_caller_identity()['Account'] or state['region']!=m['region']
            or state['manifest_sha256']!=verified['manifest_sha256']
            or state['stack_name']!='jdu-web-'+state['lab_id']
            or state['release_id']!=m['release_id']):raise ValueError('Account or signed release differs')


def existing_nodes(ec2):
    return [i for page in ec2.get_paginator('describe_instances').paginate(Filters=[dict(Name='instance-state-name',
        Values=['pending','running','stopping','stopped','shutting-down'])]) for r in page['Reservations'] for i in r['Instances']]


def budget_check(current, ceiling=9):
    # A conservative pilot guard, not a claim about an AWS/Vocareum quota.
    return dict(existing_nonterminated=len(current),new_nodes=5,pilot_ceiling=ceiling,
                projected=len(current)+5,within_pilot_budget=len(current)+5<=ceiling)


def plan(verified,a):
    import boto3
    import web_lab
    if not a.lab_id or not re.fullmatch('[a-z0-9][a-z0-9-]{2,31}',a.lab_id):raise ValueError('Lab ID required')
    if not a.output:raise ValueError('New plan output path required')
    m=verified['manifest'];region=m['region'];ec2=boto3.client('ec2',region_name=region);cfn=boto3.client('cloudformation',region_name=region)
    account=boto3.client('sts').get_caller_identity()['Account'];name='jdu-web-'+a.lab_id
    try:cfn.describe_stacks(StackName=name)
    except cfn.exceptions.ClientError as e:
        if e.response['Error']['Code']!='ValidationError' or e.response['Error']['Message']!=f'Stack with id {name} does not exist':raise
    else:raise ValueError('Existing stack retained; use status')
    web_lab.check_ami(m,ec2.describe_images(ImageIds=[m['ami']['id']]))
    key=ec2.describe_key_pairs(KeyNames=[a.key_name or 'vockey'],IncludePublicKey=True)['KeyPairs']
    if len(key)!=1:raise ValueError('One existing Academy public key is required')
    public=' '.join(key[0]['PublicKey'].split()[:2]);web_lab.ssh_public_key(public.encode())
    # Existing Academy EC2 key is only a bootstrap public-key parameter; no PEM is downloaded.
    lists=ec2.describe_managed_prefix_lists(PrefixListIds=[m['network']['s3_prefix_list_id']])['PrefixLists']
    if len(lists)!=1 or lists[0]['OwnerId']!='AWS' or lists[0]['PrefixListName']!='com.amazonaws.'+region+'.s3':raise ValueError('Wrong S3 prefix list')
    template=verified['files']['template'].read_bytes();cfn.validate_template(TemplateBody=template.decode())
    selection=web_lab.select_instances(verified,a.price_catalog,(),())
    def addresses(host):return sorted({x[4][0] for x in socket.getaddrinfo(host,443,family=socket.AF_INET,type=socket.SOCK_STREAM)})
    import ipaddress
    ranges=[ipaddress.ip_network(x['Cidr']) for x in ec2.get_managed_prefix_list_entries(PrefixListId=m['network']['s3_prefix_list_id'])['Entries']]
    s3=[v for v in addresses('s3.'+region+'.amazonaws.com') if any(ipaddress.ip_address(v) in n for n in ranges)]
    direct=[v for v in addresses(m['grading']['fqdn']) if v!=m['grading']['ipv4'] and not any(ipaddress.ip_address(v) in n for n in ranges)]
    if not s3 or not direct:raise ValueError('Live network controls unavailable')
    from prepare_teacher_probe import tls_control
    tls_control(s3[0],'s3.'+region+'.amazonaws.com','/')
    tls_control(direct[0],m['grading']['fqdn'],'/healthz',True);tls_control(m['grading']['ipv4'],m['grading']['fqdn'],'/healthz',True)
    value=dict(schema_version=1,scope='student_payload_candidate',expected_scope='student_payload',account=account,region=region,
        stack_name=name,lab_id=a.lab_id,deployment_id=str(uuid.uuid4()),release_id=m['release_id'],
        manifest_sha256=verified['manifest_sha256'],template_sha256=hashlib.sha256(template).hexdigest(),
        key_name=key[0]['KeyName'],student_public_key=public,selection=selection,
        s3_probe_ipv4=s3[0],direct_api_probe_ipv4=direct[0],resource_budget=budget_check(existing_nodes(ec2)),
        planned_at=datetime.now(timezone.utc).isoformat(),resources_created=False,student_release_ready=False,class_ready=False)
    save_new(a.output,value)
    return dict(stage='PLAN_READY',resource_budget=value['resource_budget'],private_key_download_required=False,
        selected_family=selection['family'],availability_zone=selection['availability_zone'],class_ready=False)


def validate_bootstrap_url(url,manifest,object_key):
    """Allow only the signed object, including S3's us-east-1 global endpoint.

    This checks destination identity, not the URL's cryptographic signature;
    the node loader independently verifies the downloaded signed payload.
    Never include the URL or query in exceptions or public reports.
    """
    from urllib.parse import urlsplit,unquote
    if not isinstance(url,str) or len(url)>16384 or any(c.isspace() or ord(c)<32 or ord(c)==127 for c in url):
        raise ValueError('Invalid bootstrap URL')
    parsed=urlsplit(url);bucket=manifest['bootstrap']['bucket'];region=manifest['region']
    endpoints={'s3.'+region+'.amazonaws.com'}
    if region=='us-east-1':endpoints.add('s3.amazonaws.com')
    allowed={(bucket+'.'+host,'/'+object_key) for host in endpoints}
    allowed.update((host,'/'+bucket+'/'+object_key) for host in endpoints)
    if (parsed.scheme!='https' or (parsed.hostname,unquote(parsed.path)) not in allowed
            or parsed.port not in (None,443) or parsed.username is not None or parsed.password is not None
            or parsed.fragment or not parsed.query):
        raise ValueError('Bootstrap URL must identify only the signed bucket/object')
    return url


def bootstrap_url(verified,a,s3):
    m=verified['manifest'];bundle=m['artifacts']['repo_bundle']
    object_key=m['bootstrap']['release_prefix']+Path(bundle['path']).name
    if a.bootstrap_url_file:
        file=Path(a.bootstrap_url_file);s=file.lstat()
        if (not stat.S_ISREG(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o077
                or s.st_nlink!=1 or not 0<s.st_size<=16384):
            raise ValueError('Bootstrap URL file must remain small and private')
        url=file.read_text().strip()
    else:
        head=s3.head_object(Bucket=m['bootstrap']['bucket'],Key=object_key)
        if head['ContentLength']!=bundle['size_bytes'] or head['Metadata'].get('sha256')!=bundle['sha256']:
            raise ValueError('Stored bundle differs')
        url=s3.generate_presigned_url('get_object',Params={'Bucket':m['bootstrap']['bucket'],'Key':object_key},ExpiresIn=7200)
    return validate_bootstrap_url(url,m,object_key)


def student_credential(verified,state,path):
    import web_progress
    credential=web_progress.private_json(path);m=verified['manifest']
    if (set(credential)!={'schema_version','api_base_url','fixed_ingress_ipv4','release_id','lab_id','lab_token'}
            or credential['schema_version']!=1 or not isinstance(credential['lab_token'],str) or not credential['lab_token']
            or credential['lab_id']!=state['lab_id'] or credential['release_id']!=m['release_id']
            or credential['api_base_url']!='https://'+m['grading']['fqdn']
            or credential['fixed_ingress_ipv4']!=m['grading']['ipv4']):
        raise ValueError('Only this student Lab credential and signed teacher endpoint are allowed')
    return credential


def deployment_parameters(verified,plan,template,url):
    """Validate the real selector/template boundary before human secret input."""
    m=verified['manifest'];sel=plan['selection']
    expected={'Bastion':'medium','Web':'small','Dns':'micro','Db':'small','Package':'small'}
    if (set(sel['roles'])!=set(expected) or sel['region']!=m['region'] or sel['architecture']!='x86_64'
            or sel['credit_mode']!='standard' or not re.fullmatch(r't[1-9][0-9]*[a-z]*',sel['family'])
            or not re.fullmatch(re.escape(m['region'])+r'[a-z]',sel['availability_zone'])):
        raise ValueError('Reviewed instance selection differs')
    types={r:x['instance_type'] for r,x in sel['roles'].items()}
    if any(types[r]!=sel['family']+'.'+size for r,size in expected.items()):
        raise ValueError('Selected role sizes must match the reviewed family')
    bundle=m['artifacts']['repo_bundle']
    values=dict(AvailabilityZone=sel['availability_zone'],StudentKeyName=plan['key_name'],StudentPublicKey=plan['student_public_key'],
        LabId=plan['lab_id'],DeploymentId=plan['deployment_id'],ReleaseId=m['release_id'],
        DeploymentPhase='bootstrap',ExpectedPayloadScope='student_payload',S3PrefixListId=m['network']['s3_prefix_list_id'],
        BootstrapBucket=m['bootstrap']['bucket'],BootstrapPrefix=m['bootstrap']['release_prefix'],BundleUrl=url,BundleSha256=bundle['sha256'],
        GradingApiUrl='https://'+m['grading']['fqdn'],GradingIpv4=m['grading']['ipv4'],S3ProbeIpv4=plan['s3_probe_ipv4'],
        DirectApiProbeIpv4=plan['direct_api_probe_ipv4'],BastionInstanceType=types['Bastion'],SmallInstanceType=types['Web'],DnsInstanceType=types['Dns'])
    declared=json.loads(template)['Parameters'];provided=set(values)|{'RdpPasswordHash'}
    if (provided-set(declared) or any('Default' not in rule and k not in provided for k,rule in declared.items())
            or any(not isinstance(v,str) or not v for v in values.values())):
        raise ValueError('Signed template parameter contract differs')
    return values


def create(verified,a):
    import boto3
    if not a.plan or not a.state or not a.confirmed_access or not sys.stdin.isatty():
        raise ValueError('Reviewed plan, new state, access confirmation and human TTY input required')
    p=private(a.plan);identity(verified,p);m=verified['manifest'];ec2=boto3.client('ec2',region_name=m['region'])
    if not budget_check(existing_nodes(ec2))['within_pilot_budget']:
        raise ValueError('Pilot resource ceiling exceeded; preserve existing servers and review resource plan')
    with locked(a.state):
        if Path(a.state).exists():raise ValueError('Existing state retained; use status')
        cfn=boto3.client('cloudformation',region_name=m['region'])
        try:cfn.describe_stacks(StackName=p['stack_name'])
        except cfn.exceptions.ClientError as e:
            if e.response['Error']['Code']!='ValidationError' or e.response['Error']['Message']!=f"Stack with id {p['stack_name']} does not exist":raise
        else:raise ValueError('Existing stack retained')
        template=verified['files']['template'].read_bytes()
        if hashlib.sha256(template).hexdigest()!=p['template_sha256']:raise ValueError('Plan template differs')
        key=ec2.describe_key_pairs(KeyNames=[p['key_name']],IncludePublicKey=True)['KeyPairs']
        if len(key)!=1 or ' '.join(key[0]['PublicKey'].split()[:2])!=p['student_public_key']:raise ValueError('Academy public key changed')
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(p['planned_at'])).total_seconds()
        if not 0<=age<=86400:raise ValueError('Plan must be no more than one day old')
        import web_lab
        web_lab.check_ami(m,ec2.describe_images(ImageIds=[m['ami']['id']]))
        from prepare_teacher_probe import tls_control
        tls_control(p['s3_probe_ipv4'],'s3.'+m['region']+'.amazonaws.com','/')
        tls_control(p['direct_api_probe_ipv4'],m['grading']['fqdn'],'/healthz',True)
        tls_control(m['grading']['ipv4'],m['grading']['fqdn'],'/healthz',True)
        profile=boto3.client('iam').get_instance_profile(InstanceProfileName='LabInstanceProfile')['InstanceProfile']
        if profile['InstanceProfileName']!='LabInstanceProfile' or len(profile['Roles'])!=1:raise ValueError('Existing Academy instance profile required')
        # Finish all non-secret bundle checks before asking a human for a password.
        bundle=m['artifacts']['repo_bundle']
        url=bootstrap_url(verified,a,boto3.client('s3',region_name=m['region']))
        values=deployment_parameters(verified,p,template,url)
        print('Five isolated nodes / 96 GiB; Web HTTP80; RDP reviewed50 CIDRs; bastion SSM and internal SSH only.',flush=True)
        password=getpass.getpass('RDP password (12-128 characters, hidden): ');again=getpass.getpass('Confirm RDP password: ')
        if password!=again or not 12<=len(password)<=128 or any(c in password for c in '\r\n\x00'):raise ValueError('Invalid password confirmation')
        result=subprocess.run(['openssl','passwd','-6','-stdin'],input=(password+'\n').encode(),capture_output=True,check=True)
        del password,again
        password_hash=result.stdout.decode().strip();del result
        values['RdpPasswordHash']=password_hash
        current_budget=budget_check(existing_nodes(ec2))
        if not current_budget['within_pilot_budget']:raise ValueError('Pilot resource ceiling changed; preserve state')
        state=dict(p,phase='CREATE_REQUEST_PENDING',resources_created=None,resource_budget_at_create=current_budget);save_new(a.state,state)
        response=cfn.create_stack(StackName=p['stack_name'],TemplateBody=template.decode(),
            Parameters=[dict(ParameterKey=k,ParameterValue=v) for k,v in values.items()],DisableRollback=True)
        del values,url,password_hash
        state.update(stack_id=response['StackId'],phase='CREATE_IN_PROGRESS',resources_created=True);update(a.state,state)
    return dict(stage='CREATE_IN_PROGRESS',class_ready=False)


def status(verified,a):
    import boto3
    state=private(a.state);identity(verified,state)
    if 'stack_id' not in state:
        stack=boto3.client('cloudformation',region_name=state['region']).describe_stacks(StackName=state['stack_name'])['Stacks'][0]
        params={x['ParameterKey']:x['ParameterValue'] for x in stack['Parameters']}
        if params.get('DeploymentId')!=state['deployment_id'] or params.get('LabId')!=state['lab_id']:raise ValueError('Unknown create outcome; preserve state')
        state['stack_id']=stack['StackId'];update(a.state,state)
    from inspect_teacher_probe import collect
    actual=boto3.client('cloudformation',region_name=state['region']).get_template(StackName=state['stack_id'],TemplateStage='Original')['TemplateBody']
    if isinstance(actual,str):actual=json.loads(actual)
    if actual!=json.loads(verified['files']['template'].read_text()):raise ValueError('Live template differs from signed candidate')
    report=collect(a.state,verified['files']['template'])
    if report['all_five_role_checks_passed'] and report['all_aws_checks_passed'] and report['all_five_network_checks_passed']:
        state['phase']='BASE_READY' if report['phase']=='bootstrap' else 'INFRA_READY'
        state['initial_five_node_acceptance_observed']=True;update(a.state,state)
        baseline=Path(str(a.state)+'.baseline.json')
        nodes={r:{k:n[k] for k in ('instance_id','private_ip','root_volumes')} for r,n in report['nodes'].items()}
        value=dict(account=state['account'],stack_id=state['stack_id'],lab_id=state['lab_id'],deployment_id=state['deployment_id'],
            proposed_sha256=hashlib.sha256((json.dumps(json.loads(verified['files']['template'].read_text()),separators=(',',':'))+'\n').encode()).hexdigest(),nodes=nodes)
        if baseline.exists():
            if private(baseline)!=value:raise ValueError('Saved node/root baseline changed')
        else:save_new(baseline,value)
    else:
        state['phase']='WAITING';update(a.state,state)
    if a.output:save_new(a.output,report)
    return dict(stack_status=report['stack_status'],phase=state['phase'],aws_passed=report['all_aws_checks_passed'],
        role_passed=report['all_five_role_checks_passed'],network_passed=report['all_five_network_checks_passed'],
        nodes={r:{k:v.get(k) for k in ('state','public_ip')} for r,v in report['nodes'].items()},class_ready=False)


def lock(verified,a):
    import boto3
    from inspect_teacher_probe import collect
    from lock_teacher_probe import require_baseline,validate_change_set
    state=private(a.state);identity(verified,state);path=Path(str(a.state)+'.closure.json')
    cfn=boto3.client('cloudformation',region_name=state['region'])
    actual=cfn.get_template(StackName=state['stack_id'],TemplateStage='Original')['TemplateBody']
    if isinstance(actual,str):actual=json.loads(actual)
    if actual!=json.loads(verified['files']['template'].read_text()):raise ValueError('Live template differs')
    if a.operation=='lock-prepare':
        if path.exists():raise ValueError('Existing closure retained; review it')
        require_baseline(collect(a.state,verified['files']['template']))
        stack=cfn.describe_stacks(StackName=state['stack_id'])['Stacks'][0]
        values=[dict(ParameterKey=x['ParameterKey'],ParameterValue='teaching') if x['ParameterKey']=='DeploymentPhase'
            else dict(ParameterKey=x['ParameterKey'],UsePreviousValue=True) for x in stack['Parameters']]
        name='teaching-'+uuid.uuid4().hex
        result=cfn.create_change_set(StackName=state['stack_id'],ChangeSetName=name,ChangeSetType='UPDATE',UsePreviousTemplate=True,Parameters=values)
        save_new(path,dict(account=state['account'],stack_id=state['stack_id'],deployment_id=state['deployment_id'],change_set_id=result['Id']))
        return dict(stage='CLOSURE_PREPARING',class_ready=False)
    saved=private(path)
    if any(saved[k]!=state[k] for k in ('account','stack_id','deployment_id')):raise ValueError('Wrong closure deployment')
    change=cfn.describe_change_set(StackName=state['stack_id'],ChangeSetName=saved['change_set_id'],IncludePropertyValues=True)
    review=validate_change_set(change)
    if a.operation=='lock-apply':
        require_baseline(collect(a.state,verified['files']['template']))
        save_new(str(path)+'.executed',dict(execution_requested=True))
        cfn.execute_change_set(StackName=state['stack_id'],ChangeSetName=saved['change_set_id'])
    return dict(stage='CLOSURE_EXECUTION_REQUESTED' if a.operation=='lock-apply' else 'CLOSURE_REVIEWED',changes=review,class_ready=False)


def ssh(verified,a):
    import setup_internal_ssh
    state=private(a.state);identity(verified,state)
    operation={'ssh-plan':'plan','ssh-apply':'apply','ssh-verify':'verify'}[a.operation]
    sys.argv=['setup_internal_ssh.py',operation,'--state',a.state,'--baseline-plan',a.state+'.baseline.json','--plan',a.state+'.ssh.json']
    setup_internal_ssh.main()
    return dict(stage='INTERNAL_SSH_'+operation.upper(),private_key_exported=False,class_ready=False)


def register(verified,a):
    import boto3
    from setup_internal_ssh import current_nodes,remote
    from enroll_five_node_progress import encrypt
    state=private(a.state);identity(verified,state);m=verified['manifest'];credential=student_credential(verified,state,a.student_config)
    nodes=current_nodes(boto3.client('ec2',region_name=state['region']),boto3.client('cloudformation',region_name=state['region']),state,private(a.state+'.baseline.json'))
    ssm=boto3.client('ssm',region_name=state['region']);bastion=nodes['bastion']['instance_id'];here=Path(__file__).parent
    source=(here/'progress_enrollment_guest.py').read_bytes();client=(here/'web_progress.py').read_bytes()
    common=dict(lab_id=state['lab_id'],deployment_id=state['deployment_id'],release_id=m['release_id'],instance_id=bastion)
    fields=dict(client_source_b64=base64.b64encode(client).decode(),client_sha256=hashlib.sha256(client).hexdigest());path=Path(a.state+'.registration.json')
    if a.operation=='register-plan':
        if path.exists():raise ValueError('Existing recipient retained')
        recipient=remote(ssm,bastion,source,dict(common,command='recipient'))
        if (not recipient['certificate_pem'].startswith('-----BEGIN CERTIFICATE-----')
                or hashlib.sha256(recipient['certificate_pem'].encode()).hexdigest()!=recipient['certificate_sha256']):
            raise ValueError('Own recipient certificate differs')
        probe=hashlib.sha256(uuid.uuid4().bytes).hexdigest();ciphertext=encrypt(recipient['certificate_pem'].encode(),json.dumps(dict(common,schema_version=1,purpose='transport_probe',probe=probe)).encode())
        ack=remote(ssm,bastion,source,dict(common,command='probe',ciphertext_b64=base64.b64encode(ciphertext).decode()))
        if ack!={'transport_probe':probe,'plaintext_credential_written':False}:raise ValueError('Encrypted transport probe failed')
        save_new(path,dict(**common,recipient=recipient,nodes=nodes,guest_sha256=hashlib.sha256(source).hexdigest(),client_sha256=fields['client_sha256']))
        return dict(stage='REGISTRATION_PREPARED',lab_token_issued=False,class_ready=False)
    p=private(path)
    if (any(p[k]!=common[k] for k in common) or p['nodes']!=nodes or p['guest_sha256']!=hashlib.sha256(source).hexdigest()
            or p['client_sha256']!=fields['client_sha256']):raise ValueError('Registration plan changed')
    if a.operation=='register-apply':
        current=remote(ssm,bastion,source,dict(common,command='status'))
        if current['credential_present'] and current['registration_present']:
            ack=remote(ssm,bastion,source,dict(common,command='complete' if current['transport_private_key_present'] else 'verify',**fields))
        else:
            value=dict(common,schema_version=1,purpose='progress_registration',credentials=credential)
            cipher=encrypt(p['recipient']['certificate_pem'].encode(),json.dumps(value).encode())
            ack=remote(ssm,bastion,source,dict(common,command='register',**fields,ciphertext_b64=base64.b64encode(cipher).decode()))
    else:ack=remote(ssm,bastion,source,dict(common,command='verify',**fields))
    if (ack.get('registered') is not True or ack.get('private_credential_exported') is not False
            or ack.get('transport_private_key_retired') is not True or ack.get('instance_count')!=5
            or any(ack.get(k)!=common[k] for k in ('lab_id','release_id','deployment_id'))):raise ValueError('Registration acknowledgment differs')
    receipt=Path(str(path)+'.accepted.json')
    if receipt.exists():
        if private(receipt)!=ack:raise ValueError('Registration acknowledgment changed')
    else:save_new(receipt,ack)
    return dict(stage='REGISTRATION_VERIFIED',credentials_exported=False,class_ready=False)


def install_commands(verified,a):
    state=private(a.state);identity(verified,state)
    student_credential(verified,state,a.student_config)
    # Existing registration and independently verified internal SSH are prerequisites.
    ack=private(a.state+'.registration.json.accepted.json')
    ssh=private(a.state+'.ssh.json.verified.public.json')
    if (ack['deployment_id']!=state['deployment_id'] or ack['registered'] is not True
            or ssh['deployment_id']!=state['deployment_id'] or ssh['persistent_ssh_verified_after_expiry'] is not True):
        raise ValueError('Registered deployment and persistent internal SSH required')
    here=Path(__file__).resolve().parent
    directory=Path.home()/'.jdu-web-student'/state['lab_id'];directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    bin_path=Path(a.bin_directory) if a.bin_directory else Path.home()/'.local/bin';bin_path.mkdir(mode=0o700,parents=True,exist_ok=True)
    for p in (directory,bin_path):
        s=p.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o022:raise ValueError('Unsafe personal command directory')
    config_path=directory/'command-state.json';mapping=directory/'deployment.public.json';baseline=private(a.state+'.baseline.json')
    q=shlex.quote;command='exec python3 -B '+q(str(here/'web_commands.py'));credential=' --config '+q(str(Path(a.student_config).resolve()))
    launchers={
        'jdu-web-check':'exec python3 -B '+q(str(here/'check_dispatch.py'))+' "$@" --command-state '+q(str(config_path))+'\n',
        'jdu-web-my-progress':command+' my-progress'+credential+' "$@"\n',
        'jdu-web-register':command+' register'+credential+' --state '+q(str(mapping))+' "$@"\n',
        'jdu-web-progress':'operation="${1:-}"\n[ -n "$operation" ] || exit 2\nshift\n'+command+' "$operation"'+credential+' "$@"\n'}
    if any(p.exists() or p.is_symlink() for p in [config_path,mapping,*[bin_path/n for n in launchers]]):
        raise ValueError('Existing command or config retained; select a different bin directory')
    c=dict(scope='signed_student_candidate_commands',state=str(Path(a.state).resolve()),baseline_plan=str(Path(a.state+'.baseline.json').resolve()),
        bootstrap_tools=str(here),ssh_enrollment=str(Path(a.state+'.ssh.json.enrolled.public.json').resolve()),
        pending_directory=str(directory/'pending'),network_source_sha256=hashlib.sha256((here/'network_probe.py').read_bytes()).hexdigest())
    for key,name in [('guest_source','post_restart_guest.py'),('submission_source','bootstrap_submission_guest.py')]:
        c[key]=str(here/name);c[key+'_sha256']=hashlib.sha256((here/name).read_bytes()).hexdigest()
    save_new(config_path,c);save_new(mapping,dict(lab_id=state['lab_id'],release_id=state['release_id'],deployment_id=state['deployment_id'],
        instances={r:n['instance_id'] for r,n in baseline['nodes'].items()}))
    for name,body in launchers.items():
        with os.fdopen(os.open(bin_path/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o700),'w') as f:
            f.write('#!/usr/bin/env bash\nset -euo pipefail\n'+body)
    state['command_config']=str(config_path);update(a.state,state)
    return dict(stage='COMMANDS_INSTALLED',commands=list(launchers),credential_copied=False,class_ready=False)


def preflight(verified,a):
    state=private(a.state);identity(verified,state)
    if not state.get('initial_five_node_acceptance_observed') or not state.get('command_config'):
        raise ValueError('Initial five-node acceptance, SSH, registration and command installation required')
    from check_bootstrap import main as check
    result=check(['bootstrap','--command-state',state['command_config']])
    if a.gui_confirmed:
        state['gui_confirmed_by_operator_at']=datetime.now(timezone.utc).isoformat();update(a.state,state)
    return dict(stage='PREFLIGHT_OBSERVED',current_foundation_passed=result==0,
        gui_confirmed=bool(state.get('gui_confirmed_by_operator_at')),student_release_ready=False,class_ready=False)


def run(verified,a):
    os.umask(0o077)
    if a.operation=='plan':return plan(verified,a)
    if a.operation=='create':return create(verified,a)
    if not a.state:raise ValueError('Own deployment state required')
    with locked(a.state):
        if a.operation in ('status','diagnose'):return status(verified,a)
        if a.operation.startswith('lock-'):return lock(verified,a)
        if a.operation.startswith('ssh-'):return ssh(verified,a)
        if a.operation.startswith('register-'):return register(verified,a)
        if a.operation=='install-commands':return install_commands(verified,a)
        if a.operation=='preflight':return preflight(verified,a)
        state=private(a.state);identity(verified,state)
        if a.operation=='ssm':
            from setup_internal_ssh import current_nodes
            import boto3
            nodes=current_nodes(boto3.client('ec2',region_name=state['region']),boto3.client('cloudformation',region_name=state['region']),state,private(a.state+'.baseline.json'))
            role=getattr(a,'role','bastion')
            if role not in nodes:raise ValueError('Known lab role required')
            template=json.loads(verified['files']['template'].read_text())
            label={'bastion':'Bastion','web':'Web','dns':'Dns','db':'Db','repo':'Repo'}[role]
            if template['Resources'][label+'Instance']['Properties'].get('IamInstanceProfile')!='LabInstanceProfile':
                raise ValueError('This signed template does not enable SSM on the requested role')
            subprocess.run(['aws','ssm','start-session','--region',state['region'],'--target',nodes[role]['instance_id']],check=True)
            return dict(stage='SSM_SESSION_ENDED',role=role,class_ready=False)
        raise ValueError('Unsupported student operation')
