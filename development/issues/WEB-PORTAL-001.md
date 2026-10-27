# WEB-PORTAL-001：学生の環境準備・採点確認をブラウザへ集約する

- 状態: 小規模実証の試作中。ローカル実装と個別のAWS読取り確認を実施、Web配備と統合受入は未実施。
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
- 前回は `aws lambda list-web-functions` と誤ったサービス名で確認した。正しくは `aws lambda-web list-web-functions`。前回のエラーはCLI版やWeb Functionsの利用可否を示さない。
- 学生AWSの本人確認に使うSTS署名・短命nonce・再利用拒否の試作を追加。ローカルの模擬試験は15件合格。永続的・原子的なnonce管理の実機検証、ログインおよびLab/接続先との結び付けは未完了。
- 再接続後、学生AWSのCloudShell内で署名付きSTS要求を確認。本人accountが返り、nonceを変更すると403。署名ヘッダー・60秒有効期間は試作の前提と一致した。教師・学生間の統合試験は未実施。正しい `lambda-web list-web-functions` は成功し、学生AWSの一覧は空。作成権限は未確認。
- 成績原本の変更なしに、本人確認challengeの一回限りの消費とLab/accountの重複防止をまとめる登録処理と、独立したDynamoDB tableのtemplateを試作。ローカルで競合・期限・別accountなどを確認したが、実DynamoDB、信頼できるログイン、窓口の認可と統合試験は未実施。
- 教師AWSでtable templateと同等の構成をCloudFormation `ValidateTemplate` が受理した。
- 教師AWSに独立した試作用tableを作成し、TTL有効化を確認。架空データの同一transactionを同時送信すると1回だけ成功し、試験用元データが不変であることを確認。手組みの条件式による試験であり、`enrollment.py` 本体のAWS実行や学生accountとの統合受入ではない。試験tableと架空行は保持され、従量課金の対象となる。
- 別の架空データで `enrollment.py` 本体をSHA-256照合の上、実DynamoDBで実行。登録成功・連続再送の拒否・試験元データ不変を確認した。本人確認とchallenge読取りは模擬し、同一試用tableだけを使った。学生account連携・別tableをまたぐtransaction・期限切れは未受入。
- 学内教材ポータルのGoogle Workspace認証方式を参照し、本人確認済みGoogle ID・教師承認済みLabの一対一登録と本人の62点読取りを内部処理として試作。架空IDで登録→読取り、他ID拒否・失効・登録競合を確認。Google認証、教師承認、秘密鍵の実運用とWeb入口への統合は未実装。
- 教師AWSの試作用tableで `subject_binding.py` 本体をhash照合して実行し、2つの架空IDの同時登録は1つだけ成功、元データが不変と確認。本人確認・subject変換は模擬し、実学生の連携ではない。
- 既存採点registryをbyteそのまま収録する内部Lambda候補とpackageを制作し、再現性・非公開構成をローカル検証。教師AWSでtemplateの構文受理を確認。呼出し元の権限制限、秘密鍵と本人確認の統合、実配備は未実施。
- 学内ポータルのGoogle認証を参照したJA/RU/UZ成績画面とWeb Functions候補を作成。架空データでChromeの言語切替、記録なし・UNKNOWN・確認/保存日時と限定読取りを確認。配備packageの再現性・AWS template構文を検査。実Google、成績Lambda、学生AWSとの統合と画面配備は未実施。
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

既存の署名配布版・AWS構成は保持する。新サービスや権限を追加する際は対象と影響を明確にし、別途検証する。
