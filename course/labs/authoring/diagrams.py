from curriculum import ACTIVE_NUMBERS, display_task, display_task_references
"""Editable vector scenes and matching PNGs for every P/M task in JA/RU/UZ."""
import html
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from content import T, LANGS

W,H,SCALE=1040,680,2
INK='#18354c';TEAL='#126e70';MUTED='#587083';RED='#ad3737';GRAY='#d8e1e8'
LABELS={
 'pc':T('学生PC','PC студента','Talaba PC'),
 'bastion':T('踏み台サーバ','Bastion-сервер','Bastion server'),
 'web':T('Webサーバ','Web-сервер','Web server'),
 'dns':T('DNSサーバ','DNS-сервер','DNS server'),
 'db':T('DBサーバ','DB-сервер','DB server'),
 'repo':T('配布サーバ','Repo-сервер','Repo server'),
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
    def node(self,role,x,y,active=False,w=190,h=86):
        self.rect(x,y,w,h,fill='#e7f4f2' if active else '#f4f7fa',stroke=TEAL if active else GRAY,width=3 if active else 1)
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
    def finish(self,target,alt):
        # Detect text-label collisions, not just text extending outside the canvas.
        for i,a in enumerate(self.text_bounds):
            for b in self.text_bounds[i+1:]:
                assert not (min(a[2],b[2])-max(a[0],b[0])>1 and min(a[3],b[3])-max(a[1],b[1])>1),(self.task,self.lang,'overlapping text',a[4],b[4])
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img"><title>{html.escape(display_task_references(self.task))}</title><desc>{html.escape(alt)}</desc><rect width="{W}" height="{H}" fill="white"/>'+''.join(self.parts)+'</svg>\n'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.with_suffix('.svg').write_text(svg,encoding='utf-8',newline='\n')
        self.image.save(target.with_suffix('.png'),optimize=True)
        return len(self.text_bounds)

def diagram_stem(task):
    return task.lower()+'-ssm' if task.endswith('0') else display_task(task).lower()


def connection_diagram(s):
    lang=s.lang
    practice=s.task=='P0'
    title=T('P0で操作するWebサーバー','Web-сервер для практики P0','P0 da ishlatiladigan Web server') if practice else T(
        'M0で操作する4台のサーバー','Четыре сервера для задания M0','M0 da ishlatiladigan to‘rtta server')
    s.text(25,15,title[lang],25)
    s.rect(224,65,790,575,fill='#f1f7fc',stroke='#7e9cb3',width=2)
    s.text(247,77,'AWS',20)
    s.rect(565,105,424,492,fill='white',stroke='#7e9cb3',width=2)
    s.text(588,116,'VPC  10.20.0.0/16',19)
    s.simple(35,215,LABELS['pc'][lang],w=150)
    s.simple(248,215,'Session Manager',w=190)
    browser=T('ブラウザ','Браузер','Brauzer')[lang]
    s.path([(185,247),(248,247)],browser,(215,181))
    s.text(343,294,T('EC2の接続画面から開く','Открывается из консоли EC2','EC2 ulanish sahifasidan ochiladi')[lang],16,color=TEAL,center=True,max_width=232)
    if practice:
        s.path([(438,248),(526,248),(526,274),(655,274)], 'P0.2', (494,215))
    else:
        s.path([(438,248),(526,248),(526,190),(655,190)], 'M0', (494,215))
        for target_y in (358, 442, 526):
            s.path([(526,248),(526,target_y),(655,target_y)])
    roles=('bastion','web','dns','db','repo')
    for i,role in enumerate(roles):
        y=155+i*84
        target = role == 'web' if practice else role != 'web'
        s.rect(655,y,309,71,fill='#e7f4f2' if target else '#f4f7fa',stroke=TEAL if target else GRAY,width=2)
        name=LABELS[role][lang]+('ー' if lang=='ja' else '')
        s.text(670,y+23,'EC2 '+name,18)
        s.text(900,y+25,IPS[role],15,color=MUTED,center=True)


def diagram_text(task,lang):
    n=int(task[1:])
    if n==0:
        if task=='P0':
            caption=T(
                '緑の矢印はP0.2でWebサーバーに接続する経路。',
                'Зелёная стрелка ведёт к Web-серверу в P0.2.',
                'Yashil strelka P0.2 da Web serverga ulanishni ko‘rsatadi.')[lang]
            return caption,caption
        caption=T(
            '緑の矢印はM0で接続する4台への経路。',
            'Зелёные стрелки ведут к четырём серверам для M0.',
            'Yashil strelkalar M0 da ulaniladigan to‘rtta serverga olib boradi.')[lang]
        return caption,caption
    if task=='P1':
        return T('VPCの公開サブネットにWebサーバーと踏み台サーバー、非公開サブネットに配布サーバーがあり、HTTPの経路を示す。',
                 'В публичной подсети VPC находятся Web-сервер и бастион, в приватной — сервер пакетов. Стрелки показывают маршруты HTTP.',
                 'VPC ochiq subnetida Web va Bastion serverlari, yopiq subnetida paketlar serveri joylashgan. Strelkalar HTTP yo‘llarini ko‘rsatadi.')[lang],''
    if n==2:
        return T('公開サブネットの踏み台・Webサーバーが、非公開サブネットのDNSサーバーへ問い合わせる。外部名はAWS提供のDNSへ転送する。',
                 'Бастион и Web-сервер в публичной подсети обращаются к DNS-серверу в приватной подсети. Внешние имена передаются DNS AWS.',
                 'Ochiq subnetdagi Bastion va Web serverlari yopiq subnetdagi DNS serveriga murojaat qiladi. Tashqi nomlar AWS DNS ga yuboriladi.')[lang],''
    if task=='P4':
        return T('非公開サブネットの配布サーバーからDBサーバーへPostgreSQLのパッケージを取得してインストールする。公開サブネットのWebサーバーは内部DNSでDBの名前を解決し、DBへ接続する。',
                 'Сервер БД загружает пакеты PostgreSQL с Repo-сервера в приватной подсети и устанавливает их. Web-сервер в публичной подсети разрешает имя БД через внутренний DNS и подключается к БД.',
                 'DB server yopiq subnetdagi Repo serveridan PostgreSQL paketlarini yuklab olib o‘rnatadi. Ochiq subnetdagi Web server ichki DNS orqali DB nomini aniqlaydi va DB ga ulanadi.')[lang],''
    return {
            1:T('学生PCと踏み台サーバーからWebサーバーのmission.txtへのHTTP経路。',
                'Пути HTTP от компьютера и бастиона к mission.txt на Web.',
                'Kompyuter va Bastiondan Web serverdagi mission.txt ga HTTP yo‘llari.'),
            2:T('踏み台とWebから内部DNSへ問い合わせ、踏み台からWebへ名前で接続する。',
                'Бастион и Web обращаются к внутреннему DNS. Бастион открывает Web по имени.',
                'Bastion va Web ichki DNS ga murojaat qiladi. Bastion Web ga nomi bilan ulanadi.'),
            4:T('公開サブネットのWebサーバーが、非公開サブネットのDNSでDBサーバーの名前を解決し、同じ非公開サブネットのDBへ接続する。',
                'Web-сервер в публичной подсети разрешает имя сервера БД через DNS в приватной подсети и подключается к БД в приватной подсети.',
                'Ochiq subnetdagi Web server yopiq subnetdagi DNS orqali DB server nomini aniqlaydi va yopiq subnetdagi DB ga ulanadi.'),
            5:T('公開サブネットのWebサーバーへ一般利用者が接続し、管理者は同じ公開サブネットの踏み台を経由する。Webサーバーは非公開サブネットのDBへ接続する。',
                'Пользователь обращается к Web-серверу в публичной подсети, администратор — через бастион в той же подсети. Web подключается к БД в приватной подсети.',
                'Foydalanuvchi ochiq subnetdagi Web serverga, administrator esa shu subnetdagi Bastion orqali ulanadi. Web server yopiq subnetdagi DB ga ulanadi.'),
            6:T('公開サブネットのWeb・踏み台と、非公開サブネットのDBを示す。公開側から管理画面へのアクセスを拒否し、構築用DBロールをNOLOGINにする。',
                'Web-сервер и бастион находятся в публичной подсети, БД — в приватной. Доступ к администрированию снаружи запрещён; роль настройки БД переведена в NOLOGIN.',
                'Web va Bastion ochiq subnetda, DB yopiq subnetda joylashgan. Tashqaridan boshqaruv sahifasiga kirish rad etiladi; DB ni sozlash roli NOLOGIN qilinadi.'),
        }[n][lang],''
P1_STEP_DIAGRAMS={
    1:T('配布サーバーからWebサーバーへNginxのパッケージをダウンロードする。',
        'Пакет Nginx загружается с Repo-сервера на Web-сервер.',
        'Nginx paketi Repo serveridan Web serverga yuklab olinadi.'),
    4:T('同じWebサーバー内でcurlから127.0.0.1のNginxへリクエストを送る。',
        'Внутри одного Web-сервера curl отправляет запрос в Nginx по адресу 127.0.0.1.',
        'Bitta Web server ichida curl 127.0.0.1 manzilidagi Nginx ga so‘rov yuboradi.'),
    5:T('踏み台サーバーのcurlがWebサーバーの内部IPアドレスへリクエストを送る。',
        'Curl на бастионе посылает запрос на внутренний IP Web-сервера.',
        'Bastion serveridagi curl Web serverning ichki IP manziliga so‘rov yuboradi.'),
}


def p1_diagram(s,step=None):
    lang=s.lang
    if step is None:
        s.text(25,15,T('P1で使うサーバーと通信経路','Серверы и маршруты в P1','P1 serverlari va aloqa yo‘llari')[lang],25)
    s.rect(224,65,790,575,fill='#f1f7fc',stroke='#7e9cb3',width=2)
    s.text(247,77,'AWS',20)
    s.rect(386,120,603,496,stroke='#7e9cb3',width=2)
    s.text(417,135,'VPC  10.20.0.0/16',19)
    s.rect(410,172,553,275,fill='#edf5fc',stroke='#86a6bf',width=2)
    public=T('公開サブネット','Публичная подсеть','Ochiq subnet')[lang]
    s.text(428,183,f'{public}  10.20.1.0/24',19)
    s.rect(410,468,553,132,fill='#fcf6ec',stroke='#b1956c',width=2)
    private=T('非公開サブネット','Приватная подсеть','Yopiq subnet')[lang]
    s.text(428,480,f'{private}  10.20.2.0/24',19)

    s.node('web',714,215,True,w=239,h=161)
    s.node('bastion',428,347,active=step==5,w=216)
    s.node('repo',714,501,active=step==1,w=239)

    if step is None:
        s.simple(35,222,LABELS['pc'][lang],w=150)
        s.simple(341,222,'IGW',w=90)
        s.path([(185,254),(341,254)])
        s.path([(431,254),(714,254)],'HTTP / TCP 80',(565,220))
        s.path([(834,376),(834,501)],'APT / HTTP / TCP 80',(735,407))
    if step in (None,5):
        route = 'HTTP / TCP 80' if step is None else 'curl / HTTP / TCP 80'
        s.path([(536,347),(536,313),(714,313)],route,(611,278))
        s.text(834,319,'Nginx /practice.txt',18,center=True)
        s.text(834,345,'/var/www/jdu-practice',13,center=True)
    elif step==1:
        s.path([(834,501),(834,376)])
        package=T('Nginxパッケージ','Пакет Nginx','Nginx paketi')[lang]
        s.text(740,398,package,17,color=TEAL,center=True)
        s.text(740,423,'HTTP / TCP 80',15,color=TEAL,center=True)
        s.text(834,319,T('APTでインストール','Установка через APT','APT orqali o‘rnatish')[lang],18,center=True)
    elif step==4:
        s.rect(729,294,58,30,stroke=TEAL)
        s.rect(868,294,70,30,stroke=TEAL)
        s.text(758,299,'curl',16,center=True)
        s.text(903,299,'Nginx',16,center=True)
        s.path([(787,309),(868,309)])
        s.text(834,327,'HTTP → 127.0.0.1:80',16,color=TEAL,center=True)
        s.text(834,351,'/practice.txt',15,center=True)


def dns_diagram(s):
    lang=s.lang
    s.text(25,15,T('内部DNSの設定で使うサーバーと通信経路',
                  'Серверы и маршруты внутреннего DNS',
                  'Ichki DNS serverlari va aloqa yo‘llari')[lang],25)
    s.rect(224,65,790,575,fill='#f1f7fc',stroke='#7e9cb3',width=2)
    s.text(247,77,'AWS',20)
    s.rect(386,120,603,496,stroke='#7e9cb3',width=2)
    s.text(417,135,'VPC  10.20.0.0/16',19)
    s.rect(410,172,553,275,fill='#edf5fc',stroke='#86a6bf',width=2)
    s.text(428,183,T('公開サブネット','Публичная подсеть','Ochiq subnet')[lang]+'  10.20.1.0/24',19)
    s.rect(410,468,553,132,fill='#fcf6ec',stroke='#b1956c',width=2)
    s.text(428,480,T('非公開サブネット','Приватная подсеть','Yopiq subnet')[lang]+'  10.20.2.0/24',19)
    s.node('web',714,215,w=239)
    s.node('bastion',428,347,w=216)
    s.node('dns',714,501,True,w=239)
    s.rect(730,125,224,42,fill='white',stroke='#7e9cb3')
    s.text(842,134,'AWS DNS  10.20.0.2',16,center=True,max_width=212)
    s.path([(536,347),(536,258),(714,258)],'HTTP / TCP 80',(616,225))
    s.path([(644,390),(680,390),(680,544),(714,544)],'DNS 53',(675,355))
    s.path([(834,301),(834,501)],'DNS / UDP + TCP 53',(834,405))
    s.path([(953,544),(978,544),(978,146),(954,146)],'DNS 53',(977,335))


def subnet_frame(s):
    lang=s.lang
    s.rect(224,65,790,595,fill='#f1f7fc',stroke='#7e9cb3',width=2)
    s.text(247,77,'AWS',20)
    s.rect(386,120,603,520,stroke='#7e9cb3',width=2)
    s.text(417,135,'VPC  10.20.0.0/16',19)
    s.rect(410,172,553,275,fill='#edf5fc',stroke='#86a6bf',width=2)
    s.text(428,183,T('公開サブネット','Публичная подсеть','Ochiq subnet')[lang]+'  10.20.1.0/24',19)
    s.rect(410,468,553,160,fill='#fcf6ec',stroke='#b1956c',width=2)
    s.text(428,480,T('非公開サブネット','Приватная подсеть','Yopiq subnet')[lang]+'  10.20.2.0/24',19)


def database_diagram(s):
    lang=s.lang
    practice=s.task.startswith('P')
    title=T('DBサーバーの準備とWebサーバーからの接続',
            'Подготовка БД и подключение Web-сервера',
            'DB serverini tayyorlash va Web serverdan ulanish') if practice else T('WebサーバーからDBサーバーへの接続',
                  'Подключение Web-сервера к серверу БД',
                  'Web serverdan DB serveriga ulanish')
    s.text(25,15,title[lang],25)
    subnet_frame(s)
    s.node('web',714,215,True,w=239)
    if practice:
        s.node('dns',428,501,w=160)
        s.node('db',600,501,True,w=160)
        s.node('repo',785,501,True,w=160)
        s.path([(834,301),(834,350),(680,350),(680,501)],'SQL / TCP 5432',(752,323))
        s.path([(714,258),(508,258),(508,501)],'DNS / UDP + TCP 53',(535,320))
        s.text(600,405,'practice-db.lab.test',14,center=True,max_width=150)
        s.text(680,593,'jdu_catalog_practice',14,center=True,max_width=150)
        s.text(834,398,T('PostgreSQLパッケージ','Пакеты PostgreSQL','PostgreSQL paketlari')[lang],16,center=True,max_width=235)
        s.path([(865,501),(865,455),(745,455),(745,501)],'APT / HTTP / TCP 80',(834,431))
        return
    s.node('dns',428,501,w=216)
    s.node('db',714,501,True,w=239)
    s.path([(834,301),(834,501)],'SQL / TCP 5432',(834,405))
    s.path([(714,258),(678,258),(678,544),(644,544)],'DNS / UDP + TCP 53',(635,320))
    s.text(600,360,'practice-db.lab.test' if practice else 'db.lab.test',16,center=True,max_width=235)
    s.text(834,593,'jdu_catalog_practice' if practice else 'jdu_catalog',15,center=True,max_width=225)


def application_diagram(s):
    lang=s.lang
    practice=s.task.startswith('P')
    security=s.task.endswith('6')
    s.text(25,15,T('備品管理アプリの利用経路とDB接続',
                  'Доступ к приложению и подключение к БД',
                  'Ilovadan foydalanish va DB ga ulanish')[lang],25)
    subnet_frame(s)
    s.simple(35,222,LABELS['pc'][lang],w=150)
    s.simple(341,222,'IGW',w=90)
    s.node('bastion',428,347,w=216)
    s.rect(714,215,239,215,fill='#e7f4f2',stroke=TEAL,width=3)
    s.text(834,223,'EC2',18,center=True)
    s.text(834,248,LABELS['web'][lang],18,center=True,max_width=225)
    s.text(834,276,IPS['web'],15,color=MUTED,center=True)
    s.rect(729,305,209,31,stroke=TEAL)
    s.text(834,308,'Nginx',17,center=True)
    s.rect(729,388,209,31,stroke=TEAL)
    s.text(834,391,'Gunicorn / Django',17,center=True,max_width=199)
    s.path([(834,336),(834,388)],'127.0.0.1:8000',(834,349))
    s.node('db',714,501,True,w=239)
    s.path([(185,244),(341,244)])
    s.path([(431,244),(714,244)],'HTTP / TCP 80',(565,218))
    s.path([(185,273),(341,273)],'RDP / TCP 3389',(259,289),color='#306d9d')
    s.path([(431,273),(470,273),(470,347)],color='#306d9d')
    s.path([(536,347),(536,310),(714,310)],'HTTP / TCP 8080',(611,278))
    s.path([(834,430),(834,501)],'SQL / TCP 5432',(834,452))
    if security:
        s.text(563,250,T('公開側の管理URLを拒否','Admin закрыт снаружи','Ochiq admin yopiq')[lang],14,center=True,color=RED,max_width=225)
        role='catalog_practice_setup' if practice else 'catalog_setup'
        s.text(834,593,f'{role}: NOLOGIN',14,center=True,color=RED,max_width=229)


def mission_diagram(s):
    lang=s.lang
    n=int(s.task[1:])
    practice=s.task.startswith('P')
    if n==2:
        dns_diagram(s)
        return
    if n==4:
        database_diagram(s)
        return
    if n in (5,6):
        application_diagram(s)
        return
    s.rect(224,65,790,575,fill='#f1f7fc',stroke='#7e9cb3',width=2)
    s.text(247,77,'AWS',20)
    s.rect(386,120,603,477,stroke='#7e9cb3',width=2)
    s.text(417,135,'VPC  10.20.0.0/16',19)
    if n==1:
        s.simple(35,221,LABELS['pc'][lang],w=150)
        s.simple(341,221,'IGW',w=90)
        s.path([(185,253),(341,253)])
        s.path([(431,253),(720,253)],'HTTP / TCP 80',(565,214))
        s.node('bastion',417,412,w=210)
        if practice:
            s.path([(185,273),(341,273)],'RDP / TCP 3389',(259,289),color='#306d9d')
            s.path([(431,273),(470,273),(470,412)],color='#306d9d')
        s.path([(522,412),(522,295),(720,295)],
               'HTTP / TCP 80' if n==1 else 'HTTP / TCP 8080',(586,345))
        s.node('web',720,209,True,w=239)
        s.text(840,319,'Nginx /mission.txt',19,center=True)
        s.text(840,350,'/var/www/jdu-mission',13,center=True)
        s.text(840,382,'127.0.0.1:80',17,color=MUTED,center=True)

def write_diagrams(root):
    counts={}
    for lang in LANGS:
        for step,labels in P1_STEP_DIAGRAMS.items():
            s=Scene(lang,f'P1.{step}')
            p1_diagram(s,step)
            s.finish(root/'assets'/lang/f'p1-step-{step}',labels[lang])
        for prefix in ('P','M'):
            for n in ACTIVE_NUMBERS:
                task=prefix+str(n);s=Scene(lang,task)
                if n==0:
                    connection_diagram(s)
                    alt,_=diagram_text(task,lang)
                    counts[f'{lang}/{task}']=s.finish(root/'assets'/lang/diagram_stem(task),alt)
                    continue
                if task=='P1':
                    p1_diagram(s)
                    alt,_=diagram_text(task,lang)
                    counts[f'{lang}/{task}']=s.finish(root/'assets'/lang/diagram_stem(task),alt)
                    continue
                mission_diagram(s)
                alt,_=diagram_text(task,lang)
                counts[f'{lang}/{task}']=s.finish(root/'assets'/lang/diagram_stem(task),alt)
    return counts

def diagram_markdown(task,lang):
    alt,caption=diagram_text(task,lang)
    name=f'../../assets/{lang}/{diagram_stem(task)}'
    title=T('接続するサーバー','Подключение к серверам','Ulaniladigan serverlar')[lang] if task.endswith('0') else T('今回の見取り図','Схема задания','Topshiriq diagrammasi')[lang]
    lines = ['### '+title,'',f'![{alt}]({name}.png)','']
    return lines + [caption,''] if caption else lines
