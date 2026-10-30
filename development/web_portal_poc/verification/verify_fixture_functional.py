"""Acceptance only: use the original fictional fixture password inside bastion.
The product uses the browser password form. No plaintext password leaves EC2.
"""
import argparse,base64,json,os,re,shlex,sys,time
from pathlib import Path
from zipfile import ZipFile
import boto3
from botocore.config import Config
os.umask(0o077)
p=argparse.ArgumentParser();p.add_argument('--job',required=True);args=p.parse_args()
assert re.fullmatch(r'[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}',args.job)
r=Path.home()/'jdu-web-special-checks-20261030-r1'
ZipFile(r/'checks.zip').extractall(r/'runtime');sys.path.insert(0,str(r/'runtime'))
from assessment_command_jobs import DE,native,key
s=boto3.session.Session(region_name='us-east-1');assert s.client('sts').get_caller_identity()['Account']=='965244652544'
lam=s.client('lambda',config=Config(read_timeout=150,retries={'total_max_attempts':1}));name='jdu-web-check-class193548-test1'
env=lam.get_function_configuration(FunctionName=name)['Environment']['Variables'];db=s.client('dynamodb')
raw=db.get_item(TableName=env['CHECK_TABLE'],Key=key('FLOW#'+args.job,'STATE'),ConsistentRead=True)['Item']
row=native({k:DE.deserialize(v) for k,v in raw.items()});spec=row['spec']
assert spec['deployment_id']=='3ab82943-031d-4806-b4c0-c0b0e4554006' and spec['task_id'] in ('M5','M6') and spec['check_mode']=='functional'
def invoke(operation,**fields):
 response=lam.invoke(FunctionName=name,InvocationType='RequestResponse',Payload=json.dumps({'operation':operation,'spec':spec,**fields}).encode())
 assert not response.get('FunctionError');return json.loads(response['Payload'].read())
value=invoke('result');assert value['status']=='ok'
if value['job']['phase']=='report_ready':print('FUNCTIONAL_ALREADY_COMPLETE='+json.dumps(value['result']['score']));raise SystemExit()
context=invoke('functional_context');assert context['job']['phase']=='awaiting_password'
recipient=context['functional_recipient'];assert recipient['job_id']==args.job
command_source="""import base64,json,os,stat,subprocess
from pathlib import Path
job=JOB
expected=PUBLIC
root=Path('/var/lib/jdu-web/browser-functional')/job
context=json.loads((root/'context.json').read_bytes())
assert context['context']['run_id']==job and context['context']['deployment_id']=='3ab82943-031d-4806-b4c0-c0b0e4554006'
private=root/'recipient.pem'
public=subprocess.run(['openssl','pkey','-in',str(private),'-pubout'],capture_output=True,check=True,timeout=5).stdout.decode()
assert public==expected
fd=os.open('/var/lib/jdu-web/d11-app-manager-r1/credentials.private.json',os.O_RDONLY|os.O_NOFOLLOW)
with os.fdopen(fd) as f:
 info=os.fstat(f.fileno());assert info.st_uid==0 and stat.S_ISREG(info.st_mode) and not info.st_mode&0o077
 password=json.load(f)['mission']['admin']
plain=json.dumps([job,password],separators=(',',':')).encode()
sealed=subprocess.run(['openssl','pkeyutl','-encrypt','-inkey',str(private),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'],input=plain,capture_output=True,check=True,timeout=5).stdout
assert len(sealed)==512
print(base64.b64encode(sealed).decode())
""".replace('job=JOB','job='+repr(args.job)).replace('expected=PUBLIC','expected='+repr(recipient['public_key']))
ssm=s.client('ssm',config=Config(retries={'total_max_attempts':1}));receipt=r/('functional-delivery-'+args.job+'.private.json')
if receipt.exists():command_id=json.loads(receipt.read_bytes())['command_id']
else:
 sent=ssm.send_command(InstanceIds=[spec['instances']['bastion']],DocumentName='AWS-RunShellScript',Parameters={'commands':['python3 -B -c '+shlex.quote(command_source)],'executionTimeout':['30']},TimeoutSeconds=30,Comment='JDU-functional-fixture-'+args.job,CloudWatchOutputConfig={'CloudWatchOutputEnabled':False})
 command_id=sent['Command']['CommandId']
 with receipt.open('x') as f:json.dump({'job_id':args.job,'command_id':command_id,'plaintext_exported':False},f)
for attempt in range(18):
 try:answer=ssm.get_command_invocation(CommandId=command_id,InstanceId=spec['instances']['bastion'])
 except ssm.exceptions.InvocationDoesNotExist:time.sleep(3);continue
 if answer['Status']=='Success':break
 if answer['Status'] not in ('Pending','InProgress','Delayed'):raise RuntimeError('Fixture delivery unavailable: '+answer['Status'])
 time.sleep(3)
else:raise RuntimeError('Inspect retained delivery; no automatic resend')
sealed=answer['StandardOutputContent'].strip();assert len(base64.b64decode(sealed,validate=True))==512
value=invoke('functional_start',sealed_password=sealed)
for attempt in range(20):
 assert value['status']=='ok',value['status']
 phase=value['job']['phase'];print('FUNCTIONAL_PHASE='+phase,flush=True)
 if phase=='report_ready':
  print('FUNCTIONAL_ORIGINAL_SCORE='+json.dumps(value['result']['score']),flush=True);break
 if phase=='failed':raise RuntimeError('Inspect retained observation; no retry')
 time.sleep(3);value=invoke('advance')
else:raise RuntimeError('Retained functional job pending')
with (r/('functional-'+args.job+'.public.json')).open('x') as f:json.dump({'job_id':args.job,'task_id':spec['task_id'],'fixture_delivery_only':True,'plaintext_password_exported':False,'result':value['result']},f)
