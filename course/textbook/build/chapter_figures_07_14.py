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
    cards(7,1,'configuration','BINDの設定を三つに分ける',[
        ('サーバー全体',['named.conf.options','待受・許可・転送先']),
        ('担当ゾーンの登録',['named.conf.local','lab.test とファイルの対応']),
        ('個々のレコード',['zones/db.lab.test','SOA・NS・Aなど'])],
        ['いずれもDNSサーバー内の設定。namedが読み込んで回答に使う。',
         'ファイルの保存、構文検査、サービスへの反映を区別する。'])
    s=Scene(1600,1100,'問い合わせる側のOS内の名前解決と、上流の内部DNSを分ける')
    s.text(40,18,'図7-2  OS内の名前解決と、別のEC2の内部DNS',35)
    s.rect(40,130,940,750,'#f7f9fc',BLUE)
    s.text(510,148,'EC2',26,center=True);s.text(510,191,'踏み台サーバー',33,center=True)
    s.rect(100,285,820,115,'#ffffff',BLUE)
    s.text(510,315,'ブラウザ・getentなどの名前解決の依頼',31,BLUE,center=True)
    s.text(200,500,'OSの機能を利用する方法',26,BLUE)
    s.arrow([(150,400),(150,620)],BLUE)
    s.text(535,445,'ローカルスタブを使う方法',26,GREEN)
    s.text(535,510,'127.0.0.53の53番ポート',25,GREEN)
    s.arrow([(900,400),(900,620)],GREEN)
    s.rect(100,620,820,160,'#edf7f0',GREEN)
    s.text(510,638,'systemd-resolved',34,GREEN,center=True)
    s.text(510,704,'上流DNSの設定：10.20.2.10',29,center=True)
    s.rect(1160,590,400,225,'#ffffff',GREEN)
    s.text(1360,608,'EC2',26,center=True);s.text(1360,652,'DNSサーバー',32,GREEN,center=True)
    s.text(1360,714,'10.20.2.10',29,center=True)
    s.text(1360,767,'53番ポート',27,center=True)
    s.arrow([(920,705),(1160,705)],GREEN)
    s.text(995,588,'DNS',27,GREEN);s.text(980,638,'UDP/TCP',24,GREEN)
    s.text(55,943,'127.0.0.53は同じ踏み台サーバー内。10.20.2.10は別のDNSサーバー。',28)
    s.text(55,1006,'すべての名前解決がローカルスタブへのDNS通信を通るとは限らない。',28)
    s.save('ch07-fig02-resolver')
    rows(7,3,'checks','確認する方法と、分かる範囲',[
        (['dig @10.20.2.10','DNSを直接指定'],['そのDNSが何と答えたか','SERVER・status・回答を読む']),
        (['getent','OSの通常の名前解決'],['普段の経路でどのIPが得られるか','hostsや上流DNSの設定も関係する']),
        (['名前指定のHTTP','踏み台サーバーで取得'],['名前解決後にWebへ接続できるか','Webサーバーの80番ポートを使う'])],
        ['同じ名前でも、それぞれ確かめる範囲が異なる。'])


def chapter08():
    stack(8,1,'storage','保存領域からファイルまでの対応',[
        ('AWSのEBSボリューム','EC2へ接続する、SSDやハードディスクに相当する保存領域'),
        ('Ubuntu OSから見える装置・パーティション','lsblkで装置や領域の関係を読む'),
        ('ファイルシステムとマウント先','findmntで、対象パスがどこに載っているかを読む'),
        ('ファイルのパス','例：/var/lib の下の保存ファイル')],
        ['保存の対応関係であり、ネットワーク通信の経路ではない。'])
    cards(8,2,'lifecycle','停止前・停止中・再開後を比べる',[
        ('停止前',['Ubuntu OSが動く','サービスが処理する','EBSへ内容を保存']),
        ('通常の停止中',['OSとプロセスは停止','HTTPでは利用できない','EBS上の保存内容は残る']),
        ('再開後',['Ubuntu OSが新たに起動','サービスの状態を読む','元の保存ファイルを比較'])],
        ['今回は、同じインスタンスと元のEBSを維持するStop/Startを扱う。',
         '保存内容が残ることと、サービスが動いていることは別に確かめる。'])
    rows(8,3,'evidence','比較する証拠と、その意味',[
        (['内容・ハッシュ・属性'],['ファイルの内容と所有者・権限','ハッシュだけで属性まで証明しない']),
        (['インスタンスID・ボリュームID'],['同じEC2と保存領域か','内容のハッシュとは別に比較する']),
        (['boot ID・現在の公開IP'],['今回の起動と公開側の接続先','古い公開IPへ接続し続けない'])],
        ['それぞれの値が何を区別するかを明確にする。'])


def chapter09():
    rows(9,1,'dbms','DBを利用する側と、管理する側',[
        (['EC2 Webサーバー','psql・提供アプリ'],['EC2 DBサーバーのPostgreSQL','TCPで5432番ポートへ接続']),
        (['接続時に選ぶDB名'],['PostgreSQL内のデータベース','練習用と本課題用などを区別']),
        (['送信するSQL'],['選んだDBで処理する','接続ロールの権限も判定する'])],
        ['この図は、利用する対象と選ぶ情報の対応を示す。'])
    s=Scene(1600,950,'備品表の行、列、主キーの位置を示す')
    s.text(40,18,'図9-2  行・列・主キーを表から読む',36)
    cols=[('id',160),('name',520),('quantity',980),('is_public',1360)]
    for heading,x in cols:s.text(x,175,heading,36,center=True)
    data=[('1','Desk','6','true'),('2','Monitor','1','false'),('3','Keyboard','4','true')]
    for i,values in enumerate(data):
        y=270+i*150
        s.rect(40,y,1520,115,'#edf7f0' if i==0 else '#f7f9fc',GREEN if i==0 else '#7991aa')
        for (_,x),value in zip(cols,values):s.text(x,y+32,value,36,center=True)
    s.text(55,760,'横の一行：一件の備品　　縦の一列：名前・数量などの同じ項目',29)
    s.text(55,832,'idは一件を区別する主キーの例。画面上の行番号を使うのではない。',28)
    s.save('ch09-fig02-table')
    cards(9,3,'select','SQLの条件と、取得する結果',[
        ('FROM lesson_item',['備品の表を選ぶ','Desk・Monitor・Keyboard']),
        ('WHERE is_public = true',['公開する行を選ぶ','DeskとKeyboardが対象']),
        ('SELECT name, quantity',['名前と数量の列を得る','ORDER BY nameで並べる'])],
        ['図はSQLを理解するための対応。DB内部の実行順序を規定する図ではない。',
         '行を選ぶ条件と、取得する列を分けて読む。'])


def chapter10():
    stack(10,1,'structure','PostgreSQLの中のまとまり',[
        ('EC2 DBサーバー','Ubuntu OS上でPostgreSQL 16を動かす'),
        ('クラスター：16/main','今回の一つのPostgreSQLの管理単位'),
        ('データベース','接続時に使うデータのまとまりを選ぶ'),
        ('スキーマと表','例：public.catalog_item')],
        ['ここでのクラスターは、複数台の冗長構成を意味しない。'])
    stack(10,2,'connection','WebからDBへ接続して操作する条件',[
        ('名前解決と接続先','db.lab.test → 10.20.2.20'),
        ('通信許可・待受','WebからTCPでDBサーバーの5432番ポートへ'),
        ('HBAと認証','DB名・ロール・送信元を照合し、定めた方式で認証'),
        ('SQL権限','接続後、対象の表で許された操作を行う')],
        ['パスワードは、すべての条件をまとめて満たすものではない。'])
    rows(10,3,'hba','HBAの指定と、実際の接続',[
        (['DB名・ロール','lesson_catalog・lesson_app'],['どのDBへ、誰として接続するか','OSユーザー名とは区別する']),
        (['送信元 10.20.1.20/32'],['Webサーバー一台の内部IP','DB自身の待受IPではない']),
        (['認証方式 scram-sha-256'],['最初に一致した行で認証する','失敗しても次の行へ移らない'])],
        ['接続方式・DB・ロール・接続元を、一つの組として照合する。'])


def chapter11():
    s=Scene(1600,1050,'Webサーバー内のNginxとアプリ、その先のDBサーバーの境界を示す')
    s.text(40,18,'図11-1  HTTPの入口、アプリ、DBの分担',36)
    s.rect(40,165,970,690,'#f7f9fc',BLUE)
    s.text(525,183,'EC2',26,center=True);s.text(525,226,'Webサーバー',34,center=True)
    s.rect(100,410,350,230,'#edf5fc',BLUE)
    s.text(275,434,'Nginx',36,BLUE,center=True)
    s.text(275,506,'HTTPの入口',29,center=True);s.text(275,565,'80番・8080番ポート',27,center=True)
    s.rect(610,410,350,260,'#edf7f0',GREEN)
    s.text(785,434,'Gunicorn',33,GREEN,center=True)
    s.text(785,496,'Djangoの提供アプリ',28,center=True)
    s.text(785,558,'127.0.0.1:8000',29,center=True)
    s.text(785,615,'一覧・保存の処理',27,center=True)
    s.text(525,314,'同じWebサーバー内でHTTP転送（TCP・8000番ポート）',27,center=True)
    s.arrow([(450,490),(610,490)],GREEN);s.arrow([(610,597),(450,597)],GREEN)
    s.rect(1190,410,370,260,'#ffffff',AMBER)
    s.text(1375,430,'EC2',26,center=True);s.text(1375,476,'DBサーバー',33,center=True)
    s.text(1375,542,'PostgreSQL',32,AMBER,center=True)
    s.text(1375,606,'10.20.2.20',28,center=True)
    s.arrow([(960,490),(1190,490)],AMBER);s.arrow([(1190,597),(960,597)],AMBER)
    s.text(1035,336,'DB接続',28,AMBER)
    s.text(1035,380,'TCP・5432番',25,AMBER)
    s.text(100,735,'コード・アプリ実行はWebサーバー内',29,BLUE)
    s.text(55,918,'アプリがDBへ接続する。ブラウザが直接DBへ接続する構成ではない。',28)
    s.text(55,979,'緑：同じWebサーバー内　　茶：別のDBサーバーへの通信',28)
    s.save('ch11-fig01-components')
    rows(11,2,'entries','三つの入口と、使える場所',[
        (['利用者PCのブラウザ','インターネット・AWS IGW経由'],['Webサーバーの80番ポート','一般向けの備品一覧']),
        (['踏み台サーバーのブラウザ','VPC内から接続'],['Webサーバーの8080番ポート','認証して使う管理画面']),
        (['同じWebサーバーのNginx','ループバックでHTTP転送'],['127.0.0.1の8000番ポート','Gunicornと提供アプリ'])],
        ['HTTPはいずれもTCPを使う。入口名だけでなく、接続元とポートを読む。'])
    cards(11,3,'save','管理画面の保存と、表示の対応',[
        ('踏み台のブラウザ',['管理用8080番ポート','認証して備品を入力','POSTで保存を依頼']),
        ('Webの提供アプリ',['入力と権限を確認','DBへ追加・変更','DB接続：TCP・5432番']),
        ('DBと再取得した画面',['対象行が保存される','管理画面で読める','公開対象だけ一般一覧へ'])],
        ['HTTPリクエストの入力値、DBの対象行、再表示した値を対応させる。'])


def chapter12():
    rows(12,1,'placement','コード・設定・データの保存先',[
        (['EC2 Webサーバー','コードと依存パッケージ'],['/opt/jdu-catalog/app','/opt/jdu-catalog/venv']),
        (['EC2 Webサーバー','秘密設定と配信用ファイル'],['/etc/jdu-catalog と staticを分離','秘密をHTTPの配信範囲へ置かない']),
        (['EC2 DBサーバー','PostgreSQLのデータ'],['備品・管理者・必要な補助データ','WebのアプリからTCP・5432番へ'])],
        ['保存場所と、それを扱う権限を用途に合わせて分ける。'])
    cards(12,2,'phases','初期準備と、通常の動作を分ける',[
        ('構築用の接続',['提供済みmigrationを適用','初期データを準備','アプリ管理者を作成']),
        ('通常用権限を準備',['表・列の必要な操作','シーケンスのUSAGE','接続ロールを分ける']),
        ('通常サービスの起動',['runtime設定で起動','必要な画面操作を使う','構築用接続は後で終了'])],
        ['OSの起動のたびに、表や初期データを作り直す構成ではない。'])
    rows(12,3,'service','サービスの定義と、起動する対象',[
        (['User と WorkingDirectory'],['OSユーザー catalog','/opt/jdu-catalog/app']),
        (['EnvironmentFile'],['管理側がroot専用設定を読む','必要な値をプロセスへ渡す']),
        (['ExecStart と Nginxの転送先'],['venv内のGunicornでアプリを実行','HTTP：127.0.0.1の8000番ポート'])],
        ['ユニット読込み、アプリの起動、Nginx設定の反映は対象が異なる。'])


def chapter13():
    stack(13,1,'boundaries','権限を判定する場所を分ける',[
        ('通信：接続元と入口','一般80番・踏み台からの管理8080番・WebからDB5432番'),
        ('OS：ユーザーとファイル','catalogで実行、コードや秘密は管理側で保護'),
        ('DB：ロールとSQL操作','対象の表・列・シーケンスへ必要な権限'),
        ('アプリ：認証と操作権限','備品の閲覧・追加・変更を許された担当者')],
        ['図は判定対象の整理。上から下へ同じ認証情報を流す図ではない。'])
    rows(13,2,'privileges','表の用途ごとに、必要な操作を決める',[
        (['備品：catalog_item'],['SELECT・INSERT・UPDATE','備品のDELETEは与えない']),
        (['補助データ・操作記録'],['補助データは用途ごとの更新や削除','操作記録はSELECT・INSERT']),
        (['採番用シーケンス'],['必要なものへUSAGE','番号を書き換える権限は与えない'])],
        ['すべて読取り専用でも、すべての操作を許す設定でも、用途と合わない。'])
    cards(13,3,'retirement','構築用接続を終え、通常用で動かす',[
        ('構築時',['setupロールを使用','表と初期データを準備','必要なSQL権限を設定']),
        ('構築用接続の終了',['NOLOGIN・パスワード終了','残存setup接続を終了','一時setup設定を片付ける']),
        ('通常時',['runtime接続で動く','必要な成功を確認','不要な操作の拒否も維持'])],
        ['NOLOGINは新しい直接ログインを止める。既存接続は別に扱う。',
         '表やDBは保持し、通常ロールへ所有権を移して済ませない。'])


def chapter14():
    rows(14,1,'observation','正常な流れと、観測する場所',[
        (['名前から接続先を調べる'],['dig・getent・上流DNSの設定','問い合わせ先と回答を分けて読む']),
        (['HTTPでWebへ接続する'],['ss・curl・Nginxのログ','接続元と80番・8080番を区別する']),
        (['アプリからDBを利用する'],['サービス・ログ・認証SELECT','Web内8000番、別DB5432番を分ける'])],
        ['通信はDNSの53番ポート、HTTPとDBはTCPを使う。'])
    rows(14,2,'comparison','比較結果から、次に見る範囲を選ぶ',[
        (['IP指定は成功・名前は失敗'],['名前解決の設定と回答を比較','dig指定先と通常の経路も区別']),
        (['Web自身は成功・外側は失敗'],['待受IP・宛先・通信許可を比較','現在の公開IPも確認']),
        (['静的配信は成功・アプリは失敗'],['アプリの起動と転送、DBを調べる','Nginxだけの成功と区別'])],
        ['成功した範囲を基準にする。結果一つで原因を断定しない。'])
    stack(14,3,'recovery','原因と修正結果を結び付ける',[
        ('観測と比較','場所・対象・時刻・期待結果・実際の結果を記録'),
        ('原因の候補を絞る','成功している範囲と、違いが生じる範囲を整理'),
        ('対象を限定して変更する','構文検査と、対象サービスへの反映を行う'),
        ('同じ条件で再確認する','必要な成功と、維持すべき拒否を確認して記録')],
        ['復旧のために全面開放せず、元の利用要件を保つ。'])


BUILDERS={7:chapter07,8:chapter08,9:chapter09,10:chapter10,11:chapter11,
          12:chapter12,13:chapter13,14:chapter14}
