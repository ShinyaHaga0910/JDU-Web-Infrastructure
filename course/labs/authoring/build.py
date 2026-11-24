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
PROJECT = Path(os.environ.get('JDU_WEB_PROJECT_ROOT', str(Path(__file__).resolve().parents[3] / 'development')))
from markdown_it import MarkdownIt
from pages import write_pages, browser_check
from command_notes import annotated_blocks
from diagrams import diagram_markdown, lesson_files_markdown, write_diagrams
from content import LANGS, T, PLACES, MODULES, MISSION_GUIDANCE, RDP_STEPS
from checks import CHECKS
from curriculum import ACTIVE_NUMBERS, ACTIVE_ORDER, RAW_MAXIMUM, active_registry
from explanations import LABELS, READING, ROUTES, MISSION_PLAN, MODULE_NOTES, STEP_NOTES, OUTPUT_EXAMPLES
MODULES_BY_NUMBER = {int(m['id'][1:]): m for m in MODULES}
MODULES = [MODULES_BY_NUMBER[n] for n in ACTIVE_NUMBERS]
STEP_NOTES = {k: v for k, v in STEP_NOTES.items() if k.split('.')[0] in ACTIVE_ORDER}
CHECKS = {k: v for k, v in CHECKS.items() if not k.startswith('WEB04_')}

KIT = PROJECT / '03_knowledge/aws_official/web_lab_packages_2026-10-15/web-course-class193548-20261103-r3'
EXPECTED_REGISTRY = '3feeb3d8a9225e6e19e06f68367b07c6cb4a657f05818c146ccb22cfcd654c33'
DIST_ID = 'web-course-class193548-20261103-r3'
MATERIAL_REVISION = 'r1.5'
L = {
 'practice': T('Web演習：練習P0〜P6と詳しい操作例', 'Web Infrastructure: практика P0–P6 с подробными шагами', 'Web Infrastructure: P0–P6 mashqlar va batafsil qadamlar'),
 'missions': T('Web演習：自力課題M0〜M6', 'Web Infrastructure: самостоятельные задания M0–M6', 'Web Infrastructure: M0–M6 mustaqil topshiriqlar'),
 'goal': T('学ぶこと', 'Что изучаем', 'Nimani o‘rganamiz'),
 'problem': T('課題', 'Задание', 'Topshiriq'),
 'solution': T('解答例（操作手順）', 'Пример решения (порядок действий)', 'Yechim namunasi (bajarish tartibi)'),
 'work': T('このPractice{number}で作業すること', 'Что сделать в Practice{number}', 'Practice{number} da bajariladigan ishlar'),
 'place': T('実行環境', 'Среда выполнения', 'Bajarish muhiti'),
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
 'resume': T('次回の再開・結果の確認', 'Продолжение и результаты', 'Davom ettirish va natijalar'),
 'sources': T('参考資料', 'Справочные материалы', 'Ma’lumot manbalari'),
 'draft': T('教材初版・教師確認用。学生の最初からの通し試読は未実施。', 'Первая редакция для проверки преподавателем. Полное прохождение по пособию студентом ещё не проверено.', 'O‘qituvchi tekshiruvi uchun birinchi nashr. Talabaning qo‘llanma bo‘yicha boshidan oxirigacha o‘tishi hali tekshirilmagan.'),
 'translation': T('ロシア語・ウズベク語は日本語原稿と同じ手順・条件の翻訳初稿。母語話者校閲は未実施。', 'Русский и узбекский тексты синхронизированы с японским оригиналом. Редактура носителями языка ещё не выполнена.', 'Ruscha va o‘zbekcha matn yaponcha asl nusxa bilan bir xil qadam va shartlarga ega. Ona tili mutaxassisi tahriri hali bajarilmagan.'),
}

def emit_intro(lang, kind):
    out = [f'# {L[kind][lang]}', '', L['draft'][lang], '', L['translation'][lang], '']
    out += [T('[日本語](../ja/' + kind + '.md) · [Русский](../ru/' + kind + '.md) · [O‘zbekcha](../uz/' + kind + '.md)',
              '[日本語](../ja/' + kind + '.md) · [Русский](../ru/' + kind + '.md) · [O‘zbekcha](../uz/' + kind + '.md)',
              '[日本語](../ja/' + kind + '.md) · [Русский](../ru/' + kind + '.md) · [O‘zbekcha](../uz/' + kind + '.md)')[lang], '']
    out += ['## ' + L['intro'][lang], '', T(
      'まず各Pの課題文を読み、必要なら詳しい操作例を一段ずつ使う。Pは手順付きの練習である。Mは別の対象・値で自分で構築する。課題は授業回番号ではなく、自分の進度で進める。Pの完了はMの合格に置き換わらない。',
      'Сначала прочитайте задание P; при необходимости проходите подробный пример по шагам. P — тренировка с подробными шагами. В M самостоятельно используйте другие объекты/значения. Номера заданий не являются номерами занятий; идите в своём темпе. Выполнение P не означает выполнение M.',
      'Avval P topshirig‘ini o‘qing; kerak bo‘lsa batafsil namunani qadam-baqadam bajaring. P — batafsil qadamli mashq. M da boshqa obyekt/qiymatni mustaqil quring. Topshiriq raqami dars raqami emas; o‘z sur’atingizda ishlang. P tugashi M bajarilganini anglatmaydi.')[lang], '',
      'P0 → M0 → P1 → M1 → P2 → M2 → P4 → M4 → P5 → P6 → M5 → M6', '',
      T('P5にもM2のDNSが必要。P4ではIPと名前を使ったDB接続を練習する。アプリはdb.lab.testを使う。練習profileから本課題profileへ切り替える前にP6でsetupを終了する。',
        'P5 требует DNS из M2. В P4 потренируйтесь подключаться к БД по IP и имени. Приложение использует db.lab.test. Перед переключением practice → mission завершите setup в P6.',
        'P5 uchun ham M2 DNS kerak. P4 da DB ga IP va nom orqali ulanishni mashq qiling. Ilova db.lab.test dan foydalanadi. Practice → mission almashishdan oldin P6 da setup ni tugating.')[lang], '',
      T('P0=1、M0=1、M1=8、M2=13、M4=9、M5=13、M6=16（計61素点）。本人実演・backup/restore・追加disk・アプリ開発は課さない。科目25点への換算は教師が別に行う。再提出は教師が案内する締切まで可能。別々の回のPASSを合算したり自動最高点選択はしない。',
        'P0=1, M0=1, M1=8, M2=13, M4=9, M5=13, M6=16: всего 61 балл. Нет личной демонстрации, backup/restore, дополнительных дисков и разработки приложения. Пересчёт в 25 баллов делает преподаватель отдельно. Повторные отправки возможны до объявленного срока. PASS разных попыток не объединяются; максимум автоматически не выбирается.',
        'P0=1, M0=1, M1=8, M2=13, M4=9, M5=13, M6=16: jami 61 xom ball. Shaxsiy namoyish, backup/restore, qo‘shimcha disk va app dasturlash talab qilinmaydi. 25 ballga o‘tkazishni o‘qituvchi alohida qiladi. E’lon qilingan muddatgacha qayta yuborish mumkin. Turli urinish PASS lari qo‘shilmaydi; eng yuqori ball avtomatik tanlanmaydi.')[lang], '',
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
      T('P0・M0はEC2の一覧からSession Managerを開く。後の練習でCloudShellから接続するよう指定されたときは、CloudShellで `aws ssm start-session --target i-...` を実行する。`i-...` は対象のInstance IDに置き換える。どちらも接続先の `ssm-user` として操作する。',
        'В P0 и M0 открывайте Session Manager из списка EC2. Если в дальнейшем шаг требует подключения из CloudShell, выполните там `aws ssm start-session --target i-...`, подставив ID сервера. В обоих случаях на сервере используется `ssm-user`.',
        'P0 va M0 da Session Manager’ni EC2 ro‘yxatidan oching. Keyingi qadam CloudShell orqali ulanishni so‘rasa, u yerda `aws ssm start-session --target i-server-ID` ni bajaring. Har ikkala holatda serverda `ssm-user` sifatida ishlaysiz.')[lang], '',
      T('nanoの編集：file名を指定して開く→本文を入力→Ctrl+O→Enterで保存→Ctrl+Xで終了。設定fileの枠はshell commandではない。psqlに入るとpromptが変わる。SQL/\\passwordはその中へ入力し、\\qでUbuntuへ戻る。失敗したcommandの次へ進まず、期待結果を確認する。',
        'Редактор nano: открыть файл → ввести текст → Ctrl+O → Enter сохранить → Ctrl+X выйти. Блок конфигурации не выполняется как shell-команда. В psql меняется prompt; SQL/\\password вводятся внутри, \\q возвращает в Ubuntu. Не продолжайте после ошибки без проверки результата.',
        'Nano: faylni ochish → matn yozish → Ctrl+O → Enter bilan saqlash → Ctrl+X bilan chiqish. Sozlama bloki shell buyrug‘i emas. Psql ichida prompt o‘zgaradi; SQL/\\password shu yerga yoziladi, \\q Ubuntu ga qaytaradi. Xatodan keyin natijani tekshirmay davom etmang.')[lang], '']
    out += [T('番号付きコメントは、その手順内の操作順と目的を示します。# はshell、-- はpsql内のコメントです。コメントは説明なので、書き換える必要はありません。接続・エディタ・パスワード入力の完了を待ち、一つずつ実行します。改行で続くコマンドは一つとして扱います。',
        'Нумерованные комментарии показывают порядок и цель внутри шага. # используется в shell, -- внутри psql. Комментарии менять не нужно. Выполняйте по одной команде, дожидаясь подключения, редактора и ввода пароля. Команда с продолжением строки остаётся одной командой.',
        'Raqamli izohlar shu qadamdagi tartib va maqsadni bildiradi. # shell, -- psql ichidagi izohdir. Izohni o‘zgartirish shart emas. Ulanish, editor va parol kiritish tugashini kutib, bittadan bajaring. Qatorga bo‘lingan buyruq bitta buyruq bo‘lib qoladi.')[lang], '']
    return out


def emit_end(lang):
    return ['## ' + L['resume'][lang], '', T(
      '次回は本人のLabと同じ5台を起動し、running/SSM Onlineと現在の公開IPを確認する。Web Portalへ学校Googleでログインし、まずM0で準備確認する。作成・鍵生成・登録を毎回繰り返す必要はない。期限切れは教師へ更新を依頼する。',
      'В следующий раз запустите свой Lab и те же пять узлов, проверьте running/SSM Online и текущие public IP. Войдите в Web Portal через школьный Google и начните с готовности M0. Не повторяйте создание, ключи и регистрацию каждый раз. При истечении срока запросите обновление у преподавателя.',
      'Keyingi safar o‘z Lab va ayni besh serverni ishga tushirib, running/SSM Online va joriy public IP ni tekshiring. Web Portal ga maktab Google orqali kirib, M0 tayyorligidan boshlang. Yaratish, kalit va ro‘yxatni har safar takrorlamang. Muddat tugasa o‘qituvchidan yangilashni so‘rang.')[lang], '', T(
      '結果は自動保存される。処理中は「結果を更新する」、成績確認は「保存済み成績を見る」を使う。確認対象の課題・時刻と保存状態を読む。UNKNOWNは観測不能で、合格や0点を確定した意味ではない。未確認Mの確定済み点数は保持される。最新の評価可能な結果を使い、異なる回のPASSを合算したり自動で最高点を選んだりしない。',
      'Результаты сохраняются автоматически. Во время обработки обновляйте результат; оценки смотрите в разделе сохранённых оценок. Сверяйте задание, время и сохранение. UNKNOWN означает невозможность измерения, а не успех или подтверждённый ноль. Подтверждённые баллы непроверенных M сохраняются. Используется последний оцениваемый результат, без объединения PASS разных запусков и автоматического выбора максимума.',
      'Natijalar avtomatik saqlanadi. Ishlov paytida natijani yangilang; baholarni saqlangan baholar bo‘limidan ko‘ring. Topshiriq, vaqt va saqlash holatini solishtiring. UNKNOWN o‘lchab bo‘lmagan holat, muvaffaqiyat yoki tasdiqlangan nol emas. Tekshirilmagan M ning tasdiqlangan ballari saqlanadi. Oxirgi baholanadigan natija olinadi; turli urinish PASS lari qo‘shilmaydi, maksimum avtomatik tanlanmaydi.')[lang], '',
      T('password/token/cookie/秘密鍵/env本文を提出物や会話へ送らない。',
        'Не отправляйте пароль/token/cookie/приватный ключ/env в отчёт или чат.',
        'Parol/token/cookie/maxfiy kalit/env ni hisobot yoki chat ga yubormang.')[lang], '',
      '## ' + L['sources'][lang], '',
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

def shared_image(name, caption, lang):
    caption = caption[lang]
    return [f'![{caption}](../../assets/shared/{name}.png)', '', caption, '']


def instance_id_guide(lang):
    return shared_image('ec2-session-manager-instances', T(
        'EC2のInstances一覧。P0は名前の末尾が `-web` の行、M0は `-db` の行を選ぶ。',
        'Список Instances в EC2. Для P0 выберите строку с окончанием имени `-web`, для M0 — `-db`.',
        'EC2 dagi Instances ro‘yxati. P0 uchun nomi `-web`, M0 uchun `-db` bilan tugaydigan qatorni tanlang.'), lang)


def session_connect_guide(lang):
    return shared_image('ec2-session-manager-connect', T(
        'EC2の詳細画面。Connectの右の矢印からConnect with SSM Session Managerを選ぶ。Webサーバーの画面を例に示す。',
        'Страница EC2. Нажмите стрелку справа от Connect и выберите Connect with SSM Session Manager. На снимке показан Web-сервер.',
        'EC2 tafsilot oynasi. Connect yonidagi o‘ng strelkadan Connect with SSM Session Manager ni tanlang. Rasmda Web server ko‘rsatilgan.'), lang)


def illustrated_steps(lang, steps):
    out = []
    for number, (image, title, instruction) in steps:
        out += [f'**{number}. {title[lang]}**', '', instruction[lang], '',
                f'![{title[lang]}](../../assets/shared/{image}.png)', '']
    return out


def make_markdown(reg, lang, kind):
    out = emit_intro(lang, kind)
    out += ['## ' + LABELS['read'][lang], '']
    out += [p[lang] + '\n' for p in READING]
    out += ['## ' + LABELS['routes'][lang], '',
        '| ' + T('送信元', 'Источник', 'Manba')[lang] + ' | ' + T('宛先', 'Назначение', 'Manzil')[lang] + ' | Protocol / port | ' + T('目的', 'Цель', 'Maqsad')[lang] + ' |',
        '| --- | --- | --- | --- |']
    out += [f'| {source} | {target} | {protocol} | {purpose[lang]} |' for source,target,protocol,purpose in ROUTES]
    out += ['', T('初期環境で提供されたSSMは、CloudShellから各EC2へ入る管理経路。上のWeb利用経路とは別に使う。表の内部IP/portはこのLabの仕様で、一般のWebシステム全てに同じ値を要求するものではない。',
        'SSM начальной среды — отдельный путь управления из CloudShell в EC2. Он не включён в путь обычного Web-запроса. Внутренние IP и порты таблицы заданы этим Lab, а не всеми Web-системами.',
        'Boshlang‘ich SSM CloudShell dan EC2 ga alohida management yo‘lidir. U oddiy Web request yo‘liga qo‘shilmaydi. Jadvaldagi ichki IP va portlar shu Lab uchun, barcha Web tizimlari uchun emas.')[lang], '']
    tasks = {t['id']: t for t in reg['tasks']}
    if kind == 'practice':
        for m in MODULES:
            out += ['## ' + m['id'] + ' ' + m['title'][lang], '', '### ' + L['goal'][lang], '', m['goals'][lang], '', '### ' + L['problem'][lang], '', m['problem'][lang], '']
            out += diagram_markdown(m['id'],lang)
            out += task_spec(tasks[m['id']], reg, lang)
            notes=MODULE_NOTES[m['id']]
            if 'before' in notes:
                out += ['### ' + LABELS['mechanism'][lang], '',
                        '**' + LABELS['before'][lang] + ':** ' + notes['before'][lang], '']
            out += ['**' + L['work'][lang].format(number=m['id'][1:]) + '**', '', notes['after'][lang], '']
            if 'mechanism' in notes:
                out += [notes['mechanism'][lang], '']
            if m['id']=='P0':
                out += lesson_files_markdown(lang)
            out += ['### ' + L['solution'][lang], '']
            for i, s in enumerate(m['steps'], 1):
                step_id=f"{m['id']}.{i}"
                out += [f"#### {step_id} {s['title'][lang]}", '', '**' + L['place'][lang] + ':** ' + PLACES[s['place']][lang], '', '**' + L['why'][lang] + ':** ' + s['why'][lang], '']
                if step_id=='P0.1':
                    out += instance_id_guide(lang)
                    continue
                if step_id=='P0.2':
                    out += session_connect_guide(lang)
                if step_id=='P0.3':
                    rdp_steps = list(enumerate(RDP_STEPS, 1))
                    out += illustrated_steps(lang, rdp_steps[:2])
                    out += shared_image('windows-run-rdp', T(
                        'Windowsキー＋Rで「ファイル名を指定して実行」を開く。「名前」欄に `mstsc /prompt` を入力し、**OK** を押す。',
                        'Нажмите Windows+R, чтобы открыть окно «Выполнить». Введите `mstsc /prompt` в поле «Открыть» и нажмите **OK**.',
                        'Windows+R tugmalarini bosib Run oynasini oching. Open maydoniga `mstsc /prompt` yozing va **OK** ni bosing.'), lang)
                if s['code']:
                    for fence,source in annotated_blocks(m['id'],i,s['code'],lang):
                        label=T('設定・入力データ（端末で実行するコマンドではない）','Конфигурация или данные: не выполнять как команды','Sozlama yoki ma’lumot: terminal buyrug‘i emas')[lang] if fence=='text' else T('入力するコマンド（番号はこの手順内の順番）','Команды: нумерация внутри этого шага','Buyruqlar: raqamlar shu qadam ichidagi tartib')[lang]
                        if fence=='sql':label=T('ここからはpsql内で入力する','Далее вводить внутри psql','Bundan keyin psql ichida kiriting')[lang]
                        out += [label, '', '```' + fence, shell_lines(source) if fence=='bash' else source, '```', '']
                if step_id=='P0.3':
                    out += illustrated_steps(lang, rdp_steps[2:])
                if step_id in STEP_NOTES:
                    out += ['**' + LABELS['meaning'][lang] + ':** ' + STEP_NOTES[step_id][lang], '']
                out += ['**' + L['expect'][lang] + ':** ' + s['expect'][lang], '']
                if step_id=='P0.2':
                    out += [T('プロンプトにユーザー名、ホスト名、現在のディレクトリが表示される。`~` はホームディレクトリを表し、`pwd` は現在地を絶対パスで表示する。セットアップが表示を自動設定できず、`$` だけが表示された場合は、次の1行を実行して現在地を常時表示する。作業が終わったら `exit` で接続を閉じる。',
                              'В приглашении видны имя пользователя, имя узла и текущий каталог. `~` означает домашний каталог, а `pwd` показывает полный путь. Если настройка не смогла включить это отображение и видно только `$`, выполните следующую строку. Завершите сеанс командой `exit`.',
                              'Buyruq satri boshida foydalanuvchi nomi, host nomi va joriy katalogni tekshiring. `~` uy katalogini, `pwd` esa joriy katalogning to‘liq yo‘lini ko‘rsatadi. Sozlashda bu ko‘rinish yoqilmasa va faqat `$` chiqsa, quyidagi qatorni bajaring. Ish yakunida `exit` bilan ulanishni yoping.')[lang],
                            '', '```bash', r"exec env PS1='\u@\h:\w\$ ' bash --norc -i", '```', '']
                    out += shared_image('session-manager-terminal', T(
                        'Session Managerの端末。表示を変えると、移動後のディレクトリがプロンプトに反映される。',
                        'Терминал Session Manager. После настройки приглашение обновляет текущий каталог при переходе.',
                        'Session Manager terminali. Sozlangach, katalogga o‘tganda buyruq satri yangi katalogni ko‘rsatadi.'), lang)
                if s['trouble'] is not None:
                    out += ['**' + L['trouble'][lang] + ':** ' + s['trouble'][lang], '']
            if m['id']=='P0':
                out += ['### '+T('確認・提出','Проверка и сдача','Tekshirish va topshirish')[lang], '', T(
                    '教師が案内する採点ページのURLを自分のPCのブラウザで開き、学校のGoogleアカウントでログインする。初回だけ「自分のAWS環境を登録」を選び、画面の手順で連携する。',
                    'Откройте адрес портала из объявления преподавателя в браузере на своём компьютере и войдите с учебным аккаунтом Google. При первом входе выберите регистрацию своей среды AWS и следуйте указаниям на экране.',
                    'O‘qituvchi bergan baholash manzilini o‘z kompyuteringizdagi brauzerda oching va ta’lim muassasasining Google hisobi bilan kiring. Birinchi kirishda o‘z AWS muhitingizni ro‘yxatdan o‘tkazish bo‘limini tanlang va ekrandagi ko‘rsatmalarga amal qiling.')[lang], '', T(
                    '表のP0の行で **この課題を確認する** を押す。同じページで今回の結果を確認し、P0の行に **1 / 1** が保存されたことを確認する。',
                    'В строке P0 нажмите **Проверить это задание**. Посмотрите результат на этой же странице и убедитесь, что в строке P0 сохранён **1 / 1**.',
                    'P0 qatoridagi **Ushbu vazifani tekshirish** tugmasini bosing. Shu sahifada natijani tekshirib, P0 qatorida **1 / 1** saqlanganiga ishonch hosil qiling.')[lang], '']
            if m['id'] in OUTPUT_EXAMPLES:
                example,reading=OUTPUT_EXAMPLES[m['id']]
                out += ['### ' + LABELS['output'][lang], '', '```text', example, '```', '', reading[lang], '']
            if 'question' in notes:
                out += ['### ' + LABELS['reflect'][lang], '', notes['question'][lang], '',
                        '**' + LABELS['answer'][lang] + ':** ' + notes['answer'][lang], '']
    else:
        out += ['## ' + LABELS['plan'][lang], '']
        out += [p[lang] + '\n' for p in MISSION_PLAN]
        for number in ACTIVE_NUMBERS:
            task = tasks['M' + str(number)]
            title = MODULES_BY_NUMBER[number]['title'][lang]
            points = f" ({task['raw_points_max']})"
            out += [f"## {task['id']} {title}{points}", '', '### ' + L['requirements'][lang], '', MISSION_GUIDANCE[task['id']][lang], '']
            out += diagram_markdown(task['id'],lang)
            if number==0:
                out += instance_id_guide(lang)
                out += session_connect_guide(lang)
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
            out += ['### ' + L['submit'][lang], '', browser_check(task['id'], lang), '']
    out += emit_end(lang)
    text = '\n'.join(out).replace('\u2013', '-').replace('\u2014', '-')
    # Labels form their own paragraphs so commands, explanations and results scan separately.
    return re.sub(r'^(\*\*[^\n]+?:\*\*) (.+)$', r'\1\n\n\2', text, flags=re.M)

CSS = '''
:root{color-scheme:light;font:17px/1.85 system-ui,sans-serif;color:#172637;background:#eef2f6}
*{box-sizing:border-box}body{margin:0}header,main,footer{max-width:900px;margin:auto;padding:1.5rem 2rem;background:white}
header{border-bottom:5px solid #126e70}header p{margin:0;color:#415569}nav{display:flex;flex-wrap:wrap;gap:1rem}
a{color:#085e80;text-underline-offset:.2em}a:focus-visible{outline:3px solid #b24a00;outline-offset:4px}
.skip{position:absolute;left:-9999px}.skip:focus{position:fixed;left:1rem;top:1rem;background:white;padding:.5rem;z-index:2}
h1{font-size:2rem;line-height:1.35}h2{margin-top:3rem;padding-top:.7rem;border-top:3px solid #126e70;font-size:1.55rem}
h3{font-size:1.2rem;margin-top:2.5rem;padding-top:.5rem;border-top:1px solid #b8c6d0}h4{font-size:1.08rem;margin-top:2rem;color:#134c61}
pre{background:#f0f4f7;border-left:4px solid #126e70;padding:1rem;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.55;font: .83rem/1.6 Consolas,monospace}
code{font-family:Consolas,monospace}table{width:100%;border-collapse:collapse;font-size:.9rem;margin:1rem 0;table-layout:fixed}
th,td{border:1px solid #b8c6d0;padding:.5rem;vertical-align:top;overflow-wrap:anywhere}th{background:#e8f1f3;text-align:start}
p,li{overflow-wrap:anywhere}li+li{margin-top:.5rem}blockquote{margin:1.5rem 0;border-left:4px solid #126e70;padding:.1rem 1rem;background:#f0f4f7}footer{font-size:.85rem;color:#415569;border-top:1px solid #b8c6d0}
img{display:block;max-inline-size:100%;block-size:auto;margin:1.5rem 0}
@media(max-width:600px){header,main,footer{padding:1rem}h1{font-size:1.6rem}}
@media print{body{background:white;font-size:10pt}header,main,footer{max-width:none;padding:0}nav,.skip{display:none}h2{break-before:page}h2,h3,h4{break-after:avoid}pre{white-space:pre-wrap;break-inside:auto}tr{break-inside:avoid}}
'''

def render_html(md, lang, kind):
    parser = MarkdownIt('commonmark', {'html': False}).enable('table')
    body = parser.render(md)
    body = body.replace('<th>', '<th scope="col">')
    # Generated output preserves the same folder hierarchy as Markdown.
    body = re.sub(r'href="([^"#]+)\.md(#[^"]*)?"', lambda m: 'href="' + m[1] + '.html' + (m[2] or '') + '"', body)
    body = body.replace('href="../../output/pdf/', 'href="../../pdf/')
    body = body.replace('src="../../assets/', 'src="../../../assets/').replace('href="../../assets/', 'href="../../../assets/')
    def html_image(match):
        source, alt = match.groups()
        width, height = 1040, 680
        if source.startswith('../../../assets/shared/'):
            from PIL import Image
            with Image.open(ROOT / source.removeprefix('../../../')) as picture:
                width, height = picture.size
        return f'<img src="{source}" alt="{alt}" width="{width}" height="{height}" loading="lazy">'
    body = re.sub(r'<img src="([^"]+)" alt="([^"]*)"\s*/?>', html_image, body)
    toc = []
    def heading(m):
        slug = 'section-' + str(len(toc) + 1)
        toc.append((slug, m[1]))
        return f'<h2 id="{slug}">{m[1]}</h2>'
    body = re.sub(r'<h2>(.*?)</h2>', heading, body)
    links = ' · '.join(f'<a href="#{slug}">{text}</a>' for slug, text in toc)
    title = html.escape(md.splitlines()[0].removeprefix('# '))
    return f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head><body><a class="skip" href="#content">{html.escape(L["intro"][lang])}</a><header><p>JDU · Web Infrastructure</p><nav aria-label="Contents">{links}</nav></header><main id="content" tabindex="-1">{body}</main></body></html>'

def make_pdf(md, lang, target):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, XPreformatted, Table, TableStyle, CondPageBreak, Image, KeepTogether
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
    pair_style = ParagraphStyle('commandpair',parent=code_style,spaceBefore=0,spaceAfter=0,borderPadding=0)
    small = ParagraphStyle('table', parent=styles[0], fontSize=8.5, leading=12.7, spaceAfter=0)
    parser = MarkdownIt('commonmark', {'html':False}).enable('table')
    tokens = parser.parse(md)
    def inline(token):
        result=[];active_links=[]
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
                active_links.append(href.startswith('https://'))
                result.append('<a href="'+html.escape(href,quote=True)+'" color="#085e80">' if active_links[-1] else '')
            elif c.type=='link_close':
                # Only external links are active in PDF; index/HTML keep local navigation.
                result.append('</a>' if active_links.pop() else '')
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
            images=[c for c in tokens[i+1].children or [] if c.type=='image']
            if images:
                for img in images:
                    source=(ROOT/'docs'/lang/img.attrGet('src')).resolve()
                    picture = Image(str(source))
                    scale = min(width / picture.imageWidth, 460 / picture.imageHeight)
                    picture.drawWidth = picture.imageWidth * scale
                    picture.drawHeight = picture.imageHeight * scale
                    flow.extend([picture,Spacer(1,8)])
                i+=3;continue
            value=inline(tokens[i+1])
            if list_depth:value='• '+value
            flow.append(Paragraph(value,styles[0]));i+=3;continue
        if t.type in ('bullet_list_open','ordered_list_open'):list_depth+=1
        if t.type in ('bullet_list_close','ordered_list_close'):list_depth-=1
        if t.type=='fence':
            chunks=re.split(r'(?m)(?=^(?:#|--) \d+\. )',t.content.rstrip('\n'))
            chunks=[chunk for chunk in chunks if chunk]
            paired=len(chunks)>1 or bool(re.match(r'^(?:#|--) \d+\. ',t.content))
            if paired:flow.append(Spacer(1,5))
            for chunk in chunks:
                lines=[]
                for line in chunk.rstrip('\n').split('\n'):
                    # Printing wraps visually; source MD/HTML keeps exact commands.
                    comment=bool(re.match(r'^(?:#|--) \d+\. ',line))
                    limit=56 if comment and lang=='ja' else 96
                    wrapped=textwrap.wrap(line,width=limit,replace_whitespace=False,drop_whitespace=False,break_long_words=True,break_on_hyphens=False) or ['']
                    lines.extend('<font name="'+body_font+'" color="#285f45">'+html.escape(part)+'</font>' if comment else html.escape(part) for part in wrapped)
                block=XPreformatted('\n'.join(lines),pair_style if paired else code_style)
                flow.append(KeepTogether([block]) if paired else block)
            if paired:flow.append(Spacer(1,9))
        if t.type=='table_open':
            rows=[];row=[];j=i+1
            while tokens[j].type!='table_close':
                q=tokens[j]
                if q.type=='tr_open':row=[]
                if q.type=='inline':row.append(Paragraph(inline(q),small))
                if q.type=='tr_close':rows.append(row)
                j+=1
            cols=len(rows[0])
            if cols==2:widths=[width*.36,width*.64]
            elif cols==4:widths=[width*.18,width*.22,width*.16,width*.44]
            else:widths=[width/cols]*cols
            table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f1f3')),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#b8c6d0')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            flow.extend([table,Spacer(1,10)]);i=j
        i+=1
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(body_font,8);canvas.setFillColor(colors.HexColor('#415569'))
        canvas.drawString(44,27,'JDU Web Infrastructure · '+lang.upper())
        canvas.drawRightString(A4[0]-44,27,str(doc.page));canvas.restoreState()
    doc=SimpleDocTemplate(str(target),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=38,bottomMargin=43,
        title=md.splitlines()[0].removeprefix('# '),author='JDU',pageCompression=1)
    doc.build(flow,onFirstPage=footer,onLaterPages=footer)

def main():
    p=argparse.ArgumentParser();p.add_argument('--no-pdf',action='store_true');a=p.parse_args()
    reg_raw=(KIT/'assessment/assessment-registry.json').read_bytes()
    assert hashlib.sha256(reg_raw).hexdigest()==EXPECTED_REGISTRY
    reg=active_registry(json.loads(reg_raw))
    write_diagrams(ROOT)
    assert set(CHECKS)=={c for t in reg['tasks'] if t['category']=='automated_mission' for c in t['progress_scored_checks']}
    assert set(STEP_NOTES)=={f"{module['id']}.{i}" for module in MODULES for i in range(1,len(module['steps'])+1)} - {'P0.1', 'P0.2'}
    for m in MODULES:
        assert m['id'] in MODULE_NOTES
        assert all(set(p)==set(LANGS) and all(p.values()) for p in MODULE_NOTES[m['id']].values())
        for field in ('title','goals','problem'):
            assert set(m[field])==set(LANGS)
        for s in m['steps']:
            for field in ('title','why','expect','trouble'):
                if s[field] is not None:
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
            (folder/(kind+'-full.md')).write_text(md,encoding='utf-8',newline='\n')
            out=ROOT/'output/html'/lang;out.mkdir(parents=True,exist_ok=True)
            (out/(kind+'-full.html')).write_text(render_html(md,lang,kind),encoding='utf-8',newline='\n')
        write_pages(ROOT, lang, reg, render_html, L, MODULES)
        if not a.no_pdf:
            for kind in ('practice','missions'):
                out=ROOT/'output/pdf';out.mkdir(parents=True,exist_ok=True)
                path=out/f'web_lab_{kind}_{lang}.pdf'
                make_pdf((folder/(kind+'-full.md')).read_text(encoding='utf-8'),lang,path)
                outputs.append(path.name)
    # Keep accepted initial distribution instructions as a byte-for-byte reference copy.
    for sub in ('', 'foundation'):
        for name in ('STUDENT.md','TEACHER.md'):
            dest=ROOT/'distribution'/sub/name;dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes((KIT/sub/name).read_bytes())
    # Internal links in these reference instructions resolve to original signed tools,
    # not a duplicate executable distribution inside this teaching archive.
    # The reference handouts are read in the signed course kit, not executed here.
    public_assets={
        'jdu-web-course.tar.gz':KIT.parent/(DIST_ID+'.tar.gz'),
        'jdu-web-course.tar.gz.asc':KIT.parent/(DIST_ID+'.tar.gz.asc'),
        'package-signing-public.asc':KIT.parent/'package-signing-public.asc',
    }
    for name,source in public_assets.items():
        (ROOT/'distribution'/name).write_bytes(source.read_bytes())
    links=[]
    for lang in LANGS:
        label={'ja':'日本語','ru':'Русский','uz':'O‘zbekcha'}[lang]
        links.append(f'<article><h2>{label}</h2><p><a href="{lang}/practice.html">P0–P6</a> · <a href="{lang}/missions.html">M0–M6</a></p><p><a href="../pdf/web_lab_practice_{lang}.pdf">P PDF</a> · <a href="../pdf/web_lab_missions_{lang}.pdf">M PDF</a></p></article>')
    (ROOT/'output/html/index.html').write_text('<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>JDU Web P/M 教材</title><style>'+CSS+'</style></head><body><main><h1>Web Infrastructure · P / M</h1><p>手順付き練習と自力課題 / Практика и задания / Mashqlar va topshiriqlar</p>'+''.join(links)+'</main></body></html>',encoding='utf-8',newline='\n')
    package=ROOT/'output/web-lab-pm-r1.zip'
    members=[p for folder in ('docs','assets','resources','distribution','output/html','output/pdf') for p in (ROOT/folder).rglob('*') if p.is_file()]
    members += [ROOT/'README.md',ROOT/'TEACHER-NOTES.md',ROOT/'VALIDATION.md']
    if all(p.exists() for p in members):
        inventory={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in members}
        with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for path in sorted(members):
                z.write(path,'web-lab-pm-r1/'+path.relative_to(ROOT).as_posix())
            z.writestr('web-lab-pm-r1/TEACHING-FILE-HASHES.json',json.dumps(inventory,indent=2))
    print(json.dumps(dict(material_revision=MATERIAL_REVISION,modules=len(MODULES),steps=sum(len(m['steps']) for m in MODULES),
        explained_steps=len(STEP_NOTES),languages=list(LANGS),pdfs=outputs),ensure_ascii=False))

if __name__=='__main__':
    main()
