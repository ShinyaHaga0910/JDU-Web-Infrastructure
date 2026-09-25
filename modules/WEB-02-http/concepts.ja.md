# HTTPとNginxの仕組み

## なぜWeb serverが必要か

ファイルをUbuntuへ置くだけでは、離れたブラウザからその内容を取得できません。Nginxというserviceが通信を待ち受け、HTTP requestのpathに対応するファイルを探して返します。学生は「ファイルが存在する」「Nginxが動いている」「clientが到達できる」を別々に確認します。

## 誰が何をするか

1. clientがWeb serverの名前またはIP addressとportを指定し、HTTP requestを送ります。
2. UbuntuのNginx processが待受portでrequestを受け取ります。
3. Nginxが設定に従ってファイルを読み、HTTP statusと本文を返します。
4. clientがstatusと本文を表示します。
5. Nginxはaccess logへrequestの記録を残します。errorがあればerror logも確認します。

基本の例ではport 80を使います。実習経路は大学が許可した環境内だけです。平文HTTPの実習へpasswordや実個人情報を送信しません。

## 四つの観測点

| 観測点 | 代表的な確認 | 分かること |
| --- | --- | --- |
| file | 配置先のpathと内容 | 返す対象があるか |
| service | `systemctl status nginx` | Nginxがactiveか |
| port | `ss -lntp` | どのaddressとportで待つか |
| client・log | `curl -i`とaccess/error log | 実際にrequestとresponseがあったか |

`active`という表示だけではclientから到達したことを証明できません。`curl`でHTTP status 200が出ても、意図したファイルが返ったかを本文とlogで確認します。`localhost`は実行した端末自身を指すため、Ubuntu上の`curl localhost`と学生PCからの`curl localhost`は別の対象です。

## 後続との関係

DNSを学ぶと、IP addressの代わりに内部の名前でWebへアクセスします。DNSの回答は接続先のIPを得るために使われ、その後のHTTP requestはNginxへ送られます。PostgreSQLはこの静的ページから直接使いません。
