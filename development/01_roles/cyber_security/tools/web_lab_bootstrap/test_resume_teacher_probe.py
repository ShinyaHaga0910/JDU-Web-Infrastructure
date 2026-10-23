import copy
import unittest
from resume_teacher_probe import validate_changes,ROLES,validate_report


class ResumeGuardTests(unittest.TestCase):
    def change(self):
        return {'Status':'CREATE_COMPLETE','ExecutionStatus':'AVAILABLE','Changes':[
            {'ResourceChange':{'LogicalResourceId':name,'Action':'Add','ResourceType':'AWS::EC2::Instance'}} for name in sorted(ROLES)]}

    def test_only_missing_four_roles_allowed(self):
        self.assertEqual(len(validate_changes(self.change())),4)
        for name,action,kind in [('RepoInstance','Modify','AWS::EC2::Instance'),
                ('BootstrapSg','Modify','AWS::EC2::SecurityGroup'),('S3Endpoint','Modify','AWS::EC2::VPCEndpoint')]:
            value=self.change();value['Changes'].append({'ResourceChange':{'LogicalResourceId':name,'Action':action,'ResourceType':kind}})
            with self.assertRaises(ValueError):validate_changes(value)

    def test_missing_duplicate_replace_and_pagination_are_rejected(self):
        original=self.change()
        for value in (dict(original,Changes=original['Changes'][:-1]),
                      dict(original,Changes=original['Changes']+[original['Changes'][0]]),
                      dict(original,NextToken='more')):
            with self.assertRaises(ValueError):validate_changes(value)
        value=copy.deepcopy(original);value['Changes'][0]['ResourceChange']['Action']='Modify'
        with self.assertRaises(ValueError):validate_changes(value)

    def test_failed_stack_without_current_repo_proof_is_rejected(self):
        report={'stack_status':'UPDATE_FAILED','phase':'bootstrap','nodes':{},'aws_checks':{}}
        with self.assertRaises(ValueError):validate_report(report)

    def test_only_terminated_role_retry_can_use_empty_replacement_record(self):
        value=self.change()
        for item in value['Changes']:
            r=item['ResourceChange']
            if r['LogicalResourceId']!='BastionInstance':r.update(Action='Modify',Replacement='True',Scope=[],Details=[])
        self.assertEqual(len(validate_changes(value)),4)
        for field,data in [('Scope',['Properties']),('Details',[{'Target':{'Name':'ImageId'}}])]:
            bad=copy.deepcopy(value)
            next(x['ResourceChange'] for x in bad['Changes'] if x['ResourceChange']['LogicalResourceId']=='DbInstance')[field]=data
            with self.assertRaises(ValueError):validate_changes(bad)


if __name__=='__main__':unittest.main()
