# WEB-PORTAL-001：学生の環境準備・採点確認をブラウザへ集約する

- 状態: 実現性の検討済み・小規模実証待ち（実装/配備は未着手）。
- 登録: 2026-10-23、本人依頼。
- 着手順: D12の受入残件を保持し、2026-10-23の本人依頼で本Issueの構成検討を先行。Web演習の改善課題として実証・実装へ進める。
- GitHub: [Issue #1](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/issues/1)（非公開JDU-Web-Infrastructure）。

## 学生の到達体験

教師が案内する固定のWeb入口へ学生本人がログインし、自分の環境の準備・現在状態・課題確認・採点結果・送信履歴をブラウザだけで扱える。初回コマンドの手渡しや、CloudShellで生成したURLの転記を通常の導線から減らす。

## 2026-10-23の検討結果

実現できる見込みがある。推奨は**教師側の固定Web Functions入口＋学生本人account内の操作窓口＋既存の採点API/成績DB**。教師が学生roleをAssumeRoleできるとは仮定せず、最初に本人accountの結び付けと必要なLabRole権限を実証する。

- 本人確認：**Web Functions部分はEnd Lab後も使えた**。演習用EC2はLab終了後に利用できない前提で設計する。
- ポータルはEC2停止中でも教材と保存済み成績を見せる。新しいHTTP/DNS/DB/アプリ採点とRDP/SSMは再開待ち。成績API/DBをLab終了後に呼べることは別に受入する。
- 現行の教師EC2は固定IPのTLS中継。新しい閲覧経路はこれに依存させず、既存サーバーレス採点APIへ接続する。旧提出経路の中継依存は、ポータルを置くだけでは解消しない。
- 初回は本人のAWSコンソールから導入し、以後の環境準備・状態・採点をブラウザへ集約する。既存の署名確認/価格確認/内部SSH/個別登録/通信閉鎖を、CloudFormation直リンクだけで省略しない。
- Web Functionsの現行runtimeはNode.js。Python製checker/APIは再利用し、TTY/password入力とCloudShellのprivate stateは接続方法を設計する。
- EC2のstoppedだけでEnd Labと断定しない。ポータル表示で自動Start・新規5台作成・採点の0点化を起こさない。P3/M3の停止観測は専用フローを残す。

[構成案・比較・既存コードとの対応・実証手順](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/blob/main/development/issues/WEB-PORTAL-001-feasibility.md)を正本とする。最初は①EC2に依存しない保存済み成績の閲覧、②学生窓口の導入/本人確認、③5台の状態読取りを実証し、成立後に初期構築・通常採点・対話採点へ広げる。

## 調査と設計

- AWS Lambda Web FunctionsはLearner Labで利用できることを本人が確認済み（2026-10-23）。この確認を前提とし、学生accountへの権限連携と具体的な構成に必要なLabRole/iam:PassRole等の範囲を設計する。本人のサービス利用確認と、未確認の別account操作権限を区別する。
- Web画面へのログインと、学生本人のAWS accountの構築権限を分けて設計する。AcademyのSSO/API提供や、教師roleによる学生account操作を仮定しない。
- ブラウザから既存署名手順を実行する方式、AWS Console/CloudFormationのブラウザ起動への誘導、固定の採点ポータルへのログインを比較する。新規・既存Lab・停止中・期限切れを区別する。
- 学生本人の匿名Lab ID/account/deploymentにだけアクセスでき、教師は担当学生の進捗を確認できる。教師管理キーやAWSの長期credentialをブラウザ/共有Windowsへ配らない。
- 長い構築処理は受付/job ID/進捗表示に分け、二重クリック・再読込・途中切断で重複構築しない。再開は元state/5台/鍵/採点認証を保持する。
- 構築内容・利用資源・費用の確認を画面で提示し、実行/再開/採点確認を学生が区別できる。RDP/SSMの既存制限、署名・期限の確認、62素点/UNKNOWNの扱いを維持する。

## 2026-10-27の小規模試作

- [読取り試作と実験記録](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/tree/main/development/web_portal_poc)を追加。架空データで認証拒否、62点とUNKNOWNの保持、5台停止/取得不能の扱いを8件確認した。
- 教師AWSから既存DBを直接読み、検証Labの62/62点を照合。教師EC2はrunningだったため、停止中・End Lab後は未受入。
- 別学生AWSから、既存stateとStackおよび5台のID・タグの一致、5台running・SSM Onlineを読み取りで確認した。CloudShellの個別観測であり、Web画面の連携試験ではない。
- 前回は `aws lambda list-web-functions` と誤ったサービス名で確認した。正しくは `aws lambda-web list-web-functions`。前回のエラーはCLI版やWeb Functionsの利用可否を示さない。正しいコマンドでの確認は未実施。以前の本人による利用確認を維持する。
- 学生AWSの本人確認に使うSTS署名・短命nonce・再利用拒否の試作を追加。ローカルの模擬試験は12件合格。実AWSでの署名検証、永続的・原子的なnonce管理、ログインおよびLab/接続先との結び付けは未完了。ブラウザへの接続が応答せず実AWS確認は未実施。
- Web Functions配備、学生本人とAWS accountの認証済みbinding、固定ブラウザ画面、停止時/End Lab後の実証は未完了。既存配布版r2は2026-10-27 14:24:57 UZTで期限切れ。

## 受入条件

- [x] Learner LabでWeb Functionsが利用できることを確認（2026-10-23本人確認）。
- [x] End Lab後もWeb Functions部分は利用できたことを確認（2026-10-23本人確認）。EC2の継続稼働とは区別する。
- [x] 公式仕様・既存コードから構成案と実証の順番を整理。今回AWS操作なし。
- [ ] EC2中継に依存しない経路で、保存済み成績をLab終了後にも閲覧できる。
- [ ] 採用する認証・権限連携方式を教師・別学生accountで受入する。
- [ ] 固定URLから本人認証し、本人の環境/採点だけが表示される。他学生へのアクセスは拒否される。
- [ ] 初期準備・構築状況・再開・課題確認・自分の採点まで、通常操作にコマンドやURL転記を要求しない。
- [ ] 長時間処理・二重クリック・Lab停止/再開・セッション/署名期限切れから、安全に状態確認/再開できる。
- [ ] EC2停止・停止理由不明・AWS API接続不能で勝手にStart/再作成/0点化しない。P3/M3の正規の停止観測は維持する。
- [ ] 原本/receipt/参照成績・練習・検証Lab除外が既存採点と一致し、教師が進捗を追える。
- [ ] 共有Windowsへ秘密鍵/採点token/AWS credentialを保存させない。
- [ ] 教師/学生の実ブラウザで受入し、従来CloudShell入口への復帰手順も記録する。

## 確認済みの公式情報（2026-10-23）

Web FunctionsのHTTPS入口はIamAuth又はApplicationManagedを選べる。前者はIAM署名、後者はアプリ側の本人認証が必要で、学生accountの構築権限が自動的に得られるわけではない。採用方式は未決定。

- https://docs.aws.amazon.com/lambda/latest/dg/web-functions-endpoint-access-control.html
- https://aws.amazon.com/blogs/compute/exploring-aws-lambda-web-functions-for-building-web-applications/

今回の配布版やAWS構成には、このIssueのための新サービス/認証/権限を追加しない。
