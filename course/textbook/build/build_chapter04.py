"""Chapter four: URL structure and HTTP request/response messages."""
from build_chapter01 import Scene, ROOT, BLUE, GREEN, AMBER, build


def figures():
    s=Scene(1600,850,'URLの通信方式・接続先Webサーバー・ポート番号・リクエスト対象を対応付ける')
    s.text(40,18,'図4-1  URLで指定する四つの部分',36)
    parts=[(45,320,'http://','通信方式','HTTPでリクエストを送る',BLUE),
           (420,400,'203.0.113.20','接続先Webサーバー','公開IPの例',GREEN),
           (875,240,':80','ポート番号','80番ポート',AMBER),
           (1170,385,'/example.txt','リクエストする対象のパス','説明用のファイル',BLUE)]
    for x,w,token,title,detail,color in parts:
        center=x+w/2
        s.rect(x,145,w,130,'#f5f7fa',color)
        s.text(center,180,token,41,color,center=True)
        s.arrow([(center,275),(center,380)],color)
        s.rect(x,380,w,230,'#ffffff',color)
        s.text(center,404,title,27,color,center=True)
        s.text(center,485,detail,26,center=True)
    s.text(55,675,'どの通信方式で、どのWebサーバーの、何番ポートへ、何をリクエストするかを指定する。',27)
    s.text(55,739,'HTTPのURLでは、ポート番号を省略すると通常は80番ポートを使う。',28)
    s.text(55,796,'203.0.113.20は説明用の公開IP。実際には対象環境の公開IPを使う。',26)
    s.save('ch04-fig01-url')

    s=Scene(1600,860,'SYN、SYN＋ACK、ACKの後にHTTPリクエストとレスポンスを送る')
    s.text(40,18,'図4-2  スリーウェイハンドシェイクとHTTP',40)
    s.rect(105,98,350,90,'#edf5fc',BLUE)
    s.text(280,125,'利用者PCのブラウザ',34,center=True)
    s.rect(1120,98,400,90,'#edf5fc',BLUE)
    s.text(1320,125,'Webサーバーの80番ポート',30,center=True)
    s.rect(240,205,1120,340,'#fff8ed','#e5cfae')
    s.rect(240,563,1120,266,'#f0f7ff','#c3d7ea')
    s.arrow([(280,188),(280,809)],'#91a1b2',True,2)
    s.arrow([(1320,188),(1320,809)],'#91a1b2',True,2)
    s.text(315,223,'TCP接続を確立',32,AMBER)
    for y,label,reverse in ((315,'① SYN',False),(407,'② SYN＋ACK',True),(499,'③ ACK',False)):
        start,end=(1320,280) if reverse else (280,1320)
        s.text(800,y-45,label,32,AMBER,center=True)
        s.arrow([(start,y),(end,y)],AMBER)
    s.text(315,582,'HTTPのやり取り',32,BLUE)
    s.text(800,632,'リクエスト   GET /example.txt HTTP/1.1',32,BLUE,center=True)
    s.arrow([(280,679),(1320,679)],BLUE)
    s.text(800,724,'レスポンス   HTTP/1.1 200 OK ＋ ヘッダーと本文',32,BLUE,center=True)
    s.arrow([(1320,771),(280,771)],BLUE)
    s.save('ch04-fig02-roundtrip')

    s=Scene(1600,735,'HTTPリクエストのバイト列がTCPセグメントのデータ部分に入る例')
    s.text(40,18,'図4-3  TCPのデータ部分にHTTPが入る',40)
    s.text(55,100,'アプリがTCPに渡すHTTPリクエスト',34)
    for x,w,fill,color,part in ((55,900,'#edf5fc',BLUE,'GET /example.txt HTTP/1.1  ＋  Host:'),
                                (955,590,'#edf7f0',GREEN,'203.0.113.20  ＋  空行')):
        s.rect(x,160,w,98,fill,color,0)
        s.text(x+w/2,190,part,37,color,center=True)
    s.text(800,286,'TCPが2つに分ける場合の例',32,center=True)
    s.arrow([(505,258),(505,389)],BLUE)
    s.arrow([(1250,258),(1250,272),(1570,272),(1570,612),(1545,612)],GREEN)
    for y,num,color,fill,example in (
        (335,'①',BLUE,'#edf5fc','GET /example.txt HTTP/1.1  ＋  Host:'),
        (509,'②',GREEN,'#edf7f0','203.0.113.20  ＋  空行'),
    ):
        s.text(55,y+10,'TCPセグメント '+num,29)
        s.rect(55,y+54,410,98,'#fff3df',AMBER,0)
        s.rect(465,y+54,1080,98,fill,color,0)
        s.text(260,y+72,'TCPヘッダー',34,AMBER,center=True)
        s.text(260,y+112,'ポート番号・順番の情報など',24,AMBER,center=True)
        s.text(495,y+65,'TCPのデータ部分',28,color)
        s.text(495,y+105,example,32,color)
    s.save('ch04-fig03-tcp-data')

    s=Scene(1600,765,'HTTPリクエストのリクエスト行、ヘッダー、空行、本文')
    s.text(40,18,'図4-4  HTTPリクエストの構成',40)
    s.rect(55,115,1490,142,'#edf5fc',BLUE)
    s.text(85,135,'① リクエスト行',32,BLUE)
    s.text(85,188,'POST',40,BLUE)
    s.text(240,188,'/items HTTP/1.1',40)
    s.text(1045,190,'POSTがメソッド',32,BLUE)
    s.rect(55,278,1490,203,'#edf7f0',GREEN)
    s.text(85,295,'② HTTPヘッダー',32,GREEN)
    for y,line in ((345,'Host: 203.0.113.20'),(388,'Content-Type: application/x-www-form-urlencoded'),(431,'Content-Length: 21')):
        s.text(85,y,line,29)
    s.text(1045,365,'宛先名や本文の情報',32,GREEN)
    s.text(85,502,'空行',30)
    s.rect(55,555,1490,147,'#fff3df',AMBER)
    s.text(85,576,'③ 本文',32,AMBER)
    s.text(85,631,'name=chair&quantity=2',38)
    s.text(1045,630,'送るデータ',32,AMBER)
    s.save('ch04-fig04-request')

    s=Scene(1600,920,'HTTPレスポンスを三つの枠に分け、各部分と意味を同じ番号・高さ・背景色・矢印で対応付ける')
    s.text(40,18,'図4-5  HTTPレスポンスの構成',40)
    s.text(75,111,'HTTP/1.1で届いた内容',30)
    s.text(1055,111,'各部分の意味',30)
    rows=[(200,160,'① ステータス行','① 処理の結果',BLUE,'#edf5fc'),
          (400,230,'② ヘッダー','② 本文に関する補足情報',GREEN,'#edf7f0'),
          (730,150,'③ 本文','③ 取得したデータ',AMBER,'#fff3df')]
    for y,h,left,right,color,fill in rows:
        s.rect(40,y,910,h,fill,color)
        s.rect(1050,y,500,h,fill,color)
        s.text(65,y+17,left,29,color)
        s.text(1075,y+17,right,29,color)
        s.arrow([(950,y+h/2),(1050,y+h/2)],color)
    s.text(75,278,'HTTP/1.1 200 OK',34,BLUE)
    s.text(1075,278,'正常に処理した（200）',27,BLUE)
    s.text(75,477,'Content-Type: text/plain',31,GREEN)
    s.text(75,535,'Content-Length: 24',31,GREEN)
    s.text(1075,477,'種類：通常のテキスト',27,GREEN)
    s.text(1075,535,'長さ：24バイト',27,GREEN)
    s.text(75,664,'空行（ヘッダーと本文の区切り）',27)
    s.text(75,805,'School inventory server',32,AMBER)
    s.text(1075,805,'画面に表示する文章',27,AMBER)
    s.save('ch04-fig05-response')

    s=Scene(1600,645,'同じVPCにある踏み台サーバーからWebサーバーの内部IPの80番ポートへHTTPで接続する')
    s.text(40,18,'図4-6  踏み台サーバーからWebサーバーへの内部通信',40)
    s.rect(45,91,1510,505,'#f4f8fc','#7793ae')
    s.text(75,106,'AWS',32)
    s.rect(75,162,1450,403,'#ffffff','#7793ae')
    s.text(105,180,'VPC  10.20.0.0/16',33)
    s.rect(115,275,400,218,'#edf7f0',GREEN)
    s.text(315,302,'EC2 踏み台サーバー',34,center=True)
    s.text(315,364,'内部IP  10.20.1.10',30,GREEN,center=True)
    s.text(315,420,'curlを実行する端末',28,center=True)
    s.rect(1085,275,400,218,'#edf5fc',BLUE)
    s.text(1285,302,'EC2 Webサーバー',34,center=True)
    s.text(1285,364,'内部IP  10.20.1.20',30,BLUE,center=True)
    s.text(1285,420,'TCPの80番ポート',28,center=True)
    s.text(800,293,'HTTPリクエスト',34,BLUE,center=True)
    s.arrow([(515,344),(1085,344)],BLUE)
    s.text(800,402,'HTTPレスポンス',34,GREEN,center=True)
    s.arrow([(1085,453),(515,453)],GREEN)
    s.save('ch04-fig06-internal-http')


if __name__=='__main__':
    build(source=ROOT/'docs/ja/04-http-requests-and-responses.md',chapter=4,
          diagram_builder=figures,report_name='chapter04.validation.public.json',
          new_page_headings=('章末問題','章末解答','参考資料'))
