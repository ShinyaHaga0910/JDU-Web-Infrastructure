import json
from pathlib import Path
import unittest


class BindingTemplateTests(unittest.TestCase):
    def test_one_isolated_table_with_matching_keys_and_expiry(self):
        template = json.loads(Path(__file__).with_name('binding-table.template.json').read_text('utf-8'))
        resources = template['Resources']
        self.assertEqual(set(resources), {'BindingTable'})
        table = resources['BindingTable']
        self.assertEqual(table['Type'], 'AWS::DynamoDB::Table')
        self.assertEqual(table['DeletionPolicy'], 'Retain')
        self.assertEqual(table['UpdateReplacePolicy'], 'Retain')
        props = table['Properties']
        self.assertEqual(props['BillingMode'], 'PAY_PER_REQUEST')
        self.assertEqual(props['KeySchema'], [{'AttributeName': 'pk', 'KeyType': 'HASH'},
                                              {'AttributeName': 'sk', 'KeyType': 'RANGE'}])
        self.assertEqual(props['TimeToLiveSpecification'], {'AttributeName': 'expires_at', 'Enabled': True})
        self.assertTrue(props['SSESpecification']['SSEEnabled'])
        self.assertNotIn('TableName', props)


if __name__ == '__main__':
    unittest.main()
