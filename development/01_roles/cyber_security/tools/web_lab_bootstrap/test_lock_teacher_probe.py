import copy
import unittest
from lock_teacher_probe import require_baseline,validate_change_set


class ClosureTests(unittest.TestCase):
    def change(self):
        return {'Status':'CREATE_COMPLETE','ExecutionStatus':'AVAILABLE','Changes':[{'ResourceChange':{'LogicalResourceId':n,'ResourceType':t,'Action':'Modify','Replacement':'False'}} for n,t in [('BootstrapSg','AWS::EC2::SecurityGroup'),('S3Endpoint','AWS::EC2::VPCEndpoint')]]}

    def test_only_two_in_place_changes_pass(self):
        self.assertEqual(len(validate_change_set(self.change())),2)

    def test_any_instance_change_rejected(self):
        c=self.change();c['Changes'].append({'ResourceChange':{'LogicalResourceId':'RepoInstance','ResourceType':'AWS::EC2::Instance','Action':'Modify','Replacement':'False'}})
        with self.assertRaises(ValueError):validate_change_set(c)

    def test_replacement_and_delete_rejected(self):
        for field,value in [('Replacement','True'),('Replacement','Conditional'),('Action','Remove')]:
            c=self.change();c['Changes'][0]['ResourceChange'][field]=value
            with self.assertRaises(ValueError):validate_change_set(c)

    def test_missing_or_duplicate_change_rejected(self):
        for items in (self.change()['Changes'][:1],[self.change()['Changes'][0]]*2):
            c=self.change();c['Changes']=items
            with self.assertRaises(ValueError):validate_change_set(c)

    def baseline(self):
        return {'stack_status':'CREATE_COMPLETE','phase':'bootstrap','all_five_role_checks_passed':True,
            'all_aws_checks_passed':True,'all_five_network_checks_passed':True,
            'nodes':{r:{'network_result':{'phase':'BOOTSTRAP_OBSERVED','s3_tcp_reachable':True,'s3_bootstrap_reachable_seen':True}} for r in ('bastion','web','dns','db','repo')}}

    def test_all_five_live_baselines_required(self):
        require_baseline(self.baseline())
        b=self.baseline();b['nodes']['dns']['network_result']['s3_tcp_reachable']=False
        with self.assertRaises(ValueError):require_baseline(b)
        b=self.baseline();b['stack_status']='CREATE_FAILED'
        with self.assertRaises(ValueError):require_baseline(b)


if __name__=='__main__':unittest.main()
