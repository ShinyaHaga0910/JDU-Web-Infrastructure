"""Rebuild every current chapter, then publish a version-checked single PDF."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import sys

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from pypdf.generic import Fit
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from build_chapter01 import ROOT, SANS, SERIF, blocks


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(value: str) -> str:
    return re.sub(r'\s+', '', value)


def front_matter(chapters: list[dict], published: date) -> tuple[BytesIO, list[tuple]]:
    stream = BytesIO()
    page = canvas.Canvas(stream, pagesize=A4)
    width, height = A4
    page.setTitle('Webインフラストラクチャー教科書 第1〜13章 統合版')
    page.setAuthor('JDU')
    page.setFillColor(HexColor('#2165a7'))
    page.rect(20*mm, height-47*mm, 155*mm, 2*mm, fill=1, stroke=0)
    page.setFont('JSans', 25)
    page.drawString(20*mm, height-72*mm, 'Webインフラストラクチャー')
    page.setFont('JSans', 38)
    page.drawString(20*mm, height-95*mm, '教科書')
    page.setFillColor(HexColor('#16745b'))
    page.setFont('JSans', 17)
    page.drawString(20*mm, height-116*mm, '第1〜13章 統合版')
    body = ParagraphStyle('CoverBody', fontName='JSans', fontSize=12,
                          leading=22, wordWrap='CJK', textColor=HexColor('#193047'))
    paragraph = Paragraph('学校の備品管理システムを題材に、Web・DNS・DBと、'
                          'アプリを動かすインフラストラクチャーを学ぶ。', body)
    _, ph = paragraph.wrap(155*mm, 60*mm)
    paragraph.drawOn(page, 20*mm, height-148*mm-ph)
    page.setFillColor(HexColor('#667c91'))
    page.setFont('JSans', 11)
    page.drawString(20*mm, 55*mm, f'{published.year}年{published.month}月{published.day}日 更新')
    page.drawString(20*mm, 45*mm, 'JDU')
    page.showPage()

    page.setFillColor(HexColor('#193047'))
    page.setFont('JSans', 24)
    page.drawString(20*mm, height-30*mm, '目次')
    page.setFont('JSans', 9)
    page.drawString(20*mm, height-40*mm, '章名を選ぶと、その章の開始ページへ移動できます。')
    page.drawRightString(width-20*mm, height-51*mm, '通しページ')
    style = ParagraphStyle('Contents', fontName='JSans', fontSize=10.5,
                           leading=16, wordWrap='CJK', textColor=HexColor('#193047'))
    y = height-58*mm
    links = []
    for chapter in chapters:
        paragraph = Paragraph(chapter['title'], style)
        _, ph = paragraph.wrap(width-62*mm, 34)
        if ph > 32:
            raise ValueError('Contents title exceeds its row')
        paragraph.drawOn(page, 20*mm, y-ph)
        page.setFont('JSans', 10.5)
        page.drawRightString(width-20*mm, y-12, str(chapter['start_page']))
        page.setStrokeColor(HexColor('#d5dfe8'))
        page.line(20*mm, y-27, width-20*mm, y-27)
        links.append(((20*mm, y-28, width-20*mm, y+3), chapter['start_page']-1))
        y -= 35
    page.showPage()
    page.save()
    stream.seek(0)
    return stream, links


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', type=date.fromisoformat, required=True,
                        help='Publication date in the teaching timezone, YYYY-MM-DD')
    args = parser.parse_args()
    pdfmetrics.registerFont(TTFont('JSans', str(SANS)))
    pdfmetrics.registerFont(TTFont('JSerif', str(SERIF)))

    sources = []
    inputs = set((ROOT/'build').glob('*.py'))
    for number in range(1, 14):
        matches = list((ROOT/'docs/ja').glob(f'{number:02}-*.md'))
        if len(matches) != 1:
            raise ValueError(f'Expected one source for chapter {number}')
        source = matches[0]
        sources.append((number, source))
        inputs.add(source)
        for kind, value in blocks(source.read_text(encoding='utf-8')):
            if kind == 'image':
                image = (source.parent/value[1]).resolve()
                if image.parent != (ROOT/'assets/figures').resolve():
                    inputs.add(image)
    snapshot = {str(path.resolve()): digest(path) for path in sorted(inputs)}
    font_snapshot = {str(path): digest(path) for path in (SANS, SERIF)}
    chapters = []
    next_page = 3
    for number, source in sources:
        result = subprocess.run([sys.executable, str(ROOT/f'build/build_chapter{number:02}.py')],
                                check=True, capture_output=True, text=True, encoding='utf-8')
        pdf = ROOT/f'output/pdf/web_textbook_ch{number:02}_ja.pdf'
        report_file = ROOT/('validation.public.json' if number == 1
                           else f'chapter{number:02}.validation.public.json')
        report = json.loads(report_file.read_text(encoding='utf-8'))
        if report['sha256'] != digest(pdf) or report['missing_text']:
            raise ValueError(f'Chapter {number} was not regenerated correctly')
        text = source.read_text(encoding='utf-8')
        title = text.splitlines()[0].removeprefix('# ')
        if not title.startswith(f'第{number}章 '):
            raise ValueError(f'Incorrect chapter title: {title}')
        images = []
        for kind, value in blocks(text):
            if kind == 'image':
                image = (source.parent/value[1]).resolve()
                images.append({'path': image.relative_to(ROOT).as_posix(), 'sha256': digest(image)})
        chapters.append({'chapter': number, 'title': title,
                         'source': source.relative_to(ROOT).as_posix(),
                         'source_sha256': digest(source),
                         'pdf': pdf.relative_to(ROOT).as_posix(), 'pdf_sha256': digest(pdf),
                         'pages': report['pages'], 'start_page': next_page,
                         'end_page': next_page+report['pages']-1,
                         'figures': images, 'text_blocks': report['text_blocks_checked']})
        next_page += report['pages']
        print(f'Rebuilt chapter {number}: {report["pages"]} pages', flush=True)
    if any(digest(Path(path)) != value for path, value in snapshot.items()):
        raise RuntimeError('An input changed during generation; rebuild from the current sources')
    if any(digest(Path(path)) != value for path, value in font_snapshot.items()):
        raise RuntimeError('A font changed during generation')

    front, links = front_matter(chapters, args.date)
    writer = PdfWriter()
    writer.append(PdfReader(front), import_outline=False)
    for chapter in chapters:
        reader = PdfReader(ROOT/chapter['pdf'])
        writer.append(reader, import_outline=False)
        parent = writer.add_outline_item(chapter['title'], chapter['start_page']-1,
                                         fit=Fit.fit(), is_open=False)
        page_text = [normalized(p.extract_text() or '') for p in reader.pages]
        for kind, value in blocks((ROOT/chapter['source']).read_text(encoding='utf-8')):
            if kind != 'heading' or value[0] != 2:
                continue
            title = value[1]
            if not re.match(r'^\d+\.\d+ ', title) and title not in ('章末問題', '章末解答', '参考資料'):
                continue
            found = next((i for i, text in enumerate(page_text) if normalized(title) in text), None)
            if found is None:
                raise ValueError(f'Cannot locate heading: {title}')
            writer.add_outline_item(title, chapter['start_page']-1+found, parent=parent)
    for rect, destination in links:
        writer.add_annotation(1, Link(rect=rect, target_page_index=destination, fit=Fit.fit()))

    width, height = A4
    for number, page in enumerate(writer.pages, 1):
        overlay = BytesIO()
        stamp = canvas.Canvas(overlay, pagesize=A4)
        stamp.setFillColor(HexColor('#ffffff'))
        stamp.rect(width-45*mm, 9*mm, 30*mm, 7*mm, fill=1, stroke=0)
        stamp.setFillColor(HexColor('#667c91'))
        stamp.setFont('JSans', 8)
        stamp.drawRightString(width-18*mm, 12*mm, str(number))
        stamp.save()
        overlay.seek(0)
        page.merge_page(PdfReader(overlay).pages[0])
    writer.page_mode = '/UseOutlines'
    writer.add_metadata({'/Title': 'Webインフラストラクチャー教科書 第1〜13章 統合版',
                         '/Author': 'JDU', '/Subject': f'{args.date.isoformat()} 更新'})
    output = ROOT/'output/pdf/web_textbook_ja.pdf'
    with output.open('wb') as target:
        writer.write(target)
    combined = PdfReader(output)
    if len(combined.pages) != next_page-1:
        raise ValueError('Incorrect combined page count')
    for chapter in chapters:
        original = PdfReader(ROOT/chapter['pdf'])
        for local, page in enumerate(original.pages):
            merged = combined.pages[chapter['start_page']-1+local]
            if normalized(page.extract_text() or '') not in normalized(merged.extract_text() or ''):
                raise ValueError(f'Combined text differs from chapter {chapter["chapter"]}, page {local+1}')
    if any(digest(Path(path)) != value for path, value in snapshot.items()):
        raise RuntimeError('An input changed before publication completed')
    report = {'date': args.date.isoformat(), 'chapters': chapters,
              'total_pages': len(combined.pages), 'front_matter_pages': 2,
              'chapter_count': 13, 'contents_links': len(links),
              'input_snapshot': {str(Path(p).relative_to(ROOT)): sha for p, sha in snapshot.items()},
              'fonts': font_snapshot, 'sha256': digest(output),
              'all_chapters_rebuilt': True, 'source_inputs_unchanged_during_build': True,
              'chapter_text_preserved': True, 'teacher_visual_review': 'not performed',
              'student_trial': 'not performed', 'aws_operations': 'none'}
    (ROOT/'textbook.validation.public.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'total_pages': report['total_pages'], 'chapters': 13,
                      'sha256': report['sha256']}))


if __name__ == '__main__':
    main()
