# Web演習の構築・採点・配布コード

2026-10-23、本人の「CloudFormationなどのコードもこのGitHubへ登録して管理する」という指示に基づき、従来のJUD project作業領域からWeb演習の開発ソースを移管した。**今後の開発正本はこのdevelopment以下**とし、学生教材は引き続き[course/labs](../course/labs/README.md)で管理する。

## 構成を確認する入口

- [現在の学生用5台・常設SSMのCloudFormation](templates/web-lab-student.template.json)
- [教師側62素点受付のCloudFormation](templates/web-teacher-d11.template.json)
- [学生配布と教師運用のコード](01_roles/cyber_security/tools/web_lab_release/)
- [設計仕様](01_roles/cyber_security/system_requirements/)
- [検証方法と範囲](TESTING.md)
- [最後の改善課題：ブラウザから環境準備・採点確認](issues/WEB-PORTAL-001.md) / [GitHub Issue #1](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/issues/1)

| コード群 | 内容 |
| --- | --- |
| [web_lab_bootstrap](01_roles/cyber_security/tools/web_lab_bootstrap/) | CloudFormation生成、公式AMI初期配備、内部repo、SSM、内部SSH、停止/再開、診断・復旧 |
| [web_lab_instance_selector](01_roles/cyber_security/tools/web_lab_instance_selector/) | 起動前のT系instance比較と価格台帳の処理 |
| [web_lab_catalog](01_roles/cyber_security/tools/web_lab_catalog/) | 教員提供Djangoアプリ、Nginx/systemd設定、SQL、profile・非表示password helper |
| [web_lab_teacher](01_roles/cyber_security/tools/web_lab_teacher/) | 教師側HTTPS受付、DynamoDB、個別登録、本人/教師画面、アカウント間の暗号化受渡し |
| [web_lab_assessment](01_roles/cyber_security/tools/web_lab_assessment/) | 固定registry、P0-P6/M0-M6 checker、62素点、観測、現在状態/参照成績、教師出力 |
| [web_lab_distribution](01_roles/cyber_security/tools/web_lab_distribution/) | D08署名配布、検証、既存認証の受渡し、非公開S3発行 |
| [web_lab_release](01_roles/cyber_security/tools/web_lab_release/) | D08/D11統合署名配布、本人binding、全課題入口、教師の配布・出力 |

## 運用上の区別

templatesは構成の参照と開発用の保存物であり、既存学生環境へ無条件に直接適用する入口ではない。学生の通常構築/更新は、[署名済み配布手順](../course/labs/distribution/STUDENT.md)に従う。元5台・disk・state・鍵・採点認証を保持し、既存環境へcreateや初期化を重ねない。今回GitHubへコードを登録するためのAWS操作は行っていない。

教師用の進捗・採点コードと、学生向け配布物を分ける。開発テストの架空fixtureはテスト専用で、完成状態を作る受入harnessを学生用zipへ含めない。実際の学生情報、token、password、秘密鍵、env、private plan/stateや教師の完成解答資料は登録しない。リポジトリの非公開設定は維持する。

取得済みDEB/wheel等の約1.5GBの生成cacheは登録せず、収集/buildコード、版・hash・署名metadataを登録する。現在の署名版は同梱の公開検証資料として保持するが、秘密の署名鍵は含めない。新しい版の署名には教師の別管理の署名環境が必要。

## 相対pathと再現性

既存コード内の相対pathを保つため、このdirectoryを従来のproject rootに対応させ、01_roles/03_knowledgeの配置を維持した。各コードのimportと、固定アプリ/署名のbyte照合を壊す一括改名・改行変換はしていない。[IMPORT-MANIFEST.json](IMPORT-MANIFEST.json)で、移管元の相対pathと全fileのSHA256を確認できる。378file中376fileは移管元と同一byteで、運用文書2件だけ教師/学生の個人メールを匿名化した。その2件は元hashと匿名化後hash、変換理由をmanifestに記録する。個人名入りの絶対pathを開発実行の前提にはしない。

元READMEにある過去Classの実機履歴や旧配布段階は制作履歴として扱う。現在の入口は本書、[学生教材](../course/labs/README.md)、[検証範囲](TESTING.md)を優先する。署名版r2の期限は2026-10-27 14:24:57 UZTであり、GitHubへの登録はその期限を延長しない。

今後はこのrepoのソース→必要な検証→生成物/教材更新→コミット/pushを一続きで行う。旧JUD project内の同名folderを新しい編集正本に戻さない。
