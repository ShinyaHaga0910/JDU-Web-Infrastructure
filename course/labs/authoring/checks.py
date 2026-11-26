"""Student-facing descriptions of canonical assessment criteria."""
CHECKS = {}
def C(suffix, ru, uz):
    CHECKS[suffix] = {'ru': ru, 'uz': uz}

C('WEB02_NGINX_ACTIVE', 'Nginx работает (active).', 'Nginx ishlaydi (active).')
C('WEB02_CONFIG_VALID', 'nginx -t успешно проверяет конфигурацию.', 'nginx -t sozlamani muvaffaqiyatli tekshiradi.')
C('WEB02_LISTEN_80', 'Порт 80 слушает private IP/все интерфейсы, не только loopback.', '80 port private IP/barcha interface da tinglaydi, faqat loopback emas.')
C('WEB02_FILE', 'Обычный файл содержит точный текст, владелец root:root, права 0644.', 'Oddiy faylda aniq matn bor, egasi root:root, ruxsat 0644.')
C('WEB02_LOCAL_HTTP', 'Web получает HTTP 200 и точный текст через loopback.', 'Web loopback orqali HTTP 200 va aniq matn oladi.')
C('WEB02_BASTION_HTTP', 'Бастион получает HTTP 200 и точный текст через private IP.', 'Bastion private IP orqali HTTP 200 va aniq matn oladi.')
C('WEB02_PUBLIC_HTTP', 'CloudShell получает HTTP 200 и точный текст через public IP.', 'CloudShell public IP orqali HTTP 200 va aniq matn oladi.')
C('WEB02_ACCESS_LOG', 'Access log содержит запрос с nonce именно этой проверки.', 'Access log aynan shu tekshiruv nonce li so‘rovni saqlaydi.')
C('WEB03_SERVICE', 'BIND/named работает (active).', 'BIND/named ishlaydi (active).')
C('WEB03_CONFIG_VALID', 'Проверки named и zone lab.test завершаются успешно.', 'Named va lab.test zone tekshiruvlari muvaffaqiyatli.')
C('WEB03_ZONE_AUTHORITY', 'SOA/NS zone lab.test и авторитетный ответ соответствуют схеме; NS — dns.lab.test.', 'Lab.test SOA/NS va vakolatli javob tuzilmaga mos; NS — dns.lab.test.')
C('WEB03_REQUIRED_RECORDS', 'Все заданные A-записи profile дают нужные private IP; это один пункт.', 'Profile dagi barcha A record kerakli private IP beradi; bu bitta band.')
C('WEB03_UDP_RESPONSE', 'И бастион, и Web получают правильные ответы по UDP 53.', 'Bastion ham, Web ham UDP 53 orqali to‘g‘ri javob oladi.')
C('WEB03_TCP_RESPONSE', 'И бастион, и Web получают правильные ответы по TCP 53.', 'Bastion ham, Web ham TCP 53 orqali to‘g‘ri javob oladi.')
C('WEB03_NORMAL_RESOLVER', 'Обычный resolver бастиона/Web использует только BIND; нет подмены hosts или Firefox DoH.', 'Bastion/Web odatiy resolver faqat BIND dan foydalanadi; hosts yoki Firefox DoH bilan almashtirilmaydi.')
C('WEB03_NAMED_HTTP', 'С бастиона HTTP по имени profile и заданному пути возвращает 200 и правильный текст.', 'Bastiondan profile nomi va belgilangan path orqali HTTP 200 hamda to‘g‘ri matn qaytadi.')
C('WEB03_DB_NAME', 'Обычный resolver Web разрешает имя DB profile в 10.20.2.20.', 'Web odatiy resolver profile DB nomini 10.20.2.20 ga yechadi.')
C('WEB03_FORWARD_ONLY', 'Forward only направлен только на 10.20.0.2; внешнее DNS-имя разрешается. Внешний HTTP не нужен.', 'Forward only faqat 10.20.0.2 ga yo‘naltirilgan; tashqi DNS nomi yechiladi. Tashqi HTTP shart emas.')
C('WEB03_NXDOMAIN', 'Новое отсутствующее имя этого запуска получает авторитетный NXDOMAIN.', 'Shu ishga tushirishdagi yangi mavjud bo‘lmagan nom vakolatli NXDOMAIN oladi.')
C('WEB03_CLIENT_ACL', 'Query/recursion/cache разрешены только localhost, бастиону и Web в BIND; одного SG недостаточно.', 'BIND query/recursion/cache faqat localhost, bastion va Web ga ruxsat; SG ning o‘zi yetmaydi.')
C('WEB03_AXFR_DENIED', 'AXFR с бастиона/Web явно отклоняется при успешных обычных запросах того же запуска; таймаут не подходит.', 'Ayni tekshiruv oddiy so‘rovlari o‘tgan holda bastion/Web AXFR aniq rad etiladi; timeout yetmaydi.')
C('WEB04_MARKER_CONTENT', 'Путь, личный Lab ID, task и точный текст marker соответствуют заданию.', 'Marker path, shaxsiy Lab ID, task va aniq matn topshiriqqa mos.')
C('WEB04_MARKER_PERMISSIONS', 'Файл root:root 0644, его родительский каталог root:root 0755.', 'Fayl root:root 0644, ota katalog root:root 0755.')
C('WEB04_STOP_START_RETENTION', 'Доказаны три стадии stop/start: те же instance/volume/hash, новый boot_id и отдельно наблюдённый stopped.', 'Stop/start uch bosqichi isbotlangan: ayni instance/volume/hash, yangi boot_id va alohida kuzatilgan stopped.')
C('WEB05_CLUSTER_ACTIVE', 'PostgreSQL 16/main работает (active).', 'PostgreSQL 16/main ishlaydi (active).')
C('WEB05_CLUSTER_CONFIG', 'Настройки 16/main, стандартный data directory и socket/peer для OS postgres корректны.', '16/main sozlamasi, standart data directory va OS postgres socket/peer to‘g‘ri.')
C('WEB05_LISTEN_5432', 'PostgreSQL слушает 10.20.2.20:5432.', 'PostgreSQL 10.20.2.20:5432 da tinglaydi.')
C('WEB05_DATABASE_OWNER', 'Владельцем БД и schema public является соответствующая setup-role.', 'DB va public schema egasi tegishli setup role.')
C('WEB05_ROLE_ATTRIBUTES', 'Runtime LOGIN; нет superuser/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS и повышающих membership. Setup LOGIN при сборке или NOLOGIN после неё.', 'Runtime LOGIN; superuser/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS va huquq oshiruvchi membership yo‘q. Setup qurishda LOGIN yoki tugagach NOLOGIN.')
C('WEB05_HBA_SCRAM', 'HBA допускает SCRAM лишь для перечисленных DB/role с Web /32, без широких разрешений.', 'HBA faqat ko‘rsatilgan DB/role va Web /32 uchun SCRAM ga ruxsat beradi; keng ruxsat yo‘q.')
C('WEB05_WEB_SQL', 'Новый аутентифицированный SELECT с Web возвращает нужные DB/user/значение; P по IP, M через обычный DNS.', 'Web dan yangi autentifikatsiyali SELECT kerakli DB/user/qiymatni qaytaradi; P IP bilan, M odatiy DNS orqali.')
C('WEB05_BAD_PASSWORD_DENIED', 'Один неверный пароль явно отклонён в том же запуске, где правильный работает.', 'To‘g‘ri parol ishlagan ayni tekshiruvda bitta noto‘g‘ri parol aniq rad etiladi.')
C('WEB05_WRONG_TARGET_DENIED', 'С Web запрещены postgres-role, посторонняя DB и чужой profile; ещё не созданная practice DB не обязательна.', 'Web dan postgres role, begona DB va boshqa profile taqiqlangan; hali yaratilmagan practice DB majburiy emas.')
C('WEB06_ARTIFACTS', 'Код и зависимости точно соответствуют предоставленной фиксированной версии.', 'Kod va bog‘liqliklar berilgan aniq versiyaga mos.')
C('WEB06_SERVICE', 'jdu-catalog active и enabled, работает как catalog.', 'jdu-catalog active va enabled, catalog nomidan ishlaydi.')
C('WEB06_LOOPBACK', 'Gunicorn слушает только 127.0.0.1:8000.', 'Gunicorn faqat 127.0.0.1:8000 da tinglaydi.')
C('WEB06_PROFILE_DATABASE', 'Активный процесс использует DB и runtime-role нужного profile.', 'Faol process kerakli profile DB va runtime role dan foydalanadi.')
C('WEB06_MIGRATIONS', 'Фиксированные migrations, 11 таблиц и нужные sequence находятся в выбранной БД.', 'Belgilangan migrations, 11 jadval va zarur sequence tanlangan DB da mavjud.')
C('WEB06_REQUIRED_RECORDS', 'Обе обязательные записи совпадают с параметрами profile; дополнительные допустимые записи разрешены.', 'Ikkala majburiy yozuv profile qiymatlariga mos; boshqa to‘g‘ri yozuvlar mumkin.')
C('WEB06_PUBLIC_DATA', 'Обычный публичный URL получает правильные записи из действующей БД.', 'Odatiy ochiq URL ishlayotgan DB dan to‘g‘ri yozuvlarni oladi.')
C('WEB06_ADMIN_ENTRY', 'С бастиона через обычный DNS доступна настоящая форма /admin/ на admin.lab.test:8080.', 'Bastiondan odatiy DNS orqali admin.lab.test:8080/admin/ haqiqiy login shakli ochiladi.')
C('WEB06_STATIC', 'Static-ресурсы доступны по предусмотренному маршруту.', 'Static resurslar belgilangan yo‘l orqali ochiladi.')
C('WEB06_PASSWORD_LOGIN', 'Функциональный режим проходит настоящий password/CSRF/cookie login, без обхода аутентификации.', 'Funksional rejim haqiqiy password/CSRF/cookie login dan o‘tadi, autentifikatsiya chetlab o‘tilmaydi.')
C('WEB06_CREATE_REFLECT', 'В этом запуске через admin HTTP создана одна CK-запись; значения совпали в DB и публичной странице.', 'Shu tekshiruvda admin HTTP orqali bitta CK yozuv yaratilib, DB va ochiq sahifa qiymatlari mos keladi.')
C('WEB06_EDIT_REFLECT', 'Количество именно этой CK-записи изменено; DB и публичная страница подтверждают изменение.', 'Aynan shu CK yozuv miqdori o‘zgartiriladi; DB va ochiq sahifa o‘zgarishni tasdiqlaydi.')
C('WEB06_LOGOUT', 'POST logout завершает сессию: прежний cookie снова требует входа.', 'POST logout session ni tugatadi: eski cookie bilan yana login talab etiladi.')
C('WEB07_PUBLIC_ADMIN_DENIED', 'Публичный порт 80 не открывает admin даже с поддельными Host/header; частный путь при этом работает.', 'Ochiq 80 soxta Host/header bilan ham admin ni ochmaydi; private yo‘l esa ishlaydi.')
C('WEB07_SECRET_PERMISSIONS', 'Секреты — обычные root:root 0600 файлы, без ссылок и раскрытия значений.', 'Maxfiy fayllar oddiy root:root 0600, link va qiymat ochilishi yo‘q.')
C('WEB07_CODE_PROTECTED', 'catalog без login/sudo не может менять код, venv и их управляющие каталоги.', 'Login/sudo siz catalog kod, venv va ularning boshqaruv kataloglarini o‘zgartira olmaydi.')
C('WEB07_SECRET_HTTP_DENIED', 'Проверяемые env/секретные пути не доступны через HTTP или static.', 'Tekshiriladigan env/maxfiy path lar HTTP yoki static orqali ochilmaydi.')
C('WEB07_SETUP_RETIRED', 'Setup-role NOLOGIN/password NULL, её сессии закрыты, временные setup.env удалены.', 'Setup role NOLOGIN/password NULL, session lari yopilgan, vaqtinchalik setup.env lar o‘chirilgan.')
C('WEB07_ITEM_PRIVILEGES', 'catalog_item: только SELECT/INSERT/UPDATE, без DELETE, TRUNCATE и передачи прав.', 'catalog_item: faqat SELECT/INSERT/UPDATE; DELETE, TRUNCATE va huquq uzatish yo‘q.')
C('WEB07_AUTH_USER_PRIVILEGES', 'auth_user: SELECT и UPDATE только last_login/password, без создания/удаления пользователей.', 'auth_user: SELECT va faqat last_login/password UPDATE; user yaratish/o‘chirish yo‘q.')
C('WEB07_AUTH_LOOKUP_PRIVILEGES', 'Таблицы групп, permissions, связей и content type доступны только для SELECT.', 'Guruh, permission, bog‘lanish va content type jadvallari faqat SELECT uchun.')
C('WEB07_SESSION_PRIVILEGES', 'django_session: только необходимые SELECT/INSERT/UPDATE/DELETE, без лишних прав.', 'django_session: faqat kerakli SELECT/INSERT/UPDATE/DELETE; ortiqcha huquq yo‘q.')
C('WEB07_AUDIT_PRIVILEGES', 'django_admin_log: только SELECT/INSERT.', 'django_admin_log: faqat SELECT/INSERT.')
C('WEB07_MIGRATION_PRIVILEGES', 'У runtime нет прав на django_migrations, schema CREATE, владения объектами и незаданных дополнительных прав.', 'Runtime da django_migrations huquqi, schema CREATE, obyekt egaligi va belgilanmagan qo‘shimcha huquq yo‘q.')
C('WEB07_SEQUENCE_PRIVILEGES', 'USAGE только sequence оборудования и admin-log; без лишних SELECT/UPDATE/GRANT.', 'USAGE faqat jihoz va admin-log sequence lariga; ortiqcha SELECT/UPDATE/GRANT yo‘q.')
C('WEB07_ADMIN_PERMISSIONS', 'Активный staff, не superuser: только view/add/change оборудования, без delete/user management.', 'Faol staff, superuser emas: faqat jihoz view/add/change; delete/user management yo‘q.')
C('WEB07_ANONYMOUS_DENIED', 'Анонимные добавление/изменение отклонены без изменения БД при успешном контрольном login; одного CSRF-403 мало.', 'Nazorat login o‘tgan holda anonim add/change DB ni o‘zgartirmay rad etiladi; faqat CSRF-403 yetmaydi.')
C('WEB07_BAD_PASSWORD_DENIED', 'Один неверный пароль приложения отклонён, при этом правильный login работает.', 'Bitta noto‘g‘ri app paroli rad etiladi, ayni paytda to‘g‘ri login ishlaydi.')
C('WEB07_PRIVATE_DATA_HIDDEN', 'Все найденные непубличные коды скрыты на публичной странице при доступной БД.', 'DB ishlagan holda topilgan barcha yopiq kodlar ochiq sahifada ko‘rinmaydi.')

# Student-facing descriptions. Keys are the canonical checks used by the portal.
JA = {
    'WEB02_NGINX_ACTIVE': 'WebサーバーでNginxが起動している。',
    'WEB02_CONFIG_VALID': 'Nginxの設定が構文検査に通る。',
    'WEB02_LISTEN_80': 'NginxがWebサーバーの内部IPでTCPの80番ポートへの接続を受け付ける。',
    'WEB02_FILE': '配信用の `/var/www/html/mission.txt` が通常のファイルで、本文・所有者・権限が指定どおりになっている。',
    'WEB02_LOCAL_HTTP': 'Webサーバー自身から `127.0.0.1` の `/mission.txt` を開くと、HTTP 200と指定の本文が返る。',
    'WEB02_BASTION_HTTP': '踏み台サーバーから `10.20.1.20` の `/mission.txt` を開くと、HTTP 200と指定の本文が返る。',
    'WEB02_PUBLIC_HTTP': 'Webサーバーの公開IPで `/mission.txt` を開くと、HTTP 200と指定の本文が返る。',
    'WEB02_ACCESS_LOG': '確認時の `/mission.txt` へのリクエストがNginxのアクセスログに残る。',
    'WEB03_SERVICE': 'DNSサーバーでBINDが起動している。',
    'WEB03_CONFIG_VALID': 'BINDの設定と `lab.test` のゾーンファイルが構文検査に通る。',
    'WEB03_ZONE_AUTHORITY': '内部DNSが `lab.test` の情報を保持し、指定どおりのSOA・NSレコードを返す。',
    'WEB03_REQUIRED_RECORDS': '表の6件の名前が、すべて指定の内部IPアドレスになる。',
    'WEB03_UDP_RESPONSE': '踏み台サーバーとWebサーバーの両方が、UDPの53番ポートでDNSの回答を得られる。',
    'WEB03_TCP_RESPONSE': '踏み台サーバーとWebサーバーの両方が、TCPの53番ポートでDNSの回答を得られる。',
    'WEB03_NORMAL_RESOLVER': '踏み台サーバーとWebサーバーが通常の名前解決で内部DNSだけを使う。',
    'WEB03_NAMED_HTTP': '踏み台サーバーから `http://web.lab.test/mission.txt` を開くと、HTTP 200とM1の本文が返る。',
    'WEB03_DB_NAME': 'Webサーバーの通常の名前解決で、`db.lab.test` が `10.20.2.20` になる。',
    'WEB03_FORWARD_ONLY': '外部の名前は `10.20.0.2` だけに転送して解決できる。',
    'WEB03_NXDOMAIN': '`lab.test` の未登録名を問い合わせると、存在しないことを示す `NXDOMAIN` が返る。',
    'WEB03_CLIENT_ACL': 'BINDが問い合わせ・再帰問い合わせ・キャッシュの利用を、DNSサーバー自身・踏み台・Webサーバーに限って許可する。',
    'WEB03_AXFR_DENIED': '踏み台・Webサーバーからの通常の問い合わせは成功し、ゾーンの一括転送（AXFR）は明示的に拒否される。',
    'WEB05_CLUSTER_ACTIVE': 'DBサーバーでPostgreSQLの `16/main` が動作している。',
    'WEB05_CLUSTER_CONFIG': '`16/main` が標準のデータ保存先を使い、サーバー内ではOSユーザー `postgres` がローカル接続して管理できる。',
    'WEB05_LISTEN_5432': 'PostgreSQLが `10.20.2.20:5432` で接続を待ち受けている。',
    'WEB05_DATABASE_OWNER': '課題用DBとその `public` スキーマの所有者が `catalog_setup` になっている。',
    'WEB05_ROLE_ATTRIBUTES': '`catalog_app` はログインできる。両ロールに管理者権限や、ロールの所属を通じた権限昇格がない。',
    'WEB05_HBA_SCRAM': 'Webサーバーから課題用DBと指定ロールへの接続だけを、SCRAM認証で許可する。',
    'WEB05_WEB_SQL': 'Webサーバーから `db.lab.test` に `catalog_app` で接続し、課題用DBで指定のSELECTが成功する。',
    'WEB05_BAD_PASSWORD_DENIED': '正しいパスワードで接続でき、誤ったパスワードは拒否される。',
    'WEB05_WRONG_TARGET_DENIED': 'Webサーバーから許可外のデータベースやロールで接続しようとすると拒否される。',
    'WEB06_ARTIFACTS': '配備済みのアプリ本体と指定バージョンの依存パッケージを使用している。',
    'WEB06_SERVICE': 'アプリが専用のOSユーザー `catalog` で動作し、OS起動時の自動起動が有効になっている。',
    'WEB06_LOOPBACK': 'GunicornはWebサーバー内の `127.0.0.1:8000` だけで接続を受け付ける。',
    'WEB06_PROFILE_DATABASE': 'アプリが `db.lab.test` を使い、`catalog_app` で課題用DBに接続している。',
    'WEB06_MIGRATIONS': '配布されたマイグレーションを適用し、課題用DBに11個のテーブルと必要な採番の仕組みがある。',
    'WEB06_REQUIRED_RECORDS': '表の備品2件が、すべて指定された値で課題用DBに保存されている。',
    'WEB06_PUBLIC_DATA': '一般ページがHTTP 200を返し、公開備品の表示がDBの内容と一致する。',
    'WEB06_ADMIN_ENTRY': '踏み台サーバーから `http://admin.lab.test:8080/admin/` を開くと、管理画面のログインページが表示される。',
    'WEB06_STATIC': '一般ページと管理画面に必要なCSSなどが、それぞれの入口から取得できる。',
    'WEB06_PASSWORD_LOGIN': '指定のアプリ管理者が、管理画面にパスワードでログインできる。',
    'WEB06_CREATE_REFLECT': '管理画面で登録した確認用の備品がDBに保存され、一般ページにも反映される。',
    'WEB06_EDIT_REFLECT': '確認用備品の数量を管理画面から変更すると、DBと一般ページの表示が更新される。',
    'WEB06_LOGOUT': 'ログアウト後に管理画面を開き直すと、再びログインを求められる。',
    'WEB07_PUBLIC_ADMIN_DENIED': '公開の80番ポートでは管理用URLへのアクセスが拒否され、踏み台から8080番ポートの管理画面を開ける。',
    'WEB07_SECRET_PERMISSIONS': '秘密を含む設定ファイルは通常のファイルで、`root:root`・`0600` に設定されている。',
    'WEB07_CODE_PROTECTED': 'アプリの実行ユーザーは、コード・Python環境・親ディレクトリを変更できず、ログインやsudoもできない。',
    'WEB07_SECRET_HTTP_DENIED': '公開ページから、秘密を含むファイルをHTTPで取得できない。',
    'WEB07_SETUP_RETIRED': '構築用ロールはログイン不可で、パスワード・既存の接続・一時設定が残っていない。',
    'WEB07_ITEM_PRIVILEGES': '通常運用用ロールは備品を読める・追加できる・更新できる。削除と権限委譲は許可されていない。',
    'WEB07_AUTH_USER_PRIVILEGES': 'アカウントの表は読み取りと、最終ログイン・パスワードの列の更新だけが許可されている。',
    'WEB07_AUTH_LOOKUP_PRIVILEGES': 'グループや権限などを参照する表は、読み取りだけが許可されている。',
    'WEB07_SESSION_PRIVILEGES': 'ログイン状態を管理する表は、読み取り・追加・更新・削除が許可されている。',
    'WEB07_AUDIT_PRIVILEGES': '管理操作を記録する表は、読み取りと追加だけが許可されている。',
    'WEB07_MIGRATION_PRIVILEGES': '通常運用用ロールには、構造の適用履歴の表への権限、スキーマ内にオブジェクトを作る権限、アプリのDBオブジェクトの所有権がない。',
    'WEB07_SEQUENCE_PRIVILEGES': '備品と管理ログの採番に必要なシーケンスに、使用権限（USAGE）だけがある。',
    'WEB07_ADMIN_PERMISSIONS': 'アプリ管理者は備品を閲覧・追加・変更できる。備品の削除やユーザー・グループの管理はできない。',
    'WEB07_ANONYMOUS_DENIED': 'ログインしていない利用者による備品の登録・編集が拒否される。',
    'WEB07_BAD_PASSWORD_DENIED': '正しいパスワードでログインでき、誤ったパスワードではログインできない。',
    'WEB07_PRIVATE_DATA_HIDDEN': '一般ページには公開備品が表示され、非公開備品は表示されない。',
}

for check_id, description in JA.items():
    CHECKS[check_id]['ja'] = description

# Use the current portal's HTTP criteria for the current handbooks as well.
import json as _json
from pathlib import Path as _Path
_http_labels = _json.loads((_Path(__file__).resolve().parents[3] / 'development/web_portal_poc/web/check-labels.json').read_text(encoding='utf-8'))
for _lang in ('ja', 'ru', 'uz'):
    for _cid in ('WEB02_CONFIG_VALID', 'WEB02_FILE', 'WEB02_LOCAL_HTTP'):
        CHECKS[_cid][_lang] = _http_labels[_lang][_cid].replace('{file}', '/var/www/jdu-mission/mission.txt').replace('{root}', '/var/www/jdu-mission').replace('{path}', '/mission.txt')
