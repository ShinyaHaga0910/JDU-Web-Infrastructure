"""Build the editable chapter, diagrams and reading outputs without AWS access."""
from pathlib import Path
import hashlib
import html
import json
import math
import os
import re

from PIL import Image as PILImage, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, Preformatted
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/ja/01-web-system.md'
ASSETS = ROOT / 'assets/figures'
HTML_OUT = ROOT / 'output/html'
PDF_OUT = ROOT / 'output/pdf'
SANS = Path(os.environ.get('JDU_FONT_SANS', r'C:\Windows\Fonts\NotoSansJP-VF.ttf'))
SERIF = Path(os.environ.get('JDU_FONT_SERIF', r'C:\Windows\Fonts\NotoSerifJP-VF.ttf'))
INK, BLUE, GREEN, AMBER = '#193047', '#2165a7', '#16745b', '#9d651a'


class Scene:
    """Shared vector/raster scene; node text remains editable in SVG."""
    def __init__(self, width, height, title):
        self.width, self.height = width, height
        self.image = PILImage.new('RGB', (width, height), 'white')
        self.draw = ImageDraw.Draw(self.image)
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
                    f'<title>{html.escape(title)}</title>',
                    '<rect width="100%" height="100%" fill="white"/>']

    def rect(self, x, y, w, h, fill='#ffffff', stroke='#a9b8c7', radius=18):
        self.draw.rounded_rectangle((x, y, x+w, y+h), radius=radius, fill=fill, outline=stroke, width=2)
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')

    def text(self, x, y, value, size=26, color=INK, center=False):
        font = ImageFont.truetype(str(SANS), size)
        anchor = 'mt' if center else 'lt'
        bbox=self.draw.textbbox((x,y),value,font=font,anchor=anchor)
        if bbox[0]<0 or bbox[1]<0 or bbox[2]>self.width or bbox[3]>self.height:
            raise ValueError(f'Diagram text outside canvas: {value}')
        self.draw.text((x, y), value, font=font, fill=color, anchor=anchor)
        self.svg.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="Noto Sans JP, sans-serif" font-size="{size}" dominant-baseline="text-before-edge" text-anchor="{"middle" if center else "start"}">{html.escape(value)}</text>')

    def arrow(self, points, color=BLUE, dashed=False, width=4):
        for start, end in zip(points, points[1:]):
            dx, dy = end[0]-start[0], end[1]-start[1]
            distance = math.hypot(dx, dy)
            if dashed:
                for pos in range(0, int(distance), 22):
                    a, b = pos/distance, min(pos+13, distance)/distance
                    self.draw.line((start[0]+dx*a, start[1]+dy*a, start[0]+dx*b, start[1]+dy*b), fill=color, width=width)
            else:
                self.draw.line((start, end), fill=color, width=width)
        a, b = points[-2:]
        angle = math.atan2(b[1]-a[1], b[0]-a[0])
        head = [b, (b[0]-16*math.cos(angle-.45), b[1]-16*math.sin(angle-.45)),
                (b[0]-16*math.cos(angle+.45), b[1]-16*math.sin(angle+.45))]
        self.draw.polygon(head, fill=color)
        poly = ' '.join(f'{x},{y}' for x,y in points)
        dash = ' stroke-dasharray="13 9"' if dashed else ''
        self.svg.append(f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="{width}"{dash}/><polygon points="{" ".join(f"{x},{y}" for x,y in head)}" fill="{color}"/>')

    def node(self, x, y, w, role, ip, sg):
        self.rect(x, y, w, 150, '#ffffff', '#607f9f')
        self.text(x+w/2, y+12, 'EC2', 26, center=True)
        self.text(x+w/2, y+47, role, 32, center=True)
        self.text(x+w/2, y+94, ip, 23, center=True)
        self.text(x+w/2, y+124, sg, 19, color='#536a80', center=True)

    def save(self, stem):
        self.image.save(ASSETS / f'{stem}.png', dpi=(220,220))
        (ASSETS / f'{stem}.svg').write_text('\n'.join(self.svg+['</svg>']), encoding='utf-8')


def figures():
    s = Scene(1600, 1340, 'AWS内のInternet Gatewayと5台の配置、閲覧と管理の独立した経路')
    s.text(40, 14, '図1-1  システムの全体構成', 36)
    s.rect(60, 75, 380, 125, '#f5f7fa')
    s.text(250, 94, '利用者PC', 32, center=True)
    s.text(250, 142, 'ブラウザ / RDP', 25, center=True)
    s.text(640, 85, '一般閲覧：HTTP / TCP80', 27, BLUE)
    s.text(640, 140, '管理接続：RDP / TCP3389', 27, GREEN)
    s.text(75, 211, 'インターネット経由', 23)
    s.rect(35, 245, 1530, 1030, '#f8fafc', '#7991aa')
    s.text(65, 264, 'AWS', 32)
    s.rect(650, 300, 400, 140, '#ffffff', '#7991aa')
    s.text(850, 317, 'Internet Gateway', 29, center=True)
    s.text(850, 368, 'VPCに接続するAWSの機能', 24, center=True)
    # Two independent paths, including the Internet-to-gateway segment.
    s.arrow([(440,105),(560,105),(560,340),(650,340)], BLUE)
    s.arrow([(440,155),(510,155),(510,395),(650,395)], GREEN, True)
    s.rect(60, 485, 1480, 740, '#ffffff', '#7991aa')
    s.text(85, 500, 'VPC 10.20.0.0/16', 29)
    s.rect(95, 565, 1410, 265, '#edf5fc', '#9ebed8')
    s.text(115, 580, '公開サブネット 10.20.1.0/24', 27)
    s.rect(95, 915, 1410, 245, '#f1f7f3', '#a7c2af')
    s.text(115, 930, '非公開サブネット 10.20.2.0/24', 27)
    s.arrow([(750,440),(750,625),(345,625),(345,650)], GREEN, True)
    s.text(780, 452, 'RDP / TCP3389', 25, GREEN)
    s.arrow([(1050,340),(1210,340),(1210,650)], BLUE)
    s.text(1230, 452, 'HTTP / TCP80', 25, BLUE)
    s.node(145,650,400,'踏み台サーバー','10.20.1.10','SG-Bastion')
    s.node(1010,650,400,'Webサーバー','10.20.1.20','SG-Web')
    s.node(120,990,400,'DNSサーバー','10.20.2.10','SG-DNS')
    s.node(600,990,400,'DBサーバー','10.20.2.20','SG-DB')
    s.node(1080,990,400,'配布サーバー','10.20.2.30','SG-Repo')
    s.arrow([(545,725),(1010,725)], GREEN, True)
    s.text(580,662,'踏み台から内部を管理',23,GREEN)
    s.text(605,690,'SSH / TCP22',25,GREEN)
    s.arrow([(1210,800),(1210,870),(800,870),(800,990)],BLUE)
    s.text(850,840,'アプリ → DB / TCP5432',23,BLUE)
    s.text(100,1182,'各EC2の上でUbuntuが動き、EBSへファイルとデータを保存する。',25)
    s.text(100,1241,'名前解決・配布・管理画面・SSMの経路は本文の通信表を参照。',24)
    s.text(60,1295,'青い実線：一般利用・DB要求　　緑の破線：管理接続　　矢印：要求方向（応答は逆向き）',23)
    s.save('fig01-system-overview')

    s = Scene(1600, 680, 'Web内のNginx・Gunicorn・アプリと別EC2のDB')
    s.text(40, 16, '図1-3  Webの内部とDBの関係',36)
    s.rect(290,110,940,400,'#edf5fc','#9ebed8')
    s.text(760,126,'EC2',26,center=True)
    s.text(760,169,'Webサーバー',32,center=True)
    for x,w,title,sub in [(325,270,'Nginx','HTTPの入口'),(720,455,'Gunicorn + Django','教員提供アプリを実行')]:
        s.rect(x,245,w,140)
        s.text(x+w/2,268,title,29,center=True)
        s.text(x+w/2,318,sub,24,center=True)
    s.rect(20,245,220,140,'#f5f7fa')
    s.text(130,265,'利用者PC',27,center=True)
    s.text(130,310,'ブラウザ',26,center=True)
    s.rect(1280,245,300,140,'#f1f7f3')
    s.text(1430,257,'EC2',24,center=True)
    s.text(1430,295,'DBサーバー',27,center=True)
    s.text(1430,340,'PostgreSQL',23,center=True)
    s.arrow([(240,315),(325,315)])
    s.text(245,195,'80',24,BLUE)
    s.arrow([(595,315),(720,315)])
    s.text(603,195,'8000',24,BLUE)
    s.arrow([(1175,315),(1280,315)])
    s.text(1205,195,'5432',24,BLUE)
    s.text(340,425,'Nginx → 127.0.0.1:8000（同じホスト内）',26)
    s.text(340,466,'DB名はWeb側が内部DNSで解決する。',25)
    s.text(50,552,'要求：ブラウザ → Nginx → アプリ → DB　　結果：同じ経路を逆向きに返す。',26)
    s.text(50,603,'数値はTCPのポート。IGW等の経路、DNS、管理8080、静的資源は省略。',24)
    s.save('fig02-web-and-app')

    s = Scene(1600, 620, 'EC2 Webサーバーで静的ファイルを配信する構成')
    s.text(40,18,'図1-5  練習・課題1で構築するサービス',36)
    s.rect(40,165,330,155,'#f5f7fa')
    s.text(205,188,'HTTPクライアント',28,center=True)
    s.text(205,239,'IP指定でファイルを要求',25,center=True)
    s.rect(570,110,975,335,'#edf5fc','#9ebed8')
    s.text(1057,121,'EC2',26,center=True)
    s.text(1057,164,'Webサーバー',32,center=True)
    s.rect(610,215,290,140)
    s.text(755,236,'Nginx',32,center=True)
    s.text(755,287,'静的ファイルを配信',24,center=True)
    s.rect(1090,215,405,140)
    s.text(1292,236,'保存したテキスト',29,center=True)
    s.text(1292,287,'Web内の指定ファイル',24,center=True)
    s.arrow([(370,245),(610,245)])
    s.text(393,195,'HTTP / TCP80',24,BLUE)
    s.arrow([(900,285),(1090,285)])
    s.text(926,237,'読み取り',24,BLUE)
    s.text(610,385,'要求に対応するアクセスログもWeb内へ残る。',26)
    s.text(55,493,'Nginxが保存したファイルを読み取り、HTTPの応答として内容を返す。',27)
    s.text(55,548,'この図は静的配信の例。DBの値から画面を作る構成は図1-3を参照。',27)
    s.save('fig03-first-mission')

    s = Scene(1600, 850, 'SSHのCLI操作とRDPのGUI操作の比較')
    s.text(40,18,'図1-2  SSHとRDPによる操作の比較',36)
    for x,title in [(40,'SSH：端末でCLI操作'),(820,'RDP：デスクトップでGUI操作')]:
        s.rect(x,90,740,670,'#f8fafc')
        s.text(x+30,108,title,30)
    s.rect(85,175,650,70)
    s.text(410,191,'管理用の踏み台',28,center=True)
    s.rect(865,175,650,70)
    s.text(1190,191,'利用者PC',28,center=True)
    s.arrow([(410,245),(410,325)],GREEN)
    s.text(435,265,'SSH / TCP22',24,GREEN)
    s.arrow([(1190,245),(1190,325)],GREEN,True)
    s.text(1215,265,'RDP / TCP3389',24,GREEN)
    for x,role in [(85,'Webサーバー'),(865,'踏み台サーバー')]:
        s.rect(x,325,650,360,'#edf5fc','#9ebed8')
        s.text(x+325,340,'EC2',26,center=True)
        s.text(x+325,380,role,30,center=True)
    s.rect(120,435,580,195,'#193047','#193047',8)
    s.text(145,457,'ubuntu@web:~$ hostname',25,'#ffffff')
    s.text(145,501,'web',25,'#ffffff')
    s.text(145,545,'ubuntu@web:~$ pwd',25,'#ffffff')
    s.text(145,589,'/home/ubuntu',25,'#ffffff')
    s.rect(900,435,580,195,'#f0ecfa','#b3a4ce',8)
    s.rect(900,435,580,36,'#ddd5ed','#b3a4ce',8)
    s.text(920,440,'Ubuntu デスクトップ',20)
    for x,label in [(925,'ファイル'),(1110,'ブラウザ'),(1295,'端末')]:
        s.rect(x,492,145,65,'#ffffff','#b3a4ce',8)
        s.text(x+72,509,label,22,center=True)
    s.text(925,587,'アイコンやボタンをマウスで操作',24)
    s.text(70,709,'文字のコマンドを入力して操作する',28)
    s.text(850,709,'画面のボタンやアイコンを操作する',28)
    s.text(50,790,'今回の使い方を比較したイメージ。RDPのデスクトップ内でも端末を使える。',25)
    s.save('fig04-ssh-rdp')

    s = Scene(1600,1150,'VPCの公開・非公開サブネットと通信許可の例')
    red='#ac3747'
    s.text(40,18,'図1-4  公開・非公開サブネットと通信の許可',34)
    s.rect(40,100,300,135,'#f5f7fa')
    s.text(190,120,'利用者PC',28,center=True)
    s.text(190,167,'インターネット側',24,center=True)
    s.rect(400,80,1150,980,'#f8fafc','#7991aa')
    s.text(425,94,'AWS',30)
    s.rect(850,125,360,130)
    s.text(1030,143,'Internet Gateway',27,center=True)
    s.text(1030,189,'VPCとInternetの接続',24,center=True)
    s.rect(440,300,1060,730,'#ffffff','#7991aa')
    s.text(470,315,'VPC（Virtual Private Cloud）',27)
    s.rect(480,380,980,220,'#edf5fc','#9ebed8')
    s.text(500,393,'公開サブネット',27)
    s.rect(480,680,980,340,'#f1f7f3','#a7c2af')
    s.text(500,695,'非公開サブネット',27)
    s.rect(770,435,300,135)
    s.text(920,446,'EC2',24,center=True)
    s.text(920,485,'Webサーバー',28,center=True)
    s.text(920,530,'SG-Web',21,center=True)
    for x,y,role,sg in [(1070,730,'DBサーバー','SG-DB'),(510,870,'DNSサーバー','SG-DNS'),(1070,870,'配布サーバー','SG-Repo')]:
        s.rect(x,y,300,125)
        s.text(x+150,y+9,'EC2',24,center=True)
        s.text(x+150,y+46,role,28,center=True)
        s.text(x+150,y+91,sg,20,center=True)
    s.arrow([(340,165),(850,165)])
    s.text(495,126,'HTTP / TCP80',24,BLUE)
    s.arrow([(1210,190),(1490,190),(1490,495),(1070,495)])
    s.text(1230,250,'HTTP / TCP80',23,BLUE)
    s.arrow([(920,570),(920,640),(1220,640),(1220,730)])
    s.text(940,605,'SG-DB：WebからのTCP5432を許可',23,BLUE)
    s.arrow([(810,935),(1070,935)])
    s.text(825,882,'SG-Repoで許可',23,BLUE)
    s.text(850,970,'TCP80',23,BLUE)
    s.arrow([(340,215),(380,215),(380,805),(1020,805)],red,True)
    s.text(990,769,'×',51,red,center=True)
    s.text(45,306,'インターネットから',25,red)
    s.text(45,350,'DBへ直接接続不可',25,red)
    s.text(50,1092,'青：許可する通信の例　　赤と×：直接接続できない　　VPC内でもSGの許可が必要',25)
    s.save('fig05-network-boundaries')


def inline(text, pdf=False):
    text = html.escape(text)
    text = re.sub(r'`([^`]+)`', lambda m: ('<font name="JSans" size="9">'+m[1]+'</font>') if pdf else '<code>'+m[1]+'</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>' if pdf else r'<strong>\1</strong>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: f'<a href="{m[2]}"'+(' color="#2165a7"' if pdf else '')+f'>{m[1]}</a>', text)
    return text


def blocks(text):
    lines=text.splitlines(); i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line: i+=1; continue
        if line.startswith('```'):
            code=[]; i+=1
            while i<len(lines) and not lines[i].startswith('```'):
                code.append(lines[i]); i+=1
            yield ('code','\n'.join(code)); i+=1; continue
        image=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line)
        if image: yield ('image',image.groups()); i+=1; continue
        heading=re.match(r'^(#{1,4}) (.+)',line)
        if heading: yield ('heading',(len(heading[1]),heading[2])); i+=1; continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',c) for c in cells): rows.append(cells)
                i+=1
            yield ('table',rows); continue
        if re.match(r'^- ',line): yield ('bullet',line[2:]); i+=1; continue
        para=[line]; i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#{1,4} |!\[|\||- |```)',lines[i].strip()):
            para.append(lines[i].strip()); i+=1
        yield ('paragraph',''.join(para))


def build(*, source=SOURCE, chapter=1, diagram_builder=figures, report_name='validation.public.json',
          new_page_headings=('章末解答',), extra_css=''):
    source=Path(source)
    source_text=source.read_text(encoding='utf-8')
    book_title=next(value[1] for kind,value in blocks(source_text) if kind=='heading' and value[0]==1)
    output_stem=f'web_textbook_ch{chapter:02d}_ja'
    footer_label=f'Web Infrastructure / 第{chapter}章'
    for directory in (ASSETS,HTML_OUT,PDF_OUT): directory.mkdir(parents=True,exist_ok=True)
    diagram_builder()
    pdfmetrics.registerFont(TTFont('JSans',str(SANS)))
    pdfmetrics.registerFont(TTFont('JSerif',str(SERIF)))
    pdfmetrics.registerFontFamily('JSans',normal='JSans',bold='JSans',italic='JSans',boldItalic='JSans')
    pdfmetrics.registerFontFamily('JSerif',normal='JSerif',bold='JSans',italic='JSerif',boldItalic='JSans')
    body=ParagraphStyle('Body',fontName='JSerif',fontSize=10.4,leading=18,wordWrap='CJK',spaceAfter=9,textColor=colors.HexColor(INK))
    styles={1:ParagraphStyle('H1',parent=body,fontName='JSans',fontSize=22,leading=32,spaceAfter=20,keepWithNext=True),
            2:ParagraphStyle('H2',parent=body,fontName='JSans',fontSize=15,leading=23,spaceBefore=17,spaceAfter=10,keepWithNext=True),
            3:ParagraphStyle('H3',parent=body,fontName='JSans',fontSize=12,leading=20,spaceBefore=12,spaceAfter=7,keepWithNext=True)}
    cell_style=ParagraphStyle('Cell',parent=body,fontName='JSans',fontSize=8.7,leading=14,spaceAfter=0)
    code_style=ParagraphStyle('Code',fontName='JSans',fontSize=9,leading=15,spaceBefore=4,spaceAfter=12,
                              backColor=colors.HexColor('#edf2f7'),borderPadding=7)
    story=[]; web=[]; textual=[]; figure_count=0; code_count=0
    width=A4[0]-36*mm
    for kind,value in blocks(source_text):
        if kind=='heading':
            level,title=value
            if title in new_page_headings: story.append(PageBreak())
            story.append(Paragraph(inline(title,True),styles.get(level,styles[3])))
            anchor=re.sub(r'[^\w\-\u3000-\u9fff\uf900-\uffef ]','',title).lower().replace(' ','-')
            web.append(f'<h{level} id="{anchor}">{inline(title)}</h{level}>'); textual.append(title)
        elif kind=='code':
            code_count+=1
            if any(pdfmetrics.stringWidth(line,'JSans',code_style.fontSize)>width-14 for line in value.splitlines()):
                raise ValueError('Code line exceeds reading width: '+value)
            story.append(Preformatted(value,code_style))
            web.append('<pre><code>'+html.escape(value)+'</code></pre>')
            textual.append(value)
        elif kind=='image':
            figure_count+=1
            alt,relative=value; path=(source.parent/relative).resolve()
            with PILImage.open(path) as im: w,h=im.size
            picture=Image(str(path),width=width,height=width*h/w)
            picture.keepWithNext=True
            after_picture=Spacer(1,10); after_picture.keepWithNext=True
            story.extend([Spacer(1,6),picture,after_picture])
            web.append(f'<figure><img src="{relative}" alt="{html.escape(alt)}" width="{w}" height="{h}"></figure>')
        elif kind=='table':
            count=len(value[0]); colwidths=[width*.21,width*.49,width*.30] if count==3 else [width/count]*count
            table=Table([[Paragraph(inline(c,True),cell_style) for c in row] for row in value],colWidths=colwidths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf1f8')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#b8c5d2')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
            story.extend([table,Spacer(1,12)])
            web.append('<div class="table-wrap"><table><thead><tr>'+''.join('<th scope="col">'+inline(c)+'</th>' for c in value[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in row)+'</tr>' for row in value[1:])+'</tbody></table></div>')
            textual.extend(c for row in value for c in row)
        else:
            prefix='・ ' if kind=='bullet' else ''
            paragraph=Paragraph(prefix+inline(value,True),body)
            if value.startswith(('**実行場所','**表示例')): paragraph.keepWithNext=True
            story.append(paragraph)
            web.append('<p'+(' class="bullet"' if kind=='bullet' else '')+'>'+prefix+inline(value)+'</p>')
            textual.append(value)
    css='''body{margin:0;color:#193047;background:#f7f9fc;font-family:system-ui,"Noto Sans JP",sans-serif;line-height:1.9}main{max-width:52rem;margin:auto;padding:2rem 1.25rem 4rem;background:white}h1{font-size:2rem;line-height:1.5}h2{font-size:1.4rem;margin-block-start:2.25rem;border-block-end:1px solid #c5d3e0;padding-block-end:.4rem}h3{font-size:1.1rem;margin-block-start:1.75rem}p{overflow-wrap:anywhere}a{color:#165f9d}a:focus-visible{outline:3px solid #9d651a;outline-offset:3px}code{font-size:.9em;background:#edf2f7;padding:.1em .25em;overflow-wrap:anywhere}figure{margin:1.5rem 0}img{display:block;max-inline-size:100%;block-size:auto}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{border:1px solid #b8c5d2;padding:.65rem;text-align:start;vertical-align:top}th{background:#eaf1f8}.skip{display:block;padding:.5rem 1rem}@media print{@page{size:A4;margin:18mm}body{background:white;font-size:10.4pt}main{max-width:none;padding:0}h1,h2,h3{break-after:avoid}figure, tr{break-inside:avoid}#章末解答{break-before:page}.skip{display:none}}'''
    if code_count:
        css+='pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:1rem;background:#edf2f7;font-size:.9rem;line-height:1.7}pre code{font-size:inherit;background:none;padding:0}'
    css+=extra_css
    (HTML_OUT/(output_stem+'.html')).write_text('<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="text-scale" content="scale"><title>'+html.escape(book_title)+'</title><style>'+css+'</style></head><body><a class="skip" href="#main">本文へ</a><main id="main">'+'\n'.join(web)+'</main></body></html>',encoding='utf-8')
    pdfpath=PDF_OUT/(output_stem+'.pdf')
    def footer(canvas,doc):
        canvas.saveState(); canvas.setFont('JSans',8); canvas.setFillColor(colors.HexColor('#667c91'))
        canvas.drawString(18*mm,12*mm,footer_label)
        canvas.drawRightString(A4[0]-18*mm,12*mm,str(doc.page)); canvas.restoreState()
    SimpleDocTemplate(str(pdfpath),pagesize=A4,leftMargin=18*mm,rightMargin=18*mm,topMargin=17*mm,bottomMargin=20*mm,title=book_title,author='JDU',allowSplitting=1).build(story,onFirstPage=footer,onLaterPages=footer)
    reader=PdfReader(pdfpath); normalized=lambda s:re.sub(r'\s+','',s)
    page_contents=[re.sub(re.escape(footer_label)+r'\s*\d+\s*','',p.extract_text() or '',count=1) for p in reader.pages]
    extracted=normalized(''.join(page_contents))
    plain=lambda s:re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',s).replace('**','').replace('`','')
    missing=[plain(t)[:80] for t in textual if normalized(plain(t)) not in extracted]
    sizes_ok=all(abs(float(p.mediabox.width)-A4[0])<1 and abs(float(p.mediabox.height)-A4[1])<1 for p in reader.pages)
    answer_pages=[i+1 for i,p in enumerate(reader.pages) if '章末解答' in (p.extract_text() or '')]
    report={'chapter':chapter,'language':'ja','draft':'editable prose skeleton','pages':len(reader.pages),'a4':sizes_ok,'text_blocks_checked':len(textual),'missing_text':missing,'figures':figure_count,'answer_starts_on_new_page':False,'teacher_visual_review':'not performed','student_trial':'not performed','aws_operations':'none','sha256':hashlib.sha256(pdfpath.read_bytes()).hexdigest()}
    if code_count: report['code_blocks']=code_count
    # Footer is painted first; inspect content text after that footer for the answer heading.
    if answer_pages:
        page_text=reader.pages[answer_pages[0]-1].extract_text() or ''
        report['answer_starts_on_new_page']='章末解答' in page_text[:120]
    (ROOT/report_name).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if missing or not sizes_ok or not report['answer_starts_on_new_page']: raise RuntimeError(report)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__': build()
