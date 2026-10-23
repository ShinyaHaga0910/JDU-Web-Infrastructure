"""Keep the same private SSM endpoints available to exactly the five lab nodes."""
import copy
import json


def template(original):
    result = copy.deepcopy(original); r = result['Resources']
    if (r['SsmSg']['Properties']['SecurityGroupIngress'] != [{'IpProtocol': 'tcp', 'FromPort': 443,
            'ToPort': 443, 'SourceSecurityGroupId': {'Ref': 'BastionSg'}}]
            or r['BastionSsmOut']['Properties'] != {'GroupId': {'Ref': 'BastionSg'}, 'IpProtocol': 'tcp',
                'FromPort': 443, 'ToPort': 443, 'DestinationSecurityGroupId': {'Ref': 'SsmSg'}}):
        raise ValueError('Reviewed original bastion SSM configuration required')
    for role in ('Web', 'Dns', 'Db', 'Repo'):
        p = r[role + 'Instance']['Properties']
        if 'IamInstanceProfile' in p: raise ValueError('Original peers must have no profile')
        p['IamInstanceProfile'] = 'LabInstanceProfile'
    r['SsmSg']['Properties']['SecurityGroupIngress'][0]['SourceSecurityGroupId'] = {'Ref': 'BootstrapSg'}
    # Preserve this existing logical resource to avoid unrelated stack churn.
    r['BastionSsmOut']['Properties']['GroupId'] = {'Ref': 'BootstrapSg'}
    if len((json.dumps(result, separators=(',', ':')) + '\n').encode()) > 51200:
        raise ValueError('Direct CloudFormation size limit exceeded')
    return result
