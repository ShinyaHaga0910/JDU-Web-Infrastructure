# Web Infrastructure: M0-M6 mustaqil topshiriqlar

2026-10-23 | D12 P/M r1 | web-course-class193548-20261023-r2

O‘qituvchi tekshiruvi uchun birinchi nashr. Talabaning qo‘llanma bo‘yicha boshidan oxirigacha o‘tishi hali tekshirilmagan.

Ruscha va o‘zbekcha matn yaponcha asl nusxa bilan bir xil qadam va shartlarga ega. Ona tili mutaxassisi tahriri hali bajarilmagan.

[日本語](../ja/missions.md) · [Русский](../ru/missions.md) · [O‘zbekcha](../uz/missions.md)

## Qo‘llanmadan foydalanish

Avval P topshirig‘ini o‘qing; kerak bo‘lsa batafsil namunani qadam-baqadam bajaring. P - bahoga ball qo‘shmaydigan mashq. M da boshqa obyekt/qiymatni mustaqil quring. Topshiriq raqami dars raqami emas; o‘z sur’atingizda ishlang. P tugashi M bajarilganini anglatmaydi.

P0 → M0 → P1 → M1 → P2 → M2 → P3 → M3 → P4 → M4 → P5 → P6 → M5 → M6

P5 uchun ham M2 DNS kerak. P4 IP bilan ulanadi, app esa db.lab.test dan foydalanadi. Practice → mission almashishdan oldin P6 da setup ni tugating. P ixtiyoriy mashq; checker M ning joriy old shartlarini tekshiradi.

M1=8, M2=13, M3=3, M4=9, M5=13, M6=16: jami 62 xom ball. M0=0. Shaxsiy namoyish, backup/restore, qo‘shimcha disk va app dasturlash talab qilinmaydi. 25 ballga o‘tkazishni o‘qituvchi alohida qiladi. E’lon qilingan muddatgacha qayta yuborish mumkin. Turli urinish PASS lari qo‘shilmaydi; eng yuqori ball avtomatik tanlanmaydi.

## Muhit va tayyorgarlik

Avval boshlang‘ich tarqatma imzosi, yangi beshta server yoki mavjud muhitga install, ichki SSH va shaxsiy ro‘yxatni tugating. Yo‘riqnoma zip dagi distribution/STUDENT.md da. Maxfiy kalitni umumiy Windows ga saqlamang; shaxsiy Academy hisobining CloudShell idan foydalaning. O‘qituvchi anonim Lab ID, fingerprint va muddatni beradi.

Umumiy private IP quyida; public IPv4 doimiy emas. AWS region us-east-1, Ubuntu24.04/amd64. RDP: labuser; SSM: ssm-user; ichki SSH: ubuntu. User nomi va server rolini adashtirmang.

| Role | Private IPv4 | Vazifa |
| --- | --- | --- |
| bastion | 10.20.1.10 | RDP3389 / Firefox / SSH |
| web | 10.20.1.20 | HTTP80 / private8080 / loopback8000 |
| dns | 10.20.2.10 | BIND UDP/TCP53 |
| db | 10.20.2.20 | PostgreSQL5432 |
| repo | 10.20.2.30 | Oldindan saqlangan imzolangan resurslar HTTP80 |

Har Ubuntu ga kirish uchun CloudShell da aws ssm start-session --target i-OZ-ID bajaring. Darhol id -un va bootstrap.json dagi role ni tekshiring. Server almashtirishda bitta exit bilan CloudShell ga qaytib keyingi ID ga ulang. CloudShell o‘zgaruvchilari serverga avtomatik ko‘chmaydi. ssm-user sudo qila oladi; RDP labuser sudo admin emas.

Nano: faylni ochish → matn yozish → Ctrl+O → Enter bilan saqlash → Ctrl+X bilan chiqish. Sozlama bloki shell buyrug‘i emas. Psql ichida prompt o‘zgaradi; SQL/\password shu yerga yoziladi, \q Ubuntu ga qaytaradi. Xatodan keyin natijani tekshirmay davom etmang.

## M0 Shaxsiy muhit va buyruqlarni bajarish joyi (0)

### Tayyor holat talablari

Beshta rol, asl instance, SSM/ichki SSH va shaxsiy ro‘yxat mosligini tekshiring. 0 ball. P0 ga qarang; asosni qayta yaratmang.

### Tekshirish va yuborish

```bash
jdu-web-check M0 --no-submit
jdu-web-check M0
```

## M1 HTTP orqali statik faylni qaytarish (8)

### Tayyor holat talablari

P1 ko‘nikmasi bilan belgilangan boshqa fayl va matnni mustaqil tarqating. practice.txt ni saqlang. Fayl, service, listen, local/bastion/public HTTP va joriy so‘rov log i tekshiriladi.

- File: /var/www/html/mission.txt
- URL path: /mission.txt

```text
JDU WEB-02 mission: independent HTTP delivery.
```

### Shartlar: har tekshiruvga 1 xom ball

| check ID (o‘zgartirmang) | Shart |
| --- | --- |
| WEB02_NGINX_ACTIVE | Nginx ishlaydi (active). |
| WEB02_CONFIG_VALID | nginx -t sozlamani muvaffaqiyatli tekshiradi. |
| WEB02_LISTEN_80 | 80 port private IP/barcha interface da tinglaydi, faqat loopback emas. |
| WEB02_FILE | Oddiy faylda aniq matn bor, egasi root:root, ruxsat 0644. |
| WEB02_LOCAL_HTTP | Web loopback orqali HTTP 200 va aniq matn oladi. |
| WEB02_BASTION_HTTP | Bastion private IP orqali HTTP 200 va aniq matn oladi. |
| WEB02_PUBLIC_HTTP | CloudShell public IP orqali HTTP 200 va aniq matn oladi. |
| WEB02_ACCESS_LOG | Access log aynan shu tekshiruv nonce li so‘rovni saqlaydi. |

Identity/boshqaruv/repo/tarmoq/bog‘liqlik tayyorlik tekshiruvlari ball qo‘shmaydi. Old shart ishlamasa, qisman ball keyingi bosqichga tayyorlik emas.

### Tekshirish va yuborish

```bash
jdu-web-check M1 --no-submit
jdu-web-check M1
```

## M2 Ichki DNS va odatiy nom yechimi (13)

### Tayyor holat talablari

Ayni lab.test zone ga oltita asosiy nomni qo‘shing. guide/practice-db qolishi mumkin. Bastion/Web odatiy resolver, nom orqali M1 HTTP, DB nomi, UDP/TCP, forwarding, NXDOMAIN, ACL va AXFR rad etilishi kerak.

| DNS name | A / IPv4 |
| --- | --- |
| admin.lab.test | 10.20.1.20 |
| bastion.lab.test | 10.20.1.10 |
| db.lab.test | 10.20.2.20 |
| dns.lab.test | 10.20.2.10 |
| repo.lab.test | 10.20.2.30 |
| web.lab.test | 10.20.1.20 |

- Joriy old shartlar: M1

### Shartlar: har tekshiruvga 1 xom ball

| check ID (o‘zgartirmang) | Shart |
| --- | --- |
| WEB03_SERVICE | BIND/named ishlaydi (active). |
| WEB03_CONFIG_VALID | Named va lab.test zone tekshiruvlari muvaffaqiyatli. |
| WEB03_ZONE_AUTHORITY | Lab.test SOA/NS va vakolatli javob tuzilmaga mos; NS - dns.lab.test. |
| WEB03_REQUIRED_RECORDS | Profile dagi barcha A record kerakli private IP beradi; bu bitta band. |
| WEB03_UDP_RESPONSE | Bastion ham, Web ham UDP 53 orqali to‘g‘ri javob oladi. |
| WEB03_TCP_RESPONSE | Bastion ham, Web ham TCP 53 orqali to‘g‘ri javob oladi. |
| WEB03_NORMAL_RESOLVER | Bastion/Web odatiy resolver faqat BIND dan foydalanadi; hosts yoki Firefox DoH bilan almashtirilmaydi. |
| WEB03_NAMED_HTTP | Bastiondan profile nomi va belgilangan path orqali HTTP 200 hamda to‘g‘ri matn qaytadi. |
| WEB03_DB_NAME | Web odatiy resolver profile DB nomini 10.20.2.20 ga yechadi. |
| WEB03_FORWARD_ONLY | Forward only faqat 10.20.0.2 ga yo‘naltirilgan; tashqi DNS nomi yechiladi. Tashqi HTTP shart emas. |
| WEB03_NXDOMAIN | Shu ishga tushirishdagi yangi mavjud bo‘lmagan nom vakolatli NXDOMAIN oladi. |
| WEB03_CLIENT_ACL | BIND query/recursion/cache faqat localhost, bastion va Web ga ruxsat; SG ning o‘zi yetmaydi. |
| WEB03_AXFR_DENIED | Ayni tekshiruv oddiy so‘rovlari o‘tgan holda bastion/Web AXFR aniq rad etiladi; timeout yetmaydi. |

Identity/boshqaruv/repo/tarmoq/bog‘liqlik tayyorlik tekshiruvlari ball qo‘shmaydi. Old shart ishlamasa, qisman ball keyingi bosqichga tayyorlik emas.

### Tekshirish va yuborish

```bash
jdu-web-check M2 --no-submit
jdu-web-check M2
```

## M3 To‘xtatish va qayta ishga tushirishda ma’lumotlar (3)

### Tayyor holat talablari

O‘z Lab ID bilan alohida M marker yarating. P3 dan alohida prepare-stop → AWS Stop → observe-stopped → AWS Start → M3 ketma-ketligini bajaring. Ayni Web va asl root volume kerak; oddiy reboot yetmaydi. Backup/restore va yangi disk kerak emas.

- File: /var/lib/jdu-web/mission/storage.txt

```text
lab_id={lab_id}
task=M3
payload=mission-storage-2026
```

{lab_id} ni o‘z anonim ID ga almashtiring. Fayl 0644/root:root, katalog 0755/root:root. Faqat ayni asl Web/volume ni to‘xtating.

### Shartlar: har tekshiruvga 1 xom ball

| check ID (o‘zgartirmang) | Shart |
| --- | --- |
| WEB04_MARKER_CONTENT | Marker path, shaxsiy Lab ID, task va aniq matn topshiriqqa mos. |
| WEB04_MARKER_PERMISSIONS | Fayl root:root 0644, ota katalog root:root 0755. |
| WEB04_STOP_START_RETENTION | Stop/start uch bosqichi isbotlangan: ayni instance/volume/hash, yangi boot_id va alohida kuzatilgan stopped. |

Identity/boshqaruv/repo/tarmoq/bog‘liqlik tayyorlik tekshiruvlari ball qo‘shmaydi. Old shart ishlamasa, qisman ball keyingi bosqichga tayyorlik emas.

### Tekshirish va yuborish

```bash
jdu-web-check M3 --no-submit
jdu-web-check M3
```

## M4 PostgreSQL ga autentifikatsiya bilan ulanish (9)

### Tayyor holat talablari

Asosiy DB va rollarni mustaqil quring. M2 db.lab.test ni odatiy resolver bilan yechib Web runtime role orqali SELECT bajaring. HBA faqat Web/32 va to‘g‘ri DB/role juftiga ruxsat beradi. Mavjud parolni Web mission helper orqali practice dan alohida saqlang. App jadvallari hali kerak emas.

- Profile: mission
- Database: jdu_catalog
- Setup role: catalog_setup
- Runtime role: catalog_app
- Joriy old shartlar: M2

### Shartlar: har tekshiruvga 1 xom ball

| check ID (o‘zgartirmang) | Shart |
| --- | --- |
| WEB05_CLUSTER_ACTIVE | PostgreSQL 16/main ishlaydi (active). |
| WEB05_CLUSTER_CONFIG | 16/main sozlamasi, standart data directory va OS postgres socket/peer to‘g‘ri. |
| WEB05_LISTEN_5432 | PostgreSQL 10.20.2.20:5432 da tinglaydi. |
| WEB05_DATABASE_OWNER | DB va public schema egasi tegishli setup role. |
| WEB05_ROLE_ATTRIBUTES | Runtime LOGIN; superuser/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS va huquq oshiruvchi membership yo‘q. Setup qurishda LOGIN yoki tugagach NOLOGIN. |
| WEB05_HBA_SCRAM | HBA faqat ko‘rsatilgan DB/role va Web /32 uchun SCRAM ga ruxsat beradi; keng ruxsat yo‘q. |
| WEB05_WEB_SQL | Web dan yangi autentifikatsiyali SELECT kerakli DB/user/qiymatni qaytaradi; P IP bilan, M odatiy DNS orqali. |
| WEB05_BAD_PASSWORD_DENIED | To‘g‘ri parol ishlagan ayni tekshiruvda bitta noto‘g‘ri parol aniq rad etiladi. |
| WEB05_WRONG_TARGET_DENIED | Web dan postgres role, begona DB va boshqa profile taqiqlangan; hali yaratilmagan practice DB majburiy emas. |

Identity/boshqaruv/repo/tarmoq/bog‘liqlik tayyorlik tekshiruvlari ball qo‘shmaydi. Old shart ishlamasa, qisman ball keyingi bosqichga tayyorlik emas.

### Tekshirish va yuborish

```bash
jdu-web-check M4 --no-submit
jdu-web-check M4
```

## M5 Berilgan app ni Web va DB bilan bog‘lash (13)

### Tayyor holat talablari

Ayni app ni mission DB ga ulang. P5 ko‘nikmasi bilan profile=mission tanlang, app/venv ni qayta joylamang. Service ni to‘xtatib: mission runtime yaratish → aniq activate → mission setup yaratish; practice setup P6 da tugatilgan bo‘lsin. Asosiy DB da migrations/seed/admin va grants ni bajaring, ikkita belgilangan yozuvni kiriting. P1/M1 ni saqlab mission ni active qoldiring.

- Profile: mission
- Database: jdu_catalog
- Setup role: catalog_setup
- Runtime role: catalog_app
- Application administrator: lab_admin

| code | name | quantity | location | is_public |
| --- | --- | --- | --- | --- |
| M5-PUBLIC-001 | Mission monitor | 6 | Lab cabinet C | true |
| M5-PRIVATE-001 | Mission router | 1 | Lab cabinet D | false |

- Joriy old shartlar: M2, M4

### Shartlar: har tekshiruvga 1 xom ball

| check ID (o‘zgartirmang) | Shart |
| --- | --- |
| WEB06_ARTIFACTS | Kod va bog‘liqliklar berilgan aniq versiyaga mos. |
| WEB06_SERVICE | jdu-catalog active va enabled, catalog nomidan ishlaydi. |
| WEB06_LOOPBACK | Gunicorn faqat 127.0.0.1:8000 da tinglaydi. |
| WEB06_PROFILE_DATABASE | Faol process kerakli profile DB va runtime role dan foydalanadi. |
| WEB06_MIGRATIONS | Belgilangan migrations, 11 jadval va zarur sequence tanlangan DB da mavjud. |
| WEB06_REQUIRED_RECORDS | Ikkala majburiy yozuv profile qiymatlariga mos; boshqa to‘g‘ri yozuvlar mumkin. |
| WEB06_PUBLIC_DATA | Odatiy ochiq URL ishlayotgan DB dan to‘g‘ri yozuvlarni oladi. |
| WEB06_ADMIN_ENTRY | Bastiondan odatiy DNS orqali admin.lab.test:8080/admin/ haqiqiy login shakli ochiladi. |
| WEB06_STATIC | Static resurslar belgilangan yo‘l orqali ochiladi. |
| WEB06_PASSWORD_LOGIN | Funksional rejim haqiqiy password/CSRF/cookie login dan o‘tadi, autentifikatsiya chetlab o‘tilmaydi. |
| WEB06_CREATE_REFLECT | Shu tekshiruvda admin HTTP orqali bitta CK yozuv yaratilib, DB va ochiq sahifa qiymatlari mos keladi. |
| WEB06_EDIT_REFLECT | Aynan shu CK yozuv miqdori o‘zgartiriladi; DB va ochiq sahifa o‘zgarishni tasdiqlaydi. |
| WEB06_LOGOUT | POST logout session ni tugatadi: eski cookie bilan yana login talab etiladi. |

Identity/boshqaruv/repo/tarmoq/bog‘liqlik tayyorlik tekshiruvlari ball qo‘shmaydi. Old shart ishlamasa, qisman ball keyingi bosqichga tayyorlik emas.

### Tekshirish va yuborish

```bash
jdu-web-check M5 --functional
# STORED / PENDING: inspect delivery result
```

## M6 Eng kam huquq va ochiq kirish chegarasi (16)

### Tayyor holat talablari

Mission eng kam huquqini tugating: catalog_setup NOLOGIN/password NULL, vaqtinchalik setup fayllari qolmasin. Root kod/venv, 600 maxfiy fayl, 80 da admin rad etilishi, private8080 muvaffaqiyati, admin faqat view/add/change, ochiq/yopiq ma’lumot va SQL huquqlarini tekshiring. --functional shaxsiy namoyish emas, avtomatik tekshiruv.

- Profile: mission
- Database: jdu_catalog
- Setup role: catalog_setup
- Runtime role: catalog_app
- Application administrator: lab_admin

| code | name | quantity | location | is_public |
| --- | --- | --- | --- | --- |
| M5-PUBLIC-001 | Mission monitor | 6 | Lab cabinet C | true |
| M5-PRIVATE-001 | Mission router | 1 | Lab cabinet D | false |

- Joriy old shartlar: M5

### Shartlar: har tekshiruvga 1 xom ball

| check ID (o‘zgartirmang) | Shart |
| --- | --- |
| WEB07_PUBLIC_ADMIN_DENIED | Ochiq 80 soxta Host/header bilan ham admin ni ochmaydi; private yo‘l esa ishlaydi. |
| WEB07_SECRET_PERMISSIONS | Maxfiy fayllar oddiy root:root 0600, link va qiymat ochilishi yo‘q. |
| WEB07_CODE_PROTECTED | Login/sudo siz catalog kod, venv va ularning boshqaruv kataloglarini o‘zgartira olmaydi. |
| WEB07_SECRET_HTTP_DENIED | Tekshiriladigan env/maxfiy path lar HTTP yoki static orqali ochilmaydi. |
| WEB07_SETUP_RETIRED | Setup role NOLOGIN/password NULL, session lari yopilgan, vaqtinchalik setup.env lar o‘chirilgan. |
| WEB07_ITEM_PRIVILEGES | catalog_item: faqat SELECT/INSERT/UPDATE; DELETE, TRUNCATE va huquq uzatish yo‘q. |
| WEB07_AUTH_USER_PRIVILEGES | auth_user: SELECT va faqat last_login/password UPDATE; user yaratish/o‘chirish yo‘q. |
| WEB07_AUTH_LOOKUP_PRIVILEGES | Guruh, permission, bog‘lanish va content type jadvallari faqat SELECT uchun. |
| WEB07_SESSION_PRIVILEGES | django_session: faqat kerakli SELECT/INSERT/UPDATE/DELETE; ortiqcha huquq yo‘q. |
| WEB07_AUDIT_PRIVILEGES | django_admin_log: faqat SELECT/INSERT. |
| WEB07_MIGRATION_PRIVILEGES | Runtime da django_migrations huquqi, schema CREATE, obyekt egaligi va belgilanmagan qo‘shimcha huquq yo‘q. |
| WEB07_SEQUENCE_PRIVILEGES | USAGE faqat jihoz va admin-log sequence lariga; ortiqcha SELECT/UPDATE/GRANT yo‘q. |
| WEB07_ADMIN_PERMISSIONS | Faol staff, superuser emas: faqat jihoz view/add/change; delete/user management yo‘q. |
| WEB07_ANONYMOUS_DENIED | Nazorat login o‘tgan holda anonim add/change DB ni o‘zgartirmay rad etiladi; faqat CSRF-403 yetmaydi. |
| WEB07_BAD_PASSWORD_DENIED | Bitta noto‘g‘ri app paroli rad etiladi, ayni paytda to‘g‘ri login ishlaydi. |
| WEB07_PRIVATE_DATA_HIDDEN | DB ishlagan holda topilgan barcha yopiq kodlar ochiq sahifada ko‘rinmaydi. |

Identity/boshqaruv/repo/tarmoq/bog‘liqlik tayyorlik tekshiruvlari ball qo‘shmaydi. Old shart ishlamasa, qisman ball keyingi bosqichga tayyorlik emas.

### Tekshirish va yuborish

```bash
jdu-web-check M6 --functional
# STORED / PENDING: inspect delivery result
```

## Davom ettirish va qayta yuborish

Keyingi safar shaxsiy Lab va ayni besh serverni ishga tushirib running/SSM Online hamda joriy public IP ni tekshiring. CloudShell da LAB_ID/COURSE_ID/INSTALL ni qayta belgilang, P0 dagi activate.sh ni o‘qing va M0 --no-submit bajaring. Yaratish/kalit/ro‘yxatni takrorlamang; muddat o‘tsa yangilashni so‘rang.

STORED - o‘qituvchi qabul qilgan. PENDING bo‘lsa asl request-id va ayni topshiriq bilan --retry ishlating. --no-submit yuborish emas. UNKNOWN - o‘lchab bo‘lmagan, avtomatik nol yoki muvaffaqiyat emas. U oldingi baholanadigan urinishni o‘chirmaydi, lekin hozir tayyorlikni isbotlamaydi. Oxirgi to‘liq baholanadigan urinish olinadi; maksimum yoki turli urinish PASS yig‘indisi emas.

```bash
jdu-web-check M2 --retry 'YOUR-ORIGINAL-REQUEST-ID'
jdu-web-my-progress
```

Shaxsiy URL ni faqat o‘zingiz oching. Hisobot/chat ga parol/token/cookie/kalit/env/o‘qituvchi URL ini yubormang. Screenshot da maxfiy maydon bo‘lmasin. Xatoni boshqa talaba Lab ida sinamang.

## Manbalar va versiya

Shartlar belgilangan registry va M jadvallariga asoslangan. Matn qabul qilingan amalga oshirish bilan solishtirildi, ammo yangi talaba bu batafsil qadamlarni boshidan hali bajarmagan. To‘g‘ri parolni shaxsan kiritish va app o‘rnatilgach besh server stop/start qabul tekshiruvi qolgan. Qo‘llanma tahriri CLASS_READY=true degani emas.

Versiyalar: web-course-class193548-20261023-r2; web-d11-2026-10-r1; registry SHA256 3feeb3d8a9225e6e19e06f68367b07c6cb4a657f05818c146ccb22cfcd654c33.

Imzo muddati: 2026-10-27 14:24:57 UZT. Yuklash URL muddati imzo muddatidan farq qiladi; chetlab o‘tish uchun sanani o‘zgartirmang. Quyida 2026-10-23 tekshirilgan umumiy funksiyalarning birlamchi hujjatlari. Lab IP, topshiriq va ballari ushbu kurs tomonidan belgilanadi.

- [Nginx Beginner’s Guide](https://nginx.org/en/docs/beginners_guide.html)
- [BIND 9: configurations and zones](https://bind9.readthedocs.io/en/v9.18.39/chapter3.html)
- [PostgreSQL 16: pg_hba.conf](https://www.postgresql.org/docs/16/auth-pg-hba-conf.html)
- [EC2 instance states](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)
