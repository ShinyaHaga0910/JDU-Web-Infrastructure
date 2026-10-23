import copy
import unittest

from make_five_node_template import make_template
from retry_teacher_probe import revision_template,check_changes,validate_repo_for_update,AMI


class RetryGuardTests(unittest.TestCase):
    def test_only_script_change_and_fresh_wait_handles(self):
        old=make_template();new=copy.deepcopy(old)
        body=new['Resources']['RepoInstance']['Properties']['UserData']['Fn::Base64']['Fn::Sub']
        new['Resources']['RepoInstance']['Properties']['UserData']['Fn::Base64']['Fn::Sub']=body.replace('node_loader.py','node_loader.py')+'\n'
        result=revision_template(old,new,'C3')
        self.assertNotIn('RepoHandle',result['Resources'])
        self.assertIn('RepoHandleC3',result['Resources'])
        self.assertIn('${RepoHandleC3}',result['Resources']['RepoInstance']['Properties']['UserData']['Fn::Base64']['Fn::Sub'])
        self.assertIn('RepoReadyC3',result['Resources']['BastionInstance']['DependsOn'])

    def test_network_access_change_rejected(self):
        old=make_template();new=copy.deepcopy(old)
        new['Resources']['BootstrapSg']['Properties']['SecurityGroupIngress'].append({'IpProtocol':'-1','CidrIp':'0.0.0.0/0'})
        with self.assertRaises(ValueError):revision_template(old,new,'C3')

    def test_new_resource_or_instance_change_rejected(self):
        old=make_template()
        for field,value in (('InstanceType','t3a.large'),('ImageId','ami-00000000000000000')):
            new=copy.deepcopy(old);new['Resources']['RepoInstance']['Properties'][field]=value
            with self.assertRaises(ValueError):revision_template(old,new,'C3')
        new=copy.deepcopy(old);new['Resources']['Extra']={'Type':'AWS::EC2::Instance'}
        with self.assertRaises(ValueError):revision_template(old,new,'C3')

    def change(self,name,action='Modify',kind='AWS::EC2::Instance',replacement='False'):
        return {'ResourceChange':{'LogicalResourceId':name,'Action':action,'ResourceType':kind,'Replacement':replacement}}

    def test_instance_delete_or_replacement_rejected(self):
        for change in (self.change('RepoInstance','Remove'),self.change('RepoInstance',replacement='True'),self.change('RepoInstance',replacement='Conditional')):
            with self.assertRaises(ValueError):check_changes([change],'C3')

    def test_existing_role_update_or_other_network_change_rejected(self):
        for change in (self.change('BastionInstance'),self.change('BootstrapSg',kind='AWS::EC2::SecurityGroup')):
            with self.assertRaises(ValueError):check_changes([self.change('RepoInstance'),change],'C3')

    def test_bounded_changes_allowed(self):
        changes=[self.change('RepoInstance'),self.change('WebInstance','Add'),
            self.change('RepoHandle','Remove','AWS::CloudFormation::WaitConditionHandle'),
            self.change('RepoHandleC3','Add','AWS::CloudFormation::WaitConditionHandle'),
            self.change('S3Endpoint','Modify','AWS::EC2::VPCEndpoint')]
        self.assertEqual(len(check_changes(changes,'C3')),5)

    def test_conditional_userdata_requires_live_ebs_and_exact_details(self):
        change=self.change('RepoInstance',replacement='Conditional')
        change['ResourceChange'].update(Scope=['Properties'],Details=[{'Target':{
            'Attribute':'Properties','Name':'UserData','RequiresRecreation':'Conditionally'}}])
        with self.assertRaises(ValueError):check_changes([change],'C3')
        self.assertEqual(len(check_changes([change],'C3',repo_ebs_verified=True)),1)
        for key,value in [('Name','ImageId'),('RequiresRecreation','Always'),('Attribute','Metadata')]:
            bad=copy.deepcopy(change);bad['ResourceChange']['Details'][0]['Target'][key]=value
            with self.assertRaises(ValueError):check_changes([bad],'C3',repo_ebs_verified=True)
        for field,value in [('Details',[]),('Scope',['Properties','Tags'])]:
            bad=copy.deepcopy(change);bad['ResourceChange'][field]=value
            with self.assertRaises(ValueError):check_changes([bad],'C3',repo_ebs_verified=True)

    def test_ebs_identity_requires_original_instance_image_ip_and_root(self):
        state={'source_instance':'i-0123456789abcdef0','source_volume':'vol-0123456789abcdef0'}
        node={'InstanceId':state['source_instance'],'RootDeviceType':'ebs','ImageId':AMI,
            'PrivateIpAddress':'10.20.2.30','RootDeviceName':'/dev/sda1','State':{'Name':'stopped'},
            'BlockDeviceMappings':[{'DeviceName':'/dev/sda1','Ebs':{'VolumeId':state['source_volume']}}]}
        validate_repo_for_update(node,state)
        for field,value in [('InstanceId','other'),('RootDeviceType','instance-store'),('ImageId','other'),
                            ('PrivateIpAddress','10.20.2.31'),('BlockDeviceMappings',[])]:
            bad=copy.deepcopy(node);bad[field]=value
            with self.assertRaises(ValueError):validate_repo_for_update(bad,state)


if __name__=='__main__':unittest.main()
