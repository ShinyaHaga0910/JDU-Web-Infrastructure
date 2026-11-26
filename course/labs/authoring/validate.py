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
from curriculum import ACTIVE_NUMBERS, ACTIVE_ORDER, active_registry, display_task, display_missions, task_page
MODULES_BY_NUMBER = {int(m["id"][1:]): m for m in MODULES}
MODULES = [MODULES_BY_NUMBER[n] for n in ACTIVE_NUMBERS]
from build import KIT,EXPECTED_REGISTRY,MATERIAL_REVISION
from checks import CHECKS
from diagrams import diagram_stem
from command_notes import annotated_blocks,command_groups,executable_only,explanation,CONFIG_STEPS
from PIL import Image
import xml.etree.ElementTree as ET
from explanations import LABELS,STEP_NOTES,MODULE_NOTES,READING,ROUTES,OUTPUT_EXAMPLES


class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.ids=set();self.lang=None;self.tables=0;self.bad_th=0;self.main=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='html':self.lang=a.get('lang')
        if tag=='a' and a.get('href'):self.links.append(a['href'])
        if tag=='img' and a.get('src'):self.links.append(a['src'])
        if a.get('id'):self.ids.add(a['id'])
        if tag=='main':self.main+=1
        if tag=='table':self.tables+=1
        if tag=='th' and a.get('scope')!='col':self.bad_th+=1


def main():
    checks=[]
    def published(text):
        return display_missions(text).replace('\u2013','-').replace('\u2014','-')
    def ok(name,condition):
        if not condition:raise AssertionError(name)
        checks.append(name)
    registry_raw=(KIT/'assessment/assessment-registry.json').read_bytes();reg=active_registry(json.loads(registry_raw))
    ok('frozen_registry_sha256',hashlib.sha256(registry_raw).hexdigest()==EXPECTED_REGISTRY)
    ok('active_mission_points_59',reg['raw_points_by_mission']==dict(M1=8,M2=13,M4=9,M5=13,M6=16))
    parser=MarkdownIt('commonmark',{'html':False}).enable('table')
    docs={};code={};fences=0
    for lang in LANGS:
        for kind in ('practice','missions'):
            path=ROOT/'docs'/lang/(kind+'-full.md');value=path.read_text(encoding='utf-8');docs[lang,kind]=value
            tokens=parser.parse(value)
            ok(f'{lang}_{kind}_browser_grading',not any(x in value for x in
                ('jdu-web-check','jdu-web-my-progress','--functional','--no-submit','--retry','--prepare-stop','--observe-stopped')))
            code[lang,kind]=[(t.info,t.content) for t in tokens if t.type=='fence']
            prefix = 'P' if kind=='practice' else 'M'
            ok(f'{lang}_{kind}_tasks',all(re.search(r'^## '+display_task(prefix+str(n))+r'\b',value,re.M) for n in ACTIVE_NUMBERS))
            ok(f'{lang}_{kind}_no_private_student_data',not any(x in value for x in
                ('965244652544','jdutestuser1@','?session=','X-Amz-Signature=','PRIVATE KEY','Fictional-Practice-Admin-Only')))
            if kind=='missions':
                ok(f'{lang}_mission_order',' → '.join(map(display_task,ACTIVE_ORDER)) in value)
                ok(f'{lang}_all_59_criteria',all(published(CHECKS[cid][lang]) in value
                   for t in reg['tasks'] if t['category']=='automated_mission' for cid in t['progress_scored_checks']))
            else:
                ok(f'{lang}_{kind}_working_guide',all(published(p[lang]) in value for p in READING))
                ok(f'{lang}_{kind}_routes',all(published(purpose[lang]) in value for _,_,_,purpose in ROUTES))
                for module in MODULES:
                    for i,step in enumerate(module['steps'],1):
                        key=f"{module['id']}.{i}"
                        block=re.search(r'^#### '+re.escape(key)+r'\b(.*?)(?=^#### |^## |\Z)',value,re.M|re.S)
                        ok(f'{lang}_explains_{key}',block is not None and (key not in STEP_NOTES or published(STEP_NOTES[key][lang]) in block[0]))
                    ok(f'{lang}_understanding_{module["id"]}',all(published(note[lang]) in value for note in MODULE_NOTES[module['id']].values()))
            pdf=PdfReader(ROOT/'output/pdf'/f'web_lab_{kind}_{lang}.pdf')
            text='\n'.join(page.extract_text() or '' for page in pdf.pages)
            ok(f'{lang}_{kind}_pdf_A4',all(abs(float(p.mediabox.width)-595.276)<1 and abs(float(p.mediabox.height)-841.890)<1 for p in pdf.pages))
            ok(f'{lang}_{kind}_pdf_text',len(text)>5000 and all(display_task(prefix+str(n)) in text for n in ACTIVE_NUMBERS) and '\ufffd' not in text and '\x00' not in text)
            images=sum(sum(obj.get_object().get('/Subtype')=='/Image' for obj in p.get('/Resources',{}).get('/XObject',{}).values()) for p in pdf.pages)
            ok(f'{lang}_{kind}_pdf_figures',images==(18 if kind=='practice' else 8))
            if kind=='practice':
                expected=sum(sum(active for active,_ in command_groups(s['code'])) for m in MODULES for i,s in enumerate(m['steps'],1) if s['code'] and (m['id'],i) not in CONFIG_STEPS)
                ok(f'{lang}_pdf_numbered_comments',len(re.findall(r'(?:#|--) \d+\.',text))==expected)
                ok(f'{lang}_pdf_comment_text',re.sub(r'\s+','',explanation('id -un',lang)) in re.sub(r'\s+','',text))
    for kind in ('practice','missions'):
        normalized={lang:[(info,executable_only(source)) for info,source in code[lang,kind]] for lang in LANGS}
        ok(kind+'_identical_executable_code_in_3_languages',normalized['ja']==normalized['ru']==normalized['uz'])
    for lang in LANGS:
        for kind,prefix in [('practice','P'),('missions','M')]:
            index=(ROOT/'docs'/lang/(kind+'.md')).read_text(encoding='utf-8')
            ok(f'{lang}_{kind}_index',all(f']({task_page(prefix+str(n))})' in index for n in ACTIVE_NUMBERS))
            for number in ACTIVE_NUMBERS:
                name=prefix+str(number)
                value=(ROOT/'docs'/lang/task_page(name)).read_text(encoding='utf-8')
                ok(f'{lang}_{name}_page',value.startswith('# '+display_task(name)+' '))
                if prefix=='P':
                    for step in range(1,len(MODULES_BY_NUMBER[number]['steps'])+1):
                        key=f'{name}.{step}'
                        ok(f'{lang}_{key}_page_step',f'### {key} ' in value and (key not in STEP_NOTES or published(STEP_NOTES[key][lang]) in value))
                else:
                    task=next(t for t in reg['tasks'] if t['id']==name)
                    criteria=task['progress_scored_checks']
                    valid_rows=(all(value.count(cid)==1 for cid in criteria) if name=='M0' else
                                all(f'| {i} | {published(CHECKS[cid][lang])} |' in value for i,cid in enumerate(criteria,1)))
                    ok(f'{lang}_{name}_page_checks',valid_rows)
    for lang in LANGS:
        for task in ('p0','m0'):
            text=(ROOT/'docs'/lang/(task+'.md')).read_text(encoding='utf-8')
            for filename in ('ec2-session-manager-instances.png', 'ec2-session-manager-connect.png'):
                ok(f'{lang}_{task}_{filename}', text.count(filename)==1)
    # Check Markdown paths too: GitHub is the primary reading entrance.
    for path in [ROOT/'README.md',ROOT/'TEACHER-NOTES.md',*(ROOT/'docs').rglob('*.md')]:
        for token in parser.parse(path.read_text(encoding='utf-8')):
            for child in token.children or []:
                if child.type not in ('link_open','image'):continue
                href=child.attrGet('src' if child.type=='image' else 'href');uri=urlparse(href)
                ok('retired_markdown_link_'+str(len(checks)),
                    Path(unquote(uri.path)).name not in ('start.md','portal.md')
                    and not (uri.hostname or '').endswith('.gpb.lambda-web.us-east-1.on.aws'))
                if uri.scheme:continue
                target=path.parent/unquote(uri.path) if uri.path else path
                ok('markdown_link_'+str(len(checks)),target.exists())
    annotations=0
    for module in MODULES:
        for number,step in enumerate(module['steps'],1):
            if not step['code']:continue
            for lang in LANGS:
                blocks=annotated_blocks(module['id'],number,step['code'],lang)
                joined='\n'.join(source for _,source in blocks)
                ok(f'{lang}_{module["id"]}_{number}_executable_preserved',executable_only(joined)==step['code'])
                if (module['id'],number) in CONFIG_STEPS:
                    ok(f'{lang}_{module["id"]}_{number}_config_unchanged',blocks==[('text',step['code'])])
                else:
                    expected=sum(active for active,_ in command_groups(step['code']))
                    comments=re.findall(r'^(?:#|--) (\d+)\. (.+)$',joined,re.M)
                    ok(f'{lang}_{module["id"]}_{number}_every_command_annotated',[int(n) for n,_ in comments]==list(range(1,expected+1)) and all(len(text)>=8 for _,text in comments))
                    if lang=='ja':annotations+=expected
    for lang in LANGS:
        for prefix in ('P','M'):
            for number in ACTIVE_NUMBERS:
                task=prefix+str(number)
                md=(ROOT/'docs'/lang/task_page(task)).read_text(encoding='utf-8')
                images=[c for t in parser.parse(md) for c in t.children or [] if c.type=='image']
                expected_images={'P0': 10, 'M0': 3, 'P1': 4}.get(task, 1)
                diagram_link=f'../../assets/{lang}/{diagram_stem(task)}.png'
                ok(f'{lang}_{task}_diagram_in_page',len(images)==expected_images
                   and images[0].attrGet('src')==diagram_link and bool(images[0].content.strip()))
                if task=='P0':
                    ok(f'{lang}_P0_resources_already_staged','stage_resources.py' not in md and 'YOUR-INSTALLATION-DIRECTORY' not in md)
                image_path=ROOT/'assets'/lang/(diagram_stem(task)+'.png')
                with Image.open(image_path) as img:ok(f'{lang}_{task}_diagram_size',img.size==(2080,1360))
                svg=ET.parse(image_path.with_suffix('.svg')).getroot()
                text_count=len(list(svg.iter('{http://www.w3.org/2000/svg}text')))
                ok(f'{lang}_{task}_editable_svg',svg.attrib['viewBox']=='0 0 1040 680' and text_count>=10)
                if task in ('P1','M1','M5','M6'):
                    tags=list(svg.iter('{http://www.w3.org/2000/svg}text'))
                    ok(f'{lang}_{task}_internet_aws_boundary',
                       any(t.text=='AWS' for t in tags) and any(t.text=='VPC  10.20.0.0/16' for t in tags)
                       and any(t.text=='IGW' and float(t.attrib['x'])==386 for t in tags)
                       and all(float(t.attrib['x'])>386 for t in tags if t.text=='EC2'))
                elif number in (1,5,6):
                    texts=list(svg.iter('{http://www.w3.org/2000/svg}text'))
                    boundary=440 if number==1 else 325
                    ok(f'{lang}_{task}_internet_aws_boundary',any(t.text=='AWS / VPC 10.20.0.0/16' for t in texts)
                        and any(t.text=='IGW' and float(t.attrib['x'])==boundary for t in texts)
                        and all(float(t.attrib['x'])>boundary for t in texts if t.text=='EC2'))
    ok('41_detailed_steps',sum(len(m['steps']) for m in MODULES)==41)
    for module in MODULES:
        for i,step in enumerate(module['steps'],1):
            fields = ('why','expect','trouble')
            if module['id']=='P0' and i in (1,2):
                fields = ('why',) if i==1 else ('why','expect')
            if module['id']=='P1' and i==5:
                fields = ('why','expect')
            ok(f'{module["id"]}.{i}_step_fields',all(all(step[field].values()) for field in fields))
    for info,source in code['ja','practice']+code['ja','missions']:
        if info=='bash':
            result=subprocess.run(['wsl.exe','bash','-n'],input=source,text=True,encoding='utf-8',capture_output=True)
            ok('bash_fence_'+str(fences+1),result.returncode==0)
            fences+=1
    for path in (ROOT/'output/html').rglob('*.html'):
        page=Page();page.feed(path.read_text(encoding='utf-8'))
        ok('html_structure_'+path.parent.name+'_'+path.stem,page.lang in LANGS and page.main==1 and page.bad_th==0)
        for href in page.links:
            uri=urlparse(href)
            ok('retired_html_link_'+str(len(checks)),
                Path(unquote(uri.path)).name not in ('start.html','portal.html')
                and not (uri.hostname or '').endswith('.gpb.lambda-web.us-east-1.on.aws'))
            if uri.scheme:continue
            target=(path.parent/unquote(uri.path)) if uri.path else path
            ok('html_link_'+str(len(checks))+' '+str(path.relative_to(ROOT))+' -> '+href,target.exists())
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
    result=dict(scope='D12_P_M_materials_local_checks_not_AWS_walkthrough',checked_on=date.today().isoformat(),
        languages=list(LANGS),material_revision=MATERIAL_REVISION,practice_tasks=6,practice_steps=41,
        task_pages=36,task_diagrams=36,numbered_command_comments_per_language=annotations,executable_source_preserved=True,
        explained_steps=sum(key.split(".")[0] in ACTIVE_ORDER for key in STEP_NOTES),module_understanding_questions=sum('question' in MODULE_NOTES[module['id']] for module in MODULES),communication_routes=len(ROUTES),
        worked_output_examples=len(OUTPUT_EXAMPLES),mission_tasks=6,scored_checks=64,raw_points=64,
        checks_passed=len(checks),bash_blocks_syntax_checked=fences,
        pdfs={p.name:dict(pages=len(PdfReader(p).pages),bytes=p.stat().st_size) for p in (ROOT/'output/pdf').glob('*.pdf')},
        distribution_id=pins['distribution_id'],registry_sha256=EXPECTED_REGISTRY,package_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),
        new_material_AWS_walkthrough=False,native_language_review=False,teacher_visual_review=False,class_ready=False)
    (ROOT/'validation.public.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__':main()
