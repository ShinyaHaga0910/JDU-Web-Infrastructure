import copy
import unittest
from inspect_teacher_probe import profile_matches, ssm_endpoint_matches, ssm_agent_matches


class SsmEvidenceTests(unittest.TestCase):
    def test_profile_only_allowed_when_explicit_in_reviewed_template(self):
        instance={'IamInstanceProfile':{'Arn':'arn:aws:iam::123456789012:instance-profile/LabInstanceProfile'}}
        self.assertFalse(profile_matches(instance,{}))
        self.assertTrue(profile_matches({},{}))
        self.assertTrue(profile_matches(instance,{'IamInstanceProfile':'LabInstanceProfile'}))
        self.assertFalse(profile_matches(instance,{'IamInstanceProfile':'OtherProfile'}))
        self.assertFalse(profile_matches({}, {'IamInstanceProfile':'LabInstanceProfile'}))

    def test_endpoint_requires_exact_private_path(self):
        p={'VpcId':'vpc-1','ServiceName':'com.amazonaws.us-east-1.ssm',
           'SubnetIds':['subnet-1'],'SecurityGroupIds':['sg-1']}
        endpoint={'State':'available','VpcEndpointType':'Interface','VpcId':'vpc-1',
                  'ServiceName':p['ServiceName'],'PrivateDnsEnabled':True,
                  'SubnetIds':['subnet-1'],'Groups':[{'GroupId':'sg-1'}]}
        self.assertTrue(ssm_endpoint_matches(endpoint,p))
        for field,value in [('State','pending'),('PrivateDnsEnabled',False),
                            ('Groups',[{'GroupId':'sg-1'},{'GroupId':'sg-2'}]),
                            ('SubnetIds',['subnet-2']),('ServiceName','other')]:
            bad=copy.deepcopy(endpoint);bad[field]=value
            self.assertFalse(ssm_endpoint_matches(bad,p))

    def test_agent_must_be_online_correct_identity_and_modern_transport(self):
        info={'InstanceId':'i-bastion','PingStatus':'Online','PlatformType':'Linux','AgentVersion':'3.3.40.0'}
        self.assertTrue(ssm_agent_matches(info,'i-bastion'))
        for field,value in [('InstanceId','i-other'),('PingStatus','ConnectionLost'),
                            ('AgentVersion','3.2.999.0'),('AgentVersion','unknown')]:
            bad=dict(info);bad[field]=value
            self.assertFalse(ssm_agent_matches(bad,'i-bastion'))


if __name__=='__main__':unittest.main()
