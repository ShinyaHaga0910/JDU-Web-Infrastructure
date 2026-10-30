"""Immutable, secret-free template for browser-only existing-Lab ownership proof.

No deployment, permission change, key generation or grading occurs here.
The original 5-node infrastructure is not present in this template.
"""
import argparse
import hashlib
import json
from pathlib import Path

from browser_link_handler import portal_origin

HERE=Path(__file__).resolve().parent


def inline_source():
    # Concatenate reviewed source without eval/exec or network dependencies.
    # Preserve the existing signed-proof validation in the inline Lambda.
    identity=(HERE/'identity_proof.py').read_text(encoding='utf-8')
    proof=(HERE/'student_proof.py').read_text(encoding='utf-8').replace('import identity_proof\n','',1)
    handler=(HERE/'browser_link_handler.py').read_text(encoding='utf-8').replace('from student_proof import create_proof\n','',1)
    return '\n'.join([identity,'from types import SimpleNamespace',
        'identity_proof=SimpleNamespace(NONCE=NONCE,HOST=HOST,validate=validate)',proof,handler])


def template(origin, *, purpose='enrollment'):
    portal_origin(origin)
    if purpose not in ('enrollment','preparation'):
        raise ValueError('Invalid confirmation purpose')
    source=inline_source()
    return {
        'AWSTemplateFormatVersion':'2010-09-09',
        'Description':'JDU portal AWS account verification only; no EC2, grades, credentials or IAM changes',
        'Metadata':{'JduSourceSHA256':hashlib.sha256(source.encode()).hexdigest()},
        'Parameters':{
            'ExpectedAccount':{'Type':'String','AllowedPattern':'[0-9]{12}','Description':'Your assigned student AWS account; verify console account before creating'},
            'LabId':{'Type':'String','AllowedPattern':'[a-z0-9][a-z0-9-]{2,31}'},
            'PairId':{'Type':'String','AllowedPattern':'[a-f0-9]{64}','Description':'Public correlation challenge; not a credential. Valid for five minutes.'}},
        'Resources':{
            'AccountLink':{'Type':'AWS::Lambda::Function','Properties':{
                'Runtime':'python3.13','Handler':'index.handler',
                # A wrong console account cannot pass this other-account role.
                'Role':{'Fn::Sub':'arn:aws:iam::${ExpectedAccount}:role/LabRole'},
                'Timeout':30,'MemorySize':128,'Code':{'ZipFile':source},
                'Environment':{'Variables':{'STUDENT_ACCOUNT':{'Ref':'ExpectedAccount'},'LAB_ID':{'Ref':'LabId'},
                    'BOOTSTRAP_STACK_ID':{'Ref':'AWS::StackId'},'PORTAL_ORIGIN':origin,
                    'PORTAL_LINK_PURPOSE':purpose}}}},
            'LinkLogs':{'Type':'AWS::Logs::LogGroup','Properties':{
                'LogGroupName':{'Fn::Sub':'/aws/lambda/${AccountLink}'},'RetentionInDays':3}},
            'LinkAccount':{'Type':'Custom::JduPortalAccountLink','DependsOn':'LinkLogs','Properties':{
                'ServiceToken':{'Fn::GetAtt':['AccountLink','Arn']},'ServiceTimeout':'60',
                'ExpectedAccount':{'Ref':'ExpectedAccount'},'LabId':{'Ref':'LabId'},'PairId':{'Ref':'PairId'}}}},
        'Outputs':{'Portal':{'Value':origin+('/enroll' if purpose=='enrollment' else '/prepare'),
                            'Description':'Return here to check confirmation; no credential copying'}}}


def build(destination,origin, *, purpose='enrollment'):
    data=(json.dumps(template(origin,purpose=purpose),ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
    with destination.open('xb') as target:target.write(data)
    return hashlib.sha256(data).hexdigest()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--origin',required=True)
    parser.add_argument('--purpose',choices=('enrollment','preparation'),default='enrollment')
    args=parser.parse_args()
    print(build(args.output,args.origin,purpose=args.purpose))
