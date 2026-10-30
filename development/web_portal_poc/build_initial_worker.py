"""Build the R1 worker only from valid signed assets and a fixed assignment.

This is an operator-side builder, not a web route. It never deploys or signs a
new release and never changes the old signed artifacts or existing five nodes.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

HERE = Path(__file__).resolve().parent
BOOTSTRAP = HERE.parents[0]/'01_roles/cyber_security/tools/web_lab_bootstrap'
sys.path.insert(0, str(BOOTSTRAP))
from controller_runtime import controller_files
from release_validation import verify_release
from portal_preparation import checked_assignment
from portal_enrollment import grant_digest
from browser_link_handler import portal_origin
from build_browser_link_template import template as proof_template

EXTENSIONS = ('initial_worker.py', 'initial_stack.py', 'initial_plan.py', 'initial_setup.py', 'initial_ssm.py', 'initial_registration_guest.py',
              'initial_context.py','initial_teaching.py','initial_lesson_guest.py','initial_status_handler.py','initial_checker_handler.py',
              'student_status_handler.py','status.py','student_checker_handler.py','assessment_command_jobs.py','assessment_observation.py','special_checks.py','browser_check_guest.py','portal_enrollment.py',
              'portal_preparation.py', 'identity_keys.py', 'identity_proof.py', 'student_proof.py', 'browser_link_handler.py')
FINGERPRINT = '65EC6784750CCFA703BA7179519284E45155EC2A'


def build_verified(destination, manifest_path, verified, assignment, course=None):
    """Internal builder; CLI below must first run real OpenPGP verification."""
    assignment = checked_assignment(assignment)
    data = Path(manifest_path).read_bytes()
    if (verified.get('trusted_fingerprint') != FINGERPRINT
            or hashlib.sha256(data).hexdigest() != assignment['release']['manifest_sha256']
            or verified['manifest_sha256'] != assignment['release']['manifest_sha256']
            or verified['manifest']['release_id'] != assignment['release']['release_id']):
        raise ValueError('Assigned verified release required')
    files = controller_files(verified['files']['controller_bundle'].read_bytes())
    import ast
    collector=next(n for n in ast.parse(files['inspect_teacher_probe.py']).body if isinstance(n,ast.FunctionDef) and n.name=='collect')
    if 'clients' not in {v.arg for v in collector.args.kwonlyargs}:
        raise ValueError('Signed controller with SDK collector contract required')
    if not any(isinstance(n,ast.FunctionDef) and n.name=='decrypt_oaep' for n in ast.parse(files['progress_enrollment_guest.py']).body):
        raise ValueError('Signed controller with portal registration delivery required')
    from initial_assets_package import from_course
    for name,raw in from_course(course,verified,assignment).items():
        if name in files and files[name]!=raw:raise ValueError('Signed controller and assessment sources differ')
        files[name]=raw
    for name in EXTENSIONS:
        if name in files:
            raise ValueError('Extension conflicts with signed controller')
        files[name] = (HERE/name).read_bytes()
    sources = {'web_lab.py': 'wrapper', 'select_instances.py': 'selector',
               'foundation.template.json': 'template', 'teacher-price-catalog.json': 'price_catalog'}
    for name, role in sources.items():
        raw = verified['files'][role].read_bytes()
        if name in files and files[name] != raw:
            raise ValueError('Signed controller/wrapper mismatch')
        files[name] = raw
    if hashlib.sha256(files['foundation.template.json']).hexdigest() != assignment['release']['template_sha256']:
        raise ValueError('Assigned template differs')
    files['deployment-manifest.json'] = data
    config = {'schema_version':1, 'assignment':assignment, 'initial_state':'foundation_only',
              'trusted_fingerprint':FINGERPRINT, 'files':{n:hashlib.sha256(v).hexdigest() for n,v in files.items()}}
    files['initial-assignment.json'] = (json.dumps(config, sort_keys=True, separators=(',', ':'))+'\n').encode()
    with ZipFile(destination, 'x', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(files.items()):
            info = ZipInfo(name, (2020,1,1,0,0,0))
            info.compress_type, info.external_attr = ZIP_DEFLATED, 0o100644 << 16
            archive.writestr(info, raw, compresslevel=9)
    return hashlib.sha256(Path(destination).read_bytes()).hexdigest()


def template(assignment, origin, teacher_account, code):
    assignment = checked_assignment(assignment)
    portal_origin(origin)
    if (not re.fullmatch(r'[0-9]{12}', teacher_account) or type(code) is not dict
            or set(code) != {'S3Bucket','S3Key','S3ObjectVersion'}
            or any(not isinstance(v,str) or not v or len(v)>1024 for v in code.values())):
        raise ValueError('Immutable worker artifact and teacher account required')
    artifact = re.fullmatch(r'worker/([a-f0-9]{64})/initial-worker\.zip', code['S3Key'])
    owner_bucket=(code['S3Bucket']=='jdu-web-portal-initial-'+teacher_account+'-'+artifact[1][:12]
                  or re.fullmatch(r'jdu-web-portal-bootstrap-'+teacher_account+r'-[a-f0-9]{12}',code['S3Bucket'])) if artifact else False
    if (not artifact or not owner_bucket
            or code['S3ObjectVersion'] == 'null' or not re.fullmatch(r'[A-Za-z0-9._~+/=-]{1,1024}',code['S3ObjectVersion'])):
        raise ValueError('Immutable same-owner worker artifact required')
    result = proof_template(origin, purpose='preparation')
    result['Description'] = 'JDU initial foundation worker; explicit portal operation only; existing LabRole; no exercise solutions'
    result['Metadata'] = {'JduAssignmentDigest':grant_digest(assignment), 'JduInitialState':'foundation_only',
                          'JduWorkerCodeSHA256':artifact[1]}
    result['Parameters']['ExpectedAccount']['AllowedValues'] = [assignment['account']]
    result['Parameters']['LabId']['AllowedValues'] = [assignment['lab_id']]
    resources = result['Resources']
    resources['InitialProgress'] = {'Type':'AWS::DynamoDB::Table', 'DeletionPolicy':'Retain', 'UpdateReplacePolicy':'Retain',
        'Properties':{'TableName':'jdu-web-initial-'+assignment['lab_id']+'-progress', 'BillingMode':'PAY_PER_REQUEST',
            'AttributeDefinitions':[{'AttributeName':v,'AttributeType':'S'} for v in ('pk','sk')],
            'KeySchema':[{'AttributeName':'pk','KeyType':'HASH'},{'AttributeName':'sk','KeyType':'RANGE'}]}}
    function = resources['AccountLink']['Properties']
    function.update(Runtime='python3.11', Handler='initial_worker.handler', Timeout=90, MemorySize=256,
                    FunctionName='jdu-web-initial-'+assignment['lab_id'], Code=code)
    function['Environment']['Variables'].update(INITIAL_DEPLOYMENT_ID=assignment['deployment_id'],
                                                INITIAL_PROGRESS_TABLE={'Ref':'InitialProgress'})
    resources['TeacherInitialInvoke'] = {'Type':'AWS::Lambda::Permission','Properties':{
        'Action':'lambda:InvokeFunction','FunctionName':{'Ref':'AccountLink'},
        'Principal':'arn:aws:iam::'+teacher_account+':role/LabRole'}}
    resources['CheckResults']={'Type':'AWS::DynamoDB::Table','DeletionPolicy':'Retain','UpdateReplacePolicy':'Retain',
        'Properties':{'TableName':'jdu-web-check-'+assignment['lab_id']+'-results','BillingMode':'PAY_PER_REQUEST',
            'SSESpecification':{'SSEEnabled':True},
            'AttributeDefinitions':[{'AttributeName':v,'AttributeType':'S'} for v in ('pk','sk')],
            'KeySchema':[{'AttributeName':'pk','KeyType':'HASH'},{'AttributeName':'sk','KeyType':'RANGE'}]}}
    for label,kind,handler,timeout in [('StudentStatus','status','initial_status_handler.handler',25),
                                      ('StudentChecker','check','initial_checker_handler.handler',120)]:
        props=copy.deepcopy(function)
        props.update(FunctionName='jdu-web-'+kind+'-'+assignment['lab_id'],Handler=handler,Timeout=timeout)
        if kind=='check':props['Environment']['Variables']['INITIAL_CHECK_TABLE']={'Ref':'CheckResults'}
        resources[label]={'Type':'AWS::Lambda::Function','Properties':props}
        resources[label+'Logs']={'Type':'AWS::Logs::LogGroup','Properties':{
            'LogGroupName':{'Fn::Sub':'/aws/lambda/${'+label+'}'},'RetentionInDays':3}}
        resources[label+'Invoke']={'Type':'AWS::Lambda::Permission','Properties':{
            'Action':'lambda:InvokeFunction','FunctionName':{'Ref':label},
            'Principal':'arn:aws:iam::'+teacher_account+':role/LabRole'}}
    # Deleting/maintaining this helper never deletes or recreates the five-node
    # stack: browser_link_handler handles Update/Delete without resource calls.
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ('manifest','signature','public-key','artifact-root','assignment-file','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--fingerprint', required=True, choices=[FINGERPRINT])
    kits=parser.add_mutually_exclusive_group(required=True)
    kits.add_argument('--course-root',type=Path)
    kits.add_argument('--candidate-root',type=Path)
    args = parser.parse_args()
    verified = verify_release(args.manifest,args.signature,args.public_key,args.fingerprint,args.artifact_root,include_bundle=False)
    assignment = json.loads(args.assignment_file.read_bytes())
    if args.candidate_root:
        from initial_candidate_release import verify
        course=verify(args.candidate_root,verified,args.fingerprint)
    else:
        import importlib.util
        spec=importlib.util.spec_from_file_location('initial_trusted_course_tools',BOOTSTRAP.parent/'web_lab_release/release_tools.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        course=module.verify(args.course_root,args.fingerprint)
    print(build_verified(args.output,args.manifest,verified,assignment,course))


if __name__=='__main__': main()
