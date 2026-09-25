# Webインフラ科目の到達目標と前提

## この科目だけでの目的

小さなWebインフラを構築し、構成と通信がなぜ必要かを説明し、正常動作と障害の原因を観測できるようになることです。2026年度は統合科目の後半として履修し、2027年度以降は独立科目の教材として使用します。

## 入口の技能

- Ubuntuへ教員指定の方法で接続し、現在のホストとユーザーを確認できる。
- file・directory・permission・service・process・port・logを調べられる。
- IP address、subnet、route、TCP/UDP、port、DNS queryの基礎を説明できる。
- コマンドの実行場所と、通信の送信元・宛先を区別できる。

不足している技能は、2026年度の[OS・Linux教材](https://github.com/ShinyaHaga0910/OS-Linux-Control)と教員が指定するNetworkの補習資料で確認します。翌年度の履修順は大学の正式な科目設計に従います。

## 終了時にできること

| ID | 行動 | 証拠 |
| --- | --- | --- |
| WEB-LO1 | VPCと接続経路を要件に合わせる | 構成図、route、許可通信表 |
| WEB-LO2 | Nginxから静的ページを返す | HTTP response、service、port、access log |
| WEB-LO3 | BIND 9で内部の名前を答える | 問い合わせ先と回答、recordとTTLの説明 |
| WEB-LO4 | StorageとPostgreSQLの状態を管理する | 架空データのSQL、role、接続元、backup/restore |
| WEB-LO5 | 必要な通信・権限だけを許す | 許可試験と拒否試験 |
| WEB-LO6 | 一つの障害を切り分け、復旧する | 症状、観測、原因、修正、再確認の記録 |
| WEB-LO7 | 他者に構成と再開手順を説明する | README、構成図、個人実演 |
