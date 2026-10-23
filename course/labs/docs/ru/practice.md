# Web Infrastructure: практика P0-P6 с подробными шагами

2026-10-23 | D12 P/M r1 | web-course-class193548-20261023-r2

Первая редакция для проверки преподавателем. Полное прохождение по пособию студентом ещё не проверено.

Русский и узбекский тексты синхронизированы с японским оригиналом. Редактура носителями языка ещё не выполнена.

[日本語](../ja/practice.md) · [Русский](../ru/practice.md) · [O‘zbekcha](../uz/practice.md)

## Как пользоваться пособием

Сначала прочитайте задание P; при необходимости проходите подробный пример по шагам. P - тренировка без оценочных баллов. В M самостоятельно используйте другие объекты/значения. Номера заданий не являются номерами занятий; идите в своём темпе. Выполнение P не означает выполнение M.

P0 → M0 → P1 → M1 → P2 → M2 → P3 → M3 → P4 → M4 → P5 → P6 → M5 → M6

P5 требует DNS из M2. P4 подключается по IP, а приложение - по db.lab.test. Перед переключением practice → mission завершите setup в P6. P - добровольная тренировка; checker оценивает текущие предпосылки M.

M1=8, M2=13, M3=3, M4=9, M5=13, M6=16: всего 62 исходных балла. M0=0. Нет личной демонстрации, backup/restore, дополнительных дисков и разработки приложения. Пересчёт в 25 баллов делает преподаватель отдельно. Повторные отправки возможны до объявленного срока. PASS разных попыток не объединяются; максимум автоматически не выбирается.

## Среда и подготовка

Сначала завершите проверку подписи начального комплекта, создание пяти узлов либо install в существующую среду, внутренний SSH и личную регистрацию. Инструкция - distribution/STUDENT.md в zip. Не храните приватные ключи в общем Windows; используйте CloudShell личного Academy account. Преподаватель выдаёт личный анонимный Lab ID, fingerprint и срок действия.

Общие private IP ниже; public IPv4 не фиксируется. AWS region us-east-1, Ubuntu24.04/amd64. RDP: labuser; SSM: ssm-user; внутренний SSH: ubuntu. Не путайте пользователя и роль сервера.

| Role | Private IPv4 | Назначение |
| --- | --- | --- |
| bastion | 10.20.1.10 | RDP3389 / Firefox / SSH |
| web | 10.20.1.20 | HTTP80 / private8080 / loopback8000 |
| dns | 10.20.2.10 | BIND UDP/TCP53 |
| db | 10.20.2.20 | PostgreSQL5432 |
| repo | 10.20.2.30 | HTTP80 с заранее сохранёнными подписанными ресурсами |

Для входа в каждый Ubuntu выполните в CloudShell aws ssm start-session --target i-СВОЙ-ID. Сразу проверяйте id -un и role из bootstrap.json. Для смены сервера один exit возвращает в CloudShell; затем подключайтесь к следующему ID. Переменные CloudShell не копируются на узел. ssm-user может sudo; RDP-пользователь labuser не администратор sudo.

Редактор nano: открыть файл → ввести текст → Ctrl+O → Enter сохранить → Ctrl+X выйти. Блок конфигурации не выполняется как shell-команда. В psql меняется prompt; SQL/\password вводятся внутри, \q возвращает в Ubuntu. Не продолжайте после ошибки без проверки результата.

## P0 Своя среда и место выполнения команд

### Что изучаем

Различать CloudShell, Windows и пять Ubuntu-серверов; подключаться через SSM к нужному узлу и запускать самопроверку.

### Задание

Проверьте свой Lab ID, ID комплекта и instance ID пяти ролей. Это проверка предоставленной среды, 0 баллов. Если пяти серверов ещё нет, сначала выполните начальную установку. Для готовой среды не повторяйте create, создание ключей и регистрацию.

### Пример решения: выполняйте по одному шагу

#### P0.1 Активировать комплект в своём CloudShell

**Место выполнения:** CloudShell в личном AWS-аккаунте студента

**Цель и действия:** Откройте AWS из своего класса Academy, затем CloudShell. Замените значения в первых двух строках данными преподавателя. Знак доллара означает обращение к переменной и вводится как часть команды. activate.sh добавляет каталог нового проверяющего инструмента в PATH.

```bash
LAB_ID='YOUR-LAB-ID'
COURSE_ID='web-course-class193548-20261023-r2'
INSTALL="$HOME/.local/share/jdu-web/courses/$COURSE_ID/$LAB_ID"
source "$INSTALL/activate.sh"
aws sts get-caller-identity --query Account --output text
command -v jdu-web-check
jdu-web-check --help
```

**Ожидаемый результат и его смысл:** Account соответствует вашему аккаунту, а путь команды содержит ваши COURSE_ID и LAB_ID. Справка перечисляет P0-P6/M0-M6.

**Если не получилось:** При No such file проверьте начальную установку и install. Старая команда поддерживает не все задания. Просроченный комплект обновляет преподаватель.

#### P0.2 Записать instance ID пяти серверов

**Место выполнения:** AWS Console своего студенческого аккаунта

**Цель и действия:** В EC2 → Instances сверяйте теги LabId и DeploymentId. Запишите instance ID ролей bastion/web/dns/db/repo в рабочую таблицу. Не выбирайте только по имени. Public IPv4 есть у bastion и web. Для SSM нужен instance ID, а не публичный IP.

**Ожидаемый результат и его смысл:** Все пять узлов running и SSM Online; private IP совпадают с общей таблицей. Public IPv4 может измениться после остановки и запуска.

**Если не получилось:** Не трогайте другой Lab, аккаунт или неизвестные узлы. Для остановленных серверов используйте инструкцию запуска. Не применяйте Reset или Terminate.

#### P0.3 Подключиться по SSM и вернуться

**Место выполнения:** CloudShell в личном AWS-аккаунте студента

**Цель и действия:** Подставьте instance ID Web из EC2. После подключения вы работаете в Ubuntu, а не в CloudShell. id -un показывает управляющего пользователя SSM; role в bootstrap.json - роль сервера. Один exit возвращает в CloudShell.

```bash
aws ssm start-session --target i-YOUR-WEB-INSTANCE-ID
id -un
hostname
python3 -c 'import json;print(json.load(open("/etc/jdu-web/bootstrap.json"))["role"])'
pwd
exit
```

**Ожидаемый результат и его смысл:** Ожидаются ssm-user и role web. Проверяйте их при каждом переходе. При SSH имя пользователя Ubuntu может быть ubuntu.

**Если не получилось:** При TargetNotConnected проверьте running, SSM Online и регион us-east-1. Не открывайте все порты SG и не скачивайте ключи в Windows.

#### P0.4 Подготовить только открытые учебные файлы

**Место выполнения:** CloudShell в личном AWS-аккаунте студента

**Цель и действия:** Загрузите zip этого пособия через CloudShell → Actions → Upload file; распакуйте командой unzip web-lab-pm-r1.zip. Перейдите в resources и выполните команду. Инструмент сверяет личный подписанный комплект и исходные пять узлов; переносит открытые файлы приложения, SQL и инструмент скрытого ввода на Web/DB. Сервисы и БД он не создаёт, секреты не передаёт.

```bash
cd "$HOME/web-lab-pm-r1/resources"
python3 -B stage_resources.py --installation "$INSTALL"
```

**Ожидаемый результат и его смысл:** Вывод содержит PUBLIC_LESSON_RESOURCES_READY=web и =db. Открытые файлы находятся в /var/lib/jdu-web/lesson-resources-r1; отличающиеся существующие файлы не заменяются.

**Если не получилось:** При незавершённой установке, другой версии или истечении срока остановитесь и сообщите преподавателю. Не используйте проверочные fixture, автоматически создающие готовое решение.

#### P0.5 Различать самопроверку и отправку

**Место выполнения:** CloudShell в личном AWS-аккаунте студента

**Цель и действия:** Проверка наблюдает текущее состояние. --no-submit означает только самопроверку, без отправки. Обычный запуск передаёт и промежуточный результат. P0/M0 проверяют готовность, но не добавляют баллы к оценке.

```bash
jdu-web-check P0 --no-submit
jdu-web-check P0
jdu-web-check M0 --no-submit
```

**Ожидаемый результат и его смысл:** Читайте готовность/complete отдельно от доставки. STORED - принято; PENDING - ожидает отправки; UNKNOWN - состояние не удалось проверить.

**Если не получилось:** Для обращения запишите check ID, время и роль узла. Не передавайте token, пароль и личный URL.

#### P0.6 Открыть рабочий стол бастиона по RDP

**Место выполнения:** Windows PC студента (общая учётная запись)

**Цель и действия:** Используйте текущий public IPv4 бастиона из EC2. Нажмите Windows+R, введите mstsc /prompt и Enter. В Computer укажите IP, пользователь labuser, пароль - свой RDP из начальной установки, не пароль Windows. Не выбирайте сохранение credentials. Если появится синий login xrdp, выберите Session=Xorg и labuser.

```powershell
mstsc /prompt
```

**Ожидаемый результат и его смысл:** Открываются Xfce и Firefox внутри Ubuntu-бастиона. Это не браузер Windows. labuser не имеет sudo: настройку выполняйте через CloudShell → SSM/ssm-user.

**Если не получилось:** При Login failed проверьте имя и раскладку клавиатуры. Не отправляйте пароль в чат. При недоступности сверьте текущий IP и разрешённый CIDR с преподавателем; не открывайте 3389 для всех. Перед закрытием RDP сохраните работу.

## P1 Выдача статического файла по HTTP

### Что изучаем

Связать Nginx, файл, прослушивание порта, HTTP-ответ и access log.

### Задание

Файл /var/www/html/practice.txt на Web должен возвращать заданный текст с HTTP 200: локально, с бастиона и извне.

- File: /var/www/html/practice.txt
- URL path: /practice.txt

```text
JDU WEB-02 practice: HTTP response verified.
```

### Пример решения: выполняйте по одному шагу

#### P1.1 Установить Nginx из внутреннего APT

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** Подключитесь по SSM к Web как в P0 и проверьте role=web. Проверьте APT source: используется только подписанный repo 10.20.2.30. update получает индекс, install устанавливает пакет. Не добавляйте внешние источники.

```bash
cat /etc/apt/sources.list.d/jdu-web.sources
sudo apt-get update -o APT::Update::Error-Mode=any
sudo apt-get install --no-install-recommends nginx
```

**Ожидаемый результат и его смысл:** В source указаны внутренний IP и Signed-By; установка завершается без ошибки подписи. На запрос установки ответьте Y.

**Если не получилось:** При ошибке получения проверьте repo, его running/SSM и IP. Не обходите подпись через --allow-unauthenticated или внешний pip.

#### P1.2 Создать точный текст и права файла

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** Создайте текст через nano: одна точная строка, указанная ниже, с переводом строки в конце. Ctrl+O → Enter сохраняет, Ctrl+X закрывает редактор. install копирует файл; -o/-g задают владельца и группу, -m - права.

```bash
cd ~
mkdir -p jdu-web-practice/p1
cd jdu-web-practice/p1
pwd
nano practice.txt
# File content: JDU WEB-02 practice: HTTP response verified.
sudo install -o root -g root -m 0644 practice.txt /var/www/html/practice.txt
stat -c '%U:%G %a %n' /var/www/html/practice.txt
cat /var/www/html/practice.txt
```

**Ожидаемый результат и его смысл:** Ожидается root:root 644 и ровно строка JDU WEB-02 practice: HTTP response verified. Регистр, пробелы, точка и конечный перевод строки важны.

**Если не получилось:** Если вы ещё в nano, сначала сохраните и выйдите. Не меняйте существующий mission.txt.

#### P1.3 Проверить Web root и запустить сервис

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** Начальный сайт Ubuntu использует root /var/www/html. Через nginx -T найдите включённый /etc/nginx/sites-enabled/default, root и listen 80. При необходимости редактируйте sudo nano; reload выполняйте после успешной проверки. enable --now запускает сейчас и включает автозапуск.

```bash
sudo nginx -T
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
systemctl is-active nginx
sudo ss -lntp
```

**Ожидаемый результат и его смысл:** Ожидаются успешный синтаксис, active и слушатель вроде 0.0.0.0:80. Только 127.0.0.1:80 недоступен другим узлам.

**Если не получилось:** При ошибке используйте имя файла и строку из nginx -t. Изменение SG не исправит синтаксис.

#### P1.4 Посмотреть ответ на самом Web

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** curl - HTTP-клиент; -i показывает статус, заголовки и тело. 127.0.0.1 означает этот Web-сервер, не его public IP. Сравните ответ, а не только код завершения команды.

```bash
curl --noproxy '*' -i http://127.0.0.1/practice.txt
```

**Ожидаемый результат и его смысл:** HTTP 200 и заданный текст. При 404 проверяйте файл/root/URL; при connection refused - сервис и слушатель.

**Если не получилось:** При Welcome to nginx проверьте, что запросили /practice.txt, а не /.

#### P1.5 Проверить тот же файл с бастиона и извне

**Место выполнения:** SSM-терминал бастиона: ssm-user

**Цель и действия:** Выйдите из Web через exit, откройте SSM бастиона из CloudShell и запросите URL ниже. Затем exit возвращает в CloudShell; там запросите тот же путь командой curl -i по текущему public IPv4 Web из EC2. Не путайте private 10.20.1.20 с public IPv4.

```bash
curl --noproxy '*' -i http://10.20.1.20/practice.txt
```

**Ожидаемый результат и его смысл:** На обоих маршрутах 200 и одинаковый текст. HTTP 80 открыт, управляющий 8080 и DB 5432 не публикуются.

**Если не получилось:** Если внутренний запрос успешен, а внешний нет, проверьте текущий public IP и Lab. Не ослабляйте базовые SG.

#### P1.6 Связать запрос с журналом и отправить

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** Вернитесь на Web. В access log найдите время, IP клиента, путь и статус. Журнал доказывает обработку запроса, а не только наличие файла. Затем exit в CloudShell и запустите P1.

```bash
sudo tail -n 20 /var/log/nginx/access.log
exit
jdu-web-check P1 --no-submit
jdu-web-check P1
```

**Ожидаемый результат и его смысл:** Восемь учебных проверок PASS, готовность успешна и доставка STORED. P1 даёт 0 оценочных баллов; для M1 используются другой файл и текст.

**Если не получилось:** При PENDING повторно отправьте исходный request-id. Не меняйте ожидаемый текст в checker.

## P2 Внутренний DNS и системное разрешение имён

### Что изучаем

Последовательно настроить zone, A-записи, ACL BIND и resolver клиентов.

### Задание

Настройте guide.lab.test → 10.20.1.20 и practice-db.lab.test → 10.20.2.20; откройте HTTP из P1 по имени. Фиксированные IP не меняются.

| DNS name | A / IPv4 |
| --- | --- |
| guide.lab.test | 10.20.1.20 |
| practice-db.lab.test | 10.20.2.20 |

### Пример решения: выполняйте по одному шагу

#### P2.1 Установить BIND и сохранить исходные настройки

**Место выполнения:** SSM-терминал DNS-сервера: ssm-user

**Цель и действия:** Подключитесь к DNS, проверьте role=dns. cp -a сохраняет атрибуты исходного файла, -n не заменяет прежнюю копию. Это страховка при редактировании, не задание по backup/restore БД.

```bash
sudo apt-get update -o APT::Update::Error-Mode=any
sudo apt-get install --no-install-recommends bind9 bind9-utils
sudo cp -an /etc/bind/named.conf.options /etc/bind/named.conf.options.before-p2
sudo cp -an /etc/bind/named.conf.local /etc/bind/named.conf.local.before-p2
```

**Ожидаемый результат и его смысл:** Установка использует внутренний repo. В M2 добавляйте записи в этот же DNS, сохраняя P2.

**Если не получилось:** Не копируйте целиком named.conf из чужого Lab. Если своя zone уже есть, сначала изучите её.

#### P2.2 Настроить клиентов и forwarder

**Место выполнения:** SSM-терминал DNS-сервера: ssm-user

**Цель и действия:** Откройте sudo nano /etc/bind/named.conf.options, введите и сохраните текст ниже. acl задаёт разрешённых клиентов; listen-on - адреса DNS; forward only передаёт внешние имена AWS DNS. И query, и recursion ограничены тремя источниками. dnssec-validation no соответствует изолированной учебной схеме forwarding.

```text
acl "jdu_clients" { 127.0.0.1; 10.20.1.10; 10.20.1.20; };
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
};
```

**Ожидаемый результат и его смысл:** Это содержимое файла, не команды shell. 10.20.0.2 - resolver AWS, 10.20.2.10 - ваш BIND.

**Если не получилось:** Точки с запятой и фигурные скобки обязательны. Не расширяйте ACL до any или 0.0.0.0/0.

#### P2.3 Объявить zone и создать A-записи

**Место выполнения:** SSM-терминал DNS-сервера: ssm-user

**Цель и действия:** В sudo nano /etc/bind/named.conf.local запишите первый блок zone. Создайте каталог командой sudo install -d -m 0755 /etc/bind/zones, затем откройте sudo nano /etc/bind/zones/db.lab.test и запишите остальной текст. SOA - служебные данные, NS - авторитетный DNS, A - имя/IPv4. Точка в конце обозначает полное имя; увеличивайте serial при изменениях.

```text
// /etc/bind/named.conf.local
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
practice-db IN A 10.20.2.20
```

**Ожидаемый результат и его смысл:** Сохраните как два отдельных файла. Запись dns задаёт адрес имени NS. Resolver клиентов пока не меняйте.

**Если не получилось:** Если M2 уже настроен, добавьте две учебные записи, не заменяя zone. Не объявляйте zone дважды.

#### P2.4 Проверить синтаксис и локальный DNS-ответ

**Место выполнения:** SSM-терминал DNS-сервера: ssm-user

**Цель и действия:** Переключение клиентов на неисправный DNS нарушит разрешение имён. Сначала добейтесь успешных named-checkconf и named-checkzone, затем проверьте UDP и TCP.

```bash
sudo named-checkconf -z
sudo named-checkzone lab.test /etc/bind/zones/db.lab.test
sudo systemctl enable --now named
sudo systemctl restart named
dig @127.0.0.1 guide.lab.test A
dig @127.0.0.1 guide.lab.test A +tcp
```

**Ожидаемый результат и его смысл:** Ожидаются zone loaded/OK, NOERROR, флаг aa и A=10.20.1.20. aa означает авторитетный ответ этой zone.

**Если не получилось:** При ошибке изучите sudo journalctl -u named -n 30 --no-pager, исправьте конфигурацию и проверьте снова.

#### P2.5 Запросить DNS с бастиона и Web

**Место выполнения:** SSM-терминал бастиона: ssm-user

**Цель и действия:** Выполните команды и на бастионе, и на Web. @10.20.2.10 задаёт DNS только для данного запроса. Это ещё не доказывает, что браузер и приложение используют его по умолчанию.

```bash
dig @10.20.2.10 guide.lab.test A
dig @10.20.2.10 practice-db.lab.test A +tcp
dig @10.20.2.10 absent-p2.lab.test A
dig @10.20.2.10 aws.amazon.com A
dig @10.20.2.10 lab.test AXFR
```

**Ожидаемый результат и его смысл:** Нужные имена дают правильные A; absent-p2 - авторитетный NXDOMAIN; внешнее имя - ответ; AXFR запрещён. Таймаут не считается доказанным отказом.

**Если не получилось:** При недоступности различайте источник, UDP и TCP 53. Не добавляйте остальные private-узлы в ACL клиентов.

#### P2.6 Переключить системный resolver только на BIND

**Место выполнения:** SSM-терминал бастиона: ssm-user

**Цель и действия:** На бастионе и Web по одному узлу выполните ip -br link, затем networkctl status ИМЯ для определения интерфейса и Network File. Найдите его YAML через ls /etc/netplan и сохраните копию sudo cp -an. Через sudo nano добавьте к тому же интерфейсу dhcp4-overrides/use-dns:false и nameservers. Ниже схема: имя интерфейса и имеющиеся match/set-name/renderer сохраняйте из своего файла.

```text
network:
  version: 2
  ethernets:
    ens5:
      dhcp4: true
      dhcp4-overrides:
        use-dns: false
      nameservers:
        addresses: [10.20.2.10]
```

**Ожидаемый результат и его смысл:** DHCP сохраняет IP и gateway. Не добавляйте резервный DNS, не заменяйте /etc/resolv.conf и не прописывайте имена задания в /etc/hosts. Оставьте SSM открытым.

**Если не получилось:** Несколько YAML одного интерфейса объединяются. Если resolvectl dns показывает ещё AWS DNS, проверьте все соответствующие YAML и действующую конфигурацию.

#### P2.7 После применения проверить обычный resolver и HTTP

**Место выполнения:** SSM-терминал бастиона: ssm-user

**Цель и действия:** На бастионе и Web сначала создайте конфигурацию, затем примените и проверьте. Оставьте второе окно SSH/RDP; при разрыве вернитесь по SSM и сравните с сохранённой копией. Применяйте apply только после проверки файла и успешного generate.

```bash
sudo netplan generate
sudo netplan apply
sudo systemctl restart systemd-resolved
resolvectl dns
getent ahostsv4 guide.lab.test
getent ahostsv4 practice-db.lab.test
curl --noproxy '*' -i http://guide.lab.test/practice.txt
```

**Ожидаемый результат и его смысл:** Единственный upstream DNS - 10.20.2.10. getent выдаёт нужные IP, HTTP - 200 и текст P1. 127.0.0.53 - локальный stub; upstream смотрите в resolvectl.

**Если не получилось:** Если dig успешен, а getent нет, проверяйте resolver клиента. Сохраняйте настройку Firefox с отключённым DoH.

#### P2.8 Сравнить IP и имя в браузере, затем отправить

**Место выполнения:** Firefox на рабочем столе бастиона через RDP

**Цель и действия:** Откройте Firefox на бастионе через RDP. Сравните http://10.20.1.20/practice.txt и http://guide.lab.test/practice.txt. lab.test разрешается внутри бастиона, а не обычным DNS школьного PC. Затем запустите P2 в CloudShell.

```bash
jdu-web-check P2 --no-submit
jdu-web-check P2
```

**Ожидаемый результат и его смысл:** 13 учебных проверок; текущий P1 тоже должен работать. Перед DB/app добавьте шесть основных имён в M2.

**Если не получилось:** Не считайте любую ошибку имени остановкой HTTP: сравните IP → dig → getent → HTTP.

## P3 Данные при остановке и запуске

### Что изучаем

Проверить файл и права на исходном EBS; доказать сохранение после stop/start того же Web.

### Задание

Создайте marker P3 со своим анонимным Lab ID. Зафиксируйте состояние до остановки, stopped и после запуска. Дополнительный диск, mount и backup/restore не требуются.

- File: /var/lib/jdu-web/practice/storage.txt

```text
lab_id={lab_id}
task=P3
payload=practice-storage-2026
```

### Пример решения: выполняйте по одному шагу

#### P3.1 Проверить исходный диск и свободное место

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** findmnt показывает файловую систему, lsblk - диски и разделы, df -h - свободное место. Используйте предоставленный root EBS; имя /dev/nvme не является причиной менять диск.

```bash
findmnt -T /var/lib
lsblk -o NAME,TYPE,SIZE,MOUNTPOINTS,SERIAL
df -h /var/lib
cat /proc/sys/kernel/random/boot_id
```

**Ожидаемый результат и его смысл:** Соответствует исходному root volume; свободно не менее 20% и 2 GiB. Сохраните boot_id текущей загрузки.

**Если не получилось:** Недостаток места - проблема готовности. Не удаляйте другие материалы или диски ради баллов.

#### P3.2 Создать и разместить marker

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** Задайте LAB_ID и в этом терминале. printf завершает строки переводом строки. install задаёт directory 0755 и файл 0644/root:root. Сначала проверьте существующий файл; не заменяйте отличающееся содержимое без выяснения причины.

```bash
LAB_ID='YOUR-LAB-ID'
cd ~
mkdir -p jdu-web-practice/p3
cd jdu-web-practice/p3
printf 'lab_id=%s\ntask=P3\npayload=practice-storage-2026\n' "$LAB_ID" > storage.txt
cat storage.txt
sudo install -d -o root -g root -m 0755 /var/lib/jdu-web/practice
sudo install -o root -g root -m 0644 storage.txt /var/lib/jdu-web/practice/storage.txt
stat -c '%U:%G %a %n' /var/lib/jdu-web/practice /var/lib/jdu-web/practice/storage.txt
sha256sum /var/lib/jdu-web/practice/storage.txt
```

**Ожидаемый результат и его смысл:** Три строки с конечным переводом строки, права 0755/0644. Запишите hash. Права 777 не подходят.

**Если не получилось:** Не оставляйте YOUR-LAB-ID. Используйте анонимный Lab ID, не имя EC2 и не email.

#### P3.3 Сохранить доказательство до остановки

**Место выполнения:** CloudShell в личном AWS-аккаунте студента

**Цель и действия:** Выйдите из Web через exit в CloudShell. prepare-stop сохраняет instance/volume/hash marker/boot_id, но сам не останавливает EC2. Дождитесь успеха.

```bash
jdu-web-check P3 --prepare-stop
```

**Ожидаемый результат и его смысл:** Состояние до остановки сохранено. После этого marker не редактируйте.

**Если не получилось:** Остановка после неуспешной подготовки не даст полной цепочки доказательств. Сначала исправьте файл/права/SSM.

#### P3.4 Остановить тот же Web и зафиксировать stopped

**Место выполнения:** AWS Console своего студенческого аккаунта

**Цель и действия:** Повторно сверьте instance ID Web. Выберите Instance state → Stop instance и дождитесь stopped. Не Reboot и не Terminate. Не запуская узел, выполните команду ниже в CloudShell. Остальные четыре сервера оставьте включёнными.

```bash
jdu-web-check P3 --observe-stopped
```

**Ожидаемый результат и его смысл:** Записано stopped того же instance. Во время остановки недоступность HTTP/SSM ожидаема.

**Если не получилось:** При stopping подождите. Если запустили раньше наблюдения, цепочку из трёх этапов потребуется повторить.

#### P3.5 Запустить, сравнить данные и отправить

**Место выполнения:** AWS Console своего студенческого аккаунта

**Цель и действия:** Запустите тот же Web и дождитесь running/SSM Online. Через SSM проверьте текст/hash и boot_id. instance/volume/hash сохраняются, boot_id меняется. Затем запустите P3 из CloudShell.

```bash
jdu-web-check P3 --no-submit
jdu-web-check P3
```

**Ожидаемый результат и его смысл:** Три учебные проверки PASS. Если public IPv4 изменился, используйте новый адрес для внешнего HTTP.

**Если не получилось:** Новый instance не доказывает сохранение. Для P3/M3 нужны отдельные marker и доказательства.

## P4 Подключение к PostgreSQL с аутентификацией

### Что изучаем

Различать database, role и schema; выполнять SQL с Web по установленному паролю.

### Задание

Создайте jdu_catalog_practice, catalog_practice_setup и catalog_practice_app. Разрешите SCRAM только с Web 10.20.1.20/32. Таблицы приложения на этапе P4 не нужны.

- Profile: practice
- Database: jdu_catalog_practice
- Setup role: catalog_practice_setup
- Runtime role: catalog_practice_app
### Пример решения: выполняйте по одному шагу

#### P4.1 Установить PostgreSQL и распаковать учебный SQL

**Место выполнения:** SSM-терминал DB-сервера: ssm-user

**Цель и действия:** Подключитесь к DB по SSM, проверьте role=db. Cluster PostgreSQL 16 - единица работы сервера БД. Инструмент распаковки проверяет приложение и извлекает SQL; сам он не создаёт БД или роли.

```bash
sudo apt-get update -o APT::Update::Error-Mode=any
sudo apt-get install --no-install-recommends postgresql-16 postgresql-client-16
sudo python3 -B /var/lib/jdu-web/lesson-resources-r1/offline_assets.py
pg_lsclusters
sudo -u postgres psql -X -d postgres -c "SHOW data_directory;"
```

**Ожидаемый результат и его смысл:** Cluster 16/main, data directory /var/lib/postgresql/16/main. Учебный SQL находится в /var/lib/jdu-web/lesson-resources-r1/app/sql.

**Если не получилось:** Не удаляйте существующие БД и роли. Если уже настроено, изучите состояние и выполняйте только недостающие шаги.

#### P4.2 Настроить прослушивание и SCRAM

**Место выполнения:** SSM-терминал DB-сервера: ssm-user

**Цель и действия:** Сохраните postgresql.conf через sudo cp -an. В sudo nano /etc/postgresql/16/main/postgresql.conf задайте три значения ниже. Если параметр встречается несколько раз, проверьте действующее значение через SHOW. Слушать нужно только private IP БД на 5432; password_encryption определяет хранение новых паролей.

```text
listen_addresses = '10.20.2.20'
port = 5432
password_encryption = 'scram-sha-256'
```

**Ожидаемый результат и его смысл:** Не используйте * для всех адресов. Пароли задаются после настройки HBA и restart.

**Если не получилось:** Это текст postgresql.conf, не SQL. SG и адрес прослушивания ОС - разные средства контроля.

#### P4.3 Ограничить источник, database и role в HBA

**Место выполнения:** SSM-терминал DB-сервера: ssm-user

**Цель и действия:** Сохраните pg_hba.conf, затем в sudo nano /etc/postgresql/16/main/pg_hba.conf запишите правила ниже. Действует первая совпавшая строка, поэтому прежние широкие разрешения не оставляйте. Системный postgres управляет через Unix socket/peer. Роли будущего M4 перечислены отдельно; учебной роли доступ к основной БД не даётся.

```text
local all postgres peer
local all all reject
host jdu_catalog_practice catalog_practice_setup 10.20.1.20/32 scram-sha-256
host jdu_catalog_practice catalog_practice_app 10.20.1.20/32 scram-sha-256
host jdu_catalog catalog_setup 10.20.1.20/32 scram-sha-256
host jdu_catalog catalog_app 10.20.1.20/32 scram-sha-256
host all all 0.0.0.0/0 reject
host all all ::/0 reject
```

**Ожидаемый результат и его смысл:** Разрешение зависит от сочетания database/role/источник. Строка 0.0.0.0/0 содержит reject, то есть запрет.

**Если не получилось:** Не заменяйте метод на trust. Базовый SG также разрешает DB 5432 только с Web.

#### P4.4 Перезапустить и проверить действующие значения

**Место выполнения:** SSM-терминал DB-сервера: ssm-user

**Цель и действия:** restart перечитывает настройки. SHOW и pg_hba_file_rules проверяют действующие значения, а не только текст файла. Параметр psql -X отключает личные startup-файлы.

```bash
sudo systemctl restart postgresql@16-main
systemctl is-active postgresql@16-main
sudo ss -lntp
sudo -u postgres psql -X -d postgres -c "SHOW password_encryption;"
sudo -u postgres psql -X -d postgres -c \
  "SELECT line_number,error FROM pg_hba_file_rules WHERE error IS NOT NULL;"
```

**Ожидаемый результат и его смысл:** active, 10.20.2.20:5432, scram-sha-256, ошибок HBA - 0 строк.

**Если не получилось:** active(exited) у postgresql.service не доказывает работу cluster. Изучайте journalctl -u postgresql@16-main.

#### P4.5 Создать учебную БД и две роли

**Место выполнения:** SSM-терминал DB-сервера: ssm-user

**Цель и действия:** profile_sql.py только выводит фиксированный SQL с учебными именами. Сначала прочитайте вывод, затем передайте тот же текст psql. setup владеет БД/schema и создаёт таблицы; app используется приложением. Используйте предоставленный SQL: программировать приложение не требуется.

```bash
cd /var/lib/jdu-web/lesson-resources-r1/app
python3 -B profile_sql.py --profile practice 01_create_roles.sql
python3 -B profile_sql.py --profile practice 01_create_roles.sql | sudo -u postgres \
  psql -X -v ON_ERROR_STOP=1 -d postgres
python3 -B profile_sql.py --profile practice 02_prepare_schema.sql | sudo -u postgres \
  psql -X -v ON_ERROR_STOP=1 -d jdu_catalog_practice
```

**Ожидаемый результат и его смысл:** Два CREATE ROLE, CREATE DATABASE, права schema/CONNECT/USAGE. app не получает superuser/CREATEDB.

**Если не получилось:** При already exists возможен повторный запуск. Не используйте DROP; проверьте роли и БД через \du и \l. Убедитесь, что psql справа от pipe не сообщил SQL error.

#### P4.6 Задать два пароля БД скрытым вводом

**Место выполнения:** psql на DB-сервере от имени системного postgres

**Цель и действия:** Первая строка запускается в shell DB и открывает psql с postgres=#. Команды \password вводятся внутри psql. Для setup/app задайте разные пароли длиной от 16 символов, каждый дважды скрытым вводом. Не пишите значения в команду или отчёт. \q возвращает в shell DB.

```text
sudo -u postgres psql -X -d postgres
\password catalog_practice_setup
\password catalog_practice_app
\du catalog_practice_*
\q
```

**Ожидаемый результат и его смысл:** Нет Superuser/Create role/Create DB. Это отдельные секреты, не пароль RDP, не пароль администратора приложения и не token оценивания.

**Если не получилось:** Учитывайте раскладку клавиатуры. Не записывайте пароль в чат или редактор для проверки. При потере используйте личную процедуру восстановления с преподавателем.

#### P4.7 Выполнить SELECT с Web по паролю

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** Закройте SSM DB через exit, вернитесь в CloudShell и откройте Web. У psql -h задаёт узел, -U - роль, -d - БД, -W запрашивает пароль. P4 использует private IP, чтобы не добавлять зависимость от DNS.

```bash
sudo apt-get install --no-install-recommends postgresql-client-16
psql -X -h 10.20.2.20 -U catalog_practice_app -d jdu_catalog_practice -W -c \
  'SELECT current_database(),current_user,1 AS value;'
```

**Ожидаемый результат и его смысл:** Результат jdu_catalog_practice / catalog_practice_app / 1. Открытый порт или успех pg_isready не заменяют этот SQL с аутентификацией.

**Если не получилось:** При отказе раздельно проверьте источник, БД, роль и пароль. Не публикуйте DB в Internet для диагностики.

#### P4.8 Сохранить существующий пароль для checker только на Web

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** Инструмент дважды скрыто запрашивает существующий пароль catalog_practice_app и сохраняет его только на Web в root-файл 0600. Пароль БД не меняется. Не выводите env через cat и не выполняйте source. Затем exit в CloudShell и P4.

```bash
sudo python3 -B /var/lib/jdu-web/lesson-resources-r1/database_secret.py --profile \
  practice
exit
jdu-web-check P4 --no-submit
jdu-web-check P4
```

**Ожидаемый результат и его смысл:** Вывод D11_EXISTING_DB_PASSWORD_STORED_LOCALLY и девять учебных проверок. Неверный пароль и запрещённые DB/admin-role проверяются вместе с успешным контрольным подключением.

**Если не получилось:** Если файл уже есть, не создавайте заново. В P5 тот же пароль вводится в настройку приложения. M4 использует отдельные БД/роли mission.

## P5 Соединить предоставленное приложение с Web и DB

### Что изучаем

Без программирования связать offline-зависимости, сервисного пользователя, инициализацию БД, Nginx/systemd и реальный HTTP.

### Задание

Постройте каталог в profile practice. Нужны действующие DNS из M2 и P4. БД/администраторы P и M различны, но приложение и порты на том же Web общие.

- Profile: practice
- Database: jdu_catalog_practice
- Setup role: catalog_practice_setup
- Runtime role: catalog_practice_app
- Application administrator: practice_admin

| code | name | quantity | location | is_public |
| --- | --- | --- | --- | --- |
| P5-PUBLIC-001 | Practice keyboard | 4 | Training shelf A | true |
| P5-PRIVATE-001 | Practice mouse | 2 | Training shelf B | false |

### Пример решения: выполняйте по одному шагу

#### P5.1 Проверить DNS и получить открытые ресурсы

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** На Web обычный resolver должен дать db.lab.test=10.20.2.20 и admin.lab.test=10.20.1.20. offline_assets получает семь wheel и lock из внутреннего repo, сверяя исходную подпись/hash. Он не запускает внешний pip и не настраивает DB/app.

```bash
getent ahostsv4 db.lab.test
getent ahostsv4 admin.lab.test
sudo apt-get install --no-install-recommends python3-venv python3-pip
sudo python3 -B /var/lib/jdu-web/lesson-resources-r1/offline_assets.py --wheels
ls /var/lib/jdu-web/lesson-resources-r1/app
ls /var/lib/jdu-web/lesson-resources-r1/wheels
```

**Ожидаемый результат и его смысл:** PUBLIC_APP_RESOURCES_VERIFIED и SIGNED_OFFLINE_WHEELS_READY=7. Файлы приложения открытые и контролируются root.

**Если не получилось:** Нужно и имя db.lab.test, не только practice-db. P5 зависит от M2, но не требует завершения основных заданий по каталогу.

#### P5.2 Разместить код и создать отдельный venv

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** Код и venv контролирует root; пользователь catalog не должен их менять. Если app или venv уже существуют, не повторяйте создание - проверьте версию. cp переносит только проверенные открытые ресурсы. venv отделяет зависимости приложения от системного Python.

```bash
sudo install -d -o root -g root -m 0755 /opt/jdu-catalog/app
sudo cp -a /var/lib/jdu-web/lesson-resources-r1/app/. /opt/jdu-catalog/app/
sudo python3 -m venv /opt/jdu-catalog/venv
sudo /opt/jdu-catalog/venv/bin/python -m pip --isolated --no-cache-dir install \
  --no-index --find-links=/var/lib/jdu-web/lesson-resources-r1/wheels \
  --only-binary=:all: --require-hashes -r \
  /var/lib/jdu-web/lesson-resources-r1/requirements.lock
sudo /opt/jdu-catalog/venv/bin/python -m pip check
```

**Ожидаемый результат и его смысл:** --no-index запрещает внешний index; --require-hashes требует hash из lock. pip check не находит конфликтов.

**Если не получилось:** Недостающую зависимость решают через комплект преподавателя. Не обновляйте до latest через pip и не меняйте код приложения.

#### P5.3 Создать сервисного пользователя и каталог static

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** catalog предназначен для Gunicorn, не для входа человека. Создайте его с nologin и без sudo. Только каталог static принадлежит catalog для collectstatic; код/venv остаются root. Если catalog уже есть, проверьте id и shell вместо повторного useradd.

```bash
sudo useradd --system --user-group --home-dir /nonexistent --no-create-home --shell \
  /usr/sbin/nologin catalog
sudo install -d -o root -g root -m 0755 /var/lib/jdu-catalog
sudo install -d -o catalog -g catalog -m 0755 /var/lib/jdu-catalog/static
id catalog
getent passwd catalog
```

**Ожидаемый результат и его смысл:** catalog не входит в sudo, shell /usr/sbin/nologin. Это не labuser и не ssm-user.

**Если не получилось:** Не исправляйте права через chmod -R 777 или добавление catalog в sudo. Проверьте конкретный каталог и владельца.

#### P5.4 Создать runtime-настройки скрытым вводом

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** Подставьте текущий public IPv4 Web из EC2. Runtime-инструмент дважды запрашивает существующий пароль catalog_practice_app из P4. Django secret генерируется для вашего Lab. Создаются root-only app.env и profile practice; содержимое не выводится.

```bash
PUBLIC_WEB_IPV4='YOUR-CURRENT-WEB-PUBLIC-IP'
sudo python3 -B /opt/jdu-catalog/app/configuration.py create-runtime --profile \
  practice --public-web-ipv4 "$PUBLIC_WEB_IPV4"
sudo python3 -B /opt/jdu-catalog/app/configuration.py check --phase runtime
sudo stat -c '%U:%G %a %n' /etc/jdu-catalog/app.env
```

**Ожидаемый результат и его смысл:** CATALOG_ENV_CREATED=practice, VALID, root:root 600. Выбраны учебная БД и учебная app-role.

**Если не получилось:** Не вводите пароль RDP или администратора приложения. Не удаляйте существующий файл; для уже созданного используйте check.

#### P5.5 Создать таблицы и администратора через временный setup

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** В create-setup введите пароль catalog_practice_setup из P4. migrate создаёт предоставленную структуру БД; seed однократно добавляет три вымышленных образца в пустой каталог. create_lab_admin создаёт practice_admin со скрытым вводом пароля. Обычное приложение не работает через setup.

```bash
sudo python3 -B /opt/jdu-catalog/app/configuration.py create-setup --profile practice
sudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py \
  --phase setup check
sudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py \
  --phase setup migrate
sudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py \
  --phase setup seed_catalog
sudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py \
  --phase setup create_lab_admin
```

**Ожидаемый результат и его смысл:** Фиксированные 11 таблиц, три образца и staff-администратор без superuser. Операции выполняются с правами системного catalog.

**Если не получилось:** already exists при seed/admin защищает существующие данные. Не делайте reset; проверьте текущее состояние.

#### P5.6 Выдать runtime-роли необходимые SQL-права

**Место выполнения:** SSM-терминал DB-сервера: ssm-user

**Цель и действия:** Выйдите из Web в CloudShell и откройте DB через SSM. Прочитайте SQL03: после проверки 11 таблиц и владельцев он выдаёт права по таблицам, столбцам и sequence. Владение и ALL PRIVILEGES роли app не даются.

```bash
cd /var/lib/jdu-web/lesson-resources-r1/app
python3 -B profile_sql.py --profile practice 03_runtime_grants.sql
python3 -B profile_sql.py --profile practice 03_runtime_grants.sql | sudo -u postgres \
  psql -X -v ON_ERROR_STOP=1 -d jdu_catalog_practice
```

**Ожидаемый результат и его смысл:** Успех до COMMIT. catalog_item: SELECT/INSERT/UPDATE; auth_user: чтение и UPDATE только last_login/password; session и другие объекты - по назначению.

**Если не получилось:** Ошибка guard требует проверить migrations/owner. Не удаляйте защиту ради продолжения.

#### P5.7 Разместить static и unit systemd

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** Вернитесь на Web. collectstatic собирает CSS и другие ресурсы для Nginx. Разместите unit и выполните daemon-reload. Прочитайте User=catalog, EnvironmentFile и bind 127.0.0.1:8000.

```bash
sudo /opt/jdu-catalog/venv/bin/python -B /opt/jdu-catalog/app/manage_secure.py \
  --phase runtime collectstatic
cat /opt/jdu-catalog/app/config/jdu-catalog.service
sudo install -o root -g root -m 0644 /opt/jdu-catalog/app/config/jdu-catalog.service \
  /etc/systemd/system/jdu-catalog.service
sudo systemctl daemon-reload
sudo systemctl enable --now jdu-catalog
systemctl is-active jdu-catalog
sudo ss -lntp
```

**Ожидаемый результат и его смысл:** active; приложение слушает 8000 только на 127.0.0.1. Не публикуйте его через 0.0.0.0:8000.

**Если не получилось:** При ошибке смотрите journalctl -u jdu-catalog. Не копируйте env в журнал; формат проверяется configuration.py check.

#### P5.8 Разделить публичный и управляющий входы Nginx

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** Прочитайте conf: 80 - список, private8080 - только /admin/, upstream - 8000. Сохраните ссылку начального default site под другим именем и отключите её. Если jdu-catalog уже включён, проверьте состояние вместо повторных переносов. Статические URL P1/M1 сохраняются.

```bash
cat /opt/jdu-catalog/app/config/jdu-catalog.nginx.conf
sudo install -o root -g root -m 0644 \
  /opt/jdu-catalog/app/config/jdu-catalog.nginx.conf \
  /etc/nginx/sites-available/jdu-catalog
sudo mv -n /etc/nginx/sites-enabled/default /etc/nginx/default-site.before-p5
sudo ln -s /etc/nginx/sites-available/jdu-catalog /etc/nginx/sites-enabled/jdu-catalog
sudo nginx -t
sudo systemctl reload nginx
curl --noproxy '*' -i http://127.0.0.1/practice.txt
```

**Ожидаемый результат и его смысл:** Синтаксис успешен, practice.txt по-прежнему даёт 200. Публичный журнал теперь jdu-catalog-public.access.log.

**Если не получилось:** При duplicate default server проверьте старый site. До reload исправьте -t. Управляющий port не должен слушать public IP.

#### P5.9 Добавить две учебные записи через admin

**Место выполнения:** Firefox на рабочем столе бастиона через RDP

**Цель и действия:** В Firefox бастиона откройте http://admin.lab.test:8080/admin/, войдите как practice_admin со своим паролем приложения. Через Add добавьте две строки ниже с точными code/name/quantity/location. Is public включите только у публичной записи. На http://web.lab.test/ должна быть только публичная строка.

```text
P5-PUBLIC-001 | Practice keyboard | 4 | Training shelf A | is_public=true
P5-PRIVATE-001 | Practice mouse | 2 | Training shelf B | is_public=false
```

**Ожидаемый результат и его смысл:** Удалять три demo не нужно. Две заданные записи - обязательное подмножество; другие корректные публичные записи разрешены. Непубличная запись не видна в списке.

**Если не получилось:** Открывайте admin.lab.test в Firefox внутри RDP, не на школьном PC. При CSRF проверьте host/port/proxy.

#### P5.10 Прочитать реальные строки БД и сравнить с экраном

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** На Web выполните SELECT учебной app-role. Так проверяется, что сохранение из admin действительно дошло до PostgreSQL. Для этой проверки не нужны UPDATE/DELETE.

```bash
QUERY="SELECT code,name,quantity,location,is_public
FROM catalog_item
WHERE code IN ('P5-PUBLIC-001','P5-PRIVATE-001')
ORDER BY code;"
psql -X -h db.lab.test -U catalog_practice_app -d jdu_catalog_practice -W -c "$QUERY"
```

**Ожидаемый результат и его смысл:** Обе строки совпадают с заданием. Не подменяйте страницу фиксированным HTML при отказе БД.

**Если не получилось:** При permission denied проверьте profile и database SQL03. Не заменяйте обычную роль на superuser.

#### P5.11 Запустить функциональную проверку и отправить

**Место выполнения:** CloudShell в личном AWS-аккаунте студента

**Цель и действия:** Выйдите с Web и выполните в CloudShell. --functional открывает интерактивный SSM для скрытого ввода существующего пароля practice_admin. Автоматика выполняет обычный HTTP login, создаёт одну запись CK-P-, меняет её количество, сверяет DB/страницу и делает logout. Заданные две записи не меняются, проверочная остаётся. Личная демонстрация не требуется.

```bash
jdu-web-check P5 --functional
```

**Ожидаемый результат и его смысл:** Проверьте 13 учебных пунктов и доставку. Без пароля обычная проверка оставляет четыре функциональных пункта UNKNOWN. Результаты разных попыток не объединяются.

**Если не получилось:** При неверном пароле используйте правильный существующий, не создавайте новый. Новая проверка добавляет одну CK-запись; для повторной доставки используйте --retry.

## P6 Минимальные права и границы публикации

### Что изучаем

Сохранить штатную работу, запретив лишние admin-маршруты, SQL-права и раскрытие секретов.

### Задание

Используйте practice из P5. Отключите setup-role, уберите временную конфигурацию и проверьте отказы при наличии успешного контрольного login. Не расширяйте SG/IAM.

- Profile: practice
- Database: jdu_catalog_practice
- Setup role: catalog_practice_setup
- Runtime role: catalog_practice_app
- Application administrator: practice_admin

| code | name | quantity | location | is_public |
| --- | --- | --- | --- | --- |
| P5-PUBLIC-001 | Practice keyboard | 4 | Training shelf A | true |
| P5-PRIVATE-001 | Practice mouse | 2 | Training shelf B | false |

### Пример решения: выполняйте по одному шагу

#### P6.1 Прочитать роли и права таблиц

**Место выполнения:** psql на DB-сервере от имени системного postgres

**Цель и действия:** Откройте psql как postgres на DB. \dp показывает права таблиц, \du - атрибуты ролей. Сверьте с SQL03: UPDATE auth_user только last_login/password, без DELETE catalog_item; lookup только чтение, django_migrations без прав. Не вызывайте nextval/setval ради проверки.

```text
sudo -u postgres psql -X -d jdu_catalog_practice
\du catalog_practice_*
\dp public.*
\q
```

**Ожидаемый результат и его смысл:** Runtime не владелец и не superuser. DELETE для Django session нужен, но не означает право удаления оборудования.

**Если не получилось:** При лишних правах пересмотрите SQL03 с сохранением guard. Не пробуйте отказ удалением реальных строк.

#### P6.2 Отключить вход setup-роли

**Место выполнения:** SSM-терминал DB-сервера: ssm-user

**Цель и действия:** После инициализации вход setup не нужен. SQL04 задаёт NOLOGIN/password NULL и закрывает оставшиеся setup-подключения profile. Владельцем DB/table остаётся setup; роль не удаляется и владение app не передаётся.

```bash
cd /var/lib/jdu-web/lesson-resources-r1/app
python3 -B profile_sql.py --profile practice 04_disable_setup.sql
python3 -B profile_sql.py --profile practice 04_disable_setup.sql | sudo -u postgres \
  psql -X -v ON_ERROR_STOP=1 -d jdu_catalog_practice
```

**Ожидаемый результат и его смысл:** ALTER ROLE успешен, работа catalog_practice_app сохраняется.

**Если не получилось:** Не включайте setup обратно для обычной работы. M5 инициализируется отдельной setup-role mission.

#### P6.3 Удалить только временную конфигурацию setup

**Место выполнения:** SSM-терминал Web-сервера: ssm-user

**Цель и действия:** На Web проверьте только metadata. Удалите ровно два файла setup practice. app.env, practice.app.env, DB runtime, command-state, SSH-ключи и данные оценивания сохраняются. Содержимое секретных файлов через cat не выводится.

```bash
sudo stat -c '%U:%G %a %n' /etc/jdu-catalog/setup.env \
  /etc/jdu-catalog/profiles/practice.setup.env
sudo rm -- /etc/jdu-catalog/setup.env /etc/jdu-catalog/profiles/practice.setup.env
sudo stat -c '%U:%G %a %n' /etc/jdu-catalog/app.env \
  /etc/jdu-catalog/profiles/practice.app.env /etc/jdu-web/db-practice.runtime.env
sudo python3 -B /opt/jdu-catalog/app/configuration.py check --phase runtime
```

**Ожидаемый результат и его смысл:** Runtime-файлы root:root 600, check успешен. Если setup-файлы уже удалены, пропустите удаление.

**Если не получилось:** Если setup относится к другому profile, остановитесь. Не используйте wildcard или rm -r для всего каталога.

#### P6.4 Проверить запрет admin и секретов на публичном 80

**Место выполнения:** SSM-терминал бастиона: ssm-user

**Цель и действия:** В SSM бастиона запросите обычный список на 80, затем /admin/ и env. Отдельно подтвердите штатный admin на 8080 в Firefox через RDP. Нужны нормальный ответ и явный отказ 404/403; таймаута недостаточно.

```bash
curl --noproxy '*' -i http://web.lab.test/
curl --noproxy '*' -i http://web.lab.test/admin/
curl --noproxy '*' -i http://web.lab.test/app.env
curl --noproxy '*' -i http://web.lab.test/static/app.env
```

**Ожидаемый результат и его смысл:** Список - 200; admin/env отклоняются без секретов. Публичный Nginx перезаписывает X-JDU-Entry и не допускает подмену входа.

**Если не получилось:** Если виден текст env, не распространяйте его: сообщите преподавателю и исправьте публикацию.

#### P6.5 Отправить успешный вход и отказы в одной проверке

**Место выполнения:** CloudShell в личном AWS-аккаунте студента

**Цель и действия:** P6 --functional использует успешный login practice_admin как контроль и проверяет, что анонимные операции и неверный пароль отклоняются без изменения БД. Один 403 из-за CSRF не доказывает авторизацию. Staff имеет только view/add/change оборудования, без delete и управления пользователями.

```bash
jdu-web-check P6 --functional
jdu-web-my-progress
```

**Ожидаемый результат и его смысл:** 16 учебных пунктов. Личный URL прогресса открывайте только сами. P не даёт оценочных баллов; M6 проверяется отдельно в mission.

**Если не получилось:** PENDING повторно отправляется с исходным request-id; причину UNKNOWN нужно устранить и измерить заново. Не редактируйте grade-файлы.

## Продолжение и повторная отправка

На следующем занятии запустите свой Lab и те же пять узлов, проверьте running/SSM Online и текущие public IP. В CloudShell заново задайте LAB_ID/COURSE_ID/INSTALL, прочитайте activate.sh как в P0 и выполните M0 --no-submit. Не повторяйте создание/ключи/регистрацию; при истечении срока запросите обновление.

STORED означает приём преподавателем. Для PENDING используйте исходный request-id и то же задание с --retry. --no-submit не является отправкой. UNKNOWN - измерение невозможно, а не автоматический ноль или успех. Оно не удаляет прежнюю оцениваемую попытку, но не доказывает текущую готовность. Используется последняя полностью оцениваемая попытка, не максимальная и не сумма PASS разных запусков.

```bash
jdu-web-check M2 --retry 'YOUR-ORIGINAL-REQUEST-ID'
jdu-web-my-progress
```

Личный URL открывайте только сами. Не отправляйте в отчёт или чат пароль/token/cookie/ключ/env/URL преподавателя. Снимки не должны содержать секретов. Не проверяйте ошибки на чужом Lab.

## Источники и версия

Критерии основаны на фиксированном registry и таблицах M. Текст сверен с принятой реализацией, но новый студент ещё не прошёл эти подробные шаги с нуля. Ещё нужны приёмка успешного ручного ввода пароля и stop/start всех пяти узлов после установки приложения. Редактирование пособия не делает CLASS_READY=true.

Версии: web-course-class193548-20261023-r2; web-d11-2026-10-r1; registry SHA256 3feeb3d8a9225e6e19e06f68367b07c6cb4a657f05818c146ccb22cfcd654c33.

Подпись действует до 2026-10-27 14:24:57 UZT. Срок URL загрузки отличается от срока подписи; не меняйте даты для обхода. Ниже первичные документы общих функций, проверенные 2026-10-23. IP, задания и баллы Lab определены этим курсом.

- [Nginx Beginner’s Guide](https://nginx.org/en/docs/beginners_guide.html)
- [BIND 9: configurations and zones](https://bind9.readthedocs.io/en/v9.18.39/chapter3.html)
- [PostgreSQL 16: pg_hba.conf](https://www.postgresql.org/docs/16/auth-pg-hba-conf.html)
- [EC2 instance states](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)
