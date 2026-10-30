# R1 初回環境準備の実装状況

2026-10-30。全体の終了条件は[PORTAL-ACCEPTANCE.md](PORTAL-ACCEPTANCE.md)のR1〜R6に固定する。この文書はR1の内訳であり、新しい完了項目を追加するものではない。**R1未完了・AWS未適用。**

## 学生が設定する課題を残す

ブラウザで自動準備する対象はVPC/5台/署名済み依存資源のrepo/踏み台GUI/SSM/内部SSH/採点の入口まで。学生がサーバーへ入って、ソフトウェアの導入、設定ファイル・DNS・DB権限・アプリサービスを変更し、構文検査→サービス反映→実通信を確認する課題は代行しない。Pは詳細な練習、Mは異なる条件の自力課題で、確認ボタンは解答設定を自動適用しない。

現行node_bootstrap.pyはWebのnginx、DNSのbind9、DBのpostgresql-16が未導入であることを初期状態として確認する。教材のstage_resources.pyも公開資源の配置だけで、package/service/DB/role/passwordを作らない。現在62点まで構築した検証5台と、新規学生の開始状態を区別し、前者を初期化して試験しない。

## 実装済みの内部処理（AWS未適用）

| 部分 | 動作 | 検証範囲 |
| --- | --- | --- |
| portal_preparation.py | 元成績META/完成済み5台を要求せず、教師の事前割当を作る。学校IDは既存HMACで扱い、同じAWS/Labの重複割当と既存binding上書きを拒否する | Motoの実SDK transaction。実Google/実AWSでは未試験 |
| 同上 begin/complete | 既存Google sessionに対応するnonce付きSTSで、割り当てた学生AWSを確認。期限切れは新しいform、再読込みは同じ有効な操作へ戻す | STS fetchはstub、署名の実認証は未試験 |
| 同上 confirm | 明示POSTでfoundation_onlyの要求を1件だけ保存。GET/再送はEC2作成へ進めない | Motoで重複・失効・既存データとの競合を検査 |
| browser_link_handler.py / template builder | preparation専用のAWS確認用CloudFormationを生成し、短期STS proofを固定HTTPS callbackへ送る。既存環境の登録とは別用途。鍵/パスワードのコピー不要 | SDK signer/HTTP stub/inline import。AWS未適用 |
| 既存Webのcallback | 新しいpreparation callbackだけを明示フラグで開く。既定は閉鎖。既存enrollment登録と受領を混同しない | NodeのAPI試験。新しい/prepare画面も実装・ローカルChromeで確認済み |
| initial_stack.py | 既存controllerの本物の21パラメーター構築とAMI/予算判定を再利用し、割当と署名資材のhash/期限、96GiB/全5台SSMを確認してCreateStackへ渡す。意図を先に保存し、応答不明時や再送では同じStackを観測する | 元selector/template/parameter builder＋Moto journal＋模擬EC2/CFN。実作成なし |

initial_stackは内部classであり、配備済みのLambda handlerではない。GPG署名を検証済みの資材と、本人が確定した割当を実行workerから渡す必要がある。自己申告JSONをverifiedとして受け付ける公開routeは作らない。RDP hashや署名URLを進捗表・ログへ保存しない。

CloudFormationのClientRequestTokenも固定するが、それだけで二重作成防止を主張しない。元要求・Stack名/ID・タグ・templateを照合し、観測不能では保留する。[AWS CreateStackの定義](https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_CreateStack.html)。

## 学生画面と実行workerの接続（追加実装）

- `web/preparation.mjs`と`router.mjs`にJA/RU/UZの初回準備画面を追加。本人AWS確認→構成・種類/96GiB/料金の確認→非表示RDP入力→同じ構築要求の進捗表示を接続。GETは観測のみ、POSTは操作別CSRFを確認し、成功時はGETへ戻す。期限切れ・台数上限・確認不能を完成扱いにしない。
- `initial_plan.py`はAWS CLIを使わずSDKでAMI/公開鍵/提供AZ・T系/価格catalog/S3 prefixを読む。既存selectorの最安同一family選定を再利用する。秘密鍵を取得しない。
- `initial_worker.py`は固定割当のplan/observe/create/advanceを実行し、DDBへ元planと構築意図を保持する。RDP hashはPython3.11のSHA512-cryptで一時生成し、既存の21パラメーターを組む。原文password/hash/署名URLはjournalへ入れない。実AWSでのcrypt動作は未受入。
- `initial_gateway.py`は割当から決まる学生Lambdaだけを呼ぶ。`portal_preparation.py`に本人確認後のplan/createを接続し、statusは同じ要求の観測だけにする。public bodyからAWS/identity/実行先を選ばせない。
- `build_initial_worker.py`のCLIは既存の実GPG verifierを先に通し、署名controllerのbyteを保持したworker ZIPを作る。旧r2失効を回避しない。単体試験のZIPは架空の検証入力であり、新しい署名配布の実制作ではない。
- 同builderは学生側の5資源（Lambda・DDB・ログ・本人確認処理・教師LabRole限定invoke許可）のtemplate候補を生成する。既存LabRoleを利用し、EC2/IAM role/公開URLをこのhelper自体へ追加しない。EC2の5台作成は後続の本人POSTで行う。

ローカルPython62件、Web Node65件、Web package試験を確認。Chromeで架空データの構成/非表示入力/POST後の進捗とJA/RU/UZを確認した。実Google/実STS→新5台→初期状態の通し受入ではない。

AWS965のCloudShellでsyntax-only template（SHA256 `f7f0f9e8af66d5e414e45a78024ac4ef70ab9b9c16d148a116bf0a7113af3692`）をValidateTemplateへ渡し受理。これは3parameter/5資源の構造検査のみ。参照codeは架空・未搬入で、S3実取得・Lambda実行・role間通信・resource作成の証拠ではない。

## 作成後の基盤確認・内部SSH（追加実装、AWS未適用）

`initial_setup.py`をworker/private service/学生画面へ接続した。明示した「基盤準備を続ける」POSTで、初期状態の確認→取込み用S3通信の閉鎖→内部4台のホスト鍵確認→踏み台内の鍵準備→内部SSH設定→一時鍵の期限後の独立確認を進める。GETは状態表示だけで、SSM実行・鍵準備・変更適用を行わない。採点登録は未接続のため、最後は`REGISTRATION_PENDING`/`lab_ready=false`のまま表示する。

- 元のcollector、2資源だけの閉鎖validator、同じinstance/root/SGの照合、内部SSH guest/command処理を再利用する。閉鎖では`BootstrapSg`と`S3Endpoint`の非置換変更だけを許し、他のparameterはUsePreviousValueで保持する。RDP hashを再取得・保存しない。
- `initial_ssm.py`は変更するSSM要求の意図とdigestを先に保存し、AWSが返した同じcommand IDを再利用する。応答不明時はcomment/送信先/document/全parameterの一致で受付済み要求を探す。見つからないだけで再送しない。参照：[ListCommands](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_ListCommands.html)、[CommandFilter](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_CommandFilter.html)。
- Lambdaの残り時間が少ない場合は同じ段階で保留する。強制終了等で処理中の記録が残った場合は観測・教師確認が必要と表示し、別の初期化を自動開始しない。
- collectorのソースに任意のSDK clientsを受ける入口を追加した。CLIの既定動作は維持する。既存署名archiveは変更せず、新署名controllerにこの契約を含める必要がある。builderは契約のない古いarchiveを拒否する。
- Web/private serviceの呼出し待ち時間も候補コード側で調整したが、配備templateはまだ更新していない。現在の稼働15/45秒のまま新処理を有効化しない。

新規13件＋本人限定advance1件＋旧controller拒否1件を含む関連Python77件、既存collector/closure/全台SSM21件、Web Node67件、Web package3件がローカルで合格（skipなし）。Motoと模擬AWSを使い、実SSHや実鍵発行ではない。Chromeの架空画面でJA/RU/UZとPOST→同じGET・採点登録未完の表示を確認。証拠は[作成後処理の検査記録](verification/2026-10-30-initial-setup.public.json)。

## R1内でまだ必要な接続

- 教師の正式な事前割当・有効な新署名配布/worker artifact publicationと学生画面を接続する。
- 既存Web/private servicesへの初回準備用の設定追加・timeout調整を含む更新計画を作る。現行のcode-only更新toolはtemplate変更を拒否するため、そのまま適用しない。新しいhelper/入口をAWSへ配備し、実role・crypt・初回操作を確認する。
- 作成後の基盤検査・S3閉鎖・内部SSHの候補コードを実機検証し、採点登録、公開教材資源配置、元checkまで接続する。学生の解答設定は適用しない。
- 有効な新署名版を使った実作成と、未完成の演習開始状態の確認。これはR1の受入、一般学生の通し受入はR6で確認する。

2026-10-30にEdgeの学生AWS965244652544を確認。既存5台は全てstopped、保存済みroot ID一致、nonterminated=5。新5台で計10台となり旧controllerの保守的9台上限を超える。AWSのサービスquotaと断定せず、元5台削除/上限無断変更で通さない。別の初回配備用環境の確保は実作成前に必要。コード制作は継続できる。

記録はverification/2026-10-30-initial-preparation-core.public.jsonとverification/2026-10-30-initial-preparation-ui-worker.public.json。既存成績の変更、新規AWS資源、権限追加、credential発行は行っていない。
