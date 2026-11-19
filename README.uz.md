# JDU Web Infrastructure

[日本語](README.md) · [Русский](README.ru.md) · **O‘zbekcha**

JDUning veb-infratuzilmani yaratish bo‘yicha o‘quv materiallari. Bu semestrda ular `Introduction-CyberSecurity` fanining ikkinchi yarmida ishlatiladi. Kelajakda bu materiallardan alohida kurs uchun ham foydalanish mumkin.

Talabalar AWS VPC ichidagi EC2 instanslarida DNS, veb-server va ma’lumotlar bazasini sozlaydi. Ular o‘qituvchi taqdim etgan ilovani veb-server va ma’lumotlar bazasiga ulaydi. Amaliyotda tarmoq yo‘nalishlari, xizmatlarga kirish, portlar, loglar, ma’lumotlarni saqlash va tiklash tekshiriladi. Kursda ilovani dasturlash talab qilinmaydi.

## AWS o‘quv muhitini yaratish

### Har bir rol uchun bir martalik sinov tartibi

AWS Academy’da o‘zingizga tegishli Learner Lab’ni ishga tushiring va quyidagi buyruqlarni Shimoliy Virjiniya (`us-east-1`) regionidagi CloudShell’ga joylang. Avval English, Japanese, Русский yoki O‘zbekcha tilini tanlang. Kiritish ko‘rsatmalari, jarayon holati, yakuniy natijalar va xatolar tanlangan tilda ko‘rsatiladi.

#### O‘qituvchi uchun buyruq

```bash
setup=$(mktemp)
curl -q -fsS https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/refs/heads/main/development/setup-classroom.sh -o "$setup" &&
  bash "$setup" teacher
```

Yangi muhit uchun GitHub’dagi joriy versiya ishlatiladi. Talaba sozlashni davom ettirganda, kerakli fayllar sozlash boshlangan versiyadan olinadi.

**O‘qituvchi** buyruqlarni o‘zining Learner Lab muhitida `teacher` argumenti bilan bajaradi. Til tanlangach, sozlash va tekshirish avtomatik davom etadi. Oxirida ekranda ko‘rsatilgan umumiy ro‘yxatdan o‘tish kodini faqat kurs qatnashchilariga yuboring.

#### Talaba uchun buyruq

Quyidagi buyruqlarni o‘zingizning talaba Learner Lab muhitingizdagi CloudShell’ga (`us-east-1`) o‘zgartirmasdan joylang.

```bash
setup=$(mktemp)
curl -q -fsS https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/refs/heads/main/development/setup-classroom.sh -o "$setup" &&
  bash "$setup" student
```

Tilni tanlang, o‘qituvchi bergan umumiy ro‘yxatdan o‘tish kodini nusxalab kiriting va oraliq server uchun RDP parolini belgilang. Kiritilgan qiymatlar ekranda ko‘rinmaydi. Skript alohida Lab ID va baholash tokenini yaratadi. CloudFormation beshta EC2 instansini yaratadi. Skript dars fayllarini joylab, ichki SSH aloqasini tekshirgach, oraliq serverdan o‘qituvchining baholash API’siga sinov natijasini yuboradi.

Skript GitHub’da belgilangan paket versiyalari va SHA-256 qiymatlarini tekshiradi. Paketlarni CloudShell va AWS Systems Manager orqali ichki paket tarqatish serveriga yuboradi. O‘quv materiallari uchun S3 yaratish va Class ID kiritish shart emas.

O‘qituvchining yangi steki `jdu-web-infrastructure-teacher`, talabaniki esa `jdu-web-infrastructure-student-<Lab ID>` deb nomlanadi.

Yangi tartib Learner Lab’da boshidan oxirigacha hali tekshirilmagan. Ta’lim muassasasining Google hisobi bilan kirish va Web Portal orqali topshiriqlarni baholash alohida sozlanadi.

## S3 orqali tarqatishning avvalgi tartibi

### O‘qituvchi uchun

AWS Academy’da kerakli guruhning **o‘qituvchi uchun Learner Lab** muhitini ishga tushiring. Quyidagi buyruqlarni Shimoliy Virjiniya (`us-east-1`) regionidagi CloudShell’da bajaring.

```bash
url='https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/8b080f940957fe3898e65d5a31978f581aa86dd0/development/01_roles/cyber_security/tools/web_lab_teacher/install_teacher.py'
script=$(mktemp) &&
  curl -fsS "$url" -o "$script" &&
  printf '%s  %s\n' 'f943d815e52f38442e292ffd5f74a15b4327c00618a2b8afa3a0d97ee384a2a6' "$script" |
    sha256sum -c - &&
  python3 -B "$script"
```

Skript AWS hisobini joriy CloudShell seansidan aniqlaydi va CloudFormation orqali o‘qituvchi uchun VPC, EC2 instansi, doimiy IPv4 manzili, topshiriqlarni tekshirish API’si, DynamoDB jadvali va yopiq S3 saqlash joyini yaratadi. Class ID yoki AWS hisob raqamini kiritish shart emas. Skript muhit yaratilgach, API bilan HTTPS aloqasini va saqlash joylarining sozlamalarini tekshiradi. Resurslarni yaratmasdan dastlabki tekshiruvni bajarish uchun oxirgi qatorga `--plan` qo‘shing.

Talabalarni amaliyotga taklif qilishdan oldin o‘quv materiallarini yuklang, yangi tekshirish API’siga mos imzolangan paketni tayyorlang va ta’lim muassasasining Google hisobi bilan kiriladigan topshiriqlar sahifasini sozlang. [O‘qituvchi skripti haqida batafsil (yapon tilida)](development/01_roles/cyber_security/tools/web_lab_teacher/README.md) · [Dastlabki tarqatish va ro‘yxatdan o‘tkazish (yapon tilida)](course/labs/INITIAL-WORKFLOW.md)

### Talaba uchun

O‘zingizga biriktirilgan **talaba uchun Learner Lab** muhitini ishga tushiring va o‘sha regionda CloudShell’ni oching. O‘qituvchi ko‘rsatgan umumiy paketning imzosi va amal qilish muddatini tekshiring hamda shaxsingizga mo‘ljallangan shifrlangan paketni oling. So‘ng dastlabki sozlash yo‘riqnomasiga amal qilib, CloudFormation orqali beshta EC2 instansini yarating va muhitni topshiriqlarni tekshirish tizimida ro‘yxatdan o‘tkazing. [Dastlabki sozlash (yapon tilida)](course/labs/INITIAL-WORKFLOW.md) · [Umumiy tayyorgarlik P0](course/labs/docs/uz/p0.md)

## O‘rganishni boshlash

- [Kursning maqsadi va kerakli bilimlar](course/learning-outcomes.md)
- [O‘rganish ketma-ketligi va kutiladigan natijalar](course/roadmap.md)
- [Darslikni o‘qish ketma-ketligi va kerakli bilimlar](course/textbook-plan.md)
- [13 bob va ularning bo‘limlari rejasi](course/textbook-outline.md)
- [Darslik va boblarning topshiriqlarga mosligi (13 bob)](course/textbook/README.md)
- [WEB-00 Yakuniy arxitektura](modules/WEB-00-overview/README.md)
- [WEB-02 HTTP va Nginx](modules/WEB-02-http/README.md)

Avvalgi 8-bob olib tashlangan va darslik boblari 1 dan 13 gacha ketma-ket raqamlangan. Amaliy topshiriqlarda P3/M3 raqamlari o‘tkazib yuborilgan. Baholanadigan beshta topshiriq uchun jami 59 ball beriladi.

## P mashqlari va M mustaqil topshiriqlari

2026-yil 13-noyabrda [mashqlar va mustaqil topshiriqlar](course/labs/README.md) P3/M3 chiqarilgan holda alohida sahifalarga joylandi. Yapon, rus va o‘zbek tillarida misollar bilan 44 qadam va 59 ballik baholash mezonlari mavjud. Dastlabki sozlashdan so‘ng [topshiriqlarni tekshirish va natijalarni ko‘rish uchun veb-portaldan foydalaning](course/labs/docs/uz/portal.md). Materiallarning ZIP arxiviga A4 formatdagi PDF va internetsiz ko‘rish uchun HTML ham kiritilgan.

r1.1 tahririda avvalgi 49 qadamdagi buyruq va sozlamalarning izohlari, har bir P mashqining ishlash tamoyillari, o‘zini tekshirish savollari, tarmoq yo‘nalishlari va buyruq natijalarini o‘qish misollari qo‘shilgan. M topshiriqlarida ishni va tekshirish usullarini mustaqil rejalash bo‘yicha ko‘rsatmalar berilgan.

r3 imzolangan paketi O‘zbekiston vaqti (UZT) bilan 2027-yil 31-yanvar oxirigacha amal qiladi. 3-noyabr kuni CloudFormation orqali beshta yangi instans yaratish, dastlabki ro‘yxatdan o‘tkazish, materiallarni joylashtirish, Google va AWS hisoblarini bog‘lash, SSM orqali P1/M1 sozlamalarini bajarish, brauzerda tekshirish, baholarni saqlash va o‘qituvchiga ko‘rsatish sinovdan o‘tkazildi. [Birinchi ishga tushirish tartibi va buyruqlar](course/labs/INITIAL-WORKFLOW.md). **Talabalar hali barcha 44 qadamni sinov tariqasida bosib o‘tmagan. Ona tili sohiblarining tahriri va o‘qituvchining ko‘zdan kechirishi ham bajarilmagan.** Bajarilgan tekshiruvlar doirasi [tekshiruv hisobotida](course/labs/VALIDATION.md) ko‘rsatilgan. Butun kurs uchun `CLASS_READY` qiymati `false` holatida.

## Materiallarni tayyorlovchilar uchun

- [Muhit yaratish, tarqatish, topshiriqlarni tekshirish va o‘qituvchi tizimining kodi](development/README.md)
- [Talabaning beshta instansi uchun CloudFormation](development/templates/web-lab-student.template.json) / [O‘qituvchining tekshirish API’si uchun CloudFormation](development/templates/web-teacher-d11.template.json)
- [Material tayyorlash qoidalari](COURSE_POLICY.md)
- [Sun’iy intellekt yordamchisi uchun ko‘rsatmalar](AGENTS.md)
- [Materiallarni yig‘ish va tekshirish tartibi](BUILD.md)

O‘qituvchiga mo‘ljallangan javoblar, talabalar haqidagi ma’lumotlar va autentifikatsiya ma’lumotlari repozitoriydan tashqarida saqlanadi. Tashqi materiallardan foydalanilganda manba va tekshirish sanasi ko‘rsatiladi.
