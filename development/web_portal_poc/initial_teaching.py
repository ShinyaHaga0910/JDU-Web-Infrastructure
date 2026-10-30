"""Explicit public lesson placement and readiness of the fixed two connectors."""
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import shlex
import zlib

from initial_context import get,context
from initial_ssm import JournaledSsm,InitialPending
from initial_worker import plan_digest
from portal_enrollment import EnrollmentDenied,encoded,grant_digest


def command(source,request):
    packed=base64.b64encode(zlib.compress(json.dumps({'source':source.decode(),'request':request},
        sort_keys=True,separators=(',',':')).encode(),9)).decode()
    program="import base64,zlib,json,io,sys;p=json.loads(zlib.decompress(base64.b64decode("+repr(packed)+")));sys.stdin=io.StringIO(json.dumps(p['request']));exec(p['source'])"
    text='python3 -B -c '+shlex.quote(program)
    if len(text.encode())>60000:raise EnrollmentDenied('Bounded public staging required')
    return text


class InitialTeaching:
    def __init__(self,setup,root,env,lam):
        self.setup,self.s,self.root,self.env,self.lam=setup,setup.s,Path(root),env,lam

    def configuration(self,ready=False):
        return context(self.root,self.env,self.s.db,require_ready=ready)

    def get(self,sk):
        return get(self.s.db,self.s.table,self.s.grant,sk)

    def assets(self):
        raw=(self.root/'initial-teaching.json').read_bytes();value=json.loads(raw)
        if (value.get('schema_version')!=1 or value.get('services_changed') is not False
                or set(value.get('files',{}))!={'catalog-app.tar.gz','registry.py','assessment-registry.json','database_secret.py','offline_assets.py'}):
            raise EnrollmentDenied('Fixed public teaching assets required')
        files={}
        for name,pin in value['files'].items():
            if Path(pin['source']).name!=pin['source']:raise EnrollmentDenied('Fixed public teaching source required')
            data=(self.root/pin['source']).read_bytes()
            if len(data)!=pin['size_bytes'] or hashlib.sha256(data).hexdigest()!=pin['sha256']:
                raise EnrollmentDenied('Public teaching asset changed')
            files[name]=base64.b64encode(data).decode()
        return hashlib.sha256(raw).hexdigest(),files

    def save(self,sk,body):
        row={'pk':self.s.pk,'sk':sk,'grant_digest':grant_digest(self.s.grant),**body}
        try:self.s.db.put_item(TableName=self.s.table,Item=encoded(row),ConditionExpression='attribute_not_exists(pk)')
        except self.s.db.exceptions.ConditionalCheckFailedException:
            if self.get(sk)!=row:raise EnrollmentDenied('Original preparation receipt retained') from None

    def current(self):
        observed=self.s.current()
        _,_,cfg=self.configuration()
        digest,_=self.assets()
        rows=[self.get('TEACHING#'+r) for r in ('web','db')]
        for role,row in zip(('web','db'),rows):
            if row and (row.get('asset_manifest_sha256')!=digest or row.get('role')!=role
                        or row.get('instance_id')!=cfg['baseline']['nodes'][role]['instance_id']):
                raise EnrollmentDenied('Original lesson target changed')
        ready=self.get('READY')
        if ready:
            self.configuration(ready=True)
            return {**observed,'stage':'INITIAL_READY','setup_phase':'initial_ready','can_advance':False,
                'teaching_completed_roles':2,'ssh_completed_roles':4,'foundation_ready':True,'connectors_ready':True,'lab_ready':True}
        return {**observed,'stage':'TEACHING_ASSETS_PENDING','setup_phase':'teaching_assets_pending',
            'teaching_completed_roles':sum(r is not None for r in rows),'ssh_completed_roles':4,
            'can_advance':True,'foundation_ready':True,'connectors_ready':False,'lab_ready':False}

    def advance(self):
        observed=self.current()
        if observed['lab_ready']:return observed
        _,grant,cfg=self.configuration()
        self.setup.row=self.setup.get();self.setup.teaching_nodes()
        digest,files=self.assets()
        for role in ('web','db'):
            if self.get('TEACHING#'+role):continue
            iid=cfg['baseline']['nodes'][role]['instance_id']
            request={k:grant[k] for k in ('lab_id','deployment_id')}
            request.update(role=role,instance_id=iid,files=files)
            source=(self.root/'initial_lesson_guest.py').read_bytes()
            ssm=JournaledSsm(self.s,self.setup.ssm,'teaching-'+role,self.setup.remaining)
            command_id=ssm.send_command(InstanceIds=[iid],DocumentName='AWS-RunShellScript',
                Parameters={'commands':[command(source,request)],'executionTimeout':['90']},TimeoutSeconds=30)['Command']['CommandId']
            # A single poll per explicit POST. Never send again while the
            # original command is pending, including after a lost response.
            try:reply=ssm.get_command_invocation(CommandId=command_id,InstanceId=iid)
            except ssm.exceptions.InvocationDoesNotExist:raise InitialPending('Observe the same lesson command') from None
            if reply['Status'] in ('Pending','InProgress','Delayed'):raise InitialPending('Observe the same lesson command')
            if reply['Status']!='Success':raise EnrollmentDenied('Inspect the original lesson command')
            value=json.loads(reply['StandardOutputContent'])
            if value!={'public_resources_ready':True,'role':role,'file_count':5,'services_changed':False}:
                raise EnrollmentDenied('Public lesson placement not confirmed')
            self.save('TEACHING#'+role,{'role':role,'instance_id':iid,'asset_manifest_sha256':digest})
            return self.current()
        self.connectors(cfg)
        self.save('READY',{'ready':True,'asset_manifest_sha256':digest,'config_sha256':plan_digest(cfg)})
        return self.current()

    def invoke(self,name,event):
        result=self.lam.invoke(FunctionName='arn:aws:lambda:us-east-1:'+self.s.grant['account']+':function:'+name,
            InvocationType='RequestResponse',Payload=json.dumps(event).encode())
        body=result.get('Payload')
        try:raw=body.read(16385) if body else b''
        finally:
            if hasattr(body,'close'):body.close()
        if result.get('StatusCode')!=200 or result.get('FunctionError') or len(raw)>16384:
            raise InitialPending('Own connector unavailable')
        return json.loads(raw)

    def connectors(self,cfg):
        lab=self.s.grant['lab_id'];account=self.s.grant['account']
        names={'jdu-web-initial-'+lab:'initial_worker.handler','jdu-web-status-'+lab:'initial_status_handler.handler',
               'jdu-web-check-'+lab:'initial_checker_handler.handler'}
        reference=None
        for name,handler in names.items():
            value=self.lam.get_function_configuration(FunctionName=name)
            env=value.get('Environment',{}).get('Variables',{})
            if (value.get('FunctionArn')!='arn:aws:lambda:us-east-1:'+account+':function:'+name
                    or value.get('Handler')!=handler or value.get('Runtime')!='python3.11'
                    or value.get('Role')!='arn:aws:iam::'+account+':role/LabRole'
                    or any(env.get(k)!=self.env[k] for k in ('STUDENT_ACCOUNT','LAB_ID','INITIAL_DEPLOYMENT_ID','INITIAL_PROGRESS_TABLE'))
                    or not re.fullmatch(r'[A-Za-z0-9+/]{43}=',value.get('CodeSha256',''))):
                raise EnrollmentDenied('Fixed initial connector configuration changed')
            if reference is None:reference=value['CodeSha256']
            elif value['CodeSha256']!=reference:raise EnrollmentDenied('Initial connector code differs')
            if name=='jdu-web-check-'+lab and env.get('INITIAL_CHECK_TABLE')!='jdu-web-check-'+lab+'-results':
                raise EnrollmentDenied('Fixed own result table required')
        status=self.invoke('jdu-web-status-'+lab,{'operation':'status'})
        nodes=status.get('observation',{}).get('instances',[])
        expected={n['instance_id']:r for r,n in cfg['baseline']['nodes'].items()}
        if (status.get('status')!='ok' or status.get('observation',{}).get('account')!=account
                or status['observation'].get('lab_id')!=lab or len(nodes)!=5
                or {n.get('instance_id'):n.get('role') for n in nodes}!=expected):
            raise InitialPending('Own five-node status not confirmed')
        health=self.invoke('jdu-web-check-'+lab,{'operation':'health'})
        if health!={'status':'ok','config_sha256':plan_digest(cfg)}:
            raise InitialPending('Own checker configuration not confirmed')
