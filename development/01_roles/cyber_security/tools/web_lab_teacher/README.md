# Web実習の教師用採点受付

## 教師のAWS環境を新規構築する

AWS Academyで対象クラスの**教師用Learner Lab**を開始し、米国東部（バージニア北部、`us-east-1`）のCloudShellで実行します。

```bash
work=$(mktemp -d "$HOME/web-teacher-download.XXXXXX")
cd "$work"
url='https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/8b080f940957fe3898e65d5a31978f581aa86dd0/development/01_roles/cyber_security/tools/web_lab_teacher/install_teacher.py'
curl -fSs "$url" -o install_teacher.py && python3 -B install_teacher.py
```

ログイン中のCloudShellからAWSアカウントを取得し、そのアカウントに構築します。Class IDやアカウント番号の入力は不要です。実行前に対象の教師用Learner Labを開いてください。

取得URLは、入力を省いた版のコミットを指定しています。Class IDの入力待ちが表示された場合は `Ctrl+C` で中断し、上のコマンドで取り直します。

スクリプトは、教師専用のVPC、EC2 1台と固定IPv4、採点API、採点結果用DynamoDB、非公開の教材用S3をCloudFormationで作成します。対応するAZ、CanonicalのUbuntu AMI、LabRole、EC2台数、テンプレートを作成前に確認します。構築後は固定IPv4経由のHTTPS、認証なしの教師画面へのアクセス拒否、DynamoDB、S3の公開ブロックと暗号化を確認します。教師用設定は表示された専用ディレクトリ内に保存されます。

`--plan` を付けるとAWSの前提とテンプレートのみを確認できます。構築が中断した場合はCloudFormationのイベントを確認してください。構築待ちやHTTPS検査の再開には、同じAWSアカウントと同じ `--name` で再実行します。標準のスタック名は `jdu-web-teacher-walkthrough` です。同じAWSアカウントで別の新規環境を作る場合は `--name trial2` のように名前を変えます。旧版で作成したスタックを再確認する場合は、スタック名から `jdu-web-teacher-` を除いた文字列を `--name` に指定します。

ここまでで終わるのは教師側のAWS基盤構築です。学生に演習を配布する前に、教材を登録し、新しい採点先に対応する署名済み配布版を作成します。学校Googleログイン付きのブラウザ課題画面も別途配備・確認が必要です。[初回授業の配布・生徒側の手順](../../../../../course/labs/INITIAL-WORKFLOW.md)

10/22正式配布追記：D08初期環境版r3を教師private S3へ保存/全GET一致、教師/学生実CloudShellで署名・全file検証を完了。新学生への発行と同じ学生への再配布は[共通正式配布の教師手順](../web_lab_distribution/TEACHER.md)を使用する。既存Labはreuseで元credentialを保持し、新規発行し直さない。Class193548固定helperは旧検証専用として残す。distribution_ready=true、CLASS_READY=false、期限10/27 14:24:57 UZT。以下の昇格未完表記は追記前の履歴。

10/22確定：**Class193548の教師AWS170126527713と学生AWS965244652544を分けた候補受入が合格**。学生の新規5台・S3閉鎖・恒久SSM/内部SSH・個別登録・停止再開保持・本人GUI・実WEB-02の9段階13提出を確認した。教師側で全17提出の本文/受領/hash/最新進捗/実5台登録を独立照合し一致。教師/学生JA/UZ/RUの実HTTP全6ページ、no-store/30秒更新も合格。現在は基盤47/47、P1/M1各2/10、完了0/2（学生の作業開始状態）。科目の素点ではない。正式配布への昇格・全課題/配点の確定は別で、CLASS_READY=falseを維持する。最新の証跡・再開手順は[検証状況](../../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)最上部。

## Class193548の教師が進捗を見る

教師teacher@example.invalidのLabからAWSを開き、account170126527713の個人CloudShellで実行する。

```bash
jdu-web-dashboard
```

実際の署名v7内の進捗clientに結び付けたcommandを設置済み。教師専用の時限閲覧URLを発行し、日本語・ウズベク語・ロシア語で学生Labごとの最新結果・未提出/途中/完了を確認できる。基盤は課題完了数へ加算せず、過去の最高値より最新の提出を表示する。管理keyは教師CloudShellだけ、学生へ渡すのは各Lab専用のtokenだけとする。閲覧URLをfileへ残す場合はCloudShell内の新しいprivate pathへ`--save-session`で保存でき、Windowsや教材へコピーしない。

教師の採点受付Stackはjdu-web-progress-2026、APIはhttps://7ilp8ph6ki.execute-api.us-east-1.amazonaws.com、固定IP50.16.41.7。授業開始前に教師側Lab/受付を稼働させてから学生へ案内する。教師と学生をChromeのaccount別URLで同時に扱い、単にタブ名やStudent Viewの表示だけで役割を決めない。

現在のclass193548-test1は既存tokenで登録/verify済み。`issue`やenroll applyを繰り返さない。新しい学生へ配るときは別のLab ID・正しい学生account・その学生の公開recipientを確認して個別発行する。今回のClass193548固定helperは検証用で、既存学生のprivate設定を別学生へ複写する手順ではない。期限切れの教材URL更新は既存tokenの再発行と分ける。

## 以下は制作・受入の履歴

10/20最終：テスト２の新Lab teacher-c4-probe・署名tools **c5-v6**で内部SSH/採点登録の本人apply、実WEB-02の9段階13 assessment、最終停止再開後の基盤47/47・登録verify・教師保存本文/hash/receipt/LATEST/同一再送が合格。教師/本人のJA/UZ/RU実HTTP全6ページも47/47・P1/M1各2/10・完了0/2と一致。学生作業開始状態へ復元済み。現在RDP18.207.104.230、Web44.200.206.66。新認証情報の再発行/本人applyは不要。別学生Lab [193548]からの取得・新規配備・登録・送信を確認するまでは正式配布/D08/CLASS_READYを保留する。 最新状態・証跡・再開手順は[検証状況](../../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)冒頭。以下の10/16以前の入力待ち/未実装記載は履歴であり、最上段を優先。

10/16 18:09 UZT：本人指示で一時中断。署名v4の新5台（teacher-c4-probe）はStack CREATE_COMPLETE/全running、bootstrap段階。新環境の閉鎖/内部SSH鍵/採点登録/GUI受入は未実施。下記の旧teacher-five-probeの登録・47/47を新5台の受入として使わない。入力待ちはなく、再開手順はverification_status.md冒頭。

10/16最新：実5台の採点登録・既存tokenでのverify・踏み台から47項目の送信/教師保存一致/同一再送が完了。本人apply待ちは解消済み。新token発行・鍵生成・5台停止再開を重ねない。秘密の保存先は下記のまま。

本人の指定により、現行[OS-Linux-Controlの教師機能](C:/Users/user/Documents/JDU-public/OS-Linux-Control/2026/lab/teacher/README.md)、`scripts/jdu-progress`、`teacher/scripts/jdu-dashboard`、`teacher/lambda/progress_app.py`を参照した。読取り時HEADは`8dabb06b40d199dcdbcc0fa5ff84ce1d085b52fd`。Web側も、確認後の自動送信・途中結果・課題別の最新状態・未提出/途中/全件完了・教師と本人の画面・日本語/ウズベク語/ロシア語・30秒更新を用意する。OS/Linuxのsource・AWS資源・認証情報は変更していない。

Web教師StackはCode＋認証付き自己メールrouteだけの更新でUPDATE_COMPLETE。元のAPI/Table/EC2/EIP・全parameter・鍵・登録・提出を保持した。新しいLATEST#BOOTSTRAP/Pn/Mnを独立して保存し、後のFAIL/UNKNOWNを反映、古いrequestの再送で最新状態を戻さない。既存のlast_resultだけの記録も表示を維持する。実API8群が合格し、テスト２用短commandの配置・fresh47/47と自動送信も成功。詳細と最新receiptは[検証状況](../../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)を優先する。


## 別学生Class 193548の調査入口

10/20続報：教師AWS170126527713と学生AWS965244652544を読取り照合済み。本人が教師配備を実行し、`jdu-web-progress-2026`はCREATE_COMPLETE、API/固定HTTPS/非公開S3/認証拒否/教師JA・UZ・RU画面が合格。教師adminは教師CloudShellだけに保持。学生5台と学生専用tokenはまだ作成していない。実宛先と公開証跡は[検証状況](../../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)冒頭を参照する。

`transfer_class_payload.py`は、既存テスト２で受入済みの741180532 bytesの教材を新教師private S3へ完全一致で移す専用tool。新教師でreceiver-prepare、取得元でsender-export、新教師でreceive-copyの順に使う。STSと宛先を固定し、短期URLは公開cert宛ての暗号文だけを転送、受信側で全署名tree/完全hash/S3 GETを検査する。既存受信workspace/objectは保持し、再作成・上書きしない。5境界試験合格。移送とClass193548 v7の署名制作・新private S3配置は完了し、旧c5-v6は変更していない。

`class_student_delivery.py`はClass193548の教師170126527713→学生965244652544だけの検証用配布補助。学生CloudShellで`recipient`を準備し、公開requestと独立に照合したcert SHAだけを教師へ渡す。教師は新しい署名toolsと新private S3 objectを検査する`plan`を先に実施し、本人が`issue --confirmed-access`を実行する。学生本人が`receive --confirmed-access`を実行すると、個人CloudShellの新しいprivate directoryへ本人Lab credentialと短期GET URLだけを保存する。教師adminは含めない。controller署名/全file hash・受信者・Class/account・1時間期限・正確なS3 objectを固定し、再受信で既存credentialを上書きしない。模擬Lab tokenによるLinux /tmpでの実CMS暗号化/復号・mode0600・再送保持を含む9試験合格。実アカウントでの本人issueは下記続報で完了し、学生側receiveは本人操作待ち。既存テスト２へ適用しない。

10/20続報：本人が教師側issueを実行し、class193548-test1専用認証の発行と暗号文を実確認。既存issued workspaceを保持して再発行しない。`start_class193548_student.sh`は今回の実manifest/deployment/cipherに限定した検証用の薄い実行手順で、reviewは受信・作成なし、applyは本人のTTYと--confirmed-accessが必須。既存署名helperのreceive→createを続けて呼び、RDP passwordは本人がhidden入力する。学生CloudShellでreview exit0、bash構文/非TTY apply拒否を合格。現在は本人が学生側の入力行を実行する待ち。部分受信やCreateStack不明結果があれば全体を再実行せず、既存received/stateを調べて再開する。

10/22再開：上記の古いtransport/planは期限切れ。`refresh_class_delivery.py`は既存発行credentialと教師DDB METAの一致・active、元発行暗号文の独立SHA、署名v7・同じ学生recipientとprivate payloadを確認し、同じLab tokenと新1h URLだけを新しい暗号文へ再包装する。issue/rotate/registerや権限追加は呼ばない。元credentialの不変と実CMS復号を含む8試験＋既存receive9試験合格。実AWSでのrefreshと新planも合格し、暗号文だけを学生へ搬入済み。`start_class193548_student_20261022.sh`が新plan/recipient/cipher/期限を固定した本人用runnerで、旧10/20 runnerは使用しない。実学生CloudShellでread-only review・構文・非TTY apply拒否を合格。受信済みの場合はreceiveを重ねず、新URLだけの受渡しを別に確認する。新recipient/request・planと実行待ち状態は検証状況の最上部を優先する。

10/22続報：本人のRDP入力後、新学生5台のcold CreateStack・初期化・S3閉鎖が合格。全5台のfresh/対話ssm-userと本人RDP/Firefoxも確認。`enroll_class193548_student.py`はこの新deploymentと実5 ID/元rootだけに固定した本人用SSH/登録runner。新tokenを発行せず、受信済みの本人tokenで登録・verify・署名command設置・fresh基盤送信を続ける。reviewは鍵生成/登録なし、applyは本人のTTY必須。異なるaccount/Lab/manifest/deployment/ID/rootを拒否する2境界試験合格。実学生の署名ssh-plan/register-plan・read-only reviewは合格し、現在は左側の第1端末で本人Enter待ち。最新手順は検証状況の最上部。

`cross_account_storage.py`はこのClassの教師・学生が別accountであるための受入補助。`student-export --command-state ... --output NEW.json`は署名commandの匿名reportとreceiptからhashと検査項目だけを出す。`teacher-verify --expectations NEW.json --output VERIFIED.json`は教師の既存IAM読取りでDDBの本文/receipt/hash/最新課題と登録5台を独立照合する。admin key/token/閲覧URLを読み取らず、学生へ教師DDB権限を付けない。改変本文・受領・最新・登録・別deployment・未検証再送・重複・DDB Decimal正規化を含む5試験合格。実AWS照合は新学生の送信後。

10/20続報：大容量payloadの新教師S3への移送・全1155file/完全GET検証は完了。新署名tools Class193548 v7も制作し、private S3 `student-tools/class193548-v7/` のarchive/署名/公開鍵3objectを全GET照合済み。`class_signed_tools.py export/fetch`は同じ学生recipient宛てにpublic softwareの短期URLだけを暗号化し、学生側で独立に固定したarchive/manifest SHA、raw署名を展開前に確認、outer/全controllerを検証する。Lab認証発行は行わない。6境界試験と実v7のlocal transport smokeに加え、**実学生965からのS3取得/展開前raw署名/outer全件/controller検証も合格**。両accountの補助toolは `~/jdu-web-class193548/cross-account-delivery-v1/` が現行で、上位folderの古い準備版は使わない。学生965のCloudShellの `student-delivery-v7/` recipientと `student-software-v7/` を保持し再生成・再fetchしない。AWS複数セッションは本人承認で有効化し両accountの共存を確認。学生read-only配備planも合格。**現在は教師CloudShellのissue入力行で本人Enter待ち。** 個別認証/新規配備はまだで、詳しいworkspace/期限/タブは検証状況の冒頭を優先する。

本人指定は同じClassの教師teacher@example.invalid、学生student@example.invalid。両者の実AWS accountをSTSで区別する。まず `review_class_environment.py` を本人CloudShellで使い、既存EC2/root・Web Stack・公式AMI・LabRole/profile・public subnetを読取り確認する。`--class-id 193548 --role teacher|student --exclude-account 144753397193 --output NEW-REPORT.json` を明示し、既存テスト２への誤適用はSTS直後に拒否する。Class/役割は操作者のラベルで、AWSがAcademy emailを保証したという意味ではない。

この調査toolは保存済みkey/tokenを読まず、資源や認証情報を作らない。模擬SDKによる誤account早期停止・期待account不一致・private subnet誤選択防止・未配備時の無変更を4試験で確認。別accountの実検査はLab表示/認証を確認後。**旧deploy_teacher.pyのstatusは初回key/stateを作り得るため、初回調査に使わない。** 旧VPC/subnet既定値を新accountへ転用しない。教師配備の具体案とcredential生成の本人操作は対象環境確認後に整える。

## 学生向け署名候補c4と実HTTP checker

本人の10/16指示を受け、現行Web教材のWEB-02に対応する最初のP/M一組を候補として制作・受入した。`STUDENT-CHECKER.md`とbundle内`fixtures/`が問題と配布資源、`http_task.py`が教員側の固定期待値。P1は`/practice.txt`、M1は別本文の`/mission.txt`を、root所有/0644の`/var/www/html/`配下から返す。HTML制作は学生へ課さない。正式な科目全体の課題番号や点数はこの候補から自動確定しない。

10項目はidentity、Nginx active/config/listen80、配布file、local/踏み台/公開HTTP、今回のnonce付きaccess log、現在のrepo到達。HTTPはstatus200・本文の完全一致で、redirectを合格にしない。観測不能はUNKNOWN。P完成だけでMを通さず、前提は毎回観測する。この構成のWeb HTTP80は公開契約なので、任意外部のHTTP拒否条件を加えない。

- 実9段階/13提出で、正常10/10、初期未完了・練習のみ・誤本文・localhost限定・前提停止を区別し、全件の教師保存本文/最新状態/同一再送を受入。
- 署名checker v2は19公開file/32,926 bytes、SHA256 `96920a579d47331f2d61970298c16e4ca807ddd006546f33a190fa9b4bdb21b8`。改ざんと違う信頼fingerprintは展開前拒否。v1で実試験した18fileはv2とbyte一致し、v2で追加したbindingと短commandからもP1/M1各10/10を実確認した。
- `build_checker_bundle.py`は明示した公開fileだけを決定的なtar.gzへまとめる。`install_checker_bundle.py`は独立に信頼したfingerprintで署名・安全なpath・完全一覧/hashを確認してから新しい空の場所へ展開する。`--allow-candidate`必須で、正式学生配布を装わない。
- `bind_checker_commands.py`は署名検証後のdirectoryを既存個人CloudShell設定へ結び付ける。認証情報は読まず/作らず/コピーせず、旧設定・旧launcherを保持する。テスト２は `~/.local/share/jdu-web/candidate-c4/checker`、`~/.jdu-web-student/signed-c4-command-state.json`、旧launcher `.before-signed-web02`。再bindしない。
- payload c4は1128 DEB/7 wheel/app33file/checker19file/installerを収録して署名・完全検証済み。稼働c3を変えず、非公開S3別prefixへ候補保存。`scope=student_payload`は収録範囲であり、student_release_ready/class_ready=false。新規配備wrapper/fresh受入はまだ。
- 試験後はWebのnginx/nginx-commonを元package一覧へ復元。現在のP1/M1各2/10は初期状態へ戻した観測で、教師画面にも正しく反映。復元後に署名commandでfresh基盤47/47・教師/本人の実HTTP画面一致。試験用設定/logはWeb内に退避保持。
- 実Webの独立workspaceで、署名appと固定7 wheelのオフライン導入/pip check/版一致も合格。授業用appサービス・DB・新認証は設定していない。

証跡: `03_knowledge/aws_official/web_lab_packages_2026-10-15/candidate-c4/`。新しいAWS資源の作成や認証設定のapplyを重ねず、最新の検証状況から学生の新規配備入口へ進める。関連local52試験と実AWS受入の範囲を分けて記録している。

## テスト２で現在使えるコマンド

現在のテスト２の個人CloudShellでは `~/.local/share/jdu-web/c5-v6-bin` をPATH先頭へ追加済みで、署名c5-v6のbootstrap/P1/M1 dispatcherを使用する。4つの学生commandの解決先・本人Lab一致・実import後の厳密な再検証を確認済み。元bashrcは `~/.bashrc.before-jdu-web-c5-v6-20261020`、旧launcher/config/pendingも保持。古い終了済み5台へのcommandを再bindしない。既存OS/Linuxのcommand名は変更しない。教師dashboardは同じWeb専用APIを使用。正式学生配布・別accountでの新規受入は残件。

| コマンド | 動作 |
| --- | --- |
| `jdu-web-check bootstrap` | CloudShell→SSM→踏み台→4台SSHのfresh基盤確認、ローカル結果を保存し、踏み台から自動送信 |
| `jdu-web-check P1` / `jdu-web-check M1` | WEB-02候補の練習/自力課題を別file・URL・本文で10項目検査し、自動送信 |
| `jdu-web-check bootstrap --no-submit` | 基盤確認と保存だけ。送信しない |
| `jdu-web-check bootstrap --retry UUID` | 元の本文/UUIDを保持した再送。再観測して古い本文を変えない |
| `jdu-web-progress id` | 自分のLab IDを表示 |
| `jdu-web-register` | 同じ実5台/Deployment/既存tokenで登録を再確認。再構築や鍵交換は行わない |
| `jdu-web-dashboard` | 教師管理keyで30分の教師用閲覧URLを発行 |
| `jdu-web-my-progress` | 自分のtokenで15分の本人用閲覧URLを発行 |
| `jdu-web-progress link-email` | 本人がJDU Classroomメールを入力し、表示を確認してYesの後だけWeb教師へ紐付ける |

通信失敗でlocal判定/終了codeは変えず、SUBMISSION PENDINGと再送方法を表示する。UNKNOWNや停止した比較先をPASSにしない。基盤47項目の成功を課題の点数・CLASS_READYへ加算しない。**WEB-02の候補P1/M1は実Webを観測するcheckerへ統合済み。正式な全課題ID/課題数/配点と他単元のcheckerはD11の未確定事項。以前のAPIだけのP1/M1 fixtureと、今回の実HTTP観測を区別する。**

`--save-session PRIVATE_FILE`はURLを画面へ出さずroot/本人0600で保存する検証用option。実閲覧URLは会話・教材・Git・証跡へ出さない。shared Windowsへ秘密鍵や恒久tokenを保存しない。

## 学生の識別と閲覧範囲

JDUメールは、教師がClassroom履修者とLab IDを照合するためにのみ使う。学生本人の対話入力とYes確認の後、認証したWeb教師APIからDynamoDBの本人METAへ保存し、認証済み教師ページと本人ページにだけ表示する。氏名やメールをCloudFormation/EC2/UserDataへ渡さず、登録APIはemail_linkedのbooleanだけを返す。不要になった記録は大学の保管方針に従って処理する。メール所有者確認/Google認証は行わず、形成的な進捗確認として扱う。学生の実メールはまだ収集していない。live試験の`fixture.api-smoke@jdu.uz`は架空のfixture値である。

教師ページは全Lab、本人ページは本人Labだけ。メール/Lab ID、基盤、課題別進捗、完了/提出済み数、最終受信UTCを表示し、課題の総数が未定義の間は未提出課題を含む「全課題完了」と表示しない。host名/EC2 ID・秘密値は表示しない。未達/確認不能の項目はdetailsで開ける。Uz/露は翻訳初稿で、機能試験と母語話者校閲は区別する。

## 登録時の秘密の受け渡し

`enroll_five_node_progress.py`と`progress_enrollment_guest.py`は、個人CloudShell→本人踏み台のSSM経由の認証設定を行う。prepareは本人5台/実root/Stackを照合し、踏み台内にこのDeploymentだけの復号鍵を準備して公開証明書を取得、実OpenSSL AES-GCM/RSA-OAEPの公開fixture往復を確認する。平文tokenをSSM parameters/historyや画面へ出さず、teacher管理keyはCloudShellから出さない。[OpenSSL CMS仕様](https://docs.openssl.org/3.0/man1/openssl-cms/)

本人実行のapplyがLab専用tokenを本人CloudShell privateへ発行し、暗号文だけを踏み台へ送り、root:root/0600で保存して実5台をregisterする。成功後は一時復号鍵を終了する。verifyは既存設定で同じ登録を再確認する。実5台はapply/verifyとも完了済み。D08/学生release/CLASS_READYは別の残件があるため未完了。

学生が5台を構築する前に、教師が別Stackを立て、学生ごとの匿名Lab IDと専用tokenを発行する。既存OS/Linux用のStack、関数、表、教材は変更しない。

## 2026-10-15の実配備

- 対象: テスト２、us-east-1。Stack `jdu-web-progress-2026` は初回CREATE_COMPLETE、10/16の進捗追跡更新後UPDATE_COMPLETE。
- API: `https://7eg7nm5oe2.execute-api.us-east-1.amazonaws.com`
- 学生の固定送信先: `44.216.176.215/32:443`。
- 教師EC2: `i-0040d8f349c83f2dd`。t3a.small、暗号化gp3 16 GiB。EIPと稼働EC2には継続費用がある。
- このAcademy環境での検証用配備。授業本番の教師用AWS環境で常設できること、Lab終了後の継続利用、別学生accountからの接続は未確認。
- 実APIの10ケースと教師・学生の画面応答を確認した。使用した5個のInstance IDは架空のAPI試験値。学生用5台の受入・D08完了・授業開始可能とはしない。

記録: `03_knowledge/aws_official/web_lab_teacher_2026-10-15/api-live-acceptance.json`。

## 独自ドメインを使わないHTTPS

ユーザーに独自domainがないため、API Gatewayが発行するHTTPS名を使う。教師EC2のNginx streamは、そのAPI名のSNIだけを許可し、TLSを終端せず、同じ固定上流へ中継する。任意の転送先を指定する機能はない。

学生の送信clientは接続先IPv4だけをEIPへ固定し、TLSのserver_hostnameとHTTP HostにはAWSのAPI名を使う。通常のCA・hostname検証を維持する。自己署名証明書や検証無効化、学生OSの通常DNS設定変更は不要。

教師の管理操作と画面閲覧は通常のAWS名へ接続できる。学生のBIND完成前でも、採点送信だけが固定IP経由で成立する。DNS課題の合格を意味しない。

## 教師が授業前に行う操作

Chromeのテスト２CloudShellで実行する。管理key、Lab token、session URLは画面共有・教材・Git・配布archiveへ入れない。実ファイルはCloudShellの `~/.jdu-web-teacher/`（private）にある。

```bash
# 新しい教師環境だけ: 必要な4ファイルをCloudShellへ搬入した後に実行
python3 build_template.py
python3 deploy_teacher.py create --vpc-id "$TEACHER_VPC" --subnet-id "$TEACHER_PUBLIC_SUBNET"
# 作成完了後に実出力を確認し、privateに接続設定を保存
python3 deploy_teacher.py status

# 配備済み教師環境: 学生ごとに異なる匿名IDと専用ファイルを発行
python3 web_progress.py --config ~/.jdu-web-teacher/teacher.credentials.json \
  issue --lab-id web-student-001 \
  --output ~/.jdu-web-teacher/private/web-student-001.credentials.json

# 教師画面を短時間だけ開くためのURLをprivateファイルへ保存
python3 web_progress.py --config ~/.jdu-web-teacher/teacher.credentials.json \
  session --teacher --output ~/.jdu-web-teacher/private/new-teacher.session.json
```

`issue`は同じ出力ファイルがあれば同じtokenで再試行する。既登録のLab IDへ別tokenを上書きしない。教師が学生に渡すのは、その学生専用のcredentialファイルだけ。教師のadmin keyは渡さない。教師の発行操作と学生への実際の配布は別であり、現在は既存API試験fixtureと実5台のteacher-five-probeにだけ発行済み。

学生の5台が作成されたら、実Instance ID・Deployment UUID・Lab ID・release IDを含む状態ファイルを使い、`register --state ... --receipt ...`で結び付ける。異なる5台への再登録は拒否する。構築検査の結果は `submit --report ... --receipt ...` で送る。再送には同じrequest IDと同じ本文を使い、通信失敗時も原本を保持する。学生5台を作るwrapperへの組込みは未実装。

## 判定の範囲

- DynamoDBにはtokenのhash、Lab ID、配備の対応、結果、重複処理記録を保存する。氏名は要求しない。本人が確認して紐付けたJDUメールは、教師/本人の識別表示だけに使う。
- bootstrap結果に点数を付けない。assessmentもD11の配点・課題判定器が未確定で、受付側が任意の点数を信用して採点することはない。
- 学生から受け取る結果は自己申告データであり、不正耐性を備えた成績確定システムではない。授業の確認用途とする。
- dashboardの最新結果は、後のFAIL/UNKNOWNで更新される。過去の成功を現在の合格として固定しない。
- sessionは短時間で期限切れになる。教師は30分、学生は15分。URL自体を秘密として扱う。
- unit試験17件はローカル業務規則の試験、live試験10件は実API/TLS/DynamoDBを含む範囲。学生5台・ネットワーク閉鎖・GUI・停止再開は別途検証する。

## ファイル

`progress_api.py`が受付と画面、`build_template.py`が専用Stack、`deploy_teacher.py`が誤上書きを防ぐ教師側配備、`web_progress.py`が発行・登録・送信client、`live_acceptance.py`が匿名fixtureによる実API検査。既存LabRoleを参照し、新しいIAM roleは作らない。表はStack削除でも保持する。

参考: [API Gateway HTTP APIの公式説明](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop.html)、[Nginx ssl_preread公式仕様](https://nginx.org/en/docs/stream/ngx_stream_ssl_preread_module.html)。

