# Web Functionsを使った学生用入口の実現性と構成案

更新：2026-10-23（Asia/Tashkent）。対象：[Issue #1](https://github.com/ShinyaHaga0910/JDU-Web-Infrastructure/issues/1)。実現性の検討であり、新規配備や既存Labの変更は行っていない。

## 結論

環境の初期準備・状態確認・採点結果の閲覧を、Web Functionsの固定ブラウザ入口へ集める構成は実現できる見込みがある。教師側に入口と成績表示、学生側のAWSアカウントに本人の環境を操作する窓口を置く案を推奨する。最初の実証対象は、**EC2停止中の成績閲覧**と**別学生アカウントの状態を正しく読むこと**に絞る。

Web Functionsの利用可否とEnd Lab後の画面利用は本人が確認済み。追加の確認対象は、成績DB/APIへのアクセス、本人アカウントとの結び付け、初期構築とcheckerのブラウザ向け接続である。現行のCloudShellツールをWeb画面から起動するだけで完成するものではない。

## Labの稼働についての前提

- **本人確認済み**：Learner Labを終了してもWeb Functions部分は利用できた（2026-10-23の本人説明）。この事実を設計の前提として採用する。
- **運用前提**：End Lab後は演習用EC2を利用できない。ポータルは、EC2内のWeb・DNS・DB・RDP・SSM実行を継続できるとは扱わない。
- **別途確認**：Web Functionsから教師の採点API/成績DBを呼べること、学生側のAWS APIを呼べることは、それぞれ別の確認項目。画面の応答だけで依存サービスの利用まで合格にはしない。
- EC2のstoppedだけでは「End Lab」「P3/M3の意図した停止」「手動停止」を判別できない。AcademyのLab状態を確実に取得できるAPIは、今回の調査では確認していない。STSのaccount確認もLab稼働状態の証明にはならない。

### 提案する学生向けの動作

| 操作 | Lab稼働・必要EC2がrunning/SSM Online | EC2停止中・Lab終了後 |
| --- | --- | --- |
| 教材・手順を読む | 表示する | 表示する |
| 保存済みの成績・提出履歴を見る | 表示する | 最終確認日時と一緒に表示する。採点API/DBの利用確認が条件 |
| 環境の状態を見る | 本人の5台と現在の接続先を表示する | 停止/接続不能を表示。状態を取得できない場合は「確認できない」と表示 |
| 初回の環境を準備する | 本人のAWSログインと導入確認を経て実行する | 実行せず、AcademyのLabを開く案内を表示 |
| HTTP/DNS/DB/アプリを新しく採点する | 必要前提を確認して実行する | 再開待ち。保存済み成績を0点に置き換えない |
| RDP・演習Web・通常SSMを利用する | 現在の接続先を案内する | 再開が必要と表示する |

P3/M3の停止状態の記録は専用フローとして残す。他の機能確認とは分け、停止前の証拠→同じWebのstopped観測→再開後の照合を維持する。

ポータルを開く、画面を更新する、過去成績を見るだけでEC2をStartしたり、新しい5台を作成したりしない。停止理由が分からない場合も同様。AcademyのStart Labをポータルが代行する設計にはしない。

## 固定入口の構成案

| 部分 | 置き場所と役割 |
| --- | --- |
| 教師・学生の入口 | 教師側Web Functions。本人認証、教材、状態、保存済み成績、操作の進捗を表示 |
| 成績の正本 | 既存の教師側DynamoDBとPython採点API。62素点・原本・receipt・現在状態/参照成績を継承 |
| 学生側の操作窓口 | 学生本人のAWSアカウント内。既存LabRoleの利用可能な権限でCloudFormation/SSMを呼ぶ。Web Functions等への配備・必要APIは実証対象 |
| 演習対象 | 既存方針のEC2 5台。学生がP/Mで設定するWeb/DNS/DB/アプリと接続経路を維持 |
| 操作の保存 | 専用の永続ストア。Lab/account/deployment、job ID、Stack/SSM command ID、段階、最終日時を保存 |

教師の表示用stateと、学生本人の操作用stateは保存先と権限を分ける。既存CloudShellのprivate stateをブラウザへダウンロードさせず、本人account内で検査・移行する。大容量の依存資源は既存repoへの搬入を継承し、ポータル本体へ全コピーしない。

ブラウザ→入口と、入口→学生窓口/採点APIはHTTPS443。学生窓口→AWS APIもHTTPS443。EC2のSSM agentは既存の専用接続口へHTTPS443で接続する。Web Functionsを演習WebやRDPの中継には使わない。

Web Functionsの組込みHTTPSドメインを使えるため、新しい独自ドメインの購入を必須にしない。[AWSのWeb Functions概要](https://docs.aws.amazon.com/lambda/latest/dg/web-functions.html)

### 教師EC2との依存を切る場所

現行の教師templateは、成績をEC2内に保存していない。DynamoDB＋Python Lambda＋API Gatewayを持ち、教師EC2は固定IPのTLS中継である。

- [build_template.py](../01_roles/cyber_security/tools/web_lab_teacher/build_template.py)のProgressTable/ProgressFunction/ProgressApi/TeacherInstanceで構成を確認できる。
- [grading.py](../01_roles/cyber_security/tools/web_lab_assessment/grading.py)のproject_labが、現在状態と参照成績を分ける。

新ポータルの成績閲覧は、停止し得る固定IP中継EC2を経由せず、既存のサーバーレス採点APIへ接続する。本人の成績だけを返す認証付き読取り口を用意し、既存のPython側で同じ採点投影を使う。Node.js側で62点の計算を再実装しない。

**既存EC2からの提出は、現在も固定IP中継を使う。** ポータルの追加だけではこの経路は変わらない。中継EC2停止中の新規提出まで対応するなら、学生側窓口が正規checkerの結果を回収し、既存認証と元request IDのまま採点APIへ渡す経路を別途受入する。ブラウザから渡された自己申告の得点は保存しない。

既存DDB、API、署名配布物、5台、鍵、採点tokenは、構成案の検討のために更新・再発行しない。

## 学生が使う流れ

1. 教師が固定の入口URLと本人用の初回案内を渡す。ポータルの本人認証と、AWS Academyの認証は区別する。
2. 学生は自分のAcademyからStart Labを行い、自分のAWSコンソールを開く。
3. 初回だけ「環境を準備」から、用意したCloudFormationの確認画面へ進む。アカウント・資源・既存環境の有無を確認する。導入用の窓口を本人アカウントへ配置する。
4. 本人アカウントと匿名Lab IDを教師の登録に結び付ける。以後はポータルから状態確認・初期環境準備・採点確認を行う。
5. 演習本体は教材どおりに構築する。初期準備ボタンがM問題の完成設定まで作ることはない。
6. End Lab後は同じ入口から教材と保存済み成績を見られる構成にする。新しい実行が必要なら、AcademyのLabを開き直してから状態を確認する。

CloudFormationにはブラウザのquick-createリンクがある。初回導入をブラウザ操作にできる根拠になるが、現行の5台templateへの直リンクだけでは、署名確認・版/価格の検査・内部SSH・個別採点登録・初期化後の通信閉鎖を代替しない。これらを実行する既存controllerの役割を残す。[CloudFormation quick-create](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-console-create-stacks-quick-create-links.html)

NoEchoのpassword等はquick-createのURL引数では渡せない。初回コードやRDP passwordをURLへ埋め込まず、本人の画面の非表示入力で扱う。既存学生は現在のstate/認証を取り込む更新経路、新規学生は初回作成経路に分ける。

## 権限と本人の結び付け

ポータルへのログインは、学生AWSの操作権限を自動で与えない。Web Functionsが使えるという本人確認も、CloudFormation/EC2/SSMの全操作が許されることまでは意味しない。[Web Functionsの実行roleと権限](https://docs.aws.amazon.com/lambda/latest/dg/web-functions-permissions.html)

教師側roleが学生accountのroleをAssumeRoleできるとは仮定しない。最初は学生側に操作窓口を置き、既存LabRoleの範囲を調べる。LabRoleが広い権限を持つ場合、アプリ側の対象制限がIAM権限そのものを縮めるわけではない。操作窓口は保存済みbindingとタグを照合し、自分のLab以外のStack/EC2を拒否する。

初回登録では、ブラウザが送ったaccount文字列やendpoint URLだけを信用しない。候補は、AWS側で検証されたIAM付き登録口、または固定STS宛ての短期署名要求を使ったaccount確認。後者もnonce/有効期限/再利用拒否を含めて実証する。STS GetCallerIdentityは呼出元account/roleを返すが、AcademyのLab稼働を返すAPIではない。[STSの仕様](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html)

本人確認は窓口のendpoint・匿名Lab IDにも結び付ける。account一致だけを理由に、ブラウザが指定した任意のURLへ認証情報や操作要求を転送しない。検証できない窓口は操作対象に登録しない。

学生ブラウザの入口はApplicationManaged＋アプリの本人認証を候補とする。AWSコンソールへのログインだけでは通常のブラウザ遷移がSigV4署名付きになるわけではない。教師→学生窓口の機械通信をIamAuthにする場合は、両accountの許可が必要で、LabRoleを変更できるかも確認する。許可が成立しない場合は、登録済みの窓口間だけの認証を検討する。[endpoint認証](https://docs.aws.amazon.com/lambda/latest/dg/web-functions-endpoint-access-control.html)

共有Windowsへ秘密鍵やAWS access keyを保存させない。本人セッションは短期のHttpOnly/Secure cookieを候補とし、操作にはCSRF対策と明示的なPOSTを使う。password・採点tokenをURLやlocalStorageに残さず、ログアウトを用意する。教師管理認証を学生側へ渡さない。

## 既存コードを接続するときに必要な作業

| 現行の部分 | 再利用すること | ブラウザ化に必要なこと |
| --- | --- | --- |
| 署名controller・初期配備 | 署名/期限、版、価格、同じ5台、通信閉鎖、既存保持 | 端末入力とローカルfileに依存する処理を、本人のjob/stateと秘密の入力経路へ分ける |
| 課題checker | 固定registry、P/M対象、62素点、SSM観測 | `task_id`等の限定操作APIを用意。自由なshellや完成fixtureは受け付けない |
| 採点受付 | 原本、receipt、再送、現在状態と参照成績 | 本人だけのJSON読取りと、正規checkerからの提出を既存サービスへ接続 |
| 学生用進捗URL | 本人の採点情報と表示内容 | 毎回のsession URL生成/転記を、固定入口での本人認証に置き換える |
| M5/M6等の対話確認 | 正規/誤passwordを使う実機能確認 | TTY/getpassの代替となる、秘密を残さない入力経路を追加受入 |

現行[student.py](../01_roles/cyber_security/tools/web_lab_release/student.py)は本人CloudShellのhome、保護file、PATHを前提にする。[assessment_check.py](../01_roles/cyber_security/tools/web_lab_assessment/assessment_check.py)のinteractiveは、AWS-StartInteractiveCommandとgetpassを使う。

Web Functionsの現行対応runtimeはNode.jsであり、既存Python CLIをそのままWeb Functionとして配置する案は採らない。入口をNode.js、既存のPython採点APIとEC2上の観測コードを再利用する。[runtime仕様](https://docs.aws.amazon.com/lambda/latest/dg/web-functions-runtimes.html)

HTTP仕様ではUpgrade等の接続用headerが除去されるため、既存SSMの対話接続をそのままWeb Function経由のWebSocketへ流せるとは扱わない。対話入力の秘密をSSM command引数や履歴へ平文で入れる代用もしない。初版では通常の状態/構成確認を先行し、対話機能の完全移行は別の実証項目とする。[HTTP仕様](https://docs.aws.amazon.com/lambda/latest/dg/web-functions-http.html)

## 長い構築と途中停止への対応

HTTP要求を構築完了まで保持せず、受付後にjob IDを返す。CloudFormation/SSMに受理された実行は、そのStack ID/command IDで確認する。次段階へ進む処理も、保存済みの同じjobから再開する。画面を閉じても、Web Functionsのメモリーだけに状態を残さない。

Web Functionsは不要な実行環境を破棄するため、重要なstateはDynamoDB/S3等へ保存する。Nodeのglobal変数や/tmpを正本にしない。[実行環境の仕様](https://docs.aws.amazon.com/lambda/latest/dg/web-functions-env-lifecycle.html)

- 二重クリック・再読込は同じ操作IDへ結び付け、同じ5台を重複作成しない。
- API受理後に応答を失った場合は「確認待ち」。状態を照合する前に再実行しない。
- 採点途中にEC2が停止した場合は「中断/再開待ち」。観測できない項目をFAILや0点へ変換しない。
- 送信待ちの原本は元request IDと本文を保ち、再開後に同じ原本を再送する。
- 成績には受信日時、現在の確認日時、参照している提出日時を分けて表示する。
- 署名期限切れは構築/実行用の更新案内とし、保存済み成績を消したり閲覧不能にしたりする理由にはしない。
- P3/M3の停止は専用の明示操作。ポータルの稼働を理由に通常授業のEC2を起動し続けない。

## 比較した方式

| 方式 | 初期準備 | 日常の操作 | 判断 |
| --- | --- | --- | --- |
| 教師ポータルが学生AWSを直接操作 | 学生roleへのcross-account信頼と許可が必要 | 一画面にできる | LabRoleの信頼変更が可能と未確認。最初の前提にしない |
| 教師ポータル＋学生側操作窓口 | 本人AWSで初回導入とaccount登録 | 状態/構築/採点をブラウザへ集約できる | 推奨。初回導入・認証・必要APIの実証を先行 |
| ポータルからCloudFormation画面へ案内 | 導入が比較的少ない | 構築支援はできるが、全工程と採点は別の接続が必要 | 段階的導入の入口として利用 |

## 実証の順番と合格条件

1. **成績の閲覧**：教師/学生のEC2を使わない経路で、保存済み本人結果と教師一覧を読む。実データを変更せず、既存62素点・日時・UNKNOWN/参照値と一致する。Lab終了後にも必要API/DBへ届くことは、この段階で別に確認する。
2. **学生窓口の導入と本人確認**：別学生accountへブラウザから導入し、AWSで検証された本人accountと匿名Lab IDを結び付ける。別学生・別Stackへの操作が拒否される。必要なLabRole権限を実測する。
3. **状態だけの読取り**：5台の状態、SSM、現在IP、署名期限を表示する。stopped/接続不能/状態不明で採点や自動Startが起こらない。
4. **初回環境の準備**：専用の新規試験Labで、署名取得から初期化・内部SSH・個別登録・通信閉鎖までをブラウザの導線で完了する。再押下/途中切断で資源や認証を重複作成しない。
5. **通常checkerと提出**：固定課題IDだけを受け付け、SSMの正規観測から教師保存まで確認する。自己申告点、他学生のreport、重複加点を拒否する。教師の中継EC2が使えない場合も、新経路の送信結果を別に受入する。
6. **対話確認と停止/再開**：passwordを残さずM5/M6機能を確認し、P3/M3と全5台の停止/再開、操作途中の停止、期限切れを試す。共有Windowsでの交代時に前の学生のsessionを使えないことも確認する。

初回に完了したのは公式仕様と既存ソースを使った構成検討。最初に1〜3を通し、成立した方式で4〜6へ進む。学生向けの通常導線からコマンド/URL転記がなくなることを、最終受入条件として維持する。

2026-10-29更新：教師LabRoleから別学生5台への読取り、全6台のEC2停止中の保存成績62/62と元データ不変を実測。学生End Lab後も、教師Lab開始中なら保存成績は読めたが、学生Lambdaの構成読取り/起動段階はAccessDenied/KMSAccessDeniedExceptionで取得不能となった。承認後に閉鎖Web Functionsと専用S3を配備し、教師EC2停止・教師Lab開始・学生Lab終了の条件で、実HTTPの3項目trueを確認。その後、教師End LabのUI Terminatedを確認して取り直すと、health 200のまま、可否probeは503/3項目falseとなった。30秒cacheを超えて05:43:03 UTCまで再現。**このLab内構成で教師End Lab後の保存成績閲覧は不合格**。データ消失や正確なAWSエラーコードは未確認で、0点化・制限解除・Lab自動再開はしていない。個人成績は503で閉鎖中。教師側の永続保存・成績処理・本人認証をLab終了に依存しない運用先へ分離する案について、通常AWS accountの有無を本人へ確認中。新規契約やデータ移行は未実施。Google本人確認とブラウザ経由の本人bindingも未受入。[最新の試作・実測と残件](../web_portal_poc/README.md)を優先する。
