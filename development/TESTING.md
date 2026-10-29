# 移管ソースの検証

## ローカルの確認

Linux/WSLのPython3とGPGで、repository rootから次を実行する。選択したunit/mock regressionだけを実行し、AWSへの配備・変更は行わない。

```bash
python3 -B development/run_local_checks.py
```

Python構文、instance選択、5台template/SSM/controller、教師受付、暗号化受渡し、62素点/観測、配布/再配布/署名、アプリ設定・bundleを確認する。結果はlocal-checks.public.jsonに保存する。初回移管では184件中181件が合格、root/systemd専用の3件はskipだった。AWS実機試験の結果ではない。

初回移管の全byteを再照合する場合は--verify-importを付ける。IMPORT-MANIFESTは移管時の履歴なので、今後意図してソースを修正した後はその照合と通常の回帰検査を区別する。現行の学生template/教師builder/固定appの照合はverify_source_integrity.pyで行う。

```bash
python3 -B development/run_local_checks.py --verify-import
python3 -B development/verify_source_integrity.py
```

履歴の全scriptが初回cloneだけで実機検証できる、という意味ではない。過去probeの実private plan/state、署名秘密鍵、大容量package cacheはGitHubへ登録しない。実PostgreSQL/Nginx/Gunicornを使うintegration fixtureは、専用の架空環境/収録資源が必要であり、このoffline runnerには含めない。

## 既存のAWS受入と残件

署名済みr2、D08/D11の実機受入と、今回のGitHubへのソース移管の検証を分ける。元の固定62素点とD08/D11の署名物を、ソース保存だけを理由に再発行したりAWSへ適用しない。

新しいD12の公開資源搬入と学生が49手順を最初から辿る試験、母語校閲、教師確認、本人の成功password手入力とapp後の全5台停止/再開は未受入のまま。[教材側の範囲](../course/labs/VALIDATION.md)を参照。全授業CLASS_READYはfalse。

新しいコード変更では、対応するunit/mock regressionに加え、必要な実機受入を明示して行う。旧migration用の同じ実環境を無断で初期化しない。

## Web本人登録のtransaction検査

`development/web_portal_poc`で、隔離したtest用Python環境へ`pip install -r pairing-test-requirements.txt`を実行してから次を使う。Moto/boto3は配備ZIPに収録しない。新登録13件はMoto必須で、skipを合格と数えない。

```bash
python -B -m unittest -v test_portal_enrollment test_portal_enrollment_handler test_prepare_portal_services test_apply_portal_services
```

登録・本人/AWS重複防止・原本条件確認・session失効のtransaction、再送、期限、9項目のrollback、既存62点readerとの接続、公開入口のない配備候補、適用前の差分/版/hash照合を検査する。STS fetchはstubのため実署名の認証結果ではない。Google→本人AWS→実DynamoDB→ブラウザの受入は別に記録する。`web`の`npm test`はCSRF、同一origin、serverで検証したclaimsのみの利用、body上限、既定閉鎖も確認する。

## ブラウザ本人連携候補の検査（2026-10-29）

上記test用依存を設定した`development/web_portal_poc`で次の41件が合格した。登録のpending pointerと完了時の10項目transaction、並行formの収束、原本変更・pointer変更のrollback、学生CloudFormation helperのCreate/Update/Delete、固定した接続先・署名・callback、非公開2関数のCodeだけの更新、readonly受入検査と専用S3の最小配布範囲を含む。Moto/署名stub/架空応答を含み、実本人連携の成功とはしない。

```bash
python -B -m unittest -q test_portal_enrollment test_portal_enrollment_handler test_prepare_portal_services test_apply_portal_services test_browser_link test_browser_link_publication test_update_portal_services test_verify_portal_services
```

`web`の`node --test`は43件合格。固定hashと版付きS3ソースの読取り、5分cache/同時要求/取得失敗、確認formのCSRFと同一origin・server identity、期限切れのAWSリンク拒否、session失効、62素点/UNKNOWNを検査する。SDKはlockfile固定、npm auditは0件。CloudShellのNode20で依存を収録する段階と、AWS Web実行時Node24を区別する。

実AWSでは非公開v1/v2の実作成・Code更新と未登録拒否だけを受入した。公開Webは旧ログイン版、導入S3と新Web change setは未execute。最新の成果物と適用境界は`web_portal_poc/verification/2026-10-29-browser-enrollment-plan.public.json`、実測は同folderのprivate-services-v1/v2記録を参照する。

## 認証済み学生用画面の実機受入（2026-10-29）

Web v4でNode44件。native POSTのno-referrer/Origin:nullを個人情報のないChrome formで再現し、登録成功ページだけsame-originにして厳密Origin/CSRFを維持した。実AWSでは人間が指定した先生Googleを学生役として、学生AWS965の署名、本人登録、JA/RU/UZの62点、5台停止、ログアウト拒否/再ログインを確認した。本人による学生End後、LMSのTerminated/00:00と本人62点の表示、状態取得不能後も62点保持を受入。教師Labは開始、教師EC2停止。10:19:45 UTCの検査で元成績全projection/全Lab partition不変。これを新規5台構築/ブラウザchecker/教師画面や実別identityの負例の受入に広げない。詳細はweb_portal_poc/PORTAL-ACCEPTANCE.mdと最新public JSON。

## 課題確認job基盤の検査（2026-10-29、未配備）

`web_portal_poc`でtest専用Moto/boto3を設定して、`python -B -m unittest -q test_assessment_command_jobs test_assessment_observation`を実行し29件合格。実Dynamo型のnumeric往復、並行worker、応答不明/既存command回収/ページング、停止前提の拒否、元report/request ID、既存HTTP source hash/registry bytes、外部HTTP/管理拒否とUNKNOWNを模擬検査する。SSMとHTTPはfakeであり、実コマンドやネットワークへの接続はない。既存assessmentの`test_assessment`14件も合格。ブラウザ実行/採点提出の実AWS受入とはしない。稼働Webや元署名版をこの検査で更新しない。


## ブラウザ課題確認の接続候補（2026-10-29、AWS未適用）

`test_browser_checks test_assessment_command_jobs test_assessment_observation`の35件、WebのNode48件（新4件）、package/計画5件合格。新結合試験は実job/HTTP adapterをMoto DDBと架空SSMへ接続し、本人承認、元request ID、結果再訪、GET非実行、停止前提拒否、既存成績不変を確認する。Windowsのpackage import試験はLinux標準pwdをダミーmoduleで補い、実Linux CloudShellでも同じZIPをimportして元5台のrunning/SSM Online/保持templateとnetwork baselineを読取り確認した。実SSM checker/実ブラウザ受入とは分ける。今回の完成条件はweb_portal_poc/CHECKS-ACCEPTANCE.md。


## ブラウザ課題確認の実受入（2026-10-29）

追加のmap順序/受付済みcommand再compile不要の回帰を含めPython37件、言語/同job再訪を含めNode49件合格。AWSでは実ブラウザM1 8/8、M2 13/13、M5 9/13＋未確認4、3件各SSM1回、元request/report保持を確認。M2のmap順序不具合は実機で特定し再送せず結果回収。M5の一時読取り失敗も同jobの更新で再表示できた。元5台停止後も保存M2を新GETで表示し、新規M1はjob/0点を作らず拒否。元62点・全partition/projection不変、96GiB/認証保持。全P/Mの新ブラウザ通し試験・原本への自動提出とは分ける。詳細はweb_portal_poc/verification/2026-10-29-browser-checks-accepted.public.json。
