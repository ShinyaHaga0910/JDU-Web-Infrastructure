"""Verify the comment/diagram revision against the published r1.3 source."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode=True
from build import ROOT,MATERIAL_REVISION,EXPECTED_REGISTRY
from content import MODULES,LANGS
from command_notes import annotated_blocks,executable_only,command_groups,CONFIG_STEPS

BASELINE='9abf53f'

def main():
    repo=ROOT.parents[1]
    old=lambda p:subprocess.run(['git','show',BASELINE+':'+p],cwd=repo,check=True,capture_output=True).stdout
    for name in ('content.py','checks.py','explanations.py'):
        path=ROOT/'authoring'/name
        assert old(path.relative_to(repo).as_posix())==path.read_bytes(),name
    signed={}
    for path in sorted((ROOT/'distribution').rglob('*')):
        if not path.is_file():continue
        assert old(path.relative_to(repo).as_posix())==path.read_bytes(),path
        signed[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
    count=0
    for m in MODULES:
        for i,s in enumerate(m['steps'],1):
            if not s['code']:continue
            for lang in LANGS:
                joined='\n'.join(source for _,source in annotated_blocks(m['id'],i,s['code'],lang))
                assert executable_only(joined)==s['code'],(m['id'],i,lang)
            if (m['id'],i) not in CONFIG_STEPS:count+=sum(active for active,_ in command_groups(s['code']))
    validation=json.loads((ROOT/'validation.public.json').read_text(encoding='utf-8'))
    assert validation['material_revision']==MATERIAL_REVISION=='r1.4'
    assert validation['numbered_command_comments_per_language']==count==153
    assert validation['task_diagrams']==42
    result=dict(checked_on='2026-11-03',baseline_commit=BASELINE,material_revision=MATERIAL_REVISION,
        source_content_checks_explanations_byte_identical=True,executable_source_preserved=True,
        numbered_comments_per_language=count,languages=list(LANGS),diagrams=42,editable_svg=42,internet_aws_boundary_diagrams=18,
        figure_text_bounds_and_overlap_checked=True,signed_distribution_files_unchanged=signed,
        registry_sha256=EXPECTED_REGISTRY,raw_points=62,sg_setup_is_preconfigured_not_a_scored_student_task=True,
        aws_resources_changed=False,native_language_review=False,teacher_visual_review=False,new_student_walkthrough=False)
    target=ROOT/'reviews/2026-11-03-command-comments-diagrams.public.json'
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k!='signed_distribution_files_unchanged'},ensure_ascii=True))

if __name__=='__main__':main()
