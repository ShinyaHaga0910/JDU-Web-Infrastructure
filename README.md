# JDU Web Infrastructure

JDUのWebインフラ構築教材です。今セミスターは`Introduction-CyberSecurity`という統合科目の後半で使用します。将来は、この教材を独立した科目の入口として使用できる構成にします。

学生はAWSのVPC内でEC2上のDNS・Web・DBを構築し、教員提供アプリをWebとDBへ接続します。通信経路、公開範囲、service、port、log、保存と復旧を確認します。学生がアプリケーションをプログラミングする授業ではありません。

## 学習の入口

- [この単元だけで学ぶ目的と前提](course/learning-outcomes.md)
- [教材の順序と到達状態](course/roadmap.md)
- [WEB-00 完成像](modules/WEB-00-overview/README.md)
- [WEB-02 HTTPとNginx](modules/WEB-02-http/README.md)

教材は順次制作します。現在の`WEB-02`は静的Webを扱う基礎演習の初稿で、WebとDBを接続する完成形は未実装です。AWS Academy Learner Labで学生権限の通し試験も未実施です。実際のVPC、EC2台数、接続経路、予算と権限を検証してから正式な構築手順を配布します。

## 制作担当者

- [制作方針](COURSE_POLICY.md)
- [AI作業の入口](AGENTS.md)
- [制作・検証の手順](BUILD.md)

教員専用の解答、学生情報、認証情報はこのリポジトリに保存しません。外部教材の本文は複製せず、出典と確認日を記録します。
