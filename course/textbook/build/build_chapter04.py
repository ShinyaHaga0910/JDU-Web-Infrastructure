"""Chapter four: URL structure and HTTP request/response messages."""
from build_chapter01 import Scene, ROOT, BLUE, GREEN, AMBER, build


def figures():
    s=Scene(1600,850,'URLの通信方式・接続先Webサーバー・ポート番号・要求対象を対応付ける')
    s.text(40,18,'図4-1  URLで指定する四つの部分',36)
    parts=[(45,320,'http://','通信方式','HTTPで要求を送る',BLUE),
           (420,400,'203.0.113.20','接続先Webサーバー','公開IPの例',GREEN),
           (875,240,':80','ポート番号','80番ポート',AMBER),
           (1170,385,'/example.txt','要求する対象のパス','説明用のファイル',BLUE)]
    for x,w,token,title,detail,color in parts:
        center=x+w/2
        s.rect(x,145,w,130,'#f5f7fa',color)
        s.text(center,180,token,41,color,center=True)
        s.arrow([(center,275),(center,380)],color)
        s.rect(x,380,w,230,'#ffffff',color)
        s.text(center,404,title,27,color,center=True)
        s.text(center,485,detail,26,center=True)
    s.text(55,675,'どの通信方式で、どのWebサーバーの、何番ポートへ、何を要求するかを指定する。',27)
    s.text(55,739,'HTTPのURLでは、ポート番号を省略すると通常は80番ポートを使う。',28)
    s.text(55,796,'203.0.113.20は説明用の公開IP。実際には対象環境の公開IPを使う。',26)
    s.save('ch04-fig01-url')

    s=Scene(1600,1030,'ブラウザからWebサーバーへTCP接続し、HTTP要求を送り、HTTP応答を受け取る順番')
    s.text(40,18,'図4-2  接続、HTTPの要求、HTTPの応答',36)
    s.rect(45,120,370,155,'#edf5fc',BLUE)
    s.text(230,141,'利用者PC',32,center=True)
    s.text(230,199,'ブラウザ',30,BLUE,center=True)
    s.rect(1100,120,450,155,'#f5f7fa',BLUE)
    s.text(1325,134,'EC2',27,center=True)
    s.text(1325,181,'Webサーバー',33,center=True)
    s.text(1325,232,'80番ポートで接続を受け付ける',23,center=True)
    s.arrow([(230,275),(230,870)],'#91a1b2',True,2)
    s.arrow([(1325,275),(1325,870)],'#91a1b2',True,2)
    s.text(778,315,'① TCPで80番ポートへの接続を確立する',30,AMBER,center=True)
    s.arrow([(230,385),(1325,385)],AMBER)
    s.text(778,464,'② ブラウザがHTTPの要求を送る',30,BLUE,center=True)
    s.text(778,515,'GET /example.txt HTTP/1.1',30,BLUE,center=True)
    s.arrow([(230,580),(1325,580)],BLUE)
    s.text(778,664,'③ WebサーバーがHTTPの応答を返す',30,BLUE,center=True)
    s.text(778,716,'HTTP/1.1 200 OK ＋ ヘッダーと本文',28,BLUE,center=True)
    s.arrow([(1325,785),(230,785)],BLUE)
    s.text(55,920,'上から下へ順に読む。接続しただけでは、要求するページはまだ伝わっていない。',28)
    s.text(55,975,'ブラウザは、要求に対する結果とデータを応答から読み取って表示する。',28)
    s.save('ch04-fig02-roundtrip')

    s=Scene(1600,920,'HTTP応答のステータス行、ヘッダー、空行、本文を読み分ける')
    s.text(40,18,'図4-3  HTTP応答の結果、補足情報、データ',36)
    s.rect(40,120,910,650,'#f5f7fa','#7991aa')
    s.text(75,138,'HTTP/1.1の応答例',28)
    s.text(85,215,'HTTP/1.1 200 OK',36,BLUE)
    s.text(85,325,'Content-Type: text/plain',32,GREEN)
    s.text(85,385,'Content-Length: 24',32,GREEN)
    s.text(85,550,'School inventory server',34,BLUE)
    s.text(85,678,'本文は末尾の改行を含む24バイト',25)
    for y,title,detail,color in [(180,'① ステータス','要求を処理した結果',BLUE),
                                 (350,'② ヘッダー','本文の種類や長さなど',GREEN),
                                 (560,'③ 本文','取得したデータそのもの',BLUE)]:
        s.rect(1030,y,520,140,'#ffffff',color)
        s.text(1050,y+14,title,31,color)
        s.text(1050,y+78,detail,29)
        s.arrow([(1030,y+90),(950,y+90)],color)
    s.text(1045,504,'空行を挟んで本文が続く',27,AMBER)
    s.text(55,816,'普段のブラウザ表示では、主に本文が画面に出る。ヘッダーも通信では届いている。',27)
    s.text(55,868,'curlの-iは、応答のヘッダーと本文を一緒に表示する。',28)
    s.save('ch04-fig03-response')


if __name__=='__main__':
    build(source=ROOT/'docs/ja/04-http-requests-and-responses.md',chapter=4,
          diagram_builder=figures,report_name='chapter04.validation.public.json',
          new_page_headings=('章末問題','章末解答','参考資料'))
