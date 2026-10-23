# 教員提供：JDU備品カタログ

2026-10-16制作中。コード・SQLはlocalの実PostgreSQL16.15で受入済み。収録Nginx1.24.0とGunicornを接続したlocal proxy受入2件も合格。秘密設定の作成/読取りと管理操作のhelperを実装した。AWSへのアプリ導入・学生向け署名payloadへの統合は未完。

仕様正本は[アプリ仕様](../../system_requirements/2026-10_web_infrastructure_catalog_app_spec.md)、[DB権限](../../system_requirements/2026-10_web_infrastructure_database_design.md)、[配置とservice](../../system_requirements/2026-10_web_infrastructure_service_design.md)。学生はアプリコードを変更せず、DNS/DB/Nginx/serviceの導入・接続設定を行う。

## 構成

- Django5.2.18、Gunicorn26.2.0、psycopg3.3.6。依存7 wheelはWeb Labの署名候補に収録済み。外部pipへfallbackしない。
- 公開入口はDBの公開備品を毎回取得して表示する閲覧専用一覧。管理操作はprivate8080からだけ受け付ける。
- custom AdminSiteは備品だけを登録し、閲覧/追加/変更を許可する。備品削除、ユーザー管理、browser内password変更は提供しない。
- 通常接続はcatalog_app。catalog_setupで固定migration・初期データ・管理者を作り、SQL権限を適用してからNOLOGIN/password NULLへ切り替える。
- DB障害でSQLiteや固定HTMLへfallbackしない。設定不足・placeholder・全許可Hostは起動時に拒否する。

## 配置予定とtemplate

`/opt/jdu-catalog/app`に配布コード、`/opt/jdu-catalog/venv`にオフラインvenvを置く。コード/venvはroot管理、実行userは非ログイン・非sudoのcatalog。staticは`/var/lib/jdu-catalog/static`へcollectstaticしNginxから読む。

`configuration.py create-runtime`をWeb内で本人が対話実行し、DB側で設定済みのcatalog_app passwordを非表示で2回入力する。Django secretはこの本人実行時にLabごとに生成する。`create-setup`は同じDjango secretを保持し、別の既存catalog_setup passwordを入力して一時setup.envを作る。同一password・既存file・不正権限・link・不正な接続先を拒否し、DB側のpasswordは変更しない。保存先はroot所有0600の`/etc/jdu-catalog/app.env`と`setup.env`。

環境fileは全値を一行のJSON二重引用形式で保存する。shellのsource/evalは使わず、許可した9項目だけをデータとして読む。systemdのEnvironmentFileと同じ値になることを実systemdの独立fixtureで確認した。引用符・backslash・ドル記号・日本語を保持し、command substitutionを実行しない。[systemd公式仕様](https://github.com/systemd/systemd/blob/main/man/systemd.exec.xml)

`manage_secure.py --phase setup|runtime <操作>`はrootが設定を読み、固定された操作だけを非ログイン・非sudoのcatalog userへ権限を落として実行する。setupはcheck/migrate/seed_catalog/create_lab_admin、runtimeはcheck/collectstatic/set_lab_passwordだけ。DBのsetup無効化は既存SQLで行い、helperが学生のDBを初期化/resetしたり既存設定を置き換えたりしない。collectstatic用dirは事前にcatalog userが書けるよう準備し、配置後はNginxが読める権限にする。

```bash
# Web内で実行。秘密値は引数に書かない。
sudo python3 /opt/jdu-catalog/app/configuration.py create-runtime
sudo python3 /opt/jdu-catalog/app/configuration.py create-setup
sudo /opt/jdu-catalog/venv/bin/python /opt/jdu-catalog/app/manage_secure.py --phase setup check
sudo /opt/jdu-catalog/venv/bin/python /opt/jdu-catalog/app/manage_secure.py --phase setup migrate
sudo /opt/jdu-catalog/venv/bin/python /opt/jdu-catalog/app/manage_secure.py --phase setup seed_catalog
sudo /opt/jdu-catalog/venv/bin/python /opt/jdu-catalog/app/manage_secure.py --phase setup create_lab_admin
```

上記は学生の構築段階の操作で、初期5台の自動準備では実行しない。password設定や管理者作成は本人が実行する。AWS上でのhelper/権限切替・初期化の通し受入はまだ。

`config/jdu-catalog.nginx.conf`は公開80とWeb private IP8080を分離し、proxyでX-JDU-Entryを必ず上書きする。一般入口がadmin.lab.testのHostや偽のheaderを受けても管理経路を使わせない。管理8080はBastion10.20.1.10だけをallowし、AWS SGでも制限する。Hostは8080を含めて転送する。

`config/jdu-catalog.service`はcatalog userのGunicornを127.0.0.1:8000だけで起動する。起動時にmigration/seedを自動実行しない。

## 初期構築の順序

1. 学生がDB内postgresでsql/01、02を適用し、別々のLab専用passwordを対話設定する。
2. Web上のcatalog_setup接続で固定migration、seed_catalog、create_lab_adminを実行する。
3. DB内postgresでsql/03_runtime_grants.sqlを適用する。11 table manifestや所有者等が不一致なら中断する。
4. setup接続を閉じ、DB内postgresでsql/04_disable_setup.sqlを適用する。一時setup設定を片付け、app.envはcatalog_appだけを使う。
5. static配置・Nginx検査・service起動後、Bastionの管理画面で架空備品を登録し、一般一覧とsql/check_item.sqlの読取りで照合する。

補助commandはpasswordを端末で2回非表示入力する。引数・共通資料・通常logへ値を渡さない。create_lab_adminは既存userを上書きせず、seed_catalogも既存備品があれば拒否する。set_lab_passwordはauth_user.password列だけを更新し、通常roleで利用できる。

`build_bundle.py`は明示した33個の公開fileだけを`jdu-catalog/`へ収録し、全fileのhash/sizeを持つAPP-MANIFEST.jsonを加える。試験fixture・実app.env/setup.env・private設定・cache・秘密鍵は収録しない。archiveの時刻/owner/mode/順序を固定し、既存archiveは上書きしない。アプリarchive単独はstudent releaseでもOS受入でもなく、署名payloadと外側manifestへの統合を別に確認する。

## local受入

独立WSL clusterを127.0.0.1:55439/private socketで使用した。収録済みPostgreSQL/client/libpq DEBをcacheへ展開し、既存OSへinstallしていない。架空fixture専用で、AWSへ接続しない。

`tests/provision_fixture.py`は空のfixtureだけを準備し、既存DB/roleを自動削除・resetしない。`tests/test_runtime.py`の8ケースは通常catalog_appで実行し、各変更をtransaction rollbackする。DjangoのSQLite test DBやsuperuser接続で通常操作を代用しない。

確認済み：固定migration差分なし/11 table、公開・非公開とescape、通常staffのログイン・登録・編集・公開切替・ログアウト、誤認証/権限なし/CSRF/不正入力の拒否、公開側と直接接続のadmin拒否、password列限定変更、禁止SQLと列権限、所有者/membership/setup無効化。

`tests/test_proxy.py`は収録Nginxをrootlessで起動し、実Gunicorn→Django→PostgreSQLに接続する2受入ケース。publicの偽admin header/Host/encodingを含むadmin拒否、読取り・static配信、privateのHost:8080維持/CSRF/ログイン/session/ログアウトに合格。試験後は作成した2 processだけを停止する。fixtureではloopbackの高位portと送信元を使うため、AWS SG/実private IP・systemd・実browserの登録操作を検証した結果ではない。

一次資料：[Django admin](https://docs.djangoproject.com/en/5.2/ref/contrib/admin/)、[Nginx proxy](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)、[Nginx access](https://nginx.org/en/docs/http/ngx_http_access_module.html)。
# D11のpractice/mission profile（2026-10-22追加）

既定はmission、練習用には`--profile practice`を使う。コードとportは共用し、DB/role/管理者を分ける。
`profile_sql.py --profile practice 01_create_roles.sql`等は、固定した練習名のSQLを表示するだけで実行しない。
`configuration.py create-runtime --profile practice`は本人の非表示入力からroot専用のprofiles/practice.app.envを作る。
初回だけapp.envも作る。setupも同じprofileを指定し、現在のapp.envと異なるprofileを拒否する。
manage_secure.pyは現在のprofileに応じてpractice_admin/lab_adminを作成する。
構築終了時にSQL04でsetupを無効化し、setup.envとprofiles内の当該setup.envを削除する。
切替前はserviceを明示停止し、`configuration.py activate --profile mission`等で切り替えて再開する。
元のruntime profileはroot専用のprofiles内に保持し、checkerは切替・初期化・password変更を行わない。
既存P1/M1の静的URLはアプリ用Nginxでも保持する。本人実演による採点は設けない。

