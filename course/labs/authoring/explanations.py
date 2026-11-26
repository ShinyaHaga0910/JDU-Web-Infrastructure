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
 T('まず各Practiceで作業することと図を読み、実行環境を確かめてから手順を進める。各コマンドは1つずつ実行し、表示を確かめる。行末のバックスラッシュは、コマンドが次の行に続くことを表す。',
   'Сначала прочитайте описание работы и схему Practice. Проверьте, где нужно выполнять шаги. Запускайте команды по одной и проверяйте вывод. Обратная косая черта в конце строки продолжает команду на следующей строке.',
   'Avval Practice tavsifi va diagrammasini o‘qing, so‘ng qadamlarni qayerda bajarishni tekshiring. Buyruqlarni bittadan bajarib, natijani ko‘ring. Qator oxiridagi teskari qiya chiziq buyruq keyingi qatorda davom etishini bildiradi.'),
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

MODULE_NOTES = {
 'P0': dict(
  after=T(
   '自分のAWSアカウント、各サーバーのロール、コマンドを実行する環境を確認する。',
   'Проверьте свой AWS-аккаунт, роль каждого сервера и среду выполнения команд.',
   'O‘z AWS hisobingizni, har bir server rolini va buyruq bajariladigan muhitni tekshiring.')),
 'P1': dict(
  after=T('NginxでTCPの80番ポートにHTTPを公開し、`/practice.txt` のリクエストにファイルの本文を返す。Webサーバー自身の端末と踏み台サーバーの端末からアクセスし、そのリクエストがNginxのアクセスログに残ることを確かめる。',
   'Настройте Nginx для выдачи текста файла по HTTP на TCP-порту 80 по пути `/practice.txt`. Выполните запросы из терминалов Web-сервера и бастиона, затем найдите их в журнале доступа Nginx.',
   'Nginx da HTTP uchun TCP 80 portini oching va `/practice.txt` so‘roviga fayl matnini qaytaring. Web serverning o‘z terminalidan va Bastion terminalidan so‘rov yuboring, so‘ng ularni Nginx access log ida tekshiring.'),
  question=T('Web自身では200、踏み台からは接続失敗。本文を作り直す前に何を確認するか？', 'На Web ответ 200, а с бастиона соединение не проходит. Что проверить до изменения файла?', 'Web ichida 200, bastiondan ulanish ishlamaydi. Faylni qayta yozishdan oldin nimani tekshirasiz?'),
  answer=T('要求先IP・待受アドレスとport・踏み台からWebへの通信許可を調べる。本文の正否と到達性を分ける。', 'Адрес назначения, адрес/порт прослушивания и разрешение пути bastion → Web. Содержимое файла и доступность - разные проверки.', 'Manzil IP, listen address/port va bastion → Web ruxsatini tekshiring. Fayl mazmuni va yetib borish alohida tekshiruvdir.')),
 'P2': dict(after=T("内部DNSにWeb・DBサーバーの名前を登録する。踏み台サーバーとWebサーバーがこのDNSを使うように設定し、P1のファイルを名前で開く。", "Запишите имена Web и DB во внутреннем DNS. Настройте бастион и Web на этот DNS и откройте файл P1 по имени.", "Ichki DNS ga Web va DB nomlarini yozing. Bastion va Web ni shu DNS ga sozlab, P1 faylini nom bilan oching.")),
 'P3': dict(
  before=T('同じWebの元root EBS上にmarkerを保存できる。', 'Маркер можно сохранить на исходном корневом EBS того же Web.', 'Marker ni ayni Web ning asl root EBS ida saqlash mumkin.'),
  after=T('Webを停止・起動しても同じ保存内容が残ることを、停止前後の証拠で示す。', 'Сохранность после stop/start того же Web подтверждена данными до и после.', 'Ayni Web stop/start dan keyin mazmun saqlangani oldingi va keyingi dalil bilan ko‘rsatiladi.'),
  mechanism=T('起動中のメモリーとEBS上へ保存したファイルを区別する。今回は元root EBSを保持した同じWebのStop/Startを扱う。ファイルのhashとinstance/volume IDを比べ、boot IDの変化で新しい起動も確認する。自動割当のpublic IPv4は変わることがある。[EC2の停止・起動](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html)。',
   'Различайте оперативную память и сохранённый файл на EBS. Здесь выполняется Stop/Start того же Web с исходным EBS. Сравните хеш, instance/volume ID и изменение boot ID. Автоматический public IPv4 может измениться. [Остановка и запуск EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html).',
   'Ishlayotgan xotira bilan EBS ga saqlangan faylni farqlang. Bu yerda asl EBS saqlangan ayni Web Stop/Start qilinadi. Hash, instance/volume ID va boot ID o‘zgarishini solishtiring. Avtomatik public IPv4 o‘zgarishi mumkin. [EC2 stop/start](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html).'),
  question=T('起動後に同じ本文が読めれば、別のWebを作っても合格と言えるか？', 'Достаточно ли одинакового текста на новом Web для выполнения задания?', 'Yangi Web da bir xil matn chiqishi topshiriq uchun yetarlimi?'),
  answer=T('同じ元instanceとvolumeの保持も条件なので言えない。本文だけでなく、対象の連続性と停止状態の観測が必要。', 'Нет: нужны исходные instance и volume, а также наблюдение остановленного состояния.', 'Yo‘q: asl instance va volume saqlanishi hamda stopped holati kuzatilishi kerak.')),
 'P4': dict(after=T("DBサーバーにPostgreSQLを設定し、Webサーバーから練習用DBへパスワードで接続する。", "Настройте PostgreSQL на DB-сервере и подключитесь к учебной БД с Web по паролю.", "DB serverda PostgreSQL ni sozlab, Web serverdan mashq DB siga parol bilan ulaning.")),
 'P5': dict(after=T("Webサーバーで備品管理アプリを起動し、DBサーバーにつなぐ。公開の一覧と、踏み台サーバーから使う管理画面を用意する。", "Запустите приложение на Web и подключите его к DB. Настройте публичный список и управление с бастиона.", "Web serverda jihozlar ilovasini ishga tushirib DB ga ulang. Ochiq ro‘yxat va Bastiondan boshqaruvni sozlang.")),
 'P6': dict(after=T("DBの初期設定用ロールのログインを止める。アプリが通常の権限で動き、公開側から管理画面や内部設定を開けないことを確かめる。", "Отключите вход роли настройки БД. Проверьте работу приложения с обычными правами и закрытие админки и настроек с публичного входа.", "DB sozlash roliga kirishni yoping. Ilovaning odatiy huquqlar bilan ishlashini va ochiq tomondan boshqaruv hamda sozlamalar yopilganini tekshiring.")),
}

STEP_NOTES = {}

def note(id, ja, ru, uz):
    STEP_NOTES[id] = T(ja, ru, uz)

note('P0.3',
 'RDPは踏み台の画面と入力を運ぶ。踏み台内Firefoxからの通信の送信元はWindowsではなく踏み台になる。日本語/英語などのキー配列はpasswordの記号入力にも影響するため、表示言語と配列を区別する。',
 'RDP передаёт экран и ввод бастиона. Запрос Firefox внутри RDP идёт от бастиона, а не Windows. Раскладка клавиатуры влияет на символы пароля; язык интерфейса и раскладка - разные настройки.',
 'RDP bastion ekrani va kiritishni uzatadi. RDP ichidagi Firefox request i Windows emas, bastiondan chiqadi. Klaviatura tartibi paroldagi belgilarga ta’sir qiladi; interfeys tili va keyboard layout alohida sozlamadir.')

note('P1.1',
 '`apt-get update` は利用できるパッケージの一覧を更新する。`apt-get install nginx` は、その一覧を使ってNginxをインストールする。',
 '`apt-get update` обновляет список доступных пакетов. `apt-get install nginx` использует этот список для установки Nginx.',
 '`apt-get update` mavjud paketlar ro‘yxatini yangilaydi. `apt-get install nginx` shu ro‘yxat yordamida Nginx ni o‘rnatadi.')
note('P1.2',
 '`cp` は本文を配信用ファイルへコピーする。`chown root:root` はコピー先の所有者とグループを root に変更する。`chmod 0644` は所有者に読み書き、グループとその他のユーザーに読み取りを許可する。',
 '`cp` копирует текст в файл для публикации. `chown root:root` назначает root владельцем и группой копии. `chmod 0644` даёт владельцу право чтения и записи, а группе и остальным — право чтения.',
 '`cp` matnni tarqatiladigan faylga nusxalaydi. `chown root:root` nusxaning egasi va guruhini root ga o‘zgartiradi. `chmod 0644` egaga o‘qish va yozish, guruh va boshqa foydalanuvchilarga o‘qish huquqini beradi.')
note('P1.3',
 'nginx -Tは読込対象の設定を表示し、-tは構文を検査する。systemctlのenableは次回起動時、--nowは現在の起動を指定する。設定ファイルの保存だけで終わらず、reload後のserviceと待受portを読む。',
 'Nginx -T выводит конфигурацию, -t проверяет синтаксис. В systemctl enable включает запуск при загрузке, --now запускает сейчас. После сохранения файла проверьте reload, состояние службы и порт.',
 'Nginx -T config ni ko‘rsatadi; -t sintaksisni tekshiradi. Systemctl enable keyingi boot da ishga tushishni, --now hozir ishga tushishni belgilaydi. Fayl saqlangach reload, service holati va portni tekshiring.')
note('P1.4',
 '`127.0.0.1` はループバックアドレスで、リクエストは同じWebサーバー内のNginxに届く。',
 '`127.0.0.1` — адрес обратной петли. Запрос приходит в Nginx на том же Web-сервере.',
 '`127.0.0.1` — loopback manzili. So‘rov shu Web server ichidagi Nginx ga yetib boradi.')
note('P1.5',
 '宛先はWebサーバーの内部IPに変わる。リクエストするファイルのパスはP1.4と同じ `/practice.txt` を使う。',
 'Адрес назначения меняется на внутренний IP Web-сервера. Путь к файлу остаётся тем же, что и в P1.4, — `/practice.txt`.',
 'Manzil Web serverning ichki IP siga o‘zgaradi. Fayl yo‘li P1.4 dagidek `/practice.txt` bo‘lib qoladi.')
note('P1.6',
 'access logでは時刻・要求path・statusを直前のcurlと対応させる。tailは末尾を読む操作で、logを書き換えない。exitで接続を終えたら、PCのブラウザでP1を確認する。',
 'Сопоставьте время, путь и статус в access log с недавним curl. Tail читает последние строки и не меняет журнал. После exit проверьте P1 в браузере PC.',
 'Access log dagi vaqt, path va status ni oldingi curl bilan solishtiring. Tail oxirgi qatorlarni o‘qiydi, log ni o‘zgartirmaydi. Exit dan keyin PC brauzerida P1 ni tekshiring.')


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
