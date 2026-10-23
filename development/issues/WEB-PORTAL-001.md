# WEB-PORTAL-001：学生の環境準備・採点確認をブラウザへ集約する

- 状態: next（後工程のバックログ。今回実装しない）
- 登録: 2026-10-23、本人依頼。
- 着手順: 正式学生配布の仕上げ、D12教材の後。Web演習の最後の改善課題として残す。
- GitHub: [Issue #1](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/issues/1)（非公開JDU-Web-Infrastructure）。

## 学生の到達体験

教師が案内する固定のWeb入口へ学生本人がログインし、自分の環境の準備・現在状態・課題確認・採点結果・送信履歴をブラウザだけで扱える。初回コマンドの手渡しや、CloudShellで生成したURLの転記を通常の導線から減らす。

## 調査と設計

- AWS Lambda Web FunctionsはLearner Labで利用できることを本人が確認済み（2026-10-23）。この確認を前提とし、学生accountへの権限連携と具体的な構成に必要なLabRole/iam:PassRole等の範囲を設計する。本人のサービス利用確認と、未確認の別account操作権限を区別する。
- Web画面へのログインと、学生本人のAWS accountの構築権限を分けて設計する。AcademyのSSO/API提供や、教師roleによる学生account操作を仮定しない。
- ブラウザから既存署名手順を実行する方式、AWS Console/CloudFormationのブラウザ起動への誘導、固定の採点ポータルへのログインを比較する。新規・既存Lab・停止中・期限切れを区別する。
- 学生本人の匿名Lab ID/account/deploymentにだけアクセスでき、教師は担当学生の進捗を確認できる。教師管理キーやAWSの長期credentialをブラウザ/共有Windowsへ配らない。
- 長い構築処理は受付/job ID/進捗表示に分け、二重クリック・再読込・途中切断で重複構築しない。再開は元state/5台/鍵/採点認証を保持する。
- 構築内容・利用資源・費用の確認を画面で提示し、実行/再開/採点確認を学生が区別できる。RDP/SSMの既存制限、署名・期限の確認、62素点/UNKNOWNの扱いを維持する。

## 受入条件

- [x] Learner LabでWeb Functionsが利用できることを確認（2026-10-23本人確認）。
- [ ] 採用する認証・権限連携方式を教師・別学生accountで受入する。
- [ ] 固定URLから本人認証し、本人の環境/採点だけが表示される。他学生へのアクセスは拒否される。
- [ ] 初期準備・構築状況・再開・課題確認・自分の採点まで、通常操作にコマンドやURL転記を要求しない。
- [ ] 長時間処理・二重クリック・Lab停止/再開・セッション/署名期限切れから、安全に状態確認/再開できる。
- [ ] 原本/receipt/参照成績・練習・検証Lab除外が既存採点と一致し、教師が進捗を追える。
- [ ] 共有Windowsへ秘密鍵/採点token/AWS credentialを保存させない。
- [ ] 教師/学生の実ブラウザで受入し、従来CloudShell入口への復帰手順も記録する。

## 確認済みの公式情報（2026-10-23）

Web FunctionsのHTTPS入口はIamAuth又はApplicationManagedを選べる。前者はIAM署名、後者はアプリ側の本人認証が必要で、学生accountの構築権限が自動的に得られるわけではない。採用方式は未決定。

- https://docs.aws.amazon.com/lambda/latest/dg/web-functions-endpoint-access-control.html
- https://aws.amazon.com/blogs/compute/exploring-aws-lambda-web-functions-for-building-web-applications/

今回の配布版やAWS構成には、このIssueのための新サービス/認証/権限を追加しない。
