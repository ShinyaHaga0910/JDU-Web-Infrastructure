"""Render every handbook page and check text bounds. This is not teacher visual approval."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT.parents[1]/'tmp/pdfs/web-lab-pm-r1.1')
    args=parser.parse_args()
    commands={name:shutil.which(name) for name in ('pdftotext','pdftoppm')}
    if not all(commands.values()):raise SystemExit('Install Poppler or add its bin directory to PATH.')
    args.output.mkdir(parents=True,exist_ok=True)

    def check(path):
        target=args.output/path.stem
        target.mkdir(exist_ok=True)
        xml=target/'bounds.xml'
        subprocess.run([commands['pdftotext'],'-bbox',str(path),str(xml)],check=True,capture_output=True)
        pages=[p for p in ET.parse(xml).iter() if p.tag.endswith('page')]
        issues=[]
        for number,page in enumerate(pages,1):
            width=float(page.attrib['width']);height=float(page.attrib['height'])
            for word in page.iter():
                if not word.tag.endswith('word'):continue
                if (float(word.attrib['xMin'])<35 or float(word.attrib['xMax'])>width-35
                    or float(word.attrib['yMin'])<8 or float(word.attrib['yMax'])>height-8):
                    issues.append(dict(page=number,word=word.text))
        prefix=target/'page'
        subprocess.run([commands['pdftoppm'],'-r','65','-png',str(path),str(prefix)],check=True,capture_output=True)
        rendered=sorted(target.glob('page-*.png'))
        expected=len(PdfReader(path).pages)
        if len(rendered)!=expected:raise ValueError('Rendered page count differs: '+path.name)
        for png in rendered:
            with Image.open(png) as image:
                rgb=image.convert('RGB')
                if rgb.width<500 or rgb.height<700:raise ValueError('Unexpected page dimensions: '+png.name)
                if ImageChops.difference(rgb,Image.new('RGB',rgb.size,'white')).getbbox() is None:
                    raise ValueError('Blank rendered page: '+png.name)
        return dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            pages=expected,rendered_pages=len(rendered),out_of_bounds_words=len(issues),issues=issues[:3])

    paths=sorted((ROOT/'output/pdf').glob('*.pdf'))
    with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(check,paths))
    result=dict(scope='D12_P_M_all_page_render_and_bounds_not_visual_approval',checked_on='2026-10-23',
        pdfs=results,pdf_pages_checked=sum(r['pages'] for r in results),
        rendered_pages=sum(r['rendered_pages'] for r in results),
        out_of_bounds_words=sum(r['out_of_bounds_words'] for r in results),
        teacher_visual_review=False,native_language_review=False,new_material_AWS_walkthrough=False)
    (ROOT/'rendering.public.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=True))
    if result['out_of_bounds_words']:raise SystemExit(1)

if __name__=='__main__':main()
