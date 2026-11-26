"""Parallel JA/RU/UZ prose and shared commands for P/M handbooks. No student secrets."""
LANGS = ('ja', 'ru', 'uz')
def T(ja, ru, uz):
    return dict(zip(LANGS, (ja, ru, uz)))

PLACES = {
 'portal': T('自分のPCのブラウザ：Web Portal', 'Браузер на своём PC: Web Portal', 'Shaxsiy PC brauzeri: Web Portal'),
 'pc': T('学生のWindows PC（共有アカウント）', 'Windows PC студента (общая учётная запись)', 'Talabaning Windows PC si (umumiy hisob)'),
 'cloud': T('CloudShell（学生本人のAWS）', 'CloudShell в личном AWS-аккаунте студента', 'Talabaning shaxsiy AWS hisobidagi CloudShell'),
 'web': T('WebサーバーのSSM端末：ssm-user', 'SSM-терминал Web-сервера: ssm-user', 'Web serverning SSM terminali: ssm-user'),
 'dns': T('DNSサーバーのSSM端末：ssm-user', 'SSM-терминал DNS-сервера: ssm-user', 'DNS serverning SSM terminali: ssm-user'),
 'db': T('DBサーバーのSSM端末：ssm-user', 'SSM-терминал DB-сервера: ssm-user', 'DB serverning SSM terminali: ssm-user'),
 'dns_clients': T('踏み台サーバーとWebサーバーのSSM端末', 'SSM-терминалы бастиона и Web-сервера', 'Bastion va Web serverlarining SSM terminallari'),
 'bst': T('踏み台のSSM端末：ssm-user', 'SSM-терминал бастиона: ssm-user', 'Bastionning SSM terminali: ssm-user'),
 'gui': T('RDP内のFirefox（踏み台）', 'Firefox на рабочем столе бастиона через RDP', 'RDP orqali bastiondagi Firefox'),
 'console': T('学生本人のAWSコンソール', 'AWS Console своего студенческого аккаунта', 'Talabaning shaxsiy AWS Console oynasi'),
 'dbsql': T('DBサーバーのpsql：OS postgres', 'psql на DB-сервере от имени системного postgres', 'DB serverda OS postgres nomidan psql'),
}

MODULES = []
def module(id, title, goals, problem):
    value = dict(id=id, title=title, goals=goals, problem=problem, steps=[])
    MODULES.append(value)
    return value
def step(m, title, place, why, code, expect, trouble, *, editor_input=None):
    m['steps'].append(dict(title=title, place=place, why=why, code=code.strip(), expect=expect,
                           trouble=trouble, editor_input=editor_input))

m = module('P0', T('サーバーの確認と接続', 'Своя среда и место выполнения команд', 'Shaxsiy muhit va buyruqlarni bajarish joyi'),
 T('EC2の一覧から正しいサーバーを選び、Session Managerで接続して、課題の結果を自分で確認できる。',
   'Выбрать нужный сервер в списке EC2, подключиться через Session Manager и проверить результат задания.',
   'EC2 ro‘yxatidan kerakli serverni tanlash, Session Manager orqali ulanish va topshiriq natijasini tekshirish.'),
 T('構築済みの自分の環境で、5台のインスタンスIDとロールを確認し、接続先と操作ユーザーを確かめる。',
   'В своей готовой среде проверьте идентификаторы и роли пяти серверов, затем проверьте, к какому серверу и под каким пользователем вы подключились.',
   'Tayyor muhitingizda beshta serverning instance ID si va rolini tekshiring. Qaysi serverga va qaysi foydalanuvchi sifatida ulanganingizni aniqlang.'))
step(m, T('5台のinstance IDを確認する', 'Проверить instance ID пяти серверов', 'Beshta serverning instance ID sini tekshirish'), 'console',
 T('AWSマネジメントコンソール上部のSearch欄にEC2と入力し、EC2の管理画面を開く。EC2 → Instancesを開き、Name列で自分の演習環境の5台のサーバーを確認する。同じ行のInstance ID列からi-を含めてIDを確認する。',
   'Введите EC2 в поле Search в верхней части AWS Console и откройте консоль EC2. Откройте EC2 → Instances и найдите пять серверов своей среды в столбце Name. В той же строке проверьте полный идентификатор с префиксом i- в столбце Instance ID.',
   'AWS Console tepasidagi Search maydoniga EC2 deb yozib, boshqaruv oynasini oching. EC2 → Instances ro‘yxatida Name ustunidan o‘z muhitingizdagi beshta serverni tekshiring. Shu qatordagi Instance ID ustunidan i- bilan boshlangan to‘liq ID ni ko‘ring.'), '', None, None)
step(m, T('Session ManagerでWebサーバーに接続する', 'Подключиться к Web-серверу через Session Manager', 'Session Manager orqali Web serverga ulanish'), 'web',
 T('P0.1で確認したWebサーバーの **Instance ID** をクリックする。詳細画面で **Connect** の右にある矢印を押し、**Connect with SSM Session Manager** を選ぶ。新しいタブのターミナルで、下のコマンドを上から1行ずつ実行する。初期構築時に置かれた `/etc/jdu-web/bootstrap.json` を `cat` で表示し、`"role": "web"` を探す。Webサーバーだと確認できたら、ホームディレクトリで `nano` を使って確認用ファイルを作る。',
   'Нажмите **Instance ID** Web-сервера, найденного в P0.1. На странице сведений нажмите стрелку справа от **Connect** и выберите **Connect with SSM Session Manager**. В терминале новой вкладки выполняйте команды по одной. Выведите файл `/etc/jdu-web/bootstrap.json`, созданный при начальной настройке, командой `cat` и найдите `"role": "web"`. Убедившись, что это Web-сервер, создайте проверочный файл в домашнем каталоге через `nano`.',
   'P0.1 da topilgan Web serverning **Instance ID** havolasini bosing. Tafsilotlarda **Connect** yonidagi o‘ng strelkani bosing va **Connect with SSM Session Manager** ni tanlang. Yangi varaqdagi terminalda quyidagi buyruqlarni bittadan bajaring. Dastlabki sozlashda yaratilgan `/etc/jdu-web/bootstrap.json` faylini `cat` bilan ko‘ring va `"role": "web"` yozuvini toping. Web serverga ulangan bo‘lsangiz, uy katalogida `nano` bilan tekshiruv faylini yarating.'),
 r"""id -un
cd ~
pwd
cat /etc/jdu-web/bootstrap.json
nano p0-connection.txt
cat p0-connection.txt
""",
 T('`id -un` は `ssm-user`、`pwd` は `/home/ssm-user` を表示する。JSONファイルには `"role": "web"` が含まれ、最後の `cat` では `web` だけが1行表示される。', 'Команда `id -un` выводит `ssm-user`, а `pwd` — `/home/ssm-user`. В JSON-файле есть `"role": "web"`, а последняя команда `cat` выводит только строку `web`.', '`id -un` buyrug‘i `ssm-user`, `pwd` esa `/home/ssm-user` ni ko‘rsatadi. JSON faylda `"role": "web"` bor va oxirgi `cat` buyrug‘i faqat bitta `web` satrini chiqaradi.'),
 None)
step(m, T('RDPで踏み台のデスクトップを開く', 'Открыть рабочий стол бастиона по RDP', 'RDP orqali bastion ish stolini ochish'), 'pc',
 T('Windowsの「リモート デスクトップ接続」で、自分の踏み台サーバーのデスクトップを開く。',
   'Откройте рабочий стол своего бастиона через приложение Windows «Подключение к удалённому рабочему столу».',
   'Windows dagi Remote Desktop Connection orqali o‘z oraliq serveringizning ish stolini oching.'),
 'mstsc /prompt',
 T('踏み台サーバーのUbuntuのデスクトップ（Xfce）が表示される。左上の「Applications」からFirefoxなどを開ける。', 'Откроется рабочий стол Ubuntu (Xfce) бастиона. Чтобы открыть Firefox и другие программы, используйте меню Applications.', 'Oraliq serverning Ubuntu ish stoli (Xfce) ochiladi. Yuqori chapdagi Applications menyusidan Firefox va boshqa dasturlarni ochish mumkin.'),
 T('Login failedならuser名と日本語/英語等のkeyboard配列を確認する。passwordを会話へ送らない。到達しない場合は現在のIPと許可された接続元CIDRを教師と確認し、3389を全公開しない。終了時はRDP内の自分の作業を保存し、接続を閉じる。', 'При Login failed проверьте имя и раскладку клавиатуры. Не отправляйте пароль в чат. При недоступности сверьте текущий IP и разрешённый CIDR с преподавателем; не открывайте 3389 для всех. Перед закрытием RDP сохраните работу.', 'Login failed bo‘lsa user nomi va klaviatura tartibini tekshiring. Parolni chat ga yubormang. Ulanmasa joriy IP va ruxsatli CIDR ni o‘qituvchi bilan tekshiring; 3389 ni hammaga ochmang. RDP ni yopishdan oldin ishni saqlang.'))


RDP_STEPS = (
    ('rdp-bastion-select-highlighted', T('踏み台サーバーを選ぶ', 'Выберите бастион', 'Oraliq serverni tanlang'), T(
        'EC2 → Instancesで、自分の演習環境のうち名前の末尾が `-bastion` の行を探し、同じ行の **Instance ID** をクリックする。',
        'Откройте EC2 → Instances, найдите в своей учебной среде строку с окончанием имени `-bastion` и нажмите **Instance ID** в этой строке.',
        'EC2 → Instances bo‘limida o‘z muhitingizdagi nomi `-bastion` bilan tugaydigan qatorni toping va shu qatordagi **Instance ID** ni bosing.')),
    ('rdp-bastion-public-ip-highlighted', T('公開IPv4アドレスをコピーする', 'Скопируйте публичный IPv4-адрес', 'Ommaviy IPv4 manzilini nusxalang'), T(
        'インスタンスの詳細画面で **Public IPv4 address** の横にあるコピーアイコンを押す。次に入力するのは、自分の画面に表示された現在の公開IPv4アドレス。スクリーンショットの値は例。',
        'На странице экземпляра нажмите значок копирования рядом с **Public IPv4 address**. На следующем шаге используйте текущий адрес из своей консоли. Адрес на снимке приведён для примера.',
        'Instans tafsilotlarida **Public IPv4 address** yonidagi nusxalash belgisini bosing. Keyingi qadamda o‘z oynangizdagi joriy ommaviy IPv4 manzilini ishlating. Rasmdagi manzil misol.')),
    ('rdp-connect-highlighted', T('公開IPv4アドレスを入力して接続する', 'Введите публичный IPv4-адрес и подключитесь', 'Ommaviy IPv4 manzilini kiritib ulaning'), T(
        '「リモート デスクトップ接続」の **コンピューター** 欄に、手順2でコピーした公開IPv4アドレスを貼り付け、**接続** を押す。',
        'В окне «Подключение к удалённому рабочему столу» вставьте скопированный на шаге 2 публичный IPv4-адрес в поле **Компьютер** и нажмите **Подключить**.',
        'Remote Desktop Connection oynasidagi **Computer** maydoniga 2-qadamda nusxalangan ommaviy IPv4 manzilini qo‘ying va **Connect** tugmasini bosing.')),
    ('rdp-certificate-highlighted', T('証明書の確認画面を読む', 'Проверьте предупреждение о сертификате', 'Sertifikat ogohlantirishini tekshiring'), T(
        'この画面が出た場合は、表示された接続先を手順2の公開IPv4アドレスと照合する。接続先が今回の踏み台であり、演習用の証明書だと教師に確認できたら **はい** を押す。確認できない場合は **いいえ** を押して教師に相談する。',
        'Если появилось это окно, сверьте адрес назначения с публичным IPv4 из шага 2. Нажмите **Да**, когда преподаватель подтвердит, что это ваш бастион и сертификат учебной среды. Если подтвердить это не удалось, нажмите **Нет** и обратитесь к преподавателю.',
        'Bu oyna chiqsa, ulanish manzilini 2-qadamdagi ommaviy IPv4 manzili bilan solishtiring. O‘qituvchi bu sizning oraliq serveringiz va mashq sertifikati ekanini tasdiqlasa, **Yes** ni bosing. Tasdiqlanmasa, **No** ni bosing va o‘qituvchiga murojaat qiling.')),
    ('rdp-xrdp-login-highlighted', T('踏み台サーバーにログインする', 'Войдите на бастион', 'Oraliq serverga kiring'), T(
        'xrdpのログイン画面で **Session** が `Xorg` になっていることを確かめる。**username** に `labuser`、**password** に学生用セットアップで自分が設定したRDPパスワードを入力し、**OK** を押す。',
        'В окне входа xrdp проверьте, что в поле **Session** выбрано `Xorg`. Введите `labuser` в поле **username**, свой пароль RDP из начальной настройки в поле **password** и нажмите **OK**.',
        'xrdp kirish oynasida **Session** maydonida `Xorg` tanlanganini tekshiring. **username** maydoniga `labuser`, **password** maydoniga dastlab belgilagan RDP parolingizni yozing va **OK** ni bosing.')),
    ('rdp-desktop', T('デスクトップが開いたことを確認する', 'Убедитесь, что рабочий стол открылся', 'Ish stoli ochilganini tekshiring'), T(
        'リモート デスクトップ接続のウィンドウ内に、左上の **Applications** メニューや **Home** アイコンが表示されれば、踏み台サーバーに接続できている。',
        'Если в окне удалённого рабочего стола видно меню **Applications** слева вверху и значок **Home**, вы подключены к бастиону.',
        'Uzoq ish stoli oynasining yuqori chapida **Applications** menyusi va **Home** belgisi ko‘rinsa, oraliq serverga ulangansiz.')),
)

m = module('P1', T('HTTPで静的ファイルを返す', 'Выдача статического файла по HTTP', 'HTTP orqali statik faylni qaytarish'),
 T('Nginx、保存先、待受、HTTP応答、access logを一組で確認する。', 'Связать Nginx, файл, прослушивание порта, HTTP-ответ и access log.', 'Nginx, fayl joyi, tinglash porti, HTTP javobi va access log ni bog‘lash.'),
 T('Webサーバーの /var/www/html/practice.txt を HTTP 200 で配信する。', 'Настройте выдачу файла /var/www/html/practice.txt с ответом HTTP 200.', 'Web serverdagi /var/www/html/practice.txt faylini HTTP 200 bilan qaytaring.'))
step(m, T('内部APTからNginxを導入する', 'Установить Nginx из внутреннего APT', 'Ichki APT dan Nginx o‘rnatish'), 'web',
 T('P0と同じ方法でWebサーバーへSSMで接続する。内部の配布サーバー（`10.20.2.30`）からNginxのパッケージをダウンロードし、Webサーバーにインストールする。',
   'Подключитесь к Web-серверу через SSM, как в P0. Скачайте пакет Nginx с внутреннего Repo-сервера (`10.20.2.30`) и установите его на Web-сервере.',
   'P0 dagidek Web serverga SSM orqali ulaning. Nginx paketini ichki Repo serveridan (`10.20.2.30`) yuklab olib, Web serverga o‘rnating.'),
 'sudo apt-get update\nsudo apt-get install nginx',
 T('一覧を更新すると、配布サーバーの行に `Hit:` または `Get:` が表示される。`N: Ignoring file ... ubuntu.sources.jdu-disabled` は、初回セットアップで無効にしたUbuntu標準の配布先設定をAPTが読み飛ばしたという通知である。取得や署名のエラーがなければインストールへ進む。確認画面が出たら `Y` を入力する。',
   'При обновлении списка в строке внутреннего сервера появляется `Hit:` или `Get:`. Сообщение `N: Ignoring file ... ubuntu.sources.jdu-disabled` означает, что APT пропустил стандартный источник Ubuntu, отключённый при начальной настройке. Если ошибок загрузки или проверки подписи нет, продолжайте установку. Если APT запросит подтверждение, введите `Y`.',
   'Ro‘yxat yangilanganda ichki server qatorida `Hit:` yoki `Get:` ko‘rinadi. `N: Ignoring file ... ubuntu.sources.jdu-disabled` xabari APT dastlabki sozlashda o‘chirilgan standart Ubuntu manbasi faylini o‘tkazib yuborganini bildiradi. Yuklash yoki imzo tekshiruvida xato bo‘lmasa, o‘rnatishni davom ettiring. Tasdiq so‘ralsa, `Y` kiriting.'),
 T('パッケージ一覧の取得に失敗した場合は、配布サーバーの稼働状態とIPアドレスを確認する。', 'Если не удалось получить список пакетов, проверьте состояние и IP-адрес внутреннего сервера пакетов.', 'Paketlar ro‘yxatini olib bo‘lmasa, ichki paket serverining holati va IP manzilini tekshiring.'))
step(m, T('正しい本文を作り、所有者と権限を揃える', 'Создать точный текст и права файла', 'Aniq matn yaratish va ruxsatlarni sozlash'), 'web',
 T('作業用のファイルに本文を書き、Nginxが配信するディレクトリへコピーする。',
   'Запишите текст в рабочий файл, затем скопируйте его в каталог, из которого Nginx выдаёт файлы.',
   'Matnni ish fayliga yozing, keyin uni Nginx fayllarni tarqatadigan katalogga nusxalang.'),
 """cd ~
mkdir -p jdu-web-practice/p1
cd jdu-web-practice/p1
pwd
nano practice.txt
sudo cp practice.txt /var/www/html/practice.txt
sudo chown root:root /var/www/html/practice.txt
sudo chmod 0644 /var/www/html/practice.txt
stat -c '%U:%G %a %n' /var/www/html/practice.txt
cat /var/www/html/practice.txt""",
 T('所有者・グループと権限は `root:root 644` と表示される。本文は `JDU WEB-02 practice: HTTP response verified.` の1行である。', 'Отображаются владелец, группа и права `root:root 644` и строка `JDU WEB-02 practice: HTTP response verified.`.', '`root:root 644` egasi, guruhi va ruxsatlari hamda `JDU WEB-02 practice: HTTP response verified.` qatori ko‘rinadi.'),
 T('nanoが開いている場合は、保存して終了してから次のコマンドを実行する。', 'Если nano ещё открыт, сохраните файл и выйдите перед следующей командой.', 'Nano hali ochiq bo‘lsa, keyingi buyruqdan oldin faylni saqlab chiqing.'),
 editor_input='JDU WEB-02 practice: HTTP response verified.')
step(m, T('Web rootとportを確認して起動する', 'Проверить Web root и запустить сервис', 'Web root ni tekshirish va service ni ishga tushirish'), 'web',
 T('`nginx -T` で有効な設定を表示し、`/etc/nginx/sites-enabled/default` に `root /var/www/html` と `listen 80` の指定があることを確認する。変更が必要なら `sudo nano` で編集し、構文検査に成功してから設定を再読み込みする。',
   'Выведите действующую конфигурацию командой `nginx -T` и найдите `root /var/www/html` и `listen 80` в `/etc/nginx/sites-enabled/default`. При необходимости отредактируйте файл в `sudo nano` и перечитайте настройки после успешной проверки синтаксиса.',
   '`nginx -T` bilan amaldagi sozlamani chiqaring. `/etc/nginx/sites-enabled/default` ichidan `root /var/www/html` va `listen 80` ni toping. Kerak bo‘lsa `sudo nano` bilan tahrirlang va sintaksis tekshiruvidan keyin sozlamani qayta yuklang.'),
 'sudo nginx -T\nsudo nginx -t\nsudo systemctl enable --now nginx\nsudo systemctl reload nginx\nsystemctl is-active nginx\nsudo ss -lntp',
 T('構文検査で `syntax is ok` と `test is successful`、起動状態で `active` が表示される。最後に、NginxがTCPの80番ポート（例 `0.0.0.0:80`）で待ち受けていることを確認する。', 'Проверка синтаксиса выводит `syntax is ok` и `test is successful`, а служба показывает `active`. Проверьте, что Nginx слушает TCP-порт 80, например `0.0.0.0:80`.', 'Sintaksis tekshiruvida `syntax is ok` va `test is successful`, xizmat holatida `active` chiqadi. Nginx TCP 80 portini, masalan `0.0.0.0:80` manzilida tinglayotganini tekshiring.'),
 T('構文検査に失敗した場合は、`nginx -t` に表示されたファイル名と行番号を確認して修正する。', 'При ошибке синтаксиса исправьте файл и строку, указанные в выводе `nginx -t`.', 'Sintaksis xatosida `nginx -t` ko‘rsatgan fayl va qatorni tuzating.'))
step(m, T('Web自身から応答を見る', 'Посмотреть ответ на самом Web', 'Web ichidan javobni ko‘rish'), 'web',
 T('Webサーバーの端末で `curl` を使い、HTTPリクエストを送る。宛先の `127.0.0.1` は、コマンドを実行しているWebサーバー自身を指す。',
   'Отправьте HTTP-запрос командой `curl` в терминале Web-сервера. Адрес `127.0.0.1` указывает на этот же сервер.',
   'Web server terminalida `curl` bilan HTTP so‘rov yuboring. `127.0.0.1` buyruq bajarilayotgan Web serverning o‘zini bildiradi.'),
 'curl -i http://127.0.0.1/practice.txt',
 T('HTTP 200と、practice.txtに書いた `JDU WEB-02 practice: HTTP response verified.` が表示される。', 'Отображаются HTTP 200 и строка из practice.txt: `JDU WEB-02 practice: HTTP response verified.`', 'HTTP 200 va practice.txt ichidagi `JDU WEB-02 practice: HTTP response verified.` qatori chiqadi.'),
 T('「Welcome to nginx」が表示されたら、curlで `/practice.txt` を指定したか確認する。`http://127.0.0.1/` を開くとNginxの初期ページが返ることがある。', 'Если показано «Welcome to nginx», проверьте путь `/practice.txt` в команде curl. По адресу `http://127.0.0.1/` может открыться начальная страница Nginx.', '«Welcome to nginx» chiqsa, curl buyrug‘ida `/practice.txt` ko‘rsatilganini tekshiring. `http://127.0.0.1/` manzili Nginx bosh sahifasini qaytarishi mumkin.'))
step(m, T('踏み台サーバーから同じファイルを見る', 'Проверить тот же файл с бастиона', 'Ayni faylni Bastion serveridan tekshirish'), 'bst',
 T('踏み台サーバーへSSMで接続し、`curl` でWebサーバーにHTTPリクエストを送る。イントラネット（内部ネットワーク）から接続するので、宛先にはWebサーバーの内部IPアドレス `10.20.1.20` を指定する。',
   'Подключитесь к бастиону через SSM и отправьте HTTP-запрос к Web-серверу командой `curl`. Из внутренней сети используйте внутренний IP Web-сервера `10.20.1.20`.',
   'Bastion serverga SSM orqali ulaning va `curl` bilan Web serverga HTTP so‘rov yuboring. Ichki tarmoqdan Web serverning ichki IP manzili `10.20.1.20` ni kiriting.'),
 'curl -i http://10.20.1.20/practice.txt',
 T('HTTP 200と、`JDU WEB-02 practice: HTTP response verified.` が表示される。', 'Отображаются HTTP 200 и строка `JDU WEB-02 practice: HTTP response verified.`', 'HTTP 200 va `JDU WEB-02 practice: HTTP response verified.` qatori chiqadi.'),
 None)
step(m, T('要求とlogを結び付けて提出する', 'Связать запрос с журналом и отправить', 'So‘rovni log bilan bog‘lash va yuborish'), 'web',
 T('Webへ戻り、access logの時刻・client IP・path・statusを見る。logは実際に要求を処理した証拠で、fileがある証拠とは別。exitでCloudShellへ戻ったら、PCのWeb PortalでP1を選び「この課題を確認する」を押す。', 'Вернитесь на Web. В access log найдите время, IP клиента, путь и статус. Это доказательство обработки запроса, не только наличия файла. После exit в CloudShell выберите P1 в Web Portal на PC и запустите проверку.', 'Web ga qayting. Access log da vaqt, client IP, path va statusni ko‘ring. Bu fayl borligidan tashqari so‘rov ishlanganining dalilidir. Exit bilan CloudShell ga qaytgach, PC dagi Web Portal da P1 ni tekshiring.'),
 'sudo tail -n 20 /var/log/nginx/access.log\nexit',
 T('確認画面に8項目の結果と、クリアした項目数が表示される。公開IPからのHTTPアクセスは採点システムが自動で確認する。', 'На экране показываются результаты восьми проверок и число выполненных критериев. Система автоматически проверяет HTTP-доступ по публичному IP.', 'Ekranda sakkizta tekshiruv natijasi va bajarilgan mezonlar soni ko‘rinadi. Tizim ochiq IP orqali HTTP ulanishini avtomatik tekshiradi.'),
 T('処理中なら結果を更新する。保存に失敗していれば表示された理由を確認する。checkerの期待本文を書き換えない。', 'Если идёт обработка, обновите результат. При ошибке сохранения прочитайте причину. Не меняйте ожидаемый текст checker.', 'Ishlov davom etsa natijani yangilang. Saqlash xatosida sababni o‘qing. Checker kutgan matnni o‘zgartirmang.'))

m = module('P2', T('内部DNSと通常の名前解決', 'Внутренний DNS и системное разрешение имён', 'Ichki DNS va odatiy nom yechimi'),
 T('BINDのzone・A record・問い合わせ制限と、client側resolverを順に構築する。', 'Последовательно настроить zone, A-записи, ACL BIND и resolver клиентов.', 'BIND zone, A record, ACL va client resolver ni ketma-ket sozlash.'),
 T('guide.lab.test→10.20.1.20、practice-db.lab.test→10.20.2.20を設定する。P1のHTTPを名前で利用する。基盤の固定IPは変えない。', 'Настройте guide.lab.test → 10.20.1.20 и practice-db.lab.test → 10.20.2.20; откройте HTTP из P1 по имени. Фиксированные IP не меняются.', 'guide.lab.test → 10.20.1.20 va practice-db.lab.test → 10.20.2.20 ni sozlang; P1 HTTP ni nom orqali oching. Asosiy IP lar o‘zgarmaydi.'))
step(m, T("配布サーバーからBINDをインストールする", "Установить BIND с сервера пакетов", "Paketlar serveridan BIND o‘rnatish"), 'dns',
 T("DNSサーバーで配布サーバーのパッケージ一覧を更新し、BINDと設定を確認するためのツールをインストールする。続けて、編集する設定ファイル2つの控えを作る。", "На DNS-сервере обновите список пакетов, установите BIND и инструменты проверки. Сделайте копии двух файлов перед редактированием.", "DNS serverda paketlar ro‘yxatini yangilang va BIND hamda tekshiruv vositalarini o‘rnating. Tahrirdan oldin ikkita faylni nusxalang."),
 'sudo apt-get update\nsudo apt-get install --no-install-recommends bind9 bind9-utils\nsudo cp -an /etc/bind/named.conf.options /etc/bind/named.conf.options.before-p2\nsudo cp -an /etc/bind/named.conf.local /etc/bind/named.conf.local.before-p2',
 T("`bind9` と `bind9-utils` がインストールされ、2つの `.before-p2` ファイルができる。", "Установлены `bind9` и `bind9-utils`, появились две копии `.before-p2`.", "`bind9` va `bind9-utils` o‘rnatiladi va ikkita `.before-p2` nusxasi yaratiladi."),
 None)
step(m, T("問い合わせを受け付けるサーバーを設定する", "Указать, от кого DNS принимает запросы", "DNS so‘rovini yubora oladigan serverlarni belgilash"), 'dns',
 T("問い合わせを受け付けるのは、DNSサーバー自身、踏み台サーバー、Webサーバーの3台。演習の外の名前はAWSのDNS（`10.20.0.2`）に問い合わせる。", "Разрешите запросы от DNS-сервера, бастиона и Web-сервера. Имена вне учебной зоны передаются DNS AWS (`10.20.0.2`).", "DNS serverning o‘zi, Bastion va Web serverlariga ruxsat bering. Mashq zonasidan tashqaridagi nomlar AWS DNS ga (`10.20.0.2`) yuboriladi."),
 '''acl "jdu_clients" { 127.0.0.1; 10.20.1.10; 10.20.1.20; };
options {
    directory "/var/cache/bind";
    listen-on { 127.0.0.1; 10.20.2.10; };
    listen-on-v6 { none; };
    allow-query { jdu_clients; };
    allow-recursion { jdu_clients; };
    allow-query-cache { jdu_clients; };
    recursion yes;
    forward only;
    forwarders { 10.20.0.2; };
    dnssec-validation no;
    allow-transfer { none; };
};''',
 T("`listen-on` にDNSサーバー自身の内部IP `10.20.2.10`、`forwarders` にAWSのDNS `10.20.0.2` が入る。", "В `listen-on` указан внутренний IP DNS-сервера `10.20.2.10`, в `forwarders` — DNS AWS `10.20.0.2`.", "`listen-on` da DNS serverning ichki IP manzili `10.20.2.10`, `forwarders` da AWS DNS `10.20.0.2` turadi."),
 None)
step(m, T("名前とIPv4アドレスを登録する", "Записать имена и адреса IPv4", "Nom va IPv4 manzillarini yozish"), 'dns',
 T("`named.conf.local` で、`lab.test` のゾーンファイルがどこにあるかをBINDに指定する。`db.lab.test` に、一つの名前とIPv4アドレスを一組にしてAレコードを書く。", "В `named.conf.local` укажите BIND путь к файлу зоны `lab.test`. В `db.lab.test` запишите A-записи, связывающие имена с адресами IPv4.", "`named.conf.local` da BIND ga `lab.test` zona fayli yo‘lini ko‘rsating. `db.lab.test` da nomni IPv4 manzili bilan bog‘lovchi A yozuvlarini yozing."),
 '''// /etc/bind/named.conf.local
zone "lab.test" {
    type primary;
    file "/etc/bind/zones/db.lab.test";
    allow-transfer { none; };
    allow-update { none; };
};

; /etc/bind/zones/db.lab.test
$TTL 300
@ IN SOA dns.lab.test. hostmaster.lab.test. (
    2026102301 3600 600 604800 300 )
@ IN NS dns.lab.test.
dns IN A 10.20.2.10
guide IN A 10.20.1.20
practice-db IN A 10.20.2.20''',
 T("`guide.lab.test` はWebサーバーの `10.20.1.20`、`practice-db.lab.test` はDBサーバーの `10.20.2.20` に対応する。", "`guide.lab.test` указывает на Web `10.20.1.20`, а `practice-db.lab.test` — на DB `10.20.2.20`.", "`guide.lab.test` Web serverning `10.20.1.20`, `practice-db.lab.test` DB serverning `10.20.2.20` manziliga mos keladi."),
 T('すでにゾーンファイルがある場合は、既存の名前を残して練習用の2件を追加する。レコードを変更するたびに、SOAのシリアル番号を現在の値より増やす。',
   'Если файл зоны уже существует, сохраните его имена и добавьте две учебные записи. При каждом изменении записей увеличивайте серийный номер SOA.',
   'Zona fayli mavjud bo‘lsa, mavjud nomlarni qoldirib ikkita mashq yozuvini qo‘shing. Yozuvlar o‘zgarganda SOA seriya raqamini oshiring.'))
step(m, T("BINDを起動してDNSサーバー自身から問い合わせる", "Запустить BIND и сделать запрос с DNS-сервера", "BIND ni ishga tushirib DNS serverning o‘zidan so‘rash"), 'dns',
 T("設定とゾーンファイルにエラーがないことを確かめてからBINDを起動する。`dig` はDNSに問い合わせてレスポンスを表示するコマンド。ここでは自分自身を指す `127.0.0.1` を問い合わせ先にする。", "Проверьте конфигурацию и файл зоны, затем запустите BIND. Команда `dig` отправляет DNS-запрос и выводит ответ. Адрес `127.0.0.1` указывает на сам DNS-сервер.", "Sozlama va zona faylini tekshirib BIND ni ishga tushiring. `dig` DNS so‘rovini yuborib javobni ko‘rsatadi. `127.0.0.1` DNS serverning o‘zini bildiradi."),
 'sudo named-checkconf -z\nsudo named-checkzone lab.test /etc/bind/zones/db.lab.test\nsudo systemctl enable named\nsudo systemctl restart named\ndig @127.0.0.1 guide.lab.test A\ndig @127.0.0.1 guide.lab.test A +tcp',
 T("ゾーンファイルの検査で `OK` が表示される。UDPとTCPのどちらでも `NOERROR` が返り、`guide.lab.test` のIPは `10.20.1.20` になる。", "Проверка зоны выводит `OK`. По UDP и TCP ожидаются `NOERROR` и адрес `10.20.1.20` для `guide.lab.test`.", "Zona tekshiruvida `OK` chiqadi. UDP va TCP uchun `NOERROR` hamda `guide.lab.test` uchun `10.20.1.20` qaytadi."),
 T('失敗ならsudo journalctl -u named -n 30 --no-pagerで対象行を調べ、設定を直して再検査する。', 'При ошибке изучите sudo journalctl -u named -n 30 --no-pager, исправьте конфигурацию и проверьте снова.', 'Xatoda sudo journalctl -u named -n 30 --no-pager ni o‘qing, sozlamani tuzatib yana tekshiring.'))
step(m, T("踏み台サーバーとWebサーバーからBINDを試す", "Проверить BIND с бастиона и Web-сервера", "BIND ni Bastion va Web serveridan tekshirish"), 'dns_clients',
 T("両方のサーバーで実行する。`dig` の `@10.20.2.10` は、その1回の問い合わせ先を指定する。`AXFR` はゾーンのレコードをまとめて転送するための指定で、この演習では拒否されることを確かめる。", "Выполните команды на обоих серверах. `@10.20.2.10` в `dig` задаёт DNS только для данного запроса. `AXFR` запрашивает передачу записей зоны целиком. Проверьте, что передача запрещена.", "Buyruqlarni ikkala serverda bajaring. `dig` dagi `@10.20.2.10` faqat shu so‘rov uchun DNS serverni tanlaydi. `AXFR` zona yozuvlarini to‘liq ko‘chirishni so‘raydi. Unga ruxsat berilmaganini tekshiring."),
 'dig @10.20.2.10 guide.lab.test A\ndig @10.20.2.10 practice-db.lab.test A +tcp\ndig @10.20.2.10 absent-p2.lab.test A\ndig @10.20.2.10 aws.amazon.com A\ndig @10.20.2.10 lab.test AXFR',
 T("`guide.lab.test` は `10.20.1.20`、`practice-db.lab.test` は `10.20.2.20`。未登録の名前は `NXDOMAIN`、外部名 `aws.amazon.com` にはIPアドレスが返り、ゾーン転送は拒否される。", "`guide.lab.test` даёт `10.20.1.20`, `practice-db.lab.test` — `10.20.2.20`. Незарегистрированное имя даёт `NXDOMAIN`, `aws.amazon.com` возвращает IP, передача зоны отклоняется.", "`guide.lab.test` uchun `10.20.1.20`, `practice-db.lab.test` uchun `10.20.2.20` chiqadi. Ro‘yxatda yo‘q nom uchun `NXDOMAIN`, `aws.amazon.com` uchun IP qaytadi, zona uzatish rad etiladi."),
 None)
step(m, T("Ubuntu OSが普段使うDNSを設定する", "Задать DNS по умолчанию в Ubuntu", "Ubuntu OS odatda ishlatadigan DNS ni sozlash"), 'dns_clients',
 T("踏み台サーバーとWebサーバーを1台ずつ設定する。ブラウザやアプリが名前を調べるときに使うDNSを、Ubuntu OSのNetplanで `10.20.2.10` に指定する。", "Настройте бастион и Web-сервер по одному. В Netplan укажите `10.20.2.10` как DNS, которым Ubuntu пользуется для браузера и приложений.", "Bastion va Web serverlarini bittadan sozlang. Brauzer va ilovalar nomni qidirganda Ubuntu ishlatadigan DNS sifatida Netplan da `10.20.2.10` ni belgilang."),
 '''network:
  version: 2
  ethernets:
    ens5:
      dhcp4: true
      dhcp4-overrides:
        use-dns: false
      nameservers:
        addresses: [10.20.2.10]''',
 T("DHCPでIPアドレスを受け取る設定を残し、DNSに限って自動取得を止める。YAMLのインデントをそろえて保存する。", "Сохраните получение IP по DHCP и отключите автоматическое получение только DNS. Выровняйте отступы YAML.", "IP manzilni DHCP orqali olishni saqlang. Faqat DNS ni avtomatik olishni o‘chiring va YAML chekinishlarini tekislang."),
 T('同じinterfaceが複数YAMLにあると値がmergeされる。resolvectl dnsにAWS DNSが残る場合は、対応する全YAMLとruntimeの設定を確認する。', 'Несколько YAML одного интерфейса объединяются. Если resolvectl dns показывает ещё AWS DNS, проверьте все соответствующие YAML и действующую конфигурацию.', 'Bir interface bir necha YAML da bo‘lsa, qiymatlar birlashadi. resolvectl dns da AWS DNS qolsa, tegishli barcha YAML va amaldagi sozlamani tekshiring.'))
step(m, T("DNSの設定を反映して名前でページを開く", "Применить DNS и открыть страницу по имени", "DNS sozlamasini qo‘llab sahifani nomi bilan ochish"), 'dns_clients',
 T("Netplanの設定を反映する。`resolvectl dns` で実際に使うDNSサーバーを確かめ、`getent` でUbuntu OSが名前をどう解決するかを見る。その名前を使ってP1のファイルを取得する。", "Примените Netplan. В `resolvectl dns` проверьте DNS, а через `getent` — разрешение имён в Ubuntu. Затем получите файл P1 по имени.", "Netplan sozlamasini qo‘llang. `resolvectl dns` da DNS serverni, `getent` orqali Ubuntu nomni qanday yechishini tekshiring. So‘ng P1 faylini nom bilan oling."),
 'sudo netplan generate\nsudo netplan apply\nsudo systemctl restart systemd-resolved\nresolvectl dns\ngetent ahostsv4 guide.lab.test\ngetent ahostsv4 practice-db.lab.test\ncurl -i http://guide.lab.test/practice.txt',
 T("`resolvectl dns` のDNSは `10.20.2.10`。名前はそれぞれ `10.20.1.20` と `10.20.2.20` になり、HTTP `200` と `JDU WEB-02 practice: HTTP response verified.` が返る。", "DNS в `resolvectl dns` — `10.20.2.10`. Имена дают `10.20.1.20` и `10.20.2.20`. HTTP возвращает `200` и `JDU WEB-02 practice: HTTP response verified.`", "`resolvectl dns` da `10.20.2.10` chiqadi. Nomlar `10.20.1.20` va `10.20.2.20` ga yechiladi. HTTP `200` va `JDU WEB-02 practice: HTTP response verified.` qaytadi."),
 T('dig成功/getent失敗ならclient resolverを調べる。FirefoxはDoH無効の教師設定を維持する。', 'Если dig успешен, а getent нет, проверяйте resolver клиента. Сохраняйте настройку Firefox с отключённым DoH.', 'dig o‘tib getent o‘tmasa, client resolver ini tekshiring. Firefox dagi DoH o‘chirilgan sozlamani saqlang.'))
step(m, T("踏み台サーバーのブラウザで表示を確かめる", "Проверить страницу в браузере бастиона", "Sahifani Bastion brauzerida tekshirish"), 'gui',
 T("P0の手順で踏み台サーバーへRDP接続する。踏み台サーバー上のFirefoxで `http://10.20.1.20/practice.txt`、次に `http://guide.lab.test/practice.txt` を開く。最後に自分のPCの採点ページでP2を確認する。", "Подключитесь к бастиону по RDP как в P0. В его Firefox откройте `http://10.20.1.20/practice.txt`, затем `http://guide.lab.test/practice.txt`. На своём компьютере запустите проверку P2 на странице оценок.", "P0 dagidek Bastion serveriga RDP orqali ulaning. Uning Firefox brauzerida `http://10.20.1.20/practice.txt`, keyin `http://guide.lab.test/practice.txt` ni oching. O‘z kompyuteringizdagi baholash sahifasida P2 ni tekshiring."),
 '',
 T("どちらのURLでも `JDU WEB-02 practice: HTTP response verified.` が表示される。採点ページでP2の13項目を確認できる。", "По обоим адресам видно `JDU WEB-02 practice: HTTP response verified.` На странице оценок отображаются 13 критериев P2.", "Ikkala URL da `JDU WEB-02 practice: HTTP response verified.` ko‘rinadi. Baholash sahifasida P2 ning 13 mezoni chiqadi."),
 None)

m = module('P3', T('保存内容と停止・再開', 'Данные при остановке и запуске', 'To‘xtatish va qayta ishga tushirishda ma’lumotlar'),
 T('元のEBS上のfile・権限を確認し、同じWebを停止して再開した保持を証拠で示す。', 'Проверить файл и права на исходном EBS; доказать сохранение после stop/start того же Web.', 'Asl EBS dagi fayl va ruxsatni tekshirish; ayni Web stop/start dan keyin saqlanishini isbotlash.'),
 T('P3用markerを自分の匿名Lab IDで作る。停止前→stopped→再開後を観測する。ディスク追加・mount・backup/restoreは要求しない。', 'Создайте marker P3 со своим анонимным Lab ID. Зафиксируйте состояние до остановки, stopped и после запуска. Дополнительный диск, mount и backup/restore не требуются.', 'O‘z anonim Lab ID bilan P3 marker yarating. To‘xtashdan oldin, stopped va qayta ishga tushgandan keyingi holatni qayd eting. Yangi disk, mount yoki backup/restore kerak emas.'))
step(m, T('元の保存先と空きを調べる', 'Проверить исходный диск и свободное место', 'Asl saqlash joyi va bo‘sh joyni tekshirish'), 'web',
 T('findmntは対象pathのfile system、lsblkは接続されたdisk/partitionを示す。df -hは人が読みやすい単位。提供済みroot EBSを使い、名前が/dev/nvme等でも別diskへ付け替えない。', 'findmnt показывает файловую систему, lsblk — диски и разделы, df -h — свободное место. Используйте предоставленный root EBS; имя /dev/nvme не является причиной менять диск.', 'findmnt fayl tizimini, lsblk disk va partition larni, df -h bo‘sh joyni ko‘rsatadi. Berilgan root EBS dan foydalaning; /dev/nvme nomi disk almashtirish sababi emas.'),
 'findmnt -T /var/lib\nlsblk -o NAME,TYPE,SIZE,MOUNTPOINTS,SERIAL\ndf -h /var/lib\ncat /proc/sys/kernel/random/boot_id',
 T('元root volumeと対応し、空き20%以上かつ2GiB以上。boot_idはこの起動を区別する識別子として記録する。', 'Соответствует исходному root volume; свободно не менее 20% и 2 GiB. Сохраните boot_id текущей загрузки.', 'Asl root volume ga mos; kamida 20% va 2 GiB bo‘sh. Joriy yuklanish boot_id sini yozib oling.'),
 T('容量不足は準備状態の問題。成績のために他の教材やdiskを削除せず、教師へ相談する。', 'Недостаток места — проблема готовности. Не удаляйте другие материалы или диски ради баллов.', 'Joy yetishmasligi tayyorlik muammosi. Ball uchun boshqa material yoki diskni o‘chirmang.'))
step(m, T('markerを編集して配置する', 'Создать и разместить marker', 'Marker ni yaratish va joylash'), 'web',
 T('この端末にも自分のLAB_IDを設定する。printfの各行は改行で終わる。sudo installでdirectoryを0755、fileを0644/root:rootにする。最初に既存内容を確認し、異なる内容がある場合は上書きせず理由を確認する。', 'Задайте LAB_ID и в этом терминале. printf завершает строки переводом строки. install задаёт directory 0755 и файл 0644/root:root. Сначала проверьте существующий файл; не заменяйте отличающееся содержимое без выяснения причины.', 'Bu terminalda ham LAB_ID ni belgilang. printf har qatorni yangi qator bilan tugatadi. install katalogni 0755, faylni 0644/root:root qiladi. Avval mavjud faylni tekshiring; boshqa mazmunni sababini bilmasdan almashtirmang.'),
 r"""LAB_ID='YOUR-LAB-ID'
cd ~
mkdir -p jdu-web-practice/p3
cd jdu-web-practice/p3
printf 'lab_id=%s\ntask=P3\npayload=practice-storage-2026\n' "$LAB_ID" > storage.txt
cat storage.txt
sudo install -d -o root -g root -m 0755 /var/lib/jdu-web/practice
sudo install -o root -g root -m 0644 storage.txt /var/lib/jdu-web/practice/storage.txt
stat -c '%U:%G %a %n' /var/lib/jdu-web/practice /var/lib/jdu-web/practice/storage.txt
sha256sum /var/lib/jdu-web/practice/storage.txt""",
 T('3行の本文と末尾改行、0755/0644。hashを控える。権限777にすると保存fileの条件から外れる。', 'Три строки с конечным переводом строки, права 0755/0644. Запишите hash. Права 777 не подходят.', 'Oxirida yangi qator bo‘lgan 3 qator, ruxsat 0755/0644. Hash ni yozing. 777 ruxsat mos emas.'),
 T('YOUR-LAB-IDをそのまま残すと不一致。EC2名やメールではなく匿名Lab IDを使う。', 'Не оставляйте YOUR-LAB-ID. Используйте анонимный Lab ID, не имя EC2 и не email.', 'YOUR-LAB-ID ni o‘z holicha qoldirmang. EC2 nomi yoki email emas, anonim Lab ID ishlating.'))
step(m, T('停止前の証拠を保存する', 'Сохранить доказательство до остановки', 'To‘xtatishdan oldingi dalilni saqlash'), 'portal',
 T('Web端末からexitでCloudShellへ戻る。Web PortalでP3を選び「停止前の状態を記録する」を押す。現在のinstance/volume/marker hash/boot_idを保存する操作で、EC2はまだ停止しない。保存成功を確認する。P3の証拠は最後までこのブラウザ手順で記録する。', 'Выйдите из Web через exit в CloudShell. В Web Portal выберите P3 и сохраните состояние до остановки. Сохраняются instance/volume/hash marker/boot_id; EC2 ещё не останавливается. Дождитесь успешного сохранения. Все этапы доказательства P3 выполняйте этим браузерным способом.', 'Web dan exit bilan CloudShell ga qayting. Web Portal da P3 ni tanlab to‘xtashdan oldingi holatni yozing. Instance/volume/marker hash/boot_id saqlanadi, EC2 hali to‘xtamaydi. Saqlash muvaffaqiyatini kuting. P3 dalilining barcha bosqichlarini shu brauzer usuli bilan bajaring.'),
 '',
 T('停止前の証拠が保存される。記録後はmarkerを編集しない。', 'Состояние до остановки сохранено. После этого marker не редактируйте.', 'To‘xtashdan oldingi holat saqlandi. Shundan keyin marker ni tahrirlamang.'),
 T('失敗したまま停止すると有効な三段階の証拠にならない。先にfile/権限/SSMを直す。', 'Остановка после неуспешной подготовки не даст полной цепочки доказательств. Сначала исправьте файл/права/SSM.', 'Tayyorlash xatosidan keyin to‘xtatish to‘liq dalil bermaydi. Avval fayl/ruxsat/SSM ni tuzating.'))
step(m, T('同じWebをStopしstoppedを観測する', 'Остановить тот же Web и зафиксировать stopped', 'Ayni Web ni Stop qilib stopped holatini qayd etish'), 'console',
 T('EC2で自分のWebのinstance IDを再照合。Instance state → Stop instanceを選び、stoppedになるまで待つ。Reboot/Terminateではない。その状態のままWeb PortalのP3で「停止完了を確認する」を押す。踏み台と他の3台は停止しない。', 'Сверьте instance ID своего Web в EC2. Выберите Instance state → Stop instance и дождитесь stopped. Не Reboot/Terminate. Не запуская Web, подтвердите остановку в P3 Web Portal. Остальные четыре сервера не останавливайте.', 'EC2 da o‘z Web instance ID ni solishtiring. Instance state → Stop instance ni tanlab stopped ni kuting. Reboot/Terminate emas. Web ni yoqmasdan Web Portal P3 da to‘xtash tugaganini tekshiring. Qolgan to‘rtta serverni to‘xtatmang.'),
 '',
 T('同じinstanceがstoppedと記録される。この間WebへHTTP/SSM接続できないのは予定した停止。', 'Записано stopped того же instance. Во время остановки недоступность HTTP/SSM ожидаема.', 'Ayni instance stopped deb qayd qilinadi. Bu paytda HTTP/SSM ishlamasligi kutilgan holat.'),
 T('stoppingの間は待つ。先にStartした場合は、三段階の証拠を最初から取り直す必要がある。', 'При stopping подождите. Если запустили раньше наблюдения, цепочку из трёх этапов потребуется повторить.', 'stopping bo‘lsa kuting. Kuzatuvdan oldin Start qilsangiz, uch bosqichli dalilni qayta olish kerak bo‘ladi.'))
step(m, T('Startし、保持を照合して提出する', 'Запустить, сравнить данные и отправить', 'Start qilib saqlanishni solishtirish va yuborish'), 'console',
 T('同じWebをStartしrunning/SSM Onlineまで待つ。SSMでfileの本文/hashとboot_idを再確認する。instance/volume/hashは同じでboot_idだけが新しくなる。Web PortalのP3で「再開後の保持を確認する」を押し、結果と保存を確認する。', 'Запустите тот же Web и дождитесь running/SSM Online. Через SSM сравните текст/hash и boot_id: instance/volume/hash сохраняются, boot_id меняется. В P3 Web Portal проверьте сохранение после запуска и дождитесь результата и сохранения.', 'Ayni Web ni Start qilib running/SSM Online ni kuting. SSM da matn/hash va boot_id ni solishtiring: instance/volume/hash bir xil, boot_id yangi bo‘ladi. Web Portal P3 da qayta ishga tushgandan keyingi saqlanishni tekshirib, natija saqlanishini kuting.'),
 '',
 T('練習3項目PASS。EC2のpublic IPv4が変われば外部HTTPの接続先も更新する。', 'Три учебные проверки PASS. Если public IPv4 изменился, используйте новый адрес для внешнего HTTP.', 'Uchta mashq tekshiruvi PASS. Public IPv4 o‘zgarsa, tashqi HTTP uchun yangi manzil ishlating.'),
 T('別instanceを作ると保持の証明にならない。P3/M3は別markerと別証拠を使う。', 'Новый instance не доказывает сохранение. Для P3/M3 нужны отдельные marker и доказательства.', 'Yangi instance saqlanish isboti emas. P3/M3 alohida marker va dalildan foydalanadi.'))

m = module('P4', T('PostgreSQLへの認証接続', 'Подключение к PostgreSQL с аутентификацией', 'PostgreSQL ga autentifikatsiya bilan ulanish'),
 T('DB・role・schemaの違いを理解し、Webだけから既存パスワードでSQLを実行する。', 'Различать database, role и schema; выполнять SQL с Web по установленному паролю.', 'Database, role va schema ni farqlash; Web dan belgilangan parol bilan SQL bajarish.'),
 T('jdu_catalog_practice、catalog_practice_setup、catalog_practice_appを作る。Webの10.20.1.20/32だけからSCRAMで接続させる。P4時点ではappのtableは不要。', 'Создайте jdu_catalog_practice, catalog_practice_setup и catalog_practice_app. Разрешите SCRAM только с Web 10.20.1.20/32. Таблицы приложения на этапе P4 не нужны.', 'jdu_catalog_practice, catalog_practice_setup va catalog_practice_app ni yarating. Faqat Web 10.20.1.20/32 dan SCRAM ulanishiga ruxsat bering. P4 da app jadvallari hali kerak emas.'))
step(m, T("配布サーバーからPostgreSQLをインストールする", "Установить PostgreSQL с сервера пакетов", "Paketlar serveridan PostgreSQL o‘rnatish"), 'db',
 T("DBサーバーにPostgreSQL 16をインストールする。続けて後の手順で使うSQLファイルを展開する。", "Установите PostgreSQL 16 на DB-сервере. Затем распакуйте файлы SQL для следующих шагов.", "DB serverda PostgreSQL 16 ni o‘rnating. Keyingi qadamlar uchun SQL fayllarini arxivdan chiqaring."),
 'sudo apt-get update\nsudo apt-get install --no-install-recommends postgresql-16 postgresql-client-16\nsudo python3 -B /var/lib/jdu-web/lesson-resources-r1/offline_assets.py\npg_lsclusters\nsudo -u postgres psql -X -d postgres -c "SHOW data_directory;"',
 T("`pg_lsclusters` にバージョン `16` とクラスタ名 `main` が表示される。データの保存先は `/var/lib/postgresql/16/main`。", "В `pg_lsclusters` видны версия `16` и кластер `main`. Каталог данных — `/var/lib/postgresql/16/main`.", "`pg_lsclusters` da `16` versiya va `main` klasteri chiqadi. Ma’lumot katalogi `/var/lib/postgresql/16/main`."),
 None)
step(m, T("PostgreSQLの待受アドレス・ポートを設定する", "Настроить адрес и порт PostgreSQL", "PostgreSQL manzili va portini sozlash"), 'db',
 T("`postgresql.conf` で、DBサーバーの内部IP `10.20.2.20` の5432番ポートで受け付けるようにする。パスワード認証にはSCRAM-SHA-256を使う。", "В `postgresql.conf` укажите внутренний IP DB `10.20.2.20` и порт 5432. Для паролей задайте SCRAM-SHA-256.", "`postgresql.conf` da DB serverning ichki IP manzili `10.20.2.20` va 5432-portni belgilang. Parollar uchun SCRAM-SHA-256 ni tanlang."),
 "listen_addresses = '10.20.2.20'\nport = 5432\npassword_encryption = 'scram-sha-256'",
 T("下の3項目を同じ設定ファイルに保存する。再起動は接続許可を設定した後のP4.4で行う。", "Сохраните три параметра в одном файле. Перезапуск выполняется в P4.4 после настройки доступа.", "Uchta parametrni bitta faylga saqlang. Qayta ishga tushirish kirish sozlangach P4.4 da bajariladi."),
 None)
step(m, T("WebサーバーからのDB接続を許可する", "Разрешить соединения с БД от Web-сервера", "Web serveridan DB ulanishiga ruxsat berish"), 'db',
 T("`pg_hba.conf` では、どのサーバーから、どのDBに、どのロールで接続できるかを指定する。Webサーバーの内部IP `10.20.1.20` を送信元にし、練習用と課題用のDB・ロールの組み合わせを許可する。", "В `pg_hba.conf` задайте источники, БД и роли. Разрешите указанные пары БД и ролей для практики и задания с внутреннего IP Web `10.20.1.20`.", "`pg_hba.conf` da manba, DB va rollarni belgilang. Web serverning `10.20.1.20` ichki manzilidan mashq va topshiriq uchun ko‘rsatilgan DB va rol juftliklariga ruxsat bering."),
 '''local all postgres peer
local all all reject
host jdu_catalog_practice catalog_practice_setup 10.20.1.20/32 scram-sha-256
host jdu_catalog_practice catalog_practice_app 10.20.1.20/32 scram-sha-256
host jdu_catalog catalog_setup 10.20.1.20/32 scram-sha-256
host jdu_catalog catalog_app 10.20.1.20/32 scram-sha-256
host all all 0.0.0.0/0 reject
host all all ::/0 reject''',
 T("PostgreSQLは上から読んで最初に一致した行を使う。許可する行を先に置き、その他の接続は末尾の `reject` で拒否する。", "PostgreSQL применяет первую совпавшую строку сверху. Сначала расположены разрешения, затем строки `reject` для остальных соединений.", "PostgreSQL yuqoridan birinchi mos qatorni ishlatadi. Avval ruxsat qatorlari, oxirida qolgan ulanishlar uchun `reject` turadi."),
 None)
step(m, T("PostgreSQLを再起動して設定を確認する", "Перезапустить PostgreSQL и проверить настройки", "PostgreSQL ni qayta ishga tushirib sozlamani tekshirish"), 'db',
 T("再起動して、保存した待受設定と接続許可を反映する。", "Перезапустите PostgreSQL, чтобы применить сохранённые параметры и правила доступа.", "Saqlangan parametr va kirish qoidalarini qo‘llash uchun PostgreSQL ni qayta ishga tushiring."),
 'sudo systemctl restart postgresql@16-main\nsystemctl is-active postgresql@16-main\nsudo ss -lntp\nsudo -u postgres psql -X -d postgres -c "SHOW password_encryption;"\nsudo -u postgres psql -X -d postgres -c "SELECT line_number,error FROM pg_hba_file_rules WHERE error IS NOT NULL;"',
 T("サービスは `active`。待受は `10.20.2.20:5432`、パスワードの保存方式は `scram-sha-256`、接続許可ファイルのエラーは `(0 rows)`。", "Служба — `active`, адрес и порт — `10.20.2.20:5432`, способ хранения пароля — `scram-sha-256`, ошибки правил доступа — `(0 rows)`.", "Xizmat `active`, manzil va port `10.20.2.20:5432`, parol saqlash usuli `scram-sha-256`, kirish xatolari `(0 rows)`."),
 None)
step(m, T("練習用のDBと2つのロールを作る", "Создать учебную БД и две роли", "Mashq DB va ikkita rolini yaratish"), 'db',
 T("付属のSQLで、練習用DB `jdu_catalog_practice` を作る。テーブルを準備するロールは `catalog_practice_setup`、通常のアプリ接続に使うロールは `catalog_practice_app`。最初にSQLの内容を表示し、その後 `psql` に渡して実行する。", "Готовые SQL создают БД `jdu_catalog_practice`. Роль `catalog_practice_setup` подготавливает таблицы, `catalog_practice_app` нужна для обычной работы. Сначала выведите SQL, затем передайте его в `psql`.", "Tayyor SQL `jdu_catalog_practice` DB sini yaratadi. `catalog_practice_setup` jadval tayyorlashga, `catalog_practice_app` odatiy ishlashga xizmat qiladi. Avval SQL ni ko‘ring, so‘ng `psql` orqali bajaring."),
 '''cd /var/lib/jdu-web/lesson-resources-r1/app
python3 -B profile_sql.py --profile practice 01_create_roles.sql
python3 -B profile_sql.py --profile practice 01_create_roles.sql | sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d postgres
python3 -B profile_sql.py --profile practice 02_prepare_schema.sql | sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d jdu_catalog_practice''',
 T("`CREATE ROLE` が2回、`CREATE DATABASE` が1回表示される。", "`CREATE ROLE` появляется дважды, `CREATE DATABASE` — один раз.", "`CREATE ROLE` ikki marta, `CREATE DATABASE` bir marta chiqadi."),
 T('already existsなら成功済みの可能性。DROPで消さず\\duと\\lで対応を確認する。パイプ右側psqlにSQL errorがないことを確認する。', 'При already exists возможен повторный запуск. Не используйте DROP; проверьте роли и БД через \\du и \\l. Убедитесь, что psql справа от pipe не сообщил SQL error.', 'already exists oldin bajarilganini anglatishi mumkin. DROP qilmang; \\du va \\l orqali solishtiring. Pipe o‘ngidagi psql SQL error bermaganini tekshiring.'))
step(m, T("それぞれのDBロールにパスワードを設定する", "Задать пароль каждой роли БД", "Har bir DB roliga parol belgilash"), 'db',
 T("DBサーバーの端末で `psql` を開く。`\\password` を1行ずつ実行し、ロールごとに決めたパスワードを確認のため2回入力する。入力した文字は画面に表示されない。2つのパスワードはP5でも使う。 それぞれ16文字以上で異なるものを設定する。", "Откройте `psql` на DB-сервере. Выполняйте `\\password` по одной строке и дважды введите выбранный пароль каждой роли. Символы скрыты. Оба пароля понадобятся в P5. Задайте разные пароли длиной не менее 16 символов.", "DB serverda `psql` ni oching. `\\password` ni bittadan bajaring va har rol uchun tanlagan parolni ikki marta kiriting. Belgilar ko‘rinmaydi. Ikkala parol P5 da ham kerak. Kamida 16 belgili turli parollarni tanlang."),
 r'''sudo -u postgres psql -X -d postgres
\password catalog_practice_setup
\password catalog_practice_app
\du catalog_practice_*
\q''',
 T("`\\du` に `catalog_practice_setup` と `catalog_practice_app` が表示される。", "В выводе `\\du` есть `catalog_practice_setup` и `catalog_practice_app`.", "`\\du` chiqishida `catalog_practice_setup` va `catalog_practice_app` ko‘rinadi."),
 None)
step(m, T("Webサーバーから練習用DBに接続する", "Подключиться к учебной БД с Web-сервера", "Web serveridan mashq DB ga ulanish"), 'web',
 T("P0と同じ方法でWebサーバーのSession Managerを開く。`psql` で最初はDBサーバーの内部IP、次はP2で登録した `practice-db.lab.test` を指定する。パスワードを聞かれたら、P4.6で `catalog_practice_app` に設定したものを入力する。", "Откройте Session Manager для Web-сервера как в P0. В `psql` сначала укажите внутренний IP DB, затем имя `practice-db.lab.test` из P2. В обоих случаях используйте пароль `catalog_practice_app` из P4.6.", "P0 dagidek Web server uchun Session Manager ni oching. `psql` da avval DB ichki IP manzilini, keyin P2 dagi `practice-db.lab.test` nomini kiriting. Har ikki ulanishda P4.6 dagi `catalog_practice_app` parolini ishlating."),
 '''sudo apt-get install --no-install-recommends postgresql-client-16
psql -X -h 10.20.2.20 -U catalog_practice_app -d jdu_catalog_practice -W -c 'SELECT current_database(),current_user,1 AS value;'
getent ahostsv4 practice-db.lab.test
psql -X -h practice-db.lab.test -U catalog_practice_app -d jdu_catalog_practice -W -c 'SELECT current_database(),current_user,1 AS value;' ''',
 T("どちらの接続でもDBは `jdu_catalog_practice`、ロールは `catalog_practice_app`、SQLの結果は `1` と表示される。", "В обоих случаях результат показывает БД `jdu_catalog_practice`, роль `catalog_practice_app` и значение `1`.", "Ikkala ulanishda `jdu_catalog_practice` DB si, `catalog_practice_app` roli va `1` qiymati chiqadi."),
 T('内部IPで成功し、名前で失敗する場合は、P2で設定した通常の名前解決と練習用のDB名を確認する。認証が拒否される場合は接続元・DB・ロール・パスワードを確認する。DBをInternetへ公開して試さない。', 'Если по IP подключение работает, а по имени нет, проверьте системный DNS и учебное имя DB из P2. При отказе аутентификации проверьте источник, БД, роль и пароль. Не публикуйте DB в Internet для диагностики.', 'IP orqali ulanish ishlasa, nom orqali esa ishlamasa, P2 dagi tizim DNS i va mashq DB nomini tekshiring. Autentifikatsiya rad etilsa, manba, DB, rol va parolni tekshiring. Sinash uchun DB ni Internet ga ochmang.'))
step(m, T("採点に使うDBパスワードをWebサーバーに保存する", "Сохранить пароль БД для проверки на Web-сервере", "Baholash uchun DB parolini Web serverda saqlash"), 'web',
 T("コマンドを実行し、`catalog_practice_app` に設定したパスワードを2回入力する。入力は画面に表示されず、採点で接続を確認できるようWebサーバーの保護されたファイルに保存される。自分のPCの採点ページでP4を確認する。", "Запустите команду и дважды введите пароль `catalog_practice_app`. Ввод скрыт, пароль сохраняется на Web в защищённом файле для проверки подключения. Откройте страницу оценок на своём компьютере и проверьте P4.", "Buyruqni bajarib `catalog_practice_app` parolini ikki marta kiriting. Kiritish yashirin, parol ulanishni tekshirish uchun Web serverdagi himoyalangan faylga yoziladi. O‘z kompyuteringizdagi baholash sahifasida P4 ni tekshiring."),
 'sudo python3 -B /var/lib/jdu-web/lesson-resources-r1/database_secret.py --profile practice',
 T("端末に `D11_EXISTING_DB_PASSWORD_STORED_LOCALLY` が表示され、採点ページでP4の9項目を確認できる。", "Терминал выводит `D11_EXISTING_DB_PASSWORD_STORED_LOCALLY`. На странице оценок видны девять критериев P4.", "Terminalda `D11_EXISTING_DB_PASSWORD_STORED_LOCALLY` chiqadi. Baholash sahifasida P4 ning to‘qqiz mezoni ko‘rinadi."),
 T('既存fileありなら再生成しない。P5では同じDB passwordをapp設定にも入力する。M4はmission用の別DB/roleで構築する。', 'Если файл уже есть, не создавайте заново. В P5 тот же пароль вводится в настройку приложения. M4 использует отдельные БД/роли mission.', 'Fayl mavjud bo‘lsa qayta yaratmang. P5 da ayni DB paroli app sozlamasiga kiritiladi. M4 alohida mission DB/rollaridan foydalanadi.'))

m = module('P5', T('教員アプリをWeb・DBへ接続する', 'Соединить предоставленное приложение с Web и DB', 'Berilgan app ni Web va DB bilan bog‘lash'),
 T('コードを書かず、オフライン依存・専用user・DB初期化・Nginx/systemd・実HTTPをつなぐ。', 'Без программирования связать offline-зависимости, сервисного пользователя, инициализацию БД, Nginx/systemd и реальный HTTP.', 'Dastur yozmasdan offline bog‘liqlik, service user, DB tayyorlash, Nginx/systemd va haqiqiy HTTP ni bog‘lash.'),
 T('practice profileで備品カタログを構築する。M2の正式DNSとP4が現在も使えることが前提。PのDB/管理者とMのDB/管理者を分け、同じWebのapp/portは共有する。', 'Постройте каталог в profile practice. Нужны действующие DNS из M2 и P4. БД/администраторы P и M различны, но приложение и порты на том же Web общие.', 'practice profile da katalogni quring. M2 asosiy DNS va P4 hozir ham ishlashi kerak. P/M DB va admin lari alohida, ayni Web dagi app va port umumiy.'))
step(m, T("アプリに必要な名前解決とPythonパッケージを準備する", "Проверить DNS и подготовить пакеты Python", "DNS ni tekshirish va Python paketlarini tayyorlash"), 'web',
 T("初めにWebサーバーからDBと管理画面の名前を解決する。続けて、配布サーバーからPython環境を作るためのツールをインストールし、備品管理アプリとPythonパッケージを展開する。", "Сначала разрешите имена БД и админки с Web-сервера. Затем установите инструменты Python с сервера пакетов и распакуйте приложение и пакеты Python.", "Avval Web serverdan DB va boshqaruv sahifasi nomlarini yeching. So‘ng paketlar serveridan Python vositalarini o‘rnating, ilova va Python paketlarini oching."),
 'getent ahostsv4 db.lab.test\ngetent ahostsv4 admin.lab.test\nsudo apt-get install --no-install-recommends python3-venv python3-pip\nsudo python3 -B /var/lib/jdu-web/lesson-resources-r1/offline_assets.py --wheels\nls /var/lib/jdu-web/lesson-resources-r1/app\nls /var/lib/jdu-web/lesson-resources-r1/wheels',
 T("`db.lab.test` は `10.20.2.20`、`admin.lab.test` は `10.20.1.20`。端末に `PUBLIC_APP_RESOURCES_VERIFIED` と `SIGNED_OFFLINE_WHEELS_READY=7` が表示される。", "`db.lab.test` даёт `10.20.2.20`, `admin.lab.test` — `10.20.1.20`. В терминале появляются `PUBLIC_APP_RESOURCES_VERIFIED` и `SIGNED_OFFLINE_WHEELS_READY=7`.", "`db.lab.test` uchun `10.20.2.20`, `admin.lab.test` uchun `10.20.1.20` chiqadi. Terminalda `PUBLIC_APP_RESOURCES_VERIFIED` va `SIGNED_OFFLINE_WHEELS_READY=7` ko‘rinadi."),
 None)
step(m, T("アプリのファイルを配置して専用のPython環境を作る", "Разместить приложение и создать его окружение Python", "Ilovani joylab unga alohida Python muhiti yaratish"), 'web',
 T("アプリのファイルを `/opt/jdu-catalog/app` にコピーする。`venv` で専用のPython環境を作り、展開済みのパッケージを入れる。`pip` は外部サイトに接続せず、ファイルが指定のハッシュ値と一致することを確認してからインストールする。", "Скопируйте файлы в `/opt/jdu-catalog/app`. Создайте окружение приложения через `venv` и установите подготовленные пакеты. `pip` проверяет хеши файлов и работает без обращения к внешнему сайту.", "Fayllarni `/opt/jdu-catalog/app` ga nusxalang. `venv` orqali ilova muhitini yaratib, tayyor paketlarni o‘rnating. `pip` tashqi saytga murojaat qilmasdan fayllar xeshlarini tekshiradi."),
 'sudo mkdir -p /opt/jdu-catalog/app\nsudo chown root:root /opt/jdu-catalog/app\nsudo chmod 0755 /opt/jdu-catalog/app\nsudo cp -a /var/lib/jdu-web/lesson-resources-r1/app/. /opt/jdu-catalog/app/\nsudo python3 -m venv /opt/jdu-catalog/venv\nsudo /opt/jdu-catalog/venv/bin/python -m pip --isolated --no-cache-dir install --no-index --find-links=/var/lib/jdu-web/lesson-resources-r1/wheels --only-binary=:all: --require-hashes -r /var/lib/jdu-web/lesson-resources-r1/requirements.lock\nsudo /opt/jdu-catalog/venv/bin/python -m pip check',
 T("最後の `pip check` で `No broken requirements found.` と表示される。", "Последний `pip check` выводит `No broken requirements found.`.", "Oxirgi `pip check` natijasida `No broken requirements found.` chiqadi."),
 None)
step(m, T("アプリを実行するOSユーザーを作る", "Создать системного пользователя приложения", "Ilovani ishga tushiradigan OS foydalanuvchisini yaratish"), 'web',
 T("Webサーバーでアプリを動かすOSユーザー `catalog` を作る。続けて、CSSなどのファイルを集めるディレクトリを作り、`catalog` がその中に書き込めるように設定する。", "Создайте на Web системного пользователя `catalog` для запуска приложения. Подготовьте каталог для CSS и других файлов и дайте `catalog` право записи в него.", "Web serverda ilovani ishlatuvchi `catalog` OS foydalanuvchisini yarating. CSS va boshqa fayllar katalogini yaratib, `catalog` ga yozish huquqini bering."),
 'sudo useradd --system --user-group --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin catalog\nsudo mkdir -p /var/lib/jdu-catalog\nsudo chown root:root /var/lib/jdu-catalog\nsudo chmod 0755 /var/lib/jdu-catalog\nsudo mkdir -p /var/lib/jdu-catalog/static\nsudo chown catalog:catalog /var/lib/jdu-catalog/static\nsudo chmod 0755 /var/lib/jdu-catalog/static\nid catalog\ngetent passwd catalog',
 T("ユーザー `catalog` とログインシェル `/usr/sbin/nologin` が表示される。`/var/lib/jdu-catalog/static` の所有者とグループは `catalog`。", "Вывод показывает пользователя `catalog` и оболочку `/usr/sbin/nologin`. Владелец и группа `/var/lib/jdu-catalog/static` — `catalog`.", "Natijada `catalog` foydalanuvchisi va `/usr/sbin/nologin` ko‘rinadi. `/var/lib/jdu-catalog/static` egasi va guruhi `catalog`."),
 T('権限errorをchmod -R 777やcatalogのsudo追加で解決しない。対象directoryとownerを照合する。', 'Не исправляйте права через chmod -R 777 или добавление catalog в sudo. Проверьте конкретный каталог и владельца.', 'Ruxsat xatosini chmod -R 777 yoki catalog ga sudo berish bilan hal qilmang. Aniq katalog va egasini solishtiring.'))
step(m, T("アプリの通常のDB接続を設定する", "Настроить обычное подключение приложения к БД", "Ilovaning odatiy DB ulanishini sozlash"), 'web',
 T("AWSコンソールでWebサーバーの現在の公開IPv4アドレスを確認し、`YOUR-CURRENT-WEB-PUBLIC-IP` と置き換える。設定コマンドで入力を求められたら、P4で `catalog_practice_app` に設定したパスワードを入力する。作成した練習用の設定をアプリで使うように選ぶ。 入力した文字は画面に表示されない。", "Замените `YOUR-CURRENT-WEB-PUBLIC-IP` на текущий публичный IPv4 Web из AWS Console. При запросе введите пароль `catalog_practice_app` из P4. Выберите созданные учебные настройки для приложения. Вводимые символы скрыты.", "`YOUR-CURRENT-WEB-PUBLIC-IP` o‘rniga AWS Console dagi Web serverning joriy ochiq IPv4 manzilini yozing. So‘ralganda P4 dagi `catalog_practice_app` parolini kiriting. Yaratilgan mashq sozlamasini ilova uchun tanlang. Kiritilgan belgilar ekranda ko‘rinmaydi."),
 """PUBLIC_WEB_IPV4='YOUR-CURRENT-WEB-PUBLIC-IP'
sudo python3 -B /opt/jdu-catalog/app/configuration.py create-runtime --profile practice --public-web-ipv4 "$PUBLIC_WEB_IPV4"
sudo python3 -B /opt/jdu-catalog/app/configuration.py activate --profile practice
sudo python3 -B /opt/jdu-catalog/app/configuration.py check --phase runtime
sudo stat -c '%U:%G %a %n' /etc/jdu-catalog/app.env""",
 T("`CATALOG_ENV_CREATED=practice`、`CATALOG_PROFILE_ACTIVATED=practice`、`VALID` が表示される。`app.env` の所有者は `root:root`、権限は `600`。", "Вывод содержит `CATALOG_ENV_CREATED=practice`, `CATALOG_PROFILE_ACTIVATED=practice` и `VALID`. Для `app.env` ожидаются `root:root` и `600`.", "`CATALOG_ENV_CREATED=practice`, `CATALOG_PROFILE_ACTIVATED=practice` va `VALID` chiqadi. `app.env` egasi va guruhi `root:root`, huquqi `600`."),
 None)
step(m, T("備品管理アプリのテーブルと管理者を用意する", "Подготовить таблицы и администратора приложения", "Ilova jadvallari va administratorini tayyorlash"), 'web',
 T("一時設定の作成時に、P4の `catalog_practice_setup` のパスワードを入力する。コマンドを1行ずつ実行して、テーブルを作り、見本の備品を登録する。最後に `practice_admin` のパスワードを自分で決めて入力する。 入力した文字は画面に表示されない。", "При создании временных настроек введите пароль `catalog_practice_setup` из P4. Выполняйте команды по одной, чтобы создать таблицы и примеры оборудования. В конце выберите и введите пароль `practice_admin`. Вводимые символы скрыты.", "Vaqtinchalik sozlama yaratishda P4 dagi `catalog_practice_setup` parolini kiriting. Jadvallar va namunaviy jihozlarni yaratish uchun buyruqlarni bittadan bajaring. Oxirida `practice_admin` parolini o‘zingiz tanlab kiriting. Kiritilgan belgilar ekranda ko‘rinmaydi."),
 'sudo python3 -B /opt/jdu-catalog/app/configuration.py create-setup --profile practice\nsudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py --phase setup check\nsudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py --phase setup migrate\nsudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py --phase setup seed_catalog\nsudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py --phase setup create_lab_admin',
 T("アプリ用テーブルが11個、見本の備品が3件作られる。管理画面では今回設定した `practice_admin` でログインする。", "Создаются 11 таблиц приложения и три примера. Для входа в админку используется `practice_admin`.", "11 ta ilova jadvali va uchta namunaviy jihoz yaratiladi. Boshqaruv sahifasiga `practice_admin` bilan kirasiz."),
 None)
step(m, T("アプリのDBロールに必要な権限を付ける", "Выдать роли приложения необходимые права в БД", "Ilovaning DB roliga kerakli huquqlarni berish"), 'db',
 T("DBサーバーのSession Managerを開く。通常の備品管理で使う `catalog_practice_app` に、作成済みのテーブルを読み書きするための権限を付ける。先にSQLを表示し、次のコマンドで適用する。", "Откройте Session Manager на DB-сервере. Выдайте `catalog_practice_app` права для работы с уже созданными таблицами. Сначала просмотрите SQL, затем примените его следующей командой.", "DB server uchun Session Manager ni oching. `catalog_practice_app` roliga mavjud jadvallar bilan ishlash huquqlarini bering. Avval SQL ni ko‘ring, keyingi buyruq bilan uni qo‘llang."),
 'cd /var/lib/jdu-web/lesson-resources-r1/app\npython3 -B profile_sql.py --profile practice 03_runtime_grants.sql\npython3 -B profile_sql.py --profile practice 03_runtime_grants.sql | sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d jdu_catalog_practice',
 T("`COMMIT` が表示される。備品テーブル `catalog_item` では読み取り・追加・変更が許可される。", "Вывод заканчивается `COMMIT`. Для `catalog_item` разрешены чтение, добавление и изменение.", "`COMMIT` chiqadi. `catalog_item` jadvalida o‘qish, qo‘shish va o‘zgartirish mumkin."),
 None)
step(m, T("アプリをsystemdサービスとして起動する", "Запустить приложение как службу systemd", "Ilovani systemd xizmati sifatida ishga tushirish"), 'web',
 T("WebサーバーでCSSなどをNginxが配信するディレクトリに集める。サービス定義を `/etc/systemd/system` にコピーし、systemdに読み込ませる。`enable --now` で現在の起動と、次回のOS起動時の自動起動を設定する。", "На Web соберите CSS и другие файлы в каталог для Nginx. Скопируйте описание службы в `/etc/systemd/system` и загрузите его в systemd. `enable --now` запускает службу сейчас и настраивает запуск при загрузке ОС.", "Web serverda CSS va boshqa fayllarni Nginx katalogiga yig‘ing. Xizmat ta’rifini `/etc/systemd/system` ga nusxalab, systemd ga yuklang. `enable --now` xizmatni hozir ishga tushiradi va OS yuklanganda avtomatik startni sozlaydi."),
 'sudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py --phase runtime collectstatic\ncat /opt/jdu-catalog/app/config/jdu-catalog.service\nsudo cp /opt/jdu-catalog/app/config/jdu-catalog.service /etc/systemd/system/jdu-catalog.service\nsudo chown root:root /etc/systemd/system/jdu-catalog.service\nsudo chmod 0644 /etc/systemd/system/jdu-catalog.service\nsudo systemctl daemon-reload\nsudo systemctl enable --now jdu-catalog\nsystemctl is-active jdu-catalog\nsudo ss -lntp',
 T("サービスは `active`。Gunicornは同じWebサーバーのNginxから接続できる `127.0.0.1:8000` で待ち受ける。", "Служба — `active`. Gunicorn слушает `127.0.0.1:8000` для соединений от Nginx на том же Web-сервере.", "Xizmat `active`. Gunicorn shu Web serverdagi Nginx ulanishi uchun `127.0.0.1:8000` da tinglaydi."),
 T('起動errorはjournalctl -u jdu-catalogを見る。秘密設定本文をlogへ貼らず、configuration.py checkで形式を確認する。', 'При ошибке смотрите journalctl -u jdu-catalog. Не копируйте env в журнал; формат проверяется configuration.py check.', 'Xatoda journalctl -u jdu-catalog ni o‘qing. Env mazmunini log ga qo‘ymang; formatni configuration.py check bilan tekshiring.'))
step(m, T("Nginxに公開用と管理用の入口を設定する", "Настроить публичный и административный входы Nginx", "Nginx ning ochiq va boshqaruv kirishlarini sozlash"), 'web',
 T("設定ファイルをコピーして、`sites-enabled` からシンボリックリンクを作る。設定を反映すると、80番ポートで公開一覧、踏み台サーバーからの8080番ポートで管理画面を開ける。Nginxはアプリ宛てのリクエストをGunicornへ転送する。", "Скопируйте конфигурацию и добавьте символическую ссылку в `sites-enabled`. После применения порт 80 открывает список, а порт 8080 с бастиона — админку. Nginx передаёт запросы приложения в Gunicorn.", "Sozlamani nusxalang va `sites-enabled` ichida ramziy havola yarating. Sozlamadan so‘ng 80-port ro‘yxatni, Bastiondan 8080-port boshqaruv sahifasini ochadi. Nginx ilova so‘rovlarini Gunicorn ga yuboradi."),
 'cat /opt/jdu-catalog/app/config/jdu-catalog.nginx.conf\nsudo cp /opt/jdu-catalog/app/config/jdu-catalog.nginx.conf /etc/nginx/sites-available/jdu-catalog\nsudo chown root:root /etc/nginx/sites-available/jdu-catalog\nsudo chmod 0644 /etc/nginx/sites-available/jdu-catalog\nsudo mv -n /etc/nginx/sites-enabled/default /etc/nginx/default-site.before-p5\nsudo ln -s /etc/nginx/sites-available/jdu-catalog /etc/nginx/sites-enabled/jdu-catalog\nsudo nginx -t\nsudo systemctl reload nginx\ncurl -i http://127.0.0.1/practice.txt',
 T("`nginx -t` が成功する。 `/practice.txt` にはHTTP `200` と `JDU WEB-02 practice: HTTP response verified.` が返る。同じ方法で `http://127.0.0.1/mission.txt` を開き、M1の本文も返ることを確かめる。",
   "`nginx -t` проходит. `/practice.txt` возвращает HTTP `200` и `JDU WEB-02 practice: HTTP response verified.` Тем же способом откройте `http://127.0.0.1/mission.txt` и проверьте текст M1.",
   "`nginx -t` muvaffaqiyatli. `/practice.txt` HTTP `200` va `JDU WEB-02 practice: HTTP response verified.` qaytaradi. Shu usulda `http://127.0.0.1/mission.txt` ni ochib M1 matnini tekshiring."),
 None)
step(m, T("管理画面から公開・非公開の備品を1件ずつ登録する", "Добавить через админку открытую и скрытую записи", "Boshqaruv sahifasida bittadan ochiq va yopiq jihoz qo‘shish"), 'gui',
 T("踏み台サーバーへRDP接続し、その中のFirefoxで `http://admin.lab.test:8080/admin/` を開く。P5.5で設定した `practice_admin` でログインする。「備品管理」の「備品」から追加画面を開き、下の表に従って1件ずつ保存する。登録後は公開備品を開いて数量を変更して保存し、表の数量4に戻す。",
   "Подключитесь к бастиону по RDP и откройте в его Firefox `http://admin.lab.test:8080/admin/`. Войдите как `practice_admin` с паролем из P5.5. Откройте «備品» (оборудование) и сохраните две записи по таблице. У опубликованной записи измените количество, сохраните и верните его к 4.",
   "Bastion serveriga RDP orqali ulanib, Firefox da `http://admin.lab.test:8080/admin/` ni oching. P5.5 dagi parol bilan `practice_admin` sifatida kiring. «備品» (jihozlar) bo‘limida jadvaldagi ikki yozuvni bittadan qo‘shing. Ochiq yozuv miqdorini o‘zgartirib saqlang, so‘ng 4 ga qaytaring."),
 'P5-PUBLIC-001 | Practice keyboard | 4 | Training shelf A | is_public=true\nP5-PRIVATE-001 | Practice mouse | 2 | Training shelf B | is_public=false',
 T("管理画面には `P5-PUBLIC-001` と `P5-PRIVATE-001` が表示される。Webサーバーの公開一覧で新しく表示されるのは `P5-PUBLIC-001`。", "В админке видны `P5-PUBLIC-001` и `P5-PRIVATE-001`. В публичном списке из новых записей появляется `P5-PUBLIC-001`.", "Boshqaruv sahifasida `P5-PUBLIC-001` va `P5-PRIVATE-001` ko‘rinadi. Ochiq ro‘yxatda yangi yozuvlardan `P5-PUBLIC-001` chiqadi."),
 None)
step(m, T("登録した2件がDBに保存されたことを確かめる", "Проверить сохранение обеих записей в БД", "Ikkala yozuv DB ga saqlanganini tekshirish"), 'web',
 T("Webサーバーの端末で `psql` を使い、管理画面から登録した2件をDBから読み出す。パスワードを聞かれたらP4.6で設定した `catalog_practice_app` のものを使う。", "В терминале Web прочитайте через `psql` две записи, добавленные в админке. Используйте пароль `catalog_practice_app` из P4.6.", "Web terminalida `psql` orqali boshqaruv sahifasida qo‘shilgan ikki yozuvni o‘qing. P4.6 dagi `catalog_practice_app` parolini ishlating."),
 '''QUERY="SELECT code,name,quantity,location,is_public
FROM catalog_item
WHERE code IN ('P5-PUBLIC-001','P5-PRIVATE-001')
ORDER BY code;"
psql -X -h db.lab.test -U catalog_practice_app -d jdu_catalog_practice -W -c "$QUERY" ''',
 T("`P5-PUBLIC-001` の数量は `4`、公開設定は `t`。`P5-PRIVATE-001` の数量は `2`、公開設定は `f`。名前と保管場所もP5.9の表と照合する。", "У `P5-PUBLIC-001` количество `4` и признак `t`, у `P5-PRIVATE-001` — `2` и `f`. Сверьте также название и место хранения с таблицей P5.9.", "`P5-PUBLIC-001` miqdori `4`, ochiqligi `t`. `P5-PRIVATE-001` miqdori `2`, ochiqligi `f`. Nom va saqlash joyini ham P5.9 jadvali bilan solishtiring."),
 None)
step(m, T("採点ページでアプリの動作を確かめる", "Проверить работу приложения на странице оценок", "Baholash sahifasida ilova ishini tekshirish"), 'portal',
 T("自分のPCの採点ページでP5を開き、**機能・権限を含めて確認する** を選ぶ。`practice_admin` のパスワードを入力し、**このパスワードで確認する** を押す。採点では管理画面から確認用の備品を1件登録し、数量の変更も確かめる。", "На своём компьютере откройте P5 на странице оценок и выберите проверку функций и прав. Введите пароль `practice_admin` и запустите проверку. Она создаёт одну контрольную запись и проверяет изменение количества.", "O‘z kompyuteringizdan baholash sahifasida P5 ni ochib, funksiya va huquqlarni tekshirishni tanlang. `practice_admin` parolini kiritib tekshiruvni boshlang. Tekshiruv bitta nazorat yozuvini yaratadi va miqdor o‘zgarishini tekshiradi."),
 '',
 T("P5の13項目の結果が表示される。採点で登録した確認用の備品は管理画面に残る。", "Появятся результаты 13 критериев P5. Контрольная запись остаётся в админке.", "P5 ning 13 mezoni chiqadi. Nazorat jihozi boshqaruv sahifasida qoladi."),
 None)

m = module('P6', T('最小権限と公開範囲', 'Минимальные права и границы публикации', 'Eng kam huquq va ochiq kirish chegarasi'),
 T('正しい動作を保ち、不要な管理経路・DB権限・秘密fileの公開を拒否する。', 'Сохранить штатную работу, запретив лишние admin-маршруты, SQL-права и раскрытие секретов.', 'To‘g‘ri ishlashni saqlab, ortiqcha admin yo‘li, SQL huquqi va maxfiy fayl ochilishini rad etish.'),
 T('P5のpractice profileを使う。setup roleを無効化し、一時設定を片付け、正規loginを対照に拒否を自動確認する。SGやIAMの許可を広げない。', 'Используйте practice из P5. Отключите setup-role, уберите временную конфигурацию и проверьте отказы при наличии успешного контрольного login. Не расширяйте SG/IAM.', 'P5 practice profile dan foydalaning. Setup role ni o‘chiring, vaqtinchalik sozlamani olib tashlang, muvaffaqiyatli login bilan solishtirib rad etishlarni tekshiring. SG/IAM ni kengaytirmang.'))
step(m, T("アプリがDBでできる操作を調べる", "Посмотреть, что приложение может делать в БД", "Ilova DB da bajara oladigan amallarni ko‘rish"), 'db',
 T("DBサーバーの端末で `psql` を開く。`\\du` で練習用ロールの属性、`\\dp` でテーブルごとのアクセス権限を確認する。", "Откройте `psql` в терминале DB. `\\du` показывает атрибуты учебных ролей, `\\dp` — права по таблицам.", "DB terminalida `psql` ni oching. `\\du` mashq rollari atributlarini, `\\dp` jadval huquqlarini ko‘rsatadi."),
 r'''sudo -u postgres psql -X -d jdu_catalog_practice
\du catalog_practice_*
\dp public.*
\q''',
 T("`catalog_practice_app` に備品を読み取る・追加する・変更する権限がある。備品を削除する権限は付いていない。", "У `catalog_practice_app` есть чтение, добавление и изменение оборудования. Удаление оборудования не разрешено.", "`catalog_practice_app` jihozni o‘qishi, qo‘shishi va o‘zgartirishi mumkin. Jihozni o‘chirish huquqi berilmagan."),
 None)
step(m, T("初期設定用のDBロールでログインできないようにする", "Запретить вход роли, созданной для настройки", "Boshlang‘ich sozlama uchun DB roli kirishini yopish"), 'db',
 T("テーブル作成に使った `catalog_practice_setup` でログインできる状態を残すと、そのパスワードを知られたときに高い権限を使われるおそれがある。SQLを表示して `NOLOGIN` の指定を確認し、`psql` で適用する。", "Если оставить вход для `catalog_practice_setup`, утечка его пароля даёт повышенные права. Просмотрите SQL, найдите `NOLOGIN` и примените его через `psql`.", "`catalog_practice_setup` ochiq qolsa, uning parolini bilgan kishi yuqori huquqlarni ishlatishi mumkin. SQL da `NOLOGIN` ni topib, uni `psql` orqali qo‘llang."),
 'cd /var/lib/jdu-web/lesson-resources-r1/app\npython3 -B profile_sql.py --profile practice 04_disable_setup.sql\npython3 -B profile_sql.py --profile practice 04_disable_setup.sql | sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d jdu_catalog_practice',
 T("`ALTER ROLE` が表示される。`catalog_practice_setup` のログインが無効になり、アプリは通常用の `catalog_practice_app` で引き続き接続できる。", "Появляется `ALTER ROLE`. Вход `catalog_practice_setup` отключён, а приложение продолжает подключаться как `catalog_practice_app`.", "`ALTER ROLE` chiqadi. `catalog_practice_setup` kirishi yopiladi, ilova esa `catalog_practice_app` bilan ulana oladi."),
 None)
step(m, T("Webサーバーの初期設定用ファイルを片付ける", "Убрать временные файлы настройки на Web", "Web serverdagi vaqtinchalik sozlama fayllarini olib tashlash"), 'web',
 T("練習用の初期設定ファイル2つを削除する。次にアプリを停止し、P5で作った通常用の設定 `practice` を選んでから起動する。最後に、アプリのOSユーザー `catalog` がコードを書き換えられないことを確かめる。",
   "Удалите два временных файла настройки. Остановите приложение, выберите профиль `practice` из P5 и запустите приложение. Проверьте, что пользователь ОС `catalog` не может записывать в каталог кода.",
   "Ikkita vaqtinchalik sozlama faylini o‘chiring. Ilovani to‘xtating, P5 dagi `practice` sozlamasini tanlang va ilovani ishga tushiring. `catalog` OS foydalanuvchisi ilova kodiga yoza olmasligini tekshiring."),
 """sudo stat -c '%U:%G %a %n' /etc/jdu-catalog/setup.env /etc/jdu-catalog/profiles/practice.setup.env
sudo rm -- /etc/jdu-catalog/setup.env /etc/jdu-catalog/profiles/practice.setup.env
sudo stat -c '%U:%G %a %n' /etc/jdu-catalog/app.env /etc/jdu-catalog/profiles/practice.app.env /etc/jdu-web/db-practice.runtime.env
sudo systemctl stop jdu-catalog
sudo python3 -B /opt/jdu-catalog/app/configuration.py activate --profile practice
sudo python3 -B /opt/jdu-catalog/app/configuration.py check --phase runtime
sudo systemctl start jdu-catalog
systemctl is-active jdu-catalog
sudo -u catalog find /opt/jdu-catalog/app -writable -print""",
 T("`CATALOG_PROFILE_ACTIVATED=practice` と `VALID` が表示され、アプリは `active` になる。通常用の設定ファイルは `root:root 600`。最後の `find` では何も表示されない。",
   "Появляются `CATALOG_PROFILE_ACTIVATED=practice` и `VALID`, приложение переходит в `active`. У рабочих файлов указано `root:root 600`. Последняя команда `find` ничего не выводит.",
   "`CATALOG_PROFILE_ACTIVATED=practice` va `VALID` chiqadi. Ilova `active` holatida bo‘ladi. Oddiy ish fayllari `root:root 600`. Oxirgi `find` natija chiqarmaydi."),
 T('練習用以外の設定が有効なら、ここで止める。既に削除済みのファイルは削除し直さない。停止・設定の選択・設定チェックが失敗したら、原因を確認してからアプリを起動する。', 'Если активен другой профиль, остановитесь. Не повторяйте удаление отсутствующих файлов. При ошибке остановки, выбора профиля или проверки выясните причину до запуска приложения.', 'Boshqa profil faol bo‘lsa, to‘xtang. O‘chirilgan fayllarni qayta o‘chirmang. To‘xtatish, profilni tanlash yoki tekshirishda xato bo‘lsa, ilovani ishga tushirishdan oldin sababini aniqlang.'))
step(m, T("公開用の80番ポートから見える範囲を確かめる", "Проверить, что видно через публичный порт 80", "Ochiq 80-portdan nimalar ko‘rinishini tekshirish"), 'bst',
 T("踏み台サーバーの端末からWebサーバーの80番ポートへHTTPリクエストを送る。備品一覧が表示され、管理画面や内部設定ファイルが公開されていないことを確かめる。管理画面は、RDPで開いた踏み台サーバーのFirefoxから `http://admin.lab.test:8080/admin/` で確認する。", "Из терминала бастиона отправьте запросы на порт 80 Web. Проверьте доступ к списку и отсутствие публичного доступа к админке и внутренним настройкам. Админку откройте на бастионе через RDP в Firefox по `http://admin.lab.test:8080/admin/`.", "Bastion terminalidan Web ning 80-portiga HTTP so‘rovlarini yuboring. Ro‘yxat ochilishini, boshqaruv sahifasi va ichki sozlamalar yopiq ekanini tekshiring. Boshqaruv sahifasini RDP orqali Bastion Firefox brauzerida `http://admin.lab.test:8080/admin/` bilan oching."),
 'curl -i http://web.lab.test/\ncurl -i http://web.lab.test/admin/\ncurl -i http://web.lab.test/app.env\ncurl -i http://web.lab.test/static/app.env',
 T("一覧はHTTP `200`。`/admin/` と設定ファイルのURLには `403` や `404` が返る。8080番ポートでは管理画面のログインページが表示される。", "Список возвращает HTTP `200`, адреса `/admin/` и файлов настроек — `403` или `404`. На 8080 видна форма входа в админку.", "Ro‘yxat HTTP `200` qaytaradi. `/admin/` va sozlama fayli URL manzillari uchun `403` yoki `404` qaytadi. 8080-portda boshqaruv tizimiga kirish sahifasi chiqadi."),
 T('もしenv本文が見えたら共有せず、その場で教師へ知らせ公開設定を修正する。', 'Если виден текст env, не распространяйте его: сообщите преподавателю и исправьте публикацию.', 'Env matni ko‘rinsa uni ulashmang; o‘qituvchiga aytib ochiq sozlamani tuzating.'))
step(m, T("採点ページでアクセス制御を確かめる", "Проверить ограничения доступа на странице оценок", "Baholash sahifasida kirish cheklovlarini tekshirish"), 'portal',
 T("採点ページでP6を開き、**機能・権限を含めて確認する** を選ぶ。`practice_admin` のパスワードを入力して確認を実行する。採点では、正しいパスワードで管理画面に入れることと、ログインしていない状態では備品を追加・変更できないことを確認する。", "Откройте P6 на странице оценок и выберите проверку функций и прав. Введите пароль `practice_admin` и запустите её. Проверка сравнит успешный вход и отказ добавить или изменить оборудование без входа.", "Baholash sahifasida P6 ni ochib, funksiya va huquqlarni tekshirishni tanlang. `practice_admin` parolini kiriting. Tekshiruv muvaffaqiyatli kirish va tizimga kirmasdan jihozni qo‘shish yoki o‘zgartirish rad etilishini solishtiradi."),
 '',
 T("P6の16項目の結果が表示される。", "Появляются результаты 16 критериев P6.", "P6 ning 16 mezoni natijalari ko‘rinadi."),
 None)

# M requirements and pass-condition tables are generated from the accepted frozen registry.
MISSION_GUIDANCE = {
 'M0': T(
    '''P0で練習したSession Managerの接続手順を使い、今回はDB・DNS・配布・踏み台の4台を操作します。EC2の一覧で対象の行の **Instance ID** をクリックし、**Connect** の右にある矢印から **Connect with SSM Session Manager** を選びます。各サーバーで `ssm-user` として接続し、自分のホームディレクトリに `m0-connection.txt` を作って、下の表にある文字だけを1行で保存してください。

| サーバー | EC2の名前の末尾 | ファイルに書く内容 |
| --- | --- | --- |
| DBサーバー | `-db` | `db` |
| DNSサーバー | `-dns` | `dns` |
| 配布サーバー | `-repo` | `repo` |
| 踏み台サーバー | `-bastion` | `bastion` |

課題画面で **M0** を選ぶと、4台のファイルを個別に確認できます。ファイル1つにつき1点で、満点は4点です。''',
    '''Воспользуйтесь способом подключения из P0 и откройте Session Manager для четырёх серверов. В списке EC2 нажмите **Instance ID** нужного сервера, затем стрелку справа от **Connect** и **Connect with SSM Session Manager**. На каждом сервере войдите как `ssm-user` и создайте в своём домашнем каталоге файл `m0-connection.txt` с одной строкой из таблицы.

| Сервер | Окончание имени в EC2 | Содержимое файла |
| --- | --- | --- |
| Сервер БД | `-db` | `db` |
| DNS-сервер | `-dns` | `dns` |
| Сервер пакетов | `-repo` | `repo` |
| Сервер Bastion | `-bastion` | `bastion` |

Выберите **M0** на странице заданий. За каждый верный файл начисляется 1 балл, всего можно получить 4 балла.''',
    '''P0 dagi ulanish tartibini qo‘llab, to‘rtta server uchun Session Manager’ni oching. EC2 ro‘yxatida kerakli serverning **Instance ID** sini, so‘ng **Connect** yonidagi strelkani va **Connect with SSM Session Manager** bandini bosing. Har bir serverga `ssm-user` sifatida ulanib, uy katalogingizda `m0-connection.txt` faylini yarating va jadvaldagi qiymatni bitta qatorga yozing.

| Server | EC2 dagi nomining oxiri | Fayl mazmuni |
| --- | --- | --- |
| DB server | `-db` | `db` |
| DNS server | `-dns` | `dns` |
| Repo server | `-repo` | `repo` |
| Bastion server | `-bastion` | `bastion` |

Topshiriqlar sahifasida **M0** ni tanlang. Har bir to‘g‘ri fayl uchun 1 ball beriladi. Jami 4 ball.'''),
 'M1': T(
  '''P1と同じWebサーバーで、TCPの80番ポートから `/mission.txt` を配信する。P1で作った `/practice.txt` も引き続き開けるようにする。

1. **Webサーバー（P1.2〜P1.3）**　下の本文を使って課題用ファイルを作る。所有者とグループを `root:root`、権限を `0644` にする。
2. **Webサーバーと踏み台サーバー（P1.4〜P1.6）**　curlで `/mission.txt` にアクセスする。Webサーバー自身では `127.0.0.1`、踏み台からは `10.20.1.20` を指定し、両方でHTTP 200と下の本文が返ることを確認する。Webサーバーのアクセスログでリクエストを探す。''',
  '''На том же Web-сервере настройте выдачу `/mission.txt` по HTTP на TCP-порту 80. Сохраните доступ к `/practice.txt`.

1. **Web-сервер (P1.2–P1.3).** Создайте файл с указанным ниже текстом. Задайте владельца и группу `root:root` и права `0644`.
2. **Web-сервер и бастион (P1.4–P1.6).** Запросите `/mission.txt` через curl. На самом Web используйте `127.0.0.1`, а на бастионе — `10.20.1.20`. В обоих случаях проверьте HTTP 200 и указанный ниже текст. Найдите запросы в журнале доступа Web-сервера.''',
  '''Ayni Web serverda TCP 80 porti orqali `/mission.txt` faylini HTTP da tarqating. `/practice.txt` ham ochiq qolsin.

1. **Web server (P1.2–P1.3).** Quyidagi matn bilan topshiriq faylini yarating. Egasi va guruhini `root:root`, ruxsatlarini `0644` qiling.
2. **Web va Bastion serverlari (P1.4–P1.6).** curl bilan `/mission.txt` ni so‘rang. Web serverning o‘zida `127.0.0.1`, Bastion serverida `10.20.1.20` ni ishlating. Har ikkala joyda HTTP 200 va quyidagi matn qaytishini tekshiring. So‘rovlarni Web serverning access log faylidan toping.'''),
 'M2': T(
  '''P2で構築した内部DNSに、下の6件の名前を追加する。踏み台サーバーから `http://web.lab.test/mission.txt` が開けるようにする。

1. **DNSサーバー（P2.2〜P2.4）**　既存の `lab.test` ゾーンにAレコードを追加する。ゾーンファイルのシリアル番号を更新し、構文検査を通してから設定を読み込む。P2の名前は残してよい。
2. **踏み台サーバーとWebサーバー（P2.5〜P2.8）**　内部DNSへ直接問い合わせた結果と、OSが普段使う名前解決の結果を確認する。踏み台では `web.lab.test` でM1の本文を開き、Webサーバーでは `db.lab.test` が `10.20.2.20` になることを確認する。''',
  '''Добавьте шесть имён из таблицы во внутренний DNS, настроенный в P2. С бастиона должен открываться адрес `http://web.lab.test/mission.txt`.

1. **DNS-сервер (P2.2–P2.4).** Добавьте A-записи в существующую зону `lab.test`. Увеличьте серийный номер зоны, проверьте синтаксис и перечитайте настройки. Имена из P2 можно сохранить.
2. **Бастион и Web-сервер (P2.5–P2.8).** Проверьте прямой запрос к внутреннему DNS и обычное разрешение имён ОС. На бастионе откройте текст M1 по имени `web.lab.test`. На Web проверьте, что `db.lab.test` разрешается в `10.20.2.20`.''',
  '''P2 da sozlangan ichki DNS ga jadvaldagi oltita nomni qo‘shing. Bastion serveridan `http://web.lab.test/mission.txt` ochilsin.

1. **DNS server (P2.2–P2.4).** Mavjud `lab.test` zonasiga A yozuvlarini qo‘shing. Zona seriya raqamini oshiring, sintaksisni tekshiring va sozlamani qayta yuklang. P2 nomlarini saqlash mumkin.
2. **Bastion va Web serverlari (P2.5–P2.8).** Ichki DNS ga to‘g‘ridan to‘g‘ri so‘rovni va OS ning odatiy nom yechimini tekshiring. Bastionda `web.lab.test` orqali M1 matnini oching. Web serverda `db.lab.test` manzili `10.20.2.20` bo‘lishini tekshiring.'''),
 'M3': T('M専用markerを自分のLab IDで作る。P3とは別のブラウザで停止前記録→AWS Stop→ブラウザで停止完了確認→AWS Start→ブラウザで再開後確認を行う。対象は同じWebと元root volume。単なるrebootでは不可。backup/restoreとdisk追加は不要。', 'Создайте отдельный marker M со своим Lab ID. Отдельно от P3 пройдите браузер: запись до остановки → AWS Stop → браузер: подтверждение остановки → AWS Start → браузер: проверка после запуска. Нужны тот же Web и исходный root volume; reboot не подходит. Backup/restore и новый диск не нужны.', 'O‘z Lab ID bilan alohida M marker yarating. P3 dan alohida brauzerda oldingi holat → AWS Stop → brauzerda to‘xtashni tekshirish → AWS Start → brauzerda saqlanishni tekshirish ketma-ketligini bajaring. Ayni Web va asl root volume kerak; oddiy reboot yetmaydi. Backup/restore va yangi disk kerak emas.'),
 'M4': T(
  '''P4で使ったPostgreSQLに、下の課題用データベースと2つのロールを作る。アプリのテーブルはM5で用意する。

1. **DBサーバー（P4.2〜P4.6）**　課題用DBとロールを作り、Webサーバー（`10.20.1.20/32`）から指定のDB・ロールで接続できるようにする。認証方式にはP4と同じSCRAMを使う。
2. **Webサーバー（P4.7〜P4.8）**　`db.lab.test` に通常運用用ロールで接続し、SELECTが成功することを確かめる。P4.8と同じ方法で、既存パスワードを課題用（`mission`）として保存する。''',
  '''В PostgreSQL из P4 создайте основную БД и две роли, указанные ниже. Таблицы приложения создаются в M5.

1. **DB-сервер (P4.2–P4.6).** Создайте БД и роли и разрешите подключение к нужной БД с указанными ролями только с Web-сервера (`10.20.1.20/32`). Используйте SCRAM, как в P4.
2. **Web-сервер (P4.7–P4.8).** Подключитесь к `db.lab.test` под рабочей ролью и выполните SELECT. Сохраните существующий пароль для профиля `mission` тем же способом, что и в P4.8.''',
  '''P4 dagi PostgreSQL da quyida ko‘rsatilgan topshiriq ma’lumotlar bazasi va ikkita rolni yarating. Ilova jadvallari M5 da yaratiladi.

1. **DB server (P4.2–P4.6).** Baza va rollarni yarating. Tegishli bazaga ko‘rsatilgan rollar bilan faqat Web serverdan (`10.20.1.20/32`) ulanishga ruxsat bering. P4 dagidek SCRAM ishlating.
2. **Web server (P4.7–P4.8).** Oddiy ish rejimi roli bilan `db.lab.test` ga ulanib, SELECT bajarilishini tekshiring. Mavjud parolni P4.8 dagi usul bilan `mission` profili uchun saqlang.'''),
 'M5': T(
  '''P5で動かした備品管理アプリを、M4で構築した課題用DBにつなぐ。P6で練習用の設定を仕上げてから始める。

1. **Webサーバー（P6.3、P5.4〜P5.5）**　アプリを停止し、使用する設定を `mission` に切り替える。配備済みのアプリを使い、課題用DBにテーブルと初期データを用意し、アプリ管理者を作る。
2. **DBサーバーとWebサーバー（P5.6〜P5.8）**　通常運用用ロールに権限を付け、アプリを起動する。公開ページと管理画面の両方を開き、`/practice.txt` と `/mission.txt` も引き続き開けることを確かめる。
3. **踏み台サーバー（P5.9）**　`http://admin.lab.test:8080/admin/` に `lab_admin` で入り、下の2件を登録する。一般ページでは公開にした備品を確認する。''',
  '''Подключите приложение инвентаризации из P5 к основной БД из M4. Перед переключением завершите настройку тренировочного профиля в P6.

1. **Web-сервер (P6.3, P5.4–P5.5).** Остановите приложение и выберите профиль `mission`. Используйте уже развёрнутое приложение. Создайте таблицы, исходные данные и учётную запись администратора в основной БД.
2. **DB- и Web-серверы (P5.6–P5.8).** Назначьте права рабочей роли и запустите приложение. Откройте публичную и административную страницы. Убедитесь, что `/practice.txt` и `/mission.txt` всё ещё доступны.
3. **Бастион (P5.9).** Войдите в `http://admin.lab.test:8080/admin/` как `lab_admin` и внесите две записи из таблицы. На публичной странице проверьте опубликованную запись.''',
  '''P5 dagi jihozlar ilovasini M4 da tayyorlangan topshiriq bazasiga ulang. Profilni almashtirishdan oldin P6 da mashq sozlamasini yakunlang.

1. **Web server (P6.3, P5.4–P5.5).** Ilovani to‘xtating va `mission` profilini tanlang. Mavjud ilovadan foydalanib, topshiriq bazasida jadvallar, boshlang‘ich ma’lumotlar va administratorni yarating.
2. **DB va Web serverlari (P5.6–P5.8).** Oddiy ish rejimi roliga huquqlarni bering va ilovani ishga tushiring. Ochiq sahifa hamda boshqaruv sahifasini oching. `/practice.txt` va `/mission.txt` ham ochilishini tekshiring.
3. **Bastion serveri (P5.9).** `http://admin.lab.test:8080/admin/` manziliga `lab_admin` bilan kiring va jadvaldagi ikki yozuvni kiriting. Ochiq sahifada e’lon qilingan yozuvni tekshiring.'''),
 'M6': T(
  '''P6で練習した方法で、M5の備品管理アプリを通常運用に切り替える。構築時だけ使った接続を閉じ、アプリと管理者に必要な権限を残す。

1. **DBサーバー（P6.1〜P6.2）**　`catalog_app` の権限を確認する。構築用の `catalog_setup` はログイン不可にし、パスワードと既存の接続を残さない。
2. **Webサーバー（P6.3〜P6.4）**　課題用の一時設定（`/etc/jdu-catalog/setup.env` と `/etc/jdu-catalog/profiles/mission.setup.env`）を片付け、通常運用用の `mission` 設定で起動する。実行ユーザーによるコードの書き換えを防ぎ、秘密を含む設定は `root:root`、`0600` にする。
3. **一般ページと管理画面（P6.4〜P6.5）**　公開の80番ポートではM5の公開備品だけを表示する。踏み台から8080番ポートの管理画面に入り、`lab_admin` が備品を閲覧・追加・変更できることを確認する。''',
  '''Переведите приложение M5 в обычный режим работы способом из P6. Закройте доступ, нужный только при настройке, и сохраните необходимые права приложения и администратора.

1. **DB-сервер (P6.1–P6.2).** Проверьте права `catalog_app`. Запретите вход для роли настройки `catalog_setup`, удалите её пароль и завершите оставшиеся соединения.
2. **Web-сервер (P6.3–P6.4).** Уберите временные настройки (`/etc/jdu-catalog/setup.env` и `/etc/jdu-catalog/profiles/mission.setup.env`) и запустите приложение с рабочим профилем `mission`. Пользователь сервиса не должен менять код. Файлы с секретами принадлежат `root:root` и имеют права `0600`.
3. **Открытая и административная страницы (P6.4–P6.5).** На порту 80 должна отображаться только публичная запись из M5. Откройте панель управления с бастиона на порту 8080 и проверьте, что `lab_admin` может просматривать, добавлять и изменять предметы.''',
  '''M5 ilovasini P6 dagi usul bilan oddiy ish rejimiga o‘tkazing. Faqat sozlashda kerak bo‘lgan kirishni yoping, ilova va administrator uchun zarur huquqlarni qoldiring.

1. **DB server (P6.1–P6.2).** `catalog_app` huquqlarini tekshiring. Sozlash roli `catalog_setup` uchun kirishni yoping, parolini olib tashlang va qolgan ulanishlarini yakunlang.
2. **Web server (P6.3–P6.4).** Vaqtinchalik sozlamalarni (`/etc/jdu-catalog/setup.env` va `/etc/jdu-catalog/profiles/mission.setup.env`) olib tashlang va ilovani oddiy ish uchun `mission` profili bilan ishga tushiring. Xizmat foydalanuvchisi kodni o‘zgartira olmasin. Maxfiy sozlamalar `root:root` ga tegishli bo‘lsin va `0600` ruxsatiga ega bo‘lsin.
3. **Ochiq va boshqaruv sahifalari (P6.4–P6.5).** 80-portda M5 dagi faqat ochiq yozuv ko‘rinsin. Bastion orqali 8080-portdagi boshqaruv sahifasini oching. `lab_admin` jihozlarni ko‘rishi, qo‘shishi va o‘zgartirishi mumkinligini tekshiring.'''),
}
