# Web Infrastructure: P0-P6 mashqlar va batafsil qadamlar

2026-10-23 | D12 P/M r1.1 | web-course-class193548-20261023-r2

O‘qituvchi tekshiruvi uchun birinchi nashr. Talabaning qo‘llanma bo‘yicha boshidan oxirigacha o‘tishi hali tekshirilmagan.

Ruscha va o‘zbekcha matn yaponcha asl nusxa bilan bir xil qadam va shartlarga ega. Ona tili mutaxassisi tahriri hali bajarilmagan.

[日本語](../ja/practice.md) · [Русский](../ru/practice.md) · [O‘zbekcha](../uz/practice.md)

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

## Qadamlarni qanday o‘qish kerak

Har P da topshiriq, tushuntirish, qadamlar va savollar bor. Butun bo‘limni birdan joylamang: har command ni alohida bajarib natijani o‘qing. Qator oxiridagi backslash davom etishni bildiradi: keyingi qator ham shu command ning qismidir.

Bash blokini ko‘rsatilgan muhit terminaliga kiriting. Text bloki config matni, psql ichidagi kiritish yoki natija namunasi bo‘lishi mumkin; oldingi izohni o‘qing. # bilan boshlangan izoh comment hisoblanadi. Terminaldagi $ yoki postgres=# prompt ini command ga qo‘shmang. YOUR- qiymatlarini o‘zingiznikiga almashtiring.

Tekshirish tartibi: saqlangan fayl, sintaksis, service ga qo‘llash, haqiqiy ulanish. To‘g‘ri fayl ishlayotgan service yangi sozlamani ishlatayotganini hali isbotlamaydi. HTTP response, DNS answer yoki SQL natijasini log bilan solishtiring.

## Tayyor tizim va ulanish yo‘llari

| Manba | Manzil | Protocol / port | Maqsad |
| --- | --- | --- | --- |
| Windows PC | Web public IPv4 | TCP/80 | Internet Gateway orqali ochiq ro‘yxat va statik fayllarni ko‘rish. |
| Windows PC | bastion public IPv4 | TCP/3389 | Ruxsatli CIDR dan RDP bilan bastion ish stoliga kirish. |
| bastion | Web/DNS/DB/repo | TCP/22 | Boshqarish uchun ichki SSH; private key bastion ichida qoladi. |
| bastion / Web | DNS 10.20.2.10 | UDP+TCP/53 | lab.test nomlarini yechish. DNS Web sahifa mazmunini qaytarmaydi. |
| Web app | DB 10.20.2.20 | TCP/5432 | App DB role bilan SQL bajaradi. Windows dan DB ga bevosita ulanish ishlatilmaydi. |
| bastion | Web 10.20.1.20 | TCP/8080 | admin.lab.test admin oynasi; ochiq 80 portdan alohida. |
| Nginx on Web | 127.0.0.1 on Web | TCP/8000 | Shu Web ichidagi app ga uzatish; 127.0.0.1 - ayni joriy host. |

Boshlang‘ich SSM CloudShell dan EC2 ga alohida management yo‘lidir. U oddiy Web request yo‘liga qo‘shilmaydi. Jadvaldagi ichki IP va portlar shu Lab uchun, barcha Web tizimlari uchun emas.

## P0 Shaxsiy muhit va buyruqlarni bajarish joyi

### Nimani o‘rganamiz

CloudShell, Windows va beshta Ubuntu serverni farqlash; kerakli serverga SSM orqali kirish va o‘zini tekshirish.

### Topshiriq

Lab ID, tarqatma ID va beshta rolning instance ID qiymatlarini tekshiring. Bu tayyor muhit tekshiruvi, 0 ball. Besh server hali bo‘lmasa, avval boshlang‘ich o‘rnatishni tugating. Tayyor muhit uchun create, kalit yaratish va ro‘yxatdan o‘tishni takrorlamang.

### Bu qanday ishlaydi

**Boshlashdan oldingi holat:** Boshlang‘ich tarqatma va ro‘yxat tugagan shaxsiy besh server ishlatiladi.

**Ushbu P da nima o‘zgaradi:** Account, role va ish joyini farqlaysiz; ochiq o‘quv resurslari tayyorlanadi.

AWS Console resurslarni boshqaradi; CloudShell - AWS CLI bor shaxsiy terminal; SSM tanlangan EC2 OS ichida session ochadi. Besh server alohida OS bo‘lib qoladi: Web dagi /var/www DB dagi katalog bilan bir joy emas. Server role va OS user ni alohida tekshiring.

### Yechim namunasi: bittadan bajaring

#### P0.1 Shaxsiy CloudShell ichida tarqatmani faollashtirish

**Bajarish joyi:** Talabaning shaxsiy AWS hisobidagi CloudShell

**Maqsad va amallar:** Academy dagi o‘z Class’ingizdan AWS ni, keyin CloudShell ni oching. Dastlabki ikki qatordagi qiymatlarni o‘qituvchi bergan qiymatlarga almashtiring. Dollar belgisi o‘zgaruvchiga murojaat bo‘lib, buyruqning bir qismidir. activate.sh yangi tekshiruvchi katalogini PATH ga qo‘shadi.

```bash
LAB_ID='YOUR-LAB-ID'
COURSE_ID='web-course-class193548-20261023-r2'
INSTALL="$HOME/.local/share/jdu-web/courses/$COURSE_ID/$LAB_ID"
source "$INSTALL/activate.sh"
aws sts get-caller-identity --query Account --output text
command -v jdu-web-check
jdu-web-check --help
```

**Buyruq va sozlamalar ma’nosi:** LAB_ID va COURSE_ID joriy terminal o‘zgaruvchilaridir. INSTALL ulardan path hosil qiladi; qo‘shtirnoq qiymatni bir butun saqlaydi. Source sozlamani joriy shell ga o‘qiydi; command -v qaysi command ishlashini ko‘rsatadi.

**Kutilgan natija va ma’nosi:** Account sizniki bo‘lishi, buyruq yo‘lida sizning COURSE_ID va LAB_ID bo‘lishi kerak. Yordamda P0-P6/M0-M6 ko‘rinadi.

**Ishlamasa:** No such file chiqsa, boshlang‘ich o‘rnatish va install ni tekshiring. Eski buyruq barcha topshiriqlarni qo‘llamaydi. Muddati o‘tgan tarqatmani o‘qituvchi yangilaydi.

#### P0.2 Beshta serverning instance ID qiymatini yozib olish

**Bajarish joyi:** Talabaning shaxsiy AWS Console oynasi

**Maqsad va amallar:** EC2 → Instances ro‘yxatida LabId va DeploymentId teglarini solishtiring. bastion/web/dns/db/repo uchun instance ID ni ish jadvaliga yozing. Faqat nomiga qarab tanlamang. Public IPv4 bastion va web da mavjud. SSM uchun public IP emas, instance ID kerak.

**Buyruq va sozlamalar ma’nosi:** Instance ID EC2 ni aniqlaydi; role vazifani, public IP tashqi manzilni bildiradi. Public IP o‘zgarishi instance ID almashganini anglatmaydi. Ish jadvalida besh role ni o‘z ID si bilan bog‘lang.

**Kutilgan natija va ma’nosi:** Beshala server running, SSM Online; private IP umumiy jadvalga mos. To‘xtatib ishga tushirganda public IPv4 o‘zgarishi mumkin.

**Ishlamasa:** Boshqa Lab, hisob yoki noma’lum serverni o‘zgartirmang. To‘xtagan server uchun ishga tushirish yo‘riqnomasidan foydalaning. Reset yoki Terminate ni bosmang.

#### P0.3 SSM orqali kirish va qaytish

**Bajarish joyi:** Talabaning shaxsiy AWS hisobidagi CloudShell

**Maqsad va amallar:** EC2 dagi Web instance ID ni kiriting. Ulanishdan keyin CloudShell emas, Ubuntu terminalida ishlaysiz. id -un SSM foydalanuvchisini, bootstrap.json dagi role server vazifasini ko‘rsatadi. Bitta exit CloudShell ga qaytaradi.

```bash
aws ssm start-session --target i-YOUR-WEB-INSTANCE-ID
id -un
hostname
python3 -c 'import json;print(json.load(open("/etc/jdu-web/bootstrap.json"))["role"])'
pwd
exit
```

**Buyruq va sozlamalar ma’nosi:** Avval faqat start-session ni CloudShell da bajarib ulanishni kuting. So‘ng qolgan qatorlarni bittadan kiriting. Id -un user ni, hostname OS host nomini, role o‘quv vazifasini ko‘rsatadi. Exit session ning bir pog‘onasidan qaytaradi.

**Kutilgan natija va ma’nosi:** ssm-user va web ko‘rinadi. Har safar serverni almashtirganda tekshiring. SSH orqali kirganda Ubuntu foydalanuvchisi ubuntu bo‘lishi mumkin.

**Ishlamasa:** TargetNotConnected bo‘lsa, running, SSM Online va us-east-1 ni tekshiring. SG portlarini to‘liq ochmang, Windows ga kalit yuklamang.

#### P0.4 Faqat ochiq o‘quv fayllarini tayyorlash

**Bajarish joyi:** Talabaning shaxsiy AWS hisobidagi CloudShell

**Maqsad va amallar:** Ushbu qo‘llanma zip faylini CloudShell → Actions → Upload file orqali yuklang; unzip web-lab-pm-r1.zip bilan oching. resources katalogiga o‘ting va buyruqni bajaring. Yordamchi shaxsiy imzolangan tarqatma va asl besh serverni tekshirib, Web/DB ga ochiq app, SQL va yashirin kiritish vositasini joylaydi. Service yoki DB qurmaydi, maxfiy qiymat yubormaydi.

```bash
cd "$HOME/web-lab-pm-r1/resources"
python3 -B stage_resources.py --installation "$INSTALL"
```

**Buyruq va sozlamalar ma’nosi:** Ochiq resurslar app va SQL materiallaridir, tayyor service emas. Stage_resources.py CloudShell da ishga tushib ularni Web/DB ga joylaydi. Zip ni Windows ga saqlashning o‘zi EC2 da fayl yaratmaydi.

**Kutilgan natija va ma’nosi:** PUBLIC_LESSON_RESOURCES_READY=web va =db chiqadi. Ochiq fayllar /var/lib/jdu-web/lesson-resources-r1 da. Mavjud boshqa mazmunli fayl ustiga yozilmaydi.

**Ishlamasa:** Boshlang‘ich o‘rnatish tugamagan, versiya boshqa yoki muddat o‘tgan bo‘lsa, to‘xtab o‘qituvchiga ayting. Tayyor yechim quradigan test fixture bilan almashtirmang.

#### P0.5 O‘zini tekshirish va yuborishni farqlash

**Bajarish joyi:** Talabaning shaxsiy AWS hisobidagi CloudShell

**Maqsad va amallar:** Tekshiruvchi joriy holatni kuzatadi. --no-submit faqat o‘zini tekshirish bo‘lib, natija o‘qituvchiga yuborilmaydi. Oddiy ishga tushirish oraliq natijani ham yuboradi. P0/M0 tayyorlikni tekshiradi, bahoga ball qo‘shmaydi.

```bash
jdu-web-check P0 --no-submit
jdu-web-check P0
jdu-web-check M0 --no-submit
```

**Buyruq va sozlamalar ma’nosi:** Tekshiruv va yuborish ikki xil natija. --no-submit bilan PASS bo‘lishi shu urinishni o‘qituvchiga saqlamaydi. PENDING yetkazilganini tasdiqlash yo‘qligini bildiradi, ball o‘zgarishini emas.

**Kutilgan natija va ma’nosi:** Tayyorlik/complete va yuborish holatini alohida o‘qing. STORED - qabul qilingan; PENDING - yuborilmagan; UNKNOWN - tekshirib bo‘lmagan holat.

**Ishlamasa:** Yordam uchun check ID, vaqt va server rolini yozing. Token, parol va shaxsiy URL ni ulashmang.

#### P0.6 RDP orqali bastion ish stolini ochish

**Bajarish joyi:** Talabaning Windows PC si (umumiy hisob)

**Maqsad va amallar:** EC2 dagi hozirgi bastion public IPv4 ni ishlating. Windows+R ni bosib mstsc /prompt kiriting va Enter bosing. Computer ga IP, user ga labuser, parolga boshlang‘ich o‘rnatishda belgilangan shaxsiy RDP parolini kiriting; Windows paroli emas. Credentials ni saqlashni tanlamang. Ko‘k xrdp login chiqsa Session=Xorg va labuser ni tekshiring.

```powershell
mstsc /prompt
```

**Buyruq va sozlamalar ma’nosi:** RDP bastion ekrani va kiritishni uzatadi. RDP ichidagi Firefox request i Windows emas, bastiondan chiqadi. Klaviatura tartibi paroldagi belgilarga ta’sir qiladi; interfeys tili va keyboard layout alohida sozlamadir.

**Kutilgan natija va ma’nosi:** Ubuntu bastion ichida Xfce va Firefox ochiladi; bu Windows browser idan boshqa. labuser da sudo yo‘q: qurishni CloudShell → SSM/ssm-user orqali bajaring.

**Ishlamasa:** Login failed bo‘lsa user nomi va klaviatura tartibini tekshiring. Parolni chat ga yubormang. Ulanmasa joriy IP va ruxsatli CIDR ni o‘qituvchi bilan tekshiring; 3389 ni hammaga ochmang. RDP ni yopishdan oldin ishni saqlang.

### Tushunishni tekshirish (ballsiz)

Web SSM session ichida DB qadamlarini kiritsangiz, qaysi server o‘zgaradi?

**Izoh:** Joriy Web o‘zgaradi. Exit bilan CloudShell ga qaytib DB instance ID ga qayta ulaning.

## P1 HTTP orqali statik faylni qaytarish

### Nimani o‘rganamiz

Nginx, fayl joyi, tinglash porti, HTTP javobi va access log ni bog‘lash.

### Topshiriq

Web dagi /var/www/html/practice.txt belgilangan matnni HTTP 200 bilan qaytarsin: Web ichidan, bastiondan va tashqaridan tekshiring.

- File: /var/www/html/practice.txt
- URL path: /practice.txt

```text
JDU WEB-02 practice: HTTP response verified.
```

### Bu qanday ishlaydi

**Boshlashdan oldingi holat:** Web yaratilgan, ammo mashq fayli hali qaytarilmayapti.

**Ushbu P da nima o‘zgaradi:** Nginx 80 portda practice.txt qaytarib, request ni log ga yozadi.

URL dagi /practice.txt Web ichidagi /var/www/html/practice.txt ga mos. 127.0.0.1 orqali muvaffaqiyat faqat Web ichini tekshiradi. Ayni matnni bastion va Windows dan o‘qish yo‘lning boshqa qismlarini tekshiradi. [Nginx hujjati](https://nginx.org/en/docs/beginners_guide.html).

### Yechim namunasi: bittadan bajaring

#### P1.1 Ichki APT dan Nginx o‘rnatish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** P0 dagidek Web ga SSM orqali kiring va role=web ni tekshiring. APT source faqat 10.20.2.30 dagi imzolangan repo ekanini ko‘ring. update indeksni oladi, install paketni o‘rnatadi. Internet source qo‘shmang.

```bash
cat /etc/apt/sources.list.d/jdu-web.sources
sudo apt-get update -o APT::Update::Error-Mode=any
sudo apt-get install --no-install-recommends nginx
```

**Buyruq va sozlamalar ma’nosi:** Apt-get update package ro‘yxatini yangilaydi; install tanlangan package ni o‘rnatadi. --no-install-recommends tavsiya etilgan qo‘shimchalarni o‘rnatmaydi. Signed-By ishonchli kalitni belgilaydi: repo ga ulanish imzo tekshirilganini hali isbotlamaydi.

**Kutilgan natija va ma’nosi:** Source ichida ichki IP va Signed-By bor; imzo xatosisiz tugaydi. O‘rnatish tasdig‘iga Y kiriting.

**Ishlamasa:** Yuklash xatosida repo running/SSM va IP ni tekshiring. --allow-unauthenticated yoki tashqi pip bilan chetlab o‘tmang.

#### P1.2 Aniq matn yaratish va ruxsatlarni sozlash

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** nano da quyida ko‘rsatilgan bitta aniq qatorni yarating va oxiriga yangi qator qo‘ying. Ctrl+O → Enter saqlaydi, Ctrl+X yopadi. install faylni joylaydi; -o/-g egasi va guruhni, -m ruxsatni belgilaydi.

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

**Buyruq va sozlamalar ma’nosi:** Nano dagi ish fayli va Nginx o‘qiydigan faylni ajrating. Bu yerda install package o‘rnatmaydi: faylni root:root va 0644 bilan nusxalaydi. Faqat owner yozadi, boshqalar o‘qiydi. Oxirgi newline ham mazmunning qismidir.

**Kutilgan natija va ma’nosi:** root:root 644 va aynan JDU WEB-02 practice: HTTP response verified. qatori chiqadi. Harf registri, bo‘shliq, nuqta va oxirgi yangi qator muhim.

**Ishlamasa:** Hali nano ichida bo‘lsangiz, avval saqlab chiqing. Mavjud mission.txt ni o‘zgartirmang.

#### P1.3 Web root ni tekshirish va service ni ishga tushirish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** Ubuntu boshlang‘ich sayti root sifatida /var/www/html dan foydalanadi. nginx -T da /etc/nginx/sites-enabled/default, root va listen 80 ni toping. Kerak bo‘lsa sudo nano bilan tahrirlang; tekshiruvdan keyin reload qiling. enable --now hozir ishga tushiradi va keyingi OS yuklanishiga yoqadi.

```bash
sudo nginx -T
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
systemctl is-active nginx
sudo ss -lntp
```

**Buyruq va sozlamalar ma’nosi:** Nginx -T config ni ko‘rsatadi; -t sintaksisni tekshiradi. Systemctl enable keyingi boot da ishga tushishni, --now hozir ishga tushishni belgilaydi. Fayl saqlangach reload, service holati va portni tekshiring.

**Kutilgan natija va ma’nosi:** Sintaksis muvaffaqiyatli, active va 0.0.0.0:80 kabi tinglash bor. Faqat 127.0.0.1:80 bo‘lsa, boshqa server foydalana olmaydi.

**Ishlamasa:** Xatoda nginx -t ko‘rsatgan fayl va qatorni tuzating. SG ni o‘zgartirish sintaksis xatosini tuzatmaydi.

#### P1.4 Web ichidan javobni ko‘rish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** curl HTTP client; -i status, header va body ni ko‘rsatadi. 127.0.0.1 shu Web serverning o‘zi, public IP emas. Faqat buyruq tugaganini emas, javobni solishtiring.

```bash
curl --noproxy '*' -i http://127.0.0.1/practice.txt
```

**Buyruq va sozlamalar ma’nosi:** Curl -i body bilan HTTP header ni ham ko‘rsatadi. 127.0.0.1 ayni Web bo‘lib, request Internetdan o‘tmaydi. 200 kodi bilan belgilangan matnni birga tekshiring; boshqa sahifaning 200 javobi mos emas.

**Kutilgan natija va ma’nosi:** HTTP 200 va belgilangan matn. 404 bo‘lsa fayl/root/URL, connection refused bo‘lsa service va tinglashni tekshiring.

**Ishlamasa:** Welcome to nginx chiqsa, / emas, /practice.txt so‘ralganini tekshiring.

#### P1.5 Bastiondan va tashqaridan shu faylni tekshirish

**Bajarish joyi:** Bastionning SSM terminali: ssm-user

**Maqsad va amallar:** Web dan exit bilan chiqing, CloudShell dan bastion SSM terminalini ochib quyidagi URL ni so‘rang. Keyin exit bilan CloudShell ga qayting; EC2 dagi hozirgi Web public IPv4 orqali shu path ni curl -i bilan so‘rang. 10.20.1.20 private IP va public IPv4 ni adashtirmang.

```bash
curl --noproxy '*' -i http://10.20.1.20/practice.txt
```

**Buyruq va sozlamalar ma’nosi:** Ayni curl bastiondan bajarilsa ichki yo‘l tekshiriladi. Windows browser ida Web ning joriy public IP si kerak. Windows dan 10.20.1.20 ga yetib bo‘lmasligi Web to‘xtaganini anglatmaydi.

**Kutilgan natija va ma’nosi:** Ikkala yo‘lda ham 200 va bir xil matn. HTTP 80 ochiq, boshqaruv 8080 va DB 5432 tashqariga ochilmaydi.

**Ishlamasa:** Ichki so‘rov o‘tib tashqi so‘rov o‘tmasa, public IP va Lab holatini tekshiring. Asosiy SG ni o‘zboshimchalik bilan kengaytirmang.

#### P1.6 So‘rovni log bilan bog‘lash va yuborish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** Web ga qayting. access log da vaqt, client IP, path va statusni toping. Log faqat fayl borligini emas, so‘rov ishlanganini ko‘rsatadi. Keyin exit bilan CloudShell ga qaytib P1 ni bajaring.

```bash
sudo tail -n 20 /var/log/nginx/access.log
exit
jdu-web-check P1 --no-submit
jdu-web-check P1
```

**Buyruq va sozlamalar ma’nosi:** Access log dagi vaqt, request path va status ni oldingi curl bilan solishtiring. Tail oxirgi qatorlarni o‘qiydi, log ni o‘zgartirmaydi. Exit dan keyin checker ni CloudShell da bajaring, Web ga ko‘chirmang.

**Kutilgan natija va ma’nosi:** Sakkizta mashq tekshiruvi PASS, tayyorlik muvaffaqiyatli va yuborish STORED. P1 bahoga 0 ball; M1 uchun boshqa fayl va matn ishlatiladi.

**Ishlamasa:** PENDING bo‘lsa, berilgan request-id bilan qayta yuboring. Checker dagi kutilgan matnni o‘zgartirmang.

### Natijani o‘qish namunasi (kiritmang)

```text
HTTP/1.1 200 OK

JDU WEB-02 practice: HTTP response verified.
```

Faqat kerakli qatorlar ko‘rsatilgan; haqiqiy javobda boshqa header lar ham bor. 200, matn va access log dagi path/status ni tekshiring.

### Tushunishni tekshirish (ballsiz)

Web ichida 200, bastiondan ulanish ishlamaydi. Faylni qayta yozishdan oldin nimani tekshirasiz?

**Izoh:** Manzil IP, listen address/port va bastion → Web ruxsatini tekshiring. Fayl mazmuni va yetib borish alohida tekshiruvdir.

## P2 Ichki DNS va odatiy nom yechimi

### Nimani o‘rganamiz

BIND zone, A record, ACL va client resolver ni ketma-ket sozlash.

### Topshiriq

guide.lab.test → 10.20.1.20 va practice-db.lab.test → 10.20.2.20 ni sozlang; P1 HTTP ni nom orqali oching. Asosiy IP lar o‘zgarmaydi.

| DNS name | A / IPv4 |
| --- | --- |
| guide.lab.test | 10.20.1.20 |
| practice-db.lab.test | 10.20.2.20 |

### Bu qanday ishlaydi

**Boshlashdan oldingi holat:** P1 HTTP IP orqali ishlaydi; DNS endi sozlanadi.

**Ushbu P da nima o‘zgaradi:** BIND mashq nomlari bastion va Web ning oddiy resolver idan ishlaydi.

DNS nom so‘roviga javob beradi, Web sahifani qaytarmaydi. BIND lab.test zone ni boshqaradi; A record IPv4 qaytaradi. Aniq DNS server bilan dig va OS sozlamalaridan foydalanuvchi getent/browser ni farqlang. DNS dan keyin alohida HTTP ulanish bo‘ladi. [BIND hujjati](https://bind9.readthedocs.io/en/v9.18.39/chapter3.html).

### Yechim namunasi: bittadan bajaring

#### P2.1 BIND o‘rnatish va asl sozlamani saqlash

**Bajarish joyi:** DNS serverning SSM terminali: ssm-user

**Maqsad va amallar:** DNS ga kirib role=dns ni tekshiring. cp -a asl fayl atributlarini saqlaydi; -n eski nusxa ustiga yozmaydi. Bu tahrir xatosi uchun nusxa, DB backup/restore topshirig‘i emas.

```bash
sudo apt-get update -o APT::Update::Error-Mode=any
sudo apt-get install --no-install-recommends bind9 bind9-utils
sudo cp -an /etc/bind/named.conf.options /etc/bind/named.conf.options.before-p2
sudo cp -an /etc/bind/named.conf.local /etc/bind/named.conf.local.before-p2
```

**Buyruq va sozlamalar ma’nosi:** Named - BIND service nomi; named-checkconf kabi vositalar config ni tekshiradi. Cp -an dagi -n takroriy bajarishda mavjud zaxira nusxa ustiga yozmaydi.

**Kutilgan natija va ma’nosi:** Ichki repo dan o‘rnatiladi. M2 da shu DNS ga record qo‘shilib, P2 record lari saqlanadi.

**Ishlamasa:** Boshqa Lab named.conf faylini to‘liq ko‘chirmang. O‘zingizning zone mavjud bo‘lsa, avval o‘qing.

#### P2.2 Client lar va forwarder ni sozlash

**Bajarish joyi:** DNS serverning SSM terminali: ssm-user

**Maqsad va amallar:** sudo nano /etc/bind/named.conf.options ni ochib quyidagi matnni saqlang. acl ruxsatli client larni, listen-on DNS tinglashini belgilaydi; forward only tashqi nomlarni AWS DNS ga uzatadi. Query va recursion uchta manbaga cheklanadi. dnssec-validation no yopiq o‘quv forwarding tuzilmasiga mos.

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

**Buyruq va sozlamalar ma’nosi:** Allow-query so‘rov yuboruvchi client ni, allow-recursion tashqi nom uchun recursive qidiruv client ini belgilaydi. Lab.test o‘z zone idan, tashqi nom forwarder orqali olinadi. Client lar bastion, Web va localhost bilan cheklangan.

**Kutilgan natija va ma’nosi:** Bu shell buyrug‘i emas, fayl mazmuni. 10.20.0.2 - AWS resolver, 10.20.2.10 - o‘z BIND serveringiz.

**Ishlamasa:** Nuqtali vergul va qavslar sintaksis qismidir. ACL ni any yoki 0.0.0.0/0 gacha kengaytirmang.

#### P2.3 Zone ni e’lon qilish va A record yozish

**Bajarish joyi:** DNS serverning SSM terminali: ssm-user

**Maqsad va amallar:** sudo nano /etc/bind/named.conf.local ga birinchi zone blokini yozing. sudo install -d -m 0755 /etc/bind/zones dan so‘ng sudo nano /etc/bind/zones/db.lab.test ga qolgan matnni yozing. SOA boshqaruv ma’lumoti, NS vakolatli DNS, A nom/IPv4 mosligi. Oxirgi nuqta to‘liq nomni bildiradi; har tahrirda serial ni oshiring.

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

**Buyruq va sozlamalar ma’nosi:** Zone e’loni va record lar alohida fayllarga saqlanadi. Guide nomi guide.lab.test gacha to‘ldiriladi; nuqtali dns.lab.test. to‘liq nomdir. TTL cache vaqtini, SOA serial esa zone versiyasini bildiradi, IP ni emas.

**Kutilgan natija va ma’nosi:** Ikkita alohida faylga saqlang. dns A yozuvi NS nomining manzilidir. Client resolver ini hozircha o‘zgartirmang.

**Ishlamasa:** M2 allaqachon mavjud bo‘lsa, zone ni almashtirmay ikkita mashq yozuvini qo‘shing. Zone ni ikki marta e’lon qilmang.

#### P2.4 Sintaksis va DNS ichki javobini tekshirish

**Bajarish joyi:** DNS serverning SSM terminali: ssm-user

**Maqsad va amallar:** Client ni nosoz DNS ga o‘tkazish nom yechimini to‘xtatadi. Avval named-checkconf va named-checkzone muvaffaqiyatli bo‘lsin, keyin UDP hamda TCP ni tekshiring.

```bash
sudo named-checkconf -z
sudo named-checkzone lab.test /etc/bind/zones/db.lab.test
sudo systemctl enable --now named
sudo systemctl restart named
dig @127.0.0.1 guide.lab.test A
dig @127.0.0.1 guide.lab.test A +tcp
```

**Buyruq va sozlamalar ma’nosi:** Sintaksis tekshiruvi o‘tgach sozlamani qo‘llang. Dig dagi @ DNS serverni, A IPv4 record turini bildiradi. +tcp bilan TCP53 tekshiriladi; uni UDP muvaffaqiyatidan alohida o‘qing.

**Kutilgan natija va ma’nosi:** zone loaded/OK, NOERROR, aa va A=10.20.1.20. aa shu zone uchun vakolatli javobni bildiradi.

**Ishlamasa:** Xatoda sudo journalctl -u named -n 30 --no-pager ni o‘qing, sozlamani tuzatib yana tekshiring.

#### P2.5 Bastion va Web dan DNS ga bevosita so‘rov yuborish

**Bajarish joyi:** Bastionning SSM terminali: ssm-user

**Maqsad va amallar:** Buyruqlarni bastionda ham, Web da ham bajaring. @10.20.2.10 faqat shu so‘rov uchun DNS ni belgilaydi. Bu browser va app odatda shu DNS ni ishlatishini hali isbotlamaydi.

```bash
dig @10.20.2.10 guide.lab.test A
dig @10.20.2.10 practice-db.lab.test A +tcp
dig @10.20.2.10 absent-p2.lab.test A
dig @10.20.2.10 aws.amazon.com A
dig @10.20.2.10 lab.test AXFR
```

**Buyruq va sozlamalar ma’nosi:** Mavjud ichki nom, yo‘q nom, tashqi nom va zone transfer ni alohida sinang. NXDOMAIN to‘g‘ri manfiy javob, timeout emas. AXFR butun zone ni so‘raydi; bu Lab da rad etilishi kerak.

**Kutilgan natija va ma’nosi:** Kerakli nomlar to‘g‘ri A qaytaradi; absent-p2 vakolatli NXDOMAIN, tashqi nom javob beradi; AXFR rad qilinadi. Timeout aniq rad etish isboti emas.

**Ishlamasa:** Ulanmasa, manba hamda UDP/TCP 53 ni ajratib tekshiring. Boshqa private serverlarni client ACL ga qo‘shmang.

#### P2.6 Odatiy resolver ni faqat BIND ga yo‘naltirish

**Bajarish joyi:** Bastionning SSM terminali: ssm-user

**Maqsad va amallar:** Bastion va Web da bittadan bajaring. ip -br link orqali interface nomini, networkctl status NOM orqali Network File ni aniqlang. ls /etc/netplan bilan YAML ni topib sudo cp -an orqali nusxa saqlang. sudo nano da ayni interface ga dhcp4-overrides/use-dns:false va nameservers qo‘shing. Quyida tuzilma namunasi: interface nomi hamda mavjud match/set-name/renderer qiymatlarini saqlang.

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

**Buyruq va sozlamalar ma’nosi:** Bu Netplan DNS serverga emas, client bo‘lgan bastion va Web ga yoziladi. Dhcp4 IP olishni davom ettiradi; use-dns: false DHCP DNS ni olishni to‘xtatadi. Addresses dagi DNS manzili EC2 ning o‘z IP si emas.

**Kutilgan natija va ma’nosi:** IP va gateway DHCP da qoladi. Boshqa fallback DNS qo‘shmang, /etc/resolv.conf ni almashtirmang, topshiriq nomlarini /etc/hosts ga yozmang. SSM oynasini ochiq qoldiring.

**Ishlamasa:** Bir interface bir necha YAML da bo‘lsa, qiymatlar birlashadi. resolvectl dns da AWS DNS qolsa, tegishli barcha YAML va amaldagi sozlamani tekshiring.

#### P2.7 Qo‘llagach odatiy resolver va HTTP ni tekshirish

**Bajarish joyi:** Bastionning SSM terminali: ssm-user

**Maqsad va amallar:** Bastion va Web da avval sozlamani hosil qiling, keyin qo‘llang va tekshiring. Ikkinchi SSH/RDP oynasini ochiq tuting; uzilsa SSM orqali qaytib nusxa bilan solishtiring. Fayl tekshirilgach va generate muvaffaqiyatli tugagach apply qiling.

```bash
sudo netplan generate
sudo netplan apply
sudo systemctl restart systemd-resolved
resolvectl dns
getent ahostsv4 guide.lab.test
getent ahostsv4 practice-db.lab.test
curl --noproxy '*' -i http://guide.lab.test/practice.txt
```

**Buyruq va sozlamalar ma’nosi:** Netplan generate config hosil qiladi; apply qo‘llaydi. SSM uzilsa ayni instance ga qayta ulaning. Resolvectl tanlangan DNS ni ko‘rsatadi; getent OS ning oddiy yo‘lini ishlatadi; oxirida nom bilan HTTP tekshiriladi.

**Kutilgan natija va ma’nosi:** Yagona upstream DNS 10.20.2.10. getent kerakli IP, HTTP esa 200 va P1 matnini beradi. 127.0.0.53 mahalliy stub; upstream ni resolvectl da ko‘ring.

**Ishlamasa:** dig o‘tib getent o‘tmasa, client resolver ini tekshiring. Firefox dagi DoH o‘chirilgan sozlamani saqlang.

#### P2.8 Browser da IP va nomni solishtirib yuborish

**Bajarish joyi:** RDP orqali bastiondagi Firefox

**Maqsad va amallar:** RDP orqali bastion Firefox ini oching. http://10.20.1.20/practice.txt va http://guide.lab.test/practice.txt bir xil matn berishini ko‘ring. lab.test maktab PC odatiy DNS ida emas, bastion ichki DNS ida ishlaydi. So‘ng CloudShell da P2 ni bajaring.

```bash
jdu-web-check P2 --no-submit
jdu-web-check P2
```

**Buyruq va sozlamalar ma’nosi:** Bastion Firefox i ichki guide.lab.test nomini ishlatadi. Windows browser i ayni ichki DNS ga sozlanmagan. IP va nom orqali ko‘rinishni solishtirib, yuborishdan oldin ayni P1 fayl ekanini tekshiring.

**Kutilgan natija va ma’nosi:** 13 ta mashq tekshiruvi; P1 ning joriy ishlashi ham kerak. DB/app dan oldin M2 da oltita asosiy nomni qo‘shing.

**Ishlamasa:** Nom ochilmasa darhol HTTP to‘xtagan demang: IP → dig → getent → HTTP tartibida solishtiring.

### Natijani o‘qish namunasi (kiritmang)

```text
status: NOERROR
guide.lab.test.  300  IN  A  10.20.1.20
```

Dig ning qisqa namunasi: A dan keyin IPv4, 300 esa TTL. So‘rov SERVER i 10.20.2.10 ekanini alohida tekshiring.

### Tushunishni tekshirish (ballsiz)

dig @10.20.2.10 ishlaydi, getent ishlamaydi. Muammo albatta zone dami?

**Izoh:** Yo‘q. Aniq tanlangan DNS bilan OS ning oddiy resolver i farq qilishi mumkin. Netplan va resolvectl ning amaldagi sozlamalarini tekshiring.

## P3 To‘xtatish va qayta ishga tushirishda ma’lumotlar

### Nimani o‘rganamiz

Asl EBS dagi fayl va ruxsatni tekshirish; ayni Web stop/start dan keyin saqlanishini isbotlash.

### Topshiriq

O‘z anonim Lab ID bilan P3 marker yarating. To‘xtashdan oldin, stopped va qayta ishga tushgandan keyingi holatni qayd eting. Yangi disk, mount yoki backup/restore kerak emas.

- File: /var/lib/jdu-web/practice/storage.txt

```text
lab_id={lab_id}
task=P3
payload=practice-storage-2026
```

### Bu qanday ishlaydi

**Boshlashdan oldingi holat:** Marker ni ayni Web ning asl root EBS ida saqlash mumkin.

**Ushbu P da nima o‘zgaradi:** Ayni Web stop/start dan keyin mazmun saqlangani oldingi va keyingi dalil bilan ko‘rsatiladi.

Ishlayotgan xotira bilan EBS ga saqlangan faylni farqlang. Bu yerda asl EBS saqlangan ayni Web Stop/Start qilinadi. Hash, instance/volume ID va boot ID o‘zgarishini solishtiring. Avtomatik public IPv4 o‘zgarishi mumkin. [EC2 stop/start](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html).

### Yechim namunasi: bittadan bajaring

#### P3.1 Asl saqlash joyi va bo‘sh joyni tekshirish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** findmnt fayl tizimini, lsblk disk va partition larni, df -h bo‘sh joyni ko‘rsatadi. Berilgan root EBS dan foydalaning; /dev/nvme nomi disk almashtirish sababi emas.

```bash
findmnt -T /var/lib
lsblk -o NAME,TYPE,SIZE,MOUNTPOINTS,SERIAL
df -h /var/lib
cat /proc/sys/kernel/random/boot_id
```

**Buyruq va sozlamalar ma’nosi:** Findmnt path joylashgan filesystem ni, lsblk block device larni, df bo‘sh joyni ko‘rsatadi. Ular turli kuzatuvlar. Boot_id joriy boot ni, hash fayl mazmunini aniqlaydi.

**Kutilgan natija va ma’nosi:** Asl root volume ga mos; kamida 20% va 2 GiB bo‘sh. Joriy yuklanish boot_id sini yozib oling.

**Ishlamasa:** Joy yetishmasligi tayyorlik muammosi. Ball uchun boshqa material yoki diskni o‘chirmang.

#### P3.2 Marker ni yaratish va joylash

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** Bu terminalda ham LAB_ID ni belgilang. printf har qatorni yangi qator bilan tugatadi. install katalogni 0755, faylni 0644/root:root qiladi. Avval mavjud faylni tekshiring; boshqa mazmunni sababini bilmasdan almashtirmang.

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

**Buyruq va sozlamalar ma’nosi:** Printf %s o‘rniga LAB_ID qo‘yadi; \n yangi qatordir. > ish fayliga yozadi. Install -d katalog yaratadi, keyingi install marker owner va permission ini belgilaydi. Hash mazmun bir xilligini tekshiradi.

**Kutilgan natija va ma’nosi:** Oxirida yangi qator bo‘lgan 3 qator, ruxsat 0755/0644. Hash ni yozing. 777 ruxsat mos emas.

**Ishlamasa:** YOUR-LAB-ID ni o‘z holicha qoldirmang. EC2 nomi yoki email emas, anonim Lab ID ishlating.

#### P3.3 To‘xtatishdan oldingi dalilni saqlash

**Bajarish joyi:** Talabaning shaxsiy AWS hisobidagi CloudShell

**Maqsad va amallar:** Web dan exit bilan CloudShell ga qayting. prepare-stop instance/volume/marker hash/boot_id ni saqlaydi, EC2 ni o‘zi to‘xtatmaydi. Muvaffaqiyatni kuting.

```bash
jdu-web-check P3 --prepare-stop
```

**Buyruq va sozlamalar ma’nosi:** --prepare-stop server, boot va marker ning oldingi holatini saqlaydi; EC2 ni o‘zi to‘xtatmaydi. Avval saqlanganini tekshirib, keyin Stop qiling. To‘xtatgach oldingi dalilni olib bo‘lmaydi.

**Kutilgan natija va ma’nosi:** To‘xtashdan oldingi holat saqlandi. Shundan keyin marker ni tahrirlamang.

**Ishlamasa:** Tayyorlash xatosidan keyin to‘xtatish to‘liq dalil bermaydi. Avval fayl/ruxsat/SSM ni tuzating.

#### P3.4 Ayni Web ni Stop qilib stopped holatini qayd etish

**Bajarish joyi:** Talabaning shaxsiy AWS Console oynasi

**Maqsad va amallar:** Web instance ID ni yana solishtiring. Instance state → Stop instance ni tanlab stopped ni kuting. Reboot yoki Terminate emas. Ishga tushirmasdan CloudShell da quyidagini bajaring. Qolgan to‘rtta server ishlasin.

```bash
jdu-web-check P3 --observe-stopped
```

**Buyruq va sozlamalar ma’nosi:** Console da kerakli Web ni Stop qiling; stopped holatini CloudShell dan --observe-stopped bilan qayd eting. SSM uzilishi to‘xtashni o‘zi isbotlamaydi. Stop reboot va Terminate dan farq qiladi.

**Kutilgan natija va ma’nosi:** Ayni instance stopped deb qayd qilinadi. Bu paytda HTTP/SSM ishlamasligi kutilgan holat.

**Ishlamasa:** stopping bo‘lsa kuting. Kuzatuvdan oldin Start qilsangiz, uch bosqichli dalilni qayta olish kerak bo‘ladi.

#### P3.5 Start qilib saqlanishni solishtirish va yuborish

**Bajarish joyi:** Talabaning shaxsiy AWS Console oynasi

**Maqsad va amallar:** Ayni Web ni Start qilib running/SSM Online ni kuting. SSM orqali matn/hash va boot_id ni tekshiring. instance/volume/hash bir xil, boot_id yangi bo‘ladi. So‘ng CloudShell da P3 ni bajaring.

```bash
jdu-web-check P3 --no-submit
jdu-web-check P3
```

**Buyruq va sozlamalar ma’nosi:** Ayni Web ni Start qilib running/SSM Online ni kuting. Checker joriy holatni saqlangan oldingi dalil bilan solishtiradi; start dan keyin marker ni qayta yaratmang. Keyingi tashqi kirishda Web ning yangi public IP sini ishlating.

**Kutilgan natija va ma’nosi:** Uchta mashq tekshiruvi PASS. Public IPv4 o‘zgarsa, tashqi HTTP uchun yangi manzil ishlating.

**Ishlamasa:** Yangi instance saqlanish isboti emas. P3/M3 alohida marker va dalildan foydalanadi.

### Tushunishni tekshirish (ballsiz)

Yangi Web da bir xil matn chiqishi topshiriq uchun yetarlimi?

**Izoh:** Yo‘q: asl instance va volume saqlanishi hamda stopped holati kuzatilishi kerak.

## P4 PostgreSQL ga autentifikatsiya bilan ulanish

### Nimani o‘rganamiz

Database, role va schema ni farqlash; Web dan belgilangan parol bilan SQL bajarish.

### Topshiriq

jdu_catalog_practice, catalog_practice_setup va catalog_practice_app ni yarating. Faqat Web 10.20.1.20/32 dan SCRAM ulanishiga ruxsat bering. P4 da app jadvallari hali kerak emas.

- Profile: practice
- Database: jdu_catalog_practice
- Setup role: catalog_practice_setup
- Runtime role: catalog_practice_app
### Bu qanday ishlaydi

**Boshlashdan oldingi holat:** DB da o‘quv resurslari bor; Web → DB ruxsatli yo‘li ishlatiladi.

**Ushbu P da nima o‘zgaradi:** Mashq DB va setup/runtime role yaratiladi; Web dan parol bilan SQL bajariladi.

Tarmoq yo‘li, DB listen, HBA ruxsati, parol va SQL privilege alohida kerak. ssm-user - OS user, catalog_practice_app - DB role. HBA birinchi mos qatorni ishlatadi. Ulanish huquqi table yaratish huquqini anglatmaydi. [HBA](https://www.postgresql.org/docs/16/auth-pg-hba-conf.html) va [SQL privilege](https://www.postgresql.org/docs/16/sql-grant.html).

### Yechim namunasi: bittadan bajaring

#### P4.1 PostgreSQL o‘rnatish va o‘quv SQL ni ochish

**Bajarish joyi:** DB serverning SSM terminali: ssm-user

**Maqsad va amallar:** DB ga SSM bilan kirib role=db ni tekshiring. PostgreSQL 16 cluster - DB serverni boshqarish birligi. Yordamchi app ni tekshirib SQL ni ochadi; DB yoki role yaratmaydi.

```bash
sudo apt-get update -o APT::Update::Error-Mode=any
sudo apt-get install --no-install-recommends postgresql-16 postgresql-client-16
sudo python3 -B /var/lib/jdu-web/lesson-resources-r1/offline_assets.py
pg_lsclusters
sudo -u postgres psql -X -d postgres -c "SHOW data_directory;"
```

**Buyruq va sozlamalar ma’nosi:** Package o‘rnatish va DB ichida o‘quv obyektlarini yaratish alohida bosqich. Pg_lsclusters version, cluster, port va holatni ko‘rsatadi. Sudo -u postgres command ni OS postgres bilan bajaradi; -X shaxsiy psql config ni o‘qimaydi.

**Kutilgan natija va ma’nosi:** 16/main, data directory /var/lib/postgresql/16/main. O‘quv SQL /var/lib/jdu-web/lesson-resources-r1/app/sql da.

**Ishlamasa:** Mavjud DB yoki role ni o‘chirmang. Oldin qurilgan bo‘lsa, holatni o‘qib faqat yetishmagan qadamlarni bajaring.

#### P4.2 DB tinglashi va SCRAM ni sozlash

**Bajarish joyi:** DB serverning SSM terminali: ssm-user

**Maqsad va amallar:** postgresql.conf nusxasini sudo cp -an bilan saqlang. sudo nano /etc/postgresql/16/main/postgresql.conf da uch qiymatni sozlang. Parametr takrorlansa, amaldagi qiymatni SHOW bilan tekshiring. Faqat DB private IP va 5432 tinglanadi; password_encryption keyingi parollar saqlanish turini belgilaydi.

```text
listen_addresses = '10.20.2.20'
port = 5432
password_encryption = 'scram-sha-256'
```

**Buyruq va sozlamalar ma’nosi:** Listen_addresses DB tinglaydigan o‘z IP sini bildiradi, client ruxsat ro‘yxatini emas. Password_encryption yangi o‘rnatiladigan parol formatini belgilaydi. Faylni saqlash listener yoki eski parollar o‘zgarganini isbotlamaydi.

**Kutilgan natija va ma’nosi:** Barcha manzil uchun * ishlatmang. Parollar HBA va restart dan keyin belgilanadi.

**Ishlamasa:** Bu SQL emas, postgresql.conf mazmuni. SG va OS tinglash manzili alohida nazoratdir.

#### P4.3 HBA da manba, database va role ni cheklash

**Bajarish joyi:** DB serverning SSM terminali: ssm-user

**Maqsad va amallar:** pg_hba.conf nusxasini saqlab, sudo nano /etc/postgresql/16/main/pg_hba.conf ga quyidagi qoidalarni yozing. Birinchi mos qator ishlatiladi, shu sabab eski keng ruxsatlarni qoldirmang. OS postgres Unix socket/peer orqali boshqaradi. M4 rollari alohida ko‘rsatilgan; mashq roli asosiy DB ga kira olmaydi.

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

**Buyruq va sozlamalar ma’nosi:** Host qatori DB, role, client address va authentication usuli birikmasidir. 10.20.1.20/32 faqat Web ni bildiradi. Kerakli ruxsatlar oxirgi reject dan oldin turadi. OS postgres uchun local peer TCP parolli kirishdan alohida.

**Kutilgan natija va ma’nosi:** Ruxsat database/role/manba birikmasiga bog‘liq. 0.0.0.0/0 qatori reject, ya’ni rad etishdir.

**Ishlamasa:** Autentifikatsiyani trust bilan chetlab o‘tmang. Asosiy SG ham DB 5432 ni faqat Web dan ruxsat qiladi.

#### P4.4 Qayta ishga tushirish va amaldagi qiymatni tekshirish

**Bajarish joyi:** DB serverning SSM terminali: ssm-user

**Maqsad va amallar:** restart sozlamani qayta o‘qiydi. SHOW va pg_hba_file_rules fayl matnini emas, ishlayotgan qiymatni tekshiradi. psql -X shaxsiy boshlang‘ich fayllarni o‘qimaydi.

```bash
sudo systemctl restart postgresql@16-main
systemctl is-active postgresql@16-main
sudo ss -lntp
sudo -u postgres psql -X -d postgres -c "SHOW password_encryption;"
sudo -u postgres psql -X -d postgres -c \
  "SELECT line_number,error FROM pg_hba_file_rules WHERE error IS NOT NULL;"
```

**Buyruq va sozlamalar ma’nosi:** Postgresql@16-main kerakli cluster service idir. Restart dan keyin service, listener va SHOW amaldagi qiymatini birga tekshiring. Pg_hba_file_rules da error yo‘qligi haqiqiy client ulanishini almashtirmaydi.

**Kutilgan natija va ma’nosi:** active, 10.20.2.20:5432, scram-sha-256, HBA xatosi - 0 qator.

**Ishlamasa:** postgresql.service active(exited) bo‘lishi cluster ishlashini isbotlamaydi. journalctl -u postgresql@16-main ni o‘qing.

#### P4.5 Mashq DB va ikkita role yaratish

**Bajarish joyi:** DB serverning SSM terminali: ssm-user

**Maqsad va amallar:** profile_sql.py faqat mashq nomlari bilan tayyor SQL ni chiqaradi. Avval matnni o‘qing, keyin ayni chiqishni psql ga uzating. setup DB/schema egasi va boshlang‘ich jadval yaratuvchi; app odatiy ulanish roli. App dasturlash talab qilinmagani uchun berilgan SQL dan foydalaning.

```bash
cd /var/lib/jdu-web/lesson-resources-r1/app
python3 -B profile_sql.py --profile practice 01_create_roles.sql
python3 -B profile_sql.py --profile practice 01_create_roles.sql | sudo -u postgres \
  psql -X -v ON_ERROR_STOP=1 -d postgres
python3 -B profile_sql.py --profile practice 02_prepare_schema.sql | sudo -u postgres \
  psql -X -v ON_ERROR_STOP=1 -d jdu_catalog_practice
```

**Buyruq va sozlamalar ma’nosi:** Profile_sql.py ning birinchi ishga tushishi faqat SQL ni ko‘rsatadi. | orqali psql ga uzatilganda DB o‘zgaradi. --profile practice mashq nomlarini tanlaydi; ON_ERROR_STOP=1 SQL xatosida to‘xtatadi. Mavjud DB da yaratishni takrorlamang.

**Kutilgan natija va ma’nosi:** Ikki CREATE ROLE, CREATE DATABASE va schema/CONNECT/USAGE sozlanadi. app ga superuser/CREATEDB berilmaydi.

**Ishlamasa:** already exists oldin bajarilganini anglatishi mumkin. DROP qilmang; \du va \l orqali solishtiring. Pipe o‘ngidagi psql SQL error bermaganini tekshiring.

#### P4.6 Ikki DB parolini yashirin kiritish

**Bajarish joyi:** DB serverda OS postgres nomidan psql

**Maqsad va amallar:** Birinchi qator DB shell ida bajarilib postgres=# psql ni ochadi. \password buyruqlarini psql ichida kiriting. setup/app uchun kamida 16 belgili turli parollarni har birini ikki marta yashirin kiriting. Qiymatni buyruq yoki hisobotga yozmang. \q DB shell iga qaytaradi.

```text
sudo -u postgres psql -X -d postgres
\password catalog_practice_setup
\password catalog_practice_app
\du catalog_practice_*
\q
```

**Buyruq va sozlamalar ma’nosi:** Sudo qatorini OS terminalida, keyingi \password, \du va \q ni psql ichida bittadan kiriting. Setup va app boshqa DB role bo‘lib, parollarini farqlang. Parol kiritishda belgilar ko‘rinmasligi normal.

**Kutilgan natija va ma’nosi:** Superuser/Create role/Create DB yo‘q. Bular RDP paroli, app admin paroli yoki baholash tokenidan alohida maxfiy qiymatlardir.

**Ishlamasa:** Klaviatura tartibiga e’tibor bering. Tekshirish uchun parolni chat yoki editorga yozmang. Unutilsa o‘qituvchi bilan shaxsiy tiklash tartibini bajaring.

#### P4.7 Web dan parol bilan SELECT bajarish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** DB SSM dan exit qilib CloudShell ga qayting, Web SSM ni oching. psql da -h manzil, -U role, -d DB nomi, -W parol so‘rovi. P4 qo‘shimcha DNS bog‘liqligisiz private IP dan foydalanadi.

```bash
sudo apt-get install --no-install-recommends postgresql-client-16
psql -X -h 10.20.2.20 -U catalog_practice_app -d jdu_catalog_practice -W -c \
  'SELECT current_database(),current_user,1 AS value;'
```

**Buyruq va sozlamalar ma’nosi:** Psql da -h serverni, -U DB role ni, -d DB nomini, -W parol so‘rashni, -c SQL ni belgilaydi. Web da bajaring. Natijadagi DB va user nomlari mashq profile ga ulanganini tasdiqlaydi.

**Kutilgan natija va ma’nosi:** jdu_catalog_practice / catalog_practice_app / 1. Port ochiqligi yoki pg_isready muvaffaqiyati bu autentifikatsiyali SQL o‘rnini bosmaydi.

**Ishlamasa:** Rad etilsa manba, DB, role va parolni alohida tekshiring. Sinash uchun DB ni Internet ga ochmang.

#### P4.8 Checker uchun mavjud parolni faqat Web da saqlash

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** Yordamchi mavjud catalog_practice_app parolini ikki marta yashirin so‘rab, Web dagi root-only 0600 faylga saqlaydi. DB parolini o‘zgartirmaydi. Env ni cat bilan ko‘rsatmang, source qilmang. Keyin exit orqali CloudShell ga qaytib P4 ni bajaring.

```bash
sudo python3 -B /var/lib/jdu-web/lesson-resources-r1/database_secret.py --profile \
  practice
exit
jdu-web-check P4 --no-submit
jdu-web-check P4
```

**Buyruq va sozlamalar ma’nosi:** Database_secret.py mavjud runtime parolini qayta olib Web dagi himoyalangan config ga saqlaydi. Bu yangi parol yaratish yoki almashtirish emas. Setup yoki RDP emas, catalog_practice_app ning mavjud parolini ishlating.

**Kutilgan natija va ma’nosi:** D11_EXISTING_DB_PASSWORD_STORED_LOCALLY va to‘qqizta mashq tekshiruvi. Noto‘g‘ri parol hamda taqiqlangan DB/admin-role rad etilishi muvaffaqiyatli ulanish bilan solishtiriladi.

**Ishlamasa:** Fayl mavjud bo‘lsa qayta yaratmang. P5 da ayni DB paroli app sozlamasiga kiritiladi. M4 alohida mission DB/rollaridan foydalanadi.

### Natijani o‘qish namunasi (kiritmang)

```text
current_database    | current_user         | value
jdu_catalog_practice | catalog_practice_app | 1
```

SELECT natijasini o‘qish namunasi; ustun kengligi boshqacha bo‘lishi mumkin. DB, role va value=1 ni tekshiring. Bu table o‘zgartirish huquqini isbotlamaydi.

### Tushunishni tekshirish (ballsiz)

Parol qabul qilinib CREATE TABLE rad etildi. Parol albatta xatomi?

**Izoh:** Authentication va SQL privilege boshqa-boshqa. Runtime uchun setup amalining rad etilishi to‘g‘ri holat bo‘lishi mumkin.

## P5 Berilgan app ni Web va DB bilan bog‘lash

### Nimani o‘rganamiz

Dastur yozmasdan offline bog‘liqlik, service user, DB tayyorlash, Nginx/systemd va haqiqiy HTTP ni bog‘lash.

### Topshiriq

practice profile da katalogni quring. M2 asosiy DNS va P4 hozir ham ishlashi kerak. P/M DB va admin lari alohida, ayni Web dagi app va port umumiy.

- Profile: practice
- Database: jdu_catalog_practice
- Setup role: catalog_practice_setup
- Runtime role: catalog_practice_app
- Application administrator: practice_admin

| code | name | quantity | location | is_public |
| --- | --- | --- | --- | --- |
| P5-PUBLIC-001 | Practice keyboard | 4 | Training shelf A | true |
| P5-PRIVATE-001 | Practice mouse | 2 | Training shelf B | false |

### Bu qanday ishlaydi

**Boshlashdan oldingi holat:** M2 DNS va P4 mashq DB hozir ishlaydi.

**Ushbu P da nima o‘zgaradi:** Tayyor app Web ichida ishlaydi; ochiq ro‘yxat va bastion admin oynasi DB ga ulanadi.

Nginx HTTP ni qabul qiladi, Gunicorn Python app ni ishlatadi, PostgreSQL ma’lumot saqlaydi. Statik P1 dan farqli ravishda ro‘yxat mazmuni DB dan olinadi. Venv app Python muhitini ajratadi; systemd unit ishga tushishni belgilaydi. Tayyor kodni joylaysiz, dasturni qayta yozish shart emas.

### Yechim namunasi: bittadan bajaring

#### P5.1 Kerakli DNS va ochiq resurslarni tekshirish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** Web odatiy resolver db.lab.test=10.20.2.20 va admin.lab.test=10.20.1.20 qaytarsin. offline_assets ichki repo dan asl imzo/hash bo‘yicha yettita wheel va lock oladi. Tashqi pip ishlatmaydi, DB/app sozlamaydi.

```bash
getent ahostsv4 db.lab.test
getent ahostsv4 admin.lab.test
sudo apt-get install --no-install-recommends python3-venv python3-pip
sudo python3 -B /var/lib/jdu-web/lesson-resources-r1/offline_assets.py --wheels
ls /var/lib/jdu-web/lesson-resources-r1/app
ls /var/lib/jdu-web/lesson-resources-r1/wheels
```

**Buyruq va sozlamalar ma’nosi:** P5 M2 dagi oddiy DNS ni ishlatadi; DB nomini qo‘lda IP ga almashtirmang. --wheels belgilangan Python package resurslarini tayyorlaydi, app ni ishga tushirmaydi. Ochiq fayllar bilan keyingi maxfiy config ni ajrating.

**Kutilgan natija va ma’nosi:** PUBLIC_APP_RESOURCES_VERIFIED va SIGNED_OFFLINE_WHEELS_READY=7. App fayllari ochiq va root boshqaruvida.

**Ishlamasa:** Faqat practice-db emas, db.lab.test ham kerak. P5 M2 ga bog‘liq, ammo asosiy katalog topshirig‘ini tugatish shart emas.

#### P5.2 Kod joylash va alohida venv yaratish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** App va venv ni root boshqaradi; catalog ularni o‘zgartira olmaydi. app yoki venv mavjud bo‘lsa, qayta yaratmay versiyani tekshiring. cp faqat tekshirilgan ochiq resursni joylaydi. venv app bog‘liqliklarini system Python dan ajratadi.

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

**Buyruq va sozlamalar ma’nosi:** Kod /opt/jdu-catalog/app da, Python muhiti yonidagi venv da. --no-index package index ni ishlatmaydi; --find-links local wheel joyini beradi; --require-hashes hash mosligini talab qiladi. Pip check o‘rnatilgach dependency ni tekshiradi.

**Kutilgan natija va ma’nosi:** --no-index tashqi index ni ishlatmaydi; --require-hashes lock hash ini talab qiladi. pip check bog‘liqlik ziddiyatini topmaydi.

**Ishlamasa:** Bog‘liqlik yetishmasa o‘qituvchi tarqatmasini tekshiring. Pip orqali latest ga yangilamang, app kodini o‘zgartirmang.

#### P5.3 Service user va static katalogini yaratish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** catalog inson login i uchun emas, Gunicorn service user idir. nologin va sudo siz yarating. collectstatic yozishi uchun faqat static katalogini catalog egasi qiling; kod/venv root da qoladi. catalog mavjud bo‘lsa useradd ni takrorlamay id va shell ni tekshiring.

```bash
sudo useradd --system --user-group --home-dir /nonexistent --no-create-home --shell \
  /usr/sbin/nologin catalog
sudo install -d -o root -g root -m 0755 /var/lib/jdu-catalog
sudo install -d -o catalog -g catalog -m 0755 /var/lib/jdu-catalog/static
id catalog
getent passwd catalog
```

**Buyruq va sozlamalar ma’nosi:** Catalog - OS service user, catalog_practice_app DB role idan boshqa. Nologin interaktiv shell ni cheklaydi, service ishlamaydi degani emas. Id catalog allaqachon bor bo‘lsa, avval qadam oldin bajarilganini tekshiring.

**Kutilgan natija va ma’nosi:** catalog sudo guruhida emas, shell /usr/sbin/nologin. Bu labuser yoki ssm-user dan boshqa user.

**Ishlamasa:** Ruxsat xatosini chmod -R 777 yoki catalog ga sudo berish bilan hal qilmang. Aniq katalog va egasini solishtiring.

#### P5.4 Runtime sozlamasini yashirin kiritish bilan yaratish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** EC2 dagi hozirgi Web public IPv4 ni kiriting. Runtime yordamchisiga P4 dagi mavjud catalog_practice_app parolini ikki marta kiriting. Django secret shaxsiy Lab uchun yaratiladi. Root-only app.env va practice profile yaratiladi; mazmun ko‘rsatilmaydi.

```bash
PUBLIC_WEB_IPV4='YOUR-CURRENT-WEB-PUBLIC-IP'
sudo python3 -B /opt/jdu-catalog/app/configuration.py create-runtime --profile \
  practice --public-web-ipv4 "$PUBLIC_WEB_IPV4"
sudo python3 -B /opt/jdu-catalog/app/configuration.py check --phase runtime
sudo stat -c '%U:%G %a %n' /etc/jdu-catalog/app.env
```

**Buyruq va sozlamalar ma’nosi:** Runtime config odatiy DB ulanishi va ruxsatli public host ni saqlaydi. Stop/start dan keyingi joriy PUBLIC_WEB_IPV4 ni ishlating. Check qiymatni, stat owner va permission ni tekshiradi. Maxfiy qiymatni ko‘rish uchun app.env ni to‘liq chiqarmang.

**Kutilgan natija va ma’nosi:** CATALOG_ENV_CREATED=practice, VALID, root:root 600. Mashq DB va mashq app role tanlanadi.

**Ishlamasa:** RDP yoki app admin parolini kiritmang. Mavjud faylni o‘chirib qayta yaratmang; yaratilgan bo‘lsa check ni bajaring.

#### P5.5 Vaqtinchalik setup bilan jadval va admin yaratish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** create-setup ga P4 dagi catalog_practice_setup parolini kiriting. migrate berilgan DB tuzilmasini yaratadi; seed bo‘sh katalogga bir marta uchta xayoliy namuna kiritadi. create_lab_admin yashirin parol bilan practice_admin yaratadi. Oddiy app setup orqali ishlamaydi.

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

**Buyruq va sozlamalar ma’nosi:** Migrate table tuzilishini, seed_catalog boshlang‘ich yozuvlarni, create_lab_admin app administratorini yaratadi. Uning paroli DB va RDP parolidan boshqa. Setup tayyorlash uchun, odatiy ishlash uchun emas.

**Kutilgan natija va ma’nosi:** Belgilangan 11 jadval, uchta namuna va superuser bo‘lmagan staff admin. Amallar OS catalog huquqiga tushirilgan holda bajariladi.

**Ishlamasa:** Seed/admin already exists mavjud ma’lumotni himoya qiladi. Reset qilmay joriy holatni tekshiring.

#### P5.6 Runtime role ga kerakli SQL huquqini berish

**Bajarish joyi:** DB serverning SSM terminali: ssm-user

**Maqsad va amallar:** Web dan CloudShell ga chiqib DB SSM ni oching. Avval SQL03 ni o‘qing: u 11 jadval va egalarni tekshirib jadval, ustun va sequence bo‘yicha huquq beradi. App ga egalik yoki ALL PRIVILEGES berilmaydi.

```bash
cd /var/lib/jdu-web/lesson-resources-r1/app
python3 -B profile_sql.py --profile practice 03_runtime_grants.sql
python3 -B profile_sql.py --profile practice 03_runtime_grants.sql | sudo -u postgres \
  psql -X -v ON_ERROR_STOP=1 -d jdu_catalog_practice
```

**Buyruq va sozlamalar ma’nosi:** DB ga qaytib yaratilgan table lar uchun runtime privilege bering. DB ga ulanish va table/sequence ishlatish boshqa huquqlar. Avval practice SQL ni o‘qing; runtime ni superuser qilish bilan hal qilmang.

**Kutilgan natija va ma’nosi:** COMMIT gacha muvaffaqiyat. catalog_item: SELECT/INSERT/UPDATE; auth_user: o‘qish va faqat last_login/password ustunlarini UPDATE; session va boshqalar maqsadiga ko‘ra.

**Ishlamasa:** Guard xatosi migration/owner ni tekshirish kerakligini bildiradi. O‘tish uchun himoyani o‘chirmang.

#### P5.7 Static va systemd unit ni joylash

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** Web ga qayting. collectstatic CSS va boshqa fayllarni Nginx o‘qiydigan katalogga yig‘adi. Unit ni joylab daemon-reload bajaring. User=catalog, EnvironmentFile va 127.0.0.1:8000 ni toping.

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

**Buyruq va sozlamalar ma’nosi:** Collectstatic CSS va boshqa statik fayllarni yig‘adi. Unit joylangach daemon-reload systemd ta’rifini qayta o‘qiydi, app config ni emas. 8000 port faqat Web ichidagi 127.0.0.1 da tinglashini tekshiring.

**Kutilgan natija va ma’nosi:** active; app 8000 ni faqat 127.0.0.1 da tinglaydi. Uni 0.0.0.0:8000 orqali ochmang.

**Ishlamasa:** Xatoda journalctl -u jdu-catalog ni o‘qing. Env mazmunini log ga qo‘ymang; formatni configuration.py check bilan tekshiring.

#### P5.8 Nginx ochiq va boshqaruv kirishlarini ajratish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** Conf ni o‘qing: 80 - ochiq ro‘yxat, private8080 - faqat /admin/, upstream - 8000. Boshlang‘ich default site symlink ini boshqa nom bilan saqlab o‘chiring. jdu-catalog allaqachon yoqilgan bo‘lsa qayta ko‘chirmay tekshiring. P1/M1 statik URL lari saqlanadi.

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

**Buyruq va sozlamalar ma’nosi:** Sites-available config ni saqlaydi; sites-enabled dagi symbolic link uni yoqadi. Asl default alohida saqlanadi. Nginx -t dan keyin reload qilib, P1 statik fayli hamon qaytishini tekshiring.

**Kutilgan natija va ma’nosi:** Sintaksis to‘g‘ri, practice.txt hali ham 200. Ochiq access log endi jdu-catalog-public.access.log.

**Ishlamasa:** duplicate default server bo‘lsa eski site ni tekshiring. Reload dan oldin -t xatosini tuzating. Admin port public IP da tinglamasin.

#### P5.9 Admin orqali ikkita mashq yozuvini kiritish

**Bajarish joyi:** RDP orqali bastiondagi Firefox

**Maqsad va amallar:** Bastion Firefox da http://admin.lab.test:8080/admin/ ni ochib practice_admin va o‘z app admin parolingiz bilan kiring. Add orqali quyidagi ikki qatorni code/name/quantity/location qiymatlari bilan aniq kiriting. Is public ni faqat ochiq yozuvda yoqing. http://web.lab.test/ da faqat ochiq qator ko‘rinsin.

```text
P5-PUBLIC-001 | Practice keyboard | 4 | Training shelf A | is_public=true
P5-PRIVATE-001 | Practice mouse | 2 | Training shelf B | is_public=false
```

**Buyruq va sozlamalar ma’nosi:** Ikki yozuv code, name, quantity, location va is_public bilan farqlanadi. Is_public app ro‘yxatidagi ko‘rinishni boshqaradi, SG ni emas. Private yozuv ham DB da saqlanadi, ammo ochiq ro‘yxatda ko‘rinmaydi.

**Kutilgan natija va ma’nosi:** Uch demo ni o‘chirish shart emas. Belgilangan ikkita yozuv zarur qism; boshqa to‘g‘ri ochiq yozuvlar mumkin. Yopiq yozuv ro‘yxatda ko‘rinmaydi.

**Ishlamasa:** admin.lab.test ni maktab PC da emas, RDP ichidagi Firefox da oching. CSRF xatosida host/port/proxy ni tekshiring.

#### P5.10 DB haqiqiy qatorlarini o‘qish va ekran bilan solishtirish

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** Web da mashq app role bilan SELECT bajaring. Bu admin dagi saqlash haqiqatan PostgreSQL ga yetganini tekshiradi. Ushbu tekshiruvda UPDATE/DELETE ishlatmang.

```bash
QUERY="SELECT code,name,quantity,location,is_public
FROM catalog_item
WHERE code IN ('P5-PUBLIC-001','P5-PRIVATE-001')
ORDER BY code;"
psql -X -h db.lab.test -U catalog_practice_app -d jdu_catalog_practice -W -c "$QUERY"
```

**Buyruq va sozlamalar ma’nosi:** SELECT ma’lumot o‘qiydi; WHERE kerakli ikki yozuvni tanlaydi; ORDER BY tartib beradi. Boshqa to‘g‘ri yozuvlarni o‘chirmang. Browser va SQL ni solishtirish sahifa ko‘rinishini emas, haqiqiy DB qiymatini tasdiqlaydi.

**Kutilgan natija va ma’nosi:** Ikkala qator topshiriqqa mos. DB ishlamasa, sahifani tayyor HTML bilan almashtirmang.

**Ishlamasa:** permission denied bo‘lsa SQL03 profile va database ni tekshiring. Oddiy role o‘rniga superuser ishlatmang.

#### P5.11 Funksional tekshiruvni ishga tushirish va yuborish

**Bajarish joyi:** Talabaning shaxsiy AWS hisobidagi CloudShell

**Maqsad va amallar:** Web dan chiqib CloudShell da bajaring. --functional mavjud practice_admin parolini yashirin kiritish uchun interaktiv SSM ochadi. Avtomatika oddiy HTTP login qiladi, bitta CK-P- yozuv yaratib miqdorini o‘zgartiradi, DB/sahifani solishtirib logout qiladi. Belgilangan ikki yozuv o‘zgarmaydi; tekshiruv yozuvi qoladi. Shaxsiy namoyish talab qilinmaydi.

```bash
jdu-web-check P5 --functional
```

**Buyruq va sozlamalar ma’nosi:** --functional faqat config borligini emas, berilgan kiritish bilan app amallarini tekshiradi. Yashirin maydonga app administratorining mavjud parolini kiriting. Functional PASS/FAIL/UNKNOWN va yuborish STORED/PENDING ni alohida o‘qing.

**Kutilgan natija va ma’nosi:** 13 mashq bandi va yuborish holatini ko‘ring. Parolsiz oddiy tekshiruv to‘rtta funksional bandni UNKNOWN qoldiradi. Turli urinish natijalari birlashtirilmaydi.

**Ishlamasa:** Noto‘g‘ri parolda yangisini yaratmay to‘g‘ri mavjud parolni ishlating. Har yangi tekshiruv bitta CK yozuv qo‘shadi; faqat yuborishni takrorlash uchun --retry ishlating.

### Tushunishni tekshirish (ballsiz)

Ro‘yxatda private yozuv ham chiqsa, faqat HTTP 200 ni to‘g‘ri deb hisoblash mumkinmi?

**Izoh:** Yo‘q. HTTP yetib borishi, DB qiymati va is_public bo‘yicha ajratishni alohida tekshiring.

## P6 Eng kam huquq va ochiq kirish chegarasi

### Nimani o‘rganamiz

To‘g‘ri ishlashni saqlab, ortiqcha admin yo‘li, SQL huquqi va maxfiy fayl ochilishini rad etish.

### Topshiriq

P5 practice profile dan foydalaning. Setup role ni o‘chiring, vaqtinchalik sozlamani olib tashlang, muvaffaqiyatli login bilan solishtirib rad etishlarni tekshiring. SG/IAM ni kengaytirmang.

- Profile: practice
- Database: jdu_catalog_practice
- Setup role: catalog_practice_setup
- Runtime role: catalog_practice_app
- Application administrator: practice_admin

| code | name | quantity | location | is_public |
| --- | --- | --- | --- | --- |
| P5-PUBLIC-001 | Practice keyboard | 4 | Training shelf A | true |
| P5-PRIVATE-001 | Practice mouse | 2 | Training shelf B | false |

### Bu qanday ishlaydi

**Boshlashdan oldingi holat:** P5 mashq app ishlaydi; vaqtinchalik setup ulanish hali mavjud.

**Ushbu P da nima o‘zgaradi:** Setup tugatiladi; odatiy app muvaffaqiyati va keraksiz kirish rad etilishi birga tekshiriladi.

Vaqtinchalik setup privilege va ish paytidagi runtime privilege ni ajrating. NOLOGIN va vaqtinchalik sozlama o‘chirilgach app runtime bilan ishlashi kerak. Ochiq 80, admin 8080 va loopback 8000 alohida chegara. Ruxsatli amal muvaffaqiyati bilan aniq keraksiz kirish rad etilishini birga tekshiring.

### Yechim namunasi: bittadan bajaring

#### P6.1 DB role va jadval huquqlarini o‘qish

**Bajarish joyi:** DB serverda OS postgres nomidan psql

**Maqsad va amallar:** DB da postgres psql ni oching. \dp jadval huquqini, \du role atributini ko‘rsatadi. SQL03 bilan solishtiring: auth_user UPDATE faqat last_login/password, catalog_item DELETE yo‘q; lookup faqat o‘qish, django_migrations huquqsiz. Tekshirish uchun nextval/setval chaqirmang.

```text
sudo -u postgres psql -X -d jdu_catalog_practice
\du catalog_practice_*
\dp public.*
\q
```

**Buyruq va sozlamalar ma’nosi:** \du DB role atributlarini, \dp obyekt privilege larini ko‘rsatadi. Bu ls -l dagi file permission emas. Setup va runtime ni solishtirib, runtime ga tuzilmani o‘zgartirish huquqi nega kerak emasligini tushuntiring.

**Kutilgan natija va ma’nosi:** Runtime owner yoki superuser emas. Django session uchun DELETE zarur, lekin bu jihoz yozuvini o‘chirish huquqi emas.

**Ishlamasa:** Ortiqcha huquqda SQL03 guard ini saqlab tekshiring. Haqiqiy qatorni o‘chirib rad etishni sinamang.

#### P6.2 Setup role login ini o‘chirish

**Bajarish joyi:** DB serverning SSM terminali: ssm-user

**Maqsad va amallar:** Tayyorlashdan keyin setup login kerak emas. SQL04 NOLOGIN/password NULL qiladi va shu profile setup ulanishlarini yopadi. DB/table egasi setup bo‘lib qoladi; role o‘chirilmaydi, egalik app ga o‘tmaydi.

```bash
cd /var/lib/jdu-web/lesson-resources-r1/app
python3 -B profile_sql.py --profile practice 04_disable_setup.sql
python3 -B profile_sql.py --profile practice 04_disable_setup.sql | sudo -u postgres \
  psql -X -v ON_ERROR_STOP=1 -d jdu_catalog_practice
```

**Buyruq va sozlamalar ma’nosi:** NOLOGIN setup role ning yangi bevosita login ini to‘xtatadi, DB yoki table ni o‘chirmaydi. Runtime qoladi. Qo‘llashdan oldin SQL practice uchunligini tekshiring, keyin normal app ishlashini tasdiqlang.

**Kutilgan natija va ma’nosi:** ALTER ROLE muvaffaqiyatli; catalog_practice_app ishlashi saqlanadi.

**Ishlamasa:** Keyin setup ni odatiy ish uchun LOGIN ga qaytarmang. M5 alohida mission setup role bilan tayyorlanadi.

#### P6.3 Faqat vaqtinchalik setup sozlamasini olib tashlash

**Bajarish joyi:** Web serverning SSM terminali: ssm-user

**Maqsad va amallar:** Web da faqat metadata ni tekshiring. Faqat ikkita practice setup faylini o‘chiring. app.env, practice.app.env, DB runtime, command-state, SSH kalit va baholash ma’lumoti qoladi. Maxfiy fayl mazmunini cat qilish kerak emas.

```bash
sudo stat -c '%U:%G %a %n' /etc/jdu-catalog/setup.env \
  /etc/jdu-catalog/profiles/practice.setup.env
sudo rm -- /etc/jdu-catalog/setup.env /etc/jdu-catalog/profiles/practice.setup.env
sudo stat -c '%U:%G %a %n' /etc/jdu-catalog/app.env \
  /etc/jdu-catalog/profiles/practice.app.env /etc/jdu-web/db-practice.runtime.env
sudo python3 -B /opt/jdu-catalog/app/configuration.py check --phase runtime
```

**Buyruq va sozlamalar ma’nosi:** Setup.env va practice.setup.env vaqtinchalik; app.env va runtime DB config ishlash uchun kerak. Rm faqat ko‘rsatilgan ikki faylga tegishli. O‘chirgach maxfiy mazmunni chiqarmay, qolgan fayl permission i va runtime check ni tekshiring.

**Kutilgan natija va ma’nosi:** Runtime fayllari root:root 600, check muvaffaqiyatli. Setup fayllari oldin o‘chirilgan bo‘lsa, o‘chirishni takrorlamang.

**Ishlamasa:** Setup boshqa profile ga tegishli bo‘lsa to‘xtang. Wildcard yoki rm -r bilan butun katalogni o‘chirmang.

#### P6.4 Ochiq 80 da admin va maxfiy fayl ko‘rinmasligini tekshirish

**Bajarish joyi:** Bastionning SSM terminali: ssm-user

**Maqsad va amallar:** Bastion SSM da 80 orqali avval oddiy ro‘yxatni, keyin /admin/ va env ni so‘rang. 8080 dagi to‘g‘ri admin kirishni RDP Firefox da alohida tekshiring. Oddiy muvaffaqiyat va aniq 404/403 rad etish kerak; timeout yetarli emas.

```bash
curl --noproxy '*' -i http://web.lab.test/
curl --noproxy '*' -i http://web.lab.test/admin/
curl --noproxy '*' -i http://web.lab.test/app.env
curl --noproxy '*' -i http://web.lab.test/static/app.env
```

**Buyruq va sozlamalar ma’nosi:** Bu curl bastiondan ochiq 80 port xatti-harakatini tekshiradi. / ishlashi, /admin/ va maxfiy path lar ma’lumot bermasligi kerak. Bitta ulanish xatosi to‘g‘ri taqiq bilan service to‘xtashini farqlamaydi.

**Kutilgan natija va ma’nosi:** Ro‘yxat 200; admin/env maxfiy ma’lumotsiz rad etiladi. Ochiq Nginx X-JDU-Entry ni qayta yozib kirishni soxtalashtirishga yo‘l qo‘ymaydi.

**Ishlamasa:** Env matni ko‘rinsa uni ulashmang; o‘qituvchiga aytib ochiq sozlamani tuzating.

#### P6.5 Bir tekshiruvda to‘g‘ri kirish va rad etishlarni yuborish

**Bajarish joyi:** Talabaning shaxsiy AWS hisobidagi CloudShell

**Maqsad va amallar:** P6 --functional practice_admin muvaffaqiyatli login ini nazorat sifatida olib, anonim amallar va noto‘g‘ri parol DB ni o‘zgartirmasdan rad etilishini tekshiradi. Faqat CSRF sababli 403 avtorizatsiya isboti emas. Staff faqat jihoz view/add/change huquqiga ega, delete va user boshqaruvi yo‘q.

```bash
jdu-web-check P6 --functional
jdu-web-my-progress
```

**Buyruq va sozlamalar ma’nosi:** To‘g‘ri admin amalini xato parol, setup va keraksiz yo‘l rad etilishi bilan birga tekshiring. Faqat rad etish yetarli emas. P6 dan keyin mission profile ga o‘ting; checker profile ni o‘zi qaytarmaydi.

**Kutilgan natija va ma’nosi:** 16 mashq bandi. Shaxsiy progress URL ni faqat o‘zingiz oching. P bahoga ball qo‘shmaydi; M6 mission da alohida tekshiriladi.

**Ishlamasa:** PENDING ni asl request-id bilan qayta yuboring; UNKNOWN sababini tuzatib qayta kuzating. Grade faylini o‘zgartirmang.

### Tushunishni tekshirish (ballsiz)

Setup yopilgach app ham to‘xtadi. Setup ni qayta ochish tayyor yechimmi?

**Izoh:** Yo‘q. Runtime config, role va kerakli table privilege ni tekshiring; normal ish setup siz ishlashi kerak.

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
