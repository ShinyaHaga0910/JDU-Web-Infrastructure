# JDU Web Infrastructure

JDUのWebインフラストラクチャー構築教材です。今セミスターは`Introduction-CyberSecurity`という統合科目の後半で使用します。将来は、この教材を独立した科目の入口として使用できる構成にします。

学生はAWSのVPC内でEC2上のDNS・Web・DBを構築し、教員提供アプリをWebとDBへ接続します。通信経路、公開範囲、service、port、log、保存と復旧を確認します。学生がアプリケーションをプログラミングする授業ではありません。

## 学習の入口

- [この単元だけで学ぶ目的と前提](course/learning-outcomes.md)
- [教材の順序と到達状態](course/roadmap.md)
- [後半教科書の学習順序と必要知識](course/textbook-plan.md)
- [教科書全14章の章立てと各節の説明内容](course/textbook-outline.md)
- [教科書本文と章・課題の対応表（第1〜5章を作成）](course/textbook/README.md)
- [WEB-00 完成像](modules/WEB-00-overview/README.md)
- [WEB-02 HTTPとNginx](modules/WEB-02-http/README.md)

## 現在のP/M課題教材

2026-11-03、[P0〜P6の詳しい練習とM0〜M6の自力課題](course/labs/README.md)を課題別ページへ整理しました。日本語・ロシア語・ウズベク語で、49段階の操作例と固定62素点の採点条件を読めます。初期設定後の[課題確認・成績閲覧はWeb Portal](course/labs/docs/ja/portal.md)を使います。A4 PDFとローカル閲覧HTMLは教材zipにも同梱しています。

教材改訂r1.1では、49段階すべてのコマンド/設定の意味、各Pの仕組みと理解確認、通信経路と出力の読み取り例を追加しています。Mには自分で作業と確認方法を整理する案内を付けています。

正式配布r3は2027年1月31日末（UZT）まで有効です。11/03、新5台をCloudFormationで作成し、初期登録・教材配置・Google/AWS連携・実SSMからのP1/M1設定・ブラウザ確認・成績原本保存・教師表示まで受入済みです。[教師/学生の初回ワークフローとコマンド](course/labs/INITIAL-WORKFLOW.md)を参照してください。**全49手順の学生試読・母語校閲・教師の目視確認は未実施**で、[validation](course/labs/VALIDATION.md)と実機受入の範囲を分けています。全授業のCLASS_READYはfalseのままです。

## 制作担当者

- [環境構築・配布・採点・教師側システムの開発コード](development/README.md)
- [学生5台のCloudFormation](development/templates/web-lab-student.template.json) / [教師の採点受付のCloudFormation](development/templates/web-teacher-d11.template.json)
- [制作方針](COURSE_POLICY.md)
- [AI作業の入口](AGENTS.md)
- [制作・検証の手順](BUILD.md)

教員専用の解答、学生情報、認証情報はこのリポジトリに保存しません。外部教材の本文は複製せず、出典と確認日を記録します。
