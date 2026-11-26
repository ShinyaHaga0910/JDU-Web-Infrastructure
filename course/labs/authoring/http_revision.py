"""Current HTTP lesson requirements, separate from the frozen signed course kit."""

def revise_content(modules, guidance, T):
    p1 = next(m for m in modules if m['id'] == 'P1')
    p1['problem'] = T('Nginxを設定し、`/var/www/jdu-practice/practice.txt` をHTTPで配信する。',
        'Настройте Nginx для выдачи `/var/www/jdu-practice/practice.txt` по HTTP.',
        'Nginx ni sozlab, `/var/www/jdu-practice/practice.txt` faylini HTTP orqali tarqating.')
    file = p1['steps'][1]
    file['code'] = file['code'].replace('/var/www/html', '/var/www/jdu-practice').replace(
        'sudo cp practice.txt', 'sudo mkdir -p /var/www/jdu-practice\nsudo cp practice.txt').replace(
        'chown root:root', 'chown root:www-data').replace('chmod 0644', 'chmod 0640').replace('\ncat ', '\nsudo cat ')
    file['expect'] = T('`root:www-data 640 /var/www/jdu-practice/practice.txt` と表示され、本文は `JDU WEB-02 practice: HTTP response verified.` の1行である。',
        'Показано `root:www-data 640 /var/www/jdu-practice/practice.txt`; текст — одна строка `JDU WEB-02 practice: HTTP response verified.`.',
        '`root:www-data 640 /var/www/jdu-practice/practice.txt` ko‘rinadi. Matn bitta qator: `JDU WEB-02 practice: HTTP response verified.`.')
    config = p1['steps'][2]
    config['title'] = T('Nginxに配信先を設定する', 'Настроить каталог выдачи в Nginx', 'Nginx da tarqatish katalogini sozlash')
    config['why'] = T(
        '`sudo nano /etc/nginx/sites-available/default` で設定を開く。`listen 80` がある既存の `server { ... }` の中へ、下の設定を追加する。別の `location` の中には入れない。`/practice.txt` をリクエストされたとき、Nginxは指定したrootにパスをつなげて `/var/www/jdu-practice/practice.txt` を読む。保存後、構文検査に成功したら設定を再読み込みする。',
        'Откройте настройки командой `sudo nano /etc/nginx/sites-available/default`. Добавьте блок ниже внутрь существующего `server { ... }` с `listen 80`, вне других блоков `location`. Для запроса `/practice.txt` Nginx добавляет путь к root и читает `/var/www/jdu-practice/practice.txt`. Сохраните файл, проверьте синтаксис и перечитайте настройки.',
        '`sudo nano /etc/nginx/sites-available/default` bilan sozlamani oching. Quyidagi blokni `listen 80` mavjud `server { ... }` ichiga, boshqa `location` bloklaridan tashqariga qo‘shing. `/practice.txt` so‘ralganda Nginx yo‘lni root ga qo‘shib, `/var/www/jdu-practice/practice.txt` ni o‘qiydi. Saqlang, sintaksisni tekshiring va sozlamani qayta yuklang.')
    config['code'] = 'sudo nano /etc/nginx/sites-available/default\n' + config['code']
    config['editor_input'] = 'location = /practice.txt {\n    root /var/www/jdu-practice;\n}'
    config['editor_before'] = T(
        '''**追加する位置**

![nanoで開いたNginxの既存設定。location / の閉じ括弧の直後に新しいブロックを追加する。](../../assets/shared/nginx-default-location-before.png)

nanoで `location / {` を探す。Ctrl+Wで `location /` を検索してもよい。画面の `try_files $uri $uri/ =404;` と、その次の `}` は削除しない。この `}` が既存の `location /` の終わりである。その下の空行へカーソルを移し、次の3行を追加する。`try_files` の直下、つまり `}` より手前には入れない。''',
        '''**Место добавления**

![Исходные настройки Nginx в nano. Новый блок добавляется сразу после закрывающей скобки location /.](../../assets/shared/nginx-default-location-before.png)

Найдите `location / {` в nano. Можно нажать Ctrl+W и найти `location /`. Не удаляйте строку `try_files $uri $uri/ =404;` и следующую `}`: эта скобка завершает существующий блок `location /`. Переместите курсор на пустую строку ниже этой скобки и добавьте следующие три строки. Не вставляйте их между `try_files` и закрывающей скобкой.''',
        '''**Qo‘shish joyi**

![nano dagi Nginx ning mavjud sozlamasi. Yangi blok location / ni yopuvchi qavsdan keyin qo‘shiladi.](../../assets/shared/nginx-default-location-before.png)

nano da `location / {` ni toping. Ctrl+W orqali `location /` ni qidirish mumkin. `try_files $uri $uri/ =404;` qatorini ham, undan keyingi `}` ni ham o‘chirmang. Bu qavs mavjud `location /` blokini yopadi. Kursorni shu qavs ostidagi bo‘sh qatorga olib, quyidagi uch qatorni qo‘shing. Ularni `try_files` bilan yopuvchi qavs orasiga yozmang.''')
    placement = 'location / {\n    try_files $uri $uri/ =404;\n}\n\nlocation = /practice.txt {\n    root /var/www/jdu-practice;\n}'
    config['editor_after'] = T(
        '**追加後の配置（一部抜粋）**\n\n既存のブロックと追加するブロックは、次のように並ぶ。どちらも既存の `server { ... }` の中に置く。ファイル全体をこの例へ置き換えず、ほかの設定と上側の `root /var/www/html;` はそのまま残す。\n\n```text\n' + placement + '\n```\n\n`location = /practice.txt` は、リクエストのパスが `/practice.txt` と完全に一致するときの設定である。その場合だけ追加したrootを使い、`/var/www/jdu-practice/practice.txt` を読む。',
        '**Расположение после добавления (фрагмент)**\n\nСуществующий и новый блоки должны стоять рядом, как ниже. Оба находятся внутри существующего `server { ... }`. Не заменяйте весь файл этим примером: сохраните остальные настройки и расположенную выше строку `root /var/www/html;`.\n\n```text\n' + placement + '\n```\n\n`location = /practice.txt` применяется при точном совпадении пути запроса с `/practice.txt`. Только в этом случае используется новый root и читается `/var/www/jdu-practice/practice.txt`.',
        '**Qo‘shilgandan keyingi joylashuv (parcha)**\n\nMavjud va yangi bloklar quyidagidek yonma-yon turadi. Ikkalasi ham mavjud `server { ... }` ichida bo‘ladi. Butun faylni bu misol bilan almashtirmang: boshqa sozlamalar va yuqoridagi `root /var/www/html;` qatori saqlansin.\n\n```text\n' + placement + '\n```\n\n`location = /practice.txt` so‘rov yo‘li `/practice.txt` ga aynan mos kelganda ishlaydi. Faqat shu holatda yangi root ishlatiladi va `/var/www/jdu-practice/practice.txt` o‘qiladi.')
    guidance['M1'] = T(
        '''P1と同じWebサーバーで、`/var/www/jdu-mission/mission.txt` をTCPの80番ポートから `/mission.txt` として配信する。P1のファイルと設定も残し、`/practice.txt` を引き続き開けるようにする。

1. **配信ファイル（P1.2）**　`/var/www/jdu-mission` を作り、下の本文で `mission.txt` を配置する。所有者を `root`、所有グループを `www-data`、権限を `0640` にする。
2. **Nginxの設定（P1.3）**　`/etc/nginx/sites-available/default` の80番ポートを受け付ける既存の `server` 内に、`/mission.txt` と完全一致する `location` を追加し、その `root` に `/var/www/jdu-mission` を指定する。P1の設定を残し、構文検査に成功してから再読み込みする。
3. **HTTPとログ（P1.4〜P1.6）**　Webサーバー自身と踏み台サーバーから `/mission.txt` を開き、HTTP 200と下の本文を確認する。`/practice.txt` も開けることと、リクエストがアクセスログに残ることを確認する。''',
        '''На том же Web-сервере выдавайте `/var/www/jdu-mission/mission.txt` по TCP-порту 80 как `/mission.txt`. Сохраните файл и настройки P1: `/practice.txt` должен оставаться доступным.

1. **Файл (P1.2).** Создайте `/var/www/jdu-mission` и разместите `mission.txt` с текстом ниже. Владелец — `root`, группа — `www-data`, права — `0640`.
2. **Настройки Nginx (P1.3).** В существующий `server` для порта 80 в `/etc/nginx/sites-available/default` добавьте `location` с точным совпадением `/mission.txt` и root `/var/www/jdu-mission`. Сохраните блок P1, проверьте синтаксис и перечитайте настройки.
3. **HTTP и журнал (P1.4–P1.6).** Откройте `/mission.txt` с Web и бастиона: должны вернуться HTTP 200 и текст ниже. Проверьте доступность `/practice.txt` и записи запросов в access log.''',
        '''P1 dagi Web serverda `/var/www/jdu-mission/mission.txt` ni TCP 80 orqali `/mission.txt` sifatida tarqating. P1 fayli va sozlamasini saqlang: `/practice.txt` ham ochilsin.

1. **Fayl (P1.2).** `/var/www/jdu-mission` katalogini yarating va quyidagi matnli `mission.txt` ni joylang. Egasi `root`, guruhi `www-data`, ruxsati `0640` bo‘lsin.
2. **Nginx sozlamasi (P1.3).** `/etc/nginx/sites-available/default` ichidagi 80-portni qabul qiladigan mavjud `server` ga `/mission.txt` bilan aniq mos keladigan `location` qo‘shing. Uning root qiymati `/var/www/jdu-mission` bo‘lsin. P1 blokini saqlang, sintaksisni tekshiring va sozlamani qayta yuklang.
3. **HTTP va log (P1.4–P1.6).** Web va Bastiondan `/mission.txt` ni oching: HTTP 200 va quyidagi matn qaytsin. `/practice.txt` ham ochilishini va so‘rovlar access log ga yozilishini tekshiring.''')
    app = next(m for m in modules if m['id'] == 'P5')['steps'][7]
    command = 'sudo nano /etc/nginx/sites-available/jdu-catalog'
    app['code'] = app['code'].replace('sudo nginx -t', command + '\nsudo nginx -t')
    app['editor_input'] = 'location = /practice.txt { root /var/www/jdu-practice; try_files $uri =404; }\nlocation = /mission.txt { root /var/www/jdu-mission; try_files $uri =404; }'
    extra = T('コピーした設定の `/practice.txt` と `/mission.txt` の2つのlocationを、下の内容へ置き換える。P1・M1の配信ディレクトリを引き継ぐための変更である。他の設定は保持する。',
        'В скопированной конфигурации замените два location для `/practice.txt` и `/mission.txt` на блоки ниже. Так сохраняются каталоги P1 и M1. Остальные настройки оставьте.',
        'Nusxalangan sozlamada `/practice.txt` va `/mission.txt` uchun ikkita location ni quyidagi bloklarga almashtiring. Bu P1 va M1 kataloglarini saqlaydi. Qolgan sozlamalar o‘zgarmasin.')
    app['why'] = {lang: app['why'][lang] + '\n\n' + extra[lang] for lang in extra}


def revise_notes(notes, T):
    notes['P1.2'] = T('`chown root:www-data` で所有者をroot、所有グループをwww-dataにする。`chmod 0640` は所有者に読み書き、グループに読み取りを許可し、その他のユーザーには許可しない。Nginxのワーカープロセスはwww-dataとして動くため、このグループの権限でファイルを読める。',
        '`chown root:www-data` задаёт владельца root и группу www-data. `chmod 0640` разрешает владельцу читать и писать, группе — читать, остальным доступ закрыт. Рабочие процессы Nginx работают от www-data и читают файл с правами этой группы.',
        '`chown root:www-data` egani root, guruhni www-data qiladi. `chmod 0640` egaga o‘qish/yozish, guruhga o‘qish huquqini beradi; boshqalarga ruxsat yo‘q. Nginx worker process lari www-data sifatida ishlaydi va guruh huquqi bilan faylni o‘qiydi.')
