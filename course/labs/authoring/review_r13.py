"""Reproduce the r1.3 editorial comparison with the reviewed r1.2 snapshot."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode=True
from content import MODULES
from build import ROOT, KIT, EXPECTED_REGISTRY, MATERIAL_REVISION
from markdown_it import MarkdownIt
from pypdf import PdfReader

BASELINE='463d374'
REPO=ROOT.parents[1]

def original(path):
    return subprocess.run(['git','show',BASELINE+':'+path],cwd=REPO,check=True,capture_output=True).stdout

def main():
    tree=ast.parse(original('course/labs/authoring/content.py').decode('utf-8'))
    old={};module=None;number=0
    for node in tree.body:
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call) and getattr(node.value.func,'id','')=='module':
            module=ast.literal_eval(node.value.args[0]);number=0
        if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and getattr(node.value.func,'id','')=='step':
            number+=1;old[f'{module}.{number}']=ast.literal_eval(node.value.args[4]).strip()
    new={f'{m["id"]}.{i}':s['code'] for m in MODULES for i,s in enumerate(m['steps'],1)}
    assert old.keys()==new.keys() and len(new)==49
    preserved=[];browser_only=[]
    for key,code in old.items():
        if key=='P0.1':continue  # CloudShell installation/account check replaces CLI activation/help.
        expected='\n'.join(line for line in code.splitlines() if not line.startswith(('jdu-web-check ','jdu-web-my-progress')))
        assert new[key]==expected,(key,'server instruction changed')
        (preserved if expected else browser_only).append(key)
    signed={}
    for path in sorted((ROOT/'distribution').rglob('*')):
        if not path.is_file():continue
        before=original(path.relative_to(REPO).as_posix())
        assert before==path.read_bytes(),path
        signed[path.relative_to(ROOT).as_posix()]=hashlib.sha256(before).hexdigest()
    assert len(signed)==7
    assert hashlib.sha256((KIT/'assessment/assessment-registry.json').read_bytes()).hexdigest()==EXPECTED_REGISTRY
    forbidden=('jdu-web-check','jdu-web-my-progress','--no-submit','--functional','--retry','--prepare-stop','--observe-stopped','2026-10-27')
    for path in (ROOT/'docs').rglob('*.md'):
        assert not any(x in path.read_text(encoding='utf-8') for x in forbidden),path
    for path in (ROOT/'output/pdf').glob('*.pdf'):
        text='\n'.join(page.extract_text() or '' for page in PdfReader(path).pages)
        assert 'r1.3' in text and '2027' in text and not any(x in text for x in forbidden),path
    parser=MarkdownIt('commonmark',{'html':False}).enable('table')
    root_links=[c.attrGet('href') for t in parser.parse((ROOT/'README.md').read_text(encoding='utf-8')) for c in t.children or [] if c.type=='link_open']
    assert not any(x.endswith('.html') for x in root_links)
    result=dict(checked_on='2026-11-03',baseline_commit=BASELINE,material_revision=MATERIAL_REVISION,
        detailed_steps=49,server_or_configuration_blocks_preserved=len(preserved),preserved_step_ids=preserved,
        steps_without_command_blocks=browser_only,cloudshell_preparation_change='P0.1: account and installed file check, without grading CLI activation/help',
        task_pages=42,root_github_links_use_markdown=True,student_grading_instructions_use_browser=True,
        expiry_consistent_through_student_documents_and_pdfs=True,signed_distribution_files_unchanged=signed,
        registry_sha256=EXPECTED_REGISTRY,raw_points=62,aws_resources_changed=False,
        native_language_review=False,teacher_visual_review=False)
    target=ROOT/'reviews/2026-11-03-readability-r13.public.json'
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('signed_distribution_files_unchanged','preserved_step_ids')},ensure_ascii=True))

if __name__=='__main__':main()
