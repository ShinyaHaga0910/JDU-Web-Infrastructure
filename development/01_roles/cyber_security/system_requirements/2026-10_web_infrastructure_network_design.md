# Webインフラストラクチャーのネットワーク設計

10/20最終受入：同じ新5台/元rootで署名c5-v6のテスト２候補受入が合格。常設全5台SSM・S3閉鎖・内部SSH/個別採点登録、基盤47/47・AWS29/29・全role/network、実課題13件/教師保存、空cache役割別導入・7wheel/WSGI起動、登録後停止再開/本人GUI/作業保持を確認。学生導入packageは初期状態へ復元済み。v4で新規作成後のv5/v6移行を検証した範囲で、v6 cold CreateStack/別学生accountは未検証。本人指定の別学生Lab [193548]を次に確認する。正式学生配布/D08全体/CLASS_READYは保留。詳細は[最新検証状況](../../../03_knowledge/aws_official/web_lab_ami_2026-10-15/verification_status.md)冒頭。以下の以前の未実装/待ち状態よりこの最終記録を優先。

10/20追加決定：各自のCloudShellから5台すべてへSSMで管理接続する経路を継続する。SSM/ssmmessagesの既存private endpoint2個を共用し、全5台だけが属するBootstrapSgからSsmSg宛のTCP443を許可する。この通信はS3 bootstrap閉鎖後も残す。公開SSHは追加せず、RDPの50 CIDR制限と公開Web80、踏み台だけの固定教師HTTPS、内部4台からの教師直接送信拒否、内部SSH演習を維持する。署名tools c5-v5へ同じ5台/元rootで移行し、閉鎖後のAWS29項目と全5台通信を実確認済み。最新証跡はverification_status.md冒頭。

更新: 2026-10-15（Asia/Tashkent）。現行5台用のD09採用構成。ユーザーが「その構成で問題ないです」と了承。旧CyberLab設計を置換する。既存の配置・公開方針を維持し、全台の送信、初期化専用通信と切替を具体化した。採点受付・S3等の実値、Lab権限・AWS適用・実機検証は残件。

今回の決定範囲は、5台の許可通信、routeと初回搬入、授業用制限への切替、教員採点受付、許可/拒否の確認の5点。CloudFormation＋install.sh、初期化用S3と授業前の閉鎖、教員共通の固定IP受付を含む構成を採用する。以下の設定詳細はその具体化で、実値と実機受入を伴う配布判定は別に残る。

## 配置とIP

VPCは10.20.0.0/16、単一AZ。公開subnet 10.20.1.0/24に踏み台とWeb、private subnet 10.20.2.0/24にDNS・DB・専用パッケージサーバーを置く。課題はWeb構築と正常動作を到達点とし、backup/restoreは対象外。

| 役割 | primary private IPv4 | 内部名 | 個別SG | 公開IPv4 |
| --- | --- | --- | --- | --- |
| 踏み台 | 10.20.1.10 | bastion.lab.test | SG-Bastion | AWS自動割当 |
| Web | 10.20.1.20 | web.lab.test | SG-Web | AWS自動割当 |
| DNS | 10.20.2.10 | dns.lab.test | SG-DNS | なし |
| DB | 10.20.2.20 | db.lab.test | SG-DB | なし |
| パッケージ | 10.20.2.30 | repo.lab.test | SG-Package | なし |

IPはEC2作成時に指定し、OSのDHCP設定を保つ。BIND完成前のpackage取得は10.20.2.30を直接指定。学生PCはWebと踏み台の最新の公開IPv4を使い、内部名は踏み台／Web内で使用する。

管理者入口の内部名としてadmin.lab.testも10.20.1.20を返すA recordに追加する。同じWeb EC2上に一般Nginx80と管理Nginx8080を配置する。アプリの仕様は[備品カタログ仕様](2026-10_web_infrastructure_catalog_app_spec.md)。

## routeとAWS基盤

| route table | 関連付けるsubnet | 両段階で維持するroute | 初期化専用 |
| --- | --- | --- | --- |
| RT-Public | 10.20.1.0/24 | 10.20.0.0/16→local、0.0.0.0/0→Internet Gateway | 同一regionのS3 prefix list→S3 gateway endpoint |
| RT-Private | 10.20.2.0/24 | 10.20.0.0/16→local。default routeは作らない | 同一regionのS3 prefix list→S3 gateway endpoint |

S3 endpointのroute自体は両段階で保持し、授業中はendpoint policyの全拒否と初期化用SGの送信許可削除で閉鎖する。endpointの削除・再作成を通常の切替へ含めず、EC2を置換せずに切り替える。初期化用policyとrouteの存在だけを授業中の許可とは解釈しない。endpointはLabのStack削除時に終了する。

NAT Gateway・NAT instance・踏み台のNAT化・VPC peering・IPv6・追加のCloudFormation interface endpointは基本構成に入れない。公開2台のIGW routeは一般Web/RDPの応答と採点送信に必要なので、送信制限の代わりに削除しない。

VPCのenableDnsSupport/enableDnsHostnamesを有効にし、初期化中は全台がAWS DNSを使用する。BIND完成後に踏み台/WebをBINDへ切り替える既存D06を維持する。subnetのNACLは既定の許可構成を使い、今回の接続制限はSGとservice設定で行う。新規のICMP許可は設けず、pingを合格の必須条件にしない。

## 外部接続の方針

- WebのHTTP80は0.0.0.0/0から許可する。架空データを使う授業用公開Webとして、IP制限は設けない。
- WebのSSH22は踏み台だけから許可する。HTTPの一般公開を管理portへ拡張しない。
- 踏み台のRDP3389はUztelecom・ISTTelecomの調査済みIPv4範囲へ限定する。
- ユーザーの最新決定により、RDP許可元の50 CIDRをSG-Bastionへ直接登録する方式を採用。RDPではprefix list、WAF、ASNを直接条件とする制御は使用しない。初期化用S3のAWS管理prefix listは別用途である。ASNはIP範囲の調査・再取得の根拠として保持する。
- 現時点の許可範囲はUztelecom34件、ISTTelecom16件、合計50件。構築・配布前に再取得し、Learner LabのSG変更権限とquotaを確認する。AWS用設定データは`03_knowledge/network/2026-10-13_isp_rdp_allowlist/rdp_ingress_ip_permissions.json`。
- 最新決定により、踏み台からInternetへの新規通信は原則禁止とし、教員の固定採点受付IP:443だけを例外許可する。内部の必要な送信と合わせて下表で許可する。許可済みRDPへの応答は維持し、AWS基盤サービスの通信とは区別する。

## 受信の許可表

内部通信は表のIPを教員・学生の説明用とし、AWS側の接続元には対応するSGを参照する。/32を使う必要がある箇所では各表記IPへ/32を付ける。全VPCや全subnetを一括許可する方式にしない。

| 宛先 | 許可する接続元 | protocol/port | 用途 |
| --- | --- | --- | --- |
| 踏み台10.20.1.10 | Uztelecom・ISTTelecomの50 IPv4 CIDRを直接指定 | TCP3389 | RDP管理 |
| Web10.20.1.20 | 0.0.0.0/0 | TCP80 | 一般Web閲覧 |
| Web10.20.1.20 | 踏み台10.20.1.10 / SG-Bastion | TCP22 | SSH管理 |
| Web10.20.1.20 | 踏み台10.20.1.10 / SG-Bastion | TCP80 | private IP・内部名でのDNS演習 |
| Web10.20.1.20 | 踏み台10.20.1.10 / SG-Bastion | TCP8080 | 内部の管理者入口 |
| DNS10.20.2.10 | 踏み台10.20.1.10 / SG-Bastion | TCP22 | SSH管理 |
| DNS10.20.2.10 | 踏み台10.20.1.10、Web10.20.1.20 / 各SG | UDP53とTCP53 | 内部名解決 |
| DB10.20.2.20 | 踏み台10.20.1.10 / SG-Bastion | TCP22 | SSH管理 |
| DB10.20.2.20 | Web10.20.1.20 / SG-Web | TCP5432 | アプリのDB接続 |
| パッケージ10.20.2.30 | 踏み台10.20.1.10 / SG-Bastion | TCP22 | SSH管理 |
| パッケージ10.20.2.30 | 踏み台10.20.1.10、Web10.20.1.20、DNS10.20.2.10、DB10.20.2.20 / 各SG | TCP80 | 保存済みAPT資源取得 |

WebのHTTP80が0.0.0.0/0から許可されているため、踏み台のHTTP80も既に到達可能。上表の演習行は用途の説明であり、同じportへSG-Bastionを追加する重複ruleは必須ではない。

DBのTCP5432は踏み台から直接は許可しない。DBの管理は踏み台からDBへSSHし、そのDB内でpsqlを使う。Django/GunicornはWeb EC2内の127.0.0.1:8000だけで起動し、Nginxから転送する。TCP8000を外へ公開するruleは追加しない。一般80経由の/adminと配下は拒否し、管理者は踏み台内browserのhttp://admin.lab.test:8080/admin/を使う。管理8080のprivate IP待受だけで外部非公開になるとは扱わず、SG-Bastionだけの許可と経路制限を実機確認する。

## 踏み台の送信許可と外部接続

SG-Bastionの初期値である0.0.0.0/0への全送信許可を削除し、下表だけを許可する。他のSGを付けて全送信許可が合成されないことも確認する。IPv6を使用しない現行構成で、::/0の送信許可を残さない。

| 踏み台の送信先 | protocol/port | 用途 |
| --- | --- | --- |
| SG-Web / 10.20.1.20 | TCP22 | SSH管理 |
| SG-DNS / 10.20.2.10 | TCP22 | SSH管理 |
| SG-DB / 10.20.2.20 | TCP22 | SSH管理 |
| SG-Package / 10.20.2.30 | TCP22 | SSH管理 |
| SG-DNS / 10.20.2.10 | UDP53、TCP53 | 授業BINDへの問い合わせ |
| SG-Web / 10.20.1.20 | TCP80、TCP8080 | 内部の一般・管理画面 |
| SG-Package / 10.20.2.30 | TCP80 | 保存済みAPT・配布資源取得 |
| 教員の固定採点受付IPv4/32（未取得。D10で実値を取得） | TCP443 | 採点結果送信。HTTPS＋Lab専用トークン |

SGを宛先に指定するruleはprivate IPで通信する。踏み台からWebの公開IPv4を開くのではなく、10.20.1.20またはweb/admin.lab.testを利用する。

教員の採点受付以外の外部サイト・外部APT/pip/Snap等への新規接続は踏み台では許可しない。採点受付は固定IP・HTTPSで接続しLab専用トークンを検証する。固定IPの実値は未確定であり、上表の例外はAWSへの実適用済みruleではない。AWS Consoleは学生PC側で操作する。RDPの応答は送信ruleに関係なく許可されるため、返信用0.0.0.0/0のruleは追加しない。外部RDPを維持する公開IP・IGW routeは削除しない。

AWS DNS/DHCP/metadata/Time Sync等はSGでは遮断できないため、SGで完全な無通信を保証したとは扱わない。時刻同期は169.254.169.123のAmazon Time Sync、通常のDNSはBINDを使用する。

受入条件は、内部SSH・DNS・Web80/8080・APT・許可回線からの新規RDP・教員採点受付への認証付き送信が成功し、採点受付以外への新規の外部HTTP/HTTPS接続が失敗すること。SG設定と、正常稼働を確認済みの教員管理の試験先への実通信を合わせて判定する。実機試験は未実施。

## 授業中の他4台の送信

| 送信元 | SGで追加する宛先 | protocol/port | 用途 |
| --- | --- | --- | --- |
| Web | SG-DNS | UDP53、TCP53 | db.lab.test等の内部名解決 |
| Web | SG-DB | TCP5432 | Django→PostgreSQL |
| Web | SG-Package | TCP80 | APT・app・wheel・checker取得 |
| DNS | SG-Package | TCP80 | BIND等の保存済み資源取得 |
| DB | SG-Package | TCP80 | PostgreSQL等の保存済み資源取得 |
| パッケージ | 他hostへの新規の通常通信は許可しない | — | 自身の収録資源を配信し、SSHとHTTPの許可済み受信へ応答 |

WebもInternetへの新規HTTP/HTTPSを許可しない。公開80の応答、DBやAPTへの応答はstatefulなSGで維持される。他4台から踏み台や採点受付への新規通信は不要で、採点結果は踏み台が開始したSSH接続の応答として戻す。

DNSの外部名はAWS DNS 10.20.0.2へTCP/UDP53でforward onlyとする。これはAWS resolver通信のためSGの通常送信ruleでは遮断できない。Amazon Time Sync 169.254.169.123:UDP123、DHCP、metadataも同様に基盤通信として区別する。通常resolverの設定とDNS採点はD06に従い、SGだけでAWS DNSへの迂回を禁止したとは扱わない。

### CloudFormationで送信全許可を残さない

AWS::EC2::SecurityGroupは、作成時にegressを省略すると全送信許可が追加される。全6個の論理SG（役割別5個＋初期化用1個）は、作成時のinline egressにlocalhost 127.0.0.1/32・protocol=-1を明記し、既定の全送信を作らせない。これはAWS公式例に従う無外部送信の基準設定であり、実通信に必要なruleは下記の独立resourceで追加する。[CloudFormationの既定egressとlocalhost指定](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ec2-securitygroup.html)

SG同士を参照する受信/送信はAWS::EC2::SecurityGroupIngress/Egressの独立resourceで定義して循環依存を避ける。EC2は必要なrule・route・endpoint policyの作成後に起動する。SG-Packageも既定SGも外部全送信を持たず、追加SGの許可が合成されていないことを実際のENIで確認する。SGの表示名は論理ラベルとし、AWSのGroupNameは自動生成を基本にする。

## 初期化中だけのS3通信

初期化用SG-Bootstrapを全5台へ役割別SGと併用する。このSGは受信許可なし、初期化中だけ同一regionのS3 prefix list宛TCP443を許可する。初期化中もInternet全体へのHTTP/HTTPSは許可しない。

S3 gateway endpointを両route tableへ関連付ける。SGはbucketやURL pathを識別できないため、endpoint policyを次の範囲に限定する。S3 prefix list名はcom.amazonaws.${Region}.s3、実IDはD10でregionに対応した値を取得する。

| 用途 | 送信元と宛先 | endpoint policyの許可 | 条件 |
| --- | --- | --- | --- |
| 初回搬入 | 配布10.20.2.30→教員の配布bucket | s3:GetObject、固定release prefixのobject ARNだけ | aws:VpcSourceIp=10.20.2.30/32、署名付きGET URLも有効であること |
| 配布ready通知 | 配布10.20.2.30→CloudFormation通知bucket | s3:PutObject | 該当StackのWaitConditionHandleが発行する署名付きURLを使用 |
| 他4台の初期化完了通知 | 他4台→同じ通知bucket | s3:PutObject | 各台を別のUniqueIdで通知 |

通知bucketのARNはarn:aws:s3:::cloudformation-waitcondition-${Region}/*とする。endpoint policyの通知許可は5台のprivate IPv4だけへ制限し、List/Delete/Getは追加しない。ARN・署名付きURLのhost/region・実際に必要な操作をD10で照合する。配布bucketの実名は未確定。endpoint policyの許可だけでS3 objectを公開せず、bucket policy・署名元の権限も別に満たす。

AWS公式はWaitCondition応答に上記のCloudFormation専用S3 bucketへの到達を要求している。[通知bucketの仕様](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/vpc-interface-endpoints.html)

他4台のscript・基本tool・GUIは内部HTTP10.20.2.30から署名/hashを検証して導入する。初回の配布サーバーはS3 bundle内の.deb・scriptを手元から導入する。公式AMIに必要な最小取得toolがあること、S3資源・全依存が同じ版であることはD08/D10の確認条件。外部APT/PyPI/GitHub、初回用の広い0.0.0.0/0:443、NATを代替として自動追加しない。

## 初期化から授業への切替

templateの配備段階parameterはDeploymentPhase=bootstrap/teachingを設計値とする。この値は初期化用の送信ruleとendpoint policyだけを切り替え、AMI/UserData/EC2やWaitConditionHandleの識別子を変更しない。初期化後はtemplateのhashと他parameterを維持して段階だけを更新する。更新前の変更セットでEC2の置換がないことを確認する。

| 段階 | 実行担当 | 成功条件・失敗時の扱い |
| --- | --- | --- |
| bootstrap開始 | 学生が教員配布templateを起動 | 教員が事前確認した公式AMI・release・入力値を使用。初期化用S3通信あり。授業開始可能とは表示しない |
| 配布サーバー準備 | 配布EC2のscript | bundle検証・Nginx起動・IP指定の署名付きrepo配信を確認してRepoReadyへ1件通知。失敗/timeoutなら他4台を準備済みにしない |
| 他4台準備 | CloudFormationと各台script | RepoReadyの成功後に他4台を起動。内部配布から導入し、4件の固有IDの成功をAllNodesReadyで待つ。DependsOnだけでscript完了とはしない |
| 授業用制限へ更新 | 学生が教員手順に従いStack更新 | 5台成功とlogを確認し、DeploymentPhaseだけをteachingへ変更。S3向けegress resourceを削除し、endpoint policyを全action/resource明示Denyへ変更 |
| 開始前確認 | 踏み台の教員提供検査＋学生のAWS確認 | 初期化process・S3転送が終了していること、ENIのSG/endpoint設定、新規S3通信の拒否、RDP/SSH/APT/採点の成立を確認。失敗時は学生の構築を開始しない |
| 授業中 | 学生 | DNS/DB/Webを導入設定する。通常の停止・再開ではUserDataを再実行せず、teachingの制限を維持 |

WaitConditionとHandleはteaching更新でも保持し、初期化の新たな待機を発生させない。通常更新で古い通知を新しい成功に流用しない。再初期化が必要なら新しい初期化世代のHandle/待機設計か新規Stackを用意し、元の学生環境を無断で削除・リセットしない。rollbackでbootstrapへ戻った場合も授業開始可能にせず、実際のruleを再確認する。

SG変更だけでは既存の追跡済み接続が直ちに切れない場合があるため、初期化転送を終了させて新規接続で拒否を確認する。既存接続が残ったまま「閉鎖済み」としない。[SGのconnection tracking](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-connection-tracking.html)

初期化失敗は成功通知を送らず、失敗理由をtoken/URL抜きで残す。S3経路自体の障害で失敗通知も届かない場合は待機のtimeoutで検出する。診断logはcloud-initとローカルlogを基本とし、CloudWatch/S3 log転送を恒常経路として追加しない。Stack失敗時のlog保存とrollback運用はD10で実権限と合わせて固定する。

## 教員の固定採点受付

### 2026-10-15の具体化

ユーザーは独自domainを持たず、AWS発行のdomainを使うと回答した。教師用と学生用を別Stackにし、教師が先に起動して各学生の認証情報を発行する。テスト２で教師専用 `jdu-web-progress-2026` を配備し、受付IPv4 `44.216.176.215`、HTTPS名 `7eg7nm5oe2.execute-api.us-east-1.amazonaws.com` を得た。学生向けSGへの実適用は未実施。

教師EC2はNginx streamのSNI制限付きTLS中継を行う。許可するSNIと上流はこのAWS API名のみ。TLSはAPI Gatewayまで終端せず、送信clientは接続IPv4だけを固定し、AWS API名でCA/hostnameを検証する。独自domain・教師EC2上の独自証明書は不要となり、以下の以前の「教員保有の実domain」案を置換する。通常DNSや学生のDNS課題設定は変更しない。

受付/backendは既存Linuxから独立したWeb専用API Gateway/Lambda/DynamoDBを使用する。Lab専用token、release/Deployment/5 Instance IDの結付け、同一requestの再送、誤tokenや別配備の拒否、教師・学生の画面応答を含む実APIの10ケースに合格した。架空Instance IDによるAPI試験であり、学生5台・通信制限・授業受入とは区別する。Academy環境での検証用配備で、本番教師環境の常設・別account疎通は未確認。

運用と安全な認証情報の保存先は [教師用受付README](../tools/web_lab_teacher/README.md)、結果は `03_knowledge/aws_official/web_lab_teacher_2026-10-15/`。以下は上記の更新点以外の既存設計を保持する。

今回の具体案は、教員が所有する共通AWS環境のEC2にEIPを1個割り当て、NginxのHTTPS443で採点の固定入口を用意する方式とする。全学生で共用し、各学生の実習EC2は5台のまま。既存Linux採点APIの前に固定上流の中継を設け、Web課題へのAPI対応はD11で実装する。

| 項目 | 設計 |
| --- | --- |
| 学生側の許可 | SG-Bastion→GradingIngressIpv4/32・TCP443のみ。実IP未確定のまま代替の全443許可を作らない |
| HTTPS | 教員保有の実domainと有効なCA証明書を使用。URLのhostname・CA検証を維持し、学生のWeb証明書課題は追加しない |
| APIの公開範囲 | POST /api/web/submit、必要最小限のGET /healthzを設計値とする。他path/method、CONNECT、任意上流・redirectは許可しない。正式API対応はD11 |
| 上流 | 教員が設定した採点APIのURLだけ。Bearer tokenを転送し、受付/backendでLab IDとの対応を検証。clientが上流を指定できるproxyにしない |
| DNSが未完成の場合 | 採点送信処理だけでFQDN:443→固定IPv4を明示する。curlの--resolve相当を使いhostname検証を維持。通常DNS・/etc/hostsを置き換えず、DNS採点は別に実施 |
| 送信失敗 | ローカル採点結果と未送信状態を保持。受付停止/認証/TLS失敗を課題合格・送信成功にしない。再送ID・重複処理はD11 |

教員側443は学生の公開IPが変わるため送信元固定を前提にしない。管理経路は別の教員管理用許可へ限定し、学生向けにSSHを公開しない。証明書取得/更新・上流接続・OS更新の通信と費用は教員共通基盤側のD10へ持ち、学生5台のsg/routeへ混ぜない。

GradingIngressIpv4、GradingFqdn、BootstrapBucket/ReleasePrefix、region別S3PrefixListIdをtemplate/配布manifestの入力にする。実IP・domain・bucket等は未取得であり、例示IPでAWS適用や送信を成功扱いにしない。API Gatewayの一時的なDNS回答を固定受付IPとして使わない。受付変更時はmanifestと許可IPを同じ配布版で更新し、黙って宛先を広げない。

## 許可と拒否の受入

授業開始前の基盤検査と、学生がサービスを構築した後の完成検査を分ける。BIND/DB/アプリが未構築である段階の接続失敗を、SGの拒否確認や正常完成として扱わない。

| ID | 段階と確認 | 期待結果 |
| --- | --- | --- |
| NET-01 | 新規bootstrap、DNS未構築 | repoがS3から検証済みbundleを取得し、他4台はIP指定の内部APTから準備。5台の完了待ちが成立 |
| NET-02 | 初期化の欠品・期限切れURL・通知障害 | 失敗またはtimeoutとなり、成功件数を満たさず授業を開始しない |
| NET-03 | teaching更新と設定確認 | EC2を置換せず、default全送信/IPv6送信許可なし。S3egressなし、endpoint policy全拒否。bootstrap転送終了後、有効期限内のURLを使った新規S3取得/通知を拒否 |
| NET-04 | 授業前の管理・配布 | 許可回線から新規RDP、踏み台→4台のSSH、他4台→repo80が成功。未許可回線からの新規RDPと外部SSHを拒否 |
| NET-05 | 授業中の外部送信 | 踏み台から認証済みの採点送信が成功。全5台から別の稼働確認済み外部HTTP/HTTPS先への新規接続を拒否。Web等から採点受付への新規接続も拒否 |
| NET-06 | 学生構築後のDNS/DB | 踏み台/Web→BINDのTCP/UDP53、Web→DB5432が成功。踏み台等から直接DB5432の接続を拒否 |
| NET-07 | 学生構築後の一般/管理入口 | 外部PC→公開80の一般閲覧が成功し/admin配下を拒否。踏み台→private Web8080の管理が成功し、外部→8080/8000/DB/DNSを拒否 |
| NET-08 | 採点だけの名前解決補助 | BIND停止でも必要な基盤採点結果を送信可能。DNS構築チェック自体は不合格/確認不能となり、補助経路で隠さない |
| NET-09 | 認証/TLS/採点受付の障害 | 誤token/他Lab ID/不正証明書/受付停止で送信を成功扱いしない。ローカル結果と送信待ちが区別される |
| NET-10 | 停止・再開 | public IPv4変更を確認して再接続。private IP/release/学生設定を保持、teachingとS3閉鎖を維持 |

拒否試験は同じ確認回で正規接続先の正常稼働も確認し、timeoutだけでfirewallの効果を断定しない。SG・route・endpoint policyの実設定と実通信を合わせて判定する。D11では課題ごとの前提を毎回再確認するため、以前の合格だけで後続の動作を保証しない。

## AWSの仕様と残件

- SGは許可した接続の応答を自動許可するため、返信用の広い受信port範囲を追加しない。
- TCP3389の50 CIDRはIPv4 inboundの50 rule枠を使う。一般AWSの既定60以内だが、Learner Labの実quotaと変更権限は未確認。件数増加時は再確認する。
- Amazon resolver 10.20.0.2はBINDの10.20.2.10と別。Amazon resolverへの通信をSGで遮断できるとは扱わない。
- 今回のD09では全5台の送信/route、初期化用S3と授業用制限への切替、教員のEIP付きHTTPS受付案、受入表を一組にした。OS側は既存D05/D06/D07の待受・認証・公開path制限を適用し、追加UFW/NACL構築は学生の必須課題にしない。初期化時に必要な接続を妨げるhost firewallがないことはD08で検証する。
- 現在の生徒回線でのRDP許可・禁止と、Web一般公開・privateサービスの非公開を実機で確認する。過去のJDU出口IP二つの包含は確認済みだが、現在の実回線テストは未実施。

### 未確定の実値と次の確認

| 残件 | 担当・対応先 | 完了条件 |
| --- | --- | --- |
| region/AZ・S3 prefix list実ID・公式AMI | 教員/Codex、D10 | 学生Labで利用可能な実値を記録 |
| 配布bucket・署名付きGET・待機通知 | 教員/Codex、D08/D10 | 別accountのLabから取得/通知でき、teaching切替後は拒否 |
| 固定採点受付のIP/domain・証明書・上流 | 教員/Codex、D10/D11 | 教員共通環境で受付を用意し、実値をmanifestに固定。正しいLabだけ保存可能 |
| CloudFormation/endpoint/SG・quota | 教員/Codex、D10 | 学生実権限で初期化→teaching更新、RDP50 CIDRと各ENIのSGが成立 |
| template/script・資源の全件収録 | 教員/Codex、D08 | 本表の入力・待機・切替を実装し、PKG/NET受入を記録 |

D09の構成はユーザー採用済み、実値確定・AWS適用・実機受入は未完了。[D10のAWS資源と運用](2026-10_web_infrastructure_aws_operations_design.md)でregion/type/容量/費用/運用案を具体化し、実権限と配布入力の確認、D08制作へ進む。構成の採用、実装済み・動作保証済みは区別して管理する。

## 参照

- [最終システムの設計メモ](../lesson_plans/2026-10-13_web_infrastructure_final_system_inventory.md)
- [サービスと接続設定](2026-10_web_infrastructure_service_design.md)
- [内部DNS設計と完了条件](2026-10_web_infrastructure_dns_design.md)
- [初期配備とパッケージ配布](2026-10_web_infrastructure_package_distribution_design.md)
- [採点の踏み台集約と限定送信](2026-10_web_infrastructure_grading_transport_design.md)
- [事業者・ASN・全CIDR・検証記録](../../../03_knowledge/network/2026-10-13_isp_rdp_allowlist/README.md)
- [AWS Security Group rule](https://docs.aws.amazon.com/vpc/latest/userguide/security-group-rules.html)
- [AWS SGのstatefulと制御対象外通信](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html)
- [AWS managed prefix lists](https://docs.aws.amazon.com/vpc/latest/userguide/managed-prefix-lists.html)
- [S3 gateway endpointの経路・policy](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html)
- [CloudFormationのSGと既定egress](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ec2-securitygroup.html)
- [WaitCondition](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-waitcondition.html)
- [CloudFormation通知用S3 bucket](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/vpc-interface-endpoints.html)
- [接続追跡とSG変更](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-connection-tracking.html)
- [EIPの仕様](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/elastic-ip-addresses-eip.html)
- [curlのresolve](https://curl.se/docs/manpage.html#--resolve)
- [AWS WAF ASN Match](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-asn-match.html)

公式仕様の確認日: 2026-10-15（SG/CloudFormation/S3/WaitCondition/接続追跡/EIP/curl）。RDP用の事業者CIDRは2026-10-13取得のため、配布前に更新確認する。
