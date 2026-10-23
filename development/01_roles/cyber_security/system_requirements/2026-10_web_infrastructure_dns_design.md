# Web単元：内部DNS設計と完了条件

更新: 2026-10-13（Asia/Tashkent）  
対象: D06。既存IP・内部名を維持し、問い合わせclient・resolver・外部名・初期導入を具体化する。  
状態: ユーザーの設計依頼に基づく仕様。実装・学生権限のAWS実機受入は未実施。

## 1. 完了条件との対応

| D06の設計完了条件 | 今回定義した内容 |
| --- | --- |
| zone/record | lab.test、下表のA record、SOA/NS、配置file、更新方法 |
| 問い合わせclient | 踏み台とWeb。DNS内のlocalhostは管理・自己確認用 |
| resolver設定 | BIND完成後に踏み台・Webの通常DNSを10.20.2.10へ変更。IP/gatewayはDHCPのまま |
| 外部名の扱い | BINDがAWS標準DNS 10.20.0.2へforward only。Internetのroot/public DNSへの直接問い合わせなし |
| DNS構築前の導入経路 | 配布APT・アプリ資源・SSHはprivate IP指定で利用。稼働前のBINDへ全台を切り替えない |

以上でD06の設計仕様を一組にする。下記の受入条件は実装後に確認するものであり、設計記録だけで実機PASSとは扱わない。

## 2. zoneと登録する名前

DNS EC2は10.20.2.10。zoneは`lab.test.`、primaryのNSは`dns.lab.test.`とする。既存の名前とIPを変更しない。

| A recordの名前 | IPv4 | 用途 |
| --- | --- | --- |
| bastion.lab.test. | 10.20.1.10 | 踏み台 |
| web.lab.test. | 10.20.1.20 | 一般入口 |
| admin.lab.test. | 10.20.1.20 | 管理入口。同じWeb EC2の8080 |
| dns.lab.test. | 10.20.2.10 | BIND |
| db.lab.test. | 10.20.2.20 | PostgreSQL |
| repo.lab.test. | 10.20.2.30 | 保存済み資源の配布 |

SOAのprimaryはdns.lab.test.、管理連絡名はhostmaster.lab.test.とする。メールサーバーや実アドレスの登録を意味しない。初期serialの基本値は2026101301、変更時に増やす。TTLは300秒、SOAのrefresh 3600・retry 600・expire 604800・negative TTL 300秒を基本値とする。

今回はA・NS・SOAによる正引きを必須とする。逆引きzone/PTR、secondary DNS、公開ドメインの委任、DNSSEC署名は追加の必須課題にしない。学生PCの通常DNSでlab.testを解決できる仕様にはしない。

## 3. BINDの設定と外部名

| 対象 | 基本設定 |
| --- | --- |
| 主な設定 | /etc/bind/named.conf.options、/etc/bind/named.conf.local |
| zone file | /etc/bind/zones/db.lab.test |
| DNS待受 | 10.20.2.10と127.0.0.1、UDP/TCP53。IPv6待受は使用しない |
| 問い合わせ許可 | 10.20.1.10/32、10.20.1.20/32、127.0.0.1/32 |
| recursive/cache利用許可 | 上記clientのみ。allow-recursionとallow-query-cacheも明示 |
| 外部名の転送先 | 10.20.0.2のみ |
| forwarding | forward only。転送失敗時にroot DNSへ直接問い合わせる方式を使わない |
| zone転送 | allow-transfer none。secondaryを作らない |
| 動的更新 | 許可しない。学生が配布ひな形のzone fileを編集 |

lab.testの既存名はBINDが自身のzoneから応答する。lab.test内の未登録名は権威応答のNXDOMAINとし、AWS側で同じ授業名を代わりに解決する仕組みは作らない。外部名はAWS標準DNSへ転送する。

AWS標準DNSはVPC内のサービスであり、この転送にInternet向けのNATやpublic DNS宛UDP53は不要。外部名を解決できることと、踏み台がそのWebサイトへ接続できることは別である。踏み台の外部HTTP/HTTPSへの新規接続は禁止する。

DNS EC2の通常OS resolverはAWSの初期設定を維持する。BINDを自身の上流へ指定して転送ループを作らない。BINDの動的な外部資源取得を含め、forward only構成が収録版で不要なInternet通信を要求しないことをD08の受入で確認する。

## 4. 踏み台・Webの通常DNS

| 段階／対象 | resolver |
| --- | --- |
| BIND構築前の全5台 | AWSのDHCP初期設定を維持。授業資源の取得・SSHはprivate IPを使用 |
| BIND構築後の踏み台 | 10.20.2.10のみ |
| BIND構築後のWeb | 10.20.2.10のみ |
| DNS・DB・パッケージのOS | AWSのDHCP初期設定を維持。今回のアプリ経路ではBIND clientにしない |
| 学生PC | PC本来のDNSを維持。AWS公開IPv4で一般Web/RDPへ接続 |

踏み台・WebはNetplanのnetworkd構成でDHCPのIP・routeを保持し、`dhcp4-overrides.use-dns=false`とDNS server `10.20.2.10`を設定する。通常のアプリはsystemd-resolvedを通じて問い合わせる。/etc/resolv.confへ直接書いて一時的に置き換える手順にはしない。

授業DNSとAWS DNSを同列の候補として二つ並べない。systemd-resolvedのFallbackDNSは空にし、別のinterface/global設定からAWS/public DNSが混入していないことを確認する。これにより、BIND停止中に内部名だけが別経路で偶然成功する構成を避ける。

実AMIのinterface識別子と既存cloud-init/Netplanのfile構成を確認してひな形を作る。既存のNIC設定を重複作成せず、IP固定値・gatewayをOSで手動指定しない。networkdを踏み台でも維持し、GUIのNetworkManagerへNICの管理を二重に渡さない。設定fileのpathと具体的な合成はD08/D10のAMI固定時に検証する。

踏み台Firefoxは教員の初期配布でDNSOverHTTPSを無効化・固定し、OSのresolverを使用させる。Webアクセス用proxyも配置しない。一般WebはIP指定からweb.lab.test、管理画面はadmin.lab.test:8080へ切り替えて確認する。

/etc/hostsにweb/admin/db等の授業名を固定してDNSを代用しない。授業用BINDが止まったときの確認や修正はprivate IP指定のSSH・APTで継続できる。

## 5. 学生の作業順

1. DNSサーバーへ10.20.2.10のIP指定でSSHし、10.20.2.30の保存済みAPTからBINDと確認toolを導入する。
2. 教員配布のoptions/zoneひな形を編集し、上表の名前・IP・client・転送先を設定する。
3. named-checkconfとnamed-checkzoneで検証する。zone更新時はserialを増やして再読込する。
4. 踏み台とWebから10.20.2.10を明示して問い合わせ、UDPとTCPで期待IPを確認する。
5. BINDの応答確認後に、踏み台・Webの通常DNSを変更する。
6. 通常の名前解決、browser、Webからdb.lab.testの解決を確認する。再起動後も設定が維持されることを確認する。

本番構築に使うzoneが一つであることと、P/Mを同一値でPASSにすることは別。P/Mの練習対象・値・初期状態・判定割当はD11で決める。

## 6. 受入条件

| ID | 確認すること | 期待結果 |
| --- | --- | --- |
| DNS-01 | BIND未構築時のAPT・SSH | IP指定で取得・管理ができる |
| DNS-02 | 設定とzone検証 | 構文・SOA/NS・6件のA recordが妥当 |
| DNS-03 | UDP/TCPの明示問い合わせ | 踏み台・Webから10.20.2.10を指定して期待IPが返る |
| DNS-04 | 通常の名前解決 | resolver設定と実問い合わせの両方でBIND利用を確認。hostsや別DNSで代用していない |
| DNS-05 | 正常な名前と未登録名 | 既存名は指定IP、未登録のlab.test名は権威NXDOMAIN |
| DNS-06 | 外部名の転送 | BIND経由の外部名解決がAWS DNS転送で成功。踏み台の外部Web接続成功は求めない |
| DNS-07 | 許可・拒否 | 許可clientから応答成功。他のLab内送信元の利用とzone転送を拒否。設定・SG・実通信を合わせて確認 |
| DNS-08 | アプリ経路 | 踏み台browserのweb/admin、Web側のdb.lab.testの解決が成立 |
| DNS-09 | 維持と依存 | 再起動後も設定が維持。キャッシュを消してBIND停止時に内部名の新規解決が失敗し、IP指定の管理は継続 |

拒否試験は対象稼働と許可側成功を確認したうえで行う。判定用の禁止送信元を一時的に用意する方法、変更の片付け、得点との対応はD11へ残す。単なる対象停止をアクセス制限のPASSにしない。

## 7. 踏み台の外部送信禁止との関係

踏み台のInternetへの新規通信は原則禁止とし、内部SSH、内部DNS、Web80/8080、package80と、ユーザー採用の教員固定採点受付IP:443だけを送信許可する。RDPの応答はSGのstatefulな仕組みで成立するため、外向き全許可を残す理由にしない。具体的な送信表はネットワーク設計を正本とする。

AWS DNS・DHCP・metadata・Amazon Time Sync等にはSGでは制御できない通信がある。SGだけで「AWS基盤通信を含む全送信がゼロ」「Amazon DNSへの直接問い合わせも絶対禁止」とは言わない。通常のresolverはBINDへ統一するが、OS管理権限を持つ学生によるAWS resolverの直接利用まで強制遮断する課題は今回は加えない。

時刻同期はInternet上のNTP poolではなく、169.254.169.123のAmazon Time Syncを使用する。教員が初期配布でchronyを設定し、外部poolへの代替通信を残さない。これはWeb証明書課題の追加ではなく、外部送信禁止で通常の時刻同期が失敗しないための基盤設定である。

採用済みの方式は、踏み台が既存SSHで各台を検査・集約し、教員の固定受付IP:443だけを外部送信の例外にする構成。以前のWeb送信役案は置換済み。[採点集約と限定送信の設計](2026-10_web_infrastructure_grading_transport_design.md)を参照。認証はHTTPS＋Lab専用トークン。固定受付の実IP/domain・配布・DNS未完成時の送信補助方法は残件であり、まだ実装済みruleとは扱わない。

## 次の議題

D06に続きD07は[DB設計](2026-10_web_infrastructure_database_design.md)で具体化した。次はD08の事前保存packageと初期配備。DNSの実機受入、配布AMI固有のresolver設定、全送信/routeと採点送信はそれぞれD08〜D11で検証・実装する。

## 根拠と参照

SOA時間・TTL・file配置・client選択は今回の授業用の具体化。既存IPと名前はユーザー了承の設計を再利用している。

- [設計決定一覧](2026-10_web_infrastructure_design_decision_register.md)
- [ネットワーク設計](2026-10_web_infrastructure_network_design.md)
- [サービス設計](2026-10_web_infrastructure_service_design.md)
- [BIND設定reference](https://bind9.readthedocs.io/en/v9.18.39/reference.html)
- [NetplanのDHCP DNS override](https://netplan.readthedocs.io/en/stable/netplan-yaml/)
- [FirefoxのDNSOverHTTPS policy](https://mozilla.github.io/policy-templates/)
- [AWS標準DNS](https://docs.aws.amazon.com/vpc/latest/userguide/AmazonDNS-concepts.html)
- [AWS SGのstatefulと制御対象外通信](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-security-groups.html)
- [Amazon Time SyncのUbuntu設定](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configure-ec2-ntp.html)

一次資料の確認日: 2026-10-13。systemd-resolvedの一部manualは本文取得失敗。実AMIでresolverの合成・キャッシュ・fallbackの挙動を検証する。BIND referenceの版を、収録patch版の確定という意味では使用しない。
