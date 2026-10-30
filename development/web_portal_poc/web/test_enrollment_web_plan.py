import copy
import unittest
from unittest.mock import Mock

from prepare_browser_enrollment_web import inspect, service_candidate
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

    def test_reviewed_service_update_may_be_prepared_but_unreviewed_or_wrong_account_is_denied(self):
        plan={'phase':'code-update-ready','account':'170126527713','code_sha256':'a'*64,
              'stack_id':'arn:aws:cloudformation:us-east-1:170126527713:stack/example/id'}
        self.assertEqual(service_candidate(plan),plan)
        legacy={k:v for k,v in plan.items() if k!='account'}
        self.assertEqual(service_candidate(legacy),legacy)
        for changed in ({'phase':'preparation-started'},{'account':'000000000000'},{'code_sha256':'bad'},{'stack_id':'wrong'}):
            with self.assertRaises(ValueError):service_candidate({**plan,**changed})


if __name__=='__main__':unittest.main()
