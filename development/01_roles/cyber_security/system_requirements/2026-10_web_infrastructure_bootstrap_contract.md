# Web単元の起動入口と初期化処理の実装仕様

10/22正式配布追記：D08初期環境版r3を署名して教師private S3へ保存し、教師/学生実CloudShellの展開前署名・全file・期限、教師実DBの既存token照合を完了。受入済みv7 core/既存5台/state/認証は不変。[正式配布の共通入口・教師/学生手順](../tools/web_lab_distribution/README.md)を使用する。distribution_ready=true、D11/D12と授業全体のCLASS_READY=false。期限10/27 14:24:57 UZT。以降の未配布表記は当時の履歴。最新はverification_status.md最上部。

10/22最終受入：Class193548の別学生AWS965244652544で署名v7のcold CreateStackからの候補受入を合格。教師170126527713を先に稼働させ、署名取得→新規5台→初期化→S3閉鎖→全台SSM/内部SSH→専用登録/送信→実課題→停止再開保持/本人GUIまで通した。AWS29/29・基盤47/47、実WEB-02の9段階13提出、教師の別accountによる全17提出の本文/受領/最新/登録5台の独立照合、三言語教師/本人全6ページと短いcommandも合格。テスト２の同一payloadによる全role空cache導入/7wheel/WSGI受入は保持。**D08の別学生候補受入は完了。正式配布への昇格・D11全課題/配点・授業全体のCLASS_READYは別の残件。** v7のcandidate表記/署名期限とCLASS_READY=falseを変えていない。詳細は[最新検証状況](../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)冒頭。以下の以前の未実装/待ち状態は経過記録。

2026-10-20最新方針：本人指定で、各自のCloudShellから**5台すべて**へSession Manager/ssm-userで接続できる経路を継続して残す。既存LabInstanceProfileを全5台に付け、既存SSM/ssmmessages endpoint2個を共用し、同じ5台だけの共有SGから443を許可する。初回S3通信の閉鎖後もSSMは維持する。踏み台→内部4台のSSH演習は別に残し、共有Windowsへ秘密鍵を保存しない。署名tools c5-v5に各roleのSSM入口、再起動でconsole記録が失われた際の公開検査回収を収録。下の10/16の「踏み台のみ」方針はこの決定で更新する。新5台の実機状況・未実施の鍵/採点登録はverification_status.md冒頭を優先し、旧5台の47/47と混同しない。

2026-10-16 c4続報：学生向け署名payload候補へapp/checker/検証installerを収録し、WEB-02の候補P1/M1を実機の状態確認・自動送信・教師進捗へ統合した。正式な全課題ID/配点は未確定。署名短commandの基盤47/47、実HTTP9段階/13提出、実Webの固定7 wheel/runtimeに合格した。候補収録のstudent_payload scopeと正式配布/fresh配備受入を区別し、D08/CLASS_READYは未完了。新規学生のplan/create/lock/status入口は引き続き制作・受入対象。最新の実値・再開禁止操作はverification_status.md冒頭を優先する。


2026-10-16最新方針：本人指定でCloudShell→踏み台はSession Managerのssm-userで接続する。この区間のSSH秘密鍵は不要。管理入口は踏み台だけに既存LabInstanceProfileを付け、SSM/ssmmessagesの専用endpoint2個へ踏み台SGから443だけを許可する。本人は管理権限と既存LabRoleの追加権限・endpoint時間課金を確認して適用承認済み。既存5台のID/root/RDP制限/S3閉鎖を維持する。内部4台のSSHは別に受入し、共有Windowsへの秘密鍵保存は要求しない。実受入状態はverification_status.md冒頭を優先する。

**2026-10-16最新の鍵取扱い：共有WindowsへSSH秘密鍵を保存しない。CloudShell→踏み台はSSM/ssm-userで接続し、内部4台用の鍵は踏み台のlabuser内だけで生成・保管する自動設定を実装。本人apply後に短期公開鍵の失効を待って4台の実SSHに合格し、5台停止・再開後も成功した。以下の既存KeyName/公開鍵file入力は旧prototypeの説明で、学生必須手順にそのまま転用しない。学生向け署名配布/create/lock統合は未完了。**

2026-10-15実機更新: 固定Ubuntu AMIの基礎8項目に加え、1128 DEB/7 wheelを収録・署名し、隔離private repo1台のguest10/AWS12項目に合格した。5台template/role初期化・教師probe用入口を制作し、AWS ValidateTemplate/preflightまで確認。RDP/GUI・実鍵・登録・teaching閉鎖・停止再開と、学生用create/lockの統合は未受入。UbuntuにはAWS CLI/cfn-signalがなく、通知は標準PythonのHTTPSで行う。以下は完成時の契約で、旧「未制作」の実装状況は [最新検証状況](../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md) と [実装README](../tools/web_lab_bootstrap/README.md) を優先する。

更新: 2026-10-15（Asia/Tashkent）  
対象: D08。教員の制作手順、学生の起動入口、scriptの入出力、失敗時の処理、授業開始の判定。

配布サーバーを先に準備し、他4台を内部配布で初期化する。5台の自動準備、授業用通信への切替、個別のSSH/採点設定をそれぞれ確認してから、学生がDNS・DB・Webの構築を開始する。既存の5台/IP・署名付き配布・役割別size・最安T系/AZ選定を維持する。

本稿のcommand名・path・JSON項目は制作時の契約。[インスタンス選定script](../tools/web_lab_instance_selector/README.md)と、[署名検証・読取りplan](../tools/web_lab_bootstrap/README.md)を実装した。後者のschema/検証器/wrapperはlocal24試験、selectorは9試験に合格。AWSは模擬応答で、実照会・実権限確認・CloudShell受入は未実施。create/lock/host側command、初期化script・CloudFormation・checker・実配布物は未制作。判定表は実装後の受入条件であり、実機合格の記録ではない。

## 1 教員が用意するものと制作順

| 順序 | 制作/確認 | 成果物 |
| --- | --- | --- |
| 1 | 公式AMIのowner/architecture/root・取得tool、Labの必要権限を確認 | 基準AMIの実IDと初期package一覧、pilotの検証記録 |
| 2 | 同じ基準環境でAPT・wheel・app・SQL・初期化script等を収録 | 版固定のpayload。GUI/basic toolの全依存も含む |
| 3 | payload一覧と署名付きAPTを作り、空cache・外部取得不可で導入 | release.json、SHA256SUMS/署名、PKG受入記録 |
| 4 | repoを初回起動できるbundleへまとめる | repo-bootstrap.tar.gz。Nginxと全依存を手元から導入できる |
| 5 | bundleのhashと公開鍵を使うCloudFormation、起動wrapperを制作 | web-lab.yaml、jdu-web-lab、署名付きdeployment-manifest.json |
| 6 | private S3の固定prefixと教員の固定採点受付を準備 | 実bucket/prefix、受付IPv4/FQDN、証明書、上流、個別登録方式 |
| 7 | 学生権限で新規配備→通信閉鎖→個別設定→停止再開 | PKG/NET/AWS受入、配布用の小さなtool archive |

採点受付の認証確認とLab登録はD11のAPI/ID契約にも依存する。D08の制作を進めつつ最小の登録・認証疎通をD11側と合わせ、全課題の採点器が未制作でも基盤準備と採点準備の状態を別々に表示する。採点の準備が未完なら授業開始可能とは判定しない。

### hashを循環させない配布構造

release.jsonはソフトのpayload・基準AMI・package版・必要path・公開鍵fingerprintを持つ。自身のhash、完成後のbundle/template/UserDataのhashを同じfileへ書き込まない。

1. payloadを固定し、その一覧をrelease.jsonへ書く。
2. payloadとrelease.jsonを含むSHA256SUMSを生成する。SUMS自身とその署名は対象外とする。
3. 教員がSHA256SUMSを署名し、これらをrepo-bootstrap.tar.gzへ格納する。
4. archiveのSHA256を計算し、それを参照するtemplate/UserDataを確定する。
5. 外側のdeployment-manifest.jsonにbundle/template/selector/wrapper/validation/schema/public keyのhash・サイズ・実AMI・入力仕様を書き、これも教員が署名する。実行する検証器とschema自体も配布版へ結び付ける。

deployment-manifestとtemplateはrepo bundleへ戻して格納しない。署名・bundle・templateが互いの完成hashを要求する構造を避ける。Lab固有のAZ/type/資源IDはdeployment-state.jsonへ記録し、全員共通の署名済みreleaseに混ぜない。

外側manifest version 1の実装契約は[JSON schema](../tools/web_lab_bootstrap/deployment-manifest.schema.json)。未知項目・未記入/placeholder・期限切れ・固定値の不一致・不正なpath等を拒否する。小さなtool archiveを使うCloudShellのplanでは署名と6つの小さな成果物を検証し、bundle本体は要求しない。bundleのhash/サイズは署名済み入力として保持し、配布EC2が取得した直後、展開・実行前に検証する。手元で7成果物すべてを検証する教員用verifyも実装した。配布EC2側の取得/検証/展開は次の制作対象で、現時点では未実装。

## 2 学生の入口と入力

標準入口は学生のAWS CloudShellとする。教員が提供する版固定の小さなtool archiveを取得/展開し、配布元と公開鍵fingerprintを教員資料で確認する。AWS CLI・Python3・OpenSSL・GPGの検証tool・ssh-keygenの有無と版を最初に確認する。足りないtoolや授業版の不一致を隠して続行しない。学生の踏み台からAWS APIを呼ぶ方式にはしない。

| 入力の担当 | 内容 | 保存/検証 |
| --- | --- | --- |
| 教員の署名済み配布 | region、AMI実ID/owner、release、bundle/template/hash、公開鍵、S3 prefix list/配布先、受付IP/FQDN、RDP許可CIDR | 署名とhashを検証し、配布値から勝手に宛先を広げない |
| 学生 | 匿名Lab ID、RDP password。SSH鍵は教員ツールが本人CloudShellでLabごとに生成・保管する方針 | 共有Windowsへ秘密鍵を保存しない。公開鍵/KeyNameの配備値はツールで整合させる（制作待ち）。Lab IDは小文字英数/ハイフンの3〜32文字。passwordは対話入力で2回確認しhashだけをAWSへ渡す |
| 自動選定 | 同一AZ/familyのmedium1＋small3＋micro1、料金根拠 | 既存selectorを実行しselection-plan.jsonへ保存 |
| 短期の搬入権限 | bundle取得用の署名付きURL | 配布直前に有効期限を確認。通常log/Outputsへ出さず、共通の不変manifestには含めない |
| 初回RDP接続後の学生 | 自動配置したSSH鍵での接続確認、Lab専用採点登録値 | SSH鍵の手動importは必須にしない。本人の踏み台で操作。秘密を共有archive・UserData・AWSタグへ含めない |

regionは教員の配布値を使う。AMI/IPv4/domain/bucket/hashが未記入の雛形、期限切れURL、別regionの価格台帳では作成へ進めない。公開鍵は本人CloudShellのLab専用鍵から導出し、EC2 KeyPair・対象OSの許可鍵・踏み台の秘密鍵との対応を照合する。共有Windowsを秘密鍵の取得元・保管先・手動転送元にしない。現行prototypeの--key-name/--public-key-fileは既存入力形式であり、新方式の完成実装とみなさない。[公開鍵を含む照会](https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-key-pairs.html)

RDP passwordは端末履歴やprocess引数へ置かず、OpenSSL等へ標準入力で渡してhash化する。CloudFormation parameterはNoEchoを使うが、これだけでUserData/Metadata/Outputsの秘密を保護できるとは扱わない。採点token・DB password・SSH秘密鍵をそこへ投入しない。[NoEchoの範囲](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html)

### commandの実装状況と呼出し仕様

以下は最終的な呼出し仕様。現時点では`python3 web_lab.py verify/plan`だけ実装済みで、`jdu-web-lab`のshell入口とその他のcommandは未実装。実引数と例は[tool README](../tools/web_lab_bootstrap/README.md)に従う。

| command | 実行場所/処理 | 終了時の状態 |
| --- | --- | --- |
| jdu-web-lab plan | CloudShell。認証/account/region・配布署名・AMI・KeyName等を照合し、既存Stackの有無を確認。新規だけselectorを実行 | PLAN_READY。まだEC2を作らない |
| jdu-web-lab create | CloudShell。planと配布hashを検証、RDP hashを安全に受け渡してStackを作成、RepoReady1件→他4件を待つ | BASE_READY。5台の自動準備成功まで |
| jdu-web-lab lock | CloudShell。同じtemplate/parameter/EC2を確認してDeploymentPhaseだけteachingへ更新。実SG/endpoint policyを検査 | INFRA_READY。個別鍵/GUI/採点の確認は未完でもよい |
| 旧jdu-web-import-key | PCからの手動搬入案は不採用。CloudShellからの自動受け渡し・踏み台での照合へ置き換える（制作待ち） | 学生による秘密鍵のdownload/importを必須にしない |
| jdu-web-register | 踏み台。Lab専用登録値を対話入力し、指定受付だけへ認証疎通 | GRADING_READYまたは登録/送信待ち |
| jdu-web-check bootstrap | 個人CloudShell→SSMのssm-user経由で踏み台/4台のSSH・配布・基盤・通信をfresh検査し、踏み台から自動送信。現テスト２で受入、学生署名配布は残件 | local結果と送信状態を分離 |
| jdu-web-lab status / diagnose | CloudShell。実resource ID、現在のpublic IP、Stack/SG/phase、無秘密の失敗情報を照合 | 現在の状態と次の操作を表示 |

日常のstop/startではplan/createを再実行せず、同じStackを再開しstatusとpreflightを使う。既存Stackがあるのに新規選定/作成へ進めない。lockの変更セットにEC2/UserData/AMI/AZ/type/rootの変更や置換があれば更新を中止する。UserData変更はEBS EC2を再起動させ得るため、teaching切替に使わない。[CloudFormationの更新仕様](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ec2-instance.html)

wrapperの引数は次を基本にする。秘密は引数にせず、必要時だけ対話入力かroot/本人だけが読めるfileで扱う。

- verify/plan共通: --deployment-manifest FILE --signature FILE --public-key FILE --trusted-fingerprint FINGERPRINT --artifact-root DIR。public-keyは教員の署名公開鍵。fingerprintは教員資料等で独立に確認する。verifyはbundleを含めローカル一式を検証する。
- planの追加引数: --lab-id ID --key-name NAME --public-key-file FILE --output FILE。public-key-fileは学生のSSH公開鍵。出力deployment-plan.jsonは教員manifestのhashと学生入力、selector出力、bundle検証の保留を持つ。既存fileを上書きしない。
- create: --plan FILE --state FILE。実行時に短期搬入URLとRDP passwordを受け、構造化したparameter fileでAWSへ渡す。--stateの既存fileは上書きせず、既存Stackの検出時はstatusへ誘導する。
- lock/status/diagnose: --state FILE。保存account/region/Stack ARNと実resourceを照合する。lockは秘密parameterを含めDeploymentPhase以外にUsePreviousValueを使い、新しいURL/hashを生成してUserDataを変更しない。
- 旧import-keyの--key-file入力は学生向け標準手順から外す。自動受け渡し後は本人権限で秘密鍵から公開鍵を導出して照合し、既存の異なる鍵を無断で置換しない。受け渡しの引数と経路は制作時に確定し、秘密をCLI引数/UserDataへ入れない。
- register/preflight: --config FILE。登録値だけ対話入力し、preflightは通常の検査では設定を変更しない。

stateの初回作成は排他的に行い、以後のphase更新は同じStack ARN/Deployment IDを再照合して一時fileから原子的に更新する。並行実行は同じstate単位のlockで拒否し、失敗時に半分だけ書かれたstateを再利用しない。

## 3 初期化scriptの責務と入出力

| file（制作予定） | 入力 | 実行すること | 実行しない課題作業 |
| --- | --- | --- | --- |
| cloud-initの小さな起動処理 | role、Lab/Deployment/Release ID、初期公開鍵、bundle/hashまたは内部配布先、完了通知URL | 基準OS/toolを確認。検証済み資源を専用dirへ展開しrole scriptを呼び、検査成功後だけ通知 | 外部から未検証scriptを直接shellへ流さない |
| install-common.sh | 検証済みrole設定JSONと収録package台帳 | 操作tool、chrony、署名公開鍵、IP指定APT、checker実行資源、初期化状態記録 | BIND zone・DB/role・アプリvenvの作成をしない |
| install-repo.sh | repoのローカルstageと署名付きmanifest | 手元の.debと全依存からNginxを導入、releaseを配置しread-only配信。共通処理もローカル資源を使う | 稼働前の自分のHTTPへ依存しない |
| install-bastion.sh | 内部repo、RDP hash、共通設定 | 共通処理、Xfce/xrdp/Firefox、DoH無効、RDP用labuser、集約/送信tool | 学生のSSH秘密鍵や採点tokenを共通配布から設定しない |
| install-student-base.sh | role=dns/db/web、内部repo、共通設定 | 共通処理、roleと初期状態の確認 | 対象サービス・完成設定・venv・migration・初期データを導入しない |
| verify-initial-state | role、固定版の検査定義 | 必要tool/版/path/service/配信/未導入条件を検査 | 欠品/誤設定を黙って修正しない |

共通配置は/usr/local/lib/jdu-web/<release>/、公開設定は/etc/jdu-web/bootstrap.json、状態は/var/lib/jdu-web/bootstrap/、logは/var/log/jdu-web/bootstrap.logとする。root管理のJSONをschema検証して読み、入力をshell source/evalとして実行しない。秘密と署名付きURLは別のroot0600の一時fileで渡し、通常log・状態JSONへ出さない。UserData自体に残るRDP hash/短期URLへのアクセスを、NoEchoだけで防いだとは扱わない。

role scriptは--config FILE --stage DIRECTORYを共通の必須引数とし、--check-onlyは変更なしの検査に限定する。configはschema_version=1、lab_id、deployment_id、release_id、role、expected_ubuntu=24.04、architecture=amd64、repo_ip=10.20.2.30、公開鍵fingerprint、期待するscript/package台帳hashを持つ。roleはbastion/repo/dns/db/webの列挙だけを許可し、固定IPとの対応も検査する。未知の項目やOS/role/hashの不一致は実行前に停止する。

RDP hashと一時URLは公開configへ入れず、rootのみ読める別fileを起動処理から該当roleへ渡す。--stageはroot管理の当該Deployment専用dirに解決されることを確認し、任意dirや学生設定領域を再帰削除する手順を作らない。

repoの初回APTでは手元の正確な.deb一覧と依存を使い、外部sourceを無効化してダウンロードなしで導入する。APTの--no-download相当を使い、欠品は失敗にする。--ignore-missingや署名検証無視で準備済みにしない。[APTの導入option](https://manpages.debian.org/bookworm/apt/apt-get.8.en.html)

archiveはSHA256と署名の確認後、空の専用stageへ展開する。Python3.12のdata filter等と、絶対path/..・領域外link・device・展開サイズ上限の検査を使う。検証済みarchiveでも既存の学生dirへ直接上書き展開しない。[Python tarfileの展開条件](https://docs.python.org/3.12/library/tarfile.html)

### 実行順と同時実行

1. repo起動処理がローカルstageを検証し、共通toolとNginxを導入、署名付きAPT/artifactを自己検査する。
2. RepoReadyへDeployment IDに対応した成功を1件通知する。他4台の起動resourceはこの成功を待つ。
3. 他4台がIP指定でmanifest/scriptを取得し検証、common→各roleの処理を実行する。
4. 各台が別のInstance ID/roleで初期状態を検査し、AllNodesReadyへ4件の固有IDで成功を通知する。実IDの対応はwrapperでも照合する。
5. Lab専用鍵の自動受け渡し・公開鍵対応の確認と一時転送の終了→lock→RDP/GUI/実SSH確認→採点登録→開始前確認の順へ進む。既存のS3閉鎖を無断で開き直さない。5件の通知だけでCLASS_READYにはしない。

scriptはumask077、role単位の排他lock、明示した失敗codeを使う。APT/dpkgの他処理を強制終了せず、lock解放を最大600秒待ち、超過は診断対象にする。取得/通知の一時的な障害は最大3回の上限付き再試行とし、RepoReady1800秒/他4台2700秒の全体timeoutを超えない。署名/hash/OS/role不一致は同じ入力で繰り返さない。

## 4 状態と保存する記録

| 状態 | 必須条件 | 学生の授業構築を開始できるか |
| --- | --- | --- |
| PLAN_READY | 配布/入力と選定を検証 | できない |
| BASE_READY | repo1件＋他4件、role別初期状態の検査成功 | できない |
| INFRA_READY | teaching更新成功、AWS実SG/endpointが仕様通り | できない |
| CLASS_READY | 同じDeployment IDのINFRA_READYに加え、RDP/GUI/host確認/SSH/配布/採点認証の成功、初期転送終了と全台の新規S3/不要外部接続拒否を確認 | 開始できる |
| FAILED / WAITING | 設定不一致、確認不能、timeout、未登録、送信待ち等を項目別に表示 | できない |

準備状態、構築課題の合否、結果の送信状態を別の値で管理する。初期段階のBIND/DB/授業Web未導入は予定された開始状態であり、これらが動かないことを初期化失敗にしない。学生が構築を始めた後は初期未導入条件を要求せず、D11の現在状態の検査へ切り替える。

deployment-state.jsonはCloudShell側にaccount/region/Stack ARN、Deployment/Release ID、資源ID、保存済みselection、phase、公開host key、検査結果の参照を持つ。採点token・秘密鍵・RDP hash・署名付きURLは持たない。account/region/Stack ARNが一致しない古いstateは再利用しない。

各hostの状態にはRelease/Deployment/Instance ID、role、完了した処理・時刻・検査IDだけを記録する。成功markerがあっても現物を再検査する。ローカルlog/stateの存在だけでAWSのS3閉鎖や採点受付への保存を成功扱いしない。

検査結果JSONはschema_version、lab_id、deployment_id、release_id、role、instance_id、run_id、checked_at、checksを持つ。checksの各項目はid/status/expected/observed/error_code/next_actionで、statusはPASS/FAIL/UNKNOWN/NOT_APPLICABLEとする。秘密や署名付きURLをexpected/observedへ入れない。過去runのPASSを新しいrunへ混ぜず、UNKNOWN・未登録・送信待ちはCLASS_READYへ昇格させない。

CLASS_READYはそのphase/roleで定義された必須項目が全件PASSの場合だけとする。予定されたサービス未導入等のNOT_APPLICABLEは検査定義で先に指定し、失敗した必須項目を実行時に対象外へ変えない。

終了codeは0=当該command成功、2=入力/schema/版不一致、3=AWS認証/権限/照会の失敗、4=価格/提供条件不足、5=初期化/通知失敗、6=teaching/開始前検査不合格、7=処理中/未登録/送信待ちを基本にする。0はそのcommandの成功だけを意味し、plan/createの0で授業開始可能とは表示しない。

CloudShellが実SG/endpointを確認したcloud reportと、踏み台のlocal reportを同じDeployment IDで対応させる。授業開始時に両方の最新成功を示す。学生のroot権限を持つ端末からの自己申告を改ざん不能にする保証は、この準備検査の要件に含めない。

## 5 SSH鍵と採点登録の初回操作

学生は共有Windowsへ秘密鍵をダウンロードせず、RDP共有drive/clipboardで手動搬入しない。CloudShell→本人踏み台はSSMのssm-userで接続する。内部4台へのSSH鍵はツールが本人踏み台のlabuser内だけで生成・保管し、EICの60秒公開鍵で初回接続して既存authorized_keysを保持した公開鍵追加を行う。秘密鍵directory0700/file0600、許可元10.20.1.10、password fallbackなし・StrictHostKeyChecking=yes。短期公開鍵失効後の4台SSHと5台停止・再開後の同鍵での成功を10/16に受入済み。外部SSH禁止・送信制限を維持し、秘密値を履歴・共通配布物・UserDataへ残さない。CLASS_READYは他の必須項目も全て揃ってから判定する。

4台のSSH host公開鍵/fingerprintはcloud-init consoleとEC2 GetConsoleOutputを使ってInstance ID/private IPへ対応付ける。ssh-keyscanは提示鍵の取得にだけ使い、信頼の根拠はAWS側で照合した公開鍵とする。確認後にknown_hostsへ登録し、StrictHostKeyCheckingを全面無効にしない。consoleが取得できない/対応が確認できない場合は教員がEC2 consoleで確認するまで待つ。[cloud-initの公開鍵console出力](https://docs.cloud-init.io/en/latest/reference/modules.html#keys-to-console)、[EC2 console出力](https://docs.aws.amazon.com/cli/latest/reference/ec2/get-console-output.html)

採点登録は教師が匿名Lab ID専用のtokenを発行し、そのLabの5台/Deployment IDだけへ結び付ける。個人CloudShellのprivate設定からSSM経由で本人踏み台へ自動配置する。SSM履歴には公開sourceとAES-GCM/RSA-OAEPの暗号文だけを渡し、teacher管理keyを踏み台へ渡さない。踏み台設定はroot:root/0600、受付成功後は一時的な復号鍵を終了する。10/16に本人applyで実5台を登録し、既存tokenでverify・踏み台47項目送信・教師保存一致/同一再送まで受入済み。OS/Linux式のWeb専用進捗画面・短い基盤check commandも実装/実受入中。学生向け署名releaseへの入口統合とD11の実課題checkerは残件。点数を加算しないbootstrap種別の結果送信とD11完成課題の採点器は分け、未対応のままGRADING_READY/CLASS_READYを出さない。

## 6 失敗時の分岐

| 観測した失敗 | 自動で行うこと | 停止/再開の条件 |
| --- | --- | --- |
| 対象AZに3サイズが揃わない | AWS資源作成前に次のfamily/AZ候補へ | 価格/性能条件を満たす候補がなければ停止 |
| 明確なInsufficientInstanceCapacity | 失敗pairを記録し、次候補のplanを作る | resourceが一部でも作成済みなら自動削除/別AZ追加を行わず診断へ。整理後の再試行は初回環境に限り通算最大3候補 |
| Unauthorized/AccessDenied | 認証・action・resourceを秘密抜きで記録 | これだけでfamilyの拒否とは断定しない。明示的に確認されたtype制限だけ教員の除外条件へ反映 |
| quota/予算/認証期限切れ | 原因を表示 | 小さいsize/別regionへ自動変更しない。認証更新後も既存資源を照合 |
| AMI/architecture/region/鍵の不一致 | 作成前に停止 | 教員manifestと実値を修正/再照合してから再計画 |
| 署名/hash/資源欠品/ディスク空き不足 | 当該処理を失敗、成功通知を送らない | 別鍵・最新版・外部APTへのfallbackで進めない |
| 初期化/通知timeout | 無秘密のlogと未完roleを表示 | S3通知自体が届かない場合も全件成功にしない |
| teaching更新/通信閉鎖の失敗 | 現在phase/SG/policyを照合 | BASE_READYへ見かけ上戻して成功扱いせず、授業開始を止める |
| 個別鍵/host確認/採点登録失敗 | 個別項目だけ待ち/失敗にする | 5台を再作成せず、必要な操作だけやり直す |
| 既存Stack/state/resourceの不一致 | 通常create/再選定を拒否 | 教員が実状態を確認する。新しいplanを黙って適用しない |

初期化再実行は同じRelease/Deployment/roleで完了処理を検査してから未完部分だけ行う。既存の設定fileが初期化後に編集されている場合は、初期値へ戻さず停止/診断する。異なるrelease、学生構築開始後の再初期化、DB再作成、key/passwordのローテーションを通常再試行に含めない。

## 7 今回の詳細設計と受入の対応

| 追加して確認する条件 | 対応する既存条件 |
| --- | --- |
| bundle→template→外側manifestを循環なく生成、改変を実行前に拒否 | PKG-05/08 |
| 配布前は他4台を初期化せず、repoの導入はローカル資源だけで成立 | PKG-02/03、NET-01 |
| 同じEC2/同じUserDataでlockし、全台成功前と閉鎖前はCLASS_READYにならない | PKG-09/10、NET-02/03、AWS-02 |
| 共通bundleに秘密なし、RDP/key/host確認と個別登録がLabごとに分離 | PKG-01、SVC-07 |
| 学生構築後の再開・誤ったcreate・初期化再試行で設定やDBを消さない | PKG-07/10、AWS-05/06 |
| S3閉鎖をAWS設定と新規通信の両方で確認。BIND未構築でも基盤を判定 | NET-03/08 |
| 採点未登録/送信待ち/別ID応答を準備完了にしない | NET-09、D11の登録/通信受入 |
| 容量/権限/初期化失敗を分け、作成済み資源があれば自動削除しない | AWS-06、selectorの既存plan維持 |

外側manifestのschemaと署名検証/読取りplanまで実装した。次は基準AMI/初期tool・必要権限の実確認、依存収録、最小repo template/install処理、他4台/create/lock/開始前確認の順とする。S3/採点受付の実値とLab権限は同時に確認する。全依存・GUI・登録API・新規配備/停止再開の実機受入が揃うまでD08全体の完了判定は保留する。

## 関連設計

- [D08の収録と配布](2026-10_web_infrastructure_package_distribution_design.md)
- [D09の通信と切替](2026-10_web_infrastructure_network_design.md)
- [D10の資源・費用・運用](2026-10_web_infrastructure_aws_operations_design.md)
- [採点集約と限定送信](2026-10_web_infrastructure_grading_transport_design.md)
- [設計決定一覧](2026-10_web_infrastructure_design_decision_register.md)

公式仕様の確認日: 2026-10-15。Ubuntu24.04の収録版・選定したT系/AMIでの導入とconsole/RDP機能はpilotで確認する。
