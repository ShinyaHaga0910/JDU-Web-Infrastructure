"""Publisher-side selection from the verified, unexpired signed course kit."""
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ASSESSMENT=HERE.parent/'01_roles/cyber_security/tools/web_lab_assessment'
LESSONS=HERE.parents[1]/'course/labs/resources'
CONTRACT='3feeb3d8a9225e6e19e06f68367b07c6cb4a657f05818c146ccb22cfcd654c33'
MODULES=('registry.py','network_checks.py','db_observer.py','system_observer.py','app_probe.py',
         'remote_guest.py','transport.py','aws_readiness.py','http_guest_v2.py','assessment-registry.json')
LEGACY=('http_task.py','http_task_guest.py','bootstrap_inspection.py')


def from_course(course,verified,assignment):
    if type(course) is not dict:raise ValueError('Verified signed course kit required')
    root=Path(course['root']);release=course['release']
    raw=(root/'course-release.json').read_bytes()
    expiry=datetime.fromisoformat(release['expires_at'].replace('Z','+00:00'))
    if (course.get('fingerprint')!=verified['trusted_fingerprint']
            or hashlib.sha256(raw).hexdigest()!=course['sha256'] or json.loads(raw)!=release
            or release.get('core_manifest_sha256')!=verified['manifest_sha256']
            or course['foundation']['core']['manifest_sha256']!=verified['manifest_sha256']
            or release.get('raw_maximum')!=62 or release.get('contract_sha256')!=CONTRACT
            or release.get('distribution_ready') is not True or release.get('class_ready') is not False
            or expiry.tzinfo is None or not datetime.now(timezone.utc)<expiry
            or assignment['release']['expires_at']>expiry.timestamp()):
        raise ValueError('Matching valid signed course kit required')
    archive=(root/'assessment.tar.gz').read_bytes()
    if hashlib.sha256(archive).hexdigest()!=release['assessment_archive_sha256']:
        raise ValueError('Signed assessment archive changed')
    # Import the repository's trusted verifier, not executable kit input.
    spec=importlib.util.spec_from_file_location('initial_candidate_verifier',ASSESSMENT/'candidate_install.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source,manifest=module.checked_archive(archive)
    if manifest['contract_sha256']!=CONTRACT or hashlib.sha256(source['D11-MANIFEST.json']).hexdigest()!=release['assessment_manifest_sha256']:
        raise ValueError('Fixed signed 62-point assessment required')
    files={n:source[n] for n in MODULES}
    files.update({n:source['legacy/'+n] for n in LEGACY})
    files.update({'catalog-app.tar.gz':source['catalog-app.tar.gz'],'database_secret.py':source['database_secret.py'],
                  'lesson-offline_assets.py':(LESSONS/'offline_assets.py').read_bytes()})
    mapping={n:n for n in ('catalog-app.tar.gz','registry.py','assessment-registry.json','database_secret.py')}
    mapping['offline_assets.py']='lesson-offline_assets.py'
    teaching={'schema_version':1,'course_distribution_sha256':course['sha256'],
        'distribution_id':release['distribution_id'],'contract_sha256':CONTRACT,
        'files':{target:{'source':name,'sha256':hashlib.sha256(files[name]).hexdigest(),'size_bytes':len(files[name])}
                 for target,name in mapping.items()},'services_changed':False}
    files['initial-teaching.json']=(json.dumps(teaching,sort_keys=True,separators=(',',':'))+'\n').encode()
    return files
