# Web単元：サービスと接続設定

2026-10-16最新方針：本人指定でCloudShell→踏み台はSession Managerのssm-userで接続する。この区間のSSH秘密鍵は不要。管理入口は踏み台だけに既存LabInstanceProfileを付け、SSM/ssmmessagesの専用endpoint2個へ踏み台SGから443だけを許可する。本人は管理権限と既存LabRoleの追加権限・endpoint時間課金を確認して適用承認済み。既存5台のID/root/RDP制限/S3閉鎖を維持する。内部4台のSSHは別に受入し、共有Windowsへの秘密鍵保存は要求しない。実受入状態はverification_status.md冒頭を優先する。

更新: 2026-10-16（Asia/Tashkent、共有Windowsと個人CloudShellの鍵取扱いを修正）  
対象: D05。了承済みD04の分担を基にした実装仕様。  
状態: Codexによる詳細の具体化。実装、依存資源の収録、AWS実機受入は未実施。

## 1. 前提と採用するソフトウェア

全5台をUbuntu Server 24.04 LTS / amd64に揃える。既存Linux教材と同じ系列を使い、CPU architectureを混在させない。Canonicalの通常Server imageを基準とするが、実際のregion・AMI ID・instance type・EBS容量はD10で検証・固定する。

| サーバー | 採用するソフトウェア | 開始状態と担当 |
| --- | --- | --- |
| 踏み台 | Xfce、xrdp＋xorgxrdp、Firefox（Mozilla公式DEB）、OpenSSH client/server | 教員の配布工程で導入・設定済み。学生がRDP・SSH・browserを使用 |
| パッケージ | Nginx、署名付き授業APTリポジトリ、アプリbundle・Python依存資源 | 教員の配布工程で稼働済み。学生は配布資源を取得 |
| DNS | BIND 9、DNS問い合わせ・設定検証tool | 学生が導入・設定 |
| DB | PostgreSQL 16系、PostgreSQL client | 学生が導入・設定 |
| Web | Nginx、Python 3.12、Django 5.2 LTS系、Gunicorn、psycopg 3系 | 学生が導入・配置・接続設定。アプリコードは教員提供 |

共通の時刻同期は教員の初期配布でchrony→169.254.169.123のAmazon Time Syncへ設定する。外部NTP poolに依存しない。踏み台の外部への新規通信は原則禁止とし、教員の固定採点受付IP:443だけを例外にする。内部の必要な送信は維持する。詳細はネットワーク設計。

Pythonは専用venvを使い、OS全体のPython環境へDjango等を直接追加しない。psycopgは対応するbinary wheelを含む方式を基準とする。全依存・厳密なpatch版・hash・新規AMIでの動作はD08の収録試験で固定する。BIND/Nginx等も授業中の最新版取得ではなく収録版を使う。

Firefoxは事前保存したMozilla版DEBと依存を踏み台へ導入する。UbuntuのSnap移行packageだけで済ませず、授業中にSnap StoreやMozillaの外部配布先へ取得が発生しないことを確認する。browserの実機動作は配布条件とする。

## 2. 接続経路と待受

| 用途 | 待受・接続先 | 認証・制限 |
| --- | --- | --- |
| 踏み台へのRDP | 踏み台TCP3389 | 指定50 CIDRと、Lab専用のOSユーザー・パスワード |
| サーバー管理SSH | Web/DNS/DB/パッケージのTCP22、private IP | 踏み台からのみ。公開鍵認証 |
| 一般入口 | WebのNginx TCP80 | 全IPv4へ公開。閲覧専用 |
| 管理入口 | Web private IP TCP8080 | SG-Bastionからのみ、さらにDjango管理者認証 |
| Nginx→アプリ | Web内127.0.0.1:8000 | Gunicorn。外部向けSG許可なし |
| アプリ→DB | db.lab.test:5432 | catalog_app・SCRAM-SHA-256。権限はD07のDB設計 |
| 内部DNS | 10.20.2.10のUDP/TCP53 | 踏み台とWeb。resolver詳細はD06 |
| パッケージ取得 | http://10.20.2.30/ | Lab内4台のみ。APT署名を検証 |

5台のIPとSGは[ネットワーク設計](2026-10_web_infrastructure_network_design.md)に従う。一般／管理入口はHTTPとし、ユーザーが撤回した証明書・HTTPS課題を追加しない。Web用443・8443を追加で開けない。

## 3. OS・アプリ・DBのIDを区別する

| ID | 用途 | 扱い |
| --- | --- | --- |
| labuser | 踏み台RDP・browser・SSH client操作 | Lab専用パスワード。通常のGUI操作は一般権限。直接のSSHパスワードログインは設けない |
| ubuntu | SSH先のOS管理 | Lab専用のSSH鍵で認証し、設定・導入はsudoで行う |
| catalog | Webアプリの実行用OSユーザー | 対話ログイン・sudoなし。Gunicornをこのユーザーで起動 |
| lab_admin | Djangoアプリ管理者 | 備品の閲覧・追加・変更のみ。詳細はアプリ仕様 |
| catalog_app | アプリのPostgreSQL接続role | PostgreSQLのsuperuserにしない。権限はD07 |

2026-10-16の本人確認：授業のWindows PCはOSアカウントを共有するが、AWS Academyアカウントは学生ごとに与えられる。**SSH秘密鍵を共有Windowsへダウンロード・保存し、RDPで手動搬入する手順は採用しない。本人の個別AcademyアカウントのCloudShell内での鍵取扱いは許容する。**

SSH鍵はLabごとに分離し、教員提供ツールがSSM経由で本人踏み台のlabuser配下だけに生成・保管し、公開鍵を対象4台へ登録する。CloudShell→踏み台はSSMのssm-userを使うためSSH秘密鍵不要。学生は配備ツールを実行し、RDPのTerminalでは`lab-ssh web|dns|db|repo`、SSMでは`sudo -iu labuser lab-ssh <role>`を使う。鍵の手動ダウンロード・RDP共有driveによるコピーは要求しない。踏み台の専用鍵directoryは0700、秘密鍵は0600。共通配布物・UserData・操作履歴・通常log・会話・projectへ秘密鍵を含めず、他4台には公開鍵だけを渡す。

10/16にc3で本人が自動設定を実行し、EIC短期公開鍵の期限後にも内部4台へSSH成功。5台の停止・再開後も同じ鍵/ホスト鍵pinで実SSHと5台の新しい役割・通信チェックに合格。初期KeyName=vockeyと旧公開鍵は保持し、新鍵を各OSのauthorized_keysへ追加した。EC2 KeyPairの設定変更だけでOS内の鍵が変わるとは扱わない。学生向け署名配布・create/lockの統合は別に残る。

RDP用パスワードはLabの初期配備時に学生が設定する。平文をCloudFormationの出力、教材、Git、通常logへ出さない。初期配備の補助ツールが個人AcademyのCloudShellで非表示入力を受け、OS側にはパスワードハッシュを渡す方式を基準とする。AWS投入と鍵の自動設定はD08で実検証し、学生向け配布への統合を続ける。踏み台の外部SSH22を新規公開する前提にはしない。

初回SSHのホスト鍵確認方法も配布手順に含める。確認を全面無効化する設定を標準手順にしない。OSのID・アプリ管理者・DB roleのパスワードはそれぞれ別に設定する。

## 4. Webの配置・起動・設定ファイル

| 対象 | 授業版のpath・名前 | 内容 |
| --- | --- | --- |
| アプリ | /opt/jdu-catalog/app/ | 教員提供コード。Django project名はjdu_catalog |
| Python環境 | /opt/jdu-catalog/venv/ | オフライン導入する専用venv |
| 設定 | /etc/jdu-catalog/app.env | 接続値・秘密値。root所有0600 |
| 静的資源 | /var/lib/jdu-catalog/static/ | collectstaticで配置するCSS等。Nginxが読み取り配信 |
| service | /etc/systemd/system/jdu-catalog.service | User/Group=catalog、WorkingDirectory=/opt/jdu-catalog/app |
| Nginx設定 | /etc/nginx/sites-available/jdu-catalog | 一般80・管理8080のserver。sites-enabledから有効化 |
| 静的ページの練習 | /var/www/jdu-web/index.html | アプリ連携前のNginx表示確認 |
| アプリlog | systemd journal | jdu-catalog.serviceの標準出力・標準エラー |
| Web log | /var/log/nginx/ | 一般・管理別のaccess/error log |

コードとvenvはrootが管理し、catalogは読み取り・実行のみとする。static資源はNginxから読み取れる権限にし、設定file・秘密値をstatic配信領域へ置かない。DBの業務データとsessionはDBサーバーに保存する。

Gunicornは`jdu_catalog.wsgi:application`を127.0.0.1:8000で起動する。最初はworker 1で開始し、最終的なmemory・応答の実測をD10で確認する。Djangoの開発用runserverを完成状態の起動方法にはしない。

systemdはEnvironmentFileでapp.envを読み込み、起動後のアプリはcatalog権限で実行する。OS起動時の自動起動と失敗時の再起動を設定する。network-onlineは別EC2のDB稼働を保証しないため、最終確認では実際のDB接続とページ応答も調べる。

初期化・migration・static配置・管理者作成には教員提供の補助commandを用意する。root権限で設定fileを読み、アプリ処理をcatalog権限で実行する。学生が秘密値をコマンド引数へ書いたり、rootでGunicornを常時起動したりする手順にしない。DBへのschema変更はD07で定義する初期化用権限で行う。

## 5. 学生が設定する値

| 設定項目 | 基本値／決め方 |
| --- | --- |
| DB_HOST | db.lab.test |
| DB_PORT | 5432 |
| DB_NAME | jdu_catalog |
| DB_USER | catalog_app |
| DB_PASSWORD | 学生がそのLab専用に設定。DB側と一致させる |
| DB_SSLMODE | prefer。教員の授業設定で固定。TLS保証・証明書課題の要件とはしない |
| PUBLIC_IPV4 | 起動中のWebの公開IPv4。停止・起動後に確認し更新 |
| ALLOWED_HOSTS | web.lab.test、admin.lab.test、10.20.1.20、現在の公開IPv4。全許可の*は使用しない |
| SECRET_KEY | 教員提供の初期化commandがLabごとに生成。通常の再起動では維持 |
| DEBUG | False。教員提供の授業設定で固定 |

app.envは教員が説明付きひな形を配布する。秘密値は設定fileへ保存し、通常log・採点結果・画面へ出さない。ALLOWED_HOSTSへ設定する接続先名と、SGが許可する接続元IPは別のものとして説明する。ひな形はデータとして読み込み、任意のshellコードとして実行しない。

## 6. Nginxとアプリの分担

- 一般80は公開一覧と必要なstatic資源を提供する。`/admin`と配下は拒否し、一般入口からの書込み操作は成立させない。
- 管理8080はadmin.lab.testの管理画面と必要なstatic資源を提供する。一般80にadmin.lab.testをHost指定しても管理画面へ入れないよう、portごとのserver設定を分ける。
- NginxからGunicornへ元のHostを転送する。管理URLの8080を含むHostが失われて、CSRF検証やログインが失敗しない構成にする。
- CSRF・認証・権限・入力検証は教員提供アプリで実装する。接続許可だけで認証済みとは扱わない。管理者ログインの仕様はアプリ仕様を正本とする。
- Nginx側の設定検証→service再読込→実HTTP応答の順で確認する。設定が読めたことだけでDB連携までPASSとはしない。

## 7. D05の受入条件

| ID | 実装後に確認すること |
| --- | --- |
| SVC-01 | 全5台が採用OS/architecture。踏み台RDP・Firefox・内部SSHが利用可能 |
| SVC-02 | package配布はIP指定で利用可能。browser・Python依存を含め外部取得へfallbackしない |
| SVC-03 | アプリはcatalogで動き、127.0.0.1:8000以外に公開待受しない |
| SVC-04 | 一般80は一覧を表示し、管理8080でログイン・登録できる。static資源も表示される |
| SVC-05 | 一般80の管理経路を拒否し、踏み台以外から管理8080へ接続できない |
| SVC-06 | OS起動後にserviceが起動し、DNS・DBも稼働した状態で一覧と登録反映を確認できる |
| SVC-07 | 秘密値を画面・通常log・採点結果へ出さず、設定fileとSSH秘密鍵の所有者・権限が仕様に一致 |

これらは設計上の受入条件であり、現時点の実機PASS記録ではない。採点の配点・P/Mへの割当・Web進捗送信の詳細はD11。

## 8. 次の議題と未検証事項

D06は内部DNS設計、D07はDB設計で具体化した。D08は[配布設計](2026-10_web_infrastructure_package_distribution_design.md)を公式AMI＋CloudFormation/UserData＋install.shへ変更し制作/受入待ち。D09は[通信設計](2026-10_web_infrastructure_network_design.md)で全台送信/route・S3閉鎖・採点受付案・NET受入を具体化した。次はD10のAWS実値・権限・費用を確認し、D08の全依存収録・script/template制作・導入受入へ戻る。採点の踏み台集約・限定送信はユーザー採用済みで、固定受付の実構築・秘密配布・集約/送信実装は残件。

AMI ID、packageの全依存・patch版、Firefoxとxrdpの組合せ、OS/service実名・alias、鍵とハッシュの初期配備、アプリの実HTTP動作、5台の費用・起動性能は未検証。選定値だけで授業配布可能と扱わない。

## 根拠と参照

path・ID・サービス名・worker数は今回の授業要件に合わせたCodexの具体化。

- [設計決定一覧](2026-10_web_infrastructure_design_decision_register.md)
- [備品カタログ仕様](2026-10_web_infrastructure_catalog_app_spec.md)
- [ネットワーク設計](2026-10_web_infrastructure_network_design.md)
- [Ubuntu 24.04 release notes](https://documentation.ubuntu.com/release-notes/24.04/)（Python 3.12、PostgreSQL 16系列、SSHのsocket activation）
- [UbuntuのAWS image選択](https://ubuntu.com/aws/docs/aws-how-to/instances/find-ubuntu-images/)
- [Xfce公式](https://www.xfce.org/about/)
- [xrdp公式プロジェクト](https://github.com/neutrinolabs/xrdp)
- [MozillaのLinux導入](https://support.mozilla.org/en-US/kb/install-firefox-linux)
- [Django配備設定](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)
- [DjangoとGunicorn](https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/gunicorn/)
- [Nginxのproxy設定](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)

一次資料の確認日: 2026-10-13。Ubuntu個別packageページとsystemd/xrdpの一部manualは本文取得に失敗した。版別の細かな動作は収録AMIとそのmanualで検証する。
