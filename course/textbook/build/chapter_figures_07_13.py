"""Editable diagrams for the second half of the textbook; no AWS operations."""
from build_chapter01 import Scene, BLUE, GREEN, AMBER


def cards(ch, number, stem, title, entries, note):
    """Three successive conceptual stages, explicitly labelled as such."""
    s=Scene(1600,910,title)
    s.text(40,18,f'図{ch}-{number}  {title}',35)
    s.text(55,100,'左から順に、情報や処理の対応を読む',28)
    for i,(heading,lines) in enumerate(entries):
        x=40+i*535;c=(BLUE,GREEN,AMBER)[i]
        s.rect(x,210,490,420,'#f7f9fc',c)
        s.text(x+245,240,heading,31,c,center=True)
        for j,line in enumerate(lines):s.text(x+245,330+j*68,line,27,center=True)
        if i<2:s.arrow([(x+490,465),(x+535,465)],c)
    for i,line in enumerate(note):s.text(55,725+i*65,line,28)
    s.save(f'ch{ch:02}-fig{number:02}-{stem}')


def rows(ch,number,stem,title,pairs,note):
    """Side-by-side mappings, not additional machines or network hops."""
    s=Scene(1600,1100,title)
    s.text(40,18,f'図{ch}-{number}  {title}',35)
    s.text(55,98,'同じ高さの枠を一組として読む',28)
    for i,(left,right) in enumerate(pairs):
        y=180+i*225;c=(BLUE,GREEN,AMBER)[i%3]
        s.rect(40,y,610,175,'#f7f9fc',c)
        s.rect(830,y,730,175,'#f7f9fc',c)
        for j,line in enumerate(left):s.text(345,y+25+j*65,line,30,c,center=True)
        for j,line in enumerate(right):s.text(1195,y+25+j*65,line,29,c,center=True)
        s.arrow([(650,y+88),(830,y+88)],c)
    for i,line in enumerate(note):s.text(55,930+i*65,line,28)
    s.save(f'ch{ch:02}-fig{number:02}-{stem}')


def stack(ch,number,stem,title,entries,note):
    s=Scene(1600,1120,title)
    s.text(40,18,f'図{ch}-{number}  {title}',35)
    for i,(heading,detail) in enumerate(entries):
        y=130+i*205;c=(BLUE,GREEN,AMBER,BLUE)[i]
        s.rect(160,y,1280,155,'#f7f9fc',c)
        s.text(800,y+18,heading,32,c,center=True)
        s.text(800,y+82,detail,29,center=True)
        if i<len(entries)-1:s.arrow([(800,y+155),(800,y+205)],c)
    for i,line in enumerate(note):s.text(55,1010+i*57,line,28)
    s.save(f'ch{ch:02}-fig{number:02}-{stem}')


def chapter07():
    s=Scene(1800,1150,'接続元のOSへ設定する問い合わせ先DNSのIPと、DNSサーバーが答えるWebサーバーのIPを区別する')
    s.text(40,18,'図7-1  OSには問い合わせ先を設定し、DNSから接続先IPを得る',35)
    s.rect(40,130,1000,760,'#f7f9fc',BLUE)
    s.text(540,150,'EC2',26,center=True)
    s.text(540,195,'踏み台サーバー（問い合わせる側）',33,BLUE,center=True)
    s.rect(100,280,880,125,'#ffffff',BLUE)
    s.text(540,318,'ブラウザ・getentが名前解決を依頼する',31,BLUE,center=True)
    s.arrow([(540,405),(540,510)],BLUE)
    s.rect(100,510,880,250,'#edf7f0',GREEN)
    s.text(540,533,'OSの名前解決：systemd-resolved',33,GREEN,center=True)
    s.text(540,612,'問い合わせ先DNS：10.20.2.10',32,center=True)
    s.text(540,692,'この問い合わせ先をNetplanで設定する',29,center=True)
    s.rect(1260,455,500,385,'#ffffff',GREEN)
    s.text(1510,474,'EC2',26,center=True)
    s.text(1510,517,'DNSサーバー',32,GREEN,center=True)
    s.text(1510,579,'10.20.2.10',30,center=True)
    s.text(1510,657,'名前とIPの対応を管理する',27,center=True)
    s.text(1510,717,'guide.lab.test',29,center=True)
    s.text(1510,775,'→ 10.20.1.20',30,GREEN,center=True)
    s.text(1060,370,'DNS：UDP/TCP',26,GREEN)
    s.text(1060,416,'53番ポート',26,GREEN)
    s.arrow([(980,570),(1260,570)],GREEN)
    s.text(1045,515,'名前を尋ねる',26,GREEN)
    s.arrow([(1260,690),(980,690)],GREEN)
    s.text(1050,721,'接続先IPを回答',25,GREEN)
    s.text(55,945,'OSが尋ねる相手：10.20.2.10　　回答で得るWebサーバーのIP：10.20.1.20',28)
    s.text(55,1010,'127.0.0.53は同じOS内の受付用アドレス。別のEC2のIPではない。',28)
    s.text(55,1075,'必要な情報をDNSへ尋ねる場合の流れ。Webサーバー側のOSにも問い合わせ先を設定する。',28)
    s.save('ch07-fig01-resolver')
    rows(7,2,'checks','確認する方法と、分かる範囲',[
        (['dig @10.20.2.10','DNSを直接指定'],['そのDNSが何と答えたか','SERVER・status・回答を読む']),
        (['getent','OSの通常の名前解決'],['普段の経路でどのIPが得られるか','hostsや上流DNSの設定も関係する']),
        (['名前指定のHTTP','踏み台サーバーで取得'],['名前解決後にWebへ接続できるか','Webサーバーの80番ポートを使う'])],
        ['同じ名前でも、それぞれ確かめる範囲が異なる。',
         'digは回答を見るためのコマンド。OSの問い合わせ先設定は変更しない。'])


def chapter08():
    s=Scene(1800,1120,'Webサーバー上のpsqlがDBMSのPostgreSQLへSQLを送り、PostgreSQLが管理する複数のデータベースから利用先を選ぶ')
    s.text(40,18,'図8-1  クライアントはDBMSを通してDBを利用する',36)
    s.rect(40,160,600,720,'#edf5fc',BLUE)
    s.text(340,185,'EC2',26,center=True)
    s.text(340,235,'Webサーバー',34,BLUE,center=True)
    s.rect(85,380,510,260,'#ffffff',BLUE)
    s.text(340,408,'クライアント：psql',32,BLUE,center=True)
    s.text(340,480,'起動するとプロセスが動く',28,center=True)
    s.text(340,550,'SQLを送り、結果を表示する',28,center=True)
    s.rect(770,160,990,720,'#f7f9fc',GREEN)
    s.text(1265,185,'EC2',26,center=True)
    s.text(1265,235,'DBサーバー',34,GREEN,center=True)
    s.rect(810,310,910,525,'#edf7f0',GREEN)
    s.text(1265,332,'DBMS：PostgreSQL',35,GREEN,center=True)
    s.text(1010,471,'SQLを受け付ける',29,GREEN,center=True)
    s.text(1010,540,'選んだDBを操作する',28,center=True)
    s.rect(1350,420,320,225,'#e1edf6',BLUE)
    s.text(1510,444,'本課題用のDB',27,BLUE,center=True)
    s.rect(1290,560,390,225,'#ffffff',GREEN)
    s.text(1485,585,'練習用のDB',26,GREEN,center=True)
    s.text(1485,655,'表・備品などのデータ',27,center=True)
    s.text(1485,717,'接続時に使うDBを選ぶ',26,center=True)
    s.arrow([(640,480),(810,480)],BLUE)
    s.text(683,418,'SQL',29,BLUE)
    s.arrow([(810,625),(640,625)],GREEN)
    s.text(683,660,'結果',28,GREEN)
    s.arrow([(1195,585),(1290,635)],GREEN)
    s.text(55,955,'一台のDBサーバー上で、PostgreSQLが複数のデータベースを管理する。',30)
    s.text(55,1020,'Webのpsqlが送ったSQLを、DBサーバーのPostgreSQLが処理して結果を返す。',30)
    s.save('ch08-fig01-dbms')
    s=Scene(1600,950,'備品表の行、列、主キーの位置を示す')
    s.text(40,18,'図8-2  行・列・主キーを表から読む',36)
    cols=[('id',160),('name',520),('quantity',980),('is_public',1360)]
    for heading,x in cols:s.text(x,175,heading,36,center=True)
    data=[('1','Desk','6','true'),('2','Monitor','1','false'),('3','Keyboard','4','true')]
    for i,values in enumerate(data):
        y=270+i*150
        s.rect(40,y,1520,115,'#edf7f0' if i==0 else '#f7f9fc',GREEN if i==0 else '#7991aa')
        for (_,x),value in zip(cols,values):s.text(x,y+32,value,36,center=True)
    s.text(55,760,'横の一行：一件の備品　　縦の一列：名前・数量などの同じ項目',29)
    s.text(55,832,'idは一件を区別する主キーの例。画面上の行番号を使うのではない。',28)
    s.save('ch08-fig02-table')
    s=Scene(1800,1220,'図に示したSELECT文からFROMで表、WHEREで行、SELECTで列、ORDER BYで順序を指定する対応を読む')
    s.text(40,18,'図8-3  このSQLで、どの行・列を取り出すか',36)
    s.rect(55,115,1690,360,'#f7f9fc',BLUE)
    s.text(85,138,'例に使うSQL',30,BLUE)
    for i,line in enumerate(('SELECT name, quantity','FROM lesson_item','WHERE is_public = true','ORDER BY name;')):
        s.text(95,205+i*60,line,32)
    entries=[('FROM lesson_item',['備品の表を選ぶ','Desk・Monitor・Keyboard']),
             ('WHERE is_public = true',['公開する行を選ぶ','DeskとKeyboard']),
             ('SELECT name, quantity',['名前と数量の列を得る','Desk：6、Keyboard：4'])]
    for i,(heading,lines) in enumerate(entries):
        x=55+i*575;c=(BLUE,GREEN,AMBER)[i]
        s.rect(x,575,535,320,'#f7f9fc',c)
        s.text(x+267,600,heading,29,c,center=True)
        for j,line in enumerate(lines):s.text(x+267,685+j*77,line,28,center=True)
        if i<2:s.arrow([(x+535,755),(x+575,755)],c)
    s.text(55,965,'ORDER BY name：得られた行を、名前の昇順に並べる。',30)
    s.text(55,1035,'上のSQLと同じ表・条件を例に、取り出す行と列の対応を示している。',29)
    s.text(55,1105,'図は考え方を順に示すもの。DB内部の実際の処理順序を規定していない。',28)
    s.save('ch08-fig03-select')



def chapter09():
    stack(9,1,'connection','WebからDBへ接続して操作する条件',[
        ('名前解決と接続先','db.lab.test → 10.20.2.20'),
        ('通信許可・待受','WebからTCPでDBサーバーの5432番ポートへ'),
        ('HBAと認証','DB名・ロール・送信元を照合し、定めた方式で認証'),
        ('SQL権限','接続後、対象の表で許された操作を行う')],
        ['パスワードは、すべての条件をまとめて満たすものではない。'])



def chapter10():
    s=Scene(2000,1160,'同じWebサーバー内のNginxからGunicornへHTTPで転送し、GunicornがDjango製アプリを呼び出す。アプリが別のDBサーバーを利用する')
    s.text(40,18,'図10-1  HTTPの受付、Pythonアプリの実行、DBの分担',38)
    s.rect(40,145,1390,820,'#f7f9fc',BLUE)
    s.text(735,170,'EC2',29,center=True)
    s.text(735,222,'Webサーバー',38,BLUE,center=True)
    s.rect(90,450,380,300,'#edf5fc',BLUE)
    s.text(280,477,'Nginx',39,BLUE,center=True)
    s.text(280,556,'HTTPを受け付ける',32,center=True)
    s.text(280,637,'80番・8080番ポート',30,center=True)
    s.arrow([(470,550),(680,550)],GREEN)
    s.text(570,425,'HTTP転送',32,GREEN,center=True)
    s.text(570,481,'TCP・8000番',27,GREEN,center=True)
    s.arrow([(680,705),(470,705)],GREEN)
    s.text(570,766,'レスポンス',29,GREEN,center=True)
    s.rect(680,340,690,540,'#edf7f0',GREEN)
    s.text(1025,365,'Gunicorn',39,GREEN,center=True)
    s.text(1025,432,'待受：127.0.0.1:8000',32,center=True)
    s.text(1025,504,'WSGIの取り決めでアプリを呼び出す',29,GREEN,center=True)
    s.rect(735,580,580,235,'#ffffff',GREEN)
    s.text(1025,604,'Djangoを使った提供アプリ',34,GREEN,center=True)
    s.text(1025,675,'Gunicornの処理用プロセス内で実行',28,center=True)
    s.text(1025,740,'DBの読み書き・HTML生成',30,center=True)
    s.rect(1640,495,320,355,'#ffffff',AMBER)
    s.text(1800,520,'EC2',29,center=True)
    s.text(1800,575,'DBサーバー',35,AMBER,center=True)
    s.text(1800,655,'PostgreSQL',34,AMBER,center=True)
    s.text(1800,735,'10.20.2.20',30,center=True)
    s.arrow([(1370,670),(1640,670)],AMBER)
    s.text(1505,520,'DB接続',31,AMBER,center=True)
    s.text(1505,577,'TCP・5432番',29,AMBER,center=True)
    s.arrow([(1640,780),(1370,780)],AMBER)
    s.text(1505,817,'結果',30,AMBER,center=True)
    s.text(55,1020,'Djangoはアプリが利用する枠組み。Gunicornが提供アプリのコードを読み込み、実行する。',32)
    s.text(55,1090,'緑：同じWebサーバー内の連携　　茶：別のDBサーバーへの通信',31)
    s.save('ch10-fig01-components')

    s=Scene(2020,1540,'一般利用者はインターネットからWebへ、管理担当者はRDPで踏み台へ入り、そのブラウザから内部ネットワークでWebの管理入口へ接続する')
    s.text(40,18,'図10-2  備品管理アプリの一般利用と管理者利用',39)
    s.text(225,120,'インターネット側',33,center=True)
    s.rect(480,115,1500,1360,'#fafbfe','#8298ad')
    s.text(520,140,'AWS',34)
    s.rect(760,195,1180,1240,'#f7f9fc','#8298ad')
    s.text(795,220,'今回のVPC：内部ネットワーク',31)
    s.rect(40,340,360,290,'#ffffff',BLUE)
    s.text(220,370,'一般利用者のPC',34,BLUE,center=True)
    s.text(220,448,'ブラウザ',34,center=True)
    s.text(220,535,'公開された備品一覧',30,center=True)
    s.rect(40,890,360,300,'#ffffff',GREEN)
    s.text(220,920,'アプリ管理担当者のPC',29,GREEN,center=True)
    s.text(220,1000,'RDPで遠隔操作',32,center=True)
    s.text(220,1080,'TCP・3389番ポート',29,center=True)
    s.rect(525,340,185,850,'#ffffff','#8298ad')
    for y,line in [(665,'Internet'),(723,'Gateway'),(800,'AWS IGW')]:
        s.text(617,y,line,27,center=True)
    s.arrow([(400,510),(525,510)],BLUE)
    s.arrow([(710,510),(1325,510)],BLUE)
    s.text(1005,360,'公開IPへHTTP接続',32,BLUE,center=True)
    s.text(1005,416,'TCP・80番ポート',31,BLUE,center=True)
    s.arrow([(400,1050),(525,1050)],GREEN)
    s.arrow([(710,1050),(800,1050)],GREEN)
    s.rect(800,850,395,350,'#ffffff',GREEN)
    s.text(997,870,'EC2',28,center=True)
    s.text(997,919,'踏み台サーバー',34,GREEN,center=True)
    s.text(997,985,'10.20.1.10',29,center=True)
    s.text(997,1100,'この中のブラウザを使う',28,center=True)
    s.rect(1290,270,620,730,'#edf5fc',BLUE)
    s.text(1600,288,'EC2',28,center=True)
    s.text(1600,335,'Webサーバー',35,BLUE,center=True)
    s.rect(1325,420,270,510,'#ffffff',BLUE)
    s.text(1460,439,'Nginx',34,BLUE,center=True)
    s.text(1460,515,'80番ポート',31,BLUE,center=True)
    s.text(1460,574,'一般一覧',31,BLUE,center=True)
    s.text(1460,756,'8080番ポート',30,GREEN,center=True)
    s.text(1460,819,'アプリの管理画面',28,GREEN,center=True)
    s.rect(1640,470,235,410,'#edf7f0',GREEN)
    s.text(1757,500,'Gunicorn',32,GREEN,center=True)
    s.text(1757,595,'Django製',31,center=True)
    s.text(1757,648,'アプリ',31,center=True)
    s.text(1757,755,'同じWeb内',27,center=True)
    s.text(1757,807,'8000番ポート',25,center=True)
    s.arrow([(1595,540),(1640,540)],BLUE)
    s.arrow([(1595,800),(1640,800)],GREEN)
    s.arrow([(1195,1050),(1240,1050),(1240,800),(1325,800)],GREEN)
    s.text(1000,670,'内部IPへHTTP接続',31,GREEN,center=True)
    s.text(1000,725,'10.20.1.20：8080番',31,GREEN,center=True)
    s.rect(1450,1200,425,195,'#ffffff',AMBER)
    s.text(1662,1214,'EC2',27,center=True)
    s.text(1662,1260,'DBサーバー',33,AMBER,center=True)
    s.text(1662,1325,'PostgreSQL',31,AMBER,center=True)
    s.arrow([(1757,880),(1757,1000),(1757,1200)],AMBER)
    s.text(1515,1040,'アプリからDBへ',29,AMBER,center=True)
    s.text(1515,1100,'TCP・5432番ポート',29,AMBER,center=True)
    s.text(55,1495,'青：一般利用　　緑：アプリ管理者の利用　　茶：アプリとDBの通信',30)
    s.save('ch10-fig02-entries')

    def sequence(number,stem,title,admin=False):
        s=Scene(2020,1560,title)
        s.text(40,18,f'図10-{number}  {title}',39)
        s.rect(45,140,360,1350,'#f7f9fc',GREEN if admin else BLUE)
        s.rect(475,140,900,1350,'#f7f9fc',BLUE)
        s.rect(1450,140,525,1350,'#f7f9fc',AMBER)
        s.text(225,160,'EC2 踏み台サーバー' if admin else '一般利用者のPC',29,center=True)
        s.text(925,160,'EC2 Webサーバー',32,BLUE,center=True)
        s.text(1712,160,'EC2 DBサーバー',32,AMBER,center=True)
        xs=(225,650,1160,1712)
        for x,label in zip(xs,('ブラウザ','Nginx','Gunicorn','PostgreSQL')):
            s.text(x,240,label,35,center=True)
            s.arrow([(x,350),(x,1450)],'#bcc9d6',True,2)
        s.text(1160,300,'Django製アプリを実行',28,GREEN,center=True)
        if admin:
            s.text(225,284,'アプリにログイン済み',26,GREEN,center=True)
        steps=[
            (1,225,650,410,'POST：入力内容を送る' if admin else 'GET：一覧を開く',BLUE),
            (2,650,1160,570,'HTTPでアプリへ転送',GREEN),
        ]
        for num,start,end,y,label,color in steps:
            s.arrow([(start,y),(end,y)],color)
            s.text((start+end)/2,y-96,f'{num}  {label}',30,color,center=True)
            port=('TCP・8080番ポート' if admin else 'TCP・80番ポート') if num==1 else 'TCP・8000番ポート'
            s.text((start+end)/2,y-48,port,27,color,center=True)
        if admin:
            s.rect(960,670,400,120,'#edf7f0',GREEN)
            s.text(1160,688,'3  アプリが権限と',31,GREEN,center=True)
            s.text(1160,741,'入力値を確認する',31,GREEN,center=True)
            s.arrow([(1160,935),(1712,935)],AMBER)
            s.text(1436,829,'4  INSERT または UPDATE',31,AMBER,center=True)
            s.text(1436,881,'TCP・5432番ポート',29,AMBER,center=True)
            s.arrow([(1712,1085),(1160,1085)],AMBER)
            s.text(1436,1031,'5  保存結果',32,AMBER,center=True)
            response='6  保存後の移動先を含むHTTPレスポンス'
        else:
            s.arrow([(1160,750),(1712,750)],AMBER)
            s.text(1436,644,'3  SELECT：公開する備品',31,AMBER,center=True)
            s.text(1436,696,'TCP・5432番ポート',29,AMBER,center=True)
            s.arrow([(1712,920),(1160,920)],AMBER)
            s.text(1436,865,'4  備品の値',32,AMBER,center=True)
            s.rect(960,1010,400,100,'#edf7f0',GREEN)
            s.text(1160,1039,'5  値をHTMLへ組み込む',29,GREEN,center=True)
            response='6  HTMLを含むHTTPレスポンス'
        s.arrow([(1160,1270),(650,1270)],GREEN)
        s.arrow([(650,1270),(225,1270)],BLUE)
        s.rect(240,1150,1000,90,'#ffffff','#ffffff',0)
        s.text(700,1165,response,31,BLUE,center=True)
        s.rect(240,1320,1000,90,'#ffffff','#ffffff',0)
        s.text(700,1340,'Gunicorn → Nginx → ブラウザ',31,BLUE,center=True)
        note='その後、移動先の画面をブラウザがGETし直し、保存された値を表示する。' if admin else '番号は本文の1〜6に対応する。ブラウザが接続するのはNginxの入口である。'
        s.text(55,1505,note,30)
        s.save(f'ch10-fig{number:02}-{stem}')
    sequence(3,'list','DBから備品を読み、一覧を表示する')
    sequence(4,'save','アプリの管理機能で備品を追加・変更する',True)


def chapter11():
    cards(11,1,'phases','初期準備と、通常の動作を分ける',[
        ('構築用の接続',['提供済みmigrationを適用','初期データを準備','アプリ管理者を作成']),
        ('通常用権限を準備',['表・列の必要な操作','シーケンスのUSAGE','接続ロールを分ける']),
        ('通常サービスの起動',['runtime設定で起動','必要な画面操作を使う','構築用接続は後で終了'])],
        ['OSの起動のたびに、表や初期データを作り直す構成ではない。'])
    rows(11,2,'service','サービスの定義と、起動する対象',[
        (['User と WorkingDirectory'],['OSユーザー catalog','/opt/jdu-catalog/app']),
        (['EnvironmentFile'],['管理側がroot専用設定を読む','必要な値をプロセスへ渡す']),
        (['ExecStart と Nginxの転送先'],['venv内のGunicornでアプリを実行','HTTP：127.0.0.1の8000番ポート'])],
        ['ユニット読込み、アプリの起動、Nginx設定の反映は対象が異なる。'])


def chapter12():
    purple='#7354a0'
    red='#ad3842'
    s=Scene(2400,1900,'クライアントPCからAWSのIGW、踏み台・Web・DBサーバーへの経路と、SG・Nginx・OS・アプリ・DBMSのアクセス制御を境界へ向く注釈矢印で示す')
    s.text(40,20,'図12-1  どのコンポーネントで、何を制限するか',43)
    s.rect(390,145,1970,1680,'#fafbfe','#8298ad')
    s.text(425,168,'AWS',35)
    s.rect(660,225,1655,1555,'#f7f9fc','#8298ad')
    s.text(700,247,'今回のVPC（内部ネットワーク）',33)
    s.text(190,675,'インターネット側',31,center=True)
    s.rect(50,770,280,230,'#ffffff',BLUE)
    s.text(190,795,'一般利用者のPC',29,BLUE,center=True)
    s.text(190,865,'ブラウザ',30,center=True)
    s.text(190,935,'備品一覧を見る',28,center=True)
    s.rect(50,1200,280,230,'#ffffff',GREEN)
    s.text(190,1225,'アプリ管理者のPC',28,GREEN,center=True)
    s.text(190,1300,'RDPで遠隔操作',29,center=True)
    s.text(190,1370,'踏み台へ接続',28,center=True)
    s.rect(425,800,180,600,'#ffffff','#8298ad')
    for y,line in [(1005,'Internet'),(1065,'Gateway'),(1145,'AWS IGW')]:s.text(515,y,line,27,center=True)
    s.rect(1110,650,640,750,'#f6f0fc',purple)
    s.text(1430,663,'SG-Web',31,purple,center=True)
    s.rect(1140,710,580,650,'#ffffff',BLUE)
    s.text(1430,725,'EC2',29,center=True)
    s.text(1430,777,'Webサーバー',36,BLUE,center=True)
    s.rect(1170,855,230,245,'#edf5fc',BLUE)
    s.text(1285,878,'Nginx',34,BLUE,center=True)
    s.text(1285,946,'80番／8080番',27,center=True)
    s.text(1285,1018,'HTTPの受付',28,center=True)
    s.rect(1450,855,240,245,'#edf7f0',GREEN)
    s.text(1570,878,'提供アプリ',32,GREEN,center=True)
    s.text(1570,946,'Gunicornで実行',26,center=True)
    s.text(1570,1018,'認証・操作権限',27,center=True)
    s.arrow([(1400,980),(1450,980)],GREEN)
    s.text(1430,1113,'同じWeb内：TCP・8000番ポート',27,GREEN,center=True)
    s.rect(700,1040,360,360,'#f6f0fc',purple)
    s.text(880,1054,'SG-Bastion',29,purple,center=True)
    s.rect(730,1110,300,255,'#ffffff',GREEN)
    s.text(880,1127,'EC2',28,center=True)
    s.text(880,1176,'踏み台サーバー',32,GREEN,center=True)
    s.text(880,1245,'10.20.1.10',27,center=True)
    s.text(880,1315,'この中のブラウザ',28,center=True)
    s.rect(1860,800,450,430,'#f6f0fc',purple)
    s.text(2085,814,'SG-DB',30,purple,center=True)
    s.rect(1890,865,390,325,'#ffffff',AMBER)
    s.text(2085,884,'EC2',28,center=True)
    s.text(2085,932,'DBサーバー',35,AMBER,center=True)
    s.rect(1930,990,310,175,'#fff8ed',AMBER)
    s.text(2085,1015,'PostgreSQL',34,AMBER,center=True)
    s.text(2085,1110,'備品・利用者などの表',27,center=True)
    s.arrow([(330,890),(425,890)],BLUE)
    s.arrow([(605,890),(1080,890),(1080,920),(1170,920)],BLUE)
    s.text(845,800,'HTTP：TCP・80番ポート',28,BLUE,center=True)
    s.arrow([(330,1320),(425,1320)],GREEN)
    s.arrow([(605,1320),(730,1320)],GREEN)
    s.arrow([(1030,1280),(1080,1280),(1080,1050),(1170,1050)],GREEN)
    s.text(850,1460,'HTTP：TCP・8080番ポート',27,GREEN,center=True)
    s.arrow([(1690,1050),(1930,1050)],AMBER)
    s.text(1840,941,'TCP',28,AMBER,center=True)
    s.text(1840,994,'5432番ポート',25,AMBER,center=True)

    def bubble(x,y,w,h,title,lines,points=(),color=purple,size=29):
        if points:s.arrow(points,purple,True,6)
        s.rect(x,y,w,h,'#fff9e9',color,36)
        s.text(x+w/2,y+23,title,31,color,center=True)
        for i,line in enumerate(lines):s.text(x+w/2,y+88+i*56,line,size,center=True)

    bubble(1140,315,610,290,'通信：SG-Web（AWS）',[
        '80番は一般利用者向け',
        '8080番・22番は踏み台から',
        '接続元・ポートで通信を制限'],[(1430,605),(1430,650)],size=29)
    bubble(700,325,380,375,'Web側：Nginx',[
        '公開80番の入口では',
        '/admin/ を拒否',
        '入口ラベルを上書き',
        '管理側は踏み台のみ'],[(990,700),(990,750),(1190,750),(1190,855)],size=28)
    bubble(1810,315,500,355,'DBMS：PostgreSQL',[
        '接続元・DB・ロールを確認',
        'HBAと認証で接続を判定',
        '表ごとにSQL権限を設定',
        '番号の発行権限も用途別に'],[(2110,660),(2328,660),(2328,1050),(2240,1050)],size=28)
    bubble(1175,1190,510,155,'OS：catalogで実行',[
        'コードはroot管理／秘密設定は0600'],[(1670,1190),(1705,1190),(1705,1080),(1690,1080)],color=GREEN,size=26)
    bubble(1130,1520,620,235,'アプリ：ログインと操作権限',[
        '認証した管理者に閲覧・追加・変更',
        '備品削除・利用者管理は許可しない'],[(1670,1520),(1755,1520),(1755,920),(1690,920)],color=GREEN,size=29)
    bubble(1830,1400,480,330,'通信：SG-DB（AWS）',[
        '5432番ポートへの接続は',
        'Webサーバーからだけ',
        'インターネットからDBへ',
        '直接接続させない'],[(2100,1400),(2100,1230)],size=28)
    bubble(430,1520,630,235,'通信：SG-Bastion（AWS）',[
        'RDPは許可した接続元のみ',
        '踏み台サーバーのTCP・3389番ポート'],[(620,1520),(620,1430),(720,1430),(720,1400)],size=28)
    s.text(55,1845,'紫の枠：SG　　紫の破線矢印：注釈から制御する境界へ　　実線矢印：利用する通信',32)
    s.save('ch12-fig01-boundaries')

    s=Scene(2400,1340,'構築時と通常運用時は四角、移行時の対策は矢印形で示す。構築用の高い権限の悪用リスクと、ログイン無効化・認証情報消去・接続終了・一時設定削除を示す')
    s.text(40,20,'図12-2  構築用の強い権限を、通常運用へ残さない',43)
    s.rect(40,210,620,870,'#f7f9fc',BLUE)
    s.text(350,240,'構築時',43,BLUE,center=True)
    s.text(350,350,'構築用の高い権限で接続',35,center=True)
    s.text(350,440,'表の作成・変更ができる',34,center=True)
    s.text(350,515,'DB・表の所有者になる',34,center=True)
    s.rect(80,650,540,355,'#fff1f2',red,36)
    s.text(350,676,'接続できる状態を残すリスク',31,red,center=True)
    s.text(350,760,'認証情報を盗まれると、',31,center=True)
    s.text(350,828,'攻撃者にも強い操作を許す',31,center=True)
    s.text(350,905,'表の変更・削除などの被害',31,red,center=True)
    points=[(730,320),(1480,320),(1725,645),(1480,970),(730,970),(850,645)]
    s.draw.polygon(points,fill='#fff1d2',outline=AMBER,width=3)
    poly=' '.join(f'{x},{y}' for x,y in points)
    s.svg.append(f'<polygon points="{poly}" fill="#fff1d2" stroke="{AMBER}" stroke-width="3"/>')
    s.text(1200,368,'構築用の強い権限の利用を終了',32,AMBER,center=True)
    s.text(1200,485,'DBロールのログインを無効化',31,center=True)
    s.text(1200,590,'パスワードを消去',32,center=True)
    s.text(1200,675,'既存の構築用接続を終了',31,center=True)
    s.text(1200,790,'構築用の一時設定を削除',31,center=True)
    s.text(1200,878,'使える経路と認証情報を残さない',29,AMBER,center=True)
    s.rect(1770,210,590,870,'#edf7f0',GREEN)
    s.text(2065,240,'通常運用時',43,GREEN,center=True)
    s.text(2065,350,'通常運用用ロールで接続',34,center=True)
    s.text(2065,440,'備品の閲覧・追加・変更',34,center=True)
    s.text(2065,560,'必要な権限だけを利用する',32,GREEN,center=True)
    s.text(2065,730,'構築用のDBロールでは',31,center=True)
    s.text(2065,800,'新しい直接ログインをしない',30,center=True)
    s.text(2065,930,'通常の設定とデータは保持',31,GREEN,center=True)
    s.text(55,1140,'今回のDB：構築用ロールはDB・表の所有者として残し、ログインを無効化する。',34)
    s.text(55,1225,'通常運用用ロールへ所有権を移したり、DB・表を削除したりして終了する構成ではない。',32)
    s.save('ch12-fig02-retirement')


def chapter13():
    # The operational chapter uses one continuous case and comparison tables.
    # Remove the former mappings that did not show the actual processing flow.
    pass


BUILDERS={7:chapter07,8:chapter08,9:chapter09,10:chapter10,
          11:chapter11,12:chapter12,13:chapter13}
