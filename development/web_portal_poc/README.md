# Webポータル：読取り処理の小規模試作

2026-10-27。Issue [#1](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/issues/1) の初期試作。**まだWeb Functionsに配備していない**。学生の画面・学生AWSとの認証済み接続・End Lab後の実機受入は未実施で、授業で使える製品ではない。

## 今回のコード

- `grade_reader.py` は既存の学生用lab tokenで認証し、既存 `project_lab` の62素点と現在／参照結果を返す。教師用APIの内部で使うための関数であり、HTTP入口やブラウザ認証を公開しない。生のtoken、メール、チェック明細は結果に含めない。
- `status.py` は学生アカウント内の信頼済み既存bindingを受け、STSアカウント、CloudFormationのLab/Deploymentと5台のID、EC2タグを確認する。EC2とSSMを読取り、停止・取得不能を区別する。起動、停止、コマンド送信、採点データの更新は行わない。
- `identity_proof.py` は、固定のAWS STSだけに短時間の署名付きGetCallerIdentityを送り、セッションに紐付く一回限りのnonceを検証する候補を試作する。実AWSでの署名・nonceヘッダー自体は以下のように確認したが、このmoduleを使う教師・学生間の統合試験は未実施。学生ログイン、信頼できる学生Labと接続先の決定は未実装であり、公開しない。
- `challenge_store.py` は、既に認証・認可されたセッション、学生account、Labと操作窓口の識別子を前提に、期限付きchallengeのハッシュを保存し条件付き更新で一度だけ消費する試作。DynamoDBの実環境・並行要求での試験、情報源の認可とWeb入口への組込みは未実施。
- `student_proof.py` は学生側のAWS実行環境内で、SDKを使って60秒有効の署名済みSTS要求を作る試作。要求には一時認証情報が含まれるため、ログ・ブラウザURL・共有PCに保存しない。信頼済み教師側への安全な配送は未実装。
- `enrollment.py` は、認証・認可済みのサーバー内情報を受けてSTS署名を確認し、元のLab情報の一致確認、nonce消費、LabとAWS accountの重複防止登録をDynamoDBの一つのtransactionで行う試作。元の成績tableへの書込みはない。模擬環境で同時実行・重複・情報変更を試験し、SDKがrequest形式を受け付けることも確認した。実AWSでは本人確認などを模擬して試作本体を試したが、入力情報の認可や窓口自体の確認は別途必要。
- `subject_binding.py` と `identity_grade.py` は、Googleで検証済みの本人IDと教師承認済みLabを一対一に結び付け、既存の62点計算で本人の成績のみを読む内部処理の試作。本人IDは秘密鍵を使ったHMACに変換し、元のメール・Google IDをtableに入れない。原本metadataと両方向のAWS bindingが一致していることをtransactionで条件確認し、同じLabへの別ID登録を拒否する。閲覧時も対応関係とactive/token/deploymentを確認し、原本や他Labには書き込まない。秘密鍵の管理・rotation、Google本人確認・教師承認・入口との統合、実AWS受入は未実施。これら関数にブラウザの自己申告値を直接渡してはならない。
- `identity_grade_handler.py`、`build_grade_package.py`、`internal-grade.template.json` は、検証済みIDから既存成績を読む内部Lambdaの候補。指定Secrets ManagerからHMAC用keyを取得し、元のregistry bytesと既存採点コードをそのままZIPに含む。構成はFunction URL・API入口・IAM変更を作らないが、既存LabRoleを指定するためrole自体の権限を縮小するものではない。呼出し元のIAM制限とGoogle本人確認を完成させるまでは配備・公開しない。keyの発行、secret保管、配備や実データ読取りも未実施。
- `binding-table.template.json` は登録と短期challengeを保管する独立したDynamoDB table。期限属性があるchallengeだけをTTLの対象とし、期限属性のない登録情報は保持する。従量課金、AWS管理の暗号化、stack削除時の保持を指定し、既存の成績table、IAMや公開入口には変更を加えない。
- `aws_synthetic_transaction.py` は下記の実AWS試験の操作記録。対応する条件式を使う独立した試験であり、`enrollment.py` の実行やSTS認証の統合確認ではない。架空accountの既存bindingがあれば再実行を拒否する。
- bindingはサーバー側で確立しなければならず、ブラウザからの任意入力をそのまま渡してはいけない。学生本人とAWSアカウント、Stack、ポータル認証の安全な結び付けは未実装。

## ローカル試験

このdirectoryで `python -B -m unittest -v test_status test_grade_reader test_identity_grade test_subject_binding test_identity_grade_handler test_grade_package test_identity_proof test_challenge_store test_student_proof test_enrollment test_binding_template` を実行。架空のAWS応答で、5台停止、取得不能、別account/Stack/タグの拒否、62点と現在UNKNOWNの併存、他Lab/誤tokenの拒否、認証用nonceの期限・再利用・不正な接続先の拒否を検証する。ID登録から既存採点の表示まで、別ID拒否、登録の失効・同時登録の競合も架空データで確認する。内部Lambda packageの再現性、元registry bytes、入口を公開しないtemplateも確認する。botocoreを導入した環境では、架空資格情報を使った実SDKによる署名生成・request形式も確認する。実AWS試験ではない。

既存7群の回帰試験では、6群が合格（計3件skip）、配布群は固定署名版の期限切れにより2件のsetupで停止した。期限を回避したり署名を変更したりしていない。

## 教師AWSでの読取り確認

2026-10-27、Class 193548の教師AWSから既存DynamoDBを直接読み、既存Pythonの `project_lab` で検証用Labの保存済み成績が62/62、現在の未解決が0、検証用コンテキストであることを確認した。教師EC2を経由しない読取りだが、そのEC2は当時runningであり、**EC2停止中・End Lab後の実証ではない**。この確認はCloudShellで行い、新しいWeb Functionsや `grade_reader.py` のAWS配備を意味しない。

同日、別の学生AWSのCloudShellからSTSのアカウント、保存済みstateとbaseline、CloudFormationのLab/Deploymentと5台のinstance ID、各EC2タグを照合した。5台ともrunning・SSM Onlineを確認。個別の読取り操作であり、`status.py` やブラウザ経由での実証ではない。学生ポータルとAWSアカウントの認証済み連携は引き続き未実装。

同日、学生CloudShell内でbotocoreを使い、60秒有効・nonceヘッダーを含む署名付きSTS要求を生成。正しいnonceで学生AWS accountを確認し、nonceを変えた要求は403となった。署名対象ヘッダーは `host;x-jdu-nonce` で試作の期待値と一致。署名URLや認証情報は出力・保存しなかった。実験は同じCloudShell内で完結しており、教師側への送信、リプレイ対策を含む統合確認ではない。

学生AWSの `aws lambda-web list-web-functions` は正常終了し、一覧は空だった。これは一覧読取り権限の確認であり、作成・配備権限を確認したものではない。

教師AWSのCloudShellから転記したtable templateをCloudFormation `ValidateTemplate` に渡し、受理されたことを確認した。この段階ではbyte一致やstack作成を確認していなかった。

続いてローカルtemplateのSHA-256をCloudShell内で照合し、教師AWSの独立した `jdu-web-portal-binding-poc-20261027` stackを作成、`CREATE_COMPLETE` とTTL `expires_at` の `ENABLED` を確認。従量課金の試作用tableは残っている。架空Lab・架空accountの行で、元データの条件確認、challenge消費、2つのbinding作成を同一transactionにまとめ、2つの同時要求のうち1つが成功、もう1つが拒否されることを実DynamoDBで確認した。架空の元データは不変。成績tableは使っていない。この並行試験は条件式を手作りしたもの。試験行は保持され、試験用challengeには長い期限が入っているため自動的にすぐ消えない。

別の架空Lab・accountを用い、`enrollment.py` のSHA-256 `fe12707d604d834fb3cbc3f6bdfd8430dbfa5ed66ab6e388c15ff8b0e5306046` を確認した上で同ファイル本体をCloudShellのmemoryで実行。実DynamoDBへの登録が成功し、同じchallengeの連続再送は拒否、架空の元データは不変だった。本人確認とchallenge読取りは模擬し、成績の模擬元データとbindingは同じ試作用tableを使用。別tableをまたぐ実行、期限切れ、実学生STSとの結合は未確認で、授業受入ではない。

さらに `subject_binding.py` のSHA-256 `916a72a64f442b1b2b4b04d712d49834c1e2e95db325c7fd7f0fcabb1859702a` を照合し、別の架空Labに対して2種類の架空Google IDを同時登録。実DynamoDBで一方のみ成功し、元の架空metadataは変わらなかった。Google検証・subject変換は模擬、成績とbindingは同じ試作用tableであり、実アカウントとの紐付けや画面の受入ではない。

内部成績LambdaのtemplateはbyteのSHA-256を照合して教師AWSのCloudFormation `ValidateTemplate` を通過した。これは構文の受理であり、AWSへの配備、IAM呼出し制限、Secrets Managerの利用、実成績閲覧を確認したものではない。

## 残る受入

1. 教師・学生の実アカウントと既存5台を確認し、既存の保存済み成績と読取り結果を照合する。
2. EC2非依存の経路をWeb Functionsへ接続し、EC2停止中とEnd Lab後の依存API/DBを別々に確認する。
3. 学生のAWS identityを検証して信頼済みbindingを確立し、他人のLabを拒否する。共有PCに秘密鍵や長期認証情報を残さない。
4. 実5台のEC2/SSMとIP、署名期限をブラウザで確認する。試作はまだ署名期限を表示しない。署名版r2の期限は2026-10-27 14:24:57 UZTで、新規構築には更新が必要。

同じ5台と既存のdisk、採点結果、認証情報、署名版を保持する。観測不能を0点に変換せず、ページを開くだけでEC2を起動しない。元のEC2からの提出は従来の教師中継EC2に依存したままである。
