"""Teacher-only isolated VPC / one private repo acceptance stack."""
import base64
import gzip
import json
from pathlib import Path

HERE=Path(__file__).parent


def make_template():
    files=[]
    for name in ('offline_repo_loader.py','probe_offline_repo.py'):
        files.append({'path':'/var/lib/jdu-repo-acceptance/'+name,'permissions':'0644','encoding':'gz+b64',
            'content':base64.b64encode(gzip.compress((HERE/name).read_bytes(),mtime=0)).decode()})
    public=(HERE.parents[3]/'03_knowledge/aws_official/web_lab_packages_2026-10-15/package-signing-public.asc').read_text()
    files.append({'path':'/var/lib/jdu-repo-acceptance/archive-key.asc','permissions':'0644','content':public})
    config={'bundle_url':'${BundleUrl}','bundle_sha256':'${BundleSha256}',
        'fingerprint':'65EC6784750CCFA703BA7179519284E45155EC2A','release_id':'web-2026-10-r1',
        'teacher_ipv4':'44.216.176.215','signal_url':'${RepoHandle}'}
    files.append({'path':'/var/lib/jdu-repo-acceptance/private.json','permissions':'0600','content':json.dumps(config)})
    cloud={'package_update':False,'package_upgrade':False,'write_files':files,
        'bootcmd':[['shutdown','-P','+75']],
        'runcmd':[['bash','-c','set -o pipefail; timeout 3300 python3 /var/lib/jdu-repo-acceptance/offline_repo_loader.py 2>&1 | tee /var/log/jdu-offline-repo.log > /dev/ttyS0']],
        'power_state':{'mode':'poweroff','delay':10,'timeout':60,'condition':True}}
    userdata='#cloud-config\n'+json.dumps(cloud,separators=(',',':'))+'\n'
    if len(userdata.encode())>=16384:
        raise ValueError('Offline repo UserData exceeds 16 KiB')
    resources={
        'ProbeVpc':{'Type':'AWS::EC2::VPC','Properties':{'CidrBlock':'10.20.0.0/16','EnableDnsSupport':True,'EnableDnsHostnames':True,
            'Tags':[{'Key':'Name','Value':'jdu-web-offline-repo-probe-only'}]}},
        'ProbeSubnet':{'Type':'AWS::EC2::Subnet','Properties':{'VpcId':{'Ref':'ProbeVpc'},'CidrBlock':'10.20.2.0/24',
            'AvailabilityZone':{'Ref':'AvailabilityZone'},'MapPublicIpOnLaunch':False}},
        'ProbeRouteTable':{'Type':'AWS::EC2::RouteTable','Properties':{'VpcId':{'Ref':'ProbeVpc'}}},
        'ProbeRouteAssociation':{'Type':'AWS::EC2::SubnetRouteTableAssociation','Properties':{
            'SubnetId':{'Ref':'ProbeSubnet'},'RouteTableId':{'Ref':'ProbeRouteTable'}}},
        'S3Endpoint':{'Type':'AWS::EC2::VPCEndpoint','Properties':{'VpcId':{'Ref':'ProbeVpc'},'VpcEndpointType':'Gateway',
            'ServiceName':{'Fn::Sub':'com.amazonaws.${AWS::Region}.s3'},'RouteTableIds':[{'Ref':'ProbeRouteTable'}],
            'PolicyDocument':{'Version':'2012-10-17','Statement':[
                {'Effect':'Allow','Principal':'*','Action':'s3:GetObject','Resource':{'Fn::Sub':'arn:aws:s3:::${CaptureBucket}/teacher-candidates/web-2026-10-r1/*'}},
                {'Effect':'Allow','Principal':'*','Action':'s3:PutObject','Resource':'arn:aws:s3:::cloudformation-waitcondition-us-east-1/*'}]}}},
        'ProbeSecurityGroup':{'Type':'AWS::EC2::SecurityGroup','Properties':{'VpcId':{'Ref':'ProbeVpc'},
            'GroupDescription':'Teacher private repo probe; no inbound, S3 HTTPS egress only',
            'SecurityGroupIngress':[],'SecurityGroupEgress':[{'IpProtocol':'tcp','FromPort':443,'ToPort':443,
                'DestinationPrefixListId':{'Ref':'S3PrefixListId'}}]}},
        'RepoHandle':{'Type':'AWS::CloudFormation::WaitConditionHandle'},
        'ProbeInstance':{'Type':'AWS::EC2::Instance','DependsOn':['S3Endpoint','ProbeRouteAssociation'],
            'Properties':{'ImageId':'ami-0fa5967347d08d2df','InstanceType':'t3a.small',
                'CreditSpecification':{'CPUCredits':'standard'},'MetadataOptions':{'HttpTokens':'required','HttpPutResponseHopLimit':1},
                'InstanceInitiatedShutdownBehavior':'stop','BlockDeviceMappings':[{'DeviceName':'/dev/sda1',
                    'Ebs':{'VolumeSize':32,'VolumeType':'gp3','Encrypted':True,'DeleteOnTermination':True}}],
                'NetworkInterfaces':[{'DeviceIndex':'0','SubnetId':{'Ref':'ProbeSubnet'},'PrivateIpAddress':'10.20.2.30',
                    'AssociatePublicIpAddress':False,'GroupSet':[{'Ref':'ProbeSecurityGroup'}]}],
                'UserData':{'Fn::Base64':{'Fn::Sub':userdata}},'Tags':[{'Key':'Name','Value':'jdu-web-offline-repo-probe-20261015'}]}},
        'RepoReady':{'Type':'AWS::CloudFormation::WaitCondition','DependsOn':'ProbeInstance','Properties':{
            'Handle':{'Ref':'RepoHandle'},'Timeout':'3600','Count':1}}}
    return {'AWSTemplateFormatVersion':'2010-09-09','Description':'Teacher-only one private repo package candidate. New isolated VPC, no Internet gateway/NAT/public IP or incoming access. Not a five-node student template.',
        'Parameters':{'AvailabilityZone':{'Type':'AWS::EC2::AvailabilityZone::Name','Default':'us-east-1a'},
            'S3PrefixListId':{'Type':'String','AllowedPattern':'^pl-[0-9a-f]+$'},
            'CaptureBucket':{'Type':'String','AllowedPattern':'^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$'},
            'BundleUrl':{'Type':'String','NoEcho':True,'AllowedPattern':'^https://[^\\s"\\\\]+\\.amazonaws\\.com/[^\\s"\\\\]+$'},
            'BundleSha256':{'Type':'String','AllowedPattern':'^[0-9a-f]{64}$'}},
        'Resources':resources,'Outputs':{name:{'Value':{'Ref':resource}} for name,resource in
            [('ProbeInstanceId','ProbeInstance'),('VpcId','ProbeVpc'),('SubnetId','ProbeSubnet'),('S3EndpointId','S3Endpoint'),('SecurityGroupId','ProbeSecurityGroup'),('RouteTableId','ProbeRouteTable')]}}


if __name__=='__main__':
    template=make_template(); output=HERE/'offline-repo-probe.template.json'
    output.write_text(json.dumps(template,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'file':output.name,'user_data_bytes':len(template['Resources']['ProbeInstance']['Properties']['UserData']['Fn::Base64']['Fn::Sub'].encode()),'template_bytes':output.stat().st_size}))
