"""Resume one initial-setup Run Command per fixed phase; never blindly resend."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re

from boto3.dynamodb.types import TypeDeserializer
from portal_enrollment import EnrollmentDenied, encoded, key, grant_digest


class InitialPending(RuntimeError):
    pass


def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class BoundedSsm:
    def __init__(self, client, remaining=lambda:90000):
        self.client,self.remaining=client,remaining
        self.exceptions=client.exceptions

    def guard(self):
        if self.remaining()<8000:
            raise InitialPending('Continue observing the same operation')

    def send_command(self,**request):
        self.guard()
        return self.client.send_command(**request)

    def get_command_invocation(self,**request):
        self.guard()
        return self.client.get_command_invocation(**request)

    def describe_instance_information(self,**request):
        return self.client.describe_instance_information(**request)


class JournaledSsm(BoundedSsm):
    def __init__(self,stack,client,phase,remaining=lambda:90000):
        super().__init__(client,remaining)
        if not re.fullmatch(r'(ssh-init|ssh-(enroll|verify)-(web|dns|db|repo)|progress-(recipient|register)|teaching-(web|db))',phase):
            raise EnrollmentDenied('Unknown setup phase')
        if (client.meta.config.retries or {}).get('total_max_attempts')!=1:
            raise EnrollmentDenied('Run Command retries must be disabled')
        self.stack,self.phase=stack,phase
        self.sk='COMMAND#'+phase

    def saved(self):
        s=self.stack
        item=s.db.get_item(TableName=s.table,Key=key(s.pk,self.sk),ConsistentRead=True).get('Item')
        return {k:TypeDeserializer().deserialize(v) for k,v in item.items()} if item else None

    def send_command(self,**request):
        self.guard()
        s=self.stack
        if (set(request)-{'InstanceIds','DocumentName','Parameters','TimeoutSeconds'}
                or len(request.get('InstanceIds',[]))!=1 or request.get('DocumentName')!='AWS-RunShellScript'):
            raise EnrollmentDenied('Fixed guest command required')
        parameters=request['Parameters']
        expected=sha(request)
        comment='jdu-initial-'+s.grant['deployment_id'][:8]+'-'+sha(self.phase)[:24]
        old=self.saved()
        if old is None:
            row={'pk':s.pk,'sk':self.sk,'grant_digest':grant_digest(s.grant),'request_sha256':expected,
                 'parameters_sha256':sha(parameters),'comment':comment,'instance_id':request['InstanceIds'][0],
                 'created_at':datetime.fromtimestamp(s.clock(),timezone.utc).isoformat()}
            try:
                s.db.put_item(TableName=s.table,Item=encoded(row),ConditionExpression='attribute_not_exists(pk)')
            except s.db.exceptions.ConditionalCheckFailedException:
                old=self.saved()
            else:
                try:
                    command=self.client.send_command(**request,Comment=comment)['Command']['CommandId']
                except Exception:
                    raise InitialPending('Run Command acceptance requires observation') from None
                return self.remember(row,command)
        if (not old or old.get('grant_digest')!=grant_digest(s.grant) or old.get('request_sha256')!=expected):
            raise EnrollmentDenied('Existing setup command retained')
        if old.get('command_id'):
            return {'Command':{'CommandId':old['command_id']}}
        # The intent survived but its acceptance reply did not. Match the
        # existing AWS handle, including all parameters; absence is not proof
        # that sending the command again is safe.
        found=set();token=None
        for _ in range(20):
            self.guard()
            after=datetime.fromisoformat(old['created_at'])-timedelta(seconds=5)
            args={'InstanceId':old['instance_id'],'MaxResults':50,'Filters':[
                {'key':'DocumentName','value':'AWS-RunShellScript'},
                {'key':'InvokedAfter','value':after.isoformat().replace('+00:00','Z')}]}
            if token:args['NextToken']=token
            answer=self.client.list_commands(**args)
            for command in answer.get('Commands',[]):
                if command.get('Comment')!=comment:continue
                if (command.get('InstanceIds')!=[old['instance_id']] or command.get('Targets') not in (None,[])
                        or command.get('DocumentName')!='AWS-RunShellScript'
                        or sha(command.get('Parameters'))!=old['parameters_sha256']):
                    raise EnrollmentDenied('Setup command context changed')
                found.add(command['CommandId'])
            token=answer.get('NextToken')
            if not token:break
        if token or len(found)>1:
            raise EnrollmentDenied('Setup command requires operator review')
        if not found:raise InitialPending('Run Command acceptance requires observation')
        return self.remember(old,next(iter(found)))

    def remember(self,row,command):
        if not isinstance(command,str) or not re.fullmatch(r'[a-f0-9-]{36}',command):
            raise EnrollmentDenied('Invalid AWS command handle')
        s=self.stack
        try:
            s.db.update_item(TableName=s.table,Key=key(s.pk,self.sk),UpdateExpression='SET command_id=:id',
                ConditionExpression='request_sha256=:digest AND (attribute_not_exists(command_id) OR command_id=:id)',
                ExpressionAttributeValues=encoded({':id':command,':digest':row['request_sha256']}))
        except Exception:
            raise InitialPending('Inspect the accepted setup command') from None
        return {'Command':{'CommandId':command}}
