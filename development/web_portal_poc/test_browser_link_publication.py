import copy
import unittest
from unittest.mock import Mock

from prepare_browser_link_publication import ADDITIONS,inspect,apply


class PublicationTest(unittest.TestCase):
    def change(self):
        return {'Status':'CREATE_COMPLETE','ExecutionStatus':'AVAILABLE','Changes':[
            {'ResourceChange':{'LogicalResourceId':k,'ResourceType':v,'Action':'Add'}} for k,v in ADDITIONS.items()]}

    def test_only_separate_bucket_and_explicit_student_policy_can_be_added(self):
        inspect(self.change())
        for mutation in (lambda c:c['Changes'].pop(),
                         lambda c:c['Changes'][0]['ResourceChange'].update(Action='Modify'),
                         lambda c:c['Changes'][0]['ResourceChange'].update(ResourceType='AWS::IAM::Policy'),
                         lambda c:c.update(ExecutionStatus='EXECUTE_IN_PROGRESS')):
            value=copy.deepcopy(self.change());mutation(value)
            with self.assertRaises(ValueError):inspect(value)

    def test_unapproved_context_has_no_execution_or_bucket_writes(self):
        sts,cfn,s3=Mock(),Mock(),Mock()
        sts.get_caller_identity.return_value={'Account':'987654321098'}
        with self.assertRaises(ValueError):apply(None,{},None,sts,cfn,s3)
        cfn.execute_change_set.assert_not_called();s3.put_object.assert_not_called()


if __name__=='__main__':unittest.main()
