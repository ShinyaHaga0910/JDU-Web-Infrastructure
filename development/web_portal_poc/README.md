# Webポータル：読取り処理の小規模試作

2026-10-29更新。Issue [#1](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/issues/1) の初期試作。閉鎖Web Functionsは配備済み。教師/学生のIAM接続と全EC2停止中の保存成績読取りを実測した。教師End Lab後はHTTPS入口だけ応答し成績読取りは失敗したため、本人決定により**当面は教師Lab開始中に利用する**。教師EC2は閲覧に不要。Google本人確認・実学生bindingと画面の統合は未受入で、授業で使える製品ではない。以下の実験記録は各時点の結果として読む。

## 今回のコード

- `grade_reader.py` は既存の学生用lab tokenで認証し、既存 `project_lab` の62素点と現在／参照結果を返す。教師用APIの内部で使うための関数であり、HTTP入口やブラウザ認証を公開しない。生のtoken、メール、チェック明細は結果に含めない。
- `status.py` は学生アカウント内の信頼済み既存bindingを受け、STSアカウント、CloudFormationのLab/Deploymentと5台のID、EC2タグを確認する。EC2とSSMを読取り、停止・取得不能を区別する。起動、停止、コマンド送信、採点データの更新は行わない。
- `student_status_handler.py` と `student-status.template.json` は学生AWS内の状態確認専用Lambda。固定された本人account/Stack/5台だけを検証し、callerが別IDを指定する要求や起動・停止要求を拒否する。新Lambdaへの呼出しを指定した教師LabRoleに許可する設定を含み、公開URLは作らない。LabRole自体の広い権限は縮小しない。10月29日に別学生AWSへ配備し、同accountからの実呼出しを確認。別accountの許可対象外roleの拒否も確認した。指定教師LabRoleでの成功は未受入。
- `deploy_student_status.py` は学生CloudShell用の配備入口。既定では元state/baselineとAWSを照合する計画確認だけを行う。`--apply` を付けた場合だけ、独立したartifact Stackと状態Lambda Stackを作る。artifactは暗号化・公開禁止・version管理付きS3へ収録する。既存artifact Stackは用途tagと状態・公開禁止・version管理を照合し、不明な同名資源を採用しない。元5台・IAM role・SG・採点DBには変更を加えず、新しい状態Stackも上書きしない。適用前に教師roleから学生Lambdaへの新アクセス許可の確認が必要。S3はStack削除時も保持するため、試作後の整理は別途必要。
- `status_gateway.py` は本人IDとLabの認可情報を再照合し、学生account/Labから決まる固定Lambda ARNだけを呼ぶ。戻った5台のID・状態・アドレスを検査し、通信不能や他環境の結果は状態不明として扱う。返答は学生側で変更可能な状態情報であり、採点結果や課題合格の証拠には使わない。
- `identity_proof.py` は、固定のAWS STSだけに短時間の署名付きGetCallerIdentityを送り、セッションに紐付く一回限りのnonceを検証する候補を試作する。実AWSでの署名・nonceヘッダー自体は以下のように確認したが、このmoduleを使う教師・学生間の統合試験は未実施。学生ログイン、信頼できる学生Labと接続先の決定は未実装であり、公開しない。
- `challenge_store.py` は、既に認証・認可されたセッション、学生account、Labと操作窓口の識別子を前提に、期限付きchallengeのハッシュを保存し条件付き更新で一度だけ消費する試作。DynamoDBの実環境・並行要求での試験、情報源の認可とWeb入口への組込みは未実施。
- `student_proof.py` は学生側のAWS実行環境内で、SDKを使って60秒有効の署名済みSTS要求を作る試作。要求には一時認証情報が含まれるため、ログ・ブラウザURL・共有PCに保存しない。信頼済み教師側への安全な配送は未実装。
- `enrollment.py` は、認証・認可済みのサーバー内情報を受けてSTS署名を確認し、元のLab情報の一致確認、nonce消費、Lab/accountの重複防止と固定Lambda ARNの登録をDynamoDBの一つのtransactionで行う試作。元の成績tableへの書込みはない。模擬環境で同時実行・重複・情報変更を試験し、SDKがrequest形式を受け付けることも確認した。固定ARN登録追加前の版を実AWSで試したが、追加後の版、入力情報の認可や窓口自体の確認は別途必要。
- `subject_binding.py` と `identity_grade.py` は、Googleで検証済みの本人IDと教師承認済みLabを一対一に結び付け、既存の62点計算で本人の成績のみを読む内部処理の試作。本人IDは秘密鍵を使ったHMACに変換し、元のメール・Google IDをtableに入れない。原本metadataと両方向のAWS bindingが一致していることをtransactionで条件確認し、同じLabへの別ID登録を拒否する。閲覧時も対応関係とactive/token/deploymentを確認し、原本や他Labには書き込まない。秘密鍵の管理・rotation、Google本人確認・教師承認・入口との統合、実AWS受入は未実施。これら関数にブラウザの自己申告値を直接渡してはならない。
- `identity_grade_handler.py`、`build_grade_package.py`、`internal-grade.template.json` は、検証済みIDから既存成績を読む内部Lambdaの候補。指定Secrets ManagerからHMAC用keyを取得し、元のregistry bytesと既存採点コードをそのままZIPに含む。構成はFunction URL・API入口・IAM変更を作らないが、既存LabRoleを指定するためrole自体の権限を縮小するものではない。呼出し元のIAM制限とGoogle本人確認を完成させるまでは配備・公開しない。keyの発行、secret保管、配備や実データ読取りも未実施。
- `web/` はWeb Functions向けの学生用成績・状態画面の試作。既存JDU学内教材ポータルの `auth.mjs` を改行形式を除いてそのまま移し、学内Googleで検証したIDだけをサーバー内で固定の内部Lambdaへ渡す。JA/RU/UZの点数、最新の未確認、確認日時・保存日時と5台の状態を表示し、記録がない場合は0点に置き換えない。`sessions.mjs` は最大10分の独立したセッションを使い、tableにランダム値とGoogle tokenのハッシュのみを保存する。ログアウト時はサーバー側も失効し、期限切れやstore障害では成績を返さない。共有PCではGoogle自体からもログアウトするよう画面に表示する。実際の学生AWSとの接続、環境構築や新しい採点はまだつないでいない。OAuth client設定、IAMによる呼出し制限、教師承認、実学生ログインと実成績の表示は未実施。Web Functions入口はApplicationManagedであり、公開時の認証責任はアプリにある。
- `binding-table.template.json` は登録と短期challengeを保管する独立したDynamoDB table。期限属性があるchallengeだけをTTLの対象とし、期限属性のない登録情報は保持する。従量課金、AWS管理の暗号化、stack削除時の保持を指定し、既存の成績table、IAMや公開入口には変更を加えない。
- `aws_synthetic_transaction.py` は下記の実AWS試験の操作記録。対応する条件式を使う独立した試験であり、`enrollment.py` の実行やSTS認証の統合確認ではない。架空accountの既存bindingがあれば再実行を拒否する。
- bindingはサーバー側で確立しなければならず、ブラウザからの任意入力をそのまま渡してはいけない。学生本人とAWSアカウント、Stack、ポータル認証の安全な結び付けは未実装。

## ローカル試験

このdirectoryで `python -B -m unittest -v test_status test_student_status_handler test_status_package test_status_gateway test_status_flow test_grade_reader test_identity_grade test_subject_binding test_identity_grade_handler test_grade_package test_identity_proof test_challenge_store test_student_proof test_enrollment test_binding_template` を実行。架空のAWS応答で、登録→本人ID認証→固定窓口→学生5台の状態読取りの接続、停止、取得不能、別account/Stack/タグの拒否、62点と現在UNKNOWNの併存、他Lab/誤tokenの拒否、認証用nonceの期限・再利用・不正な接続先の拒否を検証する。ID登録から既存採点の表示まで、別ID拒否、登録の失効・同時登録の競合も架空データで確認する。内部Lambda packageの再現性、元registry bytes、入口を公開しないtemplateも確認する。botocoreを導入した環境では、架空資格情報を使った実SDKによる署名生成・request形式も確認する。実AWS試験ではない。

`web/` では `npm ci --omit=dev`、`npm test`、`python -B -m unittest -v test_web_package` で、署名・組織・nonce検証、認証済みidentityの限定利用、ログアウト後の再利用拒否、期限とstore障害、未登録拒否、UNKNOWN、言語、元registryと表示上限の一致、閉鎖初期設定と配備ZIPの再現性を確認する。Google署名・セッション保存先は架空鍵・模擬DB。依存関係は2026-10-27時点の `npm audit --omit=dev` で0件。Chromeのlocalhost表示と言語切替は架空データ・模擬認証で確認した。実Googleログインや本番ブラウザ受入を意味しない。

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

学生画面のWeb Functions templateもbyteのSHA-256を照合してCloudFormation `ValidateTemplate` を通過。作成時は閉鎖設定を初期値とするが、公開HTTPS endpoint自体は作成されるため、配備前に対象・権限と公開範囲の確認が必要。Web Functions/内部成績Lambdaはどちらも未配備。

状態機能追加後、学生側Lambda・教師側内部Lambda・Web Functionsの3 templateを教師AWSでhash照合し `ValidateTemplate` に受理された。教師LabRoleから予定する学生側Lambda ARNへの `lambda:InvokeFunction` はIAM policy simulationで `allowed`。学生側のresource policy・実権限・実呼出しは確認しておらず、simulationだけではcross-account通信成功を意味しない。学生側Lambdaには、教師LabRoleだけへの新たな呼出し許可を含むため配備時に確認が必要。

## 残る受入

### 最新の実機到達点（2026-10-29）

本人承認後、教師probe StackもCREATE_COMPLETEとなった。実CodeSha256と既存LabRoleの一致を確認し、その関数から既存の保存成績62/62点と、別学生AWSの5台running/SSM Onlineを取得した。読取り前後のLab全partitionのSHA-256は一致した。指定教師LabRole→学生LabRoleの実呼出し成功であり、CloudShellからの前述の拒否と区別する。

続いて検証操作として教師の中継EC2と学生の元5台を明示的に停止した。元構成/ディスク/鍵の置換や再作成は行っていない。教師EC2 stoppedで同じ成績全項目を読めることを確認。その後 `verify_teacher_probe.py` 本体をhash照合して実行し、教師EC2と学生5台がすべてstoppedでも、保存成績62/62と全項目が一致、Lab全partitionが不変、probeの公開URLがないこと、起動要求/他Lab指定の拒否を確認した。5台のSSMはunknownと返り、その値を成績0点へ変えなかった。

[全台停止時の実測記録](verification/2026-10-29-stopped.public.json)。検査コードは読取りだけを行い、実行するだけで停止/再開しない。既存の中継EC2も現在stoppedのため、従来の中継経由の提出は再開が必要。Web Functions配備、Google本人確認と学生AWSとの登録、学生向けブラウザ画面の実受入は未完了。

### 学生End Lab後の結果と現在の境界

本人が学生LabをEnd Labにし、画面のTerminated / Lab terminated / 00:00を確認。教師Labは開始したまま、教師EC2はstoppedの条件で、保存成績62/62と全項目を読めた。一方、学生状態はunavailableとなり、全項目の停止中受入scriptは合格しなかった。EC2だけの停止と、Labセッションの終了は同じ条件ではない。

秘密を出さない限定診断を追加し、教師probeはv3（SHA-256 `71e37ead8f52689b55726bcbde673acff8e9851ffca4d5dd362ff1876cf3fe26`）、学生statusはv2（`d69a54c60c23556dd50160678adf4912e1f3064d50ecdf1f764718665f23f096`）へCodeだけを更新。IAM・元5台の構成は変更していない。学生Labの通常再開とAWS再ログイン後、同じ5台running/SSM Online、同じ成績全項目と全partitionを再確認した。

その後もう一度学生LabをEnd Labにすると、まず学生Lambda内の `DescribeStacks` がAccessDenied、時間をおいた呼出しでは `Invoke` 段階でKMSAccessDeniedExceptionとなった。[実測記録](verification/2026-10-29-student-end-lab.public.json)。同じ時点でも保存成績全項目と元Lab全partitionは不変だった。公開画面へはこの診断を渡さず、状態取得不能とする。取消policyの解除やKMS/IAMの緩和はしていない。学生CloudShellの古い資格情報もvoc-cancel-credで拒否されたが、Lambda側と同一の取消機構だとは断定しない。

この学生End Lab試験時点では学生Lab終了・教師Lab開始・教師EC2停止だった。教師Lab終了後の試験と、その後の本人決定は下記の記録を優先する。Web FunctionsのHTTPが残ることだけでは、依存先の継続利用は証明できない。

### 教師End Lab試験用の閉鎖Web（配備済み）

`web/acceptance-health.mjs` と `/healthz/acceptance` は、明示的なclosed-mode試験設定だけで動く読取り候補。固定検証Labのmetadata/成績行の取得可否、既存Python成績projectionの呼出し可否を別々のbooleanで返す。点数・メール・token・AWSエラー本文を公開しない。通常の学生運用modeでは404、個別成績画面は閉鎖したままである。30秒の結果cacheは確認日時付きなので、End Lab後の試験では終了時刻より新しいcheckedAtを確認する。

`web/web-artifacts.template.json` は専用の暗号化・非公開・version管理付きS3と、同account内の指定Web Functionのrevisionだけへcodeを読ませるservice許可の候補。[AWSのcode搬入条件](https://docs.aws.amazon.com/lambda/latest/dg/web-functions-code-s3.html)に従い、既存のversion管理なしの教師S3を流用して設定変更しない。Web Functions側はNode24、1実行環境・同時2・毎秒2要求までとし、試験中の呼出しを抑える。

Node 21件・Web package 3件が合格、npm auditの既知問題は0。ZIP SHA-256 `6a27a1d815b82b6e3d54dc6687b1e8ed1dca794cbcb00fbd637ccdf4485cd9fa`、3,271,147 bytes。Google認証/本人bindingの受入を代替するものではない。

搬入ZIPのhash `a24dea1e7f00417865ae48992afcb940f794021460eb26b1295be276d7bc97b4` と3ファイルの内包名を教師CloudShellで照合し、両templateをAWS `ValidateTemplate` が受理した。本人から6資源の追加と教師End Lab後の試験の承認を受け、専用S3 Stackを作成。S3のversioningと公開遮断、版付きcodeのhashを確認した。

最初のWeb Stackは事前検査で `MaxEnvironments: 1` が最小値2未満としてROLLBACK_COMPLETEになった。`DescribeEvents` と実provider schemaから、環境上限を2、受付上限を最小の正数100/秒に修正。単なる `ValidateTemplate` の受理ではこの制約を保証しない。元失敗Stackの資源が空であることを確認し、削除せず記録を保持。Web Function名を独立parameterにし、S3許可対象の同じFunction名を保持して、新規wrapper Stack `jdu-web-portal-poc-20261029-r1` に4資源Addの検査済みchange setを適用した。追加のIAM・公開範囲変更はしていない。

修正後はCREATE_COMPLETE。2026-10-29 05:35:22 UTC、ChromeとCloudShellの実HTTPで `/healthz` 200、`/healthz/acceptance` 200（3項目trueと日時だけ）、`/grades` 503を確認。教師EC2はstopped、教師Labは開始中、学生Labは終了済み。個人成績の公開やGoogle本人認証の受入ではない。[終了前の実測記録](verification/2026-10-29-web-before-teacher-end.public.json)。修正後のpackage検査3件合格。

### 教師End Lab後の実測（2026-10-29）

本人の終了操作後、教師LMSにTerminated/00:00/Lab terminatedが表示された。終了状態の確認後に、Chromeから05:40:49 UTCと05:43:03 UTC、既存CloudShellからAWS資格情報を使わない公開HTTPS要求で05:41:59 UTCに再観測した。いずれもstorage/savedGrades/gradeServiceがfalseで、内部30秒cacheを超えて日時が更新された。実HTTPはhealth 200、可否probe 503、個人成績503。[終了後の実測記録](verification/2026-10-29-teacher-end-lab.public.json)。

**HTTPS入口は動くが、このLab内構成の保存成績閲覧は教師End Lab後に不合格**。3項目は公開可否指標であり、storage照合が成功しなければ成績行のQuery自体を行わないため、保存行の消失を示さない。内部エラーを公開しない設計なので、AWSの正確な拒否理由は未特定。cold startや長時間後の稼働も未確認。成績値・元DB・IAM制限は変更せず、教師Labを自動再開していない。全partition不変の再照合はこの公開入口からできない。

本人はこの結果を受け「当面は教師Lab開始中の利用でよい」と決定した。通常AWS accountへの移行と教師End Lab中の保存閲覧は後続課題に移し、既存教師Lab内で本人連携・登録・状態表示の統合を続ける。移行や追加契約は行っていない。

### 現行の再開手順

1. 教師がChromeのClass193548から通常のStart Labを行い、Readyを確認する。AWSを開くときは新しいセッションを使い、旧CloudShell資格情報の拒否を制限解除で回避しない。
2. 公開可否probeの確認日時が再開後で、3項目trueへ復帰するか確認する。30秒cacheの前の結果を復帰と扱わない。教師EC2の状態は別に確認し、閲覧試験のため起動状態を必須にしない。
3. 本人成績はGoogle本人認証・承認済みLab登録・内部成績readerの統合受入後に開く。可否probe成功だけでは `/grades` の閉鎖を解除しない。
4. 学生の現在状態や新しい採点が必要な場合だけ、学生Labと対象EC2/SSMの利用可能性を確認する。学生Lab終了中の状態取得不可は、保存成績の削除や0点化の理由にしない。

LabのStartはAcademy側が既存EC2を自動起動する場合がある。画面やprobeがEC2を自動起動する処理は追加しない。教師EC2の停止は明示的な試験操作として記録し、元ディスク・認証を保持する。

10/29にこの再開を実行し、教師Ready後の05:50:03 UTCに可否3項目trueへ復帰。Academyで自動起動した元教師EC2を明示的に停止し、05:53:45 UTCにもHTTP可否200/3項目true、元の成績62/62・全成績projection・全Lab partitionの不変を確認した。学生Labは再開せず、学生5台の現状態は再観測していない。`/grades` は503のまま。[再開後の実測記録](verification/2026-10-29-teacher-restart.public.json)。

### 本人ログインの次の準備

学内Google認証はコードを用意した段階で、実OAuth clientは未設定。既存Google Cloud project/OAuth設定の有無を本人へ確認中。新しいclientやsecretは作成していない。

- 登録対象のorigin：`https://d9r6gn83y8wkl4xl.gpb.lambda-web.us-east-1.on.aws`
- 現コードのcallback：`https://d9r6gn83y8wkl4xl.gpb.lambda-web.us-east-1.on.aws/auth/callback`
- 現コードの要求scope：`openid email`、許可対象：検証済み `jdu.uz` identity。AWS AcademyのログインメールとGoogle本人IDは別々に検証する。
- Google client設定だけで開放しない。内部成績reader、subject鍵、session store、教師承認済みLab/account/subject登録がそろってから、本人・未登録・別人・失効・ログアウト・教師側取得不可と再開を実ブラウザで受入する。
- secretや署名要求を会話、Git、URL、共有Windowsへ保存しない。新しい認証情報の設定は、具体的な計画を用意してから本人操作で行う。

### 配備前の再開・準備記録（2026-10-29、履歴）

Chromeの教師用とEdgeの別学生用を、それぞれ予定したAWS accountとして確認。学生CloudShellで `status.py` と `plan_student_status.py` 本体を、転記payloadのSHA-256 `bfc77f14a4438975bff91aa872c9cbc839224161e4a81425d45fad042f460150` を照合して実行した。保存state/baseline、StackのLab/Deploymentと5台、EC2タグの一致、全5台running・SSM Onlineを確認。新Lambda/Stackの名前衝突もなかった。AWSリソースの変更は行っていない。

学生の既存LabRoleはLambda serviceから引き受け可能な設定だった。学生accountに `jdu-` prefixのartifact bucketはなかった。教師側からの呼出し許可・実配備は別工程であり、この読取り成功をcross-account受入とは扱わない。

同日のローカル検査はPython 102件（他のtest moduleからimportされたfixtureクラスの重複実行を含む）、Node 15件、Web配備package 2件が合格。模擬AWS/Googleを使う検査と実機結果を区別する。

続いて配備入口の模擬試験5件が合格。秘密を含まない7ファイルの搬入ZIP（SHA-256 `b6e8ce0b8b77fba2b7ce775157c4a5949a3d692cac1ed6eac6d1ee9f410005a6`）を学生CloudShellへuploadし、hash・内包名を確認して計画モードを実行した。Lambda用ZIPは2,693 bytes、SHA-256 `56fe94f2a0f2a9820748be047ba07e1523425991c66da23581e07604bcc32065`。

両templateのAWS構文受理後、本人が追加構成を承認。`jdu-web-portal-status-artifacts` と `jdu-web-portal-status-class193548-test1` の2 Stackを作成し、`CREATE_COMPLETE` を確認した。非公開S3、既存LabRoleを使う状態Lambda、指定教師LabRoleの呼出し許可が残り、従量課金の対象となる。新LambdaのCodeSha256が上記ZIPと一致し、Activeであること、実resource policyの許可先が指定教師LabRoleだけであることを確認。同じ学生accountから呼び出すと5台running・SSM Online、`operation=start` はunauthorized。元5台に作成/更新/起動/停止操作は行っていない。

教師CloudShellのprincipalはLabRoleとは別の既存voclabs roleで、学生LambdaへのDryRunはAccessDeniedとなった。これは意図した許可対象外の拒否であり、教師LabRoleの呼出し成功を意味しない。教師側の既存EC2にはIAM instance profileがなく、これを変更して試す方法は採っていない。

そのため `teacher_probe_handler.py` と `teacher-probe.template.json` を準備した。教師側のIAM経由だけで使う固定検証Lab専用Lambdaで、指定Labの保存成績と学生側状態の読取りを別々に呼ぶ。成績読取りは学生LambdaやEC2を呼ばない。Googleログインや学生向け認可の代用にはしない。模擬試験5件・packageの再現性/既存registry bytes/ロードが合格。ZIP SHA-256は `c53f93a644a2c7948e5cb175896150a37903c27917a12121f7c0f47155394d6c`。

教師の既存S3は公開禁止4項目がtrue、version管理は無効だった。設定は変更せず、上書き禁止条件とSHA-256 checksumを付け、hash入りの別keyへ検証コードだけを収録した。教師CloudShellで転記hashとtemplateを確認し、`jdu-web-portal-teacher-probe-20261029` / `private-readonly-probe` のCREATE change setを準備。CREATE_COMPLETE/AVAILABLEで、変更はLambda 1つのAddだけ。**まだ実行していない**。教師LabRoleを新関数へ付けるため、適用前の確認が必要。新関数のCodeSha256照合・実呼出し・EC2停止中/End Lab後は未実施。

1. 教師・学生の実アカウントと既存5台を確認し、既存の保存済み成績と読取り結果を照合する。
2. 教師Lab開始中のEC2非依存経路をWeb Functionsへ接続し、教師側の取得不可→通常再開後の復帰と、学生Lab終了後の保存閲覧を別々に確認する。教師End Lab中の閲覧は後続課題に保持する。
3. 学生のAWS identityを検証して信頼済みbindingを確立し、他人のLabを拒否する。共有PCに秘密鍵や長期認証情報を残さない。
4. 実5台のEC2/SSMとIP、署名期限をブラウザで確認する。試作はまだ署名期限を表示しない。署名版r2の期限は2026-10-27 14:24:57 UZTで、新規構築には更新が必要。

同じ5台と既存のdisk、採点結果、認証情報、署名版を保持する。観測不能を0点に変換せず、ページを開くだけでEC2を起動しない。元のEC2からの提出は従来の教師中継EC2に依存したままである。
