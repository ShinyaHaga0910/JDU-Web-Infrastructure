"""Learning explanations added to the guided lab; commands and scoring stay shared."""
from content import T

LABELS = {
 'routes': T('完成像と通信経路', 'Система и пути соединений', 'Tayyor tizim va ulanish yo‘llari'),
 'read': T('操作例の読み方', 'Как читать шаги', 'Qadamlarni qanday o‘qish kerak'),
 'before': T('始める前の状態', 'Состояние перед началом', 'Boshlashdan oldingi holat'),
 'mechanism': T('仕組みを理解する', 'Как это работает', 'Bu qanday ishlaydi'),
 'meaning': T('コマンド・設定値の意味', 'Смысл команд и настроек', 'Buyruq va sozlamalar ma’nosi'),
 'reflect': T('理解の確認（採点外）', 'Проверка понимания (без баллов)', 'Tushunishni tekshirish (ballsiz)'),
 'answer': T('考え方', 'Объяснение', 'Izoh'),
 'output': T('出力の読み取り例（入力しない）', 'Пример чтения вывода (не вводить)', 'Natijani o‘qish namunasi (kiritmang)'),
 'plan': T('自力課題に取り組む前に', 'Перед самостоятельной работой', 'Mustaqil topshiriqdan oldin'),
}

READING = [
 T('各Pは「課題→仕組み→操作例→理解の確認」の順で使う。操作例は一つのまとまりを貼り付けず、1コマンドずつ実行して表示を読む。末尾のバックスラッシュは次の行へ続く記号なので、その行と次の行を一つのコマンドとして扱う。',
   'В каждом P идут задание, объяснение, шаги и вопросы. Выполняйте команды по одной и читайте результат, не вставляйте весь раздел сразу. Обратная косая черта в конце строки означает продолжение: эта и следующая строки составляют одну команду.',
   'Har P da topshiriq, tushuntirish, qadamlar va savollar bor. Butun bo‘limni birdan joylamang: har command ni alohida bajarib natijani o‘qing. Qator oxiridagi backslash davom etishni bildiradi: keyingi qator ham shu command ning qismidir.'),
 T('bash枠は表示された実行場所の端末へ入力する。text枠は設定ファイルの本文・psql内の入力・出力例などで、直前の説明に従う。行頭が#の説明行はコメント。自分の端末に出る$、#、postgres=#などのpromptをコマンドへ付け足さない。YOUR-から始まる値だけを自分の値へ置き換える。',
   'Блок bash вводится в терминале указанного узла. Блок text может содержать конфигурацию, ввод внутри psql или пример вывода: читайте пояснение перед ним. Строка с # - комментарий. Не добавляйте приглашение $ или postgres=# из своего терминала. Значения с YOUR- заменяйте своими.',
   'Bash blokini ko‘rsatilgan muhit terminaliga kiriting. Text bloki config matni, psql ichidagi kiritish yoki natija namunasi bo‘lishi mumkin; oldingi izohni o‘qing. # bilan boshlangan izoh comment hisoblanadi. Terminaldagi $ yoki postgres=# prompt ini command ga qo‘shmang. YOUR- qiymatlarini o‘zingiznikiga almashtiring.'),
 T('設定を作るときは「保存したファイル→構文検査→サービスへの反映→実際の通信」の順で確認する。ファイルの内容が正しくても、実行中のサービスが古い設定を使うことがある。画面表示だけでなく、HTTP応答・DNS回答・SQL結果とlogを対応させる。',
   'Проверяйте по порядку: сохранённый файл, синтаксис, применение к службе, реальное соединение. Правильный файл ещё не доказывает, что работающая служба уже использует его. Сопоставляйте HTTP-ответ, DNS-ответ или SQL-результат с журналом.',
   'Tekshirish tartibi: saqlangan fayl, sintaksis, service ga qo‘llash, haqiqiy ulanish. To‘g‘ri fayl ishlayotgan service yangi sozlamani ishlatayotganini hali isbotlamaydi. HTTP response, DNS answer yoki SQL natijasini log bilan solishtiring.'),
]

ROUTES = [
 ('Windows PC', 'Web public IPv4', 'TCP/80',
  T('一般利用。Internet Gatewayを通り、公開一覧と静的ファイルを読む。', 'Публичный доступ через Internet Gateway к каталогу и статическим файлам.', 'Internet Gateway orqali ochiq ro‘yxat va statik fayllarni ko‘rish.')),
 ('Windows PC', 'bastion public IPv4', 'TCP/3389',
  T('許可CIDRからRDPで入る。踏み台のデスクトップを操作する。', 'RDP из разрешённого CIDR к рабочему столу бастиона.', 'Ruxsatli CIDR dan RDP bilan bastion ish stoliga kirish.')),
 ('bastion', 'Web/DNS/DB/repo', 'TCP/22',
  T('内部SSHの管理経路。秘密鍵は踏み台内で保持する。', 'Внутренний SSH для управления; приватный ключ остаётся на бастионе.', 'Boshqarish uchun ichki SSH; private key bastion ichida qoladi.')),
 ('bastion / Web', 'DNS 10.20.2.10', 'UDP+TCP/53',
  T('lab.testの名前を解決する。DNSはWeb本文を返さない。', 'Разрешение имён lab.test. DNS не выдаёт содержимое Web-страницы.', 'lab.test nomlarini yechish. DNS Web sahifa mazmunini qaytarmaydi.')),
 ('Web app', 'DB 10.20.2.20', 'TCP/5432',
  T('アプリのDB roleでSQLを実行する。WindowsからDBへ直接接続しない。', 'SQL от роли приложения. Прямое соединение Windows с DB не используется.', 'App DB role bilan SQL bajaradi. Windows dan DB ga bevosita ulanish ishlatilmaydi.')),
 ('bastion', 'Web 10.20.1.20', 'TCP/8080',
  T('admin.lab.testの管理画面。公開80番の入口とは分ける。', 'Администрирование через admin.lab.test отдельно от публичного порта 80.', 'admin.lab.test admin oynasi; ochiq 80 portdan alohida.')),
 ('Nginx on Web', '127.0.0.1 on Web', 'TCP/8000',
  T('同じWeb内のアプリへ渡す。127.0.0.1は実行中のそのホスト自身。', 'Передача приложению на том же Web; 127.0.0.1 - текущий локальный узел.', 'Shu Web ichidagi app ga uzatish; 127.0.0.1 - ayni joriy host.')),
]

MISSION_PLAN = [
 T('まず完成要件から「どのサーバーの、どのファイル・名前・DB・roleを変えるか」を自分の作業表へ整理する。練習と本課題の値を比較し、Mで必要な対象だけを選ぶ。採点表は完成状態の条件であり、実行順のコマンド一覧ではない。',
   'Из требований выпишите, на каком сервере меняется файл, имя, БД или роль. Сравните значения P и M и выберите объекты задания M. Таблица проверок описывает требуемое состояние, а не порядок команд.',
   'Talablardan qaysi serverdagi file, nom, DB yoki role o‘zgarishini ish jadvaliga yozing. P va M qiymatlarini solishtirib M obyektlarini tanlang. Tekshiruv jadvali command tartibi emas, kerakli tayyor holatni bildiradi.'),
 T('次に「どこから何を確認すれば、要件を満たしたと分かるか」を考える。ファイルを確認する場所と、接続を試す場所は同じとは限らない。許可経路の成功と、制限すべき経路の拒否を分けて記録する。',
   'Затем решите, откуда и чем подтвердить каждое требование. Проверка файла и проверка соединения могут выполняться на разных узлах. Отдельно фиксируйте успех разрешённого пути и отказ запрещённого.',
   'Keyin har talabni qayerdan va nima bilan tekshirishni belgilang. Faylni ko‘rish joyi bilan ulanishni sinash joyi bir xil bo‘lmasligi mumkin. Ruxsatli yo‘l muvaffaqiyati va taqiqlangan yo‘l rad etilishini alohida yozing.'),
 T('ブラウザで課題を選んで確認し、結果と保存状態を読む。M5/M6の機能確認では既存アプリ管理者パスワードを非表示入力する。成績は自動保存される。理解の確認用メモやPの説明問題を、追加の成績要件にはしない。',
   'Выберите задание в браузере, проверьте результат и сохранение. Для функций M5/M6 скрыто введите существующий пароль администратора приложения. Оценки сохраняются автоматически. Вопросы на понимание и заметки не добавляют требований к оценке.',
   'Brauzerda topshiriqni tanlab natija va saqlash holatini tekshiring. M5/M6 funksiyalari uchun app administratorining mavjud parolini yashirin kiriting. Baholar avtomatik saqlanadi. Tushunish savollari va qaydlar bahoga qo‘shimcha talab emas.'),
]

MODULE_NOTES = {
 'P0': dict(
  after=T(
   '自分のAWSアカウント、各サーバーのロール、コマンドを実行する環境を確認する。',
   'Проверьте свой AWS-аккаунт, роль каждого сервера и среду выполнения команд.',
   'O‘z AWS hisobingizni, har bir server rolini va buyruq bajariladigan muhitni tekshiring.')),
 'P1': dict(
  before=T('Webは提供済みだが、練習用ファイルはまだ配信していない。', 'Web уже создан, но учебный файл ещё не выдаётся.', 'Web yaratilgan, ammo mashq fayli hali qaytarilmayapti.'),
  after=T('Nginxが公開80番でpractice.txtを返し、要求をlogへ残す。', 'Nginx выдаёт practice.txt на порту 80 и записывает запрос в журнал.', 'Nginx 80 portda practice.txt qaytarib, request ni log ga yozadi.'),
  mechanism=T('この練習では、URLの/practice.txtをWeb内の/var/www/html/practice.txtへ対応させる。最初の127.0.0.1での成功はWeb内部の確認で、踏み台やWindowsから届く証明にはならない。同じ本文を三つの位置から読み、どの経路まで正常かを切り分ける。[Nginxの一次資料](https://nginx.org/en/docs/beginners_guide.html)も参照。',
   'Путь URL /practice.txt соответствует файлу /var/www/html/practice.txt на Web. Успех через 127.0.0.1 проверяет только сам Web. Чтение того же текста с бастиона и Windows проверяет другие участки пути. См. [документацию Nginx](https://nginx.org/en/docs/beginners_guide.html).',
   'URL dagi /practice.txt Web ichidagi /var/www/html/practice.txt ga mos. 127.0.0.1 orqali muvaffaqiyat faqat Web ichini tekshiradi. Ayni matnni bastion va Windows dan o‘qish yo‘lning boshqa qismlarini tekshiradi. [Nginx hujjati](https://nginx.org/en/docs/beginners_guide.html).'),
  question=T('Web自身では200、踏み台からは接続失敗。本文を作り直す前に何を確認するか？', 'На Web ответ 200, а с бастиона соединение не проходит. Что проверить до изменения файла?', 'Web ichida 200, bastiondan ulanish ishlamaydi. Faylni qayta yozishdan oldin nimani tekshirasiz?'),
  answer=T('要求先IP・待受アドレスとport・踏み台からWebへの通信許可を調べる。本文の正否と到達性を分ける。', 'Адрес назначения, адрес/порт прослушивания и разрешение пути bastion → Web. Содержимое файла и доступность - разные проверки.', 'Manzil IP, listen address/port va bastion → Web ruxsatini tekshiring. Fayl mazmuni va yetib borish alohida tekshiruvdir.')),
 'P2': dict(
  before=T('P1のHTTPがIP指定で使える。DNSはこれから設定する。', 'HTTP из P1 работает по IP; DNS ещё предстоит настроить.', 'P1 HTTP IP orqali ishlaydi; DNS endi sozlanadi.'),
  after=T('BINDの練習名を、踏み台とWebの通常resolverから使える。', 'Учебные имена BIND доступны обычному резолверу бастиона и Web.', 'BIND mashq nomlari bastion va Web ning oddiy resolver idan ishlaydi.'),
  mechanism=T('DNSの仕事は名前への回答で、HTTP本文の配信ではない。lab.testのzoneはBINDが管理し、A recordはIPv4を返す。digで問い合わせ先を明示した確認と、getentやbrowserがOSの設定を使う確認を分ける。名前解決後のHTTP接続は別の通信である。[BINDの一次資料](https://bind9.readthedocs.io/en/v9.18.39/chapter3.html)。',
   'DNS отвечает на запрос имени, а не выдаёт Web-страницу. BIND ведёт зону lab.test; A-запись возвращает IPv4. Различайте dig с явным сервером и getent/браузер с настройками ОС. После DNS выполняется отдельное HTTP-соединение. [Документация BIND](https://bind9.readthedocs.io/en/v9.18.39/chapter3.html).',
   'DNS nom so‘roviga javob beradi, Web sahifani qaytarmaydi. BIND lab.test zone ni boshqaradi; A record IPv4 qaytaradi. Aniq DNS server bilan dig va OS sozlamalaridan foydalanuvchi getent/browser ni farqlang. DNS dan keyin alohida HTTP ulanish bo‘ladi. [BIND hujjati](https://bind9.readthedocs.io/en/v9.18.39/chapter3.html).'),
  question=T('dig @10.20.2.10は成功し、getentは失敗する。DNSのzoneだけが原因と言えるか？', 'dig @10.20.2.10 работает, а getent - нет. Обязательно ли ошибка в зоне?', 'dig @10.20.2.10 ishlaydi, getent ishlamaydi. Muammo albatta zone dami?'),
  answer=T('言えない。明示したDNSへの回答と、OSが通常選ぶresolverは別なので、Netplanとresolvectlの実効設定を確認する。', 'Нет. Явно выбранный DNS и обычный резолвер ОС могут различаться. Проверьте применённые настройки Netplan и resolvectl.', 'Yo‘q. Aniq tanlangan DNS bilan OS ning oddiy resolver i farq qilishi mumkin. Netplan va resolvectl ning amaldagi sozlamalarini tekshiring.')),
 'P3': dict(
  before=T('同じWebの元root EBS上にmarkerを保存できる。', 'Маркер можно сохранить на исходном корневом EBS того же Web.', 'Marker ni ayni Web ning asl root EBS ida saqlash mumkin.'),
  after=T('Webを停止・起動しても同じ保存内容が残ることを、停止前後の証拠で示す。', 'Сохранность после stop/start того же Web подтверждена данными до и после.', 'Ayni Web stop/start dan keyin mazmun saqlangani oldingi va keyingi dalil bilan ko‘rsatiladi.'),
  mechanism=T('起動中のメモリーとEBS上へ保存したファイルを区別する。今回は元root EBSを保持した同じWebのStop/Startを扱う。ファイルのhashとinstance/volume IDを比べ、boot IDの変化で新しい起動も確認する。自動割当のpublic IPv4は変わることがある。[EC2の停止・起動](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html)。',
   'Различайте оперативную память и сохранённый файл на EBS. Здесь выполняется Stop/Start того же Web с исходным EBS. Сравните хеш, instance/volume ID и изменение boot ID. Автоматический public IPv4 может измениться. [Остановка и запуск EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html).',
   'Ishlayotgan xotira bilan EBS ga saqlangan faylni farqlang. Bu yerda asl EBS saqlangan ayni Web Stop/Start qilinadi. Hash, instance/volume ID va boot ID o‘zgarishini solishtiring. Avtomatik public IPv4 o‘zgarishi mumkin. [EC2 stop/start](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html).'),
  question=T('起動後に同じ本文が読めれば、別のWebを作っても合格と言えるか？', 'Достаточно ли одинакового текста на новом Web для выполнения задания?', 'Yangi Web da bir xil matn chiqishi topshiriq uchun yetarlimi?'),
  answer=T('同じ元instanceとvolumeの保持も条件なので言えない。本文だけでなく、対象の連続性と停止状態の観測が必要。', 'Нет: нужны исходные instance и volume, а также наблюдение остановленного состояния.', 'Yo‘q: asl instance va volume saqlanishi hamda stopped holati kuzatilishi kerak.')),
 'P4': dict(
  before=T('DBサーバーにサーバー構築用ファイルがあり、WebからDBへ許可された経路を使う。', 'На DB-сервере есть файлы для настройки; используется разрешённый путь Web → DB.', 'DB serverda sozlash fayllari bor; Web → DB ruxsatli yo‘li ishlatiladi.'),
  after=T('練習DBとsetup/runtime roleを作り、Webから認証付きSQLを実行する。', 'Созданы учебная БД и роли setup/runtime; SQL с Web проходит с паролем.', 'Mashq DB va setup/runtime role yaratiladi; Web dan parol bilan SQL bajariladi.'),
  mechanism=T('接続には、通信の到達、DBの待受、HBAの許可、password、SQL権限がそれぞれ必要。ssm-userはOS userで、catalog_practice_appはDB roleである。HBAは上から最初に一致した行を使う。SQLへ接続できることと、tableを作成できることも別の権限である。[HBA](https://www.postgresql.org/docs/16/auth-pg-hba-conf.html)・[SQL権限](https://www.postgresql.org/docs/16/sql-grant.html)。',
   'Нужны сетевой доступ, прослушивание DB, разрешение HBA, пароль и SQL-права. ssm-user - пользователь ОС, catalog_practice_app - роль БД. В HBA применяется первая совпавшая строка. Возможность подключиться не означает право создавать таблицы. [HBA](https://www.postgresql.org/docs/16/auth-pg-hba-conf.html) и [права SQL](https://www.postgresql.org/docs/16/sql-grant.html).',
   'Tarmoq yo‘li, DB listen, HBA ruxsati, parol va SQL privilege alohida kerak. ssm-user - OS user, catalog_practice_app - DB role. HBA birinchi mos qatorni ishlatadi. Ulanish huquqi table yaratish huquqini anglatmaydi. [HBA](https://www.postgresql.org/docs/16/auth-pg-hba-conf.html) va [SQL privilege](https://www.postgresql.org/docs/16/sql-grant.html).'),
  question=T('psqlがpasswordを受け付けたのにtable作成が拒否される。必ずpasswordの誤りか？', 'Пароль принят, но CREATE TABLE запрещён. Обязательно ли неверен пароль?', 'Parol qabul qilinib CREATE TABLE rad etildi. Parol albatta xatomi?'),
  answer=T('認証とSQL権限は別。runtime roleの役割に合った拒否なら正常で、setup用の操作をruntimeへ追加しない。', 'Аутентификация и SQL-права различны. Для runtime отказ в setup-операции может быть правильным.', 'Authentication va SQL privilege boshqa-boshqa. Runtime uchun setup amalining rad etilishi to‘g‘ri holat bo‘lishi mumkin.')),
 'P5': dict(
  before=T('M2のDNSとP4の練習DBが現在動作する。', 'Сейчас работают DNS из M2 и учебная БД из P4.', 'M2 DNS va P4 mashq DB hozir ishlaydi.'),
  after=T('提供アプリをWeb内で動かし、公開一覧と踏み台限定の管理画面をDBへ接続する。', 'Предоставленное приложение на Web связывает каталог и управление с БД.', 'Tayyor app Web ichida ishlaydi; ochiq ro‘yxat va bastion admin oynasi DB ga ulanadi.'),
  mechanism=T('NginxがHTTPの入口、GunicornがPythonアプリを実行するプロセス、PostgreSQLがデータの保存先となる。静的ファイルのP1と異なり、一覧の内容はDBから取得する。venvはアプリ用Python環境、systemd unitは起動方法の定義である。ここでは提供コードを読みながら配置し、プログラムを書き直す必要はない。',
   'Nginx принимает HTTP, Gunicorn исполняет Python-приложение, PostgreSQL хранит данные. В отличие от статического P1, каталог получает содержимое из БД. Venv отделяет Python-среду приложения, unit systemd описывает запуск. Размещайте предоставленный код, переписывать программу не требуется.',
   'Nginx HTTP ni qabul qiladi, Gunicorn Python app ni ishlatadi, PostgreSQL ma’lumot saqlaydi. Statik P1 dan farqli ravishda ro‘yxat mazmuni DB dan olinadi. Venv app Python muhitini ajratadi; systemd unit ishga tushishni belgilaydi. Tayyor kodni joylaysiz, dasturni qayta yozish shart emas.'),
  question=T('公開一覧に非公開備品も表示された場合、HTTP200だけで正常と言えるか？', 'Можно ли считать ответ 200 правильным, если каталог показывает непубличную запись?', 'Ro‘yxatda private yozuv ham chiqsa, faqat HTTP 200 ni to‘g‘ri deb hisoblash mumkinmi?'),
  answer=T('言えない。HTTPの到達、DBの値、is_publicによる表示の分離をそれぞれ確認する。', 'Нет. Проверяйте доступность HTTP, значения БД и фильтрацию по is_public отдельно.', 'Yo‘q. HTTP yetib borishi, DB qiymati va is_public bo‘yicha ajratishni alohida tekshiring.')),
 'P6': dict(
  before=T('P5の練習アプリが動作し、初期構築用のsetup接続が残る。', 'Учебное приложение P5 работает; временный setup-доступ ещё существует.', 'P5 mashq app ishlaydi; vaqtinchalik setup ulanish hali mavjud.'),
  after=T('setupを終了し、通常アプリの成功と不要なアクセスの拒否を同時に確かめる。', 'Setup завершён; нормальная работа и отказы ненужного доступа проверены вместе.', 'Setup tugatiladi; odatiy app muvaffaqiyati va keraksiz kirish rad etilishi birga tekshiriladi.'),
  mechanism=T('作成時だけ必要なsetup権限と、運用中に必要なruntime権限を分ける。setup roleをNOLOGINにし、一時setup設定を削除しても、通常アプリはruntime接続で動くことが目標。公開80番・管理8080番・loopback8000番も別の境界である。どこか一つを閉じれば全体が安全と決めず、正規操作の成功と対象を限定した拒否を組にする。',
   'Разделите временные права setup и рабочие права runtime. После NOLOGIN и удаления временной настройки приложение должно работать через runtime. Публичный 80, административный 8080 и локальный 8000 - разные границы. Проверяйте успешную разрешённую операцию вместе с отказом конкретного ненужного доступа.',
   'Vaqtinchalik setup privilege va ish paytidagi runtime privilege ni ajrating. NOLOGIN va vaqtinchalik sozlama o‘chirilgach app runtime bilan ishlashi kerak. Ochiq 80, admin 8080 va loopback 8000 alohida chegara. Ruxsatli amal muvaffaqiyati bilan aniq keraksiz kirish rad etilishini birga tekshiring.'),
  question=T('setupを閉じた後、アプリも停止した。setupを再び公開することが完成か？', 'После закрытия setup приложение перестало работать. Нужно ли просто снова открыть setup?', 'Setup yopilgach app ham to‘xtadi. Setup ni qayta ochish tayyor yechimmi?'),
  answer=T('完成ではない。runtimeの接続設定・role・必要なtable権限を確認し、setupなしで正規機能が動く状態にする。', 'Нет. Проверьте runtime-настройку, роль и необходимые права таблиц; обычная работа должна обходиться без setup.', 'Yo‘q. Runtime config, role va kerakli table privilege ni tekshiring; normal ish setup siz ishlashi kerak.')),
}

STEP_NOTES = {}

def note(id, ja, ru, uz):
    STEP_NOTES[id] = T(ja, ru, uz)

note('P0.3',
 'RDPは踏み台の画面と入力を運ぶ。踏み台内Firefoxからの通信の送信元はWindowsではなく踏み台になる。日本語/英語などのキー配列はpasswordの記号入力にも影響するため、表示言語と配列を区別する。',
 'RDP передаёт экран и ввод бастиона. Запрос Firefox внутри RDP идёт от бастиона, а не Windows. Раскладка клавиатуры влияет на символы пароля; язык интерфейса и раскладка - разные настройки.',
 'RDP bastion ekrani va kiritishni uzatadi. RDP ichidagi Firefox request i Windows emas, bastiondan chiqadi. Klaviatura tartibi paroldagi belgilarga ta’sir qiladi; interfeys tili va keyboard layout alohida sozlamadir.')

note('P1.1',
 'apt-get updateは利用可能なpackage一覧を更新し、installは選んだpackageを導入する。--no-install-recommendsは推奨packageを追加しない指定。Signed-Byは許可した署名鍵の指定であり、repoへ接続できただけでは署名確認の成功にならない。',
 'Apt-get update обновляет список пакетов, install устанавливает выбранный пакет. --no-install-recommends исключает рекомендованные дополнения. Signed-By задаёт доверенный ключ: доступ к repo ещё не доказывает успешную проверку подписи.',
 'Apt-get update package ro‘yxatini yangilaydi; install tanlangan package ni o‘rnatadi. --no-install-recommends tavsiya etilgan qo‘shimchalarni o‘rnatmaydi. Signed-By ishonchli kalitni belgilaydi: repo ga ulanish imzo tekshirilganini hali isbotlamaydi.')
note('P1.2',
 'nanoで編集する自分の作業fileと、Nginxが読む配信用fileを分ける。installはここではpackage導入ではなく、コピー時にroot:rootと0644を指定するコマンド。0644では所有者だけが書け、他のuserは読める。末尾の改行も本文の一部となる。',
 'Разделите рабочий файл nano и файл выдачи Nginx. Здесь install копирует файл с владельцем root:root и режимом 0644, а не устанавливает пакет. Писать может владелец, остальные могут читать. Завершающий перевод строки входит в содержимое.',
 'Nano dagi ish fayli va Nginx o‘qiydigan faylni ajrating. Bu yerda install package o‘rnatmaydi: faylni root:root va 0644 bilan nusxalaydi. Faqat owner yozadi, boshqalar o‘qiydi. Oxirgi newline ham mazmunning qismidir.')
note('P1.3',
 'nginx -Tは読込対象の設定を表示し、-tは構文を検査する。systemctlのenableは次回起動時、--nowは現在の起動を指定する。設定ファイルの保存だけで終わらず、reload後のserviceと待受portを読む。',
 'Nginx -T выводит конфигурацию, -t проверяет синтаксис. В systemctl enable включает запуск при загрузке, --now запускает сейчас. После сохранения файла проверьте reload, состояние службы и порт.',
 'Nginx -T config ni ko‘rsatadi; -t sintaksisni tekshiradi. Systemctl enable keyingi boot da ishga tushishni, --now hozir ishga tushishni belgilaydi. Fayl saqlangach reload, service holati va portni tekshiring.')
note('P1.4',
 'curl -iは本文に加えてHTTP headerを表示する。127.0.0.1はこのWeb自身なので、この要求はInternetを通らない。HTTP200と指定本文の両方を読み、別ページの200を成功と取り違えない。',
 'Curl -i показывает HTTP-заголовки вместе с телом. Адрес 127.0.0.1 означает сам Web, запрос не идёт через Internet. Проверяйте и код 200, и заданный текст; ответ другой страницы не подходит.',
 'Curl -i body bilan HTTP header ni ham ko‘rsatadi. 127.0.0.1 ayni Web bo‘lib, request Internetdan o‘tmaydi. 200 kodi bilan belgilangan matnni birga tekshiring; boshqa sahifaning 200 javobi mos emas.')
note('P1.5',
 '同じcurlでも踏み台から実行すれば内部通信の検査になる。WindowsのbrowserからはWebの現在の公開IPを使う。10.20.1.20をWindows側へ入力して到達できないことと、Webの停止を同一視しない。',
 'Тот же curl с бастиона проверяет внутренний путь. В браузере Windows нужен текущий public IP Web. Недоступность 10.20.1.20 с Windows сама по себе не означает остановку Web.',
 'Ayni curl bastiondan bajarilsa ichki yo‘l tekshiriladi. Windows browser ida Web ning joriy public IP si kerak. Windows dan 10.20.1.20 ga yetib bo‘lmasligi Web to‘xtaganini anglatmaydi.')
note('P1.6',
 'access logでは時刻・要求path・statusを直前のcurlと対応させる。tailは末尾を読む操作で、logを書き換えない。exitで接続を終えたら、PCのブラウザでP1を確認する。',
 'Сопоставьте время, путь и статус в access log с недавним curl. Tail читает последние строки и не меняет журнал. После exit проверьте P1 в браузере PC.',
 'Access log dagi vaqt, path va status ni oldingi curl bilan solishtiring. Tail oxirgi qatorlarni o‘qiydi, log ni o‘zgartirmaydi. Exit dan keyin PC brauzerida P1 ni tekshiring.')

note('P2.1',
 'namedはBINDのservice名、named-checkconf等は設定を検査する道具である。cp -anの-nは同名の控えを上書きしない指定なので、再実行して最初の控えを失うことを防ぐ。',
 'Named - имя службы BIND; named-checkconf и другие команды проверяют конфигурацию. Опция -n в cp -an не перезаписывает существующую резервную копию при повторном запуске.',
 'Named - BIND service nomi; named-checkconf kabi vositalar config ni tekshiradi. Cp -an dagi -n takroriy bajarishda mavjud zaxira nusxa ustiga yozmaydi.')
note('P2.2',
 'allow-queryは問い合わせを受ける相手、allow-recursionは外部名の再帰処理を認める相手を指定する。lab.testの回答は自分のzone、外部名はforwarderへ渡す。ここでは接続元を踏み台・Web・localhostへ限定する。',
 'Allow-query задаёт клиентов запросов, allow-recursion - клиентов рекурсивного поиска. Имена lab.test берутся из своей зоны, внешние передаются forwarder. В этом Lab клиенты ограничены бастионом, Web и localhost.',
 'Allow-query so‘rov yuboruvchi client ni, allow-recursion tashqi nom uchun recursive qidiruv client ini belgilaydi. Lab.test o‘z zone idan, tashqi nom forwarder orqali olinadi. Client lar bastion, Web va localhost bilan cheklangan.')
note('P2.3',
 'zone宣言とzone本文は別ファイルへ保存する。guideはzone名を補ってguide.lab.testとなり、末尾ドット付きのdns.lab.test.は完全な名前。TTLはcache時間、SOAのserialはzone更新を識別する番号で、IPアドレスではない。',
 'Объявление зоны и её записи сохраняются в разные файлы. Guide дополняется до guide.lab.test; dns.lab.test. с точкой - полное имя. TTL задаёт время кеша, serial SOA - номер версии зоны, а не IP.',
 'Zone e’loni va record lar alohida fayllarga saqlanadi. Guide nomi guide.lab.test gacha to‘ldiriladi; nuqtali dns.lab.test. to‘liq nomdir. TTL cache vaqtini, SOA serial esa zone versiyasini bildiradi, IP ni emas.')
note('P2.4',
 '構文検査が成功してからserviceへ反映する。digの@は問い合わせ先DNSを指定する記号、AはIPv4のrecord種別。+tcpを付けた確認ではTCP53を使い、UDPで成功した場合とは別に読む。',
 'Применяйте настройку после успешной проверки синтаксиса. В dig знак @ задаёт DNS-сервер, A - тип записи IPv4. Проверка с +tcp использует TCP53 и рассматривается отдельно от UDP.',
 'Sintaksis tekshiruvi o‘tgach sozlamani qo‘llang. Dig dagi @ DNS serverni, A IPv4 record turini bildiradi. +tcp bilan TCP53 tekshiriladi; uni UDP muvaffaqiyatidan alohida o‘qing.')
note('P2.5',
 '存在する内部名・存在しない内部名・外部名・zone転送を別々に試す。存在しない名のNXDOMAINは正しい否定回答で、DNSへ届かないtimeoutとは異なる。AXFRはzone一括転送の要求で、このLabでは拒否されることを確かめる。',
 'Отдельно проверьте существующее внутреннее имя, отсутствующее имя, внешнее имя и перенос зоны. NXDOMAIN - корректный отрицательный ответ, не timeout. AXFR запрашивает всю зону; здесь перенос должен быть запрещён.',
 'Mavjud ichki nom, yo‘q nom, tashqi nom va zone transfer ni alohida sinang. NXDOMAIN to‘g‘ri manfiy javob, timeout emas. AXFR butun zone ni so‘raydi; bu Lab da rad etilishi kerak.')
note('P2.6',
 'このNetplan設定はDNSサーバー側ではなく、名前を使う踏み台とWebへ入れる。dhcp4はIPの取得を継続し、use-dns: falseはDHCPからのDNS採用を止める。addressesの名前解決先と、EC2自身のIPを混同しない。',
 'Этот Netplan нужен клиентам - бастиону и Web, а не DNS-серверу. Dhcp4 сохраняет получение IP, use-dns: false отключает принятие DNS от DHCP. Адрес DNS в addresses не является адресом самого EC2.',
 'Bu Netplan DNS serverga emas, client bo‘lgan bastion va Web ga yoziladi. Dhcp4 IP olishni davom ettiradi; use-dns: false DHCP DNS ni olishni to‘xtatadi. Addresses dagi DNS manzili EC2 ning o‘z IP si emas.')
note('P2.7',
 'netplan generateは設定の生成、applyは適用である。設定変更でSSMが切れた場合は同じinstanceへ接続し直す。resolvectlは選ばれたDNS、getentはOSの通常経路を読み、最後に名前指定のHTTPも確かめる。',
 'Netplan generate формирует конфигурацию, apply применяет её. При разрыве SSM подключитесь к тому же instance. Resolvectl показывает выбранный DNS, getent использует обычный путь ОС; затем проверяется HTTP по имени.',
 'Netplan generate config hosil qiladi; apply qo‘llaydi. SSM uzilsa ayni instance ga qayta ulaning. Resolvectl tanlangan DNS ni ko‘rsatadi; getent OS ning oddiy yo‘lini ishlatadi; oxirida nom bilan HTTP tekshiriladi.')
note('P2.8',
 'Firefoxの送信元は踏み台で、内部名guide.lab.testを使う。Windows側browserは同じ内部DNSを使う設定ではない。IPでの表示と名前での表示を比較し、P1のファイルが同じことを確認してから提出する。',
 'Firefox на бастионе использует внутреннее имя guide.lab.test. Браузер Windows не настроен на тот же внутренний DNS. Сравните доступ по IP и имени и проверьте тот же файл P1 перед отправкой.',
 'Bastion Firefox i ichki guide.lab.test nomini ishlatadi. Windows browser i ayni ichki DNS ga sozlanmagan. IP va nom orqali ko‘rinishni solishtirib, yuborishdan oldin ayni P1 fayl ekanini tekshiring.')

note('P3.1',
 'findmntはpathが載るfilesystem、lsblkはOSから見えるblock device、dfは空き容量を読む。それぞれ対象が違う。boot_idは今回の起動を識別し、保存ファイルのhashとは別の証拠になる。',
 'Findmnt показывает файловую систему пути, lsblk - блочные устройства, df - свободное место. Это разные наблюдения. Boot_id идентифицирует текущую загрузку, а хеш - содержимое файла.',
 'Findmnt path joylashgan filesystem ni, lsblk block device larni, df bo‘sh joyni ko‘rsatadi. Ular turli kuzatuvlar. Boot_id joriy boot ni, hash fayl mazmunini aniqlaydi.')
note('P3.2',
 'printfの%sへ自分のLAB_IDが入り、\\nは改行になる。>は自分の作業fileを書き出す指定。install -dは親directoryを作り、続くinstallはmarkerの所有者と権限を揃える。hashは本文の一致確認に使う。',
 'Printf подставляет LAB_ID вместо %s, \\n означает перевод строки. Символ > записывает рабочий файл. Install -d создаёт каталог, следующий install задаёт владельца и права маркера. Хеш проверяет совпадение содержимого.',
 'Printf %s o‘rniga LAB_ID qo‘yadi; \\n yangi qatordir. > ish fayliga yozadi. Install -d katalog yaratadi, keyingi install marker owner va permission ini belgilaydi. Hash mazmun bir xilligini tekshiradi.')
note('P3.3',
 '停止前記録は比較用の対象・起動・markerを保存する操作。ボタン自体はEC2を止めない。保存後にAWS Stopを行い、ブラウザとコマンドの証拠を混ぜない。',
 'Запись до остановки сохраняет узел, загрузку и marker для сравнения. Кнопка сама не останавливает EC2. Затем выполните AWS Stop; не смешивайте браузерные и командные доказательства.',
 'Oldingi holat tugmasi server, boot va marker ni solishtirish uchun saqlaydi, EC2 ni to‘xtatmaydi. Keyin AWS Stop bajaring; brauzer va buyruq dalillarini aralashtirmang.')
note('P3.4',
 'AWSコンソールで対象WebをStopし、stoppedになった段階をWeb Portalで記録する。SSMが切れたことだけを停止完了の証拠にしない。再起動やTerminateとは違う操作を選ぶ。',
 'В Console выполните Stop нужного Web; состояние stopped зафиксируйте в Web Portal. Разрыв SSM сам по себе не доказывает остановку. Stop отличается от reboot и Terminate.',
 'Console da kerakli Web ni Stop qiling; stopped holatini Web Portal da qayd eting. SSM uzilishi to‘xtashni o‘zi isbotlamaydi. Stop reboot va Terminate dan farq qiladi.')
note('P3.5',
 '同じWebをStartし、runningとSSM Onlineを待つ。checkerは保存済みの停止前証拠と現在を比べるので、起動後にmarkerを作り直して証拠を上書きしない。以降の外部閲覧には更新後のWeb公開IPを使う。',
 'Запустите тот же Web и дождитесь running/SSM Online. Checker сравнивает текущее состояние с сохранённым исходным; не пересоздавайте маркер после запуска. Для внешнего доступа далее используйте новый public IP Web.',
 'Ayni Web ni Start qilib running/SSM Online ni kuting. Checker joriy holatni saqlangan oldingi dalil bilan solishtiradi; start dan keyin marker ni qayta yaratmang. Keyingi tashqi kirishda Web ning yangi public IP sini ishlating.')

note('P4.1',
 'packageの導入と、DB内の教材データ作成は別の段階。pg_lsclustersでversion・cluster・port・状態を読む。sudo -u postgresはOS userをpostgresへ切り替えて1コマンドを実行し、-Xは個人のpsql設定を読み込まない指定である。',
 'Установка пакета и создание учебных объектов в БД - разные этапы. Pg_lsclusters показывает версию, кластер, порт и состояние. Sudo -u postgres запускает команду от системного postgres; -X отключает личную настройку psql.',
 'Package o‘rnatish va DB ichida o‘quv obyektlarini yaratish alohida bosqich. Pg_lsclusters version, cluster, port va holatni ko‘rsatadi. Sudo -u postgres command ni OS postgres bilan bajaradi; -X shaxsiy psql config ni o‘qimaydi.')
note('P4.2',
 'listen_addressesはDBが接続を受ける自分側のIPで、接続元の許可リストではない。password_encryptionは新しく設定するDB passwordの保存方式。設定を保存しただけでは、稼働中の待受や既存passwordが自動で変わった証拠にはならない。',
 'Listen_addresses задаёт локальный адрес прослушивания DB, а не список клиентов. Password_encryption задаёт формат для вновь устанавливаемых паролей. Сохранение файла не доказывает изменение работающего listener или прежних паролей.',
 'Listen_addresses DB tinglaydigan o‘z IP sini bildiradi, client ruxsat ro‘yxatini emas. Password_encryption yangi o‘rnatiladigan parol formatini belgilaydi. Faylni saqlash listener yoki eski parollar o‘zgarganini isbotlamaydi.')
note('P4.3',
 'HBAのhost行は「DB名・DB role・接続元・認証方式」の組で読む。10.20.1.20/32はWeb1台だけ。末尾のrejectより前へ必要な許可を置く。localのpeerはDB内のOS postgres用で、WebからのTCP password認証とは別の行である。',
 'Строка host задаёт сочетание БД, роли, адреса клиента и метода аутентификации. /32 у 10.20.1.20 означает только Web. Разрешающие строки должны быть раньше завершающего reject. Local peer для системного postgres отличается от TCP-входа с паролем.',
 'Host qatori DB, role, client address va authentication usuli birikmasidir. 10.20.1.20/32 faqat Web ni bildiradi. Kerakli ruxsatlar oxirgi reject dan oldin turadi. OS postgres uchun local peer TCP parolli kirishdan alohida.')
note('P4.4',
 'postgresql@16-mainは実際のclusterのservice。再起動後はservice・待受・SHOWの実効値を組み合わせて確認する。pg_hba_file_rulesでerrorの行が0件でも、対象clientが接続できるかは次の実通信で確かめる。',
 'Postgresql@16-main - служба нужного кластера. После restart сопоставьте состояние службы, listener и действующее значение SHOW. Отсутствие error в pg_hba_file_rules ещё не заменяет реальное соединение клиента.',
 'Postgresql@16-main kerakli cluster service idir. Restart dan keyin service, listener va SHOW amaldagi qiymatini birga tekshiring. Pg_hba_file_rules da error yo‘qligi haqiqiy client ulanishini almashtirmaydi.')
note('P4.5',
 'profile_sql.pyの最初の実行は生成SQLを読むだけ。|でpsqlへ渡した実行で初めてDBを変更する。--profile practiceは練習DB/roleを選び、ON_ERROR_STOP=1はSQLエラーの後へ処理が続くことを防ぐ。既存DBに同じ作成SQLを重ねない。',
 'Первый запуск profile_sql.py только показывает SQL. БД изменяется при передаче через | в psql. --profile practice выбирает учебные имена, ON_ERROR_STOP=1 останавливает обработку при SQL-ошибке. Не повторяйте создание в уже созданной БД.',
 'Profile_sql.py ning birinchi ishga tushishi faqat SQL ni ko‘rsatadi. | orqali psql ga uzatilganda DB o‘zgaradi. --profile practice mashq nomlarini tanlaydi; ON_ERROR_STOP=1 SQL xatosida to‘xtatadi. Mavjud DB da yaratishni takrorlamang.')
note('P4.6',
 'sudoから始まる行をOS端末へ入力し、その後の\\password・\\du・\\qをpsql内へ1行ずつ入れる。setupとappは別のDB roleなので、それぞれのpasswordを区別する。入力が表示されなくてもキー入力は受け付けられている。',
 'Строку sudo выполните в ОС, затем вводите \\password, \\du и \\q по одной строке внутри psql. Setup и app - разные роли БД, различайте их пароли. Отсутствие символов на экране при вводе пароля нормально.',
 'Sudo qatorini OS terminalida, keyingi \\password, \\du va \\q ni psql ichida bittadan kiriting. Setup va app boshqa DB role bo‘lib, parollarini farqlang. Parol kiritishda belgilar ko‘rinmasligi normal.')
note('P4.7',
 'psqlの-hは接続先、-UはDB role、-dはDB名、-Wはpasswordの入力要求、-cは実行するSQL。これはWeb側から実行する。SELECT結果のDB名とuser名で、意図した練習環境へ入ったことを確認する。名前で接続するときは、通常のDNSで得たIPへ同じ方法で接続する。',
 'В psql -h задаёт сервер, -U - роль БД, -d - БД, -W запрашивает пароль, -c задаёт SQL. Выполняйте на Web. Имена БД и пользователя в результате подтверждают подключение к учебному профилю. При подключении по имени IP берётся из системного DNS.',
 'Psql da -h serverni, -U DB role ni, -d DB nomini, -W parol so‘rashni, -c SQL ni belgilaydi. Web da bajaring. Natijadagi DB va user nomlari mashq profile ga ulanganini tasdiqlaydi. Nom bilan ulanganda IP tizim DNS idan olinadi.')
note('P4.8',
 'database_secret.pyは今設定したruntime passwordを再入力し、Web内の保護された設定へ保存する。新しいpasswordの生成や変更ではない。setup用やRDP用の値を入れず、catalog_practice_appの既存値を使う。',
 'Database_secret.py повторно принимает уже заданный runtime-пароль и сохраняет его в защищённой настройке Web. Это не создание и не смена пароля. Нужен пароль catalog_practice_app, не setup или RDP.',
 'Database_secret.py mavjud runtime parolini qayta olib Web dagi himoyalangan config ga saqlaydi. Bu yangi parol yaratish yoki almashtirish emas. Setup yoki RDP emas, catalog_practice_app ning mavjud parolini ishlating.')

note('P5.1',
 'P5ではDB名をIPへ手で置き換えず、M2で設定した通常DNSを使う。--wheelsは固定版のPython package資源を用意する指定で、アプリの起動ではない。公開資源と、次に自分が作る秘密設定を分けて扱う。',
 'P5 использует обычный DNS из M2, не заменяйте имя DB вручную на IP. --wheels подготавливает пакеты Python фиксированных версий, но не запускает приложение. Открытые файлы и создаваемые далее секретные настройки различаются.',
 'P5 M2 dagi oddiy DNS ni ishlatadi; DB nomini qo‘lda IP ga almashtirmang. --wheels belgilangan Python package resurslarini tayyorlaydi, app ni ishga tushirmaydi. Ochiq fayllar bilan keyingi maxfiy config ni ajrating.')
note('P5.2',
 'コードは/opt/jdu-catalog/app、Python環境は隣のvenvへ置く。--no-indexは外部package一覧を使わず、--find-linksはローカルwheelの場所、--require-hashesは期待hashとの一致を必須にする。最後のpip checkは導入後の依存関係を調べる。',
 'Код находится в /opt/jdu-catalog/app, Python-среда - в соседнем venv. --no-index отключает индекс пакетов, --find-links задаёт локальные wheel, --require-hashes требует совпадения хешей. Pip check проверяет зависимости после установки.',
 'Kod /opt/jdu-catalog/app da, Python muhiti yonidagi venv da. --no-index package index ni ishlatmaydi; --find-links local wheel joyini beradi; --require-hashes hash mosligini talab qiladi. Pip check o‘rnatilgach dependency ni tekshiradi.')
note('P5.3',
 'catalogはアプリを動かすOS service userで、DB roleのcatalog_practice_appとは別物。nologinは対話shellへ入らない指定で、serviceとして実行できない意味ではない。id catalogがすでに存在するなら、作成済みかを確認してから続ける。',
 'Catalog - системный пользователь службы, не роль БД catalog_practice_app. Nologin запрещает интерактивную оболочку, но не запуск службы. Если id catalog уже найден, сначала проверьте, не выполнялся ли шаг ранее.',
 'Catalog - OS service user, catalog_practice_app DB role idan boshqa. Nologin interaktiv shell ni cheklaydi, service ishlamaydi degani emas. Id catalog allaqachon bor bo‘lsa, avval qadam oldin bajarilganini tekshiring.')
note('P5.4',
 'runtime設定はアプリが通常使うDB接続と公開host名を持つ。PUBLIC_WEB_IPV4は現在の値を使う。create-runtimeで設定を保存し、activateでアプリが使う設定として選ぶ。checkは設定の妥当性、statは所有者と権限を確認する。',
 'Runtime-настройка содержит обычное соединение с БД и разрешённый публичный host. Используйте текущий PUBLIC_WEB_IPV4. Create-runtime сохраняет настройки, activate выбирает их для приложения, check проверяет настройки, stat показывает владельца и права.',
 'Runtime config odatiy DB ulanishi va ruxsatli public host ni saqlaydi. Joriy PUBLIC_WEB_IPV4 ni ishlating. Create-runtime sozlamani saqlaydi, activate uni ilova uchun tanlaydi, check sozlamani, stat esa egasi va huquqlarini tekshiradi.')
note('P5.5',
 'migrateはアプリ用tableの構造を作り、seed_catalogは初期データ、create_lab_adminはアプリ管理者を作る。管理者のpasswordはDBやRDPのpasswordとは別。ここだけsetup接続を使い、通常起動へその権限を引き継がない。',
 'Migrate создаёт структуру таблиц, seed_catalog - начальные записи, create_lab_admin - администратора приложения. Его пароль отличается от паролей DB и RDP. Setup используется для подготовки, а не обычного запуска.',
 'Migrate table tuzilishini, seed_catalog boshlang‘ich yozuvlarni, create_lab_admin app administratorini yaratadi. Uning paroli DB va RDP parolidan boshqa. Setup tayyorlash uchun, odatiy ishlash uchun emas.')
note('P5.6',
 'DB側へ戻り、作成済みtableに通常roleの権限を付ける。DBへ接続する権限と、table/sequenceを使う権限は別。練習profileのSQLを読んでから渡し、runtimeをsuperuserへ変更して解決しない。',
 'Вернитесь на DB и выдайте рабочей роли права на созданные таблицы. Подключение к БД и доступ к таблицам/sequence - разные права. Сначала прочитайте SQL practice; не решайте проблему превращением runtime в superuser.',
 'DB ga qaytib yaratilgan table lar uchun runtime privilege bering. DB ga ulanish va table/sequence ishlatish boshqa huquqlar. Avval practice SQL ni o‘qing; runtime ni superuser qilish bilan hal qilmang.')
note('P5.7',
 'collectstaticはアプリのCSS等を配信用の保存先へ集める。unit配置後のdaemon-reloadはsystemdにunit定義を読み直させる操作で、アプリ設定の編集とは異なる。待受8000はWeb内の127.0.0.1だけであることを読む。',
 'Collectstatic собирает CSS и другие статические файлы. Daemon-reload после установки unit перечитывает определение systemd, а не настройки приложения. Порт 8000 должен слушать только 127.0.0.1 внутри Web.',
 'Collectstatic CSS va boshqa statik fayllarni yig‘adi. Unit joylangach daemon-reload systemd ta’rifini qayta o‘qiydi, app config ni emas. 8000 port faqat Web ichidagi 127.0.0.1 da tinglashini tekshiring.')
note('P5.8',
 'sites-availableは保存した設定、sites-enabledのsymbolic linkは有効にする設定を指す。元defaultは控えへ移す。nginx -tが通ってからreloadし、アプリ追加後もP1の静的ファイルを配信できることを確認する。',
 'Sites-available хранит настройку, ссылка в sites-enabled включает её. Исходный default сохраняется отдельно. После nginx -t выполните reload и убедитесь, что статический файл P1 по-прежнему выдаётся.',
 'Sites-available config ni saqlaydi; sites-enabled dagi symbolic link uni yoqadi. Asl default alohida saqlanadi. Nginx -t dan keyin reload qilib, P1 statik fayli hamon qaytishini tekshiring.')
note('P5.9',
 '2件はcode・name・quantity・location・is_publicの組で区別する。is_publicは公開一覧に出すかというアプリ内の値で、SGの公開設定ではない。非公開の1件もDBへ保存し、公開一覧からは見えないことを確かめる。',
 'Две записи различаются полями code, name, quantity, location и is_public. Is_public управляет выдачей в каталоге, а не SG. Непубличная запись тоже должна храниться в БД, но отсутствовать в публичном списке.',
 'Ikki yozuv code, name, quantity, location va is_public bilan farqlanadi. Is_public app ro‘yxatidagi ko‘rinishni boshqaradi, SG ni emas. Private yozuv ham DB da saqlanadi, ammo ochiq ro‘yxatda ko‘rinmaydi.')
note('P5.10',
 'SELECTはDB内の値を読み、WHEREは対象の2件へ絞り、ORDER BYは表示順を揃える。追加の正当なrecordがあっても消さない。browserとSQLで同じ値を見ることで、単なる見た目のページではなくDBの実データを確認する。',
 'SELECT читает данные, WHERE выбирает две нужные записи, ORDER BY задаёт порядок. Другие корректные записи удалять не нужно. Сравнение браузера и SQL подтверждает реальные данные БД, а не только вид страницы.',
 'SELECT ma’lumot o‘qiydi; WHERE kerakli ikki yozuvni tanlaydi; ORDER BY tartib beradi. Boshqa to‘g‘ri yozuvlarni o‘chirmang. Browser va SQL ni solishtirish sahifa ko‘rinishini emas, haqiqiy DB qiymatini tasdiqlaydi.')
note('P5.11',
 '機能確認は設定ファイルの存在だけでなく、実際のHTTP操作とDB更新を確かめる。パスワード欄はアプリ管理者の既存値用で、RDPの値ではない。確認結果と保存状態を両方読む。',
 'Функциональная проверка проверяет HTTP-действия и обновление БД, а не только файл настройки. Поле предназначено для существующего пароля администратора приложения, не RDP. Читайте результат и статус сохранения.',
 'Funksional tekshiruv faqat config faylini emas, HTTP amallari va DB yangilanishini tekshiradi. Maydon RDP emas, app administratorining mavjud paroli uchun. Natija va saqlash holatini o‘qing.')

note('P6.1',
 '\\duはDB roleの属性、\\dpはtable等のアクセス権を読む。OSのls -lとは別の権限表である。setupとruntimeの役割を比較し、runtimeに構造変更の権限が不要な理由を考える。',
 '\\du показывает атрибуты ролей БД, \\dp - права объектов. Это не файловые права ls -l. Сравните setup и runtime и объясните, почему рабочей роли не нужны права изменения структуры.',
 '\\du DB role atributlarini, \\dp obyekt privilege larini ko‘rsatadi. Bu ls -l dagi file permission emas. Setup va runtime ni solishtirib, runtime ga tuzilmani o‘zgartirish huquqi nega kerak emasligini tushuntiring.')
note('P6.2',
 'NOLOGINはsetup roleの新しい直接loginを止める指定で、DBやtableの削除ではない。runtimeは残す。適用前のSQLを読んで対象がpracticeであることを確認し、続く通常アプリの成功も検査する。',
 'NOLOGIN запрещает новые прямые входы setup-роли, но не удаляет БД и таблицы. Runtime остаётся. Перед применением проверьте SQL профиля practice, затем подтвердите работу обычного приложения.',
 'NOLOGIN setup role ning yangi bevosita login ini to‘xtatadi, DB yoki table ni o‘chirmaydi. Runtime qoladi. Qo‘llashdan oldin SQL practice uchunligini tekshiring, keyin normal app ishlashini tasdiqlang.')
note('P6.3',
 'setup.envとpractice.setup.envは一時構築用で、app.envとruntime用DB設定は運用に必要。rmの対象は示した2ファイルだけ。activateは指定した保存済み設定を次回の起動に適用する。アプリが動作中、または一時setup設定が残っている間は切り替えられない。',
 'Setup.env и practice.setup.env временные; app.env и runtime-настройка DB нужны для работы. Rm относится только к двум указанным файлам. Activate выбирает сохранённый профиль для следующего запуска. Смена недоступна при работающем приложении или оставшихся временных настройках setup.',
 'Setup.env va practice.setup.env vaqtinchalik; app.env va runtime DB config ishlash uchun kerak. Rm faqat ko‘rsatilgan ikki faylga tegishli. Activate keyingi ishga tushirish uchun saqlangan profilni tanlaydi. Ilova ishlab turganda yoki vaqtinchalik setup sozlamasi qolganda profilni almashtirib bo‘lmaydi.')
note('P6.4',
 'このcurlは踏み台から公開側80番の振る舞いを確かめる。/は成功し、/admin/や秘密のpathは情報を返さないことを読む。接続できないという一つの症状だけでは、意図した拒否かservice停止かを判断できない。',
 'Этот curl с бастиона проверяет поведение публичного порта 80. Путь / должен работать; /admin/ и секретные пути не должны раскрывать данные. Один сбой соединения не отличает правильный запрет от остановки службы.',
 'Bu curl bastiondan ochiq 80 port xatti-harakatini tekshiradi. / ishlashi, /admin/ va maxfiy path lar ma’lumot bermasligi kerak. Bitta ulanish xatosi to‘g‘ri taqiq bilan service to‘xtashini farqlamaydi.')
note('P6.5',
 '正しい管理操作の成功と、誤password・setup・不要経路の拒否を一緒に確認する。拒否だけの成功で満点と考えない。P6を終えてからmission profileへ進み、checkerが自動でprofileを戻すとは考えない。',
 'Проверьте разрешённое управление вместе с отказами неверного пароля, setup и ненужных путей. Одних отказов недостаточно. Переходите к mission после P6; checker сам профиль назад не переключает.',
 'To‘g‘ri admin amalini xato parol, setup va keraksiz yo‘l rad etilishi bilan birga tekshiring. Faqat rad etish yetarli emas. P6 dan keyin mission profile ga o‘ting; checker profile ni o‘zi qaytarmaydi.')

OUTPUT_EXAMPLES = {
 'P1': ('HTTP/1.1 200 OK\n\nJDU WEB-02 practice: HTTP response verified.',
  T('上は説明用に必要な行だけを抜き出した例。実際には日時などのheaderが加わる。200と本文を読み、access logのpath/statusとも照合する。',
    'Показаны только нужные строки; реальный ответ содержит и другие заголовки. Проверьте 200, текст и путь/статус в access log.',
    'Faqat kerakli qatorlar ko‘rsatilgan; haqiqiy javobda boshqa header lar ham bor. 200, matn va access log dagi path/status ni tekshiring.')),
 'P2': ('status: NOERROR\nguide.lab.test.  300  IN  A  10.20.1.20',
  T('dig出力の説明用抜粋。Aの右が回答IPv4、300がTTL。回答が出ても、問い合わせ先SERVERが10.20.2.10かを別に確認する。',
    'Сокращённый пример dig: после A стоит IPv4, 300 - TTL. Отдельно проверьте, что SERVER запроса - 10.20.2.10.',
    'Dig ning qisqa namunasi: A dan keyin IPv4, 300 esa TTL. So‘rov SERVER i 10.20.2.10 ekanini alohida tekshiring.')),
 'P4': ('current_database    | current_user         | value\njdu_catalog_practice | catalog_practice_app | 1',
  T('SELECT結果の読み方の例。列の幅や罫線は実際と異なってよい。DB名・role名・value=1を確認する。table編集の許可を証明する結果ではない。',
    'Пример чтения SELECT; ширина столбцов может отличаться. Сверьте БД, роль и value=1. Это не доказательство права менять таблицы.',
    'SELECT natijasini o‘qish namunasi; ustun kengligi boshqacha bo‘lishi mumkin. DB, role va value=1 ni tekshiring. Bu table o‘zgartirish huquqini isbotlamaydi.')),
}
