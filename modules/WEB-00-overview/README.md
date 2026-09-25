# WEB-00 完成像と通信要件

## 何を作るか

学生用のUbuntu環境へ、内部DNS、静的Web、PostgreSQLを構築します。教員が用意した静的Webファイルと架空のDBデータを使います。現在の完成像では、WebとDBの間にアプリケーション通信はありません。

## 三つの通信

| 用途 | 送信元 | 宛先 | 主なprotocol・port | 観測すること |
| --- | --- | --- | --- | --- |
| 名前解決 | 作業端末 | 内部DNS | UDP/TCP 53 | 問い合わせ先、回答したIP、TTL |
| ページ取得 | 許可されたclient | Nginx | HTTP TCP 80（実験環境内） | status、表示内容、access log |
| データ操作 | 許可されたpsql client | PostgreSQL | TCP 5432または検証済みlocal socket | 表の内容、接続元、DB権限 |

実際のclient、EC2台数、内部IP、portの開放範囲は、採用するLearner Labの構成を検証してから教材へ記入します。学生PCから内部DNSやprivate Webへ直接到達できると仮定しません。

## 学生が説明すること

1. 各serviceが何を返すか。
2. DNSの回答を受けた後、HTTP requestはどこへ送られるか。
3. WebページとDBはこの構成で直接つながっているか。
4. どの経路を許可し、どの経路を拒否するか。
5. ページが表示されないときに、名前解決、経路、service、file、logのどこを確認するか。
