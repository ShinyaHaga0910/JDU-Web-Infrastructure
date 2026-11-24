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
def step(m, title, place, why, code, expect, trouble):
    m['steps'].append(dict(title=title, place=place, why=why, code=code.strip(), expect=expect, trouble=trouble))

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
    ('rdp-bastion-select', T('踏み台サーバーを選ぶ', 'Выберите бастион', 'Oraliq serverni tanlang'), T(
        'EC2 → Instancesで、自分の演習環境のうち名前の末尾が `-bastion` の行を探し、同じ行の **Instance ID** をクリックする。',
        'Откройте EC2 → Instances, найдите в своей учебной среде строку с окончанием имени `-bastion` и нажмите **Instance ID** в этой строке.',
        'EC2 → Instances bo‘limida o‘z muhitingizdagi nomi `-bastion` bilan tugaydigan qatorni toping va shu qatordagi **Instance ID** ni bosing.')),
    ('rdp-bastion-public-ip', T('公開IPv4アドレスをコピーする', 'Скопируйте публичный IPv4-адрес', 'Ommaviy IPv4 manzilini nusxalang'), T(
        'インスタンスの詳細画面で **Public IPv4 address** の横にあるコピーアイコンを押す。次に入力するのは、自分の画面に表示された現在の公開IPv4アドレス。スクリーンショットの値は例。',
        'На странице экземпляра нажмите значок копирования рядом с **Public IPv4 address**. На следующем шаге используйте текущий адрес из своей консоли. Адрес на снимке приведён для примера.',
        'Instans tafsilotlarida **Public IPv4 address** yonidagi nusxalash belgisini bosing. Keyingi qadamda o‘z oynangizdagi joriy ommaviy IPv4 manzilini ishlating. Rasmdagi manzil misol.')),
    ('rdp-connect', T('公開IPv4アドレスを入力して接続する', 'Введите публичный IPv4-адрес и подключитесь', 'Ommaviy IPv4 manzilini kiritib ulaning'), T(
        '「リモート デスクトップ接続」の **コンピューター** 欄に、手順2でコピーした公開IPv4アドレスを貼り付け、**接続** を押す。',
        'В окне «Подключение к удалённому рабочему столу» вставьте скопированный на шаге 2 публичный IPv4-адрес в поле **Компьютер** и нажмите **Подключить**.',
        'Remote Desktop Connection oynasidagi **Computer** maydoniga 2-qadamda nusxalangan ommaviy IPv4 manzilini qo‘ying va **Connect** tugmasini bosing.')),
    ('rdp-certificate', T('証明書の確認画面を読む', 'Проверьте предупреждение о сертификате', 'Sertifikat ogohlantirishini tekshiring'), T(
        'この画面が出た場合は、表示された接続先を手順2の公開IPv4アドレスと照合する。接続先が今回の踏み台であり、演習用の証明書だと教師に確認できたら **はい** を押す。確認できない場合は **いいえ** を押して教師に相談する。',
        'Если появилось это окно, сверьте адрес назначения с публичным IPv4 из шага 2. Нажмите **Да**, когда преподаватель подтвердит, что это ваш бастион и сертификат учебной среды. Если подтвердить это не удалось, нажмите **Нет** и обратитесь к преподавателю.',
        'Bu oyna chiqsa, ulanish manzilini 2-qadamdagi ommaviy IPv4 manzili bilan solishtiring. O‘qituvchi bu sizning oraliq serveringiz va mashq sertifikati ekanini tasdiqlasa, **Yes** ni bosing. Tasdiqlanmasa, **No** ni bosing va o‘qituvchiga murojaat qiling.')),
    ('rdp-xrdp-login', T('踏み台サーバーにログインする', 'Войдите на бастион', 'Oraliq serverga kiring'), T(
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
 T('Webの/var/www/html/practice.txtから指定本文をHTTP200で返す。Web自身・踏み台・外部の三経路で確認する。', 'Файл /var/www/html/practice.txt на Web должен возвращать заданный текст с HTTP 200: локально, с бастиона и извне.', 'Web dagi /var/www/html/practice.txt belgilangan matnni HTTP 200 bilan qaytarsin: Web ichidan, bastiondan va tashqaridan tekshiring.'))
step(m, T('内部APTからNginxを導入する', 'Установить Nginx из внутреннего APT', 'Ichki APT dan Nginx o‘rnatish'), 'web',
 T('P0と同じ方法でWebへSSM接続し、role=webを確認する。APTのsourceを読み、10.20.2.30の署名済みrepoだけを使う。updateは一覧を取得し、installはpackageを導入する。Internet用sourceを追加しない。',
   'Подключитесь по SSM к Web как в P0 и проверьте role=web. Проверьте APT source: используется только подписанный repo 10.20.2.30. update получает индекс, install устанавливает пакет. Не добавляйте внешние источники.',
   'P0 dagidek Web ga SSM orqali kiring va role=web ni tekshiring. APT source faqat 10.20.2.30 dagi imzolangan repo ekanini ko‘ring. update indeksni oladi, install paketni o‘rnatadi. Internet source qo‘shmang.'),
 'cat /etc/apt/sources.list.d/jdu-web.sources\nsudo apt-get update -o APT::Update::Error-Mode=any\nsudo apt-get install --no-install-recommends nginx',
 T('sourceに内部IPとSigned-Byがあり、署名エラーなしで終了する。インストール確認にYを入力する。', 'В source указаны внутренний IP и Signed-By; установка завершается без ошибки подписи. На запрос установки ответьте Y.', 'Source ichida ichki IP va Signed-By bor; imzo xatosisiz tugaydi. O‘rnatish tasdig‘iga Y kiriting.'),
 T('取得失敗ならrepoのrunning/SSMとIPを確認。--allow-unauthenticatedや外部pipで回避しない。', 'При ошибке получения проверьте repo, его running/SSM и IP. Не обходите подпись через --allow-unauthenticated или внешний pip.', 'Yuklash xatosida repo running/SSM va IP ni tekshiring. --allow-unauthenticated yoki tashqi pip bilan chetlab o‘tmang.'))
step(m, T('正しい本文を作り、所有者と権限を揃える', 'Создать точный текст и права файла', 'Aniq matn yaratish va ruxsatlarni sozlash'), 'web',
 T('まずnanoで練習本文を編集する。表示する1行は下の指定どおりで、最後に改行を入れる。Ctrl+O→Enterで保存、Ctrl+Xで終了する。installはファイルを配置し、-o/-gは所有者、-mは権限を指定する。',
   'Создайте текст через nano: одна точная строка, указанная ниже, с переводом строки в конце. Ctrl+O → Enter сохраняет, Ctrl+X закрывает редактор. install копирует файл; -o/-g задают владельца и группу, -m — права.',
   'nano da quyida ko‘rsatilgan bitta aniq qatorni yarating va oxiriga yangi qator qo‘ying. Ctrl+O → Enter saqlaydi, Ctrl+X yopadi. install faylni joylaydi; -o/-g egasi va guruhni, -m ruxsatni belgilaydi.'),
 """cd ~
mkdir -p jdu-web-practice/p1
cd jdu-web-practice/p1
pwd
nano practice.txt
# File content: JDU WEB-02 practice: HTTP response verified.
sudo install -o root -g root -m 0644 practice.txt /var/www/html/practice.txt
stat -c '%U:%G %a %n' /var/www/html/practice.txt
cat /var/www/html/practice.txt""",
 T('root:root 644。本文は JDU WEB-02 practice: HTTP response verified. の1行である。大文字、小文字、空白、句点も判定対象。', 'Ожидается root:root 644 и ровно строка JDU WEB-02 practice: HTTP response verified. Регистр, пробелы, точка и конечный перевод строки важны.', 'root:root 644 va aynan JDU WEB-02 practice: HTTP response verified. qatori chiqadi. Harf registri, bo‘shliq, nuqta va oxirgi yangi qator muhim.'),
 T('空白画面ならまだnano内。保存して終了してから次のcommandを実行する。既存のmission.txtは変更しない。', 'Если вы ещё в nano, сначала сохраните и выйдите. Не меняйте существующий mission.txt.', 'Hali nano ichida bo‘lsangiz, avval saqlab chiqing. Mavjud mission.txt ni o‘zgartirmang.'))
step(m, T('Web rootとportを確認して起動する', 'Проверить Web root и запустить сервис', 'Web root ni tekshirish va service ni ishga tushirish'), 'web',
 T('Ubuntuの初期siteは/var/www/htmlをrootにする。nginx -Tで実効設定を読み、/etc/nginx/sites-enabled/defaultが有効でrootとlisten 80があることを確認する。変更が必要ならsudo nanoで編集し、構文検査に成功してからreloadする。enable --nowは今起動し、次のOS起動時も起動させる。',
   'Начальный сайт Ubuntu использует root /var/www/html. Через nginx -T найдите включённый /etc/nginx/sites-enabled/default, root и listen 80. При необходимости редактируйте sudo nano; reload выполняйте после успешной проверки. enable --now запускает сейчас и включает автозапуск.',
   'Ubuntu boshlang‘ich sayti root sifatida /var/www/html dan foydalanadi. nginx -T da /etc/nginx/sites-enabled/default, root va listen 80 ni toping. Kerak bo‘lsa sudo nano bilan tahrirlang; tekshiruvdan keyin reload qiling. enable --now hozir ishga tushiradi va keyingi OS yuklanishiga yoqadi.'),
 'sudo nginx -T\nsudo nginx -t\nsudo systemctl enable --now nginx\nsudo systemctl reload nginx\nsystemctl is-active nginx\nsudo ss -lntp',
 T('syntax is ok/test is successful、active、0.0.0.0:80等の待受。127.0.0.1:80だけでは他のサーバーから利用できない。', 'Ожидаются успешный синтаксис, active и слушатель вроде 0.0.0.0:80. Только 127.0.0.1:80 недоступен другим узлам.', 'Sintaksis muvaffaqiyatli, active va 0.0.0.0:80 kabi tinglash bor. Faqat 127.0.0.1:80 bo‘lsa, boshqa server foydalana olmaydi.'),
 T('失敗時はnginx -tのfile名・行番号を確認し、そのfileを直す。SGを変更しても構文エラーは直らない。', 'При ошибке используйте имя файла и строку из nginx -t. Изменение SG не исправит синтаксис.', 'Xatoda nginx -t ko‘rsatgan fayl va qatorni tuzating. SG ni o‘zgartirish sintaksis xatosini tuzatmaydi.'))
step(m, T('Web自身から応答を見る', 'Посмотреть ответ на самом Web', 'Web ichidan javobni ko‘rish'), 'web',
 T('curlはHTTP client。-iはstatus/headerと本文を表示する。127.0.0.1は今のWeb自身で、public IPではない。表示を読み、端末のcommandが成功しただけで合格としない。',
   'curl — HTTP-клиент; -i показывает статус, заголовки и тело. 127.0.0.1 означает этот Web-сервер, не его public IP. Сравните ответ, а не только код завершения команды.',
   'curl HTTP client; -i status, header va body ni ko‘rsatadi. 127.0.0.1 shu Web serverning o‘zi, public IP emas. Faqat buyruq tugaganini emas, javobni solishtiring.'),
 'curl --noproxy \'*\' -i http://127.0.0.1/practice.txt',
 T('HTTP200と指定本文。404はfile/root/URLの関係、connection refusedはservice/listenを調べる。', 'HTTP 200 и заданный текст. При 404 проверяйте файл/root/URL; при connection refused — сервис и слушатель.', 'HTTP 200 va belgilangan matn. 404 bo‘lsa fayl/root/URL, connection refused bo‘lsa service va tinglashni tekshiring.'),
 T('Welcome to nginxが出るなら/ではなく/practice.txtを要求したか確認する。', 'При Welcome to nginx проверьте, что запросили /practice.txt, а не /.', 'Welcome to nginx chiqsa, / emas, /practice.txt so‘ralganini tekshiring.'))
step(m, T('踏み台と外部から同じファイルを見る', 'Проверить тот же файл с бастиона и извне', 'Bastiondan va tashqaridan shu faylni tekshirish'), 'bst',
 T('Web端末をexitで閉じ、CloudShellから踏み台へSSM接続して下のURLを要求する。その後exitでCloudShellへ戻り、EC2に表示された現在のWeb公開IPv4を使って同じpathをcurl -iで要求する。内部の10.20.1.20と公開IPv4を混同しない。',
   'Выйдите из Web через exit, откройте SSM бастиона из CloudShell и запросите URL ниже. Затем exit возвращает в CloudShell; там запросите тот же путь командой curl -i по текущему public IPv4 Web из EC2. Не путайте private 10.20.1.20 с public IPv4.',
   'Web dan exit bilan chiqing, CloudShell dan bastion SSM terminalini ochib quyidagi URL ni so‘rang. Keyin exit bilan CloudShell ga qayting; EC2 dagi hozirgi Web public IPv4 orqali shu path ni curl -i bilan so‘rang. 10.20.1.20 private IP va public IPv4 ni adashtirmang.'),
 'curl --noproxy \'*\' -i http://10.20.1.20/practice.txt',
 T('両経路とも200/同じ本文。InternetからのHTTP80は公開、管理8080とDB5432は公開しない。', 'На обоих маршрутах 200 и одинаковый текст. HTTP 80 открыт, управляющий 8080 и DB 5432 не публикуются.', 'Ikkala yo‘lda ham 200 va bir xil matn. HTTP 80 ochiq, boshqaruv 8080 va DB 5432 tashqariga ochilmaydi.'),
 T('内部成功/外部失敗なら現在のpublic IPとLab稼働を確認する。教師の基盤SGを無断で緩めない。', 'Если внутренний запрос успешен, а внешний нет, проверьте текущий public IP и Lab. Не ослабляйте базовые SG.', 'Ichki so‘rov o‘tib tashqi so‘rov o‘tmasa, public IP va Lab holatini tekshiring. Asosiy SG ni o‘zboshimchalik bilan kengaytirmang.'))
step(m, T('要求とlogを結び付けて提出する', 'Связать запрос с журналом и отправить', 'So‘rovni log bilan bog‘lash va yuborish'), 'web',
 T('Webへ戻り、access logの時刻・client IP・path・statusを見る。logは実際に要求を処理した証拠で、fileがある証拠とは別。exitでCloudShellへ戻ったら、PCのWeb PortalでP1を選び「この課題を確認する」を押す。', 'Вернитесь на Web. В access log найдите время, IP клиента, путь и статус. Это доказательство обработки запроса, не только наличия файла. После exit в CloudShell выберите P1 в Web Portal на PC и запустите проверку.', 'Web ga qayting. Access log da vaqt, client IP, path va statusni ko‘ring. Bu fayl borligidan tashqari so‘rov ishlanganining dalilidir. Exit bilan CloudShell ga qaytgach, PC dagi Web Portal da P1 ni tekshiring.'),
 'sudo tail -n 20 /var/log/nginx/access.log\nexit',
 T('練習8項目と準備確認の結果が表示・保存される。P1は成績0点。M1は別file/本文で自分で構成する。', 'Результаты восьми учебных проверок и готовности показаны и сохранены. P1 не даёт оценочных баллов; M1 требует другого файла и текста.', 'Sakkizta mashq va tayyorlik tekshiruvi natijalari ko‘rinib saqlanadi. P1 bahoga ball qo‘shmaydi; M1 boshqa fayl va matn bilan bajariladi.'),
 T('処理中なら結果を更新する。保存に失敗していれば表示された理由を確認する。checkerの期待本文を書き換えない。', 'Если идёт обработка, обновите результат. При ошибке сохранения прочитайте причину. Не меняйте ожидаемый текст checker.', 'Ishlov davom etsa natijani yangilang. Saqlash xatosida sababni o‘qing. Checker kutgan matnni o‘zgartirmang.'))

m = module('P2', T('内部DNSと通常の名前解決', 'Внутренний DNS и системное разрешение имён', 'Ichki DNS va odatiy nom yechimi'),
 T('BINDのzone・A record・問い合わせ制限と、client側resolverを順に構築する。', 'Последовательно настроить zone, A-записи, ACL BIND и resolver клиентов.', 'BIND zone, A record, ACL va client resolver ni ketma-ket sozlash.'),
 T('guide.lab.test→10.20.1.20、practice-db.lab.test→10.20.2.20を設定する。P1のHTTPを名前で利用する。基盤の固定IPは変えない。', 'Настройте guide.lab.test → 10.20.1.20 и practice-db.lab.test → 10.20.2.20; откройте HTTP из P1 по имени. Фиксированные IP не меняются.', 'guide.lab.test → 10.20.1.20 va practice-db.lab.test → 10.20.2.20 ni sozlang; P1 HTTP ni nom orqali oching. Asosiy IP lar o‘zgarmaydi.'))
step(m, T('BINDを導入し元設定を残す', 'Установить BIND и сохранить исходные настройки', 'BIND o‘rnatish va asl sozlamani saqlash'), 'dns',
 T('DNSへSSMで入りrole=dnsを確認。cp -aは元fileの属性を保って控えを作る。-nは既存の控えを上書きしない。これは編集失敗への控えであり、DB backup/restore課題ではない。', 'Подключитесь к DNS, проверьте role=dns. cp -a сохраняет атрибуты исходного файла, -n не заменяет прежнюю копию. Это страховка при редактировании, не задание по backup/restore БД.', 'DNS ga kirib role=dns ni tekshiring. cp -a asl fayl atributlarini saqlaydi; -n eski nusxa ustiga yozmaydi. Bu tahrir xatosi uchun nusxa, DB backup/restore topshirig‘i emas.'),
 'sudo apt-get update -o APT::Update::Error-Mode=any\nsudo apt-get install --no-install-recommends bind9 bind9-utils\nsudo cp -an /etc/bind/named.conf.options /etc/bind/named.conf.options.before-p2\nsudo cp -an /etc/bind/named.conf.local /etc/bind/named.conf.local.before-p2',
 T('内部repoから導入される。後のM2では同じDNSにrecordを追加し、P2のrecordを消さない。', 'Установка использует внутренний repo. В M2 добавляйте записи в этот же DNS, сохраняя P2.', 'Ichki repo dan o‘rnatiladi. M2 da shu DNS ga record qo‘shilib, P2 record lari saqlanadi.'),
 T('別Labのnamed.conf全体を流用しない。既に自分のzoneがある場合は内容を読んでから編集する。', 'Не копируйте целиком named.conf из чужого Lab. Если своя zone уже есть, сначала изучите её.', 'Boshqa Lab named.conf faylini to‘liq ko‘chirmang. O‘zingizning zone mavjud bo‘lsa, avval o‘qing.'))
step(m, T('問い合わせ元とforwarderを設定する', 'Настроить клиентов и forwarder', 'Client lar va forwarder ni sozlash'), 'dns',
 T('sudo nano /etc/bind/named.conf.optionsで次の内容を設定し保存する。aclは許可するclient集合、listen-onはDNS自身の待受、forward onlyは外部名をAWS DNSへ渡す指定。recursionとqueryの両方を同じ3送信元へ限定する。dnssec-validation noは閉じた学習用forward構成に合わせた設定である。',
   'Откройте sudo nano /etc/bind/named.conf.options, введите и сохраните текст ниже. acl задаёт разрешённых клиентов; listen-on — адреса DNS; forward only передаёт внешние имена AWS DNS. И query, и recursion ограничены тремя источниками. dnssec-validation no соответствует изолированной учебной схеме forwarding.',
   'sudo nano /etc/bind/named.conf.options ni ochib quyidagi matnni saqlang. acl ruxsatli client larni, listen-on DNS tinglashini belgilaydi; forward only tashqi nomlarni AWS DNS ga uzatadi. Query va recursion uchta manbaga cheklanadi. dnssec-validation no yopiq o‘quv forwarding tuzilmasiga mos.'),
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
 T('これは設定fileの内容で、shellへ直接実行しない。10.20.0.2はAWS resolver、10.20.2.10は自分のBIND。', 'Это содержимое файла, не команды shell. 10.20.0.2 — resolver AWS, 10.20.2.10 — ваш BIND.', 'Bu shell buyrug‘i emas, fayl mazmuni. 10.20.0.2 — AWS resolver, 10.20.2.10 — o‘z BIND serveringiz.'),
 T('セミコロン・波括弧も構文。0.0.0.0/0やanyで許可を広げない。', 'Точки с запятой и фигурные скобки обязательны. Не расширяйте ACL до any или 0.0.0.0/0.', 'Nuqtali vergul va qavslar sintaksis qismidir. ACL ni any yoki 0.0.0.0/0 gacha kengaytirmang.'))
step(m, T('zoneを登録しA recordを書く', 'Объявить zone и создать A-записи', 'Zone ni e’lon qilish va A record yozish'), 'dns',
 T('sudo nano /etc/bind/named.conf.localで先頭のzoneブロックを記入。sudo install -d -m 0755 /etc/bind/zonesの後、sudo nano /etc/bind/zones/db.lab.testで残りを記入する。SOAは管理情報、NSは権威DNS、Aは名前とIPv4。末尾のドットは絶対名を示す。serialは編集のたびに増やす。',
   'В sudo nano /etc/bind/named.conf.local запишите первый блок zone. Создайте каталог командой sudo install -d -m 0755 /etc/bind/zones, затем откройте sudo nano /etc/bind/zones/db.lab.test и запишите остальной текст. SOA — служебные данные, NS — авторитетный DNS, A — имя/IPv4. Точка в конце обозначает полное имя; увеличивайте serial при изменениях.',
   'sudo nano /etc/bind/named.conf.local ga birinchi zone blokini yozing. sudo install -d -m 0755 /etc/bind/zones dan so‘ng sudo nano /etc/bind/zones/db.lab.test ga qolgan matnni yozing. SOA boshqaruv ma’lumoti, NS vakolatli DNS, A nom/IPv4 mosligi. Oxirgi nuqta to‘liq nomni bildiradi; har tahrirda serial ni oshiring.'),
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
 T('二つの別fileへ分けて保存する。dnsのAはNS名の到達先。まだclientのresolverは変更しない。', 'Сохраните как два отдельных файла. Запись dns задаёт адрес имени NS. Resolver клиентов пока не меняйте.', 'Ikkita alohida faylga saqlang. dns A yozuvi NS nomining manzilidir. Client resolver ini hozircha o‘zgartirmang.'),
 T('既存M2がある場合はzoneを置換せず、この練習2件を追加する。zone定義を二重登録しない。', 'Если M2 уже настроен, добавьте две учебные записи, не заменяя zone. Не объявляйте zone дважды.', 'M2 allaqachon mavjud bo‘lsa, zone ni almashtirmay ikkita mashq yozuvini qo‘shing. Zone ni ikki marta e’lon qilmang.'))
step(m, T('構文を検査してDNS自身から確認する', 'Проверить синтаксис и локальный DNS-ответ', 'Sintaksis va DNS ichki javobini tekshirish'), 'dns',
 T('設定誤りのままclientを切り替えると名前解決が止まる。先にnamed-checkconfとnamed-checkzoneを成功させ、起動後にUDP/TCPの両方で応答を見る。', 'Переключение клиентов на неисправный DNS нарушит разрешение имён. Сначала добейтесь успешных named-checkconf и named-checkzone, затем проверьте UDP и TCP.', 'Client ni nosoz DNS ga o‘tkazish nom yechimini to‘xtatadi. Avval named-checkconf va named-checkzone muvaffaqiyatli bo‘lsin, keyin UDP hamda TCP ni tekshiring.'),
 'sudo named-checkconf -z\nsudo named-checkzone lab.test /etc/bind/zones/db.lab.test\nsudo systemctl enable --now named\nsudo systemctl restart named\ndig @127.0.0.1 guide.lab.test A\ndig @127.0.0.1 guide.lab.test A +tcp',
 T('zone loaded/OK、status NOERROR、flagsにaa、A=10.20.1.20。aaはこのzoneの権威応答。', 'Ожидаются zone loaded/OK, NOERROR, флаг aa и A=10.20.1.20. aa означает авторитетный ответ этой zone.', 'zone loaded/OK, NOERROR, aa va A=10.20.1.20. aa shu zone uchun vakolatli javobni bildiradi.'),
 T('失敗ならsudo journalctl -u named -n 30 --no-pagerで対象行を調べ、設定を直して再検査する。', 'При ошибке изучите sudo journalctl -u named -n 30 --no-pager, исправьте конфигурацию и проверьте снова.', 'Xatoda sudo journalctl -u named -n 30 --no-pager ni o‘qing, sozlamani tuzatib yana tekshiring.'))
step(m, T('踏み台とWebからDNSを指定して問い合わせる', 'Запросить DNS с бастиона и Web', 'Bastion va Web dan DNS ga bevosita so‘rov yuborish'), 'bst',
 T('踏み台とWebの両方で下を実行する。@10.20.2.10は今回だけ問い合わせ先を指定する。この成功だけでは、普通のbrowserやアプリが同じDNSを使うとは言えない。', 'Выполните команды и на бастионе, и на Web. @10.20.2.10 задаёт DNS только для данного запроса. Это ещё не доказывает, что браузер и приложение используют его по умолчанию.', 'Buyruqlarni bastionda ham, Web da ham bajaring. @10.20.2.10 faqat shu so‘rov uchun DNS ni belgilaydi. Bu browser va app odatda shu DNS ni ishlatishini hali isbotlamaydi.'),
 'dig @10.20.2.10 guide.lab.test A\ndig @10.20.2.10 practice-db.lab.test A +tcp\ndig @10.20.2.10 absent-p2.lab.test A\ndig @10.20.2.10 aws.amazon.com A\ndig @10.20.2.10 lab.test AXFR',
 T('必要名は正しいA、absent-p2は権威NXDOMAIN、外部名は回答、AXFRは転送拒否。timeoutは意図した拒否成功としない。', 'Нужные имена дают правильные A; absent-p2 — авторитетный NXDOMAIN; внешнее имя — ответ; AXFR запрещён. Таймаут не считается доказанным отказом.', 'Kerakli nomlar to‘g‘ri A qaytaradi; absent-p2 vakolatli NXDOMAIN, tashqi nom javob beradi; AXFR rad qilinadi. Timeout aniq rad etish isboti emas.'),
 T('DNSへ届かない場合は送信元とport53のUDP/TCPを区別して調べる。DNS以外のprivate台を問い合わせclientに追加しない。', 'При недоступности различайте источник, UDP и TCP 53. Не добавляйте остальные private-узлы в ACL клиентов.', 'Ulanmasa, manba hamda UDP/TCP 53 ni ajratib tekshiring. Boshqa private serverlarni client ACL ga qo‘shmang.'))
step(m, T('通常resolverをBINDだけへ向ける', 'Переключить системный resolver только на BIND', 'Odatiy resolver ni faqat BIND ga yo‘naltirish'), 'bst',
 T('踏み台とWebで1台ずつ実施。ip -br linkでens5等の実interface名を調べ、networkctl status その名前でNetwork Fileを読む。対応するnetplan YAMLをls /etc/netplanで探し、sudo cp -anで控えを作る。sudo nanoで既存の同じinterfaceにdhcp4-overrides/use-dns:falseとnameserversを追加する。下はファイルの構造例であり、interface名と既存match/set-name/renderer等を自分のファイルに合わせて保持する。',
   'На бастионе и Web по одному узлу выполните ip -br link, затем networkctl status ИМЯ для определения интерфейса и Network File. Найдите его YAML через ls /etc/netplan и сохраните копию sudo cp -an. Через sudo nano добавьте к тому же интерфейсу dhcp4-overrides/use-dns:false и nameservers. Ниже схема: имя интерфейса и имеющиеся match/set-name/renderer сохраняйте из своего файла.',
   'Bastion va Web da bittadan bajaring. ip -br link orqali interface nomini, networkctl status NOM orqali Network File ni aniqlang. ls /etc/netplan bilan YAML ni topib sudo cp -an orqali nusxa saqlang. sudo nano da ayni interface ga dhcp4-overrides/use-dns:false va nameservers qo‘shing. Quyida tuzilma namunasi: interface nomi hamda mavjud match/set-name/renderer qiymatlarini saqlang.'),
 '''network:
  version: 2
  ethernets:
    ens5:
      dhcp4: true
      dhcp4-overrides:
        use-dns: false
      nameservers:
        addresses: [10.20.2.10]''',
 T('IP/gatewayを手書きせずDHCPを保持。別DNSをfallbackに加えない。/etc/resolv.confを直接置換せず、/etc/hostsへ課題名を書かない。次の手順まで同じSSM端末を開いたままにする。', 'DHCP сохраняет IP и gateway. Не добавляйте резервный DNS, не заменяйте /etc/resolv.conf и не прописывайте имена задания в /etc/hosts. Оставьте SSM открытым.', 'IP va gateway DHCP da qoladi. Boshqa fallback DNS qo‘shmang, /etc/resolv.conf ni almashtirmang, topshiriq nomlarini /etc/hosts ga yozmang. SSM oynasini ochiq qoldiring.'),
 T('同じinterfaceが複数YAMLにあると値がmergeされる。resolvectl dnsにAWS DNSが残る場合は、対応する全YAMLとruntimeの設定を確認する。', 'Несколько YAML одного интерфейса объединяются. Если resolvectl dns показывает ещё AWS DNS, проверьте все соответствующие YAML и действующую конфигурацию.', 'Bir interface bir necha YAML da bo‘lsa, qiymatlar birlashadi. resolvectl dns da AWS DNS qolsa, tegishli barcha YAML va amaldagi sozlamani tekshiring.'))
step(m, T('適用後に通常名前解決とHTTPを見る', 'После применения проверить обычный resolver и HTTP', 'Qo‘llagach odatiy resolver va HTTP ni tekshirish'), 'bst',
 T('踏み台とWebで構文生成→適用→確認の順に行う。SSH/RDPの別端末も開いておき、もし切断したらSSMで戻って控えとの差分を確認する。netplan tryの確認待ちは使わず、設定を読んでgenerate成功後にapplyする。', 'На бастионе и Web сначала создайте конфигурацию, затем примените и проверьте. Оставьте второе окно SSH/RDP; при разрыве вернитесь по SSM и сравните с сохранённой копией. Применяйте apply только после проверки файла и успешного generate.', 'Bastion va Web da avval sozlamani hosil qiling, keyin qo‘llang va tekshiring. Ikkinchi SSH/RDP oynasini ochiq tuting; uzilsa SSM orqali qaytib nusxa bilan solishtiring. Fayl tekshirilgach va generate muvaffaqiyatli tugagach apply qiling.'),
 'sudo netplan generate\nsudo netplan apply\nsudo systemctl restart systemd-resolved\nresolvectl dns\ngetent ahostsv4 guide.lab.test\ngetent ahostsv4 practice-db.lab.test\ncurl --noproxy \'*\' -i http://guide.lab.test/practice.txt',
 T('実DNSの集合は10.20.2.10だけ。getentは期待IP、HTTPは200/練習本文。127.0.0.53はローカルstubであり、上流はresolvectlで確認する。', 'Единственный upstream DNS — 10.20.2.10. getent выдаёт нужные IP, HTTP — 200 и текст P1. 127.0.0.53 — локальный stub; upstream смотрите в resolvectl.', 'Yagona upstream DNS 10.20.2.10. getent kerakli IP, HTTP esa 200 va P1 matnini beradi. 127.0.0.53 mahalliy stub; upstream ni resolvectl da ko‘ring.'),
 T('dig成功/getent失敗ならclient resolverを調べる。FirefoxはDoH無効の教師設定を維持する。', 'Если dig успешен, а getent нет, проверяйте resolver клиента. Сохраняйте настройку Firefox с отключённым DoH.', 'dig o‘tib getent o‘tmasa, client resolver ini tekshiring. Firefox dagi DoH o‘chirilgan sozlamani saqlang.'))
step(m, T('browserでIPと名前を比較して提出する', 'Сравнить IP и имя в браузере, затем отправить', 'Browser da IP va nomni solishtirib yuborish'), 'gui',
 T('RDPで踏み台へ入りFirefoxを開く。http://10.20.1.20/practice.txt と http://guide.lab.test/practice.txt が同じ本文になることを確認する。lab.testは学校PCの通常DNSではなく踏み台の内部DNSで使う名前。その後、PCのWeb PortalでP2を選び確認する。', 'Откройте Firefox на бастионе через RDP. Сравните http://10.20.1.20/practice.txt и http://guide.lab.test/practice.txt. lab.test разрешается внутренним DNS бастиона, а не DNS школьного PC. Затем выберите P2 в Web Portal на PC и проверьте результат.', 'RDP orqali bastion Firefox ini oching. http://10.20.1.20/practice.txt va http://guide.lab.test/practice.txt bir xil matn berishini ko‘ring. lab.test maktab PC DNS ida emas, bastion ichki DNS ida ishlaydi. Keyin PC dagi Web Portal da P2 ni tekshiring.'),
 '',
 T('13項目の練習確認。P1の現在機能も必要。次のM2で正式名6件を追加してからDB/appへ進む。', '13 учебных проверок; текущий P1 тоже должен работать. Перед DB/app добавьте шесть основных имён в M2.', '13 ta mashq tekshiruvi; P1 ning joriy ishlashi ham kerak. DB/app dan oldin M2 da oltita asosiy nomni qo‘shing.'),
 T('名前が開かない原因をHTTP停止と決めつけず、IP指定→dig→getent→HTTPの順で比べる。', 'Не считайте любую ошибку имени остановкой HTTP: сравните IP → dig → getent → HTTP.', 'Nom ochilmasa darhol HTTP to‘xtagan demang: IP → dig → getent → HTTP tartibida solishtiring.'))

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
step(m, T('DBを導入しDB構築用SQLを展開する', 'Установить PostgreSQL и распаковать SQL для настройки БД', 'PostgreSQL o‘rnatish va DB sozlash uchun SQL ni ochish'), 'db',
 T('DBへSSM接続しrole=dbを確認する。PostgreSQL16のclusterはDBをまとめて動かす単位。公開資源の展開補助は署名版のappを検査し、SQLを取り出すだけでroleやDBを作らない。', 'Подключитесь к DB по SSM, проверьте role=db. Cluster PostgreSQL 16 — единица работы сервера БД. Инструмент распаковки проверяет приложение и извлекает SQL; сам он не создаёт БД или роли.', 'DB ga SSM bilan kirib role=db ni tekshiring. PostgreSQL 16 cluster — DB serverni boshqarish birligi. Yordamchi app ni tekshirib SQL ni ochadi; DB yoki role yaratmaydi.'),
 'sudo apt-get update -o APT::Update::Error-Mode=any\nsudo apt-get install --no-install-recommends postgresql-16 postgresql-client-16\nsudo python3 -B /var/lib/jdu-web/lesson-resources-r1/offline_assets.py\npg_lsclusters\nsudo -u postgres psql -X -d postgres -c "SHOW data_directory;"',
 T('16/main、data directory=/var/lib/postgresql/16/main。DB構築用SQLは/var/lib/jdu-web/lesson-resources-r1/app/sqlにある。', 'Cluster 16/main, data directory /var/lib/postgresql/16/main. SQL для настройки БД находится в /var/lib/jdu-web/lesson-resources-r1/app/sql.', '16/main, data directory /var/lib/postgresql/16/main. DB sozlash uchun SQL /var/lib/jdu-web/lesson-resources-r1/app/sql da.'),
 T('既存DBやroleは削除しない。すでに構築した場合は現在の状態を読み、未実施の手順だけ進める。', 'Не удаляйте существующие БД и роли. Если уже настроено, изучите состояние и выполняйте только недостающие шаги.', 'Mavjud DB yoki role ni o‘chirmang. Oldin qurilgan bo‘lsa, holatni o‘qib faqat yetishmagan qadamlarni bajaring.'))
step(m, T('DBの待受とSCRAMを設定する', 'Настроить прослушивание и SCRAM', 'DB tinglashi va SCRAM ni sozlash'), 'db',
 T('sudo cp -anでpostgresql.confの控えを作り、sudo nano /etc/postgresql/16/main/postgresql.confで次の3値を設定する。同じ項目が複数ある場合は有効値を後でSHOWで確認。listen_addressesはDBのprivate IPだけ、portは5432。password_encryptionはこの後設定するpasswordの保存方式。',
   'Сохраните postgresql.conf через sudo cp -an. В sudo nano /etc/postgresql/16/main/postgresql.conf задайте три значения ниже. Если параметр встречается несколько раз, проверьте действующее значение через SHOW. Слушать нужно только private IP БД на 5432; password_encryption определяет хранение новых паролей.',
   'postgresql.conf nusxasini sudo cp -an bilan saqlang. sudo nano /etc/postgresql/16/main/postgresql.conf da uch qiymatni sozlang. Parametr takrorlansa, amaldagi qiymatni SHOW bilan tekshiring. Faqat DB private IP va 5432 tinglanadi; password_encryption keyingi parollar saqlanish turini belgilaydi.'),
 "listen_addresses = '10.20.2.20'\nport = 5432\npassword_encryption = 'scram-sha-256'",
 T('外部全addressを示す*は使わない。まだpasswordを設定せず、次のHBAを整えてからrestartする。', 'Не используйте * для всех адресов. Пароли задаются после настройки HBA и restart.', 'Barcha manzil uchun * ishlatmang. Parollar HBA va restart dan keyin belgilanadi.'),
 T('これは設定内容。psqlではなくpostgresql.confへ書く。SGとOSのlistenは別の制御である。', 'Это текст postgresql.conf, не SQL. SG и адрес прослушивания ОС — разные средства контроля.', 'Bu SQL emas, postgresql.conf mazmuni. SG va OS tinglash manzili alohida nazoratdir.'))
step(m, T('接続元・DB・roleをHBAで限定する', 'Ограничить источник, database и role в HBA', 'HBA da manba, database va role ni cheklash'), 'db',
 T('sudo cp -anでpg_hba.confを控え、sudo nano /etc/postgresql/16/main/pg_hba.confで以下を保存。最初に一致する行が使われるため、既存の広い許可行は残さない。OS postgresだけはUnix socketのpeerで管理できる。M4で作る別profileも明示列挙し、練習roleが本課題DBへ入る組合せは許さない。',
   'Сохраните pg_hba.conf, затем в sudo nano /etc/postgresql/16/main/pg_hba.conf запишите правила ниже. Действует первая совпавшая строка, поэтому прежние широкие разрешения не оставляйте. Системный postgres управляет через Unix socket/peer. Роли будущего M4 перечислены отдельно; учебной роли доступ к основной БД не даётся.',
   'pg_hba.conf nusxasini saqlab, sudo nano /etc/postgresql/16/main/pg_hba.conf ga quyidagi qoidalarni yozing. Birinchi mos qator ishlatiladi, shu sabab eski keng ruxsatlarni qoldirmang. OS postgres Unix socket/peer orqali boshqaradi. M4 rollari alohida ko‘rsatilgan; mashq roli asosiy DB ga kira olmaydi.'),
 '''local all postgres peer
local all all reject
host jdu_catalog_practice catalog_practice_setup 10.20.1.20/32 scram-sha-256
host jdu_catalog_practice catalog_practice_app 10.20.1.20/32 scram-sha-256
host jdu_catalog catalog_setup 10.20.1.20/32 scram-sha-256
host jdu_catalog catalog_app 10.20.1.20/32 scram-sha-256
host all all 0.0.0.0/0 reject
host all all ::/0 reject''',
 T('接続許可はDB/role/送信元の組合せで判断する。0.0.0.0/0の行はrejectであり許可ではない。', 'Разрешение зависит от сочетания database/role/источник. Строка 0.0.0.0/0 содержит reject, то есть запрет.', 'Ruxsat database/role/manba birikmasiga bog‘liq. 0.0.0.0/0 qatori reject, ya’ni rad etishdir.'),
 T('trustへ変えて認証を省略しない。DB5432は基盤SGでもWebだけから許可される。', 'Не заменяйте метод на trust. Базовый SG также разрешает DB 5432 только с Web.', 'Autentifikatsiyani trust bilan chetlab o‘tmang. Asosiy SG ham DB 5432 ni faqat Web dan ruxsat qiladi.'))
step(m, T('起動して設定の実効値を読む', 'Перезапустить и проверить действующие значения', 'Qayta ishga tushirish va amaldagi qiymatni tekshirish'), 'db',
 T('restartは設定を読み直す。SQLのSHOWとpg_hba_file_rulesで、編集したつもりの値ではなく動作中の値を確認する。psqlの-Xは個人設定fileを読み込ませない指定。', 'restart перечитывает настройки. SHOW и pg_hba_file_rules проверяют действующие значения, а не только текст файла. Параметр psql -X отключает личные startup-файлы.', 'restart sozlamani qayta o‘qiydi. SHOW va pg_hba_file_rules fayl matnini emas, ishlayotgan qiymatni tekshiradi. psql -X shaxsiy boshlang‘ich fayllarni o‘qimaydi.'),
 'sudo systemctl restart postgresql@16-main\nsystemctl is-active postgresql@16-main\nsudo ss -lntp\nsudo -u postgres psql -X -d postgres -c "SHOW password_encryption;"\nsudo -u postgres psql -X -d postgres -c "SELECT line_number,error FROM pg_hba_file_rules WHERE error IS NOT NULL;"',
 T('active、10.20.2.20:5432、scram-sha-256、HBA errorは0行。', 'active, 10.20.2.20:5432, scram-sha-256, ошибок HBA — 0 строк.', 'active, 10.20.2.20:5432, scram-sha-256, HBA xatosi — 0 qator.'),
 T('postgresql.serviceのactive(exited)だけでcluster稼働を判断しない。journalctl -u postgresql@16-mainで調べる。', 'active(exited) у postgresql.service не доказывает работу cluster. Изучайте journalctl -u postgresql@16-main.', 'postgresql.service active(exited) bo‘lishi cluster ishlashini isbotlamaydi. journalctl -u postgresql@16-main ni o‘qing.'))
step(m, T('練習DBと2種類のroleを作る', 'Создать учебную БД и две роли', 'Mashq DB va ikkita role yaratish'), 'db',
 T('profile_sql.pyは固定SQLの練習名を出力するだけ。最初のcommandで内容を読み、その後同じ出力をpsqlへ渡す。setupはDB/schemaを所有し初期tableを作るrole、appは通常接続するrole。コードを作る授業ではないので配布SQLを使う。', 'profile_sql.py только выводит фиксированный SQL с учебными именами. Сначала прочитайте вывод, затем передайте тот же текст psql. setup владеет БД/schema и создаёт таблицы; app используется приложением. Используйте предоставленный SQL: программировать приложение не требуется.', 'profile_sql.py faqat mashq nomlari bilan tayyor SQL ni chiqaradi. Avval matnni o‘qing, keyin ayni chiqishni psql ga uzating. setup DB/schema egasi va boshlang‘ich jadval yaratuvchi; app odatiy ulanish roli. App dasturlash talab qilinmagani uchun berilgan SQL dan foydalaning.'),
 '''cd /var/lib/jdu-web/lesson-resources-r1/app
python3 -B profile_sql.py --profile practice 01_create_roles.sql
python3 -B profile_sql.py --profile practice 01_create_roles.sql | sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d postgres
python3 -B profile_sql.py --profile practice 02_prepare_schema.sql | sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d jdu_catalog_practice''',
 T('CREATE ROLEが2回、CREATE DATABASE、schemaとCONNECT/USAGEの設定。appにsuperuser/CREATEDB等は付けない。', 'Два CREATE ROLE, CREATE DATABASE, права schema/CONNECT/USAGE. app не получает superuser/CREATEDB.', 'Ikki CREATE ROLE, CREATE DATABASE va schema/CONNECT/USAGE sozlanadi. app ga superuser/CREATEDB berilmaydi.'),
 T('already existsなら成功済みの可能性。DROPで消さず\\duと\\lで対応を確認する。パイプ右側psqlにSQL errorがないことを確認する。', 'При already exists возможен повторный запуск. Не используйте DROP; проверьте роли и БД через \\du и \\l. Убедитесь, что psql справа от pipe не сообщил SQL error.', 'already exists oldin bajarilganini anglatishi mumkin. DROP qilmang; \\du va \\l orqali solishtiring. Pipe o‘ngidagi psql SQL error bermaganini tekshiring.'))
step(m, T('2つのDBパスワードを非表示で設定する', 'Задать два пароля БД скрытым вводом', 'Ikki DB parolini yashirin kiritish'), 'dbsql',
 T('DBのshellで最初の行を実行するとpostgres=#のpsqlに入る。\\passwordはその中で入力する。16文字以上の異なるpasswordをsetup/appへそれぞれ2回入力。値は画面にも履歴にも書かない。最後の\\qでDBのshellへ戻る。', 'Первая строка запускается в shell DB и открывает psql с postgres=#. Команды \\password вводятся внутри psql. Для setup/app задайте разные пароли длиной от 16 символов, каждый дважды скрытым вводом. Не пишите значения в команду или отчёт. \\q возвращает в shell DB.', 'Birinchi qator DB shell ida bajarilib postgres=# psql ni ochadi. \\password buyruqlarini psql ichida kiriting. setup/app uchun kamida 16 belgili turli parollarni har birini ikki marta yashirin kiriting. Qiymatni buyruq yoki hisobotga yozmang. \\q DB shell iga qaytaradi.'),
 r'''sudo -u postgres psql -X -d postgres
\password catalog_practice_setup
\password catalog_practice_app
\du catalog_practice_*
\q''',
 T('roleの属性にSuperuser/Create role/Create DB等がない。RDP用password、アプリ管理者password、採点tokenとは別の秘密である。', 'Нет Superuser/Create role/Create DB. Это отдельные секреты, не пароль RDP, не пароль администратора приложения и не token оценивания.', 'Superuser/Create role/Create DB yo‘q. Bular RDP paroli, app admin paroli yoki baholash tokenidan alohida maxfiy qiymatlardir.'),
 T('keyboard配列に注意。値を確認するために会話やエディタへ書き出さない。忘れた場合は教師と本人用復旧を行う。', 'Учитывайте раскладку клавиатуры. Не записывайте пароль в чат или редактор для проверки. При потере используйте личную процедуру восстановления с преподавателем.', 'Klaviatura tartibiga e’tibor bering. Tekshirish uchun parolni chat yoki editorga yozmang. Unutilsa o‘qituvchi bilan shaxsiy tiklash tartibini bajaring.'))
step(m, T('Webからpassword付きSELECTを行う', 'Выполнить SELECT с Web по паролю', 'Web dan parol bilan SELECT bajarish'), 'web',
 T('DBのSSMをexitしCloudShellへ戻り、WebのSSMへ入る。psqlの-hは接続先、-UはDB role、-dはDB名、-Wはpassword入力を要求する。まず内部IPで接続する。続けて、P2で登録した練習用のDB名で同じSELECTを実行する。両方で同じDB名・ロール・結果が返ることを確かめる。', 'Закройте SSM DB через exit, вернитесь в CloudShell и откройте Web. У psql -h задаёт узел, -U — роль, -d — БД, -W запрашивает пароль. Сначала подключитесь по внутреннему IP, затем выполните тот же SELECT по учебному имени DB из P2. Сверьте имя БД, роль и результат.', 'DB SSM dan exit qilib CloudShell ga qayting, Web SSM ni oching. psql da -h manzil, -U role, -d DB nomi, -W parol so‘rovi. Avval ichki IP orqali ulaning, keyin P2 da ro‘yxatga olingan mashq DB nomi orqali shu SELECT ni bajaring. DB nomi, rol va natijani solishtiring.'),
 '''sudo apt-get install --no-install-recommends postgresql-client-16
psql -X -h 10.20.2.20 -U catalog_practice_app -d jdu_catalog_practice -W -c 'SELECT current_database(),current_user,1 AS value;'
getent ahostsv4 practice-db.lab.test
psql -X -h practice-db.lab.test -U catalog_practice_app -d jdu_catalog_practice -W -c 'SELECT current_database(),current_user,1 AS value;' ''',
 T('jdu_catalog_practice / catalog_practice_app / 1。portが開くだけ、pg_isreadyが成功するだけではこの認証SQLの代わりにならない。', 'Результат jdu_catalog_practice / catalog_practice_app / 1. Открытый порт или успех pg_isready не заменяют этот SQL с аутентификацией.', 'jdu_catalog_practice / catalog_practice_app / 1. Port ochiqligi yoki pg_isready muvaffaqiyati bu autentifikatsiyali SQL o‘rnini bosmaydi.'),
 T('内部IPで成功し、名前で失敗する場合は、P2で設定した通常の名前解決と練習用のDB名を確認する。認証が拒否される場合は接続元・DB・ロール・パスワードを確認する。DBをInternetへ公開して試さない。', 'Если по IP подключение работает, а по имени нет, проверьте системный DNS и учебное имя DB из P2. При отказе аутентификации проверьте источник, БД, роль и пароль. Не публикуйте DB в Internet для диагностики.', 'IP orqali ulanish ishlasa, nom orqali esa ishlamasa, P2 dagi tizim DNS i va mashq DB nomini tekshiring. Autentifikatsiya rad etilsa, manba, DB, rol va parolni tekshiring. Sinash uchun DB ni Internet ga ochmang.'))
step(m, T('checkerが使う既存passwordをWeb内だけに保存する', 'Сохранить существующий пароль для checker только на Web', 'Checker uchun mavjud parolni faqat Web da saqlash'), 'web',
 T('helperは既存のcatalog_practice_app passwordを2回非表示入力し、Webのroot専用0600 fileへ保存する。DBのpasswordは変えない。envをcatしたりshellでsourceしない。exitでCloudShellへ戻ったら、PCのWeb PortalでP4を確認する。', 'Инструмент дважды скрыто запрашивает существующий пароль catalog_practice_app и сохраняет его только на Web в root-файл 0600. Пароль БД не меняется. Не выводите env через cat и не выполняйте source. После exit проверьте P4 в Web Portal на PC.', 'Yordamchi mavjud catalog_practice_app parolini ikki marta yashirin so‘rab, Web dagi root-only 0600 faylga saqlaydi. DB parolini o‘zgartirmaydi. Env ni cat bilan ko‘rsatmang va source qilmang. Exit dan keyin PC dagi Web Portal da P4 ni tekshiring.'),
 'sudo python3 -B /var/lib/jdu-web/lesson-resources-r1/database_secret.py --profile practice\nexit',
 T('D11_EXISTING_DB_PASSWORD_STORED_LOCALLYと練習9項目。誤password・他DB/管理roleの拒否も正常接続との対照で確認される。', 'Вывод D11_EXISTING_DB_PASSWORD_STORED_LOCALLY и девять учебных проверок. Неверный пароль и запрещённые DB/admin-role проверяются вместе с успешным контрольным подключением.', 'D11_EXISTING_DB_PASSWORD_STORED_LOCALLY va to‘qqizta mashq tekshiruvi. Noto‘g‘ri parol hamda taqiqlangan DB/admin-role rad etilishi muvaffaqiyatli ulanish bilan solishtiriladi.'),
 T('既存fileありなら再生成しない。P5では同じDB passwordをapp設定にも入力する。M4はmission用の別DB/roleで構築する。', 'Если файл уже есть, не создавайте заново. В P5 тот же пароль вводится в настройку приложения. M4 использует отдельные БД/роли mission.', 'Fayl mavjud bo‘lsa qayta yaratmang. P5 da ayni DB paroli app sozlamasiga kiritiladi. M4 alohida mission DB/rollaridan foydalanadi.'))

m = module('P5', T('教員アプリをWeb・DBへ接続する', 'Соединить предоставленное приложение с Web и DB', 'Berilgan app ni Web va DB bilan bog‘lash'),
 T('コードを書かず、オフライン依存・専用user・DB初期化・Nginx/systemd・実HTTPをつなぐ。', 'Без программирования связать offline-зависимости, сервисного пользователя, инициализацию БД, Nginx/systemd и реальный HTTP.', 'Dastur yozmasdan offline bog‘liqlik, service user, DB tayyorlash, Nginx/systemd va haqiqiy HTTP ni bog‘lash.'),
 T('practice profileで備品カタログを構築する。M2の正式DNSとP4が現在も使えることが前提。PのDB/管理者とMのDB/管理者を分け、同じWebのapp/portは共有する。', 'Постройте каталог в profile practice. Нужны действующие DNS из M2 и P4. БД/администраторы P и M различны, но приложение и порты на том же Web общие.', 'practice profile da katalogni quring. M2 asosiy DNS va P4 hozir ham ishlashi kerak. P/M DB va admin lari alohida, ayni Web dagi app va port umumiy.'))
step(m, T('必要なDNSと公開資源を確認する', 'Проверить DNS и получить открытые ресурсы', 'Kerakli DNS va ochiq resurslarni tekshirish'), 'web',
 T('Webで通常resolverのdb.lab.testが10.20.2.20、admin.lab.testが10.20.1.20になることを確認。offline_assetsは元署名にある7 wheelとlockを内部repoから取得しhashを検査する。pipの外部取得やDB/appの設定は行わない。', 'На Web обычный resolver должен дать db.lab.test=10.20.2.20 и admin.lab.test=10.20.1.20. offline_assets получает семь wheel и lock из внутреннего repo, сверяя исходную подпись/hash. Он не запускает внешний pip и не настраивает DB/app.', 'Web odatiy resolver db.lab.test=10.20.2.20 va admin.lab.test=10.20.1.20 qaytarsin. offline_assets ichki repo dan asl imzo/hash bo‘yicha yettita wheel va lock oladi. Tashqi pip ishlatmaydi, DB/app sozlamaydi.'),
 'getent ahostsv4 db.lab.test\ngetent ahostsv4 admin.lab.test\nsudo apt-get install --no-install-recommends python3-venv python3-pip\nsudo python3 -B /var/lib/jdu-web/lesson-resources-r1/offline_assets.py --wheels\nls /var/lib/jdu-web/lesson-resources-r1/app\nls /var/lib/jdu-web/lesson-resources-r1/wheels',
 T('PUBLIC_APP_RESOURCES_VERIFIEDとSIGNED_OFFLINE_WHEELS_READY=7。app資源はroot管理の公開fileだけ。', 'PUBLIC_APP_RESOURCES_VERIFIED и SIGNED_OFFLINE_WHEELS_READY=7. Файлы приложения открытые и контролируются root.', 'PUBLIC_APP_RESOURCES_VERIFIED va SIGNED_OFFLINE_WHEELS_READY=7. App fayllari ochiq va root boshqaruvida.'),
 T('practice-dbでなくdb.lab.testも必要。P5はM2へ依存する。Mの備品課題を終えていなくてもM2のDNSは使う。', 'Нужно и имя db.lab.test, не только practice-db. P5 зависит от M2, но не требует завершения основных заданий по каталогу.', 'Faqat practice-db emas, db.lab.test ham kerak. P5 M2 ga bog‘liq, ammo asosiy katalog topshirig‘ini tugatish shart emas.'))
step(m, T('コードを配置し専用venvを作る', 'Разместить код и создать отдельный venv', 'Kod joylash va alohida venv yaratish'), 'web',
 T('appとvenvはrootが管理し、実行user catalogには書換えさせない。/opt/jdu-catalog/appまたはvenvが既にある場合は新規配置を中止し、現在の版を確認する。cpは検査済み公開資源だけを配置する。venvはシステムPythonと依存を分離する。', 'Код и venv контролирует root; пользователь catalog не должен их менять. Если app или venv уже существуют, не повторяйте создание — проверьте версию. cp переносит только проверенные открытые ресурсы. venv отделяет зависимости приложения от системного Python.', 'App va venv ni root boshqaradi; catalog ularni o‘zgartira olmaydi. app yoki venv mavjud bo‘lsa, qayta yaratmay versiyani tekshiring. cp faqat tekshirilgan ochiq resursni joylaydi. venv app bog‘liqliklarini system Python dan ajratadi.'),
 'sudo install -d -o root -g root -m 0755 /opt/jdu-catalog/app\nsudo cp -a /var/lib/jdu-web/lesson-resources-r1/app/. /opt/jdu-catalog/app/\nsudo python3 -m venv /opt/jdu-catalog/venv\nsudo /opt/jdu-catalog/venv/bin/python -m pip --isolated --no-cache-dir install --no-index --find-links=/var/lib/jdu-web/lesson-resources-r1/wheels --only-binary=:all: --require-hashes -r /var/lib/jdu-web/lesson-resources-r1/requirements.lock\nsudo /opt/jdu-catalog/venv/bin/python -m pip check',
 T('--no-indexは外部indexを使わない、--require-hashesはlockのhashを要求する。pip checkは依存矛盾なし。', '--no-index запрещает внешний index; --require-hashes требует hash из lock. pip check не находит конфликтов.', '--no-index tashqi index ni ishlatmaydi; --require-hashes lock hash ini talab qiladi. pip check bog‘liqlik ziddiyatini topmaydi.'),
 T('依存不足は教員の収録資源へ戻す。pip installで最新版へ更新しない。appコードは変更しない。', 'Недостающую зависимость решают через комплект преподавателя. Не обновляйте до latest через pip и не меняйте код приложения.', 'Bog‘liqlik yetishmasa o‘qituvchi tarqatmasini tekshiring. Pip orqali latest ga yangilamang, app kodini o‘zgartirmang.'))
step(m, T('service userとstatic保存先を作る', 'Создать сервисного пользователя и каталог static', 'Service user va static katalogini yaratish'), 'web',
 T('catalogは人のlogin用ではなくGunicornの専用user。nologin、sudoなしで作る。staticの配置先だけはcollectstaticが書けるようcatalog所有にする。root管理のコード/venvとは役割が違う。既にcatalogがある場合はidとshellを確認し、useraddを繰り返さない。', 'catalog предназначен для Gunicorn, не для входа человека. Создайте его с nologin и без sudo. Только каталог static принадлежит catalog для collectstatic; код/venv остаются root. Если catalog уже есть, проверьте id и shell вместо повторного useradd.', 'catalog inson login i uchun emas, Gunicorn service user idir. nologin va sudo siz yarating. collectstatic yozishi uchun faqat static katalogini catalog egasi qiling; kod/venv root da qoladi. catalog mavjud bo‘lsa useradd ni takrorlamay id va shell ni tekshiring.'),
 'sudo useradd --system --user-group --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin catalog\nsudo install -d -o root -g root -m 0755 /var/lib/jdu-catalog\nsudo install -d -o catalog -g catalog -m 0755 /var/lib/jdu-catalog/static\nid catalog\ngetent passwd catalog',
 T('catalogはsudo groupになくshellは/usr/sbin/nologin。labuserやssm-userとは別user。', 'catalog не входит в sudo, shell /usr/sbin/nologin. Это не labuser и не ssm-user.', 'catalog sudo guruhida emas, shell /usr/sbin/nologin. Bu labuser yoki ssm-user dan boshqa user.'),
 T('権限errorをchmod -R 777やcatalogのsudo追加で解決しない。対象directoryとownerを照合する。', 'Не исправляйте права через chmod -R 777 или добавление catalog в sudo. Проверьте конкретный каталог и владельца.', 'Ruxsat xatosini chmod -R 777 yoki catalog ga sudo berish bilan hal qilmang. Aniq katalog va egasini solishtiring.'))
step(m, T('通常接続の設定を作って有効にする', 'Создать и активировать runtime-настройки', 'Runtime sozlamasini yaratish va faollashtirish'), 'web',
 T('PUBLIC_WEB_IPV4はEC2に表示された現在のWeb公開IPv4へ置き換える。runtime helperへP4で設定したcatalog_practice_appの既存passwordを2回入力する。Django secretは本人Labで生成される。通常接続の設定を作ったら、activateでpracticeをアプリが使う設定として選ぶ。アプリを起動する前に行い、設定チェックが成功したらP5.5で一時構築用の設定を作る。', 'Подставьте текущий public IPv4 Web из EC2. Runtime-инструмент дважды запрашивает существующий пароль catalog_practice_app из P4. Django secret генерируется для вашего Lab. Создайте runtime-настройки, затем выберите practice командой activate до запуска приложения. После успешной проверки создайте временные настройки setup в P5.5.', 'EC2 dagi hozirgi Web public IPv4 ni kiriting. Runtime yordamchisiga P4 dagi mavjud catalog_practice_app parolini ikki marta kiriting. Django secret shaxsiy Lab uchun yaratiladi. Runtime sozlamasini yarating, so‘ng ilovani ishga tushirishdan oldin activate buyrug‘i bilan practice profilini tanlang. Tekshiruvdan keyin P5.5 da vaqtinchalik setup sozlamasini yarating.'),
 """PUBLIC_WEB_IPV4='YOUR-CURRENT-WEB-PUBLIC-IP'
sudo python3 -B /opt/jdu-catalog/app/configuration.py create-runtime --profile practice --public-web-ipv4 "$PUBLIC_WEB_IPV4"
sudo python3 -B /opt/jdu-catalog/app/configuration.py activate --profile practice
sudo python3 -B /opt/jdu-catalog/app/configuration.py check --phase runtime
sudo stat -c '%U:%G %a %n' /etc/jdu-catalog/app.env""",
 T('CATALOG_ENV_CREATED=practice、CATALOG_PROFILE_ACTIVATED=practice、VALID、root:root 600。DB_NAMEは練習DB、DB_USERは練習app roleとして生成される。', 'CATALOG_ENV_CREATED=practice, CATALOG_PROFILE_ACTIVATED=practice, VALID, root:root 600. Выбраны учебная БД и учебная app-role.', 'CATALOG_ENV_CREATED=practice, CATALOG_PROFILE_ACTIVATED=practice, VALID, root:root 600. Mashq DB va mashq app role tanlanadi.'),
 T('RDPや管理者用passwordを入力しない。再開時はすでに成功した操作を繰り返さず、最初に未完了の操作から進む。activateが失敗した場合は、アプリの稼働状態と一時構築用の設定が残っていないかを確認してから次へ進む。', 'Не вводите пароль RDP или администратора приложения. При продолжении начните с первого незавершённого действия. При ошибке activate проверьте, работает ли приложение и остались ли временные настройки setup, прежде чем идти дальше.', 'RDP yoki app admin parolini kiritmang. Davom ettirishda bajarilmagan birinchi amaldan boshlang. Activate xato bersa, keyingi qadamdan oldin ilova ishlayotganini va vaqtinchalik setup sozlamalari qolganini tekshiring.'))
step(m, T('一時setup接続でtableと管理者を作る', 'Создать таблицы и администратора через временный setup', 'Vaqtinchalik setup bilan jadval va admin yaratish'), 'web',
 T('create-setupにはP4のcatalog_practice_setup passwordを入力する。migrateは配布済みDB構造を作り、seedは空DBへ架空サンプル3件を一度だけ入れる。create_lab_adminはpractice_adminを非表示password入力で作る。通常アプリはこのsetup roleでは動かさない。', 'В create-setup введите пароль catalog_practice_setup из P4. migrate создаёт предоставленную структуру БД; seed однократно добавляет три вымышленных образца в пустой каталог. create_lab_admin создаёт practice_admin со скрытым вводом пароля. Обычное приложение не работает через setup.', 'create-setup ga P4 dagi catalog_practice_setup parolini kiriting. migrate berilgan DB tuzilmasini yaratadi; seed bo‘sh katalogga bir marta uchta xayoliy namuna kiritadi. create_lab_admin yashirin parol bilan practice_admin yaratadi. Oddiy app setup orqali ishlamaydi.'),
 'sudo python3 -B /opt/jdu-catalog/app/configuration.py create-setup --profile practice\nsudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py --phase setup check\nsudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py --phase setup migrate\nsudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py --phase setup seed_catalog\nsudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py --phase setup create_lab_admin',
 T('固定11table、サンプル3件、staff管理者（superuserではない）。操作はcatalog OS userへ権限を落として実行される。', 'Фиксированные 11 таблиц, три образца и staff-администратор без superuser. Операции выполняются с правами системного catalog.', 'Belgilangan 11 jadval, uchta namuna va superuser bo‘lmagan staff admin. Amallar OS catalog huquqiga tushirilgan holda bajariladi.'),
 T('seedや管理者のalready existsは既存データ保護。初期化/resetせず次の状態確認へ進む。', 'already exists при seed/admin защищает существующие данные. Не делайте reset; проверьте текущее состояние.', 'Seed/admin already exists mavjud ma’lumotni himoya qiladi. Reset qilmay joriy holatni tekshiring.'))
step(m, T('通常roleへ必要なSQL権限を付ける', 'Выдать runtime-роли необходимые SQL-права', 'Runtime role ga kerakli SQL huquqini berish'), 'db',
 T('WebをexitしてCloudShellへ戻りDBへSSM接続する。SQL03を先に読み、11table/所有者を検査してからtable・列・sequence単位に必要権限を付ける。appに所有権やALL PRIVILEGESを与える方法ではない。', 'Выйдите из Web в CloudShell и откройте DB через SSM. Прочитайте SQL03: после проверки 11 таблиц и владельцев он выдаёт права по таблицам, столбцам и sequence. Владение и ALL PRIVILEGES роли app не даются.', 'Web dan CloudShell ga chiqib DB SSM ni oching. Avval SQL03 ni o‘qing: u 11 jadval va egalarni tekshirib jadval, ustun va sequence bo‘yicha huquq beradi. App ga egalik yoki ALL PRIVILEGES berilmaydi.'),
 'cd /var/lib/jdu-web/lesson-resources-r1/app\npython3 -B profile_sql.py --profile practice 03_runtime_grants.sql\npython3 -B profile_sql.py --profile practice 03_runtime_grants.sql | sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d jdu_catalog_practice',
 T('COMMITまで成功。catalog_itemはSELECT/INSERT/UPDATE、auth_userは参照とlast_login/password列だけの更新、session等は用途別。', 'Успех до COMMIT. catalog_item: SELECT/INSERT/UPDATE; auth_user: чтение и UPDATE только last_login/password; session и другие объекты — по назначению.', 'COMMIT gacha muvaffaqiyat. catalog_item: SELECT/INSERT/UPDATE; auth_user: o‘qish va faqat last_login/password ustunlarini UPDATE; session va boshqalar maqsadiga ko‘ra.'),
 T('guard errorはmigration/ownerを確認する合図。制約を削除して通さない。', 'Ошибка guard требует проверить migrations/owner. Не удаляйте защиту ради продолжения.', 'Guard xatosi migration/owner ni tekshirish kerakligini bildiradi. O‘tish uchun himoyani o‘chirmang.'))
step(m, T('staticとsystemd unitを配置する', 'Разместить static и unit systemd', 'Static va systemd unit ni joylash'), 'web',
 T('Webへ戻る。collectstaticは配布CSS等をNginxが読むdirectoryへ集める。unitを/etc/systemd/systemへ置きdaemon-reloadでsystemdに認識させる。unit内容を読み、User=catalog、EnvironmentFile、127.0.0.1:8000を見つける。', 'Вернитесь на Web. collectstatic собирает CSS и другие ресурсы для Nginx. Разместите unit и выполните daemon-reload. Прочитайте User=catalog, EnvironmentFile и bind 127.0.0.1:8000.', 'Web ga qayting. collectstatic CSS va boshqa fayllarni Nginx o‘qiydigan katalogga yig‘adi. Unit ni joylab daemon-reload bajaring. User=catalog, EnvironmentFile va 127.0.0.1:8000 ni toping.'),
 'sudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py --phase runtime collectstatic\ncat /opt/jdu-catalog/app/config/jdu-catalog.service\nsudo install -o root -g root -m 0644 /opt/jdu-catalog/app/config/jdu-catalog.service /etc/systemd/system/jdu-catalog.service\nsudo systemctl daemon-reload\nsudo systemctl enable --now jdu-catalog\nsystemctl is-active jdu-catalog\nsudo ss -lntp',
 T('activeで、アプリ8000は127.0.0.1だけ。0.0.0.0:8000へ直接公開しない。', 'active; приложение слушает 8000 только на 127.0.0.1. Не публикуйте его через 0.0.0.0:8000.', 'active; app 8000 ni faqat 127.0.0.1 da tinglaydi. Uni 0.0.0.0:8000 orqali ochmang.'),
 T('起動errorはjournalctl -u jdu-catalogを見る。秘密設定本文をlogへ貼らず、configuration.py checkで形式を確認する。', 'При ошибке смотрите journalctl -u jdu-catalog. Не копируйте env в журнал; формат проверяется configuration.py check.', 'Xatoda journalctl -u jdu-catalog ni o‘qing. Env mazmunini log ga qo‘ymang; formatni configuration.py check bilan tekshiring.'))
step(m, T('Nginxの公開入口と管理入口を分ける', 'Разделить публичный и управляющий входы Nginx', 'Nginx ochiq va boshqaruv kirishlarini ajratish'), 'web',
 T('配布confをcatで読み、80→公開一覧、private8080→/admin/だけ、転送先8000を確認。初期default siteのsymlinkは別名で保存して無効化する。既にjdu-catalogが有効なら再移動せず現在設定を確認する。P1/M1の静的URLを保持したconfを使う。', 'Прочитайте conf: 80 — список, private8080 — только /admin/, upstream — 8000. Сохраните ссылку начального default site под другим именем и отключите её. Если jdu-catalog уже включён, проверьте состояние вместо повторных переносов. Статические URL P1/M1 сохраняются.', 'Conf ni o‘qing: 80 — ochiq ro‘yxat, private8080 — faqat /admin/, upstream — 8000. Boshlang‘ich default site symlink ini boshqa nom bilan saqlab o‘chiring. jdu-catalog allaqachon yoqilgan bo‘lsa qayta ko‘chirmay tekshiring. P1/M1 statik URL lari saqlanadi.'),
 'cat /opt/jdu-catalog/app/config/jdu-catalog.nginx.conf\nsudo install -o root -g root -m 0644 /opt/jdu-catalog/app/config/jdu-catalog.nginx.conf /etc/nginx/sites-available/jdu-catalog\nsudo mv -n /etc/nginx/sites-enabled/default /etc/nginx/default-site.before-p5\nsudo ln -s /etc/nginx/sites-available/jdu-catalog /etc/nginx/sites-enabled/jdu-catalog\nsudo nginx -t\nsudo systemctl reload nginx\ncurl --noproxy \'*\' -i http://127.0.0.1/practice.txt',
 T('構文成功、practice.txtは引き続き200。公開access logはjdu-catalog-public.access.logへ切り替わる。', 'Синтаксис успешен, practice.txt по-прежнему даёт 200. Публичный журнал теперь jdu-catalog-public.access.log.', 'Sintaksis to‘g‘ri, practice.txt hali ham 200. Ochiq access log endi jdu-catalog-public.access.log.'),
 T('duplicate default serverなら旧siteを確認。reload前に-t失敗を直す。管理portをpublic IPでlistenさせない。', 'При duplicate default server проверьте старый site. До reload исправьте -t. Управляющий port не должен слушать public IP.', 'duplicate default server bo‘lsa eski site ni tekshiring. Reload dan oldin -t xatosini tuzating. Admin port public IP da tinglamasin.'))
step(m, T('管理画面で練習用2件を登録する', 'Добавить две учебные записи через admin', 'Admin orqali ikkita mashq yozuvini kiritish'), 'gui',
 T('踏み台のFirefoxでhttp://admin.lab.test:8080/admin/を開き、practice_adminと自分のアプリ管理者passwordでログイン。備品のAddから下の2行を登録する。code/name/quantity/locationを正確に入力し、公開行だけIs publicを有効にする。保存後にhttp://web.lab.test/で公開行だけ出るか見る。', 'В Firefox бастиона откройте http://admin.lab.test:8080/admin/, войдите как practice_admin со своим паролем приложения. Через Add добавьте две строки ниже с точными code/name/quantity/location. Is public включите только у публичной записи. На http://web.lab.test/ должна быть только публичная строка.', 'Bastion Firefox da http://admin.lab.test:8080/admin/ ni ochib practice_admin va o‘z app admin parolingiz bilan kiring. Add orqali quyidagi ikki qatorni code/name/quantity/location qiymatlari bilan aniq kiriting. Is public ni faqat ochiq yozuvda yoqing. http://web.lab.test/ da faqat ochiq qator ko‘rinsin.'),
 'P5-PUBLIC-001 | Practice keyboard | 4 | Training shelf A | is_public=true\nP5-PRIVATE-001 | Practice mouse | 2 | Training shelf B | is_public=false',
 T('demo3件を消す必要はない。指定2件は完成条件の部分集合で、他の正当な公開備品も許される。非公開備品は公開一覧に出ない。', 'Удалять три demo не нужно. Две заданные записи — обязательное подмножество; другие корректные публичные записи разрешены. Непубличная запись не видна в списке.', 'Uch demo ni o‘chirish shart emas. Belgilangan ikkita yozuv zarur qism; boshqa to‘g‘ri ochiq yozuvlar mumkin. Yopiq yozuv ro‘yxatda ko‘rinmaydi.'),
 T('school PCでadmin.lab.testを開かず、RDP内Firefoxを使う。CSRFエラーはhost/port/正しいproxy設定を調べる。', 'Открывайте admin.lab.test в Firefox внутри RDP, не на школьном PC. При CSRF проверьте host/port/proxy.', 'admin.lab.test ni maktab PC da emas, RDP ichidagi Firefox da oching. CSRF xatosida host/port/proxy ni tekshiring.'))
step(m, T('DBの実データを読み、画面と照合する', 'Прочитать реальные строки БД и сравнить с экраном', 'DB haqiqiy qatorlarini o‘qish va ekran bilan solishtirish'), 'web',
 T('Webのpsqlで練習app roleを使って読取りSQLを実行する。管理画面の保存が本当にPostgreSQLへ届いたかを確認する。SELECTは読み取りで、UPDATE/DELETEはこの確認では使わない。', 'На Web выполните SELECT учебной app-role. Так проверяется, что сохранение из admin действительно дошло до PostgreSQL. Для этой проверки не нужны UPDATE/DELETE.', 'Web da mashq app role bilan SELECT bajaring. Bu admin dagi saqlash haqiqatan PostgreSQL ga yetganini tekshiradi. Ushbu tekshiruvda UPDATE/DELETE ishlatmang.'),
 '''QUERY="SELECT code,name,quantity,location,is_public
FROM catalog_item
WHERE code IN ('P5-PUBLIC-001','P5-PRIVATE-001')
ORDER BY code;"
psql -X -h db.lab.test -U catalog_practice_app -d jdu_catalog_practice -W -c "$QUERY" ''',
 T('指定した2行が一致する。画面が出てもDB接続失敗を固定HTMLで隠す構成にはしない。', 'Обе строки совпадают с заданием. Не подменяйте страницу фиксированным HTML при отказе БД.', 'Ikkala qator topshiriqqa mos. DB ishlamasa, sahifani tayyor HTML bilan almashtirmang.'),
 T('permission deniedならSQL03のprofile/対象DBを確認。superuserで通常接続を代用しない。', 'При permission denied проверьте profile и database SQL03. Не заменяйте обычную роль на superuser.', 'permission denied bo‘lsa SQL03 profile va database ni tekshiring. Oddiy role o‘rniga superuser ishlatmang.'))
step(m, T('自動機能確認を起動して提出する', 'Запустить функциональную проверку и отправить', 'Funksional tekshiruvni ishga tushirish va yuborish'), 'portal',
 T('WebをexitしてPCのWeb PortalでP5を選び、「機能・権限を含めて確認する」を選ぶ。既存practice_adminのパスワードを「アプリ管理者の既存パスワード」へ非表示入力し「このパスワードで確認する」を押す。RDP用とは別。自動処理はHTTPでloginし、自分専用CK-P-備品1件の登録・数量編集、DB/公開画面の照合、logoutを行う。指定2件は変えず、確認用1件は残る。本人実演・教師立会いは不要。', 'После exit с Web выберите P5 в Web Portal на PC и функциональную проверку с правами. В скрытое поле введите существующий пароль practice_admin и запустите проверку с этим паролем. Это не пароль RDP. Автоматика выполняет HTTP login, создаёт одну запись CK-P-, меняет количество, сверяет DB/страницу и выполняет logout. Две заданные записи не меняются; проверочная остаётся. Личная демонстрация не нужна.', 'Web dan exit qilib PC dagi Web Portal da P5 va funksiya/huquq tekshiruvini tanlang. Yashirin maydonga practice_admin mavjud parolini kiritib, shu parol bilan tekshiring. Bu RDP paroli emas. Avtomatika HTTP login, bitta CK-P- yozuv yaratish, miqdor tahriri, DB/ochiq sahifani solishtirish va logout ni bajaradi. Belgilangan ikkita yozuv o‘zgarmaydi; tekshiruv yozuvi qoladi. Shaxsiy namoyish kerak emas.'),
 '',
 T('練習13項目と保存状態が表示される。設定だけの確認と機能確認を区別する。', 'Показаны 13 учебных пунктов и статус сохранения. Различайте проверку конфигурации и функций.', '13 ta mashq bandi va saqlash holati ko‘rinadi. Faqat sozlama tekshiruvi bilan funksional tekshiruvni farqlang.'),
 T('誤パスワードなら既存の正しい値でやり直す。結果の更新だけなら「結果を更新する」を使う。新しい機能確認は確認用CKレコードを1件追加する。', 'При неверном пароле повторите с правильным существующим. Для просмотра текущего запуска обновите результат. Каждый новый функциональный запуск добавляет одну запись CK.', 'Parol xato bo‘lsa to‘g‘ri mavjud qiymat bilan takrorlang. Joriy urinishni ko‘rish uchun natijani yangilang. Har yangi funksional tekshiruv bitta CK yozuv qo‘shadi.'))

m = module('P6', T('最小権限と公開範囲', 'Минимальные права и границы публикации', 'Eng kam huquq va ochiq kirish chegarasi'),
 T('正しい動作を保ち、不要な管理経路・DB権限・秘密fileの公開を拒否する。', 'Сохранить штатную работу, запретив лишние admin-маршруты, SQL-права и раскрытие секретов.', 'To‘g‘ri ishlashni saqlab, ortiqcha admin yo‘li, SQL huquqi va maxfiy fayl ochilishini rad etish.'),
 T('P5のpractice profileを使う。setup roleを無効化し、一時設定を片付け、正規loginを対照に拒否を自動確認する。SGやIAMの許可を広げない。', 'Используйте practice из P5. Отключите setup-role, уберите временную конфигурацию и проверьте отказы при наличии успешного контрольного login. Не расширяйте SG/IAM.', 'P5 practice profile dan foydalaning. Setup role ni o‘chiring, vaqtinchalik sozlamani olib tashlang, muvaffaqiyatli login bilan solishtirib rad etishlarni tekshiring. SG/IAM ni kengaytirmang.'))
step(m, T('DB roleとtable権限を読む', 'Прочитать роли и права таблиц', 'DB role va jadval huquqlarini o‘qish'), 'dbsql',
 T('DBでpostgresのpsqlへ入る。\\dpはtable権限、\\duはrole属性。auth_user全体のUPDATEではなくlast_login/password列だけ、catalog_itemにDELETEなし、lookupは読取りだけ、django_migrationsは権限なしをSQL03と比べる。sequenceのnextval/setvalは確認目的で呼ばない。', 'Откройте psql как postgres на DB. \\dp показывает права таблиц, \\du — атрибуты ролей. Сверьте с SQL03: UPDATE auth_user только last_login/password, без DELETE catalog_item; lookup только чтение, django_migrations без прав. Не вызывайте nextval/setval ради проверки.', 'DB da postgres psql ni oching. \\dp jadval huquqini, \\du role atributini ko‘rsatadi. SQL03 bilan solishtiring: auth_user UPDATE faqat last_login/password, catalog_item DELETE yo‘q; lookup faqat o‘qish, django_migrations huquqsiz. Tekshirish uchun nextval/setval chaqirmang.'),
 r'''sudo -u postgres psql -X -d jdu_catalog_practice
\du catalog_practice_*
\dp public.*
\q''',
 T('runtimeはowner/superuserではない。Django sessionには必要なDELETEがあるが備品削除権限とは別。', 'Runtime не владелец и не superuser. DELETE для Django session нужен, но не означает право удаления оборудования.', 'Runtime owner yoki superuser emas. Django session uchun DELETE zarur, lekin bu jihoz yozuvini o‘chirish huquqi emas.'),
 T('想定外の権限があればSQL03のguardを維持して見直す。実データを削除して拒否を試さない。', 'При лишних правах пересмотрите SQL03 с сохранением guard. Не пробуйте отказ удалением реальных строк.', 'Ortiqcha huquqda SQL03 guard ini saqlab tekshiring. Haqiqiy qatorni o‘chirib rad etishni sinamang.'))
step(m, T('setup roleをNOLOGINにする', 'Отключить вход setup-роли', 'Setup role login ini o‘chirish'), 'db',
 T('初期化に使ったsetup roleは完成後には不要。SQL04はNOLOGIN/password NULLにし、そのprofileの残存setup接続も閉じる。DB/tableの所有者はsetupのまま残す。削除やappへの所有権移転はしない。', 'После инициализации вход setup не нужен. SQL04 задаёт NOLOGIN/password NULL и закрывает оставшиеся setup-подключения profile. Владельцем DB/table остаётся setup; роль не удаляется и владение app не передаётся.', 'Tayyorlashdan keyin setup login kerak emas. SQL04 NOLOGIN/password NULL qiladi va shu profile setup ulanishlarini yopadi. DB/table egasi setup bo‘lib qoladi; role o‘chirilmaydi, egalik app ga o‘tmaydi.'),
 'cd /var/lib/jdu-web/lesson-resources-r1/app\npython3 -B profile_sql.py --profile practice 04_disable_setup.sql\npython3 -B profile_sql.py --profile practice 04_disable_setup.sql | sudo -u postgres psql -X -v ON_ERROR_STOP=1 -d jdu_catalog_practice',
 T('ALTER ROLE成功。通常catalog_practice_appの動作を止めない。', 'ALTER ROLE успешен, работа catalog_practice_app сохраняется.', 'ALTER ROLE muvaffaqiyatli; catalog_practice_app ishlashi saqlanadi.'),
 T('この後setupをLOGINへ戻して常用しない。M5は別のmission setup roleで初期化する。', 'Не включайте setup обратно для обычной работы. M5 инициализируется отдельной setup-role mission.', 'Keyin setup ni odatiy ish uchun LOGIN ga qaytarmang. M5 alohida mission setup role bilan tayyorlanadi.'))
step(m, T('一時設定を片付け、通常接続の設定を選び直す', 'Убрать временные настройки и заново выбрать runtime', 'Vaqtinchalik sozlamani olib tashlab, runtime ni qayta tanlash'), 'web',
 T('Webで対象のmetadataだけを確認する。rmの対象は練習setupの2fileに限定する。app.env、practice.app.env、DB runtime file、元command-state、SSH鍵、採点認証は残す。対象を片付けたらアプリを停止し、既存のpractice設定を明示的に選び直してから起動する。この順番を練習しておくと、M5でmissionを選ぶときにも使える。', 'На Web проверьте только metadata. Удалите ровно два файла setup practice. app.env, practice.app.env, DB runtime, command-state, SSH-ключи и данные оценивания сохраняются. Затем остановите приложение, явно выберите существующий профиль practice и запустите приложение. Тот же порядок пригодится в M5 при выборе mission.', 'Web da faqat metadata ni tekshiring. Faqat ikkita practice setup faylini o‘chiring. app.env, practice.app.env, DB runtime, command-state, SSH kalit va baholash ma’lumoti qoladi. So‘ng ilovani to‘xtating, mavjud practice profilini aniq tanlab, ilovani ishga tushiring. Shu tartib M5 da mission ni tanlashda kerak bo‘ladi.'),
 """sudo stat -c '%U:%G %a %n' /etc/jdu-catalog/setup.env /etc/jdu-catalog/profiles/practice.setup.env
sudo rm -- /etc/jdu-catalog/setup.env /etc/jdu-catalog/profiles/practice.setup.env
sudo stat -c '%U:%G %a %n' /etc/jdu-catalog/app.env /etc/jdu-catalog/profiles/practice.app.env /etc/jdu-web/db-practice.runtime.env
sudo systemctl stop jdu-catalog
sudo python3 -B /opt/jdu-catalog/app/configuration.py activate --profile practice
sudo python3 -B /opt/jdu-catalog/app/configuration.py check --phase runtime
sudo systemctl start jdu-catalog
systemctl is-active jdu-catalog""",
 T('通常用ファイルはroot:root 600。CATALOG_PROFILE_ACTIVATED=practice、設定チェック成功、最後にactiveと表示される。次の手順で一覧を開き、練習用DBの備品が表示されることを確かめる。', 'Файлы runtime имеют root:root 600. Ожидаются CATALOG_PROFILE_ACTIVATED=practice, успешная проверка и статус active. В следующем шаге проверьте записи учебной БД в списке.', 'Runtime fayllari root:root 600. CATALOG_PROFILE_ACTIVATED=practice, tekshiruv muvaffaqiyati va active holatini kuting. Keyingi qadamda ro‘yxatdagi mashq DB yozuvlarini tekshiring.'),
 T('練習用以外の設定が有効なら、ここで止める。既に削除済みのファイルは削除し直さない。停止・設定の選択・設定チェックが失敗したら、原因を確認してからアプリを起動する。', 'Если активен другой профиль, остановитесь. Не повторяйте удаление отсутствующих файлов. При ошибке остановки, выбора профиля или проверки выясните причину до запуска приложения.', 'Boshqa profil faol bo‘lsa, to‘xtang. O‘chirilgan fayllarni qayta o‘chirmang. To‘xtatish, profilni tanlash yoki tekshirishda xato bo‘lsa, ilovani ishga tushirishdan oldin sababini aniqlang.'))
step(m, T('公開80から管理画面と秘密が見えないか確認する', 'Проверить запрет admin и секретов на публичном 80', 'Ochiq 80 da admin va maxfiy fayl ko‘rinmasligini tekshirish'), 'bst',
 T('踏み台のSSMで公開用port80を使い、通常一覧の成功を対照に/admin/やenvを要求する。8080の管理成功はRDP内Firefoxで別に確認する。404/403等の明示拒否と通常成功を組にして読み、timeoutだけで安全としない。', 'В SSM бастиона запросите обычный список на 80, затем /admin/ и env. Отдельно подтвердите штатный admin на 8080 в Firefox через RDP. Нужны нормальный ответ и явный отказ 404/403; таймаута недостаточно.', 'Bastion SSM da 80 orqali avval oddiy ro‘yxatni, keyin /admin/ va env ni so‘rang. 8080 dagi to‘g‘ri admin kirishni RDP Firefox da alohida tekshiring. Oddiy muvaffaqiyat va aniq 404/403 rad etish kerak; timeout yetarli emas.'),
 'curl --noproxy \'*\' -i http://web.lab.test/\ncurl --noproxy \'*\' -i http://web.lab.test/admin/\ncurl --noproxy \'*\' -i http://web.lab.test/app.env\ncurl --noproxy \'*\' -i http://web.lab.test/static/app.env',
 T('一覧は200、管理とenvは秘密を含まない拒否。公開用NginxがX-JDU-Entryを上書きして管理偽装を許さない。', 'Список — 200; admin/env отклоняются без секретов. Публичный Nginx перезаписывает X-JDU-Entry и не допускает подмену входа.', 'Ro‘yxat 200; admin/env maxfiy ma’lumotsiz rad etiladi. Ochiq Nginx X-JDU-Entry ni qayta yozib kirishni soxtalashtirishga yo‘l qo‘ymaydi.'),
 T('もしenv本文が見えたら共有せず、その場で教師へ知らせ公開設定を修正する。', 'Если виден текст env, не распространяйте его: сообщите преподавателю и исправьте публикацию.', 'Env matni ko‘rinsa uni ulashmang; o‘qituvchiga aytib ochiq sozlamani tuzating.'))
step(m, T('正規成功と拒否を同じ確認回で送る', 'Отправить успешный вход и отказы в одной проверке', 'Bir tekshiruvda to‘g‘ri kirish va rad etishlarni yuborish'), 'portal',
 T('Web PortalでP6を選び、「機能・権限を含めて確認する」から既存practice_adminパスワードを非表示入力する。正規loginを対照に、匿名登録/編集や誤passwordがDBを変えず拒否されるかを確かめる。CSRF不足だけの403と認可制限を混同しない。通常userは備品のview/add/changeだけを持ち、deleteやuser管理は持たない。', 'В Web Portal выберите P6, функциональную проверку с правами и скрыто введите существующий пароль practice_admin. Успешный login служит контролем: анонимные операции и неверный пароль должны отклоняться без изменения БД. Один CSRF-403 не доказывает авторизацию. Staff имеет только view/add/change оборудования, без delete и управления пользователями.', 'Web Portal da P6 va funksiya/huquq tekshiruvini tanlab, practice_admin mavjud parolini yashirin kiriting. To‘g‘ri login nazorat bo‘lib, anonim amallar va xato parol DB ni o‘zgartirmasdan rad etilishini tekshiradi. Faqat CSRF-403 avtorizatsiya isboti emas. Staff faqat jihoz view/add/change huquqiga ega, delete va user boshqaruvi yo‘q.'),
 '',
 T('練習16項目と保存状態を読む。M6はmission profileで別に確認する。「保存済み成績を見る」でMの成績原本を確認できる。', 'Прочитайте 16 учебных пунктов и статус сохранения. M6 проверяется отдельно в mission. Сохранённые оценки M доступны в разделе оценок.', '16 ta mashq bandi va saqlash holatini o‘qing. M6 mission profile da alohida tekshiriladi. Saqlangan baholar bo‘limida M asl bahosini ko‘rish mumkin.'),
 T('処理中は結果を更新する。UNKNOWNは原因を直して再確認する。満点表示のためにgrade fileを編集しない。', 'Во время обработки обновляйте результат. Устраните причину UNKNOWN и проверьте заново. Не редактируйте grade-файлы ради баллов.', 'Ishlov paytida natijani yangilang. UNKNOWN sababini tuzatib qayta tekshiring. Ball uchun grade faylini tahrirlamang.'))

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
 'M1': T('P1を参考に、指定された別fileと本文を独力でHTTP配信する。P1のpractice.txtを残す。file・service・listen・local/踏み台/public HTTP・今回要求のlogが対象。', 'По навыкам P1 самостоятельно выдайте другой заданный файл и текст. Сохраните practice.txt. Проверяются файл, сервис, слушатель, local/bastion/public HTTP и журнал текущего запроса.', 'P1 ko‘nikmasi bilan belgilangan boshqa fayl va matnni mustaqil tarqating. practice.txt ni saqlang. Fayl, service, listen, local/bastion/public HTTP va joriy so‘rov log i tekshiriladi.'),
 'M2': T('同じlab.test zoneへ正式6名を設定する。P2のguide/practice-dbは保持してよい。踏み台/Webの通常resolver、名前によるM1 HTTP、DB名、UDP/TCP、外部forward、NXDOMAIN、ACL、AXFR拒否まで確認する。', 'Добавьте шесть основных имён в ту же zone lab.test. guide/practice-db можно сохранить. Нужны обычный resolver бастиона/Web, HTTP M1 по имени, имя DB, UDP/TCP, forwarding, NXDOMAIN, ACL и запрет AXFR.', 'Ayni lab.test zone ga oltita asosiy nomni qo‘shing. guide/practice-db qolishi mumkin. Bastion/Web odatiy resolver, nom orqali M1 HTTP, DB nomi, UDP/TCP, forwarding, NXDOMAIN, ACL va AXFR rad etilishi kerak.'),
 'M3': T('M専用markerを自分のLab IDで作る。P3とは別のブラウザで停止前記録→AWS Stop→ブラウザで停止完了確認→AWS Start→ブラウザで再開後確認を行う。対象は同じWebと元root volume。単なるrebootでは不可。backup/restoreとdisk追加は不要。', 'Создайте отдельный marker M со своим Lab ID. Отдельно от P3 пройдите браузер: запись до остановки → AWS Stop → браузер: подтверждение остановки → AWS Start → браузер: проверка после запуска. Нужны тот же Web и исходный root volume; reboot не подходит. Backup/restore и новый диск не нужны.', 'O‘z Lab ID bilan alohida M marker yarating. P3 dan alohida brauzerda oldingi holat → AWS Stop → brauzerda to‘xtashni tekshirish → AWS Start → brauzerda saqlanishni tekshirish ketma-ketligini bajaring. Ayni Web va asl root volume kerak; oddiy reboot yetmaydi. Backup/restore va yangi disk kerak emas.'),
 'M4': T('本課題用DB/roleを自分で構築する。P4.7の名前指定と同じ方法で、M2のdb.lab.testを使い、Webのruntime roleで認証SELECTを成功させる。HBAはWeb/32・正しいDB/roleだけ。既存passwordをWeb内のmission用helperへ保存し、practiceと混ぜない。app tableはまだ不要。', 'Самостоятельно настройте основную БД и роли. Используйте db.lab.test из M2 по аналогии с подключением по имени в P4.7 и выполните SELECT с Web runtime-role. HBA разрешает только Web/32 и правильную пару DB/role. Существующий пароль сохраните через helper mission на Web, отдельно от practice. Таблицы приложения пока не нужны.', 'Asosiy DB va rollarni mustaqil quring. P4.7 dagi nom bilan ulanish usulini qo‘llab, M2 dagi db.lab.test orqali Web runtime role orqali SELECT bajaring. HBA faqat Web/32 va to‘g‘ri DB/role juftiga ruxsat beradi. Mavjud parolni Web mission helper orqali practice dan alohida saqlang. App jadvallari hali kerak emas.'),
 'M5': T('同じ教員アプリをmission DBへ接続する。P5のpractice手順を参考にprofile=missionを選ぶ。既存app/venvを再配置しない。アプリの停止はP6.3、通常接続の設定を作って選び、一時構築用の設定を作る流れはP5.4〜P5.5で練習した手順を使う。設定対象を課題用のmissionに置き換える。固定migration/seed/管理者と権限をそのDBへ構築し指定2件を登録する。P1/M1を保持する。完成後はmissionをactiveにする。', 'Подключите то же приложение к БД mission. Используйте навыки P5 с profile=mission, не копируйте заново app/venv. Остановите приложение по примеру P6.3. Используйте порядок P5.4–P5.5 для создания и активации runtime и подготовки временного setup, подставив профиль mission. Выполните migrations/seed/admin и grants в основной БД, добавьте две заданные записи. Сохраните P1/M1, оставьте mission активным.', 'Ayni app ni mission DB ga ulang. P5 ko‘nikmasi bilan profile=mission tanlang, app/venv ni qayta joylamang. Ilovani P6.3 dagi mashq kabi to‘xtating. Runtime yaratish va faollashtirish, so‘ng vaqtinchalik setup yaratishda P5.4–P5.5 tartibini mission profili bilan qo‘llang. Asosiy DB da migrations/seed/admin va grants ni bajaring, ikkita belgilangan yozuvni kiriting. P1/M1 ni saqlab mission ni active qoldiring.'),
 'M6': T('mission側の最小権限を完成する。catalog_setupはNOLOGIN/password NULL、一時mission setup.envは残さない。root管理コード/venv、600秘密file、公開80からの管理拒否、private8080の正規成功、備品のview/add/changeだけの管理者、公開/非公開分離とSQL権限を確認する。ブラウザの機能確認は本人実演ではなく自動確認。', 'Завершите минимальные права mission: catalog_setup NOLOGIN/password NULL, временные setup-файлы удалены. Проверьте root-код/venv, секреты 600, запрет admin на 80, успешный private8080, права admin только view/add/change, разделение публичных данных и SQL-права. Функциональная проверка в браузере автоматическая; личная демонстрация не нужна.', 'Mission eng kam huquqini tugating: catalog_setup NOLOGIN/password NULL, vaqtinchalik setup fayllari qolmasin. Root kod/venv, 600 maxfiy fayl, 80 da admin rad etilishi, private8080 muvaffaqiyati, admin faqat view/add/change, ochiq/yopiq ma’lumot va SQL huquqlarini tekshiring. Brauzerdagi funksional tekshiruv avtomatik; shaxsiy namoyish kerak emas.'),
}
