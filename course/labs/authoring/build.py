"""Generate the P/M handbooks from parallel prose and one frozen signed assessment registry."""
import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import textwrap
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path('C:/Users/user/Documents/JUD project')
DEPS = PROJECT / '.codex_tmp/d12deps'
if DEPS.is_dir():
    sys.path.insert(0, str(DEPS))
from markdown_it import MarkdownIt
from content import LANGS, T, PLACES, MODULES, MISSION_GUIDANCE
from checks import CHECKS

KIT = PROJECT / '03_knowledge/aws_official/web_lab_packages_2026-10-15/web-course-class193548-20261023-r2'
EXPECTED_REGISTRY = '3feeb3d8a9225e6e19e06f68367b07c6cb4a657f05818c146ccb22cfcd654c33'
DIST_ID = 'web-course-class193548-20261023-r2'
L = {
 'practice': T('Web演習：練習P0〜P6と詳しい操作例', 'Web Infrastructure: практика P0–P6 с подробными шагами', 'Web Infrastructure: P0–P6 mashqlar va batafsil qadamlar'),
 'missions': T('Web演習：自力課題M0〜M6', 'Web Infrastructure: самостоятельные задания M0–M6', 'Web Infrastructure: M0–M6 mustaqil topshiriqlar'),
 'goal': T('学ぶこと', 'Что изучаем', 'Nimani o‘rganamiz'),
 'problem': T('課題', 'Задание', 'Topshiriq'),
 'solution': T('操作例：一つずつ実行する', 'Пример решения: выполняйте по одному шагу', 'Yechim namunasi: bittadan bajaring'),
 'place': T('実行場所', 'Место выполнения', 'Bajarish joyi'),
 'why': T('目的と操作', 'Цель и действия', 'Maqsad va amallar'),
 'expect': T('期待する結果と読み方', 'Ожидаемый результат и его смысл', 'Kutilgan natija va ma’nosi'),
 'trouble': T('うまくいかないとき', 'Если не получилось', 'Ishlamasa'),
 'intro': T('使い方と共通の約束', 'Как пользоваться пособием', 'Qo‘llanmadan foydalanish'),
 'targets': T('対象・前提・準備', 'Среда и подготовка', 'Muhit va tayyorgarlik'),
 'requirements': T('完成要件', 'Требуемый результат', 'Tayyor holat talablari'),
 'checks': T('合格条件：採点check各1素点', 'Условия: 1 исходный балл за проверку', 'Shartlar: har tekshiruvga 1 xom ball'),
 'checkid': T('check ID（変更しない）', 'check ID (не менять)', 'check ID (o‘zgartirmang)'),
 'condition': T('満たすこと', 'Условие', 'Shart'),
 'submit': T('確認・提出', 'Проверка и отправка', 'Tekshirish va yuborish'),
 'resume': T('次回の再開・送信の再試行', 'Продолжение и повторная отправка', 'Davom ettirish va qayta yuborish'),
 'sources': T('根拠と使用版', 'Источники и версия', 'Manbalar va versiya'),
 'draft': T('教材初版・教師確認用。学生の最初からの通し試読は未実施。', 'Первая редакция для проверки преподавателем. Полное прохождение по пособию студентом ещё не проверено.', 'O‘qituvchi tekshiruvi uchun birinchi nashr. Talabaning qo‘llanma bo‘yicha boshidan oxirigacha o‘tishi hali tekshirilmagan.'),
 'translation': T('ロシア語・ウズベク語は日本語原稿と同じ手順・条件の翻訳初稿。母語話者校閲は未実施。', 'Русский и узбекский тексты синхронизированы с японским оригиналом. Редактура носителями языка ещё не выполнена.', 'Ruscha va o‘zbekcha matn yaponcha asl nusxa bilan bir xil qadam va shartlarga ega. Ona tili mutaxassisi tahriri hali bajarilmagan.'),
}

def emit_intro(lang, kind):
    out = [f'# {L[kind][lang]}', '', f'2026-10-23 | D12 P/M r1 | {DIST_ID}', '', L['draft'][lang], '', L['translation'][lang], '']
    out += [T('[日本語](../ja/' + kind + '.md) · [Русский](../ru/' + kind + '.md) · [O‘zbekcha](../uz/' + kind + '.md)',
              '[日本語](../ja/' + kind + '.md) · [Русский](../ru/' + kind + '.md) · [O‘zbekcha](../uz/' + kind + '.md)',
              '[日本語](../ja/' + kind + '.md) · [Русский](../ru/' + kind + '.md) · [O‘zbekcha](../uz/' + kind + '.md)')[lang], '']
    out += ['## ' + L['intro'][lang], '', T(
      'まず各Pの課題文を読み、必要なら詳しい操作例を一段ずつ使う。Pは練習で成績に加算しない。Mは別の対象・値で自分で構築する。課題は授業回番号ではなく、自分の進度で進める。Pの完了はMの合格に置き換わらない。',
      'Сначала прочитайте задание P; при необходимости проходите подробный пример по шагам. P — тренировка без оценочных баллов. В M самостоятельно используйте другие объекты/значения. Номера заданий не являются номерами занятий; идите в своём темпе. Выполнение P не означает выполнение M.',
      'Avval P topshirig‘ini o‘qing; kerak bo‘lsa batafsil namunani qadam-baqadam bajaring. P — bahoga ball qo‘shmaydigan mashq. M da boshqa obyekt/qiymatni mustaqil quring. Topshiriq raqami dars raqami emas; o‘z sur’atingizda ishlang. P tugashi M bajarilganini anglatmaydi.')[lang], '',
      'P0 → M0 → P1 → M1 → P2 → M2 → P3 → M3 → P4 → M4 → P5 → P6 → M5 → M6', '',
      T('P5にもM2のDNSが必要。P4はIP指定だが、アプリはdb.lab.testを使う。練習profileから本課題profileへ切り替える前にP6でsetupを終了する。Pは任意の練習で、採点は各Mの現在の前提を検査する。',
        'P5 требует DNS из M2. P4 подключается по IP, а приложение — по db.lab.test. Перед переключением practice → mission завершите setup в P6. P — добровольная тренировка; checker оценивает текущие предпосылки M.',
        'P5 uchun ham M2 DNS kerak. P4 IP bilan ulanadi, app esa db.lab.test dan foydalanadi. Practice → mission almashishdan oldin P6 da setup ni tugating. P ixtiyoriy mashq; checker M ning joriy old shartlarini tekshiradi.')[lang], '',
      T('M1=8、M2=13、M3=3、M4=9、M5=13、M6=16、合計62素点。M0は0点。本人実演・backup/restore・追加disk・アプリ開発は課さない。科目25点への換算は教師が別に行う。再提出は教師が案内する締切まで可能。別々の回のPASSを合算したり自動最高点選択はしない。',
        'M1=8, M2=13, M3=3, M4=9, M5=13, M6=16: всего 62 исходных балла. M0=0. Нет личной демонстрации, backup/restore, дополнительных дисков и разработки приложения. Пересчёт в 25 баллов делает преподаватель отдельно. Повторные отправки возможны до объявленного срока. PASS разных попыток не объединяются; максимум автоматически не выбирается.',
        'M1=8, M2=13, M3=3, M4=9, M5=13, M6=16: jami 62 xom ball. M0=0. Shaxsiy namoyish, backup/restore, qo‘shimcha disk va app dasturlash talab qilinmaydi. 25 ballga o‘tkazishni o‘qituvchi alohida qiladi. E’lon qilingan muddatgacha qayta yuborish mumkin. Turli urinish PASS lari qo‘shilmaydi; eng yuqori ball avtomatik tanlanmaydi.')[lang], '',
      '## ' + L['targets'][lang], '',
      T('初期配布の署名確認、新規5台または既存環境へのinstall、内部SSHと個別採点登録までを先に完了する。初期配布の手順は教材zipのdistribution/STUDENT.mdを読む。秘密鍵を共有Windowsへ置かず、CloudShellは本人Academy accountの中で使う。教師は本人用の匿名Lab ID・署名fingerprint・有効期限を案内する。',
        'Сначала завершите проверку подписи начального комплекта, создание пяти узлов либо install в существующую среду, внутренний SSH и личную регистрацию. Инструкция — distribution/STUDENT.md в zip. Не храните приватные ключи в общем Windows; используйте CloudShell личного Academy account. Преподаватель выдаёт личный анонимный Lab ID, fingerprint и срок действия.',
        'Avval boshlang‘ich tarqatma imzosi, yangi beshta server yoki mavjud muhitga install, ichki SSH va shaxsiy ro‘yxatni tugating. Yo‘riqnoma zip dagi distribution/STUDENT.md da. Maxfiy kalitni umumiy Windows ga saqlamang; shaxsiy Academy hisobining CloudShell idan foydalaning. O‘qituvchi anonim Lab ID, fingerprint va muddatni beradi.')[lang], '',
      T('共通IP表。public IPv4は固定しない。AWS regionはus-east-1、Ubuntu24.04/amd64。RDPはlabuser、SSMはssm-user、内部SSHはubuntu。user名とサーバー役割を混同しない。',
        'Общие private IP ниже; public IPv4 не фиксируется. AWS region us-east-1, Ubuntu24.04/amd64. RDP: labuser; SSM: ssm-user; внутренний SSH: ubuntu. Не путайте пользователя и роль сервера.',
        'Umumiy private IP quyida; public IPv4 doimiy emas. AWS region us-east-1, Ubuntu24.04/amd64. RDP: labuser; SSM: ssm-user; ichki SSH: ubuntu. User nomi va server rolini adashtirmang.')[lang], '',
      '| Role | Private IPv4 | ' + T('用途', 'Назначение', 'Vazifa')[lang] + ' |', '| --- | --- | --- |',
      '| bastion | 10.20.1.10 | RDP3389 / Firefox / SSH |', '| web | 10.20.1.20 | HTTP80 / private8080 / loopback8000 |',
      '| dns | 10.20.2.10 | BIND UDP/TCP53 |', '| db | 10.20.2.20 | PostgreSQL5432 |', '| repo | 10.20.2.30 | ' + T('事前保存した署名資源のHTTP80', 'HTTP80 с заранее сохранёнными подписанными ресурсами', 'Oldindan saqlangan imzolangan resurslar HTTP80')[lang] + ' |', '',
      T('各Ubuntuへ入る操作：CloudShellで aws ssm start-session --target i-自分の対象ID。接続直後にid -unとbootstrap.jsonのroleを確認する。サーバーを替えるときはexitを1回でCloudShellへ戻り、次のIDでstart-sessionする。CloudShellの変数は接続先へ自動コピーされない。SSMのssm-userはsudo可能。RDPのlabuserはsudo管理者ではない。',
        'Для входа в каждый Ubuntu выполните в CloudShell aws ssm start-session --target i-СВОЙ-ID. Сразу проверяйте id -un и role из bootstrap.json. Для смены сервера один exit возвращает в CloudShell; затем подключайтесь к следующему ID. Переменные CloudShell не копируются на узел. ssm-user может sudo; RDP-пользователь labuser не администратор sudo.',
        'Har Ubuntu ga kirish uchun CloudShell da aws ssm start-session --target i-OZ-ID bajaring. Darhol id -un va bootstrap.json dagi role ni tekshiring. Server almashtirishda bitta exit bilan CloudShell ga qaytib keyingi ID ga ulang. CloudShell o‘zgaruvchilari serverga avtomatik ko‘chmaydi. ssm-user sudo qila oladi; RDP labuser sudo admin emas.')[lang], '',
      T('nanoの編集：file名を指定して開く→本文を入力→Ctrl+O→Enterで保存→Ctrl+Xで終了。設定fileの枠はshell commandではない。psqlに入るとpromptが変わる。SQL/\\passwordはその中へ入力し、\\qでUbuntuへ戻る。失敗したcommandの次へ進まず、期待結果を確認する。',
        'Редактор nano: открыть файл → ввести текст → Ctrl+O → Enter сохранить → Ctrl+X выйти. Блок конфигурации не выполняется как shell-команда. В psql меняется prompt; SQL/\\password вводятся внутри, \\q возвращает в Ubuntu. Не продолжайте после ошибки без проверки результата.',
        'Nano: faylni ochish → matn yozish → Ctrl+O → Enter bilan saqlash → Ctrl+X bilan chiqish. Sozlama bloki shell buyrug‘i emas. Psql ichida prompt o‘zgaradi; SQL/\\password shu yerga yoziladi, \\q Ubuntu ga qaytaradi. Xatodan keyin natijani tekshirmay davom etmang.')[lang], '']
    return out

def emit_end(lang):
    return ['## ' + L['resume'][lang], '', T(
      '次回は本人のLabと同じ5台を起動し、running/SSM Onlineと現在の公開IPを確認する。CloudShellでLAB_ID/COURSE_ID/INSTALLを再設定し、P0のactivate.shを読む。M0 --no-submitで準備確認する。作成・鍵生成・登録を繰り返さず、期限切れは教師へ更新を依頼する。',
      'На следующем занятии запустите свой Lab и те же пять узлов, проверьте running/SSM Online и текущие public IP. В CloudShell заново задайте LAB_ID/COURSE_ID/INSTALL, прочитайте activate.sh как в P0 и выполните M0 --no-submit. Не повторяйте создание/ключи/регистрацию; при истечении срока запросите обновление.',
      'Keyingi safar shaxsiy Lab va ayni besh serverni ishga tushirib running/SSM Online hamda joriy public IP ni tekshiring. CloudShell da LAB_ID/COURSE_ID/INSTALL ni qayta belgilang, P0 dagi activate.sh ni o‘qing va M0 --no-submit bajaring. Yaratish/kalit/ro‘yxatni takrorlamang; muddat o‘tsa yangilashni so‘rang.')[lang], '',
      T('STOREDは教師受付済み。PENDINGなら表示された元request-idを元の課題と一緒に--retryへ渡す。--no-submitの自己確認は提出にならない。UNKNOWNは観測不能で、0点や合格を勝手に確定しない。現在のUNKNOWNで過去の評価可能な提出は消えないが、現在の前提が満たされる意味ではない。最新の評価可能な1回を参照し、最高点や回をまたぐPASSの寄せ集めを使わない。',
        'STORED означает приём преподавателем. Для PENDING используйте исходный request-id и то же задание с --retry. --no-submit не является отправкой. UNKNOWN — измерение невозможно, а не автоматический ноль или успех. Оно не удаляет прежнюю оцениваемую попытку, но не доказывает текущую готовность. Используется последняя полностью оцениваемая попытка, не максимальная и не сумма PASS разных запусков.',
        'STORED — o‘qituvchi qabul qilgan. PENDING bo‘lsa asl request-id va ayni topshiriq bilan --retry ishlating. --no-submit yuborish emas. UNKNOWN — o‘lchab bo‘lmagan, avtomatik nol yoki muvaffaqiyat emas. U oldingi baholanadigan urinishni o‘chirmaydi, lekin hozir tayyorlikni isbotlamaydi. Oxirgi to‘liq baholanadigan urinish olinadi; maksimum yoki turli urinish PASS yig‘indisi emas.')[lang], '',
      '```bash', "jdu-web-check M2 --retry 'YOUR-ORIGINAL-REQUEST-ID'", 'jdu-web-my-progress', '```', '',
      T('本人用URLは自分だけで開く。password/token/cookie/秘密鍵/env本文/教師URLを提出物や会話へ送らない。画面撮影は秘密欄を含めない。画面だけの操作が失敗した場合も、他人のLabで試さない。',
        'Личный URL открывайте только сами. Не отправляйте в отчёт или чат пароль/token/cookie/ключ/env/URL преподавателя. Снимки не должны содержать секретов. Не проверяйте ошибки на чужом Lab.',
        'Shaxsiy URL ni faqat o‘zingiz oching. Hisobot/chat ga parol/token/cookie/kalit/env/o‘qituvchi URL ini yubormang. Screenshot da maxfiy maydon bo‘lmasin. Xatoni boshqa talaba Lab ida sinamang.')[lang], '',
      '## ' + L['sources'][lang], '',
      T('採点条件は同梱の固定registryと各Mの表を正本とする。原稿は受入済み実装・資源に照合したが、この詳細手順を新規学生が最初から辿る試験は未実施。成功passwordの本人手入力と、app導入後の全5台停止再開も追加受入が残る。教材編集だけで全授業のCLASS_READYをtrueにしない。',
        'Критерии основаны на фиксированном registry и таблицах M. Текст сверен с принятой реализацией, но новый студент ещё не прошёл эти подробные шаги с нуля. Ещё нужны приёмка успешного ручного ввода пароля и stop/start всех пяти узлов после установки приложения. Редактирование пособия не делает CLASS_READY=true.',
        'Shartlar belgilangan registry va M jadvallariga asoslangan. Matn qabul qilingan amalga oshirish bilan solishtirildi, ammo yangi talaba bu batafsil qadamlarni boshidan hali bajarmagan. To‘g‘ri parolni shaxsan kiritish va app o‘rnatilgach besh server stop/start qabul tekshiruvi qolgan. Qo‘llanma tahriri CLASS_READY=true degani emas.')[lang], '',
      T('使用版', 'Версии', 'Versiyalar')[lang] + ': ' + DIST_ID + '; web-d11-2026-10-r1; registry SHA256 ' + EXPECTED_REGISTRY + '.', '',
      T('署名期限：2026-10-27 14:24:57 UZT。取得URLの期限と署名の期限は別。期限を書き換えて続行しない。以下は一般機能の一次資料（2026-10-23確認）。Lab固有のIP・課題・点数は本教材の仕様。',
        'Подпись действует до 2026-10-27 14:24:57 UZT. Срок URL загрузки отличается от срока подписи; не меняйте даты для обхода. Ниже первичные документы общих функций, проверенные 2026-10-23. IP, задания и баллы Lab определены этим курсом.',
        'Imzo muddati: 2026-10-27 14:24:57 UZT. Yuklash URL muddati imzo muddatidan farq qiladi; chetlab o‘tish uchun sanani o‘zgartirmang. Quyida 2026-10-23 tekshirilgan umumiy funksiyalarning birlamchi hujjatlari. Lab IP, topshiriq va ballari ushbu kurs tomonidan belgilanadi.')[lang], '',
      '- [Nginx Beginner’s Guide](https://nginx.org/en/docs/beginners_guide.html)',
      '- [BIND 9: configurations and zones](https://bind9.readthedocs.io/en/v9.18.39/chapter3.html)',
      '- [PostgreSQL 16: pg_hba.conf](https://www.postgresql.org/docs/16/auth-pg-hba-conf.html)',
      '- [EC2 instance states](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html)', '']

def task_spec(task, reg, lang):
    out = []
    if 'expected' in task:
        e = task['expected']
        if 'file' in e:
            out += ['- File: ' + e['file']]
        if 'path' in e:
            out += ['- URL path: ' + e['path']]
        if 'body' in e or 'body_template' in e:
            out += ['', '```text', (e.get('body') or e['body_template']).rstrip('\n'), '```', '']
        if 'records' in e:
            out += ['| DNS name | A / IPv4 |', '| --- | --- |']
            out += [f'| {name} | {ip} |' for name, ip in e['records'].items()]
            out += ['']
    if task.get('profile'):
        profile = reg['profiles'][task['profile']]
        out += ['- Profile: ' + task['profile'], '- Database: ' + profile['db_name'], '- Setup role: ' + profile['setup_role'], '- Runtime role: ' + profile['runtime_role']]
        if task['id'][1:] in ('5', '6'):
            out += ['- Application administrator: ' + profile['app_admin'], '', '| code | name | quantity | location | is_public |', '| --- | --- | --- | --- | --- |']
            out += [f"| {r['code']} | {r['name']} | {r['quantity']} | {r['location']} | {str(r['is_public']).lower()} |" for r in profile['records']]
            out += ['']
    return out

def shell_lines(source):
    """Wrap only unquoted shell separators, adding real continuation characters."""
    out=[]
    for original in source.splitlines():
        line=original
        while len(line)>88 and not line.lstrip().startswith('#'):
            quote=None;escaped=False;spaces=[]
            for i,char in enumerate(line):
                if escaped:escaped=False;continue
                if char=='\\' and quote!="'":escaped=True;continue
                if quote:
                    if char==quote:quote=None
                elif char in ('"',"'"):quote=char
                elif char==' ' and 12<i<86:spaces.append(i)
            if not spaces:break
            at=spaces[-1]
            out.append(line[:at]+' \\')
            line='  '+line[at+1:]
        out.append(line)
    return '\n'.join(out)

def make_markdown(reg, lang, kind):
    out = emit_intro(lang, kind)
    tasks = {t['id']: t for t in reg['tasks']}
    if kind == 'practice':
        for m in MODULES:
            out += ['## ' + m['id'] + ' ' + m['title'][lang], '', '### ' + L['goal'][lang], '', m['goals'][lang], '', '### ' + L['problem'][lang], '', m['problem'][lang], '']
            out += task_spec(tasks[m['id']], reg, lang)
            out += ['### ' + L['solution'][lang], '']
            for i, s in enumerate(m['steps'], 1):
                out += [f"#### {m['id']}.{i} {s['title'][lang]}", '', '**' + L['place'][lang] + ':** ' + PLACES[s['place']][lang], '', '**' + L['why'][lang] + ':** ' + s['why'][lang], '']
                if s['code']:
                    fence = 'bash'
                    if s['place']=='pc':
                        fence='powershell'
                    if (m['id'], i) in {('P2', 2), ('P2', 3), ('P2', 6), ('P4', 2), ('P4', 3), ('P5', 9)}:
                        fence = 'text'
                    if (m['id'], i) in {('P4', 6), ('P6', 1)}:
                        fence = 'text'
                    out += ['```' + fence, shell_lines(s['code']) if fence=='bash' else s['code'], '```', '']
                out += ['**' + L['expect'][lang] + ':** ' + s['expect'][lang], '', '**' + L['trouble'][lang] + ':** ' + s['trouble'][lang], '']
    else:
        for number in range(7):
            task = tasks['M' + str(number)]
            title = MODULES[number]['title'][lang]
            out += [f"## {task['id']} {title} ({task['raw_points_max']})", '', '### ' + L['requirements'][lang], '', MISSION_GUIDANCE[task['id']][lang], '']
            out += task_spec(task, reg, lang)
            if task['requires_current']:
                out += ['- ' + T('現在必要な前提', 'Текущие предпосылки', 'Joriy old shartlar')[lang] + ': ' + ', '.join(task['requires_current']), '']
            if task['id'] == 'M3':
                out += [T('本文の{lab_id}は自分の匿名Lab IDに置き換える。file0644/root:root、親directory0755/root:root。停止はWebのみ、同じ元instance/volumeで行う。', 'Замените {lab_id} своим анонимным ID. Файл 0644/root:root, каталог 0755/root:root. Останавливайте только тот же исходный Web/volume.', '{lab_id} ni o‘z anonim ID ga almashtiring. Fayl 0644/root:root, katalog 0755/root:root. Faqat ayni asl Web/volume ni to‘xtating.')[lang], '']
            if number:
                out += ['### ' + L['checks'][lang], '', '| ' + L['checkid'][lang] + ' | ' + L['condition'][lang] + ' |', '| --- | --- |']
                for cid in task['progress_scored_checks']:
                    text = reg['check_definitions'][cid]['pass_condition'] if lang == 'ja' else CHECKS[cid][lang]
                    out += [f'| {cid} | {text} |']
                out += ['', T('本人確認・管理・配布元・通信基盤・依存前提等の準備checkは上表の素点に加えない。必要前提が未完了なら、点が一部あっても次段階の準備完了ではない。', 'Проверки identity/управления/repo/сети/зависимостей не добавляют баллов. Частичные баллы не означают готовность следующего этапа при неисправных предпосылках.', 'Identity/boshqaruv/repo/tarmoq/bog‘liqlik tayyorlik tekshiruvlari ball qo‘shmaydi. Old shart ishlamasa, qisman ball keyingi bosqichga tayyorlik emas.')[lang], '']
            out += ['### ' + L['submit'][lang], '', '```bash', 'jdu-web-check ' + task['id'] + (' --functional' if number in (5,6) else ' --no-submit'), 'jdu-web-check ' + task['id'] if number not in (5,6) else '# STORED / PENDING: inspect delivery result', '```', '']
    out += emit_end(lang)
    return '\n'.join(out).replace('\u2013', '-').replace('\u2014', '-')

CSS = '''
:root{color-scheme:light;font:17px/1.8 system-ui,sans-serif;color:#172637;background:#eef2f6}
*{box-sizing:border-box}body{margin:0}header,main,footer{max-width:1000px;margin:auto;padding:1.5rem 2rem;background:white}
header{border-bottom:5px solid #126e70}header p{margin:0;color:#415569}nav{display:flex;flex-wrap:wrap;gap:1rem}
a{color:#085e80;text-underline-offset:.2em}a:focus-visible{outline:3px solid #b24a00;outline-offset:4px}
.skip{position:absolute;left:-9999px}.skip:focus{position:fixed;left:1rem;top:1rem;background:white;padding:.5rem;z-index:2}
h1{font-size:2rem;line-height:1.35}h2{margin-top:3rem;padding-top:.7rem;border-top:3px solid #126e70;font-size:1.55rem}
h3{font-size:1.2rem;margin-top:2rem}h4{font-size:1.08rem;margin-top:2rem;color:#134c61}
pre{background:#f0f4f7;border-left:4px solid #126e70;padding:1rem;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55;font: .83rem/1.6 Consolas,monospace}
code{font-family:Consolas,monospace}table{width:100%;border-collapse:collapse;font-size:.9rem;margin:1rem 0;table-layout:fixed}
th,td{border:1px solid #b8c6d0;padding:.5rem;vertical-align:top;overflow-wrap:anywhere}th{background:#e8f1f3;text-align:start}
p,li{overflow-wrap:anywhere}footer{font-size:.85rem;color:#415569;border-top:1px solid #b8c6d0}
@media(max-width:600px){header,main,footer{padding:1rem}h1{font-size:1.6rem}}
@media print{body{background:white;font-size:10pt}header,main,footer{max-width:none;padding:0}nav,.skip{display:none}h2{break-before:page}h2,h3,h4{break-after:avoid}pre{white-space:pre-wrap;break-inside:auto}tr{break-inside:avoid}}
'''

def render_html(md, lang, kind):
    parser = MarkdownIt('commonmark', {'html': False}).enable('table')
    body = parser.render(md)
    body = body.replace('<th>', '<th scope="col">')
    # Generated output preserves the same folder hierarchy as Markdown.
    body = re.sub(r'href="([^"#]+)\.md(#[^"]*)?"', lambda m: 'href="' + m[1] + '.html' + (m[2] or '') + '"', body)
    toc = []
    def heading(m):
        slug = 'section-' + str(len(toc) + 1)
        toc.append((slug, m[1]))
        return f'<h2 id="{slug}">{m[1]}</h2>'
    body = re.sub(r'<h2>(.*?)</h2>', heading, body)
    links = ' · '.join(f'<a href="#{slug}">{text}</a>' for slug, text in toc)
    title = html.escape(L[kind][lang])
    return f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head><body><a class="skip" href="#content">{html.escape(L["intro"][lang])}</a><header><p>JDU · Web Infrastructure · D12 P/M r1</p><nav aria-label="Contents">{links}</nav></header><main id="content" tabindex="-1">{body}</main><footer>{DIST_ID} · 62 raw points · 2026-10-23</footer></body></html>'

def make_pdf(md, lang, target):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, Table, TableStyle, CondPageBreak
    for name, path in [('JP','msgothic.ttc'), ('Body','arial.ttf'), ('Mono','consola.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, 'C:/Windows/Fonts/' + path, subfontIndex=0))
    body_font = 'JP' if lang == 'ja' else 'Body'
    pdfmetrics.registerFontFamily(body_font, normal=body_font, bold=body_font, italic=body_font, boldItalic=body_font)
    width = A4[0] - 88
    styles = {0: ParagraphStyle('body', fontName=body_font, fontSize=10, leading=15.8, spaceAfter=8, wordWrap='CJK' if lang=='ja' else None,allowWidows=0,allowOrphans=0)}
    for n, size in [(1,20),(2,16),(3,12),(4,11)]:
        styles[n] = ParagraphStyle('h'+str(n), parent=styles[0], fontSize=size, leading=size*1.45,
            textColor=colors.HexColor('#134c61'), spaceBefore=14 if n>1 else 4, spaceAfter=9, keepWithNext=True)
    code_style = ParagraphStyle('code', fontName='Mono', fontSize=8.1, leading=11.3, leftIndent=7, rightIndent=3,
        spaceBefore=5, spaceAfter=9, backColor=colors.HexColor('#f0f4f7'), borderPadding=5)
    small = ParagraphStyle('table', parent=styles[0], fontSize=8.5, leading=12.7, spaceAfter=0)
    parser = MarkdownIt('commonmark', {'html':False}).enable('table')
    tokens = parser.parse(md)
    def inline(token):
        result=[]
        for c in token.children or []:
            if c.type=='text':
                value=html.escape(c.content)
                if lang!='ja':
                    value=re.sub(r'[\u3000-\u30ff\u3400-\u9fff\uff00-\uffef]+',lambda m:'<font name="JP">'+m[0]+'</font>',value)
                result.append(value)
            elif c.type=='code_inline': result.append('<font name="Mono">'+html.escape(c.content)+'</font>')
            elif c.type in ('softbreak','hardbreak'): result.append('<br/>')
            elif c.type=='strong_open': result.append('<b>')
            elif c.type=='strong_close': result.append('</b>')
            elif c.type=='em_open': result.append('<i>')
            elif c.type=='em_close': result.append('</i>')
            elif c.type=='link_open':
                href=c.attrGet('href')
                result.append('<a href="'+html.escape(href,quote=True)+'" color="#085e80">' if href.startswith('https://') else '')
            elif c.type=='link_close':
                # Only external links are active in PDF; index/HTML keep local navigation.
                j=(token.children or []).index(c)
                opened=next((x for x in reversed(token.children[:j]) if x.type=='link_open'),None)
                result.append('</a>' if opened and opened.attrGet('href').startswith('https://') else '')
        return ''.join(result)
    flow=[];i=0;list_depth=0
    while i<len(tokens):
        t=tokens[i]
        if t.type=='heading_open':
            level=int(t.tag[1:]); text=tokens[i+1].content
            if level==2:
                flow.append(CondPageBreak(210))
            if level==4:
                flow.append(CondPageBreak(160))
            flow.append(Paragraph(html.escape(text),styles[level]));i+=3;continue
        if t.type=='paragraph_open':
            value=inline(tokens[i+1])
            if list_depth:value='• '+value
            flow.append(Paragraph(value,styles[0]));i+=3;continue
        if t.type in ('bullet_list_open','ordered_list_open'):list_depth+=1
        if t.type in ('bullet_list_close','ordered_list_close'):list_depth-=1
        if t.type=='fence':
            lines=[]
            for line in t.content.rstrip('\n').split('\n'):
                # Printing wraps visually; source MD/HTML keeps exact commands.
                lines.extend(textwrap.wrap(line, width=96, replace_whitespace=False, drop_whitespace=False,
                    break_long_words=True, break_on_hyphens=False) or [''])
            flow.append(Preformatted('\n'.join(lines),code_style))
        if t.type=='table_open':
            rows=[];row=[];j=i+1
            while tokens[j].type!='table_close':
                q=tokens[j]
                if q.type=='tr_open':row=[]
                if q.type=='inline':row.append(Paragraph(inline(q),small))
                if q.type=='tr_close':rows.append(row)
                j+=1
            cols=len(rows[0]); widths=([width*.36,width*.64] if cols==2 else [width/cols]*cols)
            table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f1f3')),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#b8c6d0')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            flow.extend([table,Spacer(1,10)]);i=j
        i+=1
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(body_font,8);canvas.setFillColor(colors.HexColor('#415569'))
        canvas.drawString(44,27,'JDU Web Infrastructure · D12 P/M r1 · '+lang.upper())
        canvas.drawRightString(A4[0]-44,27,str(doc.page));canvas.restoreState()
    doc=SimpleDocTemplate(str(target),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=38,bottomMargin=43,
        title=md.splitlines()[0].removeprefix('# '),author='JDU',pageCompression=1)
    doc.build(flow,onFirstPage=footer,onLaterPages=footer)

def main():
    p=argparse.ArgumentParser();p.add_argument('--no-pdf',action='store_true');a=p.parse_args()
    reg_raw=(KIT/'assessment/assessment-registry.json').read_bytes()
    assert hashlib.sha256(reg_raw).hexdigest()==EXPECTED_REGISTRY
    reg=json.loads(reg_raw)
    assert set(CHECKS)=={c for t in reg['tasks'] if t['category']=='automated_mission' for c in t['progress_scored_checks']}
    for m in MODULES:
        for field in ('title','goals','problem'):
            assert set(m[field])==set(LANGS)
        for s in m['steps']:
            for field in ('title','why','expect','trouble'):
                assert set(s[field])==set(LANGS) and all(s[field].values())
    pins=dict(distribution_id=DIST_ID,registry_sha256=EXPECTED_REGISTRY,fingerprint='65EC6784750CCFA703BA7179519284E45155EC2A',
        import_pins={n:hashlib.sha256((KIT/n).read_bytes()).hexdigest() for n in ('student.py','release_tools.py')},
        resource_pins={'offline_assets.py':hashlib.sha256((ROOT/'resources/offline_assets.py').read_bytes()).hexdigest()})
    (ROOT/'resources/release-map.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf-8',newline='\n')
    outputs=[]
    for lang in LANGS:
        for kind in ('practice','missions'):
            folder=ROOT/'docs'/lang;folder.mkdir(parents=True,exist_ok=True)
            md=make_markdown(reg,lang,kind)
            (folder/(kind+'.md')).write_text(md,encoding='utf-8',newline='\n')
            out=ROOT/'output/html'/lang;out.mkdir(parents=True,exist_ok=True)
            (out/(kind+'.html')).write_text(render_html(md,lang,kind),encoding='utf-8',newline='\n')
            if not a.no_pdf:
                out=ROOT/'output/pdf';out.mkdir(parents=True,exist_ok=True)
                path=out/f'web_lab_{kind}_{lang}.pdf'
                make_pdf(md,lang,path)
                outputs.append(path.name)
    # Keep accepted initial distribution instructions as a byte-for-byte reference copy.
    for sub in ('', 'foundation'):
        for name in ('STUDENT.md','TEACHER.md'):
            dest=ROOT/'distribution'/sub/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((KIT/sub/name).read_bytes())
    # Internal links in these reference instructions resolve to original signed tools,
    # not a duplicate executable distribution inside this teaching archive.
    # The reference handouts are read in the signed course kit, not executed here.
    downloads=KIT.parent/(DIST_ID+'-download')
    for name in ('jdu-web-course.tar.gz','jdu-web-course.tar.gz.asc','package-signing-public.asc'):
        (ROOT/'distribution'/name).write_bytes((downloads/name).read_bytes())
    links=[]
    for lang in LANGS:
        label={'ja':'日本語','ru':'Русский','uz':'O‘zbekcha'}[lang]
        links.append(f'<article><h2>{label}</h2><p><a href="{lang}/practice.html">P0–P6</a> · <a href="{lang}/missions.html">M0–M6</a></p><p><a href="../pdf/web_lab_practice_{lang}.pdf">P PDF</a> · <a href="../pdf/web_lab_missions_{lang}.pdf">M PDF</a></p></article>')
    (ROOT/'output/html/index.html').write_text('<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>JDU Web P/M 教材</title><style>'+CSS+'</style></head><body><main><h1>Web Infrastructure · P / M</h1><p>手順付き練習と自力課題 / Практика и задания / Mashqlar va topshiriqlar</p><p>2026-10-23 · 教師確認用初版 / Для проверки преподавателем / O‘qituvchi tekshiruvi uchun</p>'+''.join(links)+'<p>署名版の期限: 2026-10-27 14:24:57 UZT</p></main></body></html>',encoding='utf-8',newline='\n')
    package=ROOT/'output/web-lab-pm-r1.zip'
    members=[p for folder in ('docs','resources','distribution','output/html','output/pdf') for p in (ROOT/folder).rglob('*') if p.is_file()]
    members += [ROOT/'README.md',ROOT/'VALIDATION.md']
    if all(p.exists() for p in members):
        inventory={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in members}
        with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for path in sorted(members):
                z.write(path,'web-lab-pm-r1/'+path.relative_to(ROOT).as_posix())
            z.writestr('web-lab-pm-r1/TEACHING-FILE-HASHES.json',json.dumps(inventory,indent=2))
    print(json.dumps(dict(modules=len(MODULES),steps=sum(len(m['steps']) for m in MODULES),languages=list(LANGS),pdfs=outputs),ensure_ascii=False))

if __name__=='__main__':
    main()
