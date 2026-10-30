"""Validate the authored P/M material and public-resource helpers. Does not use AWS."""
import ast
from datetime import date
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
from unittest.mock import patch
from urllib.parse import unquote, urlparse
import zipfile

sys.dont_write_bytecode = True
ROOT=Path(__file__).resolve().parents[1]
PROJECT=Path(os.environ.get('JDU_WEB_PROJECT_ROOT', str(Path(__file__).resolve().parents[3] / 'development')))
from markdown_it import MarkdownIt
from pypdf import PdfReader
from content import MODULES,LANGS
from build import KIT,EXPECTED_REGISTRY,MATERIAL_REVISION
from explanations import LABELS,STEP_NOTES,MODULE_NOTES,READING,ROUTES,MISSION_PLAN,OUTPUT_EXAMPLES


class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.ids=set();self.lang=None;self.tables=0;self.bad_th=0;self.main=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='html':self.lang=a.get('lang')
        if tag=='a' and a.get('href'):self.links.append(a['href'])
        if a.get('id'):self.ids.add(a['id'])
        if tag=='main':self.main+=1
        if tag=='table':self.tables+=1
        if tag=='th' and a.get('scope')!='col':self.bad_th+=1


def main():
    checks=[]
    def ok(name,condition):
        if not condition:raise AssertionError(name)
        checks.append(name)
    registry_raw=(KIT/'assessment/assessment-registry.json').read_bytes();reg=json.loads(registry_raw)
    ok('frozen_registry_sha256',hashlib.sha256(registry_raw).hexdigest()==EXPECTED_REGISTRY)
    ok('fixed_mission_points_62',reg['raw_points_by_mission']==dict(M1=8,M2=13,M3=3,M4=9,M5=13,M6=16))
    parser=MarkdownIt('commonmark',{'html':False}).enable('table')
    docs={};code={};fences=0
    for lang in LANGS:
        for kind in ('practice','missions'):
            path=ROOT/'docs'/lang/(kind+'.md');value=path.read_text(encoding='utf-8');docs[lang,kind]=value
            tokens=parser.parse(value)
            ok(f'{lang}_{kind}_current_revision','D12 P/M '+MATERIAL_REVISION in value)
            ok(f'{lang}_{kind}_working_guide',all(p[lang] in value for p in READING))
            ok(f'{lang}_{kind}_routes',all(purpose[lang] in value for _,_,_,purpose in ROUTES))
            code[lang,kind]=[(t.info,t.content) for t in tokens if t.type=='fence']
            ok(f'{lang}_{kind}_tasks',all(re.search(r'^## '+prefix+str(n)+r'\b',value,re.M) for n in range(7) for prefix in [('P' if kind=='practice' else 'M')]))
            ok(f'{lang}_{kind}_no_private_student_data',not any(x in value for x in
                ('965244652544','jdutestuser1@','?session=','X-Amz-Signature=','PRIVATE KEY','Fictional-Practice-Admin-Only')))
            if kind=='missions':
                ok(f'{lang}_all_62_check_ids',all(value.count(cid)==1 for t in reg['tasks'] if t['category']=='automated_mission' for cid in t['progress_scored_checks']))
                ok(f'{lang}_mission_planning',all(p[lang] in value for p in MISSION_PLAN))
            else:
                for module in MODULES:
                    for i,step in enumerate(module['steps'],1):
                        key=f"{module['id']}.{i}"
                        block=re.search(r'^#### '+re.escape(key)+r'\b(.*?)(?=^#### |^## |\Z)',value,re.M|re.S)
                        ok(f'{lang}_explains_{key}',block is not None and STEP_NOTES[key][lang] in block[0])
                    ok(f'{lang}_understanding_{module["id"]}',all(MODULE_NOTES[module['id']][k][lang] in value
                        for k in ('before','after','mechanism','question','answer')))
            pdf=PdfReader(ROOT/'output/pdf'/f'web_lab_{kind}_{lang}.pdf')
            text='\n'.join(page.extract_text() or '' for page in pdf.pages)
            ok(f'{lang}_{kind}_pdf_A4',all(abs(float(p.mediabox.width)-595.276)<1 and abs(float(p.mediabox.height)-841.890)<1 for p in pdf.pages))
            ok(f'{lang}_{kind}_pdf_text',len(text)>5000 and all(prefix+str(n) in text for n in range(7) for prefix in [('P' if kind=='practice' else 'M')]) and '\ufffd' not in text and '\x00' not in text)
    for kind in ('practice','missions'):
        ok(kind+'_identical_code_in_3_languages',code['ja',kind]==code['ru',kind]==code['uz',kind])
    ok('49_detailed_steps',sum(len(m['steps']) for m in MODULES)==49 and all(all(s[k].values()) for m in MODULES for s in m['steps'] for k in ('why','expect','trouble')))
    for info,source in code['ja','practice']+code['ja','missions']:
        if info=='bash':
            result=subprocess.run(['wsl.exe','bash','-n'],input=source,text=True,capture_output=True)
            ok('bash_fence_'+str(fences+1),result.returncode==0)
            fences+=1
    for path in (ROOT/'output/html').rglob('*.html'):
        page=Page();page.feed(path.read_text(encoding='utf-8'))
        ok('html_structure_'+path.parent.name+'_'+path.stem,page.lang in LANGS and page.main==1 and page.bad_th==0)
        for href in page.links:
            uri=urlparse(href)
            if uri.scheme:continue
            target=(path.parent/unquote(uri.path)) if uri.path else path
            ok('html_link_'+str(len(checks)),target.exists())
            if uri.fragment:
                dest=Page();dest.feed(target.read_text(encoding='utf-8'))
                ok('html_anchor_'+str(len(checks)),uri.fragment in dest.ids)
    for path in (ROOT/'resources').glob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'))
    spec=importlib.util.spec_from_file_location('lesson_assets',ROOT/'resources/offline_assets.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    raw=(KIT/'assessment/catalog-app.tar.gz').read_bytes()
    files=helper.unpack(raw,reg)
    ok('actual_signed_app_all_files',len(files)==len(reg['application_manifest']['files'])+1)
    try:helper.unpack(raw+b'changed',reg)
    except ValueError:checks.append('modified_app_rejected')
    else:raise AssertionError('modified app accepted')
    for name in ('jdu-catalog/../escape','jdu-catalog/link'):
        output=io.BytesIO()
        with tarfile.open(fileobj=output,mode='w:gz') as tar:
            member=tarfile.TarInfo(name)
            if name.endswith('link'):member.type=tarfile.SYMTYPE;member.linkname='/etc/passwd'
            else:member.size=1
            tar.addfile(member,io.BytesIO(b'x') if member.isfile() else None)
        evil=output.getvalue();digest=hashlib.sha256(evil).hexdigest()
        with patch.object(helper,'APP_HASH',digest):
            try:helper.unpack(evil,dict(reg,application_archive_sha256=digest))
            except ValueError:checks.append('unsafe_tar_rejected_'+name.rsplit('/',1)[-1])
            else:raise AssertionError('unsafe tar accepted')
    with tempfile.TemporaryDirectory() as tmp:
        target=Path(tmp)/'file'
        with patch.object(os,'O_NOFOLLOW',getattr(os,'O_NOFOLLOW',0),create=True), patch.object(os,'fchmod',getattr(os,'fchmod',lambda fd,mode:None),create=True):
            helper.retain(target,b'one');helper.retain(target,b'one')
            try:helper.retain(target,b'two')
            except ValueError:checks.append('different_existing_file_preserved')
            else:raise AssertionError('overwritten resource')
        ok('same_resource_retry',target.read_bytes()==b'one')
    pins=json.loads((ROOT/'resources/release-map.json').read_text())
    ok('resource_hash_pins',all(hashlib.sha256((KIT/n).read_bytes()).hexdigest()==v for n,v in pins['import_pins'].items()) and
       all(hashlib.sha256((ROOT/'resources'/n).read_bytes()).hexdigest()==v for n,v in pins['resource_pins'].items()))
    import base64,zlib
    contents={n:base64.b64encode((KIT/'assessment'/n).read_bytes()).decode() for n in ('catalog-app.tar.gz','registry.py','assessment-registry.json','database_secret.py')}
    contents['offline_assets.py']=base64.b64encode((ROOT/'resources/offline_assets.py').read_bytes()).decode()
    spec=importlib.util.spec_from_file_location('lesson_staging',ROOT/'resources/stage_resources.py')
    staging=importlib.util.module_from_spec(spec);spec.loader.exec_module(staging)
    request=dict(files=contents,lab_id='fictional-lab',deployment_id='00000000-0000-4000-8000-000000000000',instance_id='i-00000000000000000',role='web')
    packed_command=staging.packed_command(request)
    ok('ssm_public_resources_bounded',len(packed_command.encode())<60000)
    ast.parse(staging.GUEST)
    ok('ssm_resources_do_not_configure_services',not any(x in staging.GUEST for x in ('systemctl','ALTER ROLE','CREATE ROLE','chpasswd','apt-get','progress.credentials')))
    for sub in ('','foundation'):
        for name in ('STUDENT.md','TEACHER.md'):
            ok('distribution_reference_'+sub+'_'+name,(ROOT/'distribution'/sub/name).read_bytes()==(KIT/sub/name).read_bytes())
    package=ROOT/'output/web-lab-pm-r1.zip'
    with zipfile.ZipFile(package) as z:
        hashes=json.loads(z.read('web-lab-pm-r1/TEACHING-FILE-HASHES.json'))
        ok('zip_exact_inventory',set(z.namelist())=={'web-lab-pm-r1/'+p for p in hashes}|{'web-lab-pm-r1/TEACHING-FILE-HASHES.json'})
        ok('zip_all_hashes',all(hashlib.sha256(z.read('web-lab-pm-r1/'+p)).hexdigest()==v for p,v in hashes.items()))
    result=dict(scope='D12_P_M_materials_local_checks_not_AWS_walkthrough',checked_on=date.today().isoformat(),browser_guide_revision='2026-10-30',
        languages=list(LANGS),material_revision=MATERIAL_REVISION,practice_tasks=7,practice_steps=49,
        explained_steps=len(STEP_NOTES),module_understanding_questions=len(MODULE_NOTES),communication_routes=len(ROUTES),
        worked_output_examples=len(OUTPUT_EXAMPLES),mission_tasks=7,scored_checks=62,raw_points=62,
        checks_passed=len(checks),bash_blocks_syntax_checked=fences,
        pdfs={p.name:dict(pages=len(PdfReader(p).pages),bytes=p.stat().st_size) for p in (ROOT/'output/pdf').glob('*.pdf')},
        distribution_id=pins['distribution_id'],registry_sha256=EXPECTED_REGISTRY,package_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),
        new_material_AWS_walkthrough=False,native_language_review=False,teacher_visual_review=False,class_ready=False)
    (ROOT/'validation.public.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__':main()
