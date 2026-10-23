import copy
import unittest
from prepare_c4_transition import validate_targets


class TransitionTargetGuards(unittest.TestCase):
    def fixture(self):
        plan=dict(lab_id='fixture',deployment_id='fixture-deployment',nodes={r:dict(instance_id='i-'+str(n)*17,root_volumes=['vol-'+str(n)*17])
            for n,r in enumerate(['bastion','web','dns','db','repo'],1)})
        instances=[dict(InstanceId=n['instance_id'],State=dict(Name='running'),Tags=[dict(Key='LabId',Value=plan['lab_id']),dict(Key='DeploymentId',Value=plan['deployment_id'])],
            BlockDeviceMappings=[dict(Ebs=dict(VolumeId=n['root_volumes'][0]))]) for n in plan['nodes'].values()]
        return plan,instances
    def test_only_exact_reviewed_five_original_roots_accepted(self):
        plan,instances=self.fixture();validate_targets(instances,plan)
        for alteration in ('instance','extra_volume','deployment'):
            changed=copy.deepcopy(instances)
            if alteration=='instance':changed[0]['InstanceId']='i-'+'9'*17
            elif alteration=='extra_volume':changed[0]['BlockDeviceMappings'].append(dict(Ebs=dict(VolumeId='vol-'+'9'*17)))
            else:changed[0]['Tags'][1]['Value']='other'
            with self.subTest(alteration=alteration),self.assertRaises(ValueError):validate_targets(changed,plan)


if __name__=='__main__':unittest.main()
