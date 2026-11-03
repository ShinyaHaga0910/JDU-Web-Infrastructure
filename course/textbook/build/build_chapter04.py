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

    s=Scene(1600,1030,'ブラウザからWebサーバーへTCP接続し、HTTPリクエストを送り、HTTPレスポンスを受け取る順番')
    s.text(40,18,'図4-2  接続、HTTPのリクエスト、HTTPのレスポンス',36)
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
    s.text(778,464,'② ブラウザがHTTPのリクエストを送る',30,BLUE,center=True)
    s.text(778,515,'GET /example.txt HTTP/1.1',30,BLUE,center=True)
    s.arrow([(230,580),(1325,580)],BLUE)
    s.text(778,664,'③ WebサーバーがHTTPのレスポンスを返す',30,BLUE,center=True)
    s.text(778,716,'HTTP/1.1 200 OK ＋ ヘッダーと本文',28,BLUE,center=True)
    s.arrow([(1325,785),(230,785)],BLUE)
    s.text(55,920,'上から下へ順に読む。接続しただけでは、リクエストするページはまだ伝わっていない。',28)
    s.text(55,975,'ブラウザは、リクエストに対する結果とデータをレスポンスから読み取って表示する。',28)
    s.save('ch04-fig02-roundtrip')

    s=Scene(1600,1040,'HTTPレスポンスを三つの枠に分け、各部分と意味を同じ番号・高さ・背景色・矢印で対応付ける')
    s.text(40,18,'図4-3  レスポンスの各部分と、その意味',36)
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
    s.text(55,930,'同じ番号の枠が一組。矢印に沿って、届いた内容と右の説明を読み比べる。',28)
    s.text(55,987,'三つの枠は、実際には一つに続いて届くHTTPレスポンスの一部分を表す。',27)
    s.save('ch04-fig03-response')


if __name__=='__main__':
    build(source=ROOT/'docs/ja/04-http-requests-and-responses.md',chapter=4,
          diagram_builder=figures,report_name='chapter04.validation.public.json',
          new_page_headings=('章末問題','章末解答','参考資料'))
