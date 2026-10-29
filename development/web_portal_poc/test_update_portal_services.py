import copy
import unittest
from unittest.mock import Mock

from update_portal_services import inspect,apply


class UpdateTest(unittest.TestCase):
    def change(self):
        return {'Status':'CREATE_COMPLETE','ExecutionStatus':'AVAILABLE','Changes':[
            {'ResourceChange':{'LogicalResourceId':name,'ResourceType':'AWS::Lambda::Function','Action':'Modify',
                'Replacement':'False','Scope':['Properties'],'Details':[{'Target':{'Attribute':'Properties','Name':'Code'}}]}}
            for name in ('EnrollmentService','GradeReader')]}

    def test_only_the_two_existing_code_properties_may_change(self):
        inspect(self.change())
        for mutation in (lambda c:c['Changes'].pop(),
                         lambda c:c['Changes'][0]['ResourceChange'].update(Replacement='True'),
                         lambda c:c['Changes'][0]['ResourceChange'].update(Action='Add'),
                         lambda c:c['Changes'][0]['ResourceChange'].update(LogicalResourceId='SubjectKey'),
                         lambda c:c['Changes'][0]['ResourceChange']['Details'][0]['Target'].update(Name='Role'),
                         lambda c:c['Changes'][0]['ResourceChange'].update(Scope=['Properties','Tags']),
                         lambda c:c['Changes'][0]['ResourceChange'].update(Details=[])):
            value=copy.deepcopy(self.change());mutation(value)
            with self.assertRaises(ValueError):inspect(value)

    def test_wrong_context_does_not_execute_or_upload_anything(self):
        clients=[Mock() for _ in range(4)]
        clients[0].get_caller_identity.return_value={'Account':'987654321098'}
        with self.assertRaises(ValueError):apply({},None,clients)
        clients[1].execute_change_set.assert_not_called()
        clients[2].put_object.assert_not_called()


if __name__=='__main__':unittest.main()
