# WEB-02 HTTPとNginx

状態: 教材の初版。Ubuntu 24.04 LTSでの学生権限・AWS Academy Learner Lab通し試験は未実施。VPCと接続経路はWEB-01で確定させる。

## 前提

- 教員が許可したUbuntu環境へ接続でき、現在のhostnameとuserを確認できる。
- fileの置き場所、permission、systemd service、listening port、journalの基本を確認できる。
- 演習用のHTTP到達経路が教員によって用意され、送信元と宛先が明示されている。

## この単位の目標

教員配布の静的ファイルをNginxで返し、clientのHTTP response、Ubuntu上のservice・port・file、Nginxのaccess logを関連付けます。設定や接続を変えたときには、何が変わったかを観測で説明します。HTMLやアプリケーションのプログラミングは行いません。

## 教材

1. [なぜWeb serverが必要か](concepts.ja.md)
2. [手順付き練習](practice.ja.md)
3. [自力課題の仕様](mission.ja.md)
4. [確認項目](checks.md)
5. [症状からの確認](troubleshooting.ja.md)
6. [保存・再開・復旧](resume-reset.md)
7. [検証記録](validation.md)

学生へ正式配布する前に、実際のUbuntu image、package version、Nginx設定、接続経路、HTTPの観測結果を検証します。
