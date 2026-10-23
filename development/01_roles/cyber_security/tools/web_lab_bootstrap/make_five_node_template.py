"""Generate the five-node network and one-time role preparation template.

Package-only scope is for explicit teacher probes. Student releases use the
student_payload scope and require the outer signed deployment manifest.
"""
import base64
import gzip
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).parent
PROJECT=HERE.parents[3]
NAMES={'bastion':'Bastion','web':'Web','dns':'Dns','db':'Db','repo':'Repo'}
IPS={'bastion':'10.20.1.10','web':'10.20.1.20','dns':'10.20.2.10','db':'10.20.2.20','repo':'10.20.2.30'}
ROOTS={'bastion':24,'web':16,'dns':8,'db':16,'repo':32}
FINGERPRINT='65EC6784750CCFA703BA7179519284E45155EC2A'


def ref(name): return {'Ref':name}
def sub(value): return {'Fn::Sub':value}


def make_template():
    r={}; rules=[]
    r['Vpc']={'Type':'AWS::EC2::VPC','Properties':{'CidrBlock':'10.20.0.0/16','EnableDnsSupport':True,'EnableDnsHostnames':True}}
    r['InternetGateway']={'Type':'AWS::EC2::InternetGateway'}
    r['GatewayAttachment']={'Type':'AWS::EC2::VPCGatewayAttachment','Properties':{'VpcId':ref('Vpc'),'InternetGatewayId':ref('InternetGateway')}}
    for name,cidr,public in [('Public','10.20.1.0/24',True),('Private','10.20.2.0/24',False)]:
        r[name+'Subnet']={'Type':'AWS::EC2::Subnet','Properties':{'VpcId':ref('Vpc'),'CidrBlock':cidr,'AvailabilityZone':ref('AvailabilityZone'),'MapPublicIpOnLaunch':public}}
        r[name+'Routes']={'Type':'AWS::EC2::RouteTable','Properties':{'VpcId':ref('Vpc')}}
        r[name+'RouteAssociation']={'Type':'AWS::EC2::SubnetRouteTableAssociation','Properties':{'SubnetId':ref(name+'Subnet'),'RouteTableId':ref(name+'Routes')}}
    r['PublicDefaultRoute']={'Type':'AWS::EC2::Route','DependsOn':'GatewayAttachment','Properties':{'RouteTableId':ref('PublicRoutes'),'DestinationCidrBlock':'0.0.0.0/0','GatewayId':ref('InternetGateway')}}
    cidrs=json.loads((PROJECT/'03_knowledge/network/2026-10-15_isp_rdp_allowlist/rdp_ingress_ip_permissions.json').read_text(encoding='utf-8'))[0]['IpRanges']
    if len(cidrs)!=50 or len({c['CidrIp'] for c in cidrs})!=50: raise ValueError('Expected 50 reviewed RDP CIDRs')
    marker={'IpProtocol':'-1','CidrIp':'127.0.0.1/32'}
    for role,label in NAMES.items():
        incoming=[{'IpProtocol':'tcp','FromPort':3389,'ToPort':3389,'CidrIp':c['CidrIp'],'Description':c['Description']} for c in cidrs] if role=='bastion' else []
        r[label+'Sg']={'Type':'AWS::EC2::SecurityGroup','Properties':{'VpcId':ref('Vpc'),'GroupDescription':'Web Lab '+role+' least-privilege traffic','SecurityGroupIngress':incoming,'SecurityGroupEgress':[marker]}}
    # Inline conditional egress avoids conditional DependsOn affecting EC2s.
    # All five retain their SG membership; teaching changes only this SG/policy.
    r['BootstrapSg']={'Type':'AWS::EC2::SecurityGroup','Properties':{'VpcId':ref('Vpc'),'GroupDescription':'Bootstrap S3 only; no incoming access',
        'SecurityGroupIngress':[],'SecurityGroupEgress':[marker,{'Fn::If':['IsBootstrap',{'IpProtocol':'tcp','FromPort':443,'ToPort':443,'DestinationPrefixListId':ref('S3PrefixListId')},ref('AWS::NoValue')]}]}}
    def ingress(name,destination,source,protocol,port,cidr=None):
        properties={'GroupId':ref(NAMES[destination]+'Sg'),'IpProtocol':protocol,'FromPort':port,'ToPort':port}
        properties.update({'CidrIp':cidr} if cidr else {'SourceSecurityGroupId':ref(NAMES[source]+'Sg')})
        r[name]={'Type':'AWS::EC2::SecurityGroupIngress','Properties':properties}; rules.append(name)
    def egress(name,source,destination,protocol,port,cidr=None):
        properties={'GroupId':ref(NAMES[source]+'Sg'),'IpProtocol':protocol,'FromPort':port,'ToPort':port}
        properties.update({'CidrIp':cidr} if cidr else {'DestinationSecurityGroupId':ref(NAMES[destination]+'Sg')})
        r[name]={'Type':'AWS::EC2::SecurityGroupEgress','Properties':properties}; rules.append(name)
    ingress('PublicHttp','web',None,'tcp',80,'0.0.0.0/0')
    for role in ('web','dns','db','repo'):
        ingress(NAMES[role]+'Ssh',role,'bastion','tcp',22)
        egress('BastionSsh'+NAMES[role],'bastion',role,'tcp',22)
    for source in ('bastion','web'):
        for protocol in ('tcp','udp'):
            ingress(NAMES[source]+protocol+'DnsIn','dns',source,protocol,53)
            egress(NAMES[source]+protocol+'DnsOut',source,'dns',protocol,53)
    for source in ('bastion','web','dns','db'):
        ingress(NAMES[source]+'RepoIn','repo',source,'tcp',80)
        egress(NAMES[source]+'RepoOut',source,'repo','tcp',80)
    ingress('BastionAdmin','web','bastion','tcp',8080)
    for port in (80,8080): egress('BastionWeb'+str(port),'bastion','web','tcp',port)
    ingress('WebDbIn','db','web','tcp',5432); egress('WebDbOut','web','db','tcp',5432)
    egress('BastionGrading','bastion',None,'tcp',443,{'Fn::Join':['',[ref('GradingIpv4'),'/32']]})
    bootstrap_policy={'Version':'2012-10-17','Statement':[
        {'Effect':'Allow','Principal':'*','Action':'s3:GetObject','Resource':sub('arn:aws:s3:::${BootstrapBucket}/${BootstrapPrefix}*'),'Condition':{'IpAddress':{'aws:VpcSourceIp':'10.20.2.30/32'}}},
        {'Effect':'Allow','Principal':'*','Action':'s3:PutObject','Resource':'arn:aws:s3:::cloudformation-waitcondition-us-east-1/*','Condition':{'IpAddress':{'aws:VpcSourceIp':[ip+'/32' for ip in IPS.values()]}}}]}
    teaching_policy={'Version':'2012-10-17','Statement':[{'Effect':'Deny','Principal':'*','Action':'s3:*','Resource':'*'}]}
    r['S3Endpoint']={'Type':'AWS::EC2::VPCEndpoint','Properties':{'VpcId':ref('Vpc'),'VpcEndpointType':'Gateway','ServiceName':'com.amazonaws.us-east-1.s3',
        'RouteTableIds':[ref('PublicRoutes'),ref('PrivateRoutes')],'PolicyDocument':{'Fn::If':['IsBootstrap',bootstrap_policy,teaching_policy]}}}
    for name in ('Repo','AllNodes'): r[name+'Handle']={'Type':'AWS::CloudFormation::WaitConditionHandle'}
    pins={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('node_bootstrap.py','payload_runtime.py','release_validation.py','network_probe.py')}
    public=(PROJECT/'03_knowledge/aws_official/web_lab_packages_2026-10-15/package-signing-public.asc').read_text()
    loader=base64.b64encode(gzip.compress((HERE/'node_loader.py').read_bytes(),mtime=0)).decode()
    for role,label in NAMES.items():
        config={'schema_version':1,'lab_id':'${LabId}','deployment_id':'${DeploymentId}','release_id':'${ReleaseId}','role':role,
            'fingerprint':FINGERPRINT,'expected_scope':'${ExpectedPayloadScope}','script_pins':pins,
            'student_public_key':'${StudentPublicKey}','grading_api_url':'${GradingApiUrl}','grading_ipv4':'${GradingIpv4}',
            's3_probe_ipv4':'${S3ProbeIpv4}','direct_api_probe_ipv4':'${DirectApiProbeIpv4}',
            'signal_url':'${RepoHandle}' if role=='repo' else '${AllNodesHandle}'}
        if role=='repo': config.update(bundle_url='${BundleUrl}',bundle_sha256='${BundleSha256}')
        if role=='bastion':
            config['rdp_hash']='${RdpPasswordHash}'
            config['peer_instances']={k:'${'+v+'Instance}' for k,v in NAMES.items() if k!='bastion'}
        cloud={'package_update':False,'package_upgrade':False,'write_files':[
            {'path':'/var/lib/jdu-web/initial/private.json','permissions':'0600','content':json.dumps(config)},
            {'path':'/var/lib/jdu-web/initial/archive-key.asc','permissions':'0644','content':public},
            {'path':'/var/lib/jdu-web/initial/node_loader.py','permissions':'0644','encoding':'gz+b64','content':loader}],
            'runcmd':[['bash','-c','set -o pipefail; timeout 2400 python3 /var/lib/jdu-web/initial/node_loader.py 2>&1 | tee /var/log/jdu-web-bootstrap.log > /dev/ttyS0']]}
        user='#cloud-config\n'+json.dumps(cloud,separators=(',',':'))+'\n'
        if len(user.encode())>=16384: raise ValueError('Role UserData exceeds 16 KiB')
        properties={'ImageId':'ami-0fa5967347d08d2df','InstanceType':ref('BastionInstanceType' if role=='bastion' else 'DnsInstanceType' if role=='dns' else 'SmallInstanceType'),
            'SubnetId':ref('PublicSubnet' if role in ('bastion','web') else 'PrivateSubnet'),'PrivateIpAddress':IPS[role],
            'SecurityGroupIds':[ref(label+'Sg'),ref('BootstrapSg')],'KeyName':ref('StudentKeyName'),
            'CreditSpecification':{'CPUCredits':'standard'},'MetadataOptions':{'HttpTokens':'required','HttpPutResponseHopLimit':1},
            'InstanceInitiatedShutdownBehavior':'stop','BlockDeviceMappings':[{'DeviceName':'/dev/sda1','Ebs':{'VolumeSize':ROOTS[role],'VolumeType':'gp3','Encrypted':True,'DeleteOnTermination':True}}],
            'UserData':{'Fn::Base64':sub(user)},'Tags':[{'Key':'Name','Value':sub('${AWS::StackName}-'+role)},{'Key':'LabId','Value':ref('LabId')},{'Key':'DeploymentId','Value':ref('DeploymentId')}]}
        dependencies=['S3Endpoint','PublicDefaultRoute','PublicRouteAssociation','PrivateRouteAssociation',*rules]
        if role!='repo': dependencies.append('RepoReady')
        r[label+'Instance']={'Type':'AWS::EC2::Instance','DependsOn':dependencies,'Properties':properties}
    r['RepoReady']={'Type':'AWS::CloudFormation::WaitCondition','DependsOn':'RepoInstance','Properties':{'Handle':ref('RepoHandle'),'Timeout':'1800','Count':1}}
    r['AllNodesReady']={'Type':'AWS::CloudFormation::WaitCondition','DependsOn':[NAMES[n]+'Instance' for n in NAMES if n!='repo'],
        'Properties':{'Handle':ref('AllNodesHandle'),'Timeout':'2700','Count':4}}
    parameters={'AvailabilityZone':{'Type':'AWS::EC2::AvailabilityZone::Name'},'StudentKeyName':{'Type':'AWS::EC2::KeyPair::KeyName'},
        'StudentPublicKey':{'Type':'String','AllowedPattern':'^ssh-(rsa|ed25519) [A-Za-z0-9+/=]+$'},
        'RdpPasswordHash':{'Type':'String','NoEcho':True,'AllowedPattern':r'^\$6\$[A-Za-z0-9./]{1,16}\$[A-Za-z0-9./]{86}$'},
        'LabId':{'Type':'String','AllowedPattern':'^[a-z0-9][a-z0-9-]{2,31}$'},'DeploymentId':{'Type':'String','AllowedPattern':'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'},
        'ReleaseId':{'Type':'String','Default':'web-2026-10-r1','AllowedPattern':'^web-[0-9]{4}-[0-9]{2}-r[1-9][0-9]*$'},
        'DeploymentPhase':{'Type':'String','Default':'bootstrap','AllowedValues':['bootstrap','teaching']},
        'ExpectedPayloadScope':{'Type':'String','Default':'student_payload','AllowedValues':['student_payload','package_only_candidate']},
        'S3PrefixListId':{'Type':'String','AllowedPattern':'^pl-[0-9a-f]+$'},'BootstrapBucket':{'Type':'String'},'BootstrapPrefix':{'Type':'String','AllowedPattern':'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_/-]+/$'},
        'BundleUrl':{'Type':'String','NoEcho':True,'AllowedPattern':'^https://[^\\s"\\\\]+\\.amazonaws\\.com/[^\\s"\\\\]+$'},'BundleSha256':{'Type':'String','AllowedPattern':'^[0-9a-f]{64}$'},
        'GradingApiUrl':{'Type':'String','Default':'https://7eg7nm5oe2.execute-api.us-east-1.amazonaws.com','AllowedPattern':'^https://[a-z0-9]+\\.execute-api\\.us-east-1\\.amazonaws\\.com$'},
        'GradingIpv4':{'Type':'String','Default':'44.216.176.215','AllowedPattern':'^[0-9.]+$'}}
    for name in ('S3ProbeIpv4','DirectApiProbeIpv4'): parameters[name]={'Type':'String','AllowedPattern':'^[0-9.]+$'}
    for name,suffix in [('BastionInstanceType','medium'),('SmallInstanceType','small'),('DnsInstanceType','micro')]:
        parameters[name]={'Type':'String','Default':'t3a.'+suffix,'AllowedPattern':'^t[0-9][a-z0-9]*\\.'+suffix+'$'}
    output={label+'InstanceId':{'Value':ref(label+'Instance')} for label in NAMES.values()}
    output.update({label+'PublicIp':{'Value':{'Fn::GetAtt':[label+'Instance','PublicIp']}} for label in ('Bastion','Web')})
    output.update({name:{'Value':ref(name)} for name in ('Vpc','S3Endpoint','BootstrapSg','PublicRoutes','PrivateRoutes')})
    return {'AWSTemplateFormatVersion':'2010-09-09','Description':'Five-node Web Lab foundation; package-only candidates are teacher probes, not accepted student releases.',
        'Parameters':parameters,'Conditions':{'IsBootstrap':{'Fn::Equals':[ref('DeploymentPhase'),'bootstrap']}},'Resources':r,'Outputs':output}


if __name__=='__main__':
    data=make_template(); path=HERE/'web-lab.template.json'
    path.write_text(json.dumps(data,separators=(',',':'))+'\n',encoding='utf-8',newline='\n')
    if path.stat().st_size>51200: raise ValueError('Template exceeds direct CloudFormation limit')
    print(json.dumps({'file':path.name,'bytes':path.stat().st_size,'resources':len(data['Resources'])}))
