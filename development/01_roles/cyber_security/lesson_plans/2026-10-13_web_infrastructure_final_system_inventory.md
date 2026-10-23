# Web単元の最終システム：設計の棚卸しとパッケージ配布基盤

確認日: 2026-10-13（Asia/Tashkent）  
追記: 2026-10-15、D08の配布設計主案と実収録・AMI検証待ちを反映。  
状態: 5 EC2・公開2台／private3台・課題範囲を確定。ユーザー依頼に基づきIP設計を設定。構築実装・AWS実機への適用と試験は未実施。

10/15の制作状況: [外側manifest schemaと署名検証/読取りplan](../tools/web_lab_bootstrap/README.md)を実装しlocal24試験合格、既存T系selector9試験も合格。AWS応答は模擬で実照会/実配備は未実施。実配布物・create/lock/初期化・実機受入は残る。次は公式AMI/初期tool・必要権限の実確認、依存収録、最小repo template/install処理。

## 1. 今回の指示と確定した追加要件

- 採点・課題の実装より先に、最終的なシステムを詳細に詰めて確定する。
- 今回の課題はWebシステムの構築と正常動作を到達点とし、バックアップと復元は実施・採点対象にしない。以前のbackup/restore要件より今回の指示を優先する。
- 踏み台・Web・DNS・DB・専用パッケージサーバーの5 EC2を採用する。踏み台への配布機能併設案は採用しない。
- 公開subnetに踏み台・Web、private subnetにDNS・DB・パッケージを置く配置をユーザーが了承。下記のIP設計で具体化する。
- 初期状態からUbuntuのパッケージ配布サーバーを用意する。
- 配布方式はユーザー回答により「事前保存して配布」。外部リポジトリを実行時に中継・キャッシュする方式ではない。
- パッケージの事前収集には外部取得が必要だが、学生の授業中の導入は保存済み資源で完結する設計にする。AWS Console、RDP、進捗送信等の外部通信まで全面禁止する要求ではない。
- D04の分担案をユーザーが了承。教員は開始できるAWS資源・踏み台・稼働済みpackage配布・完成アプリコードを用意し、学生は起動と配置確認、DNS/DB/Webの導入・設定・連携を行う。段階ごとの終了条件は設計決定一覧、D05の具体的なソフト・ID・path・起動設定はサービス設計を正本とする。
- D06は既存IP・lab.testの6件のA recordを維持し、踏み台/WebのBIND利用、外部名のAWS DNSへのforward only、初期のIP指定導入、設定/応答/拒否/再起動の受入条件を具体化。最新のユーザー希望に沿い踏み台のInternet新規通信は禁止し、必要な内部送信だけを許可する。
- 後続のユーザー決定で、採点は踏み台のSSH検査・集約＋教員固定受付:443への限定送信を採用。踏み台の外部原則禁止に採点先だけの例外を追加し、HTTPS＋Lab専用トークンを使う。各台の常駐checkerは必須にしない。固定受付の実IP/domain・共通基盤・採点実装はD09/D11の残件。
- D07はDB設計で具体化。catalog_setupがDB/public/tableを所有して初期化し、通常完成後はNOLOGIN・password消去。catalog_appは必要なtable/列単位DMLのみ、Web/32のSCRAM接続、標準data directory・DBルートgp3 16 GiBを設計値とする。DB導入の接続確認と、アプリ連携後の最終DB受入を分ける。
- D08は収録範囲・全依存の解決方法・署名付きAPT・Python wheel・固定URLを具体化。10/15のユーザー指示で、初期配備は公式AMI＋CloudFormation/UserData＋役割別install.shへ変更した。S3 endpointでの初回投入・完了通知と、授業前の送信許可閉鎖は具体案で実機未確認。全依存収録・script/template制作・学生権限の導入受入までD08完了判定は保留。

## 2. どこまでまとまっているか

| 設計項目 | 確認できた内容 | 残り |
| --- | --- | --- |
| 教育目的・主要技術 | Linux/Networkの基礎をWebシステムで使う。Ubuntu、Nginx、BIND 9、PostgreSQL、教員提供アプリ | 到達確認と詳細仕様の対応 |
| 完成構成 | 単一VPC・AZ、公開2台・private3台の5 EC2を採用。IP設計を下記で設定 | 構築実装、費用・権限の実機確認 |
| 通常閲覧 | 学生PC→公開Web→Web側アプリ→private DB | アプリ仕様、起動方式、Web側の転送先port、実データ取得の仕様 |
| 管理 | RDP3389→Ubuntu GUI踏み台→内部SSH22 | GUI選択、接続設定、認証・鍵配布、緊急復旧・代替管理経路 |
| DNS体験 | lab.test、web.lab.test、db.lab.test。踏み台でIP指定→名前指定 | zone設定、resolver設定、forwarding、初期導入時の名前解決 |
| 通信制御 | 役割別SG、内部SSHは踏み台、DBはWebから、HTTP/RDPは許可送信元 | inbound/egressの全通信表、IP/CIDR、初期・完成・復旧時の差分 |
| Web基礎 | WEB-02の説明・練習・課題仕様・確認・再開原稿 | 正式なfile/path、fixture、設定、checker、実機確認 |
| Storage・DB | 基本SQL、role、接続制限、Webからのデータ取得。今回backup/restoreを対象から除外 | 必要なEBS容量・DB保存先、role/table/架空データ。Storage独立課題の扱いは構築範囲の整理時に見直す |
| パッケージ取得 | 現行資料では未確定。今回、事前保存方式を追加 | package/依存関係/版/署名/index、配布方法、初期配備、欠品時の対応 |
| AWS構築・予算 | Learner Lab学生権限で確認する方針 | AMI、instance type、台数、EBS、予算、権限、停止・再開・削除の実測 |
| 採点・進捗 | P/Mの二分類と自動判定を希望。設計案あり | 最終構成に基づく観測点と実装 |

Web教材repoにはcourseとmodules配下のMarkdownがあり、今回確認したローカルツリーにCloudFormation、導入script、教員アプリ、実装されたWeb checker、パッケージ配布資源はない。共通repoには最終構成の図の編集元がある。

`system_requirements/2026-09_cyberlab_*.md`は、名前に2026-09とあるが本文の作成・改訂日は7月で、Proxy・Web1/2・MariaDB・Squid等の旧構成を扱う。現在のBIND 9・公開Web・PostgreSQL・GUI踏み台の詳細設計完成版として扱わない。7/23・8/7のSquid設計も、今回の事前保存リポジトリの実装ではない。過去教材を新教材の制作元としてコピーしない方針は維持する。

## 3. BIND 9・PostgreSQL・Nginx以外に必要なもの

三つは授業の主要サービスだが、最終システム全体には補助機能が必要。全機能に専用EC2が必要という意味ではない。

| 役割 | 必要な機能・配布対象の候補 | 初期状態／学生作業の候補 |
| --- | --- | --- |
| パッケージ配布 | 保存済み.deb、依存package、APT用indexと署名、配布HTTPサーバー、固定したリポジトリ版 | 教員が初期提供。Nginxを配布用途にも利用可能 |
| 踏み台 | OpenSSH client/server、軽量desktop（Xfce等は候補）、xrdp、browser、必要なfont | 管理とDNS体験のため初期提供する案 |
| DNS | bind9、問い合わせ・設定確認用tool | BINDの導入・zone構築・確認を学生が実施 |
| Web | nginx、教員提供の静的file | Nginx導入・配置・設定を学生が実施 |
| DB | postgresql、client、role/SQL用tool、必要な保存領域 | DB導入・接続・権限・架空データを学生が実施。backup/restore課題なし |
| アプリ | 教員アプリ、実行runtime、HTTP実行サーバー、PostgreSQL driver、起動設定 | コードは教員配布。配置・起動・DB接続設定を学生が実施 |
| 共通の操作・観測 | curl、DNS query tool、ip/ss、editor、必要時のtcpdump等 | 使用package一覧と初期導入範囲を確定する |
| 判定・進捗 | 複数EC2の状態確認、AWS構成確認、結果送信、学生/教員ページ | Linux基盤を参考に別途設計。進捗backendは学生システム外の教員基盤 |

パッケージ名の初期候補はnginx、bind9、bind9-utils/bind9-dnsutils、postgresql、postgresql-client、openssh-server、openssh-client、xrdp、desktop、browser、curl、iproute2、editor等。実際の採用Ubuntu/AMIで名前・必要版・依存関係を確認して確定する。

アプリの候補にはPython 3＋Flask＋Gunicorn＋PostgreSQL driverがある。Ubuntu Nobleの公式一覧に関連packageが存在することは確認したが、このアプリ方式を採用したわけではない。APT以外のpip/npmやbrowser配布を使う場合も、必要資源を事前収集して授業中の外部取得を残さない。

最新の選定: 上記Flask候補は置換し、Djangoの標準管理画面を利用する教員制作の備品カタログとする。一般は公開一覧、管理者は踏み台から8080へ接続して登録・編集する。DB登録と一般画面への反映を必須動作とし、学生はアプリコードを書かず接続・起動・Web/DNS設定を行う。[アプリの5点の仕様](../system_requirements/2026-10_web_infrastructure_catalog_app_spec.md)を参照する。実装は未実施。

## 4. 採用した5台構成とIP設計

ユーザーが専用パッケージサーバーを含む5台と、公開2台・private3台の配置を了承した。IPは以下の値を構築仕様に設定する。実AWS資源はまだ作成・変更していない。

| サーバー | 配置 | 公開IPv4 | 主な役割 | 個別SG |
| --- | --- | --- | --- | --- |
| 踏み台 | 公開subnet | あり | 学生PCからRDP接続、各サーバーのSSH管理、内部DNSのブラウザ演習 | SG-Bastion |
| Web | 公開subnet | あり | Nginx＋教員提供アプリ。学生PCへページを返し、DBからデータ取得 | SG-Web |
| DNS | private subnet | なし | BIND 9による内部名の名前解決 | SG-DNS |
| DB | private subnet | なし | PostgreSQLで架空データを保存しWeb側アプリへ返す | SG-DB |
| パッケージ | private subnet | なし | 教員が事前保存した署名済みAPTリポジトリの配布 | SG-Package |

- 公開subnet: 踏み台、授業用Web。
- private subnet: DNS、DB、パッケージサーバー。
- パッケージサーバーは事前準備したNginxと署名済みAPTリポジトリを配備した状態で提供する。
- 各EC2がprivate IPでパッケージサーバーへHTTP取得する。外部へ中継するproxyではない。
- SG-Packageを設け、必要なLab内clientからの配布HTTPと、踏み台からのSSH管理を許可する。
- 課題対象のWebの状態に左右されずパッケージを取得できる。配布用と授業用のNginxは別EC2で動く。
- 追加EC2/EBSの費用とLearner Lab制限を確認する。配布台数・容量・帯域は実測前。

### VPCとサブネットのIP

| 対象 | CIDR | 範囲・用途 |
| --- | --- | --- |
| Web単元専用VPC | 10.20.0.0/16 | 授業用5台のネットワーク |
| 公開subnet | 10.20.1.0/24 | 踏み台・Web |
| private subnet | 10.20.2.0/24 | DNS・DB・パッケージ |

各サーバーのprimary private IPv4をEC2作成時に明示指定する。Ubuntu内で手動の固定IP設定を上書きせず、AWS側で割り当てた固定のprivate IPをDHCPで受け取る。五つのアドレスは相互に重複せず、各subnetのAWS予約アドレス（.0〜.3と.255）を避けている。

### サーバーの内部IPと内部名

| サーバー | 固定private IPv4 | 内部DNS名（lab.testのA record） | 学生PCからの直接接続 |
| --- | --- | --- | --- |
| 踏み台 | 10.20.1.10 | bastion.lab.test | AWS割当の公開IPv4へRDP |
| Web | 10.20.1.20 | web.lab.test | AWS割当の公開IPv4へHTTP |
| DNS | 10.20.2.10 | dns.lab.test | 踏み台経由の管理・演習 |
| DB | 10.20.2.20 | db.lab.test | 踏み台経由の管理 |
| パッケージ | 10.20.2.30 | repo.lab.test | 踏み台経由の管理 |

内部名はBIND 9演習の完成時の仕様。構築初期はまだ存在しないため、SSH・APT等でprivate IPを使う。APTの初期取得先は`http://10.20.2.30/`を基点とし、リポジトリのpathは配布資源の設計時に決める。DNSの実習用問い合わせ先は10.20.2.10。踏み台のbrowserではHTTPを`http://10.20.1.20/`から`http://web.lab.test/`へ切り替える。DB接続はWeb側アプリからdb.lab.testへ行い、10.20.2.20を返す。

### IPの運用とDNS初期状態

- 踏み台・Webの公開IPv4はAWSによる自動割当とし、具体値を教材に固定しない。停止・起動後は最新の公開IPv4を確認する。Elastic IPは今回の基本構成に追加しない。
- private IPは通常の同一EC2/ENIの停止・起動で維持される。削除・再構築時は、古い割当が残っていないことを確認して同じ設計値を指定する。
- 公開subnetのVPC routerは10.20.1.1、private側は10.20.2.1。OSへ独自gatewayを設定せず、AWSのDHCP情報を使う。
- Amazon提供resolverはVPC基点+2の10.20.0.2。授業用BIND 9の10.20.2.10と区別し、BIND構築前に全台のresolverを未稼働の10.20.2.10へ変更しない。
- 学生PCの通常DNSでlab.testを解決できるとは扱わない。内部名の体験は踏み台内、アプリのDB名前解決はWeb内で行う。
- 各学生の独立したLab/VPCでは同じIP表を利用する。学生VPC同士は接続しない。将来VPN・peering等を加える場合はその時点で重複を見直す。
- IP表は完成するM側システムの共通基盤とする。P/Mで変える具体的パラメータは後で決め、各演習ごとに五台の固定IPを無条件に変更しない。

### 主要な通信の配置案

最新の接続元方針: WebのHTTP80は0.0.0.0/0へ公開する。踏み台のRDP3389はUztelecom・ISTTelecomの50 IPv4 CIDRをSGへ直接登録する方式をユーザーが採用。prefix listは使用しない。詳細の現行正本は[ネットワーク設計](../system_requirements/2026-10_web_infrastructure_network_design.md)。AWSへの適用は未実施。

| 送信元 | 宛先 | 通信・目的 |
| --- | --- | --- |
| Uztelecom・ISTTelecomの50 IPv4 CIDRを直接指定 | 踏み台の公開IPv4 | TCP3389 / RDP |
| 0.0.0.0/0（全IPv4） | Webの公開IPv4 | TCP80 / ページ利用 |
| 踏み台 | Web・DNS・DB・パッケージのprivate IP | TCP22 / SSH管理 |
| 踏み台・Web | DNSのprivate IP | UDP/TCP53 / 内部名の解決 |
| 踏み台 | Webのprivate IP | TCP80 / IP指定から内部名指定へのDNS演習 |
| Web側アプリ | DBのprivate IP | TCP5432 / PostgreSQL（portの仕様固定は詳細設計時） |
| 踏み台・Web・DNS・DB | パッケージのprivate IP | TCP80 / 保存済みpackage取得 |

内部の許可元は役割別SGを使う案とする。private三台は学生PCからの直接利用対象にしない。public/privateの同一VPC内通信はprivate IPを使う。DNSの他client、DNS forwarding、採点API、初期配備の追加通信は全通信表で別途決める。

公開subnetはVPC内local経路とIGWへのdefault経路、private subnetは授業中のコア機能についてVPC内local経路を使う案。事前保存のpackage配布はVPC内で完結する。privateサーバーの初期資源投入やAWS API通信の方式は未確定であり、Internetへの直接接続があるとは仮定しない。

5台は学生の実習システムの台数。既存の教員用進捗backendは別の共通基盤として扱う。以前の踏み台併設4台案は、この5台採用決定により検討対象から外した。

## 5. 初期配備で避ける循環依存

1. **最初の配布はIP指定。** BIND構築前でも、package serverのprivate IPでAPTを使えるようにする。後でrepo.lab.test等の内部名を設定することは追加案。
2. **配布サーバー自身は先に完成させる。** 配布用Nginxをインストールするために未稼働の自身のAPTへ依存させない。初期配備済みソフトとリポジトリを教師の配備工程で用意する。
3. **privateサーバーへ配布物を持ち込む経路を確定する。** 初期image、EBS/配布bundle、踏み台経由の転送、許可されたS3等は方式候補。Learner Lab権限と再構築可能性を検証して一つに決める。private EC2で外部apt installできると仮定しない。
4. **公開鍵とAPT sourceも初期提供する。** 署名確認に必要な公開鍵を取得するために、未完成の授業DNSへ依存させない。署名の秘密鍵は教員の作成環境に保持し、学生EC2へ配布しない。
5. **採点・復旧用資源も初期提供する。** DNS/Web/DBのどれかが未完成でも、判定・再インストールへ到達できる配置を設計する。

## 6. 事前保存リポジトリに必要な資源

- BIND 9・PostgreSQL・Nginxの本体に加え、選択した導入方法で必要な依存関係を含める。
- GUI、browser、アプリruntime/driver、確認toolと初期配備に必要な資源も対象にする。backup/restoreのためだけの収録は今回要求しない。
- Ubuntu release、CPU architecture、AMIの初期package、導入オプション、配布版を固定する。Ubuntu 24.04 LTS/amd64は現行教材と揃える候補。実AMIは未決。
- `.deb`の保管だけでなく、APTが読むPackages/indexと署名付きRelease情報を用意する。apt-ftparchiveはPackagesとReleaseの生成に使える。APTの署名とSigned-Byによる鍵指定を使う設計候補（公式参照参照）。
- 上流から取得した資源の確認情報、package名・版・architecture・hashと、生成した授業リポジトリ版を台帳へ残す。必要に応じて元のライセンス・copyright情報も維持する。
- 授業期間中に収録版を無断更新しない。更新が必要なら新しいsnapshotと変更記録を作り、導入・採点・復旧を確認してから切り替える。
- 最小限の収録で開始し、Ubuntu全体のmirrorは基本案にしない。容量の確定は完全な依存一覧の生成後。

ブラウザには注意点がある。Ubuntu 24.04の公式firefox packageはSnapへの移行packageであり、この.debだけを保存してもbrowser本体を収録したことにはならない。MozillaはUbuntu向けの実体DEB配布を公式に提供している。Mozilla版DEBと依存を収録する方式、あるいは事前導入済みimage等を比較し、学生の授業中にSnap Storeへの取得が発生しないことを確認する。

## 7. 配布基盤の受入条件案

1. 採用するAMIの新規環境で、外部APT等のpackage配布先へ到達できない条件を作って確認する（AWS管理・進捗通信を一律遮断しない）。
2. 授業用BIND・Web・DBが未構築でも、IP指定のローカルAPT update/installが成功する。
3. 授業で要求する全roleのpackage、選択した依存関係、browser、アプリを導入・起動できる。
4. 取得結果が事前収録版と一致する。別の外部repositoryへfallbackして成功していない。
5. パッケージ配布・管理・授業用の通信が別々に観測できる。不要な外部公開がない。
6. 停止・再開後も保存したリポジトリが利用でき、設定を戻して再導入できる。
7. 授業用Webを停止／設定失敗にした状態でも、配布と復旧を継続できる。

## 8. 次に確定する順序

以後の議題選択・決める深さ・設計完了の基準は[設計決定一覧](../system_requirements/2026-10_web_infrastructure_design_decision_register.md)を使用する。D03〜D07は仕様具体化済み。D08は[配布設計](../system_requirements/2026-10_web_infrastructure_package_distribution_design.md)をCloudFormation＋install.sh方式へ変更し、収録・制作・受入待ち。D09は[通信設計](../system_requirements/2026-10_web_infrastructure_network_design.md)で全台送信/route・S3閉鎖・採点受付案・NET受入を具体化。実値と実機が残り完了判定は保留。次はD10のAWS実値/権限/費用を確認し、D08の制作/受入へ戻る。以下は当初の整理順の記録であり、現在の進行状況は設計決定一覧を優先する。

1. 採用済みの配置とIP表を基に、SGのinbound/egress全通信とroute tableの設定を具体化する。
2. 完成アプリ: 画面で行う操作、架空データ、runtime、Nginx→アプリ→DBの構成。
3. 初期状態と学生の構築範囲: 先に配るもの、学生が導入・設定するもの。完成Webが動くことを課題の到達点にする。
4. 環境・保存: OS/architecture/AMI、必要なEBSと保存先、認証・秘密、停止・再開。IP/CIDRは上記で設定済み、backup/restoreは対象外。
5. 配布資源: package一覧と完全な依存、APT repo、browserとアプリ資源、初期配備方式。
6. 上記に基づく受入試験とP/Mの仕様・自動判定。

先に最終システムを確定するという今回の指示により、以前の「HTTP P/Mの実装を先行する」提案はこの確定工程の後に置く。

## 9. 調査元

ローカルWeb教材、共通完成図、45コマ採用プラン、7〜9月の日次記録と旧設計書を確認した。GitHubリモート最新版とAWS実資源は今回未確認。

- [現行Web方針](C:/Users/user/Documents/JDU-private/JDU-Web-Infrastructure/COURSE_POLICY.md)
- [WEB-06制作枠](C:/Users/user/Documents/JDU-private/JDU-Web-Infrastructure/modules/WEB-06-app-integration/README.md)
- [共通の構成図編集元](C:/Users/user/Documents/JDU-private/Introduction-CyberSecurity/orientation/system-map.mmd)
- [これまでの整理](2026-10-13_web_infrastructure_status_and_next_steps.md)
- [採点設計案](2026-10-13_web_infrastructure_exercises_and_autograding_design.md)
- [旧基本設計](../system_requirements/2026-09_cyberlab_basic_design.md)（現行構成への適用不可）
- [apt-ftparchive公式manual](https://manpages.debian.org/bookworm/apt-utils/apt-ftparchive.1.en.html)（2026-10-13確認、Packages/Release生成）
- [apt-secure公式manual](https://manpages.debian.org/testing/apt/apt-secure.8.en.html)（2026-10-13確認、署名と鍵指定。実装時は採用APT版のmanualへ照合）
- [Ubuntu Nobleのfirefox](https://packages.ubuntu.com/en/noble/firefox)（2026-10-13確認、Snap移行package）
- [MozillaのLinux導入手順](https://support.mozilla.org/en-US/kb/install-firefox-linux)（2026-10-13確認、公式DEB配布）
- [Ubuntu NobleのPython package一覧](https://packages.ubuntu.com/noble/python/)（2026-10-13確認、アプリruntime関連の候補）
- [AWS Subnet CIDR blocks](https://docs.aws.amazon.com/vpc/latest/userguide/subnet-sizing.html)（2026-10-13確認、予約アドレス）
- [AWS EC2 instance IP addressing](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-instance-addressing.html)（2026-10-13確認、private/public IPv4と停止・起動）
- [AWS Amazon DNS server](https://docs.aws.amazon.com/vpc/latest/userguide/AmazonDNS-concepts.html)（2026-10-13確認、VPC基点+2のresolver）

Ubuntu Nobleの一部manual・個別packageページは本文取得に失敗したため、取得できた公式APT manual・Ubuntuの索引・Mozilla資料で確認した。依存関係の完全な収集と配布容量の算出は未実施。
