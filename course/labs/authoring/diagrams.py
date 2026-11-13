from curriculum import ACTIVE_NUMBERS
"""Editable vector scenes and matching PNGs for every P/M task in JA/RU/UZ."""
import html
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from content import T, LANGS

W,H,SCALE=1040,680,2
INK='#18354c';TEAL='#126e70';MUTED='#587083';RED='#ad3737';GRAY='#d8e1e8'
STAGES=[
 (T('5台は初期配備済み','Пять узлов уже созданы','Besh server oldin yaratilgan'),T('本人・接続先を確かめる','Сверить аккаунт и сервер','Hisob va serverni tekshirish'),T('正しい役割へSSMで入る','Войти по SSM в нужную роль','To‘g‘ri serverga SSM bilan kirish')),
 (T('Webの練習配信は未完成','HTTP-задание ещё не готово','HTTP topshirig‘i hali tayyor emas'),T('Web内の配信を設定する','Настроить выдачу на Web','Web ichida tarqatishni sozlash'),T('本文とログを照合する','Сверить ответ и журнал','Javob va log ni solishtirish')),
 (T('IP指定のHTTPが使える','HTTP по IP уже работает','IP orqali HTTP ishlaydi'),T('DNSとresolverを設定する','Настроить DNS и resolver','DNS va resolver ni sozlash'),T('名前でも同じWebへ届く','Имя ведёт к тому же Web','Nom ham ayni Web ga olib boradi')),
 (T('同じWebの元ディスク','Исходный диск того же Web','Ayni Web ning asl diski'),T('記録 → Stop → Start','Запись → Stop → Start','Qayd → Stop → Start'),T('内容保持と新boot ID','Данные сохранены, boot ID новый','Mazmun saqlangan, boot ID yangi')),
 (T('WebからDB接続を準備','Подготовить доступ Web к БД','Web dan DB ulanishini tayyorlash'),T('DB・role・認証を設定','Настроить БД, роли и вход','DB, role va auth ni sozlash'),T('許可したSELECTだけ成功','Разрешённый SELECT успешен','Ruxsatli SELECT muvaffaqiyatli')),
 (T('DNSとDBは準備済み','DNS и БД уже готовы','DNS va DB tayyor'),T('提供アプリを接続・起動','Подключить и запустить app','Tayyor app ni ulash va yoqish'),T('操作結果がDBと画面へ','Изменения видны в БД и Web','Amal natijasi DB va Web da')),
 (T('アプリは動作済み','Приложение уже работает','App allaqachon ishlaydi'),T('不要な権限・公開を除く','Убрать лишние права и доступ','Ortiqcha huquq va yo‘lni yopish'),T('許可は成功、禁止は拒否','Разрешённое работает, лишнее нет','Ruxsat ishlaydi, taqiq rad etadi')),
]
LABELS={
 'before':T('開始時点','В начале','Boshlanish'),
 'now':T('今回の操作','Сейчас','Hozirgi amal'),
 'result':T('確認する結果','Результат','Tekshiriladigan natija'),
 'pc':T('学生PC','PC студента','Talaba PC'),
 'bastion':T('踏み台サーバ','Bastion-сервер','Bastion server'),
 'web':T('Webサーバ','Web-сервер','Web server'),
 'dns':T('DNSサーバ','DNS-сервер','DNS server'),
 'db':T('DBサーバ','DB-сервер','DB server'),
 'repo':T('配布サーバ','Repo-сервер','Repo server'),
 'legend':T('太枠：今回の主な設定・確認対象','Толстая рамка: объект настройки или проверки','Qalin ramka: sozlash yoki tekshirish obyekti'),
}
IPS=dict(bastion='10.20.1.10',web='10.20.1.20',dns='10.20.2.10',db='10.20.2.20',repo='10.20.2.30')

class Scene:
    def __init__(self,lang,task):
        self.lang=lang;self.task=task;self.parts=[];self.text_bounds=[]
        self.image=Image.new('RGB',(W*SCALE,H*SCALE),'white');self.draw=ImageDraw.Draw(self.image)
    def font(self,size):
        return ImageFont.truetype('C:/Windows/Fonts/'+('msgothic.ttc' if self.lang=='ja' else 'arial.ttf'),int(size*SCALE))
    def rect(self,x,y,w,h,fill='white',stroke=GRAY,width=1,ellipse=False):
        shape='ellipse' if ellipse else 'rect'
        attrs=f'cx="{x+w/2}" cy="{y+h/2}" rx="{w/2}" ry="{h/2}"' if ellipse else f'x="{x}" y="{y}" width="{w}" height="{h}" rx="5"'
        self.parts.append(f'<{shape} {attrs} fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')
        method=self.draw.ellipse if ellipse else self.draw.rounded_rectangle
        kw=dict(fill=fill,outline=stroke,width=width*SCALE)
        if not ellipse:kw['radius']=5*SCALE
        method((x*SCALE,y*SCALE,(x+w)*SCALE,(y+h)*SCALE),**kw)
    def text(self,x,y,text,size=20,color=INK,center=False,max_width=None):
        font=self.font(size);width=self.draw.textlength(text,font=font)/SCALE
        assert max_width is None or width<=max_width,(self.task,self.lang,text,width,max_width)
        left=x-width/2 if center else x
        assert left>=10 and left+width<=W-10 and y>=0 and y+size+8<=H,(self.task,text)
        self.text_bounds.append((left,y,left+width,y+size+8,text))
        self.parts.append(f'<text x="{x}" y="{y+size}" font-size="{size}" font-family="Arial,MS Gothic,sans-serif" fill="{color}"'+(' text-anchor="middle"' if center else '')+'>'+html.escape(text)+'</text>')
        self.draw.text((left*SCALE,y*SCALE),text,font=font,fill=color)
    def wrap(self,text,width,size):
        # Wrap on words where possible; CJK can wrap at each character.
        units=list(text) if self.lang=='ja' else text.split(' ')
        glue='' if self.lang=='ja' else ' ';lines=[];line=''
        for unit in units:
            candidate=line+glue+unit if line else unit
            if self.draw.textlength(candidate,font=self.font(size))/SCALE>width and line:lines.append(line);line=unit
            else:line=candidate
        if line:lines.append(line)
        return lines
    def node(self,role,x,y,active=False,w=190):
        self.rect(x,y,w,86,fill='#e7f4f2' if active else '#f4f7fa',stroke=TEAL if active else GRAY,width=3 if active else 1)
        self.text(x+w/2,y+8,'EC2',18,center=True)
        self.text(x+w/2,y+34,LABELS[role][self.lang],18,center=True,max_width=w-14)
        self.text(x+w/2,y+62,IPS[role],14,color=MUTED,center=True)
    def path(self,points,label='',label_at=None,color=TEAL):
        self.parts.append('<polyline points="'+' '.join(f'{x},{y}' for x,y in points)+'" fill="none" stroke="'+color+'" stroke-width="2.5"/>')
        scaled=[(x*SCALE,y*SCALE) for x,y in points];self.draw.line(scaled,fill=color,width=5)
        (a,b),(x,y)=points[-2:];angle=math.atan2(y-b,x-a)
        head=[(x,y),(x-12*math.cos(angle-.45),y-12*math.sin(angle-.45)),(x-12*math.cos(angle+.45),y-12*math.sin(angle+.45))]
        self.parts.append('<polygon points="'+' '.join(f'{a:.2f},{b:.2f}' for a,b in head)+'" fill="'+color+'"/>')
        self.draw.polygon([(round(a*SCALE),round(b*SCALE)) for a,b in head],fill=color)
        if label:
            cx,cy=label_at;tw=self.draw.textlength(label,font=self.font(17))/SCALE
            self.rect(cx-tw/2-5,cy-1,tw+10,25,fill='white',stroke='white')
            self.text(cx,cy,label,17,color=color,center=True)
    def simple(self,x,y,label,w=190,ellipse=False):
        self.rect(x,y,w,65,fill='#f4f7fa',ellipse=ellipse)
        self.text(x+w/2,y+18,label,19,center=True,max_width=w-12)
    def internet_boundary(self,x):
        """The IGW sits on the VPC edge; all EC2 nodes stay on the AWS side."""
        self.rect(40,233,x-40,367,fill='#fcf8f1',stroke='#b8b0a0')
        self.rect(x,233,998-x,367,fill='#f1f7fc',stroke='#7e9cb3',width=2)
        self.text(56,236,T('インターネット側','Интернет','Internet tomoni')[self.lang],17,color=MUTED)
        self.text(x+14,236,'AWS / VPC 10.20.0.0/16',17,color=MUTED)
    def finish(self,target,alt):
        # Detect text-label collisions, not just text extending outside the canvas.
        for i,a in enumerate(self.text_bounds):
            for b in self.text_bounds[i+1:]:
                assert not (min(a[2],b[2])-max(a[0],b[0])>1 and min(a[3],b[3])-max(a[1],b[1])>1),(self.task,self.lang,'overlapping text',a[4],b[4])
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img"><title>{html.escape(self.task)}</title><desc>{html.escape(alt)}</desc><rect width="{W}" height="{H}" fill="white"/>'+''.join(self.parts)+'</svg>\n'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.with_suffix('.svg').write_text(svg,encoding='utf-8',newline='\n')
        self.image.save(target.with_suffix('.png'),optimize=True)
        return len(self.text_bounds)

def diagram_text(task,lang):
    n=int(task[1:]);before,action,result=STAGES[n]
    caption=T('図の太枠が今回の主な対象です。設定操作は各手順の実行場所で行い、図の矢印は接続・確認の向きを表します。','Толстая рамка отмечает основной объект. Настраивайте в терминале, указанном в шаге; стрелки показывают направление подключения или проверки.','Qalin ramka asosiy obyektni bildiradi. Har qadamdagi terminalda sozlang; strelkalar ulanish yoki tekshirish yo‘nalishidir.')[lang]
    caption+=' '+T('SGの通信許可は初期配備済みで、今回の課題はサーバー内の設定です。','Разрешения SG заданы начальным комплектом; здесь настраивается сервер.','SG ruxsatlari boshlang‘ich tarqatmada tayyor; bu topshiriqda server ichini sozlaysiz.')[lang]
    if n in (0,4):
        caption+=' '+T('SSMの矢印はAWSの接続管理を使う経路で、EC2の443番受信を開く指示ではありません。','Стрелка SSM означает подключение через AWS, а не открытие входящего 443 на EC2.','SSM strelkasi AWS orqali ulanishdir; EC2 kiruvchi 443 portini ochish ko‘rsatmasi emas.')[lang]
    if n==3:
        caption+=' '+T('Stop/StartはAWS APIによる管理操作で、Webの受信443番を開く操作ではありません。','Stop/Start выполняется через AWS API, а не через входящий 443 Web.','Stop/Start AWS API boshqaruvidir; Web kiruvchi 443 portini ochish emas.')[lang]
    if n in (5,6):
        caption+=' '+T('8000番はWeb内部だけ、8080番は踏み台からの管理用です。','8000 доступен только внутри Web; 8080 используется для управления с бастиона.','8000 faqat Web ichida; 8080 bastiondan boshqarish uchun.')[lang]
    if n in (1,5,6):
        caption+=' '+T('左はインターネット側、右の枠はAWSのVPCです。IGWはVPCの境界に置き、踏み台を含む全EC2はAWS側にあります。','Слева Интернет, справа VPC в AWS. IGW стоит на границе VPC; все EC2, включая бастион, находятся в AWS.','Chapda Internet, o‘ngdagi ramka AWS VPC sidir. IGW VPC chegarasida; barcha EC2, jumladan bastion, AWS tomonida.')[lang]
    if task.startswith('M'):
        caption+=' '+T('図を参考に完成要件から設定値を自分で決めます。','По схеме самостоятельно выберите настройки из требований.','Diagrammaga qarab talablardan sozlama qiymatlarini mustaqil tanlang.')[lang]
    alt=f'{task}: {before[lang]} → {action[lang]} → {result[lang]}。 '+caption
    return alt,caption

def write_diagrams(root):
    counts={}
    for lang in LANGS:
        for prefix in ('P','M'):
            for n in ACTIVE_NUMBERS:
                task=prefix+str(n);s=Scene(lang,task)
                s.text(24,12,f'{task} · '+T('いま何をしているか','Что мы сейчас делаем','Hozir nima qilamiz')[lang],24)
                for i,(label,value) in enumerate(zip(('before','now','result'),STAGES[n])):
                    x=24+i*338;s.rect(x,60,316,112,fill='#e7f4f2' if i==1 else '#f4f7fa',stroke=TEAL if i==1 else GRAY)
                    s.text(x+12,68,LABELS[label][lang],17,color=TEAL)
                    for j,line in enumerate(s.wrap(value[lang],288,20)):
                        s.text(x+12,96+j*28,line,20,max_width=288)
                s.rect(24,194,992,426,stroke=GRAY)
                s.text(44,204,LABELS['legend'][lang],18,color=MUTED)
                if n==0:
                    s.simple(56,264,LABELS['pc'][lang]);s.simple(430,264,'CloudShell',ellipse=True)
                    s.path([(246,296),(430,296)],'HTTPS 443',(338,260))
                    s.path([(525,329),(525,423)],'SSM / HTTPS 443',(525,360))
                    for i,role in enumerate(('bastion','web','dns','db','repo')):
                        x=44+i*196
                        s.path([(525,423),(x+82,423),(x+82,480)])
                        s.node(role,x,480,True,w=164)
                    s.text(525,589,'ssm-user',20,color=TEAL,center=True)
                elif n==1:
                    s.internet_boundary(440)
                    s.simple(56,270,LABELS['pc'][lang]);s.simple(380,270,'IGW',w=120)
                    s.node('web',770,270,True);s.node('bastion',500,472);s.node('repo',770,482)
                    s.path([(246,303),(380,303)],'HTTP / TCP 80',(313,269))
                    s.path([(500,303),(770,303)],'HTTP / TCP 80',(635,269))
                    s.path([(595,472),(595,338),(770,338)],'HTTP / TCP 80',(595,414))
                    s.path([(865,356),(865,482)],'HTTP / TCP 80',(865,414))
                    s.text(720,575,T('Web内でも127.0.0.1へ確認','Также 127.0.0.1 внутри Web','Web ichida 127.0.0.1 ham')[lang],16,center=True)
                elif n==2:
                    s.node('bastion',56,270,True);s.node('web',56,480,True);s.node('dns',770,270,True)
                    s.simple(770,490,'VPC DNS',w=190)
                    s.path([(246,307),(770,307)],'DNS / UDP + TCP 53',(508,272))
                    s.path([(151,356),(151,480)],'HTTP / TCP 80',(151,409))
                    s.path([(246,522),(586,522),(586,342),(770,342)],'DNS / UDP + TCP 53',(480,490))
                    s.path([(865,356),(865,490)],'DNS / UDP + TCP 53',(865,409))
                    s.text(773,569,'10.20.0.2',17,color=MUTED)
                elif n==3:
                    s.simple(56,280,'AWS Console');s.node('web',430,270,True)
                    s.simple(782,280,'EBS (root)')
                    s.path([(246,312),(430,312)],'AWS API / 443',(338,277))
                    s.path([(620,312),(782,312)],T('同じdisk','Тот же диск','Ayni disk')[lang],(702,277))
                    for x,label in [(80,'running'),(430,'stopped'),(780,'running')]:s.simple(x,464,label)
                    s.path([(270,496),(430,496)],'Stop',(350,461))
                    s.path([(620,496),(780,496)],'Start',(700,461))
                    s.text(520,575,T('元instance・元volume・同じmarkerを比較','Сравнить исходные instance, volume и marker','Asl instance, volume va ayni marker ni solishtirish')[lang],18,center=True)
                elif n==4:
                    s.node('web',66,280,True);s.node('db',770,280,True)
                    s.path([(256,320),(770,320)],'PostgreSQL / TCP 5432',(510,280))
                    s.text(520,389,'SELECT / SCRAM',21,center=True,color=TEAL)
                    s.simple(66,488,'CloudShell',ellipse=True)
                    s.path([(256,520),(660,520),(660,348),(770,348)],'SSM / HTTPS 443',(507,488))
                    s.text(520,570,T('Web /32・正しいDB・正しいroleだけ許可','Разрешить только Web /32 и нужные DB/role','Faqat Web /32 va to‘g‘ri DB/role ga ruxsat')[lang],18,center=True)
                else:
                    s.internet_boundary(325)
                    s.simple(42,272,LABELS['pc'][lang],w=155);s.simple(280,272,'IGW',w=90)
                    s.node('web',484,260,True,w=170);s.node('db',810,260,n==6,w=170)
                    s.node('bastion',484,480,w=170);s.node('dns',810,480,w=170)
                    s.path([(197,304),(280,304)],'HTTP 80',(237,268))
                    s.path([(370,304),(484,304)],'TCP 80',(426,268))
                    s.path([(654,304),(810,304)],'SQL / TCP 5432',(732,268))
                    s.path([(484,523),(416,523),(416,328),(484,328)],'HTTP / TCP 8080',(416,423))
                    s.path([(654,328),(724,328),(724,523),(810,523)],'DNS / UDP + TCP 53',(835,420))
                    s.text(569,363,T('Web内部だけ','Только внутри Web','Faqat Web ichida')[lang],16,color=MUTED,center=True)
                    s.text(569,391,'127.0.0.1:8000',17,color=MUTED,center=True)
                    if n==6:
                        s.text(62,467,'/admin/ :80',20,color=RED)
                        s.text(62,505,T('公開側では拒否','Снаружи запрещено','Ochiq yo‘lda rad etiladi')[lang],18,color=RED)
                        s.text(62,559,'setup: NOLOGIN',18,color=RED)
                from pages import ORDER
                pos=ORDER.index(task)
                next_task=ORDER[pos+1] if pos+1<len(ORDER) else T('M成績の確認','Проверка оценок M','M baholarini ko‘rish')[lang]
                s.text(26,638,T('次に進む先：','Далее: ','Keyingi: ')[lang]+next_task,20,color=TEAL)
                alt,_=diagram_text(task,lang)
                counts[f'{lang}/{task}']=s.finish(root/'assets'/lang/task.lower(),alt)
    return counts

def diagram_markdown(task,lang):
    alt,caption=diagram_text(task,lang)
    name=f'../../assets/{lang}/{task.lower()}'
    title=T('今回の見取り図','Схема задания','Topshiriq diagrammasi')[lang]
    zoom=T('図を拡大する','Открыть крупно','Kattalashtirish')[lang]
    return ['### '+title,'',f'![{alt}]({name}.png)','',caption,'',f'[{zoom}]({name}.png) · [SVG]({name}.svg)','']
