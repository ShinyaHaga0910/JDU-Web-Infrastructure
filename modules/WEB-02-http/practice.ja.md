# WEB-02 手順付き練習原稿

この原稿はUbuntu上の単体動作を理解するための初版です。AWS Academyでのpackage取得とclientからの到達経路はWEB-01の実機検証後に固定します。教員が指定したUbuntu以外では実行しません。

## 1. 実行場所と初期状態

以下のコマンドは、教員指定の**Ubuntu Web serverのshell**で実行します。学生PCのPowerShellやCloudShellで実行する場合は、教員の指示がある箇所だけです。

```bash
hostnamectl
whoami
pwd
```

予想したWeb server・userか確認します。想定と違う場合は変更操作を続けません。

## 2. Nginxの確認

```bash
systemctl is-active nginx
systemctl status nginx --no-pager
```

Nginxが未導入の場合のpackage導入は、WEB-01で検証した取得経路と教員の手順に従います。初版では、未検証のprivate subnetへ`apt install`を直接実行させません。

## 3. 配布ファイルの配置

教員が配布した練習用ファイルを、指定の場所へ配置します。実際のpathと所有者は、Lab初期状態を確認してから教材に記入します。配置後、`ls -l`で対象とpermissionを確かめ、`cat`で内容を見ます。

ファイル配置の前後でNginx設定の参照先を確認します。別のWeb rootへ置いた場合、ファイルは存在してもHTTPで返りません。

## 4. Ubuntu自身からのHTTP確認

```bash
ss -lntp
curl -i http://127.0.0.1/
```

`ss`でNginxの待受address・portを読み、`curl`のHTTP statusと本文が教員配布ファイルに対応するか確認します。`127.0.0.1`への成功は、そのUbuntu自身からの到達を示します。学生PCから到達できる証拠ではありません。

## 5. 許可されたclientからの確認

WEB-01で指定したclientと接続先を使って、同じファイルを要求します。実際のIP・名前・portを記録し、responseのstatusと本文をUbuntu自身の結果と比較します。この経路の具体的なコマンドはAWS実機検証後に記入します。

## 6. logとserviceの照合

requestを行った時刻を記録し、Nginx access logの対応する行を確認します。Ubuntuの標準的なpath例は`/var/log/nginx/access.log`ですが、採用imageと設定で確認します。errorの場合はerror logとjournalを調べます。

```bash
journalctl -u nginx -n 30 --no-pager
```

記録するのは「確認コマンド」「結果」「判断」の3点です。実認証情報をlogや提出物に含めません。
