# Web単元の保存済みパッケージと初期配備

10/22正式配布追記：**D08初期環境版d08-class193548-20261022-r3を制作・署名し、教師の既存非公開S3へ保存/全GET一致、教師/別学生の実CloudShellでraw/inner署名と全file検証を完了。** v7 coreは全byte不変、個別account/Lab ID/recipientを照合する共通受渡しと教師/学生手順を収録。既存5台/state/tokenは不変。distribution_ready=true、全課題/配点/教材のCLASS_READY=false。10/27 14:24:57 UZT期限。運用は[正式配布README](../tools/web_lab_distribution/README.md)、証跡と次の一手は[検証状況](../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)最上部。以下の「正式配布未完」は追記前の履歴。

10/22受入確定：**D08の候補配布・初期配備について、Class193548の別学生accountでの実受入を合格**。署名v7の実取得・展開前署名・新規5台/96GiB・全1155fileを含む同一payloadの初期展開・AWS29/29・S3閉鎖・全台SSM・内部SSH・専用採点登録・47/47送信を確認した。WEB-02は実9段階13提出と初期packageへの復元、全17提出の教師側保存/受領/最新一致、教師/本人の三言語6ページ、登録後の同じ5台停止再開/SSH・token・作業保持/本人GUIも合格。テスト２で受入済みの完全依存/空cache全role導入/7wheel/WSGIは同じpayload SHAの検証として保持する。**検証済み候補の受入完了であり、正式releaseへの昇格やD11全課題・配点の確定、CLASS_READYを意味しない。** 署名v7の候補表記と期限を変更していない。証跡と次の一手は[検証状況](../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)最上部。以下の未検証/制作予定は当時の記録。

10/20受入更新：テスト２の同じ新5台で候補c5-v6の基盤47/47・AWS29/29、実WEB-02 13件/教師保存、常設全5台SSM・内部SSH・空cache内部repo導入・7wheel/WSGI起動・停止再開/本人GUIが合格。学生が構築するpackageは初期未導入へ復元した。これはv4新規作成後のv5/v6移行を含む候補受入で、v6 cold create/別accountの正式配布は未検証。次は同じClass [193548]で教師teacher@example.invalidと学生student@example.invalidの別AWS環境を使う。署名・期限/価格・配布元・専用認証を再確認し、D08全体/CLASS_READYの保留を解消する。最新証跡/再開手順は[検証状況](../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)冒頭。以下の初期設計時点の未実装記載より、この受入範囲を優先する。

更新: 2026-10-15（Asia/Tashkent）  
対象: D08。教員用の配布設計と制作・受入条件。

学生の起動入口、role別scriptの引数・処理、失敗時の分岐、BASE_READY/INFRA_READY/CLASS_READYの区別は[初期化処理の実装仕様](2026-10_web_infrastructure_bootstrap_contract.md)を正本とする。以下の収録/署名方針を入力に制作する。仕様化と配布可能判定は分ける。

授業用ソフトと依存資源を事前収録し、専用サーバー10.20.2.30から配布する。学生はDNS・DB・Webを自分でインストールして設定し、踏み台と配布サーバーは教員が利用可能な状態で用意する。授業中の外部APT・PyPI・Snapへの取得に依存させない。

初期配備は、ユーザー指示により、公式Ubuntu AMI＋CloudFormationのUserDataから役割別のinstall.shを実行する方式へ変更する。直前の自作AMIを3種類共有する主案は置換する。公式AMIの実IDと配布版・scriptを固定し、初期環境を揃える。完全な依存資源の収録、Learner Labの必要権限・通信、実際の導入試験を終えるまで、D08の配布可能判定は保留する。

## 完了条件と制作物

| D08の完了条件 | 設計内容 | 配布前に揃える制作物・確認 |
| --- | --- | --- |
| OSと本体・全依存の整合 | Ubuntu24.04/amd64を共通にし、下表の直接導入対象と依存一式を収録 | 基準AMI ID、初期package一覧、全.debの版・architecture・hash、空のcacheからの導入記録 |
| browserとアプリ資源 | Mozilla版Firefox、Python3.12用wheel、完成コードと初期化資源を収録 | GUI起動・browser操作、wheelの完全なlock、migration/grantとの整合確認 |
| repo版・署名・保存先 | 版ごとの固定URL、署名付きAPT index、署名付き配布manifest | 公開鍵fingerprint、署名・hash・期限の確認、改変時の拒否 |
| 初期配備方式 | 同じ公式AMIから5台を起動し、UserData＋役割別scriptで準備 | 学生権限でCloudFormationを実行でき、初期化成功・通信制限への切替・Labごとの鍵とIDの分離を確認 |
| DNS等に依存しない導入 | IP指定でAPTと配布物を取得 | DNS/DB/授業Web未完成でも導入・採点準備が成立し、停止・再開後も利用可能 |

本稿は収録方法と主案を定義する。package/AMIの実ID・版・hash・サイズを記入したmanifestと上記試験結果は、実収録で作成する。

制作済みは[外側manifest schema・署名検証/読取りplan](../tools/web_lab_bootstrap/README.md)と既存のT系selector。前者24件・後者9件のlocal試験に合格したが、AWS照会は模擬。教員用verifyはbundleを含め7成果物を検証し、CloudShell用planは小さな6成果物を検証してbundle本体は配布EC2取得後へ保留する。実bundle/署名鍵/AMI実値・template/install処理・依存資源は未制作/未確定であり、配布可能とは扱わない。

## 収録するソフトと学生の作業

| 用途 | 直接導入対象の基本名 | 初期導入と授業中の扱い |
| --- | --- | --- |
| 共通の操作・検査 | openssh-server、openssh-client、python3、curl、ca-certificates、gpgv、nano、iproute2、procps、tar、gzip、xz-utils、chrony、bind9-dnsutils | 教員の初期化scriptで導入。再導入用資源も配布へ収録 |
| GUI踏み台 | xfce4、xrdp、xorgxrdp、FirefoxのMozilla公式DEB、表示に必要なfont | 教員が事前導入。RDP・browser・内部SSHを利用可能にする |
| 内部DNS | bind9、bind9-utils | 学生が保存済みAPTから導入し、zone/転送/client設定を実施 |
| DB | postgresql-16、postgresql-client-16 | 学生が導入し、DB・role・認証・接続制限・配布grantを設定 |
| Web | nginx、python3-venv、python3-pip | 学生が導入。venv作成、配布wheelの導入、アプリ配置・起動・Nginx設定を実施 |
| Pythonアプリ | Django5.2 LTS系、Gunicorn、psycopgとpsycopg-binary、全依存wheel | 教員が版を固定して配布し、学生が専用venvへ導入 |
| 配布サーバー | nginx、保存済みAPT・アプリ・checker・ひな形 | 教員が事前導入し、授業の開始時に稼働 |
| 教員の収録環境 | apt-utils/apt-ftparchive、gnupg、Python依存の解決・収集tool | 教員側だけで使用。署名秘密鍵を学生EC2へ配布しない |

上表は導入対象の指定であり、完全な.deb一覧ではない。依存名・package分割は収録するUbuntu packageで照合する。OSが元から持つPython3と、学生が作るアプリ用venv・アプリ依存を区別する。DNS・DB・Webの初期化ではBINDのdaemon、PostgreSQL、Nginxや完成したアプリ環境を導入して課題を終わらせない。

FirefoxはMozilla版の実体DEBを選び、UbuntuのSnap移行packageとの選択競合を収録設定で防ぐ。font、Xorg、desktop session、browserのsandbox・既定設定もGUIで確認する。FirefoxはOSのDNSを使用し、D06のDoH無効設定を初期提供する。

## 完全な依存資源の収録

教員は本番と同じ基準AMI・architectureの独立した収録環境で、APTのDepends・Pre-Dependsと採用するRecommendsを解決する。代替依存の選択、Ubuntu由来とMozilla由来の優先関係も記録する。Ubuntu全体のmirrorは作らず、授業の導入・限定的な再導入に必要な範囲を保存する。

教師の作業PCに導入済みであることを理由に、依存.debを収録から落とさない。AMIの初期package状態と追加導入の依存を合わせて一覧化し、同じ版を再取得できるよう、対象となる依存の本体も保存する。ダウンロードcacheが空の新規環境で、外部配布先に接続せずに導入できることを確認する。

PythonはUbuntu24.04/amd64・Python3.12で使用できるbinary wheelとpure Python wheelを収録する。Django/Gunicorn/psycopgだけでなく、asgiref、sqlparse、packaging等を含む解決済み依存を全件固定する。実際の一覧は依存resolverの結果を使い、上記の例だけで完全と扱わない。

requirements.lockは全件を厳密な版とSHA256で固定する。外部URL・VCS参照・授業中のsource buildを含めない。学生が取得した資源の署名とhashを確認後、venvでは次の形式で導入する。

```text
pip install --no-index --find-links=<取得済みwheelhouse> --only-binary=:all: --require-hashes -r requirements.lock
pip check
```

venvの作成に必要なUbuntu側のpip/ensurepip資源もAPT依存へ含める。外部へpip自体を更新する手順にはしない。対応wheelがない版は配布前に見直し、学生側で外部ビルド依存を探して取得させない。

## 配布URLと署名

最初の配布版IDを`web-2026-10-r1`とする。これは制作対象の識別子で、公開済みのreleaseではない。配布後は同じIDの内容を差し替えず、変更時はr2以降を作り、影響する教材・採点・AMIも同じ版へ対応させる。

配布元は`http://10.20.2.30/releases/web-2026-10-r1/`。DNS完成後も基本のAPT取得先はIP指定を保つ。保存先は`/srv/jdu-repo/releases/web-2026-10-r1/`とする。

```text
apt/dists/jdu-noble/InRelease
apt/dists/jdu-noble/Release
apt/dists/jdu-noble/Release.gpg
apt/dists/jdu-noble/main/binary-amd64/Packages
apt/dists/jdu-noble/main/binary-amd64/Packages.gz
apt/pool/...
artifacts/app/jdu-catalog.tar.gz
artifacts/python/requirements.lock
artifacts/python/wheelhouse/...
artifacts/checker/checker-bundle.tar.gz
artifacts/bootstrap/...
artifacts/templates/...
manifests/release.json
manifests/deb-packages.csv
manifests/python-packages.csv
manifests/SHA256SUMS
manifests/SHA256SUMS.asc
```

APTのPackagesへamd64とarchitecture=allの対象を収録する。ReleaseのOrigin/LabelはJDU-WebLab、Suite/Codenameはjdu-noble、Componentsはmainとする。apt-ftparchiveでindexとReleaseを作成し、教員のOpenPGP署名を付ける。HTTPで配ることと、署名検証を省略することは別である。

署名鍵はRSA3072以上、digestはSHA256以上を基準とし、公開鍵の有効期間を作成から1年とする。教員の公開鍵はCloudFormationの初期化資源に同梱し、全5台の`/usr/share/keyrings/jdu-web-archive-keyring.gpg`へ配置する。教師の署名秘密鍵は学生EC2・配布物に含めない。鍵のfingerprintは授業の配布manifestにも記録し、未検証のHTTP取得鍵だけで信頼を作り直さない。

他4台のAPT設定は`/etc/apt/sources.list.d/jdu-web.sources`へ初期提供する。

```text
Types: deb
URIs: http://10.20.2.30/releases/web-2026-10-r1/apt/
Suites: jdu-noble
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/jdu-web-archive-keyring.gpg
```

外部Ubuntu/MozillaのAPT sourceは初期化scriptで無効化し、授業中はこのsourceから取得する。trusted=yes、認証なし許可、署名失敗の無視を使わない。期限確認も無効化せず、ReleaseのValid-Untilは署名生成日から180日を基本とする。授業期間を覆うことを配布時に確認し、期限延長が必要なら版と署名metadataを更新して再配布する。

アプリ・wheel・checker等はSHA256SUMSとその教員署名で検証する。manifestだけを改変されても成功しないよう、署名を初期公開鍵で確認してからhashを照合する。Nginxは配布用の読取り配信に限定し、upload・外部取得proxy・署名処理を行わせない。

hashの循環参照は作らない。release.jsonのfile一覧はpayloadを対象にし、台帳作成後にSHA256SUMSを生成する。SHA256SUMSは自身とSHA256SUMS.ascを対象から除外し、そのSHA256SUMSへ署名する。

## 配布manifest

教員が保存するrelease.jsonはソフトの収録manifestとし、次の情報を持たせる。

- 配布版ID、作成日、Ubuntu release、architecture、Python ABI。
- 基準のCanonical公式AMIのowner・region・実ID。授業版ではlatestを随時解決しない。
- 公式AMIの初期package一覧、role別の初期化後一覧、導入対象、全依存の厳密な版・hash・取得元。
- 役割別scriptの版・hash。完成bundle/template/UserDataのhashは外側のdeployment-manifest.jsonへ分ける。
- app/checkerの版・元commit、migration/DB権限manifestの版。
- 全配布fileのpath・bytes・SHA256、公開鍵fingerprint、署名の期限。
- 収録試験の環境・結果、repo容量、AMIとEBSの必要容量。

資格情報は含めない。DB password、SSH秘密鍵、RDP password/hash、採点トークン、Django SECRET_KEYはLabごとに扱う。共有する配布物とLab固有情報を同じarchiveへ混ぜない。

release.json自身のhashはSHA256SUMSへ含め、SUMS自身とその署名は除外する。署名済み資源をbundle化してからbundle hash→template→外側deployment-manifestの順に生成し、循環させない。短期の署名付きURLとLab個別のselection/deployment-stateは、不変の共通manifestへ混ぜない。詳細は上記の初期化仕様に従う。

## 初期配備：CloudFormation＋install.sh

2026-10-15のユーザー指示で、初期化scriptを使って共通の開始状態を作る方針を採用した。5台とも同じCanonical公式Ubuntu24.04/amd64 AMIを使い、教員用の自作AMIは作成・共有の必須条件にしない。CloudFormationがEC2のUserDataを設定し、cloud-initがEC2内でscriptを実行する。[EC2 UserDataの仕様](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html)

UserDataには小さな起動処理と検証用公開鍵・hashだけを含め、大きな配布資源は分離する。raw UserDataの16 KiB制限に収める。初回取得に使うPython3等が選定した公式AMIに存在することも事前確認し、そのtoolを入れるために未稼働repoへ接続する循環を作らない。

| scriptの役割（制作予定） | 対象 | 自動化する開始状態 |
| --- | --- | --- |
| install-common.sh | 全5台 | 基本tool、chrony、署名公開鍵、APT source、採点実行資源・共通設定 |
| install-repo.sh | 専用配布 | 保存済み資源の展開、手元の.debからNginxと依存を導入、署名付き配布を起動 |
| install-bastion.sh | 踏み台 | 共通処理後、内部repoからXfce/xrdp/Firefox・採点集約資源を導入 |
| install-student-base.sh | DNS・DB・Web | 共通処理のみ。BIND/PostgreSQL/Nginxとアプリの導入・設定を学生に残す |

配布サーバーでは、bundle内の.deb・依存を使ってNginxを導入し、共通処理も必要な資源を手元から使う。初回導入で稼働前の自分のHTTPへ依存させない。他4台は配布サーバーの準備成功後に初期化する。script名は責務を示す設計値で、実fileは未作成。

### 初回の資源投入と通信（Codexの具体案）

private側の配布サーバーへ、何も入っていない状態から全資源を渡す経路が必要になる。初期配備専用として、同じregionのS3に教員が事前保存したbundleを置き、S3 gateway endpointで取得する案を採る。S3は搬入元であり、授業中のAPT取得先は専用配布サーバーのままとする。NATや6台目のEC2を追加しない。[S3 gateway endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html)

- public/private両方の必要なroute tableへendpointを関連付け、初期化用SGはそのregionのS3 prefix list宛TCP443だけを追加する。インターネット全体への許可ではない。SGは接続先bucketを区別できないため、endpoint policyも必要な配布bucketと初期化完了通知用bucketへ制限する。
- bundleはprivate S3 objectの有効な署名付きGET URLで取得する案とする。EC2への長期AWS access key配布や、学生による新しいIAM role作成を前提にしない。URL署名元の権限・bucket policy・endpoint policyの全てが取得を許可する必要があり、Learner Labをまたぐ取得も実機で確認する。
- 配布bundleのSHA256をtemplateで固定し、ダウンロード後に検証してから展開・実行する。scriptと全.deb、APT index、アプリ等を同じreleaseへ対応させる。署名検証も行い、取得物を直接shellへ流し込まない。
- URLは初期化時だけ必要。署名元credentialの失効で期限前でも無効になり得るため、配備時間を覆う期限を確認し、初回起動前に更新できる配布手順を用意する。URLやtokenをlog・Outputsへ出さない。[署名付きURLの期限と権限](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)
- 初期化の完了通知にもS3経路を使うWaitCondition案を用いる。endpoint policyは配布bucketだけに絞ると通知を妨げるため、AWS公式の該当regionのCloudFormation通知bucketも対象にする。実bucket名と操作範囲はD09/D10で確定する。

S3搬入・通知と授業前の閉鎖はD09でユーザーが構成を採用した。Learner LabのVPC endpoint作成とCloudFormation権限、署名付き取得の可否は未確認。成立しなければ初回搬入方法を見直し、一般インターネット通信を黙って開けない。

### 配備と授業開始の二段階

1. CloudFormationで既存のVPC/subnet/IP/SG設計と、固定した公式AMIを指定する。初期化専用のS3通信を有効にする。
2. 配布サーバーを起動し、bundleの取得・検証・展開・Nginx起動・IPでの配信確認を実施する。成功通知を受けるまで他4台の導入へ進めない。
3. 他4台を起動し、IP指定の配布先から共通資源と役割別資源を導入する。BINDはまだ未完成でよい。各台で確認に成功した後に、別々のIDで完了通知を送る。
4. CloudFormationのWaitConditionで成功を待つ。EC2作成のDependsOnだけではinstall.shの完了を保証しない。期限超過・失敗通知は配備失敗とし、Stackの作成完了だけを初期化成功の根拠にしない。[WaitConditionとS3経路](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-waitcondition.html)
5. 教員配布手順の次のStack更新で、初期化用SGのS3送信許可を削除し、授業用の制限へ切り替える。初期化用と授業用の切替はSG等の更新で行い、EC2の置換やUserDataの再実行に依存させない。D09の具体案ではendpoint/routeは保持し、授業中はendpoint policyを全拒否へ変更して使用を終了する。
6. 自動準備のBASE_READY、AWS側閉鎖のINFRA_READY、個別鍵/host/GUI/SSH/配布/採点登録と実通信のCLASS_READYを分ける。同じDeployment IDで全条件を確認できた時点で「授業開始可能」とし、DNS・DB・Webの構築を学生が開始する。

配布readyは1件、他4台の完了は4件の固有IDで待つ。DeploymentPhase=bootstrap/teachingはSG/endpoint policyだけを切り替え、WaitConditionHandleと待機resourceはteaching更新でも保持する。UserDataの参照を壊したり新たな待機を発生させたりしない。[D09の通信と切替設計](2026-10_web_infrastructure_network_design.md)を参照。通知resourceの生成順、古い通知の再利用防止、timeout/rollback時のlog取得はtemplate制作時に実装・検証する。初期化中は授業開始可能と表示しない。

### 環境の一致と再実行

公式AMI ID、配布release、template/script、厳密なpackage版を固定する。起動時に最新scriptを取得したり、外部APT/PyPIで最新版へ更新したりしない。同一授業版でroleごとのpackage一覧と設定hashを照合する。IP・Lab ID・鍵・password等の意図した違いは一致条件から除く。

scriptは上限付き再試行、排他、失敗時の終了code、秘密を含めないlogを実装する。準備完了markerは検証成功後にだけ記録し、markerの存在だけで破損を成功扱いにしない。途中失敗後の明示的な再実行で復旧できることを確認する。

UserDataはLinuxでは標準で初回起動時に実行される。通常の停止・再開で初期化を繰り返し、学生の設定やDBを消す方式にはしない。学生作業後の再実行は検査を基本とし、初期化やデータ上書きを無条件に行わない。RDP用labuserのpassword hash・SSH公開鍵はLab固有で渡し、通常アプリのDB password・SECRET_KEYは学生の配置段階で生成する。資格情報を共有bundleへ含めない。

### D10で先に確認すること

学生の実権限で、公式AMIの起動、5 EC2とnetwork資源の作成、CloudFormation、S3 gateway endpoint、bundle取得と完了通知、通信制限へ切り替えるStack更新を一続きで試す。共有自作AMIの起動可否は必須確認項目から外す。実AMI ID・bundle容量・初期化時間・料金と、成功/失敗時の停止・削除手順を残す。

## 教員と学生の分担

教員は収録・署名・CloudFormation template・役割別初期化script・設定ひな形・SQL・採点資源を制作し、公式AMIを選定する。学生が実行する課題対象のinstallをひとつの完成環境構築scriptで代行しない。

学生はAPTでBIND/PostgreSQL/Nginx等を導入し、設定値を編集、DB/role/権限を適用、venvへ依存を導入、アプリを配置・起動する。教員のmodel/migration・認証実装・checker自体は編集しない。Pは完全手順、Mは同じ技能で異なる値とするD11の方針を維持する。

## 配布可能にするための受入

| ID | 試験 | 期待結果 |
| --- | --- | --- |
| PKG-01 | 学生権限で新規起動 | CloudFormation＋固定した公式AMIから5台を初期化でき、Lab固有の鍵・password等が分離される |
| PKG-02 | 初期の導入 | BIND・DB・授業Webが未完成でも、IP指定でAPT update/installとartifacts取得が成功 |
| PKG-03 | 外部取得の除外 | 外部APT/PyPI/Snapへ到達できない条件、空のcacheから全roleの導入が成功 |
| PKG-04 | GUIとPython | RDP・Firefox・内部SSHが動き、専用venvのpip checkとアプリの起動が成功 |
| PKG-05 | 署名・hash | 正常配布は検証成功。別鍵・改変・期限切れの検査fixtureは拒否 |
| PKG-06 | 授業作業の維持 | DNS/DB/Webは学生が導入・設定する。初期AMIで完成済みになっていない |
| PKG-07 | 独立性と再開 | 授業Web停止やDNS設定失敗でも配布が動き、停止・再開後も同じreleaseを取得可能 |
| PKG-08 | 容量と全件照合 | manifestの全fileと版・hash・サイズが一致し、配布側・導入側の必要容量が足りる |
| PKG-09 | 初期化失敗と完了待ち | 欠品・取得失敗・timeoutは配備失敗。全台の検証前に開始可能としない。再試行で秘密を露出しない |
| PKG-10 | 授業用通信への切替 | S3搬入/通知の送信許可を閉じ、既存の授業用許可/拒否が成立。授業開始後の停止・再開で学生設定を上書きしない |

必要な.debが欠ける、初期化が完了しない、初期化専用通信が開いたまま、browserの外部取得が残る、という状態では配布可能にしない。正しい設定の受入記録と、代表的な欠品・署名失敗の検出を揃えてreleaseを固定する。

## 次に進める設計

初期配備はCloudFormation＋script方式へ変更し、D09で全5台の送信/route・初期化専用S3と閉鎖・教員採点先の案を具体化した。D10では公式AMI、bucket/受付等の実値、CloudFormation/endpointの実権限を先行確認する。基準AMIを固定して全依存manifestとscriptを制作し、D08の受入・配布判定へ戻る。template/script制作・AWS適用・実機試験は未実施。

## 一次資料

- [EC2のUserDataと初期化script](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html)
- [S3 gateway endpointと経路・policy](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html)
- [S3署名付きURLの権限と期限](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)
- [CloudFormationのWaitConditionとS3通知](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-waitcondition.html)
- [APT sourceとSigned-By](https://manpages.debian.org/bookworm/apt/sources.list.5.en.html)
- [apt-ftparchive](https://manpages.debian.org/bookworm/apt-utils/apt-ftparchive.1.en.html)
- [APTの署名検証](https://manpages.debian.org/bookworm/apt/apt-secure.8.en.html)
- [pipのhashとwheelによる導入](https://pip.pypa.io/en/stable/topics/secure-installs/)
- [MozillaのFirefox DEB導入](https://support.mozilla.org/en-US/kb/install-firefox-linux)
- [cloud-init clean](https://docs.cloud-init.io/en/latest/reference/cli.html)

確認日: 2026-10-15。APTの参照manualは仕組みの根拠であり、配布時はUbuntu24.04の収録APTで設定を検証する。
