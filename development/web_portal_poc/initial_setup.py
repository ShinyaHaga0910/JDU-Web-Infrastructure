"""R1 post-create foundation/closure/internal SSH; never apply lesson answers.

One explicit advance performs one bounded step. Observation cannot run SSM,
change a security group, push a key, or install anything. The original CLI
collector, closure validator and guest SSH helper remain the authoritative
checks; registration is a later, separately visible incomplete stage.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from portal_enrollment import EnrollmentDenied, encoded, key, grant_digest
from initial_ssm import BoundedSsm, JournaledSsm, InitialPending

ROLES=('web','dns','db','repo')


def collect_foundation(stack,state,ssm):
    from inspect_teacher_probe import collect
    from initial_worker import native
    # Only public plan/state is staged. No token, hash, URL or SSH private key
    # is restored to Lambda /tmp or copied to a student's Windows computer.
    with tempfile.TemporaryDirectory(prefix='jdu-initial-') as directory:
        path=Path(directory)/'state.json'
        with path.open('x',encoding='utf-8') as target:
            os.chmod(path,0o600);json.dump(native(state),target)
        return collect(path,stack.verified['files']['template'],clients={
            'sts':stack.sts,'cloudformation':stack.cfn,'ec2':stack.ec2,'ssm':ssm})


class InitialSetup:
    def __init__(self,stack,plan,ssm,eic,*,collector=collect_foundation,remaining=lambda:90000):
        self.s,self.plan,self.ssm,self.eic=stack,plan,ssm,eic
        self.collector,self.remaining=collector,remaining
        self.row=None

    def get(self):
        s=self.s
        item=s.db.get_item(TableName=s.table,Key=key(s.pk,'SETUP'),ConsistentRead=True).get('Item')
        row={k:TypeDeserializer().deserialize(v) for k,v in item.items()} if item else None
        if row and row.get('grant_digest')!=grant_digest(s.grant):
            raise EnrollmentDenied('Initial setup belongs to another assignment')
        return row

    def current(self):
        observed=self.s.current()
        row=self.get()
        if not row:
            if observed.get('stack_status') not in ('CREATE_COMPLETE','UPDATE_COMPLETE'):
                return observed
            return {**observed,'stage':'SETUP_REQUIRED','setup_phase':'check_foundation','can_advance':True}
        phase=row['phase']
        available=observed.get('stack_status') in ('CREATE_COMPLETE','UPDATE_COMPLETE','UPDATE_IN_PROGRESS')
        return {**observed,'stage':'SETUP_OBSERVATION_REQUIRED' if row.get('busy') else
                'REGISTRATION_PENDING' if phase=='registration_pending' else 'SETUP_PENDING',
            'setup_phase':phase,'can_advance':available and not row.get('busy') and phase!='registration_pending',
            'available_after':int(row.get('available_after',0)),
            'ssh_completed_roles':int(row.get('verified_peers',0)),
            'setup_result':row.get('last_result','pending'),
            'foundation_ready':phase=='registration_pending','lab_ready':False}

    def checkpoint(self,**updates):
        s=self.s;old=self.row
        new={**old,**updates,'revision':int(old['revision'])+1}
        s.db.put_item(TableName=s.table,Item=encoded(new),
            ConditionExpression='#rev=:rev AND #busy=:yes AND #owner=:owner',
            ExpressionAttributeNames={'#rev':'revision','#busy':'busy','#owner':'owner'},
            ExpressionAttributeValues=encoded({':rev':old['revision'],':yes':True,':owner':old['owner']}))
        self.row=new

    def advance(self):
        observed=self.s.current()
        if observed.get('stack_status') not in ('CREATE_COMPLETE','UPDATE_COMPLETE','UPDATE_IN_PROGRESS'):
            return observed
        s=self.s;row=self.get()
        if row is None:
            saved=self.plan()
            if not saved:raise EnrollmentDenied('Original plan unavailable')
            state={**saved['plan'],'stack_id':observed['stack_id']}
            row={'pk':s.pk,'sk':'SETUP','grant_digest':grant_digest(s.grant),
                 'phase':'check_foundation','revision':0,'busy':False,'state':state}
            try:s.db.put_item(TableName=s.table,Item=encoded(row),ConditionExpression='attribute_not_exists(pk)')
            except s.db.exceptions.ConditionalCheckFailedException:return self.current()
        if row.get('busy') or row['phase']=='registration_pending':return self.current()
        owner=uuid.uuid4().hex
        try:
            s.db.update_item(TableName=s.table,Key=key(s.pk,'SETUP'),
                UpdateExpression='SET #busy=:yes,#owner=:owner',
                ConditionExpression='#rev=:rev AND #busy=:no',
                ExpressionAttributeNames={'#rev':'revision','#busy':'busy','#owner':'owner'},
                ExpressionAttributeValues=encoded({':rev':row['revision'],':yes':True,':no':False,':owner':owner}))
        except s.db.exceptions.ConditionalCheckFailedException:return self.current()
        self.row={**row,'busy':True,'owner':owner}
        try:
            self.step()
        except InitialPending:
            # Keep the same phase and its accepted command/change-set handles.
            self.checkpoint(last_result='pending')
        except Exception:
            self.checkpoint(last_result='unavailable')
            raise
        else:
            self.checkpoint(last_result='ok')
        finally:
            s.db.update_item(TableName=s.table,Key=key(s.pk,'SETUP'),
                UpdateExpression='SET #busy=:no REMOVE #owner',ConditionExpression='#owner=:owner',
                ExpressionAttributeNames={'#busy':'busy','#owner':'owner'},
                ExpressionAttributeValues=encoded({':no':False,':owner':owner}))
        return self.current()

    def report(self,phase):
        report=self.collector(self.s,self.row['state'],BoundedSsm(self.ssm,self.remaining))
        if (report.get('phase')!=phase or not all(report.get(k) is True for k in
                ('all_five_role_checks_passed','all_aws_checks_passed','all_five_network_checks_passed'))
                or set(report.get('nodes',{}))!={'bastion',*ROLES}):
            raise InitialPending('Initial foundation checks not yet confirmed')
        return report

    def baseline(self,report):
        raw=json.loads(self.s.verified['files']['template'].read_bytes())
        state=self.row['state']
        return {'account':state['account'],'stack_id':state['stack_id'],'lab_id':state['lab_id'],
            'deployment_id':state['deployment_id'],
            'proposed_sha256':hashlib.sha256((json.dumps(raw,separators=(',',':'))+'\n').encode()).hexdigest(),
            'nodes':{r:{k:n[k] for k in ('instance_id','private_ip','root_volumes')} for r,n in report['nodes'].items()}}

    def teaching_nodes(self):
        from setup_internal_ssh import current_nodes
        nodes=current_nodes(self.s.ec2,self.s.cfn,self.row['state'],self.row['baseline'])
        infos=self.ssm.describe_instance_information(Filters=[{'Key':'InstanceIds',
            'Values':[n['instance_id'] for n in nodes.values()]}])['InstanceInformationList']
        if (len(infos)!=5 or {v['InstanceId'] for v in infos}!={n['instance_id'] for n in nodes.values()}
                or any(v.get('PingStatus')!='Online' for v in infos)):
            raise InitialPending('Keep the same five servers; management is unavailable')
        return nodes

    def change(self):
        try:
            return self.s.cfn.describe_change_set(StackName=self.row['state']['stack_id'],
                ChangeSetName=self.row.get('change_set_id','portal-teaching-'+self.s.grant['deployment_id']))
        except ClientError as error:
            if error.response.get('Error',{}).get('Code') in ('ChangeSetNotFound','ChangeSetNotFoundException'):
                raise InitialPending('Observe the same closure request') from None
            raise

    def guest(self,phase,source,request):
        from setup_internal_ssh import remote
        # DynamoDB map ordering must not change the actual retained command.
        request=json.loads(json.dumps(request,sort_keys=True))
        return remote(JournaledSsm(self.s,self.ssm,phase,self.remaining),
                      self.row['baseline']['nodes']['bastion']['instance_id'],source,request)

    def step(self):
        from lock_teacher_probe import require_baseline,validate_change_set
        from setup_internal_ssh import console_host_key
        from internal_ssh_guest import public_key
        s=self.s;phase=self.row['phase'];state=self.row['state']
        if phase=='check_foundation':
            report=self.report('bootstrap');require_baseline(report)
            self.checkpoint(baseline=self.baseline(report),phase='close_prepare')
            return
        if phase=='close_prepare':
            report=self.report('bootstrap');require_baseline(report)
            if self.baseline(report)!=self.row['baseline']:
                raise EnrollmentDenied('Initial five IDs or roots changed')
            stack=s.cfn.describe_stacks(StackName=state['stack_id'])['Stacks'][0]
            parameters=[{'ParameterKey':v['ParameterKey'],'ParameterValue':'teaching'} if v['ParameterKey']=='DeploymentPhase'
                        else {'ParameterKey':v['ParameterKey'],'UsePreviousValue':True} for v in stack['Parameters']]
            # Commit the deterministic handle before the external request.
            self.checkpoint(phase='close_plan_sent')
            try:
                response=s.cfn.create_change_set(StackName=state['stack_id'],
                    ChangeSetName='portal-teaching-'+s.grant['deployment_id'],ChangeSetType='UPDATE',
                    UsePreviousTemplate=True,Parameters=parameters,ClientToken='portal-plan-'+s.grant['deployment_id'])
            except Exception:
                raise InitialPending('Observe the same closure request') from None
            self.checkpoint(change_set_id=response['Id'])
            return
        if phase=='close_plan_sent':
            change=self.change()
            if change['Status']=='CREATE_IN_PROGRESS':raise InitialPending('Closure plan pending')
            validate_change_set(change)
            self.checkpoint(phase='close_apply_sent')
            try:s.cfn.execute_change_set(StackName=state['stack_id'],ChangeSetName=change['ChangeSetId'],
                                        ClientRequestToken='portal-close-'+s.grant['deployment_id'])
            except Exception:raise InitialPending('Observe the same closure execution') from None
            return
        if phase=='close_apply_sent':
            stack=s.cfn.describe_stacks(StackName=state['stack_id'])['Stacks'][0]
            params={p['ParameterKey']:p.get('ParameterValue') for p in stack['Parameters']}
            if stack['StackStatus']!='UPDATE_COMPLETE' or params.get('DeploymentPhase')!='teaching':
                raise InitialPending('Closure execution not confirmed')
            report=self.report('teaching')
            if self.baseline(report)!=self.row['baseline']:raise EnrollmentDenied('Original roots changed during closure')
            self.checkpoint(phase='ssh_discover',peers={},peer_index=0)
            return
        nodes=self.teaching_nodes()
        common={k:state[k] for k in ('lab_id','deployment_id')}
        if phase=='ssh_discover':
            role=ROLES[int(self.row['peer_index'])];node=nodes[role]
            try:host=console_host_key(s.ec2.get_console_output(InstanceId=node['instance_id'],Latest=True).get('Output',''))
            except ValueError:
                from ssm_node_evidence import collect
                host=public_key(collect(BoundedSsm(self.ssm,self.remaining),state,role,node['instance_id'],'teaching')['public_host_key'])
            peers={**self.row['peers'],role:{**node,'host_key':host}}
            index=int(self.row['peer_index'])+1
            self.checkpoint(peers=peers,peer_index=0 if index==4 else index,
                            phase='ssh_init' if index==4 else phase)
            return
        import internal_ssh_guest
        source=Path(internal_ssh_guest.__file__).read_bytes()
        if phase=='ssh_init':
            result=self.guest('ssh-init',source,{**common,'command':'init','instance_id':nodes['bastion']['instance_id'],'peers':self.row['peers']})
            if result.get('private_key_exported') is not False:raise EnrollmentDenied('Private key export refused')
            pub=public_key(result['public_key'])
            self.checkpoint(public_key=pub,phase='ssh_enroll',peer_index=0)
            return
        if phase not in ('ssh_enroll','ssh_verify'):raise EnrollmentDenied('Unknown setup phase')
        role=ROLES[int(self.row['peer_index'])];peer=nodes[role];pub=self.row['public_key']
        command_phase='ssh-'+('enroll' if phase=='ssh_enroll' else 'verify')+'-'+role
        if phase=='ssh_verify' and s.clock()<self.row['available_after']:
            raise InitialPending('Wait for the ephemeral key to expire')
        if phase=='ssh_enroll' and JournaledSsm(s,self.ssm,command_phase,self.remaining).saved() is None:
            pushed=self.eic.send_ssh_public_key(InstanceId=peer['instance_id'],InstanceOSUser='ubuntu',
                                              SSHPublicKey=pub,AvailabilityZone=peer['availability_zone'])
            if pushed.get('Success') is not True:raise InitialPending('SSH public key was not accepted')
            self.checkpoint(available_after=int(s.clock())+63)
        self.guest(command_phase,source,{**common,'command':'connect','instance_id':nodes['bastion']['instance_id'],
            'peer_role':role,'peer_instance_id':peer['instance_id'],'public_key':pub,
            'verify_only':phase=='ssh_verify','helper_b64':base64.b64encode(source).decode()})
        index=int(self.row['peer_index'])+1
        if phase=='ssh_enroll':
            self.checkpoint(peer_index=0 if index==4 else index,phase='ssh_verify' if index==4 else phase)
        else:
            self.checkpoint(peer_index=0 if index==4 else index,verified_peers=index,
                            phase='registration_pending' if index==4 else phase)
