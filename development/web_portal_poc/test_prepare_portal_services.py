import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from prepare_portal_services import ADDITIONS, assert_new_stack, inspect_change, private_write
from approve_portal_student import original_grant
from portal_enrollment import encoded


class PlanTest(unittest.TestCase):
    def change(self):
        return {'Status':'CREATE_COMPLETE','ExecutionStatus':'AVAILABLE','Changes':[
            {'ResourceChange':{'Action':'Add','LogicalResourceId':k,'ResourceType':v}} for k,v in ADDITIONS.items()]}

    def test_only_exact_five_additions_pass(self):
        inspect_change(self.change())
        for mutate in (lambda c:c['Changes'].pop(),
                       lambda c:c['Changes'].append(copy.deepcopy(c['Changes'][0])),
                       lambda c:c['Changes'][0]['ResourceChange'].update(Action='Modify'),
                       lambda c:c['Changes'][0]['ResourceChange'].update(ResourceType='AWS::IAM::Policy'),
                       lambda c:c.update(ExecutionStatus='EXECUTE_IN_PROGRESS')):
            value=self.change();mutate(value)
            with self.assertRaises(ValueError): inspect_change(value)

    def test_existing_stack_and_receipt_are_not_overwritten(self):
        with self.assertRaises(ValueError): assert_new_stack(Mock())
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'plan.private.json'
            private_write(path,{'phase':'prepared'})
            with self.assertRaises(FileExistsError): private_write(path,{'phase':'replaced'})
            self.assertEqual(json.loads(path.read_text())['phase'],'prepared')

    def test_approval_uses_original_deployment_and_five_ids_not_operator_supplied_values(self):
        db=Mock()
        row={'active':True,'lab_id':'test-lab','deployment_id':'12345678-1234-1234-1234-123456789012',
             'token_hash':'a'*64,'instances':{r:'i-'+str(i)*17 for i,r in enumerate(('bastion','web','dns','db','repo'),1)}}
        db.get_item.return_value={'Item':encoded(row)}
        grant=original_grant(db,'grades','test-lab','123456789012')
        self.assertEqual(grant['instances'],row['instances'])
        self.assertTrue(db.get_item.call_args.kwargs['ConsistentRead'])
        db.put_item.assert_not_called()
        row['active']=False
        db.get_item.return_value={'Item':encoded(row)}
        with self.assertRaises(ValueError): original_grant(db,'grades','test-lab','123456789012')


if __name__=='__main__': unittest.main()
