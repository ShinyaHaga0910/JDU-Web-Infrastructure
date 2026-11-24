"""Student AWS CloudFormation account-link helper; no EC2 or grade changes.

The signed STS request stays in memory and travels only in an HTTPS JSON body.
Never log events, proof URLs, CloudFormation ResponseURL or AWS exceptions.
The inline template builder bundles the existing student_proof implementation.
"""
import hashlib
import http.client
import json
import os
import re
from urllib.parse import urlsplit

from student_proof import create_proof

HEX = re.compile(r'[a-f0-9]{64}\Z')
RESPONSE_HOSTS = {
    'cloudformation-custom-resource-response-useast1.s3.amazonaws.com',
    'cloudformation-custom-resource-response-useast1.s3.us-east-1.amazonaws.com',
}


def portal_origin(value):
    if not isinstance(value,str) or not re.fullmatch(r'https://[a-z0-9]{10,64}\.[a-z0-9]{2,16}\.lambda-web\.us-east-1\.on\.aws',value):
        raise ValueError('Invalid portal origin')
    return value


def post_proof(origin, pair_id, proof_url, *, purpose='enrollment'):
    if purpose not in ('enrollment', 'preparation'):
        raise ValueError('Invalid confirmation purpose')
    target=urlsplit(portal_origin(origin))
    body=json.dumps({'pair_id':pair_id,'proof_url':proof_url},separators=(',',':')).encode()
    connection=http.client.HTTPSConnection(target.hostname,timeout=7)
    try:
        connection.request('POST','/api/'+purpose+'/complete',body=body,
            headers={'Content-Type':'application/json','Content-Length':str(len(body))})
        response=connection.getresponse()
        result=response.read(4097)
        expected={'registered':True} if purpose=='enrollment' else {'aws_confirmed':True}
        if response.status!=200 or len(result)>4096 or json.loads(result)!=expected:
            raise ValueError('Registration not confirmed')
    finally:
        connection.close()


def response_target(value):
    if not isinstance(value,str) or len(value)>8192:
        raise ValueError('Invalid response destination')
    target=urlsplit(value)
    if (target.scheme!='https' or target.netloc not in RESPONSE_HOSTS
            or not target.path.startswith('/') or target.path=='/' or target.fragment or not target.query):
        raise ValueError('Invalid response destination')
    return target


def send_response(url,body):
    target=response_target(url)
    data=json.dumps(body,separators=(',',':')).encode()
    if len(data)>4096:
        raise ValueError('Invalid response size')
    connection=http.client.HTTPSConnection(target.hostname,timeout=5)
    try:
        connection.request('PUT',target.path+'?'+target.query,body=data,
            headers={'Content-Type':'','Content-Length':str(len(data))})
        response=connection.getresponse()
        response.read(1024)
        if response.status not in (200,204):
            raise ValueError('CloudFormation response unavailable')
    finally:
        connection.close()


def envelope(event,env):
    if (type(event) is not dict or event.get('RequestType') not in ('Create','Update','Delete')
            or event.get('StackId')!=env.get('BOOTSTRAP_STACK_ID')
            or event.get('LogicalResourceId')!='LinkAccount'
            or event.get('ResourceType')!='Custom::JduPortalAccountLink'
            or not isinstance(event.get('RequestId'),str) or not re.fullmatch(r'[A-Za-z0-9-]{1,128}',event['RequestId'])
            or not isinstance(env.get('STUDENT_ACCOUNT'),str) or not re.fullmatch(r'[0-9]{12}',env['STUDENT_ACCOUNT'])
            or not isinstance(env.get('LAB_ID'),str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,31}',env['LAB_ID'])
            or not isinstance(event.get('StackId'),str)
            or not re.fullmatch(r'arn:aws:cloudformation:us-east-1:'+env['STUDENT_ACCOUNT']
                                +r':stack/jdu-web-link-[a-z0-9-]{3,90}/[A-Za-z0-9-]{36}',event['StackId'])):
        raise ValueError('Invalid CloudFormation request')
    response_target(event.get('ResponseURL'))


def serve(event,env,session,*,sign=create_proof,post=post_proof,reply=send_response):
    # Untrusted event envelopes cannot select a callback or cause AWS calls.
    try:
        envelope(event,env)
    except Exception:
        return {'status':'unauthorized'}
    physical='jdu-web-link-'+hashlib.sha256((event['StackId']+'|LinkAccount').encode()).hexdigest()[:32]
    body={'StackId':event['StackId'],'RequestId':event['RequestId'],'LogicalResourceId':'LinkAccount',
          'PhysicalResourceId':physical,'NoEcho':True,'Data':{}}
    try:
        if event['RequestType']=='Create':
            props=event.get('ResourceProperties')
            if (type(props) is not dict or not {'ServiceToken','PairId','ExpectedAccount','LabId'}<=set(props)
                    or set(props)-{'ServiceToken','PairId','ExpectedAccount','LabId','ServiceTimeout'}
                    or ('ServiceTimeout' in props and str(props['ServiceTimeout'])!='60')
                    or props.get('ExpectedAccount')!=env['STUDENT_ACCOUNT'] or props.get('LabId')!=env['LAB_ID']
                    or not isinstance(props.get('PairId'),str) or not HEX.fullmatch(props['PairId'])):
                raise ValueError('Invalid registration request')
            origin=portal_origin(env.get('PORTAL_ORIGIN'))
            purpose=env.get('PORTAL_LINK_PURPOSE','enrollment')
            if purpose not in ('enrollment','preparation'):
                raise ValueError('Invalid confirmation purpose')
            from botocore.config import Config
            sts=session.client('sts',region_name='us-east-1',config=Config(
                connect_timeout=3,read_timeout=5,retries={'max_attempts':0}))
            if sts.get_caller_identity()['Account']!=env['STUDENT_ACCOUNT']:
                raise ValueError('Wrong student account')
            proof=sign(session,props['PairId'])
            if purpose=='preparation':
                post(origin,props['PairId'],proof,purpose='preparation')
            else:
                post(origin,props['PairId'],proof)
            proof=None
            body.update(Status='SUCCESS',Reason='Account registration confirmed. Return to the portal.')
        else:
            # Rollback, deletion and template maintenance never revoke an
            # established identity or re-submit an expired registration proof.
            body.update(Status='SUCCESS',Reason='No registration operation on update or delete.')
    except Exception:
        body.update(Status='FAILED',Reason='Registration not confirmed. Return to the portal and check registration.')
    try:
        reply(event['ResponseURL'],body)
    except Exception:
        # A generic error permits CloudFormation delivery retry without ever
        # echoing the signed S3 callback or the STS request in the exception.
        raise RuntimeError('CloudFormation response unavailable') from None
    return {'status':'ok' if body['Status']=='SUCCESS' else 'unavailable'}


def handler(event,context):
    import boto3
    return serve(event,os.environ,boto3.Session(region_name='us-east-1'))
