"""Chapter two diagrams and reading outputs, using the existing book renderer."""
from build_chapter01 import Scene, ROOT, BLUE, GREEN, AMBER, build


def figures():
    s=Scene(1600,1000,'VPCと二つのサブネットに配置した5台の内部IP')
    s.text(40,18,'図2-1  VPCとサブネットのアドレス',36)
    s.rect(35,95,1530,810,'#f8fafc','#7991aa')
    s.text(70,116,'VPC  10.20.0.0/16',32)
    s.text(70,166,'10.20で始まる範囲に、今回のサーバーを配置する。',27)
    s.rect(75,240,1450,260,'#edf5fc','#9ebed8')
    s.text(100,257,'公開サブネット  10.20.1.0/24',29)
    s.text(100,301,'10.20.1で始まる範囲',25)
    s.node(300,345,400,'踏み台サーバー','10.20.1.10','SG-Bastion')
    s.node(900,345,400,'Webサーバー','10.20.1.20','SG-Web')
    s.rect(75,550,1450,300,'#f1f7f3','#a7c2af')
    s.text(100,568,'非公開サブネット  10.20.2.0/24',29)
    s.text(100,611,'10.20.2で始まる範囲',25)
    s.node(120,675,400,'DNSサーバー','10.20.2.10','SG-DNS')
    s.node(600,675,400,'DBサーバー','10.20.2.20','SG-DB')
    s.node(1080,675,400,'配布サーバー','10.20.2.30','SG-Repo')
    s.text(55,940,'/16や/24はアドレスの範囲を表す。各サーバーへは、その内部IPを指定して接続する。',25)
    s.save('ch02-fig01-subnets')

    s=Scene(1600,1180,'同じWebサーバーの公開IPと内部IPをAWSのIGWで対応付ける')
    s.text(40,18,'図2-2  接続する場所と使うIPアドレス',36)
    s.rect(25,155,305,170,'#edf5fc',BLUE)
    s.text(178,179,'利用者PC',31,center=True)
    s.text(178,235,'ブラウザ',28,center=True)
    s.rect(25,390,305,195,'#edf5fc',BLUE)
    s.text(178,410,'ブラウザが指定する',24,BLUE,center=True)
    s.text(178,458,'Webサーバーの公開IP',30,BLUE,center=True)
    s.text(178,515,'203.0.113.20',30,BLUE,center=True)
    s.rect(385,90,1180,1015,'#f8fafc','#7991aa')
    s.text(415,109,'AWS',30)
    s.rect(480,155,620,235,'#ffffff',BLUE)
    s.text(790,175,'AWSのInternet Gateway（IGW）',29,center=True)
    s.text(790,233,'Webサーバーの宛先アドレスを変換する',28,center=True)
    s.text(790,288,'公開IP → 内部IP',29,BLUE,center=True)
    s.text(790,337,'203.0.113.20 → 10.20.1.20',29,BLUE,center=True)
    s.arrow([(330,240),(480,240)])
    s.text(345,194,'TCP80',25,BLUE)
    s.rect(435,460,1080,600,'#ffffff','#7991aa')
    s.text(465,478,'VPC：内部の通信には内部IPを指定する',29)
    for x,w,role,ip in [(475,400,'踏み台サーバー','10.20.1.10'),(1020,450,'Webサーバー','10.20.1.20')]:
        s.rect(x,550,w,205,'#f1f7f3',GREEN)
        s.text(x+w/2,562,'EC2',26,center=True)
        s.text(x+w/2,602,role,31,center=True)
        s.text(x+w/2,653,'内部IP',25,GREEN,center=True)
        s.text(x+w/2,698,ip,32,GREEN,center=True)
    s.arrow([(1100,270),(1245,270),(1245,550)])
    s.text(1265,329,'HTTP / TCP80',25,BLUE)
    s.text(1265,377,'同じWebサーバーへ届く',25,BLUE)
    s.arrow([(875,650),(1020,650)],GREEN,True)
    s.text(490,798,'踏み台 → Webサーバー：内部IP 10.20.1.20 / SSH TCP22',26,GREEN)
    s.arrow([(1245,755),(1245,880)],GREEN)
    s.text(1280,820,'TCP5432',25,GREEN)
    s.rect(1020,880,450,155,'#f1f7f3',GREEN)
    s.text(1245,893,'EC2',25,center=True)
    s.text(1245,932,'DBサーバー',30,center=True)
    s.text(1245,983,'内部IP  10.20.2.20',28,GREEN,center=True)
    s.text(45,1129,'青：公開IPで外部から接続　　緑：VPC内で内部IPを使って接続',26)
    s.save('ch02-fig02-public-private')

    s=Scene(1600,480,'WebサーバーとDBサーバーのEC2を、それぞれに適用するSGの枠で囲む')
    s.text(40,18,'図2-3  EC2とSecurity Groupの対応',36)
    s.rect(40,85,1520,355,'#f8fafc','#7991aa')
    s.text(65,100,'VPC',28)
    for x,group,role,ip in [
        (95,'SG-Web','Webサーバー','10.20.1.20'),
        (1035,'SG-DB','DBサーバー','10.20.2.20'),
    ]:
        center=x+235
        s.rect(x,150,470,245,'#fff3df',AMBER)
        s.text(center,162,f'Security Group：{group}',30,AMBER,center=True)
        s.rect(x+35,222,400,145,'#edf5fc',BLUE)
        s.text(center,231,'EC2',26,BLUE,center=True)
        s.text(center,268,role,32,center=True)
        s.text(center,317,ip,28,center=True)
    s.arrow([(530,295),(1070,295)],GREEN,width=5)
    s.text(800,249,'DBへの内部通信',30,GREEN,center=True)
    s.text(800,312,'TCP / 宛先ポート5432',28,GREEN,center=True)
    s.save('ch02-fig03-security-groups')

    s=Scene(1600,485,'WebからDBへ向かう通信を送信側と受信側のSGが許可する流れ')
    s.text(40,18,'図2-4  DBへ接続するときのSGの判定',36)
    s.text(800,94,'Webサーバー  →  DBサーバー（10.20.2.20）',32,GREEN,center=True)
    s.text(800,145,'TCP / 宛先ポート5432',30,GREEN,center=True)
    for x,title,condition in [
        (45,'① SG-Webの送信規則','宛先がSG-DBなら許可'),
        (610,'② SG-DBの受信規則','送信元がSG-Webなら許可'),
    ]:
        center=x+245
        s.rect(x,218,490,184,'#fff3df',AMBER)
        s.text(center,232,title,34,AMBER,center=True)
        s.text(center,289,condition,31,center=True)
        s.text(center,340,'TCP / 宛先ポート5432',27,center=True)
    s.rect(1175,218,380,184,'#f1f7f3',GREEN)
    s.text(1365,260,'DBサーバーに届く',32,GREEN,center=True)
    s.text(1365,320,'10.20.2.20:5432',29,center=True)
    for left,right in [(535,610),(1100,1175)]:
        s.arrow([(left,311),(right,311)],GREEN,width=5)
    s.text(800,431,'通信が届くには、①と②の両方の許可が必要',29,center=True)
    s.save('ch02-fig04-sg-rule-checks')

    s=Scene(1600,920,'127.0.0.1はそれぞれのホスト自身を指す')
    s.text(40,18,'図2-5  127.0.0.1が指す相手',36)
    s.rect(40,110,680,640,'#edf5fc','#9ebed8')
    s.rect(880,110,680,640,'#f1f7f3','#a7c2af')
    for center,role in [(380,'Webサーバー'),(1220,'踏み台サーバー')]:
        s.text(center,130,'EC2',26,center=True)
        s.text(center,176,role,32,center=True)
    s.rect(100,280,560,95)
    s.text(380,303,'Nginx',30,center=True)
    s.arrow([(380,375),(380,485)])
    s.text(400,409,'127.0.0.1:8000',26,BLUE)
    s.rect(100,485,560,140)
    s.text(380,504,'同じWebサーバー内のアプリ',29,center=True)
    s.text(380,555,'Gunicornが8000番で待受',25,center=True)
    s.rect(940,280,560,95)
    s.text(1220,303,'踏み台のブラウザ',29,center=True)
    s.arrow([(1220,375),(1220,485)],GREEN,True)
    s.text(1240,409,'127.0.0.1:8000',26,GREEN)
    s.rect(940,485,560,140)
    s.text(1220,504,'踏み台自身の8000番',29,center=True)
    s.text(1220,555,'こちらへ接続しようとする',25,center=True)
    red='#b32d36'
    s.arrow([(940,325),(660,325)],red,True)
    s.text(800,235,'向かわない',25,red,center=True)
    s.text(800,284,'×',56,red,center=True)
    s.text(75,684,'127.0.0.1はWebサーバー自身',28,BLUE)
    s.text(915,684,'127.0.0.1は踏み台自身',28,GREEN)
    s.text(55,796,'踏み台からWebサーバーの管理画面を開くときの宛先：10.20.1.20:8080',28)
    s.text(55,851,'同じアドレスでも、どこで接続を実行するかによって相手が変わる。',26)
    s.save('ch02-fig05-loopback')


if __name__=='__main__':
    build(source=ROOT/'docs/ja/02-network-paths.md', chapter=2,
          diagram_builder=figures, report_name='chapter02.validation.public.json',
          new_page_headings=('2.5 Security Groupで通信する相手を制限する', '章末解答'))
