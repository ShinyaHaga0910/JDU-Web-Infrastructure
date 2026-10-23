# Web Lab checker 候補版

正式な学生配布前の検証候補です。現在の対象は基盤確認とWEB-02の一組だけです。
他の単元、25点の配点、科目修了の判定は含みません。

## 実行場所

自分のAWS AcademyアカウントのCloudShellで実行します。Windowsへ秘密鍵を保存しません。
テスト２の10/20受入版は署名tools c5-v6で、短いcommandは `~/.local/share/jdu-web/c5-v6-bin` にあります。設定済みCloudShellではPATHがこの版を優先します。別アカウントでの配布確認前のため、この検証用設定を学生全員へコピーしないでください。各学生の配備と専用認証を確認してから使用します。
CloudShellから踏み台はSSM、踏み台から内部サーバーは登録済みの鍵を使います。
設定変更はRDPの踏み台から `lab-ssh web` でWebサーバーへ接続して行います。

## WEB-02 手順付き練習 P1

Webサーバーに、内部リポジトリからNginxを導入します。配布物の
`fixtures/practice.txt` を `/var/www/html/practice.txt` に配置します。
所有者root、permission 644とし、Nginxの80番から `/practice.txt` で返します。
Nginxの設定確認を行って起動し、Web自身、踏み台、公開IPからの応答を照合します。
標準の `/var/log/nginx/access.log` に要求の記録を残します。

CloudShellで `jdu-web-check P1` を実行します。結果は自動送信されます。

## WEB-02 自力課題 M1

練習とは別の配布ファイル `fixtures/mission.txt` を使い、Webサーバーの
`/var/www/html/mission.txt` からURL `/mission.txt` で同じ本文とHTTP 200を返してください。
所有者root、permission 644、Nginxの80番待受、別clientからの到達とaccess logを満たします。
本文やURLを練習のままにしても自力課題は通りません。HTMLの制作は不要です。

CloudShellで `jdu-web-check M1` を実行します。

## 結果と再送

- PASS: 今回の観測で条件を満たした。
- FAIL: 今回の観測で条件を満たさなかった。
- UNKNOWN: 通信や観測ができず、判断できなかった。

`--no-submit` は観測だけを行います。送信失敗でも観測結果と未送信データを保持します。
表示された `--retry UUID` で同じ結果を再送します。再試験はUUIDなしで実行してください。
以前のPASSは現在の正常動作の証拠にはなりません。

`jdu-web-my-progress` で自分の最新結果、教師は `jdu-web-dashboard` で受信済みの各課題を確認します。
教師画面の完了件数は提出された課題の件数であり、科目全体の修了を意味しません。
このHTTP演習のWeb 80番は公開する契約です。任意の外部HTTP接続を拒否する要件はありません。
RDPとSSH等の入口制限は、別の基盤・ネットワーク検証で確認します。
