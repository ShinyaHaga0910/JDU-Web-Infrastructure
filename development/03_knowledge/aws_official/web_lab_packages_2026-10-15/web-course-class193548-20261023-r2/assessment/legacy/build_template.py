"""Build a separate Web teacher API and fixed-IP TLS passthrough."""
import json
from pathlib import Path

ROUTES = ["GET /healthz", "GET /dashboard", "POST /api/web/admin/issue", "POST /api/web/register",
          "POST /api/web/submit", "POST /api/web/admin/session", "POST /api/web/student/session", "POST /api/web/link-email"]

def build():
    source = Path(__file__).with_name("progress_api.py").read_text(encoding="utf-8")
    nginx = """load_module /usr/lib/nginx/modules/ngx_stream_module.so;
user www-data;
worker_processes auto;
pid /run/nginx.pid;
error_log /var/log/nginx/error.log warn;
events { worker_connections 512; }
stream {
 resolver 169.254.169.253 valid=60s ipv6=off;
 map $ssl_preread_server_name $target {
  default "";
  ${ApiHost} ${ApiHost}:443;
 }
 limit_conn_zone $binary_remote_addr zone=per_ip:1m;
 server {
  listen 443;
  ssl_preread on;
  proxy_pass $target;
  proxy_connect_timeout 10s;
  proxy_timeout 30s;
  limit_conn per_ip 20;
 }
}
"""
    setup = """set -eu
export DEBIAN_FRONTEND=noninteractive
ready=0
for attempt in $(seq 1 30); do
 if apt-get update -o APT::Update::Error-Mode=any && apt-get install -y --no-install-recommends nginx libnginx-mod-stream; then ready=1; break; fi
 sleep 5
done
test "$ready" = 1
install -m 0644 /var/lib/jdu-web-teacher/nginx.conf /etc/nginx/nginx.conf
nginx -t
systemctl enable nginx
systemctl restart nginx
printf 'JDU_WEB_TEACHER_PROXY_READY\n' > /dev/ttyS0
"""
    cfg = {"package_update":False,"package_upgrade":False,"write_files":[
        {"path":"/var/lib/jdu-web-teacher/nginx.conf","permissions":"0600","content":nginx},
        {"path":"/var/lib/jdu-web-teacher/setup.sh","permissions":"0700","content":setup}],
        "runcmd":[["bash","/var/lib/jdu-web-teacher/setup.sh"]]}
    api_host = {"Fn::Sub":"${ProgressApi}.execute-api.${AWS::Region}.${AWS::URLSuffix}"}
    r = {
        "ProgressTable":{"Type":"AWS::DynamoDB::Table","DeletionPolicy":"Retain","UpdateReplacePolicy":"Retain","Properties":{
            "BillingMode":"PAY_PER_REQUEST","AttributeDefinitions":[{"AttributeName":k,"AttributeType":"S"} for k in ("pk","sk")],
            "KeySchema":[{"AttributeName":"pk","KeyType":"HASH"},{"AttributeName":"sk","KeyType":"RANGE"}],
            "SSESpecification":{"SSEEnabled":True},"TimeToLiveSpecification":{"AttributeName":"expires_at","Enabled":True}}},
        "ProgressApi":{"Type":"AWS::ApiGatewayV2::Api","Properties":{"ProtocolType":"HTTP","Name":{"Fn::Sub":"${AWS::StackName}-api"}}},
        "ProgressFunction":{"Type":"AWS::Lambda::Function","Properties":{
            "Runtime":"python3.12","Handler":"index.handler","Timeout":20,"MemorySize":256,
            "Role":{"Fn::Sub":"arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${LambdaExecutionRoleName}"},
            "Code":{"ZipFile":source},"Environment":{"Variables":{"TABLE_NAME":{"Ref":"ProgressTable"},
                "ADMIN_KEY_HASH":{"Ref":"AdminKeyHash"},"API_BASE_URL":{"Fn::Sub":"https://${ProgressApi}.execute-api.${AWS::Region}.${AWS::URLSuffix}"}}}}},
        "LogGroup":{"Type":"AWS::Logs::LogGroup","Properties":{"LogGroupName":{"Fn::Sub":"/aws/lambda/${ProgressFunction}"},"RetentionInDays":14}},
        "Integration":{"Type":"AWS::ApiGatewayV2::Integration","Properties":{"ApiId":{"Ref":"ProgressApi"},"IntegrationType":"AWS_PROXY",
            "IntegrationUri":{"Fn::GetAtt":["ProgressFunction","Arn"]},"PayloadFormatVersion":"2.0","TimeoutInMillis":20000}},
        "Stage":{"Type":"AWS::ApiGatewayV2::Stage","Properties":{"ApiId":{"Ref":"ProgressApi"},"StageName":"$default","AutoDeploy":True,
            "DefaultRouteSettings":{"ThrottlingBurstLimit":30,"ThrottlingRateLimit":10}}},
        "InvokePermission":{"Type":"AWS::Lambda::Permission","Properties":{"Action":"lambda:InvokeFunction","Principal":"apigateway.amazonaws.com",
            "FunctionName":{"Ref":"ProgressFunction"},"SourceArn":{"Fn::Sub":"arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:${ProgressApi}/*/*"}}},
        "TeacherSecurityGroup":{"Type":"AWS::EC2::SecurityGroup","Properties":{"VpcId":{"Ref":"VpcId"},"GroupDescription":"Teacher TLS to one fixed AWS API; no SSH",
            "SecurityGroupIngress":[{"IpProtocol":"tcp","FromPort":443,"ToPort":443,"CidrIp":"0.0.0.0/0"}],
            "SecurityGroupEgress":[{"IpProtocol":"tcp","FromPort":p,"ToPort":p,"CidrIp":"0.0.0.0/0"} for p in (80,443)]}},
        "TeacherInstance":{"Type":"AWS::EC2::Instance","Properties":{"ImageId":"ami-0fa5967347d08d2df","InstanceType":"t3a.small",
            "CreditSpecification":{"CPUCredits":"standard"},"MetadataOptions":{"HttpTokens":"required","HttpEndpoint":"enabled","HttpPutResponseHopLimit":1},
            "BlockDeviceMappings":[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":16,"VolumeType":"gp3","Encrypted":True,"DeleteOnTermination":True}}],
            "NetworkInterfaces":[{"DeviceIndex":"0","SubnetId":{"Ref":"SubnetId"},"AssociatePublicIpAddress":False,"GroupSet":[{"Ref":"TeacherSecurityGroup"}]}],
            "UserData":{"Fn::Base64":{"Fn::Sub":["#cloud-config\n"+json.dumps(cfg)+"\n",{"ApiHost":api_host}]}},
            "Tags":[{"Key":"Name","Value":"jdu-web-teacher-2026"}]}},
        "TeacherEip":{"Type":"AWS::EC2::EIP","Properties":{"Domain":"vpc"}},
        "TeacherEipAssociation":{"Type":"AWS::EC2::EIPAssociation","Properties":{"AllocationId":{"Fn::GetAtt":["TeacherEip","AllocationId"]},"InstanceId":{"Ref":"TeacherInstance"}}}}
    for i, route in enumerate(ROUTES):
        r[f"Route{i}"]={"Type":"AWS::ApiGatewayV2::Route","Properties":{"ApiId":{"Ref":"ProgressApi"},"RouteKey":route,"Target":{"Fn::Join":["/",["integrations",{"Ref":"Integration"}]]}}}
    return {"AWSTemplateFormatVersion":"2010-09-09","Description":"Separate Web teacher API and fixed-IP TLS passthrough. Linux progress unchanged.",
        "Parameters":{"VpcId":{"Type":"AWS::EC2::VPC::Id"},"SubnetId":{"Type":"AWS::EC2::Subnet::Id"},
            "LambdaExecutionRoleName":{"Type":"String","Default":"LabRole","AllowedPattern":"[A-Za-z0-9+=,.@_-]+"},
            "AdminKeyHash":{"Type":"String","NoEcho":True,"AllowedPattern":"[a-f0-9]{64}"}},
        "Resources":r,"Outputs":{
            "ApiBaseUrl":{"Value":{"Fn::Sub":"https://${ProgressApi}.execute-api.${AWS::Region}.${AWS::URLSuffix}"}},
            "FixedIngressIpv4":{"Value":{"Ref":"TeacherEip"}},"TeacherInstanceId":{"Value":{"Ref":"TeacherInstance"}},"TableName":{"Value":{"Ref":"ProgressTable"}}}}

if __name__=="__main__":
    p=Path(__file__).with_name("web-teacher.template.json")
    p.write_text(json.dumps(build(),indent=2)+"\n",encoding="utf-8",newline="\n")
    print(p.name)
