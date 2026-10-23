# Web Labの配布検証と起動計画

10/22正式配布追記：D08初期環境版r3を教師private S3へ保存/全GET一致、教師/学生実CloudShellでraw署名・全file・期限を検証済み。受入済みv7 coreは全byte不変。新学生への入口は[共通正式配布toolと学生手順](../web_lab_distribution/README.md)を使う。既存state/5台/tokenは維持し、配布版確認のためにcreate等を繰り返さない。distribution_ready=true、CLASS_READY=false、期限10/27 14:24:57 UZT。以下の正式配布未完表記は当時の履歴。

10/22確定：**Class193548の別学生AWS965244652544で、署名v7取得→新規5台/96GiB→S3閉鎖→全5台SSM→内部4台SSH→個別採点登録→実課題→停止再開の候補受入が合格**。教師AWS170126527713へ全17提出の本文/受領/最新進捗が一致。最終基盤47/47・AWS29/29、WEB-02の9段階13提出、同じID/root/作業/SSH/token保持、本人の再開後RDP/Firefox、教師/学生JA/UZ/RU全6ページを確認した。署名v7とpayloadは不変。正式配布への昇格や全課題・配点の確定は別で、CLASS_READY/student_release_ready=falseを維持する。以下の「別account未検証」は以前の履歴。詳細・証跡索引・再開禁止操作は[検証状況](../../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)最上部を優先する。

## Class193548の検証済み学生環境を使う

学生本人のAWS965244652544のCloudShellを使う。現在は次の短いcommandを設置済みで、新しい端末でもPATHへ自動追加する。既存.bashrcは変更前のbackupを保持。共有Windowsへ秘密鍵や認証fileをdownloadする手順はない。

```bash
jdu-web-progress id
jdu-web-check bootstrap
jdu-web-check P1
jdu-web-check M1
jdu-web-my-progress
```

`id`はclass193548-test1、基盤は47/47。P1/M1は未導入の学生開始状態へ戻してあるため各2/10で、完了0/2が正しい。上の値は検査項目数で、科目配点ではない。`jdu-web-my-progress`の時限閲覧URLは本人のCloudShellで扱い、教材や提出物へ書き込まない。授業で使う正式な全課題ID/配点と残checkerはD11に残る。

```bash
jdu-web-lab status --state "$HOME/jdu-web-class193548/student-v7.private.json"
jdu-web-lab ssm --state "$HOME/jdu-web-class193548/student-v7.private.json" --role web
```

`--role`はbastion/web/dns/db/repo。いずれもssm-userで入り、`exit`でCloudShellへ戻る。内部SSHの学習経路は踏み台のlabuserからの4台SSHとして別に保持する。RDPは現在98.86.160.22、labuserと本人設定済みpasswordを使用する。停止再開でpublic IPは変わるため、必要時だけstatusで再照会する。

この学生state/受信済み認証/元の5台を使い続け、create・受信・鍵生成・登録apply・今回のstop/start試験を重ねない。別の学生へ現在のprivate state/tokenや検証専用runnerを流用しない。新規配布は、その学生のLab ID/account・期限内の価格/署名・教師の新規個別認証を照合してから進める。検証専用のClass193548固定補助と、署名済み共通jdu-web-labを区別する。

## 以下は制作・受入の履歴

10/20最終：署名tools **c5-v6**でテスト２の同じ新5台/元rootの候補受入が合格。全5台の常設SSM・S3閉鎖・内部SSH/採点登録・基盤47/47/AWS29/29・実WEB-02 13 assessment・全roleの空cache内部導入・7wheel/WSGI起動・登録後停止再開/本人GUIを実確認。学生が導入するNginx/BIND/PostgreSQL/venv/pipは未導入へ復元した。bytecode抑止修正の関連74試験/移行guard2試験も合格。外側署名v6は10/27期限、旧署名物は保持。v4新規作成→常設SSM v5→bytecodeだけのv6移行を受入した範囲で、v6のcold CreateStackは未検証。別学生Lab [193548]の取得・配備・登録・送信を次に確認する。正式学生配布/D08全体/CLASS_READYは保留。 最新状態・証跡・再開手順は[検証状況](../../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)冒頭。以下の10/16以前の入力待ち/未実装記載は履歴であり、最上段を優先。

10/16 18:09 UZT：本人指示で一時中断。署名v4の新5台（teacher-c4-probe）はStack CREATE_COMPLETE/全running、bootstrap段階。新環境の閉鎖/内部SSH鍵/採点登録/GUI受入は未実施。下記の旧teacher-five-probeの登録・47/47を新5台の受入として使わない。入力待ちはなく、再開手順はverification_status.md冒頭。

10/16 v4：v3は本人password入力後、selectorの大文字roleを小文字で参照してStack要求前に停止。v4でrole/templateの全21 parameterを入力前に検査する形へ修正・再署名。59試験、署名展開sourceの作成境界6試験、CloudShell実SDK schema/新planに合格。新規配備はv4だけを使用。現在は本人再入力待ちで、まだ新Stackを要求していない。最新状態はverification_status.md冒頭。

10/16再開：署名tools候補v3のlocal53試験・CloudShell署名/改ざん拒否・読取りplanに合格。S3 global URL対応、password入力前の配布物確認、教師API/IP照合、minimal GPGのpublic-only検証を修正。本人が旧5台をroot96GiB保持で終了して新5台へ置換する具体案を承認。終了/保持確認後に新規配備へ進む。D08/正式配布/CLASS_READYは未完了。最新状態はverification_status.md冒頭。

10/16中断：本人指示により既存学生5台を維持し、追加・置換・終了を行わず再開待ち。共通入口の署名tools候補c4-v1は制作済みで、関連47試験とCloudShellの読取りplanのみ実受入。新規create等の通し受入は未実施。下記の古い「作成・更新・削除は未実装」は初期段階の記録。現在は試作実装があるが、正式配布/CLASS_READYは未認定。置換計画は未承認・未実行。最新の停止判断と再開時レビューはverification_status.md冒頭を優先。

10/16 c4統合続報：1128 DEB/7 wheel/署名app33file/checker19file/installerを含む署名payload候補を完全検証し、非公開S3別prefixへ保存。実WEB-02の候補P1/M1は9段階/13提出と署名短command・教師保存・本人画面まで受入。実Webで署名app/7 wheelのオフラインruntimeも合格した。試験用Nginxは元package状態へ戻し、最後のfresh基盤47/47も合格。**正式学生配布・新規plan/create/lock/status/preflight・fresh配備受入は残り、D08/CLASS_READYは未完了。** c4のscope student_payloadは収録範囲であり、新規5台の受入を表さない。現在の5台はc3のまま。詳細は[教師用README](../web_lab_teacher/README.md)とverification_status.md冒頭。


10/16最新受入：同じ5台の停止再開後も4台SSH/役割/通信/AWS25が合格し、本人がRDPとFirefoxの再起動後利用も確認。実5台の採点登録/verifyと踏み台47項目送信/教師保存一致が完了。OS-Linux-Controlの現行command/教師機能を参照し、Web専用教師を課題別最新結果・3言語・30秒更新・本人ページへ更新した。個人CloudShellの`jdu-web-check bootstrap`はSSM→踏み台→4台のfresh確認後に自動送信する。テスト２用commandの実受入版であり、学生向け署名payload/create/lock/status統合は未完。詳細は[教師用README](../web_lab_teacher/README.md)とverification_status.md冒頭。

以下は実装経過。現在の受入状態と鍵方針は上の最新段落を優先する。

10/16最新訂正：本人指定でCloudShell→踏み台はSSMのssm-userを採用する。この区間はSSH秘密鍵不要。`enable_ssm_probe.py`はteaching閉鎖済み5台のlive状態を確認し、踏み台だけの既存LabInstanceProfile追加とSSM用endpoint2個・専用SG・限定egressの5変更をprepare/review/executeする。サーバー置換・他4台変更・UserData/KeyName/RDP/S3変更を拒否する。本人が権限と課金を確認後に適用承認済み。実受入の最新状態はverification_status.md冒頭。下のCloudShell→踏み台の鍵転送案も旧方針で、内部4台のSSHは別に検証する。

SSMは適用済みUPDATE_COMPLETE。AWS25項目全PASS、CloudShellからssm-userで接続/sudo成功。SSMでの新しい実通信確認も4項目全PASS。`setup_internal_ssh.py plan`は本人配備5台/4ホスト鍵を読取り照合してplanを保存する。`apply`は本人操作で実行し、踏み台labuser内で新鍵を生成、EICの短期公開鍵で内部4台へ接続して既存authorized_keysを保持した公開鍵追記と`lab-ssh`入口を準備する。秘密鍵は踏み台から出さない。`verify`は最終EIC公開から62秒以上待ち、短期鍵を再送せず4台へSSHし、永続登録を検証する。本人applyと期限後/停止再開後の実4台SSHは受入済み。実行先/引数/再開状態はverification_status.md冒頭。

10/16鍵取扱いの本人訂正：授業Windowsは共有OSアカウント、Academyは学生ごとのアカウント。秘密鍵の共有Windowsへのdownload/保存/RDP手動搬入は採用しない。個人CloudShellでの生成・保管は本人了承。配備ツールから本人踏み台への安全な自動受け渡し・4台の公開鍵対応を制作する。現行c3のKeyName=vockeyは保持しつつ、CloudShell→SSM/踏み台内鍵だけの4台SSHを実装・受入済み。下記のPC→踏み台/import-key案は旧手順。詳しくは[サービス設計](../../system_requirements/2026-10_web_infrastructure_service_design.md)と[起動契約](../../system_requirements/2026-10_web_infrastructure_bootstrap_contract.md)。

10/16 GUI受入続報：本人がRDPのLogin failedの原因をキー配列の違いと確認し、配列を合わせてデスクトップ・Firefoxとも起動成功。password設定変更やCIDR拡張は行っていない。[RDPの接続案内](RDP_CONNECT.md)へ再発時の確認を追加。旧vockeyのPC download案は不採用。CloudShell→SSM、踏み台内だけの内部鍵自動準備・4台SSHを受入済み。GUI成功だけでSSH/採点登録/CLASS_READYを合格にしない。以下の認証切分け中という記述は経過。

10/16最新受入：c3で全5台初期化・AWS21・bootstrap通信が合格し、teachingのBootstrapSg/S3Endpointだけを更新。05:29:15 UTCに同じ5台でLOCK_TRANSITION_OBSERVED/S3新規接続拒否/他role通信全PASS・UPDATE_COMPLETEを実確認。証拠はpackages側candidate-c3/five-node-teaching-acceptance.json。本人RDPは青いxrdp画面でLogin failedとなり認証切分け中。`check_rdp_password.py`は配備入力hashとの読取り照合だけを行い、password変更・保存・hash出力はしない。guest shadow/PAMの検査ではない。入力待ちを妨げず、verification_status.md冒頭から再開する。D08/CLASS_READYは未完了。以下は経過記録。

10/16の適用続報：c3でrepo初期化6項目/network3項目に実合格。新規3台がVocareumに起動直後終了されたため、本人承認で完了済み旧probe4台のEC2だけを終了しroot80GiBを全保持した。`resume_teacher_probe.py`は成功repoを維持し、同一template/全parameterのまま失敗4役を再試行する。解決済み変更セット（IncludePropertyValues=True）で成功済みrepo/endpointのno-opが消えることを確認し、終了済み・CREATE_FAILEDの3台だけの再作成を許す。4試験合格。CloudShellの適用版は`c3-transfer/transfer/resume_teacher_probe_v2.py`。再試行後は全5台running/AWS21項目全PASS、残roleの導入/teaching閉鎖/GUI/鍵/登録等を受入中。D08未完了。

10/16再開の最新情報：clean cloneを起動後に接続してread-only診断が成功し、初回repoは`sshd -t`時の`/run/sshd`不存在で失敗していたと確定。SSH policy検査前にroot:root/0755のruntime directoryを準備し、既存symlink/file/不正owner/modeは拒否する。認証制限は維持。serialログに挿入される時刻はbracket付き/optional Zだけを除去し、report本来の時刻は保持する。関連33試験がWSL Ubuntuで合格、修正を含むc3を署名制作。旧templateは保持し`web-lab-c3.template.json`を分離した。回収機はstop/元UserData復元/clone detach実施済み。以下の10/15の中断・原因未確定の記述は履歴。現在のAWS適用状況は[検証状況](../../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)冒頭を参照。

更新: 2026-10-15。D08の最初の実装。署名済み配布物を検証する`verify`と、AWSを読取り照会して新規計画を保存する`plan`を提供する。EC2/Stackの作成・更新・削除は実装していない。

追記: 上記の作成未実装は学生用 `web_lab.py create/lock` を指す。教師専用のAMI probe・依存collector・回収templateを別に制作し、テスト２で実行している。Ubuntu基礎8項目と、private repo1台のguest10/AWS12項目に合格。1128 DEB/7 wheelを収録・回収し、RSA3072/SHA256の署名APT/全file目録を制作した。外側manifest24試験とpayload7試験の計31件に加え、role保護・5台構成・loaderの16試験も合格。学生releaseはまだない。

教師用の採点受付は別の [web_lab_teacher](../web_lab_teacher/README.md) に制作し、実API10ケースを確認した。`make_five_node_template.py` / `node_loader.py` / `node_bootstrap.py` はrepo先行後の5台を準備し、`network_probe.py` は初期S3接続から閉鎖後の新規接続拒否を記録する。57 resources/49,872 bytesのtemplateをAWS ValidateTemplateで確認した。公開RDPは10/15更新の公式50 CIDR、SSHは内部だけ。ユーザーはこの条件の配備を承認済み。実5台導入・学生create/lock統合・GUI/SSH/登録/停止再開は残件。D08/BASE_READY/CLASS_READYとはしない。package-only candidateは明示指定した教師検証だけに使え、学生releaseとしての検証は拒否する。

`prepare_teacher_probe.py` は読取りだけでprivate planを作る。`deploy_teacher_probe.py` はレビューした教師probeだけを対象とし、同じtemplate/account/既存公開鍵/c2 bundleを再照合する。本人によるRDP passwordの非表示2回入力後、NoEcho hashだけをAWSへ渡す。password/hash/短期URLをstateや通常出力へ保存しない。一般学生の起動wrapperや最安選定との完成統合ではない。既存probe state/Stackがあれば新規作成を拒否する。

`inspect_teacher_probe.py` は配備/実Instance IDに一致するguest結果だけを採用し、AWSのSG全rule・root EBS・route・endpointと照合する。`lock_teacher_probe.py` は全5台の初期受入とS3到達baselineが確認できた場合だけteaching change setを作り、BootstrapSgとS3Endpointの置換なし2変更以外を拒否する。これらの保護11試験はローカル合格、実5台/lock受入は未完。初回5台probeはrepo初期化のCalledProcessErrorでCREATE_FAILEDとなり、他4台は未作成。診断中にAcademyのAWS権限が明示denyになったため、Lab再開後に原因を調査する。失敗Stackへcreateを重ねない。

Lab復旧後、元account/private stateとの一致と旧診断7台の停止を確認した。`diagnose_teacher_node.py` はこの失敗repoだけを照合して停止し、rootのsnapshotから独立したcloneを作る。元rootはdetachしない。診断機は元のprivate subnet/BootstrapSgだけで公開IP/IAM/keyを持たず、cloneの明示volume IDとext4 root partitionを照合して`ro,noload`で読む。安全化した末尾logだけをconsoleへ出し、自動停止する。進行stateはCloudShell privateに保持し、prepare/snapshot/launch/statusの各段階で再実行・対象相違を拒否する。診断資源の削除はこのtoolに含めない。

実行時、新規診断機はVocareumの管理処理により起動7秒後に終了したため、新規機の追加試行を止めた。既存回収3号を使う `reuse_node_diagnostic.py` を追加。cloneを起動前に接続するとcloneがguest rootとして選ばれたため、回収機を自身のrootだけで起動し、45秒以上後にclean cloneを後付けする。GUESTは既にmount済みのtargetを拒否する。古いUserDataはCloudShell privateにのみ退避し、中断時に元へ戻した。10/15本人指示で中断、初回repoの根本原因は未確定。再開はverification_status.md冒頭を参照する。

未配布の次candidate向けに、初期化失敗の段階・固定command名・exit codeだけの診断を追加。例外本文・argv・標準出力/標準エラー・password/hash/URLは含めない。秘密混入の拒否4試験と既存Linux role9試験はWSL Ubuntuで合格。これだけで初回失敗の原因確定や実5台受入とはしない。

`retry_teacher_probe.py` は元passwordをUsePreviousValueで維持する修復候補の制作段階。node UserDataだけのtemplate差分、新しいWaitHandle、既存repoの置換なし変更だけを許す。元rootを残したEC2 root復元はDryRunOperationのみ確認し、実行していない。修復差分保護6件、誤clone拒否2件を加えた関連21試験はWSL Ubuntuで合格。まだ署名candidateへ収録せず、AWSへ搬入/適用していない。

仕様の正本は[起動入口と初期化の実装仕様](../../system_requirements/2026-10_web_infrastructure_bootstrap_contract.md)。既存の[最安T系選定](../web_lab_instance_selector/README.md)を、署名付きhashの確認後に呼び出す。既存Linuxのscriptは変更していない。


## 新しいClass向け候補を制作するとき

`build_student_tools.py` は今後 `--teacher-facts` / `--payload-facts` / `--teacher-account` / `--class-id` を必須とする。既存テスト２の教師API/IP/S3を新しいClassへ暗黙に持ち込まない。公開factsのaccount/Class/region、24時間内の検査日時、HTTPS health、AWS発行API名/公開IPを検査し、搬入先を移す場合も受入済みpayloadの完全なhash/size一致を要求する。scopeはteacher_endpoint_public_facts / teacher_payload_public_facts。RDP password・Lab token・短期URL・教師adminをfactsへ入れない。5境界試験合格。Class193548の教師実値は配備・HTTPS受入済み。大容量payloadの新private S3移送/全1155file/GET完全検証を完了し、実teacher/payload factsからClass193548 v7を制作した。82,074 bytes/archive SHA256 082ffed4773ea42d9c35368cedca0a8e5f8ea213979971f25e7e953707a35365、manifest SHA256 a00239fa1cb8efc09d8cad214c6e97f5c99f1436c9549c3f66bf09ea9ee4a3d2。raw/outer署名とcontrollerをlocal・教師CloudShellで検証し、新private S3の3object全GETも一致。実学生accountの取得・新規配備はまだ。c5-v6以前の署名archiveは不変。

## 入力と信頼の基準

- Python 3.10以上、GnuPG、`plan`では認証済みAWS CLI v2が必要。Pythonの追加packageは不要。CloudShellでの実受入は未実施。
- CloudShellのAmazon Linux 2023ではGPG最小版だけの場合がある。今回、gpg-agent不足で公開鍵のimportが失敗し、[AWS公式手順](https://docs.aws.amazon.com/linux/al2023/ug/gnupg-minimal.html)の `sudo dnf -y swap gnupg2-minimal gnupg2-full` 後に実署名検証が成功した。gpgの存在だけで動作済みとしない。学生用verify/planの通し受入は別に残る。
- 教員が配布する小さなtool archiveには、`web_lab.py`、`release_validation.py`、`deployment-manifest.schema.json`、selector、CloudFormation template、公開鍵、署名済みmanifestを含める。これらの版を揃える。
- `--trusted-fingerprint`は、授業資料等の別経路で確認した教員の完全な40桁primary fingerprintを指定する。同じ未検証archive内の値を写すだけでは信頼の確認にならない。最初に実行する検証tool自体の配布元も確認する。
- 教員の署名秘密鍵はこのdirectoryにも学生配布物にも置かない。RDP password・採点token・SSH秘密鍵・短期URLはこのcommandの入力にしない。学生から受け取るのはSSH**公開鍵**だけ。

完成した授業用deployment manifestと受入済みの学生releaseはまだ存在しない。実際の署名公開鍵・package candidate・教師probe templateは制作済み。`test_web_lab.py`内のIP/AMI/鍵/価格/templateは使い捨ての試験値で、実配布用の値ではない。公開IPの文字列検査は所有権や受付の稼働を保証しない。

## command

以下はCloudShell/Bash向け。教員が実際の配布版を作ってから実行する。現在`jdu-web-lab`というshell commandは設置していないため、Pythonで呼ぶ。

教員がbundleを含む配布物一式を手元で検証する場合:

```bash
python3 web_lab.py verify \
  --deployment-manifest deployment-manifest.json \
  --signature deployment-manifest.sig \
  --public-key jdu-web-release.asc \
  --trusted-fingerprint "$TEACHER_FINGERPRINT" \
  --artifact-root .
```

署名→JSON構造/期限/固定値→7成果物のSHA256とサイズ→実行中toolとの一致を確認する。成功は`RELEASE_VERIFIED`、`scope=local_files_only`。AWSの確認や授業開始可能の意味ではない。

学生が新規起動計画を作る場合:

```bash
python3 web_lab.py plan \
  --deployment-manifest deployment-manifest.json \
  --signature deployment-manifest.sig \
  --public-key jdu-web-release.asc \
  --trusted-fingerprint "$TEACHER_FINGERPRINT" \
  --artifact-root . \
  --lab-id student-001 \
  --key-name student-key \
  --public-key-file student-key.pub \
  --output deployment-plan.json
```

学生の小さなtool archiveに大容量のrepo bundleは不要。`plan`はmanifestに署名されたbundle hash/サイズを保持し、他6成果物を実検証する。bundleの実検証は配布EC2での取得後に行う。`node_loader.py` / `payload_runtime.py` に取得・hash・署名・安全展開を実装し、private repo1台で実測済み。学生用create/lockとの統合は未完。保存planの`bundle_verified_locally=false`で保留を明示する。手元にbundleがあっても`plan`では本体の検証を省く。完全検証には`verify`を使う。

署名検証後、次を照会する。失敗を未確認のまま成功に置き換えない。

| 確認 | 停止する条件 |
| --- | --- |
| STS account | 認証/照会失敗、account不明 |
| `jdu-web-<Lab ID>`の既存Stack | 状態にかかわらず存在する。正確な「存在しない」エラー以外も停止 |
| 固定AMI | liveのowner/ID/name/x86_64/HVM/EBS/root容量/available/publicが署名値と不一致 |
| KeyNameの公開鍵 | 学生fileとのOpenSSH鍵本体の不一致。EC2 fingerprintの方式差には依存しない |
| S3 prefix list | AWS管理IPv4かつ指定regionのS3用でない |
| template | `ValidateTemplate`失敗。現在はローカル51,200 byte以下のみ |
| AZ/type/価格 | 同一AZに3サイズが揃わない、性能不足、価格不明/台帳期限切れ |

`--price-catalog FILE`、`--exclude-family FAMILY`、`--exclude-pair FAMILY@AZ`も選定toolと同じ条件で使える。Pricing照会失敗時に価格を推測しない。台帳を使う場合はregion/USD/AWS Price List/7日以内を確認する。既存Stackの停止再開・更新には`plan`を使わない。

成功は`PLAN_READY`であり、作成権限/quota/実容量・S3取得・初期化・GUI・SSH・採点は未確認。`ValidateTemplate`は構文等の確認で、ネットワーク仕様との一致や配備成功の保証ではない。[AWS仕様](https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_ValidateTemplate.html)

planは排他的に新規保存し、上書きを拒否する。POSIXでは0600で作成する。WindowsのACL設定はこのmode値だけでは保証しないため、標準運用はCloudShellとする。account/Deployment ID/鍵のhash等を含むplanを学生間で共有・公開しない。標準出力にはaccountや公開鍵本体を表示しない。既存stateの更新とcreate時のplan再検証は後続実装。

終了codeは現段階で`0=当該commandの成功`、`2=入力/署名/構造/選定の検証失敗`、`3=AWS読取り失敗`。仕様書の将来のcode 4〜7やcreate/lock/status/diagnose/host側commandは未実装。

## schemaと検証規則

[deployment-manifest.schema.json](deployment-manifest.schema.json)をschema version 1の契約とする。固定CIDR、50件のRDP許可IPv4、Canonical Ubuntu24.04/amd64、実AMI、S3/採点先、releaseと期限、7成果物を必須にする。未知field・boolによる整数代用・JSON重複key・非有限値・path逸脱・リンク・欠品・重複成果物を拒否する。RDP CIDRは公開IPv4の正規表記と非重複を確認する。現在のschemaは授業方針の50件を要求するため、許可件数の変更はschemaと配布版も合わせて更新する。

`release_validation.py`の構造検査は、この同梱schemaで使う限定的なJSON Schema vocabularyの実装である。一般のJSON Schema validatorを代替するAPIではない。schemaを拡張するときは検査器も対応させる。[JSON Schema Validation 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation)

署名検証では一時的な空のkeyringだけを使い、自動key取得を無効にする。RSA3072以上、SHA256/384/512、独立に固定したprimary fingerprint、有効なprimary/signer・manifest/署名期限を確認する。失効は同梱公開鍵で観測できる範囲の確認で、オンライン失効照会は行わない。`gpgv`単独は鍵の期限/失効を検査しないため、GPG metadataも確認する実装にした。[GnuPG公式](https://www.gnupg.org/documentation/manuals/gnupg/gpgv.html)

配布dirは本人が管理し、検証中に別processが書き換えない。鍵とOS/toolの信頼をこのscript単独で確立することはできない。bundle/templateから実環境を作る処理は、実行直前にもrelease/account/期限/planを再検証する必要がある。

## 試験と残件

```bash
python3 -m unittest -v test_web_lab
```

2026-10-15、WindowsのPythonとGit付属GnuPGで24件合格。実際の使い捨てRSA3072鍵/署名を用い、改変・異なるfingerprint・SHA1・期限切れmanifest/鍵・署名subkeyのprimaryへの結合/期限・欠品・path逸脱・実行tool不一致等を確認した。AWSはすべて模擬応答で、AMI/鍵/region不一致・既存Stack/AccessDenied・Pricing失敗・小さなarchiveからの計画保存・書込みAPI拒否を確認した。既存selectorの9件も合格。AWS照会とCloudShellでの実受入は未実施。

次は公式AMI/初期tool・学生の必要権限を実確認し、依存一式の収録と最小repo用template/install処理を制作する。その後、他4台、create/lock、個別鍵/採点登録、通信拒否、停止再開の順に受入する。D08全体は未完了。

公開仕様の確認日: 2026-10-15。[AMI照会](https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-images.html)、[公開鍵を含む照会](https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-key-pairs.html)、[prefix list照会](https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-managed-prefix-lists.html)。

## 教員のAMI初期状態の検証

`ami-probe.template.json` と `probe_ubuntu_base.py` は、固定AMIの初期ツール・dpkg一覧を採取する1台専用の検証物。学生用5台templateとは別物で、`web_lab.py create` の実装でもない。packageを追加せず、公開IP/IAM profile/受信許可を付けず、暗号化gp3 8 GiBと外向き通信を閉じたSGで実行する。

測定出力は `/var/lib/jdu-ami-probe/console-report.txt` に保存し、`/dev/ttyS0` にも送る。採取後の自動停止まで5分の猶予を設ける。`GetConsoleOutput --latest` は起動中に回収し、`JDU_AMI_BASE_DONE`・圧縮report・reportのSHA256をすべて確認してから測定成功とする。Stack作成成功や自動停止だけでは合格にしない。停止済みの初回検証でconsole出力が空になったため、回収経路を補強した。空になった原因自体は未確定。

実機結果・残存資源・再開手順は [検証状況](../../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md) を参照する。検証後も停止したEBSには課金が残るため、必要な証拠の回収・保持判断を記録する。


## 教師5台probeの現在の入口

2026-10-15、candidate c2のローカル/CloudShell両方の署名全file検証と非公開S3保存が完了。教師probe専用の起動保護5試験もCloudShellで合格。RDP passwordはCloudShellの対話promptで本人が2回入力する。入力が一致すると、事前承認されたネットワーク条件の5台を新規作成する。現在のprivate plan/state名、再開commandと実資源は [検証状況](../../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md) を参照。既存Stack/stateがある場合はcreateを繰り返さない。
