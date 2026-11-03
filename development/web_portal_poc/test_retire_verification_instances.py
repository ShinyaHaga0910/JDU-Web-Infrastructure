import copy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock,patch

import retire_verification_instances as r


class RetirementTests(unittest.TestCase):
    def setUp(self):
        self.sts=SimpleNamespace(get_caller_identity=lambda:{'Account':r.ACCOUNT})
        self.nodes=[{'InstanceId':iid,'State':{'Name':'running'},'RootDeviceName':'/dev/sda1',
            'Tags':[{'Key':'LabId','Value':r.LAB},{'Key':'DeploymentId','Value':r.DEPLOYMENT}],
            'BlockDeviceMappings':[{'DeviceName':'/dev/sda1','Ebs':{'VolumeId':vid,'DeleteOnTermination':True}}]}
            for iid,vid in r.ROOTS.items()]
        sizes=[32,16,16,16,16]
        self.ec2=Mock()
        self.ec2.describe_instances.return_value={'Reservations':[{'Instances':self.nodes}]}
        self.ec2.describe_volumes.return_value={'Volumes':[{'VolumeId':v,'Encrypted':True,'Size':s}
            for v,s in zip(r.ROOTS.values(),sizes)]}

    def test_wrong_account_stops_before_any_ec2_call(self):
        with self.assertRaises(ValueError):r.inventory(SimpleNamespace(get_caller_identity=lambda:{'Account':'0'*12}),self.ec2)
        self.assertEqual(self.ec2.mock_calls,[])

    def test_wrong_lab_or_root_retains_every_instance(self):
        for key in ('lab','root'):
            nodes=copy.deepcopy(self.nodes)
            if key=='lab':nodes[0]['Tags'][0]['Value']='another-lab'
            else:nodes[0]['BlockDeviceMappings'][0]['Ebs']['VolumeId']='vol-'+'0'*17
            self.ec2.describe_instances.return_value={'Reservations':[{'Instances':nodes}]}
            with self.assertRaises(ValueError):r.inventory(self.sts,self.ec2)
            self.ec2.terminate_instances.assert_not_called()

    def test_all_five_protections_required_before_termination_and_no_blind_retry(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(r.time,'sleep'):
            with self.assertRaises(ValueError):r.apply(self.sts,self.ec2,Path(folder))
            self.assertEqual(self.ec2.modify_instance_attribute.call_count,5)
            self.ec2.terminate_instances.assert_not_called()
            with self.assertRaises(FileExistsError):r.apply(self.sts,self.ec2,Path(folder))
            self.assertEqual(self.ec2.modify_instance_attribute.call_count,5)


if __name__=='__main__':unittest.main()
