# WEB-00 完成像と通信要件

## 何を作るか

AWSのVPC内にEC2上の踏み台・DNS・Web・DBを構成します。一つのVPCの単一AZに、踏み台・Webを置く一つの公開サブネットと、DNS・DBを置く一つのプライベートサブネットを配置します。四つのEC2には別々のSG-Bastion、SG-Web、SG-DNS、SG-DBを関連付けます。学生PCのブラウザから公開WebへHTTPで接続し、Webの教員提供アプリが内部DNSでdb.lab.testを解決してDBへ接続します。管理者はRDPでUbuntu＋軽量デスクトップ＋xrdpの踏み台へ接続し、そこからWeb・DNS・DBをSSHで管理します。踏み台は通常のWeb閲覧経路に挟みません。 学生はアプリを開発せず、接続、権限、観測、復旧を担当します。

WEB-02の静的Web演習は、HTTPとWebサーバーを学ぶ途中段階です。最終構成では教員提供アプリを通してWebとDBが接続されます。

## 通信の順序

| 用途 | 送信元 | 宛先 | 観測すること |
| --- | --- | --- | --- |
| リモートデスクトップ | 学生PC | EC2踏み台 | RDP3389、許可接続元 |
| サーバー管理 | EC2踏み台 | DNS・Web・DB | SSH22、SG-Bastion以外を拒否 |
| 名前解決 | Web・踏み台 | EC2上のDNS | Web用web.lab.test、DB用db.lab.testのIP回答 |
| ページ取得 | 学生PCのブラウザ | EC2上のWeb・教員提供アプリ | HTTPの応答、Webのlog |
| DNS演習のページ取得 | 踏み台上のブラウザ | EC2上のWeb | IP指定からweb.lab.test指定へ切り替えて同じページを表示 |
| データ取得 | Web側の教員提供アプリ | EC2上のDB | DB接続、権限、問い合わせの結果 |

Security Groupは必要な通信だけを許可します。実際のEC2台数、IP、portの開放範囲、アプリの起動方式は、AWS Academy Learner Labを学生権限で検証してから手順へ固定します。学生PCからHTTPで接続できるのは公開Webです。private DNS・DBと、各サーバーのSSH22を学生PCへ直接公開しません。

## 学生が説明すること

1. DNS、Web、アプリ、DBの役割。
2. 公開Webへのページ要求、内部DNSによるDBの名前解決、DB応答の通信順序。
3. アプリがDBへ接続する理由と、必要な接続元・権限。
4. どの通信を許可し、どの通信を拒否するか。
5. 表示できないときに、DNS、経路、Web、アプリ、DB、logのどこを確認するか。
