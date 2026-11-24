"""Numbered command explanations; executable source stays in content.py."""
import re
import shlex
from content import T

CONFIG_STEPS={('P2',2),('P2',3),('P2',6),('P4',2),('P4',3),('P5',9)}
PSQL_STEPS={('P4',6),('P6',1)}

def command_groups(source):
    """Keep quoted multiline values and pipelines as one copyable command."""
    pending=[]
    for line in source.splitlines():
        if not pending and (not line.strip() or line.lstrip().startswith('#')):
            yield False,line
            continue
        pending.append(line)
        try:shlex.split('\n'.join(pending))
        except ValueError:continue
        if line.rstrip().endswith('\\'):continue
        yield True,'\n'.join(pending)
        pending=[]
    assert not pending,'Incomplete command in source'

def explanation(command, lang):
    """Use operation-specific descriptions and the actual target, rather than a generic caption."""
    a=lambda ja,ru,uz:T(ja,ru,uz)[lang]
    args=shlex.split(command)
    if command.startswith('LAB_ID='):return a('教師から案内された自分のLab IDを変数へ入れる。','Записать свой Lab ID от преподавателя в переменную.','O‘qituvchi bergan o‘z Lab ID ni o‘zgaruvchiga yozish.')
    if command.startswith('COURSE_ID='):return a('使用する署名配布版のIDを変数へ入れる。','Указать ID используемого подписанного комплекта.','Ishlatiladigan imzolangan tarqatma ID sini belgilash.')
    if command.startswith('INSTALL='):return a('自分の配布版が導入されている保存先を変数へ入れる。','Сохранить путь к своему установленному комплекту.','O‘z tarqatmangiz o‘rnatilgan katalog yo‘lini saqlash.')
    if command.startswith('PUBLIC_WEB_IPV4='):return a('AWS画面で確認した現在のWeb公開IPv4を変数へ入れる。','Указать текущий public IPv4 Web из AWS Console.','AWS Console dagi joriy Web public IPv4 ni belgilash.')
    if command.startswith('QUERY='):return a('指定した2件を読むSQLを変数へ保存する。まだDBへ送らない。','Сохранить SELECT двух заданных записей; пока не отправлять в БД.','Belgilangan ikki yozuv uchun SELECT ni saqlash; hali DB ga yubormaslik.')
    if command.startswith('test -f '):return a('初期導入のファイルがあればINSTALL_OKを表示する。','Показать INSTALL_OK, если файл начальной установки существует.','Boshlang‘ich o‘rnatish fayli bo‘lsa INSTALL_OK chiqarish.')
    if args[0]=='aws':
        if args[1]=='sts':return a('現在操作中のAWSアカウント番号を表示する。','Показать номер текущего AWS account.','Joriy AWS hisob raqamini ko‘rsatish.')
        return a('CloudShellから指定EC2へSSM接続する。接続完了後に次へ進む。','Из CloudShell открыть SSM к выбранному EC2; дождаться подключения.','CloudShell dan tanlangan EC2 ga SSM ochish; ulanishni kutish.')
    if args[0]=='exit':return a('現在のサーバーへの接続を閉じ、CloudShellへ戻る。','Закрыть сеанс текущего сервера и вернуться в CloudShell.','Joriy server session ini yopib CloudShell ga qaytish.')
    if args[0]=='mstsc':return a('WindowsのRDP接続画面を開き、資格情報の入力を求める。','Открыть RDP Windows с запросом учётных данных.','Windows RDP ni hisob ma’lumotlarini so‘rash bilan ochish.')
    if args[:2]==['id','-un']:return a('この端末で操作しているOSユーザー名を表示する。','Показать имя пользователя ОС в этом терминале.','Shu terminaldagi OS user nomini ko‘rsatish.')
    if args[0]=='id':return a('catalogユーザーのUID・GID・所属グループを確認する。','Проверить UID, GID и группы пользователя catalog.','Catalog user UID, GID va guruhlarini tekshirish.')
    if args[0]=='hostname':return a('接続中のサーバーのホスト名を表示する。','Показать hostname подключённого сервера.','Ulangan server hostname ini ko‘rsatish.')
    if args[0]=='pwd':return a('現在の作業ディレクトリを表示する。','Показать текущий рабочий каталог.','Joriy ish katalogini ko‘rsatish.')
    if args[0]=='cd':
        target=args[1]
        return a(f'作業場所を {target} へ移す。',f'Перейти в рабочий каталог {target}.',f'Ish katalogini {target} ga o‘zgartirish.')
    if args[0]=='mkdir':return a('練習の作業ディレクトリを作る。既存ならそのまま使う。','Создать рабочий каталог; существующий сохранить.','Mashq katalogini yaratish; mavjud bo‘lsa saqlash.')
    if args[0]=='nano':return a('practice.txtを編集する。本文を入力し、保存して終了する。','Открыть practice.txt: ввести текст, сохранить и выйти.','Practice.txt ni ochish: matn yozish, saqlash va chiqish.')
    if args[0]=='printf':
        if 'p0-connection.txt' in command:return a('ホームディレクトリの確認用ファイルに web と1行書く。','Записать одну строку web в проверочный файл домашнего каталога.','Uy katalogidagi tekshiruv fayliga bitta web satrini yozish.')
        return a('自分のLab IDを含む練習用marker本文を作業ファイルへ書く。','Записать учебный marker со своим Lab ID в рабочий файл.','O‘z Lab ID bilan mashq marker matnini ish fayliga yozish.')
    if args[0]=='findmnt':return a('/var/libが載っているファイルシステムを調べる。','Определить файловую систему для /var/lib.','/var/lib joylashgan filesystem ni aniqlash.')
    if args[0]=='lsblk':return a('ディスクの名前・種類・容量・マウント先・識別情報を読む。','Показать имена, типы, размеры, точки монтирования и ID дисков.','Disk nomi, turi, hajmi, mount joyi va ID sini o‘qish.')
    if args[0]=='df':return a('/var/libの使用量と空き容量を確認する。','Проверить занятое и свободное место /var/lib.','/var/lib ishlatilgan va bo‘sh joyini tekshirish.')
    if args[0]=='sha256sum':return a('markerの内容を比較するためのSHA256を表示する。','Вычислить SHA256 marker для сравнения содержимого.','Marker mazmunini solishtirish uchun SHA256 chiqarish.')
    if args[0]=='pg_lsclusters':return a('PostgreSQLのversion・cluster・port・起動状態を読む。','Показать версию, кластер, порт и состояние PostgreSQL.','PostgreSQL version, cluster, port va holatini o‘qish.')
    if args[:2]==['resolvectl','dns']:return a('通常の名前解決に使うDNSサーバーを表示する。','Показать DNS-серверы системного resolver.','Odatiy resolver ishlatadigan DNS serverlarni ko‘rsatish.')
    if args[0]=='getent':
        if args[1]=='passwd':return a('catalogのホームとログインシェルを確認する。','Проверить home и login shell пользователя catalog.','Catalog user home va login shell ini tekshirish.')
        return a(f'通常のresolverで {args[-1]} のIPv4を調べる。',f'Получить IPv4 {args[-1]} через системный resolver.',f'Odatiy resolver orqali {args[-1]} IPv4 sini olish.')
    if args[0]=='dig':
        target=next(x for x in args[1:] if not x.startswith(('@','+')))
        if 'AXFR' in args:return a('zone全件の転送を要求し、明示的に拒否されるか調べる。','Запросить AXFR всей zone и проверить явный отказ.','Butun zone uchun AXFR so‘rab aniq rad etilishini tekshirish.')
        transport='TCP' if '+tcp' in args else 'UDP'
        return a(f'{transport} 53で {target} を問い合わせ、応答を読む。',f'Запросить {target} по {transport} 53 и прочитать ответ.',f'{transport} 53 orqali {target} ni so‘rab javobini o‘qish.')
    if args[0]=='curl':
        url=args[-1]
        return a(f'{url} へHTTP要求し、status・header・本文を表示する。',f'Отправить HTTP к {url}; показать статус, заголовки и тело.',f'{url} ga HTTP yuborib status, header va matnni ko‘rsatish.')
    if args[0]=='psql':return a('Webから指定DBへ既存パスワードで接続し、SELECT結果を読む。','Подключиться с Web к нужной БД с существующим паролем и выполнить SELECT.','Web dan kerakli DB ga mavjud parol bilan ulanib SELECT natijasini o‘qish.')
    if command.startswith('\\password '):
        role=args[-1]
        return a(f'psql内で {role} のパスワードを非表示入力する。',f'В psql скрыто задать пароль роли {role}.',f'Psql ichida {role} parolini yashirin kiritish.')
    if command.startswith('\\du'):return a('psql内で練習用DB roleの属性と権限を確認する。','В psql проверить атрибуты и права учебных ролей.','Psql ichida mashq DB role atribut va huquqlarini tekshirish.')
    if command.startswith('\\dp'):return a('psql内でpublic schemaのテーブル権限を読む。','В psql прочитать права таблиц схемы public.','Psql ichida public schema jadval huquqlarini o‘qish.')
    if command=='\\q':return a('psqlを終了し、同じDBサーバーのOS端末へ戻る。','Выйти из psql в терминал ОС того же DB-сервера.','Psql dan chiqib ayni DB server OS terminaliga qaytish.')
    # Inspect sudo operations without changing the original command.
    if args[0]=='sudo':
        if args[1:3]==['-u','postgres']:
            if '-c' not in args:return a('DBのOS端末からpostgresとしてpsqlを開く。以降はpsql内で操作する。','В терминале DB открыть psql от postgres; следующие действия внутри psql.','DB OS terminalida postgres sifatida psql ochish; keyingi amallar psql ichida.')
            sql=args[-1]
            if 'pg_hba_file_rules' in sql:return a('HBAの読込エラー行を調べる。正常なら0行。','Найти ошибки HBA; в норме 0 строк.','HBA xato qatorlarini topish; to‘g‘ri bo‘lsa 0 qator.')
            return a(f'postgresとしてDB設定を読む：{sql}',f'Прочитать настройку БД от postgres: {sql}',f'Postgres sifatida DB sozlamasini o‘qish: {sql}')
        args=args[1:]
    program=args[0]
    if program=='apt-get':
        if 'update' in args:return a('内部repoのパッケージ一覧を更新する。取得エラーは失敗扱いにする。','Обновить индекс пакетов внутреннего repo; считать ошибки загрузки сбоем.','Ichki repo package ro‘yxatini yangilash; yuklash xatosini xato deb olish.')
        names=' '.join(x for x in args[2:] if not x.startswith('-'))
        return a(f'内部repoから {names} を推奨追加なしで導入する。',f'Установить {names} из внутреннего repo без рекомендуемых дополнений.',f'Ichki repo dan {names} ni tavsiya etilgan qo‘shimchalarsiz o‘rnatish.')
    if program=='systemctl':
        verb=args[1];target=args[-1]
        return {
         'enable':a(f'{target} を今すぐ起動し、次回起動時も自動起動させる。',f'Запустить {target} сейчас и включить автозапуск.',f'{target} ni hozir yoqish va avtomatik start ni yoqish.'),
         'stop':a(f'{target} を停止してから使用する設定を選ぶ。',f'Остановить {target} перед выбором настроек.',f'Sozlamani tanlashdan oldin {target} ni to‘xtatish.'),
         'start':a(f'選んだ設定で {target} を起動する。',f'Запустить {target} с выбранными настройками.',f'{target} ni tanlangan sozlama bilan ishga tushirish.'),
         'restart':a(f'{target} を再起動して設定を読み直す。',f'Перезапустить {target} с обновлённой настройкой.',f'{target} ni yangi sozlama bilan qayta ishga tushirish.'),
         'reload':a(f'{target} を止めずに設定を再読込する。',f'Перечитать настройки {target} без остановки.',f'{target} ni to‘xtatmay sozlamani qayta o‘qish.'),
         'is-active':a(f'{target} の現在の起動状態を読む。',f'Прочитать текущее состояние {target}.',f'{target} joriy ish holatini o‘qish.'),
         'daemon-reload':a('配置したsystemd unitファイルを管理機能へ読み込ませる。','Перечитать установленные unit-файлы systemd.','Joylangan systemd unit fayllarini qayta o‘qitish.')
        }[verb]
    if program=='ss':return a('TCP待受のIP・port・対応プロセスを表示する。','Показать IP, порты и процессы слушающих TCP-сокетов.','TCP listen IP, port va jarayonlarini ko‘rsatish.')
    if program=='nginx':return a('Nginxの設定全体を表示する（秘密の値は共有しない）。','Показать полную конфигурацию Nginx; не передавать секреты.','Nginx to‘liq sozlamasini ko‘rsatish; maxfiy qiymatlarni ulashmaslik.') if '-T' in args else a('Nginx設定の構文と参照ファイルを検査する。','Проверить синтаксис и файлы конфигурации Nginx.','Nginx config sintaksisi va fayllarini tekshirish.')
    if program=='named-checkconf':return a('BINDの設定と参照zoneを構文検査する。','Проверить конфигурацию BIND и подключённые zone.','BIND config va ulangan zone sintaksisini tekshirish.')
    if program=='named-checkzone':return a('lab.testのzoneファイルを検査する。','Проверить zone-файл lab.test.','Lab.test zone faylini tekshirish.')
    if program=='netplan':return a('netplan YAMLから設定を生成し、適用前の構文を検査する。','Сгенерировать конфигурацию netplan и проверить YAML перед применением.','Netplan YAML dan config yaratib, qo‘llashdan oldin sintaksisni tekshirish.') if args[1]=='generate' else a('保存したnetplan設定をネットワークへ適用する。','Применить сохранённые настройки netplan к сети.','Saqlangan netplan sozlamasini tarmoqqa qo‘llash.')
    if program=='cat':
        if args[-1]=='/proc/sys/kernel/random/boot_id':return a('今回の起動を識別するboot IDを読み、停止前後の比較に使う。','Прочитать boot ID для сравнения загрузок до и после остановки.','To‘xtashdan oldin/keyin solishtirish uchun boot ID ni o‘qish.')
        return a(f'{args[-1]} の内容を変更せずに読む。',f'Прочитать {args[-1]} без изменения.',f'{args[-1]} mazmunini o‘zgartirmay o‘qish.')
    if program=='ls':return a(f'{args[-1]} に配置されたサーバー構築用ファイルを一覧する。',f'Показать файлы для настройки серверов в {args[-1]}.',f'{args[-1]} dagi serverlarni sozlash fayllarini ro‘yxatlash.')
    if program=='stat':return a('指定ファイルの所有者・グループ・権限・名前を読む。','Прочитать владельца, группу, права и имя указанных файлов.','Ko‘rsatilgan fayl owner, guruh, permission va nomini o‘qish.')
    if program=='cp':return a('元ファイルを控えへコピーする。既存の控えは上書きしない。','Скопировать исходный файл в резервную копию, не затирая существующую.','Asl fayldan nusxa olish; mavjud nusxani ustidan yozmaslik.') if '-an' in args else a('教員提供アプリを/optの運用先へ属性を保ってコピーする。','Скопировать приложение преподавателя в /opt с сохранением атрибутов.','O‘qituvchi app ini /opt ga atributlarini saqlab ko‘chirish.')
    if program=='mv':return a('既定サイトのリンクを控えへ移す。既存の控えは上書きしない。','Переместить ссылку стандартного сайта в копию без перезаписи.','Default sayt linkini nusxaga ko‘chirish; mavjud nusxani ustidan yozmaslik.')
    if program=='ln':return a('配置したアプリ用サイト設定への有効化リンクを作る。','Создать ссылку включения конфигурации сайта приложения.','App sayt sozlamasini yoqish uchun link yaratish.')
    if program=='install':
        if '-d' in args:return a('指定した所有者・グループ・権限でディレクトリを作る。','Создать каталог с указанными владельцем, группой и правами.','Belgilangan owner, guruh va permission bilan katalog yaratish.')
        return a('指定ファイルを配置し、所有者・グループ・権限を揃える。','Установить файл с нужными владельцем, группой и правами.','Faylni joylab owner, guruh va permission ni belgilash.')
    if program=='useradd':return a('ログイン用homeやshellを持たないアプリ専用catalogユーザーを作る。','Создать системного catalog для приложения без login shell и home.','App uchun login shell va home siz catalog tizim user ini yaratish.')
    if program=='tail':return a('access log末尾20行を読み、直前のHTTP要求を探す。','Прочитать последние 20 строк access log и найти свой HTTP-запрос.','Access log oxirgi 20 qatoridan oldingi HTTP so‘rovini topish.')
    if program=='rm':return a('表示して確認した2つの一時setup秘密ファイルだけを削除する。','Удалить только два проверенных временных секретных файла setup.','Tekshirilgan ikkita vaqtinchalik setup maxfiy faylini o‘chirish.')
    if program.startswith(('python','/opt/jdu-catalog/venv/bin/python')):
        if '-c' in args:return a('設置済みのJSONファイルからサーバーのロールを読み出す。','Прочитать только role из bootstrap, чтобы проверить выбранный сервер.','Bootstrap dan faqat role ni o‘qib, ulangan server vazifasini tekshirish.')
        if 'offline_assets.py' in command:return a('署名・hashを確認してアプリと固定wheelを教材領域へ展開する。','Проверить подпись/hash, подготовить приложение и фиксированные wheel.','Imzo/hash ni tekshirib app va belgilangan wheel larni tayyorlash.') if '--wheels' in args else a('固定hashを照合して教員提供アプリ・SQL資源を展開する。','Сверить фиксированный hash и распаковать приложение/SQL преподавателя.','Belgilangan hash ni tekshirib o‘qituvchi app/SQL resurslarini ochish.')
        if 'profile_sql.py' in command:
            stage=args[args.index('--profile')+2]
            actions={
              '01_create_roles.sql':T('練習用DB roleを作るSQL','SQL создания учебных ролей','Mashq DB role yaratish SQL i'),
              '02_prepare_schema.sql':T('練習用DBとschemaを作るSQL','SQL создания учебной БД и схемы','Mashq DB va schema yaratish SQL i'),
              '03_runtime_grants.sql':T('runtimeへ必要なSQL権限を与えるSQL','SQL необходимых прав runtime','Runtime uchun kerakli SQL huquqlari SQL i'),
              '04_disable_setup.sql':T('構築用roleのログインを無効にするSQL','SQL отключения входа setup','Setup role login ini o‘chirish SQL i')}
            action=actions[stage][lang]
            return a(f'{action}を生成し、postgres経由で指定DBへ適用する。',f'Сформировать {action} и применить через postgres к нужной БД.',f'{action} ni yaratib postgres orqali kerakli DB ga qo‘llash.') if '|' in args else a(f'{action}を表示する。まだ適用しない。',f'Показать {action} без выполнения.',f'{action} ni ko‘rsatish; hali qo‘llamaslik.')
        if 'database_secret.py' in command:return a('既存の練習用DBパスワードを非表示入力し、Web内だけに保存する。','Скрыто ввести существующий пароль учебной БД и сохранить только на Web.','Mavjud mashq DB parolini yashirin kiritib, faqat Web da saqlash.')
        if '-m' in args and args[args.index('-m')+1]=='venv':return a('アプリ専用のPython仮想環境を作る。','Создать отдельное Python venv приложения.','App uchun alohida Python venv yaratish.')
        if '-m' in args and args[args.index('-m')+1]=='pip':
            if args[-1]=='check':return a('導入済みPython依存パッケージの整合を検査する。','Проверить совместимость установленных Python-зависимостей.','O‘rnatilgan Python bog‘liqliklari mosligini tekshirish.')
            return a('固定lock/hashと内部wheelだけでPython依存を導入する。','Установить зависимости только из локальных wheel с lock/hash.','Python bog‘liqliklarini faqat ichki wheel va lock/hash bilan o‘rnatish.')
        if 'configuration.py' in command:
            if 'create-runtime' in args:return a('既存DBパスワードを非表示入力し、練習用runtime設定を作る。','Скрыто ввести существующий пароль БД и создать runtime practice.','Mavjud DB parolini yashirin kiritib, practice runtime config yaratish.')
            if 'activate' in args:return a('保存済みの練習用設定を、アプリが次に起動するときに使う設定として選ぶ。','Выбрать сохранённый учебный профиль для следующего запуска приложения.','Keyingi ishga tushirish uchun saqlangan mashq profilini tanlash.')
            if 'create-setup' in args:return a('既存構築用パスワードを非表示入力し、一時setup設定を作る。','Скрыто ввести существующий пароль setup и создать временную настройку.','Mavjud setup parolini yashirin kiritib, vaqtinchalik config yaratish.')
            return a('秘密の値を表示せずruntime設定の妥当性を検査する。','Проверить runtime-конфигурацию без вывода секретов.','Maxfiy qiymatlarni chiqarmay runtime config ni tekshirish.')
        if 'manage_secure.py' in command:
            return {
             'check':a('構築用設定でアプリの設定エラーを検査する。','Проверить ошибки приложения в режиме setup.','Setup rejimida app sozlama xatolarini tekshirish.'),
             'migrate':a('教員提供migrationを実行し、対象DBへ必要な表を作る。','Применить migrations преподавателя и создать таблицы нужной БД.','O‘qituvchi migration larini bajarib, kerakli DB jadvallarini yaratish.'),
             'seed_catalog':a('提供済みの固定初期データを練習用DBへ登録する。','Загрузить фиксированные начальные данные в учебную БД.','Belgilangan boshlang‘ich ma’lumotni mashq DB ga yozish.'),
             'create_lab_admin':a('アプリ管理者を作り、そのパスワードを非表示入力する。','Создать администратора приложения со скрытым вводом пароля.','App administratorini yaratib parolini yashirin kiritish.'),
             'collectstatic':a('runtime設定でCSS等の静的ファイルを配信先へ集める。','Собрать CSS и другую статику в каталог выдачи с runtime-настройкой.','Runtime config bilan CSS va static fayllarni tarqatish katalogiga yig‘ish.')
            }[args[-1]]
    raise ValueError('Missing explanation: '+command)

def annotated_blocks(module, index, source, lang):
    if (module,index) in CONFIG_STEPS:return [('text',source)]
    groups=list(command_groups(source));out=[];parts=[];number=0;psql=False
    for is_command,command in groups:
        if not is_command:parts.append(command);continue
        number+=1
        if (module,index) in PSQL_STEPS and command.startswith('\\') and not psql:
            out.append(('bash','\n'.join(parts)));parts=[];psql=True
        prefix='--' if psql else '#'
        parts += [f'{prefix} {number}. {explanation(command,lang)}',command]
    out.append(('sql' if psql else ('powershell' if (module,index)==('P0',5) else 'bash'),'\n'.join(parts)))
    return out

def executable_only(source):
    return '\n'.join(line for line in source.splitlines() if not re.match(r'^\s*(?:#|--) \d+\. ',line))
