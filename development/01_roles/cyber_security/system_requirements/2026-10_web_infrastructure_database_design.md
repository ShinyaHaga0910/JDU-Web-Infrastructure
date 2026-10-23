# Web単元：DBの接続認証・権限・保存先

更新: 2026-10-13（Asia/Tashkent）  
対象: D07。ユーザーの「内容を詰めてください」に基づく具体化。  
状態: 設計仕様。SQL・補助command・アプリの実装とAWS実機受入は未実施。

## 1. D07の完了条件との対応

| 完了条件 | 今回の仕様 |
| --- | --- |
| DB/table/架空データ | PostgreSQL16系、jdu_catalog、public.catalog_item、Django標準補助table、既存の架空備品を維持 |
| app roleの許可SQL | catalog_appにtableごとの必要なDMLだけを付与。所有権・DDL・DB/role作成権限なし |
| 初期作成・更新 | 所有者catalog_setupでmigration・初期データ・管理者作成。その後NOLOGIN＋password消去 |
| 接続認証 | Web10.20.1.20から指定DB/roleだけをSCRAM-SHA-256で許可。DB管理はDB内Unix socketのpeer |
| 保存先と必要容量 | 標準の/var/lib/postgresql/16/main、DBルートEBS gp3 16 GiBを設計値にする。実AMIと容量検証はD10 |

設計仕様と実機合格を分ける。下記のDB受入条件を実装後に確認してから授業版を固定する。

## 2. 保存するtableとデータ

業務tableはpublic.catalog_item。code/name/quantity/location/description/is_publicと自動採番・作成/更新時刻は[アプリ仕様](2026-10_web_infrastructure_catalog_app_spec.md)に従う。codeの一意性、必須値、数量0以上等は教員のmodel/migrationと入力検証で用意する。学生はmodelやmigrationを編集しない。

Django標準のauth・contenttypes・sessions・adminも使用する。基本の収録対象は次の11 table。教員は固定したmigrationの実生成結果と照合し、table/sequence manifestを配布する。

- catalog_item
- auth_user、auth_group、auth_permission
- auth_user_groups、auth_user_user_permissions、auth_group_permissions
- django_content_type、django_session、django_admin_log、django_migrations

公開の架空備品2件と非公開1件を初期データにし、学生が指定備品を追加する。大学の実台帳や学生個人情報を使わない。一般利用者の会員tableを追加しない。

## 3. DB用のIDと所有者

| PostgreSQL role | 用途 | 権限と完成時の状態 |
| --- | --- | --- |
| postgres | DB内のOS管理・採点検査 | OSのpostgresとしてUnix socketからpeer認証。WebからのTCP接続は拒否 |
| catalog_setup | 初期構築・migration | jdu_catalog/publicと生成objectの所有者。初期構築時だけLOGIN。完成後はNOLOGIN、passwordはNULL |
| catalog_app | Djangoの通常実行 | LOGIN、指定DBへCONNECT、publicへUSAGE、下表のDMLのみ |

catalog_setup/catalog_appはNOSUPERUSER・NOCREATEDB・NOCREATEROLE・NOREPLICATION・NOBYPASSRLSとする。catalog_appをcatalog_setupや管理roleのmemberにしない。catalog_appへobjectの所有権やGRANT OPTIONを与えない。

初期構築用roleは対象DBの範囲で必要な所有者権限を持つが、PostgreSQLクラスタ全体のsuperuserではない。管理者のアプリID lab_admin、実行用OS user catalog、PostgreSQL role catalog_appは別のIDである。

DB名・roleを作る操作は、踏み台→DBへのSSH後にDB内でsudo -u postgres psqlを使用する。完成後のschema更新が必要になった場合も、この管理経路でcatalog_setupを一時的に再有効化してから実施し、終了時に再び無効化する。

## 4. 待受と接続認証

DBのIPv4は10.20.2.20、Webは10.20.1.20。DBのTCP5432はSG-Webからのみ許可し、踏み台から直接のDB TCP接続は許可しない。管理・採点は既存SSH経由でDB内のUnix socketを使う。

postgresql.confの主要な設定値:

```text
listen_addresses = '10.20.2.20'
port = 5432
password_encryption = 'scram-sha-256'
```

pg_hba.confの授業用ルール（順序を維持し、収録AMIの広い既定許可を残さない）:

```text
# DB内のOS postgresによる管理
local   all           postgres                              peer
local   all           all                                   reject

# 初期構築用と通常実行用。どちらもWebのprivate IPのみ
host    jdu_catalog   catalog_setup   10.20.1.20/32          scram-sha-256
host    jdu_catalog   catalog_app     10.20.1.20/32          scram-sha-256

# その他のTCP接続を拒否
host    all           all            0.0.0.0/0              reject
host    all           all            ::/0                   reject
```

pg_hbaは最初に一致した行を使用する。localhostのtrustや広いhost all all許可が前に残る構成は合格にしない。物理replicationには許可行を設けず、role自体もNOREPLICATIONとする。

Webの接続先はdb.lab.test:5432。pg_hbaの接続元はIP/32で指定し、逆引きDNSを接続認証の前提にしない。listen_addresses変更はDB再起動、pg_hba変更は検証後の再読込と、実際の新規接続で確認する。

DB passwordは各Lab専用に16文字以上で設定し、catalog_setupとcatalog_appで別の値を使う。DB内でSCRAM設定を確認してから対話式のpassword設定を行い、既存のMD5 verifierのままにしない。平文password入りのSQL・コマンド引数を教材や履歴へ残さない。

今回はDB用の証明書作成・配布・検証を新しい課題に加えない。収録clusterのSSL既定設定を維持し、教員提供driverはsslmode=preferを指定する。これはTLSの利用を保証する設定ではなく、DBの必須認証条件はSCRAMとする。採点先へ送信するHTTPSの証明書検証とは別の設定である。

## 5. 通常実行用roleの許可表

| object | catalog_appへ許可する操作 | 理由 |
| --- | --- | --- |
| jdu_catalog | CONNECT | 指定DBへ接続 |
| public schema | USAGE | 配布tableを参照。CREATEは与えない |
| catalog_item | SELECT、INSERT、UPDATE | 一覧、登録、編集、公開切替。備品のDELETEなし |
| auth_user | SELECT、UPDATE(last_login, password) | ログイン時刻・password hash更新。user作成・削除・権限属性変更なし |
| auth_group、auth_permission、auth_user_groups、auth_user_user_permissions、auth_group_permissions、django_content_type | SELECT | 配布済みの認証・権限・model情報を取得 |
| django_session | SELECT、INSERT、UPDATE、DELETE | session作成/更新とログアウト・期限切れsession削除 |
| django_admin_log | SELECT、INSERT | 管理画面の操作記録。履歴の書換え・削除なし |
| django_migrations | なし | migration状態の変更・確認は初期構築用roleまたはDB内管理で行う |
| catalog_itemとdjango_admin_logのid用sequence | USAGE | 自動採番に必要な範囲。setvalのためのUPDATEは与えない |

DB内での備品DELETEと、Djangoの削除ボタン・削除権限は両方制限する。session tableのDELETEまで禁止するとログアウトが壊れるため、用途を区別する。

認証関連tableへのINSERT・permissionのUPDATEを通常実行へ与えず、管理者作成・権限付与はcatalog_setupで初期化する。教員はアプリ管理画面へauth_user/groupの管理を登録しない。

auth_userを列単位で更新するため、教員提供のpassword変更補助commandはset_passwordとsave(update_fields=['password'])を使用する。標準changepasswordや標準のWeb password変更formをそのまま実行すると全列UPDATEになるため、この授業のroleでは使用しない。browser内のpassword変更入口は設けず、必要な再設定はWeb内の対話式補助commandを使う。これは学生の認証コーディング課題ではない。

### 初期構築時にDB内で行うSQLの基本形

以下は設計用の具体例。password設定・既存状態の照合・エラー処理を含む配布commandはこれから実装する。CREATE DATABASEはtransaction内では実行しない。

```sql
CREATE ROLE catalog_setup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS;
CREATE ROLE catalog_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS;
CREATE DATABASE jdu_catalog OWNER catalog_setup ENCODING 'UTF8' TEMPLATE template0;
```

jdu_catalogへ接続した後、初期migrationの前に:

```sql
REVOKE ALL ON DATABASE jdu_catalog FROM PUBLIC;
GRANT CONNECT ON DATABASE jdu_catalog TO catalog_setup, catalog_app;
ALTER SCHEMA public OWNER TO catalog_setup;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO catalog_app;
ALTER ROLE catalog_app IN DATABASE jdu_catalog SET search_path = public;
ALTER ROLE catalog_setup IN DATABASE jdu_catalog SET search_path = public;
```

Webのcatalog_setupによるmigration・初期データ・lab_admin作成完了後、DB内で以下の権限表を適用する:

```sql
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM catalog_app;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM catalog_app;

GRANT SELECT, INSERT, UPDATE ON public.catalog_item TO catalog_app;
GRANT SELECT ON public.auth_user, public.auth_group,
  public.auth_permission, public.auth_user_groups,
  public.auth_user_user_permissions, public.auth_group_permissions,
  public.django_content_type TO catalog_app;
GRANT UPDATE (last_login, password) ON public.auth_user TO catalog_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.django_session TO catalog_app;
GRANT SELECT, INSERT ON public.django_admin_log TO catalog_app;
```

sequenceは固定migrationの生成結果を確認し、pg_get_serial_sequenceでcatalog_item.idとdjango_admin_log.idに結びつくsequenceを取得して、その2件だけにUSAGEを付与する。全sequenceへのALL付与はしない。

新規tableに一律の全権限を与えるALTER DEFAULT PRIVILEGESは設定しない。migrationを追加したときは、実際のtable/sequenceと配布manifestを照合して権限表を再適用する。既存roleへ再適用する場合は、列権限・PUBLIC権限・所有者・role membershipも確認し、余分な権限が残らないよう配布commandで処理する。

## 6. 初期構築から通常実行への切替

1. 学生が保存済みpackageからPostgreSQLと必要clientを導入し、待受・pg_hba・SCRAM設定を行う。
2. DB内のpostgresでDB・2 role・publicの権限を設定し、それぞれのpasswordを対話設定する。
3. Webからcatalog_app/catalog_setupで指定DBへ接続できることを確認する。この時点はDB導入段階で、業務tableの完成前である。
4. アプリ連携段階で、教員提供コードとruntimeをWebへ配置し、catalog_setupでmigration、架空初期データ、lab_adminと備品の閲覧/追加/変更権限を作成する。
5. DB内で通常実行用の権限表を適用する。初期化helperの接続を閉じる。
6. DB内のpostgresで以下を実行し、catalog_setupの既存sessionも終了させる。

```sql
ALTER ROLE catalog_setup NOLOGIN PASSWORD NULL;
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE usename = 'catalog_setup' AND pid <> pg_backend_pid();
```

7. Webの一時的なsetup設定を消去する。/etc/jdu-catalog/app.envにはcatalog_appだけを指定し、Gunicornをcatalogで起動する。
8. 通常roleでログイン・登録・表示・編集・ログアウトが成立し、初期構築用の新規接続が拒否されることを確認する。

通常用app.envと一時的setup.envを分け、どちらもroot所有0600で扱う。初期構築用passwordを通常serviceの環境へ渡さない。初期化helperは一時設定をrootで読み、Django処理はOS user catalogへ切り替える。失敗した初期化を通常完成と表示せず、状態に応じて再開できる手順を配布する。

通常serviceの起動時にmigrationや初期データ作成を自動実行しない。通常用のpassword変更helperもmigration履歴を読み書きする処理を要求しない。schemaの確認・変更はcatalog_setupまたはDB内管理の担当とする。

DB導入段階の終了条件は、DB/role/認証/接続制限が成立すること。migration・通常DML・catalog_setup無効化を含む最終DB受入はアプリ連携後に行う。この二段階をP/Mの判定で混同しない。

## 7. 保存先・容量・起動

| 対象 | 設計値 |
| --- | --- |
| DB cluster | PostgreSQL16、main cluster一つ |
| データ | /var/lib/postgresql/16/main |
| 設定 | /etc/postgresql/16/main/postgresql.conf、pg_hba.conf |
| log | /var/log/postgresql/postgresql-16-main.log |
| 主なservice | postgresql@16-main.service。実収録packageのunitをD08で照合 |
| DB用EBS | ルートvolume gp3 16 GiB。OS・DB・WAL・logを同じvolumeに置く |
| 最低空き容量 | 新規配布・受入時に20%以上かつ2 GiB以上 |

データdirectoryはpostgres所有、0700を基本とし、WebのOS userやSSH用ubuntuへ直接の読み書き権限を渡さない。DBへはSQLでアクセスする。

別のデータvolumeや手動mount課題は追加せず、標準保存先を使う。16 GiBは授業版の設計値であり、実AMIの最小volume・OS/package/DBの使用量・log増加・費用をD10で確認して最終配布値に固定する。不足が確認された場合は容量を見直し、記録する。

log rotationは収録packageの設定を使い、受入で有効性を確認する。SQL本文の常時記録を標準にはせず、password/認証hash/設定fileの値を採点結果へ出さない。service wrapperがactiveであることだけで合格にせず、clusterの起動・待受・認証・SQLを確認する。

EBSは通常の停止・起動で保持される。停止・再開後に登録済みの同じ備品と認証状態を確認する。EC2削除時のEBS終了処理はD10で定義し、削除後の復元可能性を保証しない。backup/restoreは今回の課題に追加しない。

## 8. 受入条件と採点観測

| ID | 確認する内容 | 完成状態の期待結果 |
| --- | --- | --- |
| DB-01 | cluster・待受 | 指定16/mainが起動し、10.20.2.20:5432で待受。DB管理はUnix socket |
| DB-02 | 接続先と認証 | Webからdb.lab.testを通常DNSで解決し、catalog_appでjdu_catalogへ新規接続・SQL成功 |
| DB-03 | 拒否 | 誤password、別DB、postgres/無効化後catalog_setupのWeb接続を拒否。踏み台など他送信元のTCP5432を許可しない |
| DB-04 | schemaとデータ | 固定migrationのtable/sequence/制約と架空初期データがmanifestに一致 |
| DB-05 | 通常操作 | 管理者ログイン・指定備品の登録/編集/公開切替、一般一覧の反映、ログアウトが正常 |
| DB-06 | role・SQL制限 | catalog_appはobject所有者・setup member・superuserではなく、備品DELETE・DDL・権限属性変更・不要なSQL権限がない |
| DB-07 | 準備権限の終了 | catalog_setupはNOLOGIN、password消去、既存sessionなし。通常serviceにsetupの秘密値なし |
| DB-08 | 保存と再開 | 標準data directoryと所有者/権限・容量に一致。停止・再開後も同じ備品と通常操作が維持 |

採点は、踏み台からSSHでDB内の教員checkerを実行し、DB内のpostgresからrole/ACL/所有者/pg_hba等を検査する。Web上では実際のcatalog_appの接続・操作を確認する。踏み台から直接5432を開けない。

不要な権限はhas_table_privilege/has_column_privilege/has_schema_privilege等と所有者・role membershipで確認する。TRUNCATE/DROPを実データへ実行して拒否を試す方式にはしない。書込み試験は専用の検査record・transactionと片付けを定義し、初期備品や学生の登録を破壊しない。

通信拒否は正常な対象・許可側の接続成功と合わせて確認し、単なるtimeoutを完成証拠にしない。採点実行権限・試験record・P/M期待値・課題配点はD11で定義する。Webからの認証とSQLまで確認せず、pg_isreadyだけでDB連携完了としない。

## 次の議題と残件

D07の設計仕様は上記で具体化した。D08は[配布設計](2026-10_web_infrastructure_package_distribution_design.md)を公式AMI＋CloudFormation/UserData＋install.shへ変更し制作/受入待ち。D09は[通信設計](2026-10_web_infrastructure_network_design.md)で全台送信/route・S3閉鎖・採点受付案・NET受入を具体化した。次はD10のAWS実値・権限・費用を確認し、D08の全依存収録・script/template制作・導入受入へ戻る。

固定migrationとgrantの実整合、password列限定更新helper、初期化の失敗/再開、DBの二段階判定、実packageのpath/unit、使用量とAMI/EBS、実機の認証/拒否/停止再開は未検証。設計だけで動作保証済みにはしない。

## 根拠と参照

role名、権限表、file、容量、工程は今回の授業用の具体化。

- [設計決定一覧](2026-10_web_infrastructure_design_decision_register.md)
- [備品カタログ仕様](2026-10_web_infrastructure_catalog_app_spec.md)
- [サービス設計](2026-10_web_infrastructure_service_design.md)
- [PostgreSQL16 pg_hba](https://www.postgresql.org/docs/16/auth-pg-hba-conf.html)
- [PostgreSQL16のSCRAM認証](https://www.postgresql.org/docs/16/auth-password.html)
- [PostgreSQL16 GRANT](https://www.postgresql.org/docs/16/sql-grant.html)
- [PostgreSQL16 CREATE ROLE](https://www.postgresql.org/docs/16/sql-createrole.html)
- [PostgreSQL16 schema](https://www.postgresql.org/docs/16/ddl-schemas.html)
- [PostgreSQL16 default privileges](https://www.postgresql.org/docs/16/sql-alterdefaultprivileges.html)
- [PostgreSQL16の権限確認関数](https://www.postgresql.org/docs/16/functions-info.html)
- [PostgreSQL16のSSL mode](https://www.postgresql.org/docs/16/libpq-ssl.html)
- [Django5.2 session](https://docs.djangoproject.com/en/5.2/topics/http/sessions/)
- [Django5.2 password変更commandの実装](https://raw.githubusercontent.com/django/django/stable/5.2.x/django/contrib/auth/management/commands/changepassword.py)
- [EBS root volumeの保持](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/RootDeviceStorage.html)
- [EBS gp3](https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html)

一次資料の確認日: 2026-10-13。Ubuntu Nobleのpg_createcluster manual本文は取得失敗。標準path/unitとclusterの初期状態は収録AMIのpackageで検証する。
