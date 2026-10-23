# JDU Web Infrastructure

JDUのWebインフラストラクチャー構築教材です。今セミスターは`Introduction-CyberSecurity`という統合科目の後半で使用します。将来は、この教材を独立した科目の入口として使用できる構成にします。

学生はAWSのVPC内でEC2上のDNS・Web・DBを構築し、教員提供アプリをWebとDBへ接続します。通信経路、公開範囲、service、port、log、保存と復旧を確認します。学生がアプリケーションをプログラミングする授業ではありません。

## 学習の入口

- [この単元だけで学ぶ目的と前提](course/learning-outcomes.md)
- [教材の順序と到達状態](course/roadmap.md)
- [WEB-00 完成像](modules/WEB-00-overview/README.md)
- [WEB-02 HTTPとNginx](modules/WEB-02-http/README.md)

## 現在のP/M課題教材

2026-10-23、5台構成・62素点の署名配布/checkerへ合わせ、[P0-P6の詳しい練習とM0-M6の自力課題](course/labs/README.md)を日本語・ロシア語・ウズベク語で制作しました。[ブラウザ用の入口](course/labs/output/html/index.html)とA4 PDFを用意しています。Pは49段階の操作例、Mは別対象の完成要件と固定採点checkです。本人実演・backup/restore・追加disk・アプリ開発は要求しません。

初期配布と採点機能は教師/別学生のAWSで受入済みですが、**今回の教材を学生が最初から辿る通し試験・母語校閲・教師の目視確認は未実施**です。確認範囲を[validation](course/labs/VALIDATION.md)で分けています。初期署名版の期限は2026-10-27 14:24:57 UZTです。全授業のCLASS_READYはfalseのままです。

## 制作担当者

- [環境構築・配布・採点・教師側システムの開発コード](development/README.md)
- [学生5台のCloudFormation](development/templates/web-lab-student.template.json) / [教師の採点受付のCloudFormation](development/templates/web-teacher-d11.template.json)
- [制作方針](COURSE_POLICY.md)
- [AI作業の入口](AGENTS.md)
- [制作・検証の手順](BUILD.md)

教員専用の解答、学生情報、認証情報はこのリポジトリに保存しません。外部教材の本文は複製せず、出典と確認日を記録します。
