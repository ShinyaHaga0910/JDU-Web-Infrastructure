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
- 同builderの現在の候補は学生側12資源（初回準備/status/checkerの3 Lambda、2 DDB、3ログ、本人確認処理、教師LabRole限定invoke許可3）を生成する。既存LabRoleを利用し、EC2/IAM role/公開URLをこのhelper自体へ追加しない。EC2の5台作成は後続の本人POSTで行う。下の5資源のAWS構文検査は旧候補の履歴。現在の12資源も後段の構文検査を実施したが、両方とも実配備の証拠ではない。

ローカルPython62件、Web Node65件、Web package試験を確認。Chromeで架空データの構成/非表示入力/POST後の進捗とJA/RU/UZを確認した。実Google/実STS→新5台→初期状態の通し受入ではない。

AWS965のCloudShellでsyntax-only template（SHA256 `f7f0f9e8af66d5e414e45a78024ac4ef70ab9b9c16d148a116bf0a7113af3692`）をValidateTemplateへ渡し受理。これは3parameter/5資源の構造検査のみ。参照codeは架空・未搬入で、S3実取得・Lambda実行・role間通信・resource作成の証拠ではない。

## 作成後の基盤確認・内部SSH（追加実装、AWS未適用）

`initial_setup.py`をworker/private service/学生画面へ接続した。明示した「基盤準備を続ける」POSTで、初期状態の確認→取込み用S3通信の閉鎖→内部4台のホスト鍵確認→踏み台内の鍵準備→内部SSH設定→一時鍵の期限後の独立確認を進める。GETは状態表示だけで、SSM実行・鍵準備・変更適用を行わない。内部SSH後は`REGISTRATION_PENDING`へ進み、下記の採点登録を行う。教材配置/checker接続が残るため`lab_ready=false`を維持する。

- 元のcollector、2資源だけの閉鎖validator、同じinstance/root/SGの照合、内部SSH guest/command処理を再利用する。閉鎖では`BootstrapSg`と`S3Endpoint`の非置換変更だけを許し、他のparameterはUsePreviousValueで保持する。RDP hashを再取得・保存しない。
- `initial_ssm.py`は変更するSSM要求の意図とdigestを先に保存し、AWSが返した同じcommand IDを再利用する。応答不明時はcomment/送信先/document/全parameterの一致で受付済み要求を探す。見つからないだけで再送しない。参照：[ListCommands](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_ListCommands.html)、[CommandFilter](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_CommandFilter.html)。
- Lambdaの残り時間が少ない場合は同じ段階で保留する。強制終了等で処理中の記録が残った場合は観測・教師確認が必要と表示し、別の初期化を自動開始しない。
- collectorのソースに任意のSDK clientsを受ける入口を追加した。CLIの既定動作は維持する。既存署名archiveは変更せず、新署名controllerにこの契約を含める必要がある。builderは契約のない古いarchiveを拒否する。
- Web/private serviceの呼出し待ち時間も候補コード側で調整したが、配備templateはまだ更新していない。現在の稼働15/45秒のまま新処理を有効化しない。

新規13件＋本人限定advance1件＋旧controller拒否1件を含む関連Python77件、既存collector/closure/全台SSM21件、Web Node67件、Web package3件がローカルで合格（skipなし）。Motoと模擬AWSを使い、実SSHや実鍵発行ではない。Chromeの架空画面でJA/RU/UZとPOST→同じGET・採点登録未完の表示を確認。証拠は[作成後処理の検査記録](verification/2026-10-30-initial-setup.public.json)。

## 採点登録・本人連携の接続（追加実装、AWS未適用）

`initial_registration.py`と`initial_registration_guest.py`を、本人用の登録POSTへ接続した。初期5台/内部SSHの確認後だけ、踏み台の一回用受取鍵を既存guestで準備し、Webのserver内で生成した256bitのLab tokenをその公開鍵へ暗号化して渡す。画面・form・SSM履歴・DDBへ平文tokenを置かない。共有Windowsへ鍵や認証ファイルを保存する作業もない。

- `web/initial-delivery.mjs`はNode標準のRSA3072/OAEP-SHA256を使う。用途/Lab/release/deployment/踏み台ID/tokenを含む短いJSON配列を1blockへ暗号化し、受取側は同じcontextを照合して元のcredential検査/保存/登録処理を使う。独自の暗号・padding・ASN.1実装は作らない。[Node publicEncrypt](https://nodejs.org/api/crypto.html#cryptopublicencryptkey-buffer)、[OpenSSL pkeyutl](https://docs.openssl.org/3.0/man1/openssl-pkeyutl/)。
- 元guestへ`register_oaep`を追加した。従来の認証済みAES-GCM/CMS経路とCBC拒否を維持する。新しい関数を含まない旧controllerはbuilderが拒否し、署名済み旧archiveを編集して利用しない。
- 発行時にはtoken hashと暗号文/元5台の対応を、成績METAの新規作成と同じtransactionで保持する。送信が中断しても元の暗号文を使い、別tokenで上書きしない。既存META/本人bindingがあるLabを取り込まない。
- 踏み台からの登録応答と受取秘密鍵の廃棄を確認後、前段の学校Google/本人AWS確認に対応する本人だけへ、元readerと同じschemaの閲覧bindingを一括作成する。失効session・異なるMETA/release・競合bindingでは全bindingをrollbackし、無関係な成績は不変。新規Labに点数を創作しない。
- 受付済みSSMは同command IDで回収し、登録後の再送は保存済みreceiptを読む。登録後は`TEACHING_ASSETS_PENDING`と表示し、教材配置/checker接続の完成に置き換えない。新しいstatus/checker関数の配備もこれから必要。

関連Python90件（新規13件）、private serviceのpackage/更新計画7件、Node71件（新規4件）、Web package3件が合格、skipなし。Node→OpenSSLの実暗号化/復号と改変・異なるcontext・旧CMS/CBC拒否をローカルで検査。Motoの実transactionと模擬SSM/EC2/CFN/STSを使い、実AWSのcredential発行や登録ではない。Chromeの架空JA/RU/UZで登録POST→同じGET/教材準備待ちを確認した。[採点登録候補の検査記録](verification/2026-10-30-initial-registration.public.json)。

## 公開教材の配置・status/checker接続（追加実装、AWS未適用）

有効な署名済みcourse kitと同じcoreを照合し、固定62点のassessmentと教員提供アプリ、公開教材5ファイルをworkerへ収録する。CLIはcoreとcourse両方の実署名検査を先に実行する。単体試験のcourse envelopeは架空データで、新しい正規署名配布を作成した証拠ではない。

採点登録後の明示POSTで、同じWeb/DBだけへ公開教材を配置する。既存の異なる内容を上書きせず、途中で止まった場合は同じSSM要求を回収する。サービス導入・設定・DB・パスワード変更は行わない。配置先は`/var/lib/jdu-web/lesson-resources-r1`。学生手順との最終的な配置先の統合は新署名配布で確認する。

同じjournalの元5台と登録receiptだけからstatus/checker用のcontextを構成し、既存の状態observerとStudentCheckerを呼ぶ。公開教材2台の配置、3関数の固定設定・同一コード、実status応答の5 IDとchecker設定healthが揃った時だけ初回基盤readyを保存する。healthは実課題の実行成功を意味しない。GETは配置・課題実行・EC2起動をしない。3言語画面は準備後の状態/課題/成績リンクを持つ。

関連Python97件、Node73件が合格（skipなし、前回実行済み）。Moto/模擬AWSを使う接続検査と、WSL Ubuntuでのroot所有権・mode・symlink・途中配置再開の実filesystem検査4件を区別する。AWS上のLinux/SSM/実課題実行は未試験。新ready画面も架空データのChromeでJA/RU/UZを確認済み。証拠：[教材接続候補](verification/2026-10-30-initial-teaching.public.json)。

## R1内でまだ必要な接続

- 教師の正式な事前割当・有効な新署名配布/worker artifact publicationと学生画面を接続する。
- 既存Web/private servicesへの初回準備用の設定追加・timeout調整を含む更新計画を作る。現行のcode-only更新toolはtemplate変更を拒否するため、そのまま適用しない。新しいhelper/入口をAWSへ配備し、実role・crypt・初回操作を確認する。
- 作成後の基盤検査・S3閉鎖・内部SSH・採点登録・公開教材資源配置とstatus/checker接続候補を実機検証する。旧採点APIへの踏み台登録時は教師EC2の稼働が必要。表示で自動起動せず、学生の解答設定も適用しない。
- 有効な新署名版を使った実作成と、未完成の演習開始状態の確認。これはR1の受入、一般学生の通し受入はR6で確認する。

2026-10-30の既存読取りでは学生AWS965244652544の元5台は全てstopped、保存済みroot ID一致、nonterminated=5。新5台で計10台となり旧controllerの保守的9台guardを超える。このguardは停止中も数え、AWS/Vocareumの実quotaの証拠ではない。本人は別の試験環境を用意できず、既存環境の整理・再利用を希望した。まず対象Classの実制限・Lab再開時の全台起動・予算を確認し、削除なしの併設可否を判断する。必要なら対象ID/保持disk/復旧手順の具体案を作る。台数guardを無断変更せず、元5台の削除・置換も未承認。独立した学校Google identityも未確保で、先生を学生役にする試験を独立学生の受入に読み替えない。

その後の実読取りで元5台running/元root一致を確認し、同ClassのREADMEの同時9台/32vCPU・再開時全台起動を確認した。10台保持の併設案は採用しない。旧repo1台を整理する最小案と、既存bindingを保持した試験割当の検討は[既存環境再利用案](INITIAL-REUSE.md)へ記録。現12資源のValidateTemplateも成功したが、参照artifactは架空で新資源は作成していない。

記録はverification/2026-10-30-initial-preparation-core.public.jsonとverification/2026-10-30-initial-preparation-ui-worker.public.json。既存成績の変更、新規AWS資源、権限追加、credential発行は行っていない。

## 新しい署名付き検証候補（2026-10-30、AWS未配備）

正式配布builderは「そのcoreそのものの実機合格」を要求するため、変更したcontrollerへ旧coreの合格証拠を流用しない。`initial_candidate_release.py`で初回検証用の署名envelopeを用意し、worker builderへ明示`--candidate-root`を追加した。通常の`--course-root`は従来どおり正式配布の検査を行う。候補はdistribution_ready=false / class_ready=false / foundation_acceptance_pending=trueとし、署名・期限・core hash・既存62点assessmentの署名と全hashを検査する。

既存のWSL署名鍵は有効で、秘密鍵を持ち出さず新coreと候補を実署名した。期限は2026-11-06T08:52:07.545392+00:00。教師受付HTTPS200、同じ741,180,532 bytesの元payload全GET hash、公式料金CSVの更新を実確認した。コードは現repoから、旧記録rootは読取り専用の参照証拠として使う。旧toolsを編集正本に戻さず、旧署名archiveも変更しない。

実GPGのcore/envelope/assessment検査から67 fileのworker ZIPを組立て、WSL Ubuntu Python3.12.3で実pwd/fcntl・全file照合・合成passwordのcryptを確認。Lambda Python3.11や実AWS作成の成功とは扱わない。関連21件と元endpoint検査5件も合格（skipなし）。[検査記録](verification/2026-10-30-initial-candidate-release.public.json)と[署名候補の保存先](../03_knowledge/aws_official/web_lab_packages_2026-10-15/portal-initial-class193548-20261030-r1/README.md)。

workerの公開コードは既存の非公開・version管理済み配布bucketを再利用できるようにした。`prepare_initial_publication.py`は元policyを保ち、この学生向けの1 objectだけのread追加計画を作る。新bucket/公開URLを増やさず、権限追加の実行は具体計画への直前確認後とする。現段階はAWS未適用。
