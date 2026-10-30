"""Read-only existing status observer using the new Lab's retained journal."""
from pathlib import Path


def serve(event,root,env,db,sts,cfn,ec2,ssm):
    if event!={'operation':'status'}:return {'status':'unauthorized'}
    try:
        from initial_context import context
        from student_status_handler import serve as observe
        _,grant,config=context(root,env,db)
        target={'STUDENT_ACCOUNT':grant['account'],'LAB_ID':grant['lab_id'],
            'DEPLOYMENT_ID':grant['deployment_id'],'STACK_ARN':config['state']['stack_id'],
            **{'INSTANCE_'+r.upper():n['instance_id'] for r,n in config['baseline']['nodes'].items()}}
        return observe(event,target,sts,cfn,ec2,ssm)
    except Exception:return {'status':'unavailable'}


def handler(event,ctx):
    import os
    import boto3
    session=boto3.Session(region_name='us-east-1')
    return serve(event,Path(__file__).resolve().parent,os.environ,
        *(session.client(n) for n in ('dynamodb','sts','cloudformation','ec2','ssm')))
