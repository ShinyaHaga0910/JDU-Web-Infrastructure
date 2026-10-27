"""Record of the isolated AWS transaction experiment, not a deployment tool.

This creates synthetic rows and retains them in the specifically named POC
table. It refuses to run if the synthetic account is already present. The
experiment exercises the same DynamoDB conditions as enrollment.py with
manually constructed input; it does not run enrollment.py or verify STS.
"""
import threading
import uuid
import boto3

s = boto3.client('sts', region_name='us-east-1')
assert s.get_caller_identity()['Account'] == '170126527713'
c = boto3.client('cloudformation', region_name='us-east-1')
stack = c.describe_stacks(StackName='jdu-web-portal-binding-poc-20261027')['Stacks'][0]
assert stack['StackStatus'] == 'CREATE_COMPLETE'
t = {o['OutputKey']: o['OutputValue'] for o in stack['Outputs']}['TableName']
assert t.startswith('jdu-web-portal-binding-poc-20261027-BindingTable-')
d = boto3.client('dynamodb', region_name='us-east-1')
lab = 'poc-' + uuid.uuid4().hex[:20]
account, token, dep = '000000000000', 'c' * 64, 'poc-deployment'
nodes = {r: 'i-' + str(i) * 17 for i, r in enumerate(('bastion', 'web', 'dns', 'db', 'repo'), 1)}
nm = {k: {'S': v} for k, v in nodes.items()}
def key(p, s):
    return {'pk': {'S': p}, 'sk': {'S': s}}
meta = {**key('LAB#' + lab, 'META'), 'active': {'BOOL': True}, 'token_hash': {'S': token},
        'deployment_id': {'S': dep}, 'instances': {'M': nm}, 'test_only': {'BOOL': True}}
assert not d.get_item(TableName=t, Key=key('ACCOUNT#' + account, 'BINDING'), ConsistentRead=True).get('Item')
d.put_item(TableName=t, Item=meta, ConditionExpression='attribute_not_exists(pk)')
n = 'CHALLENGE#' + uuid.uuid4().hex
ctx = {'account': {'S': account}, 'lab_id': {'S': lab}, 'deployment_id': {'S': dep}, 'connector': {'S': 'synthetic'}}
challenge = {**key(n, 'IDENTITY'), 'used': {'BOOL': False}, 'expires_at': {'N': '4102444800'},
             'session': {'S': 'synthetic'}, 'account': {'S': account}, 'lab': {'S': lab}, 'connector': {'S': 'synthetic'}}
d.put_item(TableName=t, Item=challenge, ConditionExpression='attribute_not_exists(pk)')
ops = [
    {'ConditionCheck': {'TableName': t, 'Key': key('LAB#' + lab, 'META'),
        'ConditionExpression': '#active=:yes AND token_hash=:token AND deployment_id=:deployment AND #instances=:instances',
        'ExpressionAttributeNames': {'#active': 'active', '#instances': 'instances'},
        'ExpressionAttributeValues': {':yes': {'BOOL': True}, ':token': {'S': token}, ':deployment': {'S': dep}, ':instances': {'M': nm}}}},
    {'Update': {'TableName': t, 'Key': key(n, 'IDENTITY'), 'UpdateExpression': 'SET #used=:true',
        'ConditionExpression': '#used=:false AND #expires>:now AND #session=:session AND #account=:account AND #lab=:lab AND #connector=:connector',
        'ExpressionAttributeNames': {'#used': 'used', '#expires': 'expires_at', '#session': 'session', '#account': 'account', '#lab': 'lab', '#connector': 'connector'},
        'ExpressionAttributeValues': {':false': {'BOOL': False}, ':true': {'BOOL': True}, ':now': {'N': '1'}, ':session': {'S': 'synthetic'}, ':account': {'S': account}, ':lab': {'S': lab}, ':connector': {'S': 'synthetic'}}}},
    {'Put': {'TableName': t, 'Item': {**key('LAB#' + lab, 'BINDING'), **ctx}, 'ConditionExpression': 'attribute_not_exists(pk)'}},
    {'Put': {'TableName': t, 'Item': {**key('ACCOUNT#' + account, 'BINDING'), **ctx}, 'ConditionExpression': 'attribute_not_exists(pk)'}}]
bar = threading.Barrier(2)
results, errors = [], []
def run():
    try:
        bar.wait()
        d.transact_write_items(TransactItems=ops)
        results.append('success')
    except d.exceptions.TransactionCanceledException:
        results.append('rejected')
    except Exception as e:
        errors.append(str(e))
a = [threading.Thread(target=run) for _ in range(2)]
for x in a: x.start()
for x in a: x.join(20)
assert not errors, (results, errors)
assert sorted(results) == ['rejected', 'success'] and not any(x.is_alive() for x in a), results
assert d.get_item(TableName=t, Key=key('LAB#' + lab, 'META'), ConsistentRead=True)['Item'] == meta
assert d.get_item(TableName=t, Key=key(n, 'IDENTITY'), ConsistentRead=True)['Item']['used']['BOOL']
assert d.get_item(TableName=t, Key=key('LAB#' + lab, 'BINDING'), ConsistentRead=True).get('Item')
assert d.get_item(TableName=t, Key=key('ACCOUNT#' + account, 'BINDING'), ConsistentRead=True).get('Item')
print('AWS_SYNTHETIC_TRANSACTION_RACE_OK; POC_META_UNCHANGED; REPLAY_REJECTED')
