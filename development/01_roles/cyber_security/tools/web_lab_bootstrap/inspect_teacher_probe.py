"""Read-only, identity-bound evidence for the five-node teacher package probe.

Exports only selected public fields, never full stack parameters or console logs.
"""
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re

NAMES={'bastion':'Bastion','web':'Web','dns':'Dns','db':'Db','repo':'Repo'}
IPS={'bastion':'10.20.1.10','web':'10.20.1.20','dns':'10.20.2.10','db':'10.20.2.20','repo':'10.20.2.30'}
ROOTS={'bastion':24,'web':16,'dns':8,'db':16,'repo':32}


def role_checks(role):
    checks={'ssh_active','chrony_active','pinned_role_packages_installed','root_free_space','initial_global_apt_cache_empty'}
    if role in ('dns','db','web'):checks.add('student_service_not_installed')
    if role=='repo':checks.add('repo_http_manifest_served')
    if role=='bastion':checks.update(('rdp_active','desktop_browser_and_dbus_present','rdp_user_not_admin'))
    return checks


def parse_console(output,role,instance,state):
    if 'JDU_NODE_' not in output:
        try:output=base64.b64decode(output,validate=True).decode('utf-8',errors='replace')
        except (ValueError,UnicodeError):pass
    # EC2 occasionally inserts standalone serial timestamps into an output line.
    output=re.sub(r'\[2026-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z?\]','',output)
    result={'role_result':None,'network_result':None,'failure_classes':[]}
    decoder=json.JSONDecoder()
    for name,key in (('ROLE','role_result'),('NETWORK','network_result')):
        marker='JDU_NODE_'+name+'_RESULT='
        for match in re.finditer(re.escape(marker),output):
            try:value,_=decoder.raw_decode(output[match.end():])
            except (ValueError,TypeError):continue
            identity={'lab_id':state['lab_id'],'deployment_id':state['deployment_id'],'release_id':'web-2026-10-r1',
                'role':role,'instance_id':instance,'expected_scope':state.get('expected_scope','package_only_candidate')}
            if not isinstance(value,dict) or any(value.get(k)!=v for k,v in identity.items()):continue
            checks=value.get('checks',{})
            expected=role_checks(role) if name=='ROLE' else {'repo_http','direct_api_egress_denied','fixed_teacher_https' if role=='bastion' else 'teacher_ingress_denied'}
            if set(checks)!=expected or any(type(v) is not bool for v in checks.values()):continue
            safe=dict(identity,checks=checks,checked_at=value.get('checked_at'))
            if name=='ROLE':
                if value.get('stage')!='ROLE_PREPARED' or value.get('student_release_ready') is not False:continue
                safe.update(stage='ROLE_PREPARED',student_release_ready=False)
            else:
                phase=value.get('phase')
                if phase not in ('BOOTSTRAP_OBSERVED','LOCK_TRANSITION_OBSERVED','NO_BOOTSTRAP_BASELINE') or value.get('class_ready') is not False:continue
                for field in ('s3_tcp_reachable','s3_bootstrap_reachable_seen','all_role_network_checks_passed'):
                    if type(value.get(field)) is not bool:break
                    safe[field]=value[field]
                else:
                    safe.update(phase=phase,class_ready=False);result[key]=safe
                continue
            result[key]=safe
    result['failure_classes']=sorted(set(re.findall(r'JDU_NODE_(?:BOOTSTRAP|LOADER|NETWORK)_FAILED=([A-Za-z][A-Za-z0-9_]{0,80})',output)))
    return result


def permissions(values):
    result=set()
    for item in values:
        base=(str(item['IpProtocol']),item.get('FromPort'),item.get('ToPort'))
        for key,field in (('IpRanges','CidrIp'),('Ipv6Ranges','CidrIpv6'),('UserIdGroupPairs','GroupId'),('PrefixListIds','PrefixListId')):
            for target in item.get(key,[]):result.add(base+(key,target[field]))
    return result


def profile_matches(instance, properties):
    expected = properties.get('IamInstanceProfile')
    actual = instance.get('IamInstanceProfile')
    if expected is None:
        return not actual
    return (isinstance(expected, str) and bool(actual)
            and actual.get('Arn', '').rsplit('/', 1)[-1] == expected)


def ssm_endpoint_matches(endpoint, properties):
    return (endpoint.get('State') == 'available'
            and endpoint.get('VpcEndpointType') == 'Interface'
            and endpoint.get('VpcId') == properties['VpcId']
            and endpoint.get('ServiceName') == properties['ServiceName']
            and endpoint.get('PrivateDnsEnabled') is True
            and set(endpoint.get('SubnetIds', [])) == set(properties['SubnetIds'])
            and {g['GroupId'] for g in endpoint.get('Groups', [])} == set(properties['SecurityGroupIds']))


def ssm_agent_matches(info, instance_id):
    try:
        version = tuple(int(x) for x in info.get('AgentVersion', '').split('.'))
    except ValueError:
        return False
    return (info.get('InstanceId') == instance_id and info.get('PingStatus') == 'Online'
            and info.get('PlatformType') == 'Linux' and version >= (3, 3, 40, 0))


def resolve(value,refs,phase):
    if isinstance(value,list):return [resolve(v,refs,phase) for v in value if v!={'Ref':'AWS::NoValue'}]
    if not isinstance(value,dict):return value
    if 'Ref' in value:return refs[value['Ref']]
    if 'Fn::If' in value:return resolve(value['Fn::If'][1 if phase=='bootstrap' else 2],refs,phase)
    if 'Fn::Join' in value:return value['Fn::Join'][0].join(resolve(value['Fn::Join'][1],refs,phase))
    if 'Fn::Sub' in value:return re.sub(r'\$\{([A-Za-z0-9]+)\}',lambda m:refs[m[1]],value['Fn::Sub'])
    return {k:resolve(v,refs,phase) for k,v in value.items()}


def expected_permissions(template,refs,phase):
    groups={name:{'ingress':[],'egress':[]} for name,r in template['Resources'].items() if r['Type']=='AWS::EC2::SecurityGroup'}
    def rule(p):
        if 'CidrIp' in p:
            target=('IpRanges',[{'CidrIp':p['CidrIp']}])
        else:
            target=('UserIdGroupPairs',[{'GroupId':p.get('SourceSecurityGroupId',p.get('DestinationSecurityGroupId'))}]) if 'SourceSecurityGroupId' in p or 'DestinationSecurityGroupId' in p else ('PrefixListIds',[{'PrefixListId':p['DestinationPrefixListId']}])
        return dict({k:p[k] for k in ('IpProtocol','FromPort','ToPort') if k in p},**{target[0]:target[1]})
    for name,r in template['Resources'].items():
        if r['Type']=='AWS::EC2::SecurityGroup':
            for field,direction in (('SecurityGroupIngress','ingress'),('SecurityGroupEgress','egress')):
                for value in r['Properties'].get(field,[]):
                    if 'Fn::If' in value and phase=='teaching':continue
                    groups[name][direction].append(rule(resolve(value,refs,phase)))
        elif r['Type'] in ('AWS::EC2::SecurityGroupIngress','AWS::EC2::SecurityGroupEgress'):
            group=r['Properties']['GroupId']['Ref'];direction='ingress' if r['Type'].endswith('Ingress') else 'egress'
            groups[group][direction].append(rule(resolve(r['Properties'],refs,phase)))
    return {k:{d:permissions(p) for d,p in v.items()} for k,v in groups.items()}


def collect(state_path,template_path,*,clients=None):
    # The Lambda setup adapter supplies bounded SDK clients. Existing CLI
    # callers keep the same behaviour; no signed artifact is edited in place.
    default_clients=clients is None
    if default_clients:
        import boto3
        clients={name:boto3.client(name,region_name='us-east-1') for name in ('sts','cloudformation','ec2')}
    state=json.loads(Path(state_path).read_text());template_bytes=Path(template_path).read_bytes();template=json.loads(template_bytes)
    expected_stack='jdu-web-'+state['lab_id'] if state.get('scope')=='student_payload_candidate' else 'jdu-web-five-node-probe-20261015'
    if state['account']!=clients['sts'].get_caller_identity()['Account'] or state['stack_name']!=expected_stack:raise ValueError('Wrong probe identity')
    if hashlib.sha256(template_bytes).hexdigest()!=state['template_sha256']:raise ValueError('Reviewed template changed')
    cfn=clients['cloudformation'];ec2=clients['ec2']
    stack=cfn.describe_stacks(StackName=state['stack_id'])['Stacks'][0]
    if stack['StackId']!=state['stack_id']:raise ValueError('Stack identity differs')
    params={v['ParameterKey']:v['ParameterValue'] for v in stack['Parameters']}
    if params['LabId']!=state['lab_id'] or params['DeploymentId']!=state['deployment_id']:raise ValueError('Deployment identity differs')
    resources=[]
    for page in cfn.get_paginator('list_stack_resources').paginate(StackName=state['stack_id']):resources.extend(page['StackResourceSummaries'])
    refs={r['LogicalResourceId']:r.get('PhysicalResourceId') for r in resources};refs.update(params)
    managed={role:refs[label+'Instance'] for role,label in NAMES.items()
        if refs.get(label+'Instance') and template['Resources'][label+'Instance']['Properties'].get('IamInstanceProfile')}
    ssm=(boto3.client('ssm',region_name='us-east-1') if default_clients else clients['ssm']) if managed else None
    infos={x['InstanceId']:x for x in ssm.describe_instance_information(Filters=[{'Key':'InstanceIds',
        'Values':list(managed.values())}])['InstanceInformationList']} if managed else {}
    report={'scope':'teacher_five_node_package_probe_not_class_acceptance','checked_at':datetime.now(timezone.utc).isoformat(),
        'stack_name':state['stack_name'],'stack_status':stack['StackStatus'],'deployment_id':state['deployment_id'],'phase':params['DeploymentPhase'],
        'resources':[{'logical_id':r['LogicalResourceId'],'status':r['ResourceStatus']} for r in resources],
        'nodes':{},'aws_checks':{},'class_ready':False,'student_release_ready':False}
    for role,label in NAMES.items():
        instance=refs.get(label+'Instance')
        if not instance or not instance.startswith('i-'):continue
        i=ec2.describe_instances(InstanceIds=[instance])['Reservations'][0]['Instances'][0]
        node={'instance_id':instance,'state':i['State']['Name'],'private_ip':i.get('PrivateIpAddress'),'public_ip':i.get('PublicIpAddress'),
            'type':i['InstanceType'],'root_volumes':[v['Ebs']['VolumeId'] for v in i.get('BlockDeviceMappings',[])]}
        console=ec2.get_console_output(InstanceId=instance,Latest=True).get('Output','');node.update(parse_console(console,role,instance,state));report['nodes'][role]=node
        report['aws_checks'][role+'_identity_and_access']=(i['ImageId']=='ami-0fa5967347d08d2df' and i.get('PrivateIpAddress')==IPS[role]
            and bool(i.get('PublicIpAddress'))==(role in ('bastion','web'))
            and profile_matches(i,template['Resources'][label+'Instance']['Properties'])
            and i['State']['Name']=='running' and i.get('KeyName')==params['StudentKeyName']
            and i['InstanceType']==params['BastionInstanceType' if role=='bastion' else 'DnsInstanceType' if role=='dns' else 'SmallInstanceType']
            and i['MetadataOptions']['HttpTokens']=='required' and {g['GroupId'] for g in i['SecurityGroups']}=={refs[label+'Sg'],refs['BootstrapSg']})
        vols=ec2.describe_volumes(VolumeIds=node['root_volumes'])['Volumes'] if node['root_volumes'] else []
        report['aws_checks'][role+'_encrypted_root_size']=len(vols)==1 and vols[0]['Size']==ROOTS[role] and vols[0]['Encrypted'] is True and vols[0]['VolumeType']=='gp3'
        if (role in managed and ssm_agent_matches(infos.get(instance,{}),instance)
                and report['aws_checks'][role+'_identity_and_access'] and (not node['role_result'] or not node['network_result'])):
            from ssm_node_evidence import collect as fresh_evidence
            try:
                fresh=fresh_evidence(ssm,state,role,instance,params['DeploymentPhase'])
                parsed=parse_console('JDU_NODE_ROLE_RESULT='+json.dumps(fresh['initial_role'])+'\nJDU_NODE_NETWORK_RESULT='
                    +json.dumps(fresh['network_result']),role,instance,state)
                if not parsed['role_result'] or not parsed['network_result']:raise ValueError('Invalid public SSM records')
                node.update(parsed,evidence_source='ssm_fresh_with_retained_initial_role',fresh_runtime_checks=fresh['fresh_checks'],
                    fresh_checked_at=fresh['fresh_checked_at'])
            except ValueError:
                node['failure_classes']=sorted(set(node['failure_classes']+['FreshSsmCheckUnavailable']))
    if all(refs.get(n) for n in ('BastionSg','WebSg','DnsSg','DbSg','RepoSg','BootstrapSg')):
        expected=expected_permissions(template,refs,params['DeploymentPhase'])
        groups={g['GroupId']:g for g in ec2.describe_security_groups(GroupIds=[refs[k] for k in expected])['SecurityGroups']}
        for name,wanted in expected.items():
            actual=groups[refs[name]]
            report['aws_checks'][name+'_exact_rules']=(permissions(actual['IpPermissions'])==wanted['ingress'] and permissions(actual['IpPermissionsEgress'])==wanted['egress'])
    if refs.get('S3Endpoint'):
        endpoint=ec2.describe_vpc_endpoints(VpcEndpointIds=[refs['S3Endpoint']])['VpcEndpoints'][0]
        wanted=resolve(template['Resources']['S3Endpoint']['Properties']['PolicyDocument'],refs,params['DeploymentPhase'])
        report['aws_checks']['s3_endpoint_policy']=json.loads(endpoint['PolicyDocument'])==wanted
        report['aws_checks']['s3_endpoint_routes']=set(endpoint['RouteTableIds'])=={refs['PublicRoutes'],refs['PrivateRoutes']}
    if all(refs.get(n) for n in ('PublicRoutes','PrivateRoutes','Vpc','InternetGateway','S3Endpoint')):
        tables={t['RouteTableId']:t for t in ec2.describe_route_tables(RouteTableIds=[refs['PublicRoutes'],refs['PrivateRoutes']])['RouteTables']}
        for side in ('Public','Private'):
            table=tables[refs[side+'Routes']]
            routes=table['Routes']
            expected_count=3 if side=='Public' else 2
            def allowed(route):
                if route.get('GatewayId')=='local':return route.get('DestinationCidrBlock')=='10.20.0.0/16'
                if route.get('DestinationPrefixListId')==params['S3PrefixListId']:return route.get('GatewayId')==refs['S3Endpoint']
                return side=='Public' and route.get('DestinationCidrBlock')=='0.0.0.0/0' and route.get('GatewayId')==refs['InternetGateway']
            report['aws_checks'][side.lower()+'_exact_routes']=len(routes)==expected_count and all(allowed(route) for route in routes)
        report['aws_checks']['no_nat_gateway']=not ec2.describe_nat_gateways(Filter=[{'Name':'vpc-id','Values':[refs['Vpc']]},{'Name':'state','Values':['pending','available','deleting']}])['NatGateways']
    expected_check_count=21
    if 'SsmSg' in template['Resources']:
        expected_check_count+=3+len(managed)  # exact endpoint SG, two endpoints, every managed agent
        for name in ('SsmEndpoint','SsmMessagesEndpoint'):
            matches=False
            if refs.get(name):
                endpoints=ec2.describe_vpc_endpoints(VpcEndpointIds=[refs[name]])['VpcEndpoints']
                properties=resolve(template['Resources'][name]['Properties'],refs,params['DeploymentPhase'])
                matches=len(endpoints)==1 and ssm_endpoint_matches(endpoints[0],properties)
            report['aws_checks'][name+'_exact_config']=matches
        for role,instance in managed.items():
            report['aws_checks'][role+'_ssm_online_current_agent']=ssm_agent_matches(infos.get(instance,{}),instance)
        report['ssm_session_accepted']=False  # Online alone never proves an interactive ssm-user session.
    report['all_five_role_checks_passed']=len(report['nodes'])==5 and all(n['role_result'] and all(n['role_result']['checks'].values()) for n in report['nodes'].values())
    report['all_aws_checks_passed']=len(report['nodes'])==5 and len(report['aws_checks'])==expected_check_count and all(report['aws_checks'].values())
    report['all_five_network_checks_passed']=len(report['nodes'])==5 and all(n['network_result'] and all(n['network_result']['checks'].values()) for n in report['nodes'].values())
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',required=True);p.add_argument('--template',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    report=collect(a.state,a.template)
    with Path(a.output).open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print('FIVE_NODE_INSPECTION='+json.dumps({k:report[k] for k in ('checked_at','stack_status','phase','all_five_role_checks_passed','all_aws_checks_passed','all_five_network_checks_passed','class_ready')}))
    for role,node in report['nodes'].items():print('NODE='+json.dumps({'role':role,'instance_id':node['instance_id'],'state':node['state'],'role_prepared':bool(node['role_result']),'network_phase':(node['network_result'] or {}).get('phase'),'failures':node['failure_classes']}))


if __name__=='__main__':
    try:main()
    except Exception as exc:print('PROBE_INSPECTION_FAILED='+type(exc).__name__);raise SystemExit(2)
