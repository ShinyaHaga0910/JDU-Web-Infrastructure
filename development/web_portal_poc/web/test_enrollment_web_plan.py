import copy
import unittest
from unittest.mock import Mock

from prepare_browser_enrollment_web import inspect
from apply_browser_enrollment_web import apply


class PlanTest(unittest.TestCase):
    def change(self):
        return {'Status':'CREATE_COMPLETE','ExecutionStatus':'AVAILABLE','Changes':[
            {'ResourceChange':{'LogicalResourceId':k,'ResourceType':v,'Action':'Modify'}} for k,v in
            {'Revision':'AWS::Lambda::WebFunctionRevision','Endpoint':'AWS::Lambda::WebFunctionEndpoint'}.items()]}

    def test_only_existing_revision_and_endpoint_are_updated(self):
        inspect(self.change())
        for mutate in (lambda c:c['Changes'].pop(),
                       lambda c:c['Changes'][0]['ResourceChange'].update(Action='Add'),
                       lambda c:c['Changes'][0]['ResourceChange'].update(ResourceType='AWS::IAM::Role'),
                       lambda c:c.update(ExecutionStatus='EXECUTE_IN_PROGRESS')):
            change=copy.deepcopy(self.change());mutate(change)
            with self.assertRaises(ValueError):inspect(change)

    def test_wrong_context_never_executes_change_set(self):
        clients=[Mock() for _ in range(4)]
        clients[0].get_caller_identity.return_value={'Account':'987654321098'}
        with self.assertRaises(ValueError):apply({},None,None,clients)
        clients[1].execute_change_set.assert_not_called()


if __name__=='__main__':unittest.main()
