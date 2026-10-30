"""Existing storage and functional checks with browser-driven explicit steps."""
import base64
import copy
import hashlib
import json
import re
import uuid

from assessment_command_jobs import CommandJobs,JobDenied,encoded,key,native,DE,sha
from assessment_observation import Observation,checked_snapshot
from registry import CONTRACT_SHA256,score


class SpecialChecks:
    def __init__(self,owner,spec):
        self.o,self.spec=owner,spec
        self.pk='FLOW#'+spec['job_id']

    def get(self):
        item=self.o.db.get_item(TableName=self.o.table,Key=key(self.pk,'STATE'),ConsistentRead=True).get('Item')
        row=native({k:DE.deserialize(v) for k,v in item.items()}) if item else None
        if row and row.get('spec')!=self.spec:raise JobDenied('Own original workflow required')
        return row

    def once(self,field,value):
        try:
            self.o.db.update_item(TableName=self.o.table,Key=key(self.pk,'STATE'),
                UpdateExpression='SET #field=:value',ConditionExpression='spec_sha256=:spec AND attribute_not_exists(#field)',
                ExpressionAttributeNames={'#field':field},ExpressionAttributeValues=encoded({':value':value,':spec':sha(self.spec)}))
        except self.o.db.exceptions.ConditionalCheckFailedException:
            pass
        return self.get()

    def create(self):
        row=self.get()
        if row:return row
        # A normal job and special workflow may not reuse the same ID.
        existing=self.o.db.get_item(TableName=self.o.table,Key=key('CHECK#'+self.spec['job_id'],'JOB'),ConsistentRead=True).get('Item')
        if existing:raise JobDenied('Retained job ID already used')
        snapshot=checked_snapshot(self.spec,self.o.snapshot(self.spec))
        row={'pk':self.pk,'sk':'STATE','spec':self.spec,'spec_sha256':sha(self.spec),'snapshot':snapshot}
        try:self.o.db.put_item(TableName=self.o.table,Item=encoded(row),ConditionExpression='attribute_not_exists(pk)')
        except self.o.db.exceptions.ConditionalCheckFailedException:pass
        return self.get()

    def prepare_spec(self):
        value=copy.deepcopy(self.spec)
        value['job_id']=str(uuid.UUID(bytes=hashlib.sha256(('prepare:'+self.spec['job_id']).encode()).digest()[:16],version=4))
        value['check_mode']=self.spec['check_mode']+'_prepare'
        return value

    def jobs(self,spec,snapshot,**options):
        expected={**snapshot,'spec_sha256':sha(spec)}
        observer=Observation(spec,expected,**options)
        return CommandJobs(self.o.db,self.o.table,self.o.ssm,observer.command,
            lambda value:self.o.snapshot(value)==expected,finish_observation=observer.finish)

    def view(self,phase):
        return {'status':'ok','job':{'job_id':self.spec['job_id'],'task_id':self.spec['task_id'],
                                  'check_mode':self.spec['check_mode'],'phase':phase,
                                  **({'web_instance_id':self.spec['instances']['web']} if self.spec['check_mode']=='storage' else {})}}

    def preparation(self,row,operation):
        spec=self.prepare_spec();jobs=self.jobs(spec,row['snapshot'])
        saved=jobs.get(spec)
        if operation in ('start','advance'):
            if not saved:jobs.enqueue(spec)
            view=jobs.advance(spec)
        elif saved:view=jobs.current(spec)
        else:return self.view('queued'),None
        if view['phase']!='report_ready':return self.view(view['phase']),None
        return None,jobs.get(spec)

    def before(self,prepared):
        evidence=prepared.get('observation_metadata',{}).get('storage_evidence',{})
        if (score(prepared['report'])['raw_earned']<2
                or evidence.get('root_volume') not in self.get()['snapshot']['root_volumes']['web']
                or not re.fullmatch(r'[a-f0-9]{64}',evidence.get('marker_sha256',''))
                or not re.fullmatch(r'[a-f0-9-]{36}',evidence.get('boot_id',''))):
            raise JobDenied('Prepare the task marker and permissions first')
        return {**{k:self.spec[k] for k in ('lab_id','deployment_id')},
            **{k:evidence[k] for k in ('root_volume','marker_sha256','boot_id')},
            'task_id':self.spec['task_id'],'instance_id':self.spec['instances']['web'],
            'contract_sha256':CONTRACT_SHA256,'evidence_id':self.spec['job_id']}

    def recipient(self,prepared):
        value=prepared.get('observation_metadata',{}).get('functional_recipient')
        if (type(value) is not dict or set(value)!={'job_id','public_key'} or value['job_id']!=self.spec['run_id']
                or not isinstance(value['public_key'],str) or len(value['public_key'])>2048
                or not value['public_key'].startswith('-----BEGIN PUBLIC KEY-----')):
            raise JobDenied('Own password recipient unavailable')
        return value

    def stopped(self,before,row):
        if row.get('stopped'):return row
        node=self.o.ec2.describe_instances(InstanceIds=[before['instance_id']])['Reservations'][0]['Instances'][0]
        tags={t['Key']:t['Value'] for t in node.get('Tags',[])}
        if (node['InstanceId']!=before['instance_id'] or node['State']['Name']!='stopped'
                or tags.get('LabId')!=before['lab_id'] or tags.get('DeploymentId')!=before['deployment_id']
                or [v['Ebs']['VolumeId'] for v in node['BlockDeviceMappings']]!=[before['root_volume']]):
            raise JobDenied('Stop the same Web explicitly in AWS first')
        saved={k:before[k] for k in ('lab_id','deployment_id','instance_id','task_id','root_volume','evidence_id')}
        return self.once('stopped',{**saved,'state':'stopped'})

    def serve(self,event):
        operation=event['operation'];row=self.create() if operation=='start' else self.get()
        if not row:raise JobDenied('Start your own workflow first')
        pending,prepared=self.preparation(row,operation)
        if pending:return pending
        options={};mode=self.spec['check_mode']
        if mode=='functional':
            recipient=self.recipient(prepared)
            if operation=='functional_context':return {**self.view('awaiting_password'),'functional_recipient':recipient}
            if operation=='functional_start':
                sealed=event.get('sealed_password')
                if not isinstance(sealed,str) or len(base64.b64decode(sealed,validate=True))!=512:
                    raise JobDenied('Encrypted password delivery required')
                row=self.once('sealed_password',sealed)
            if not row.get('sealed_password'):return self.view('awaiting_password')
            options['sealed_password']=row['sealed_password'];snapshot=row['snapshot']
        else:
            before=self.before(prepared)
            if operation=='storage_observe':row=self.stopped(before,row)
            if not row.get('stopped'):return self.view('awaiting_stop')
            if not row.get('resume_snapshot'):
                if operation!='storage_resume':return self.view('awaiting_restart')
                current=checked_snapshot(self.spec,self.o.snapshot(self.spec))
                if any(current[k]!=row['snapshot'][k] for k in current if k!='public_web_ipv4'):
                    raise JobDenied('Original five nodes and volumes required after restart')
                row=self.once('resume_snapshot',current)
            snapshot=row['resume_snapshot'];options.update(before=before,stopped=row['stopped'])
        jobs=self.jobs(self.spec,snapshot,**options);saved=jobs.get(self.spec)
        if operation in ('start','advance','functional_start','storage_resume'):
            if not saved:jobs.enqueue(self.spec)
            view=jobs.advance(self.spec)
        elif saved:view=jobs.current(self.spec)
        else:return self.view('queued')
        answer={'status':'ok','job':{**view,'check_mode':mode}}
        if view['phase']=='report_ready':
            report=jobs.retained_report(self.spec)
            if operation=='report':return {**answer,'report':report}
            answer['result']={'task_id':self.spec['task_id'],'checked_at':report['checked_at'],'request_id':report['request_id'],
                'checks':[{'id':c['id'],'status':c['status']} for c in report['checks']],'score':score(report)}
        return answer
