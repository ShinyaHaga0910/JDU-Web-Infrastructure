"""Compare the published templates and app with their sources; never deploy to AWS."""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
TOOLS=ROOT/'01_roles/cyber_security/tools'
sys.path.insert(0,str(TOOLS/'web_lab_assessment'))
from freeze_registry import application_bundle
from build_teacher import build

def main():
    kit=ROOT/'03_knowledge/aws_official/web_lab_packages_2026-10-15/web-course-class193548-20261023-r2'
    registry=json.loads((kit/'assessment/assessment-registry.json').read_text())
    app,manifest=application_bundle()
    app_hash=hashlib.sha256(app).hexdigest()
    if app_hash!=registry['application_archive_sha256'] or manifest!=registry['application_manifest']:
        raise ValueError('Application source differs from the frozen signed release; review and version intentionally.')
    if (ROOT/'templates/web-lab-student.template.json').read_bytes()!=(kit/'foundation/core/web-lab-ssm-all-nodes-c5.template.json').read_bytes():
        raise ValueError('Student template differs from signed r2.')
    if json.loads((ROOT/'templates/web-teacher-d11.template.json').read_text())!=build():
        raise ValueError('Teacher template differs from the current builder.')
    result=dict(scope='published_source_integrity_not_AWS',date='2026-10-23',
        student_template_matches_signed_r2=True,teacher_template_matches_current_builder=True,
        application_manifest_matches_frozen_registry=True,application_archive_sha256=app_hash,aws_mutations=False)
    (ROOT/'source-integrity.public.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
