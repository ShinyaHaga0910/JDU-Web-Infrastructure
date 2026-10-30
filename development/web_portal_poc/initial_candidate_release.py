"""Signed R1 test input, separate from an accepted student course release."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
BOOTSTRAP=HERE.parent/'01_roles/cyber_security/tools/web_lab_bootstrap'
sys.path.insert(0,str(BOOTSTRAP))
from release_validation import read_regular,verify_signature,verify_release
from initial_assets_package import CONTRACT

FINGERPRINT='65EC6784750CCFA703BA7179519284E45155EC2A'
SCOPE='initial_foundation_verification_candidate'
MEMBERS={'assessment.tar.gz','assessment.tar.gz.asc','package-signing-public.asc','course-release.json','course-release.json.asc'}


def verify(root,core,fingerprint):
    root=Path(root)
    if fingerprint!=FINGERPRINT or core.get('trusted_fingerprint')!=fingerprint:
        raise ValueError('Pinned independently verified core required')
    if root.is_symlink() or set(p.name for p in root.iterdir())!=MEMBERS:
        raise ValueError('Exact candidate inventory required')
    raw=read_regular(root/'course-release.json',65536)
    key=read_regular(root/'package-signing-public.asc',256*1024)
    if key!=read_regular(core['files']['public_key'],256*1024):
        raise ValueError('Same pinned public key required')
    key_expiry=verify_signature(raw,read_regular(root/'course-release.json.asc',65536),key,fingerprint)
    release=json.loads(raw)
    expected={'schema_version','scope','distribution_id','class_id','teacher_account','created_at','expires_at',
              'core_manifest_sha256','assessment_archive_sha256','assessment_manifest_sha256','contract_sha256',
              'raw_maximum','distribution_ready','class_ready','foundation_acceptance_pending'}
    if set(release)!=expected:raise ValueError('Fixed candidate fields required')
    created=datetime.fromisoformat(release['created_at']);expiry=datetime.fromisoformat(release['expires_at'])
    core_expiry=datetime.fromisoformat(core['manifest']['expires_at'])
    now=datetime.now(timezone.utc)
    if (release['schema_version']!=1 or release['scope']!=SCOPE
            or not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,95}',release['distribution_id'])
            or type(release['class_id']) is not int or release['class_id']<=0
            or not re.fullmatch(r'[0-9]{12}',release['teacher_account'])
            or release['core_manifest_sha256']!=core['manifest_sha256']
            or release['raw_maximum']!=62 or release['contract_sha256']!=CONTRACT
            or release['distribution_ready'] is not False or release['class_ready'] is not False
            or release['foundation_acceptance_pending'] is not True
            or created.tzinfo is None or expiry.tzinfo is None or not created<=now<expiry<=core_expiry
            or expiry.timestamp()>key_expiry):
        raise ValueError('Valid unpromoted initial candidate required')
    archive=read_regular(root/'assessment.tar.gz',4*1024*1024)
    verify_signature(archive,read_regular(root/'assessment.tar.gz.asc',65536),key,fingerprint)
    if hashlib.sha256(archive).hexdigest()!=release['assessment_archive_sha256']:
        raise ValueError('Candidate assessment changed')
    return {'root':root,'release':release,'sha256':hashlib.sha256(raw).hexdigest(),'fingerprint':fingerprint,
            'foundation':{'core':{'manifest_sha256':core['manifest_sha256']}},'verification_candidate':True}


def build(root,core,assessment,signature,*,class_id,teacher,distribution_id,signing_home):
    """Internal builder: caller first verifies the actual signed core."""
    root=Path(root);key=read_regular(core['files']['public_key'],256*1024)
    archive=read_regular(assessment,4*1024*1024);signature=read_regular(signature,65536)
    verify_signature(archive,signature,key,FINGERPRINT)
    import importlib.util
    path=BOOTSTRAP.parent/'web_lab_assessment/candidate_install.py'
    spec=importlib.util.spec_from_file_location('initial_candidate_assessment',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    sources,manifest=module.checked_archive(archive)
    if manifest['contract_sha256']!=CONTRACT:raise ValueError('Existing 62-point contract required')
    now=datetime.now(timezone.utc)
    value={'schema_version':1,'scope':SCOPE,'distribution_id':distribution_id,'class_id':class_id,
        'teacher_account':teacher,'created_at':now.isoformat(),'expires_at':core['manifest']['expires_at'],
        'core_manifest_sha256':core['manifest_sha256'],'assessment_archive_sha256':hashlib.sha256(archive).hexdigest(),
        'assessment_manifest_sha256':hashlib.sha256(sources['D11-MANIFEST.json']).hexdigest(),
        'contract_sha256':CONTRACT,'raw_maximum':62,'distribution_ready':False,'class_ready':False,
        'foundation_acceptance_pending':True}
    root.mkdir(mode=0o700,exist_ok=False)
    for name,data in {'assessment.tar.gz':archive,'assessment.tar.gz.asc':signature,
                      'package-signing-public.asc':key,'course-release.json':(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()}.items():
        with (root/name).open('xb') as stream:stream.write(data)
        (root/name).chmod(0o600)
    subprocess.run(['gpg','--no-options','--homedir',str(signing_home),'--batch','--digest-algo','SHA256',
        '--local-user',FINGERPRINT,'--armor','--detach-sign','--output',str(root/'course-release.json.asc'),
        str(root/'course-release.json')],capture_output=True,check=True)
    return verify(root,core,FINGERPRINT)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','signature','public-key','artifact-root','assessment','assessment-signature','output','signing-home'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--class-id',type=int,required=True);p.add_argument('--teacher-account',required=True)
    p.add_argument('--distribution-id',required=True)
    a=p.parse_args()
    core=verify_release(a.manifest,a.signature,a.public_key,FINGERPRINT,a.artifact_root,include_bundle=False)
    result=build(a.output,core,a.assessment,a.assessment_signature,class_id=a.class_id,teacher=a.teacher_account,
        distribution_id=a.distribution_id,signing_home=a.signing_home)
    print(json.dumps({'marker':'SIGNED_INITIAL_VERIFICATION_CANDIDATE','sha256':result['sha256'],
        'distribution_ready':False,'class_ready':False,'foundation_acceptance_pending':True}))


if __name__=='__main__':main()
