"""Original browser checker, bound to the initial Lab's fixed saved context."""
from pathlib import Path


def serve(event,root,env,db,sts,cfn,ec2,ssm):
    try:
        from initial_context import context
        from initial_worker import plan_digest
        health=event=={'operation':'health'}
        _,grant,config=context(root,env,db,require_ready=not health)
        if env.get('INITIAL_CHECK_TABLE')!='jdu-web-check-'+grant['lab_id']+'-results':
            raise ValueError('Fixed own result table required')
        if health:return {'status':'ok','config_sha256':plan_digest(config)}
        from student_checker_handler import StudentChecker
        return StudentChecker(config,db,env['INITIAL_CHECK_TABLE'],sts,cfn,ec2,ssm).serve(event)
    except Exception:return {'status':'unavailable'}


def handler(event,ctx):
    import os
    import boto3
    from assessment_command_jobs import no_retry_ssm
    session=boto3.Session(region_name='us-east-1')
    return serve(event,Path(__file__).resolve().parent,os.environ,
        *(session.client(n) for n in ('dynamodb','sts','cloudformation','ec2')),no_retry_ssm(session))
