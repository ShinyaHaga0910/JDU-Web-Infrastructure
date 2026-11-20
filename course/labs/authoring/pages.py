from curriculum import ACTIVE_NUMBERS, ACTIVE_ORDER
"""Task-sized student pages derived from the complete handbooks, without duplicating steps."""
from pathlib import Path
import re

from content import T

def expiry_text(lang):
    return T('配布版の有効期限：2027年1月31日末（UZT）。',
        'Комплект действителен до конца 31 января 2027 года (UZT).',
        'Tarqatma 2027-yil 31-yanvar oxirigacha amal qiladi (UZT).')[lang]

def browser_check(task, lang):
    out = T(
        f'1. 教師から案内された課題画面に学校のGoogleアカウントでログインし、自分のLabと **{task}** を選ぶ。',
        f'1. Откройте страницу заданий по ссылке преподавателя, войдите через учебный аккаунт Google и выберите свой Lab и **{task}**.',
        f'1. O‘qituvchi bergan havola orqali topshiriqlar sahifasini oching, ta’lim muassasasining Google hisobi bilan kiring va o‘z Lab muhitingiz hamda **{task}** ni tanlang.')[lang]
    if task[1:] == '3':
        out += '\n' + T(
            '2. 「停止前の状態を記録する」→保存成功→AWSで同じWebをStop→stopped→「停止完了を確認する」→記録成功→AWSで同じWebをStart→running/SSM Online→「再開後の保持を確認する」の順で進める。P3とは別にM3を記録する。',
            '2. Запишите состояние до остановки → дождитесь сохранения → Stop того же Web в AWS → stopped → подтвердите остановку → дождитесь записи → Start того же Web → running/SSM Online → проверьте сохранение после запуска. Доказательство M3 записывайте отдельно от P3.',
            '2. To‘xtashdan oldingi holatni yozing → saqlanishini kuting → AWS da ayni Web ni Stop → stopped → to‘xtashni tasdiqlang → yozilishini kuting → ayni Web ni Start → running/SSM Online → qayta ishga tushgach saqlanishni tekshiring. M3 dalilini P3 dan alohida yozing.')[lang]
    elif task[1:] in ('5', '6'):
        admin = 'lab_admin' if task.startswith('M') else 'practice_admin'
        out += '\n' + T(
            f'2. 「機能・権限を含めて確認する」を選び、{admin} の既存パスワードを「アプリ管理者の既存パスワード」に非表示入力して「このパスワードで確認する」を押す。RDP用とは別。設定だけの確認では機能の合格を確定しない。',
            f'2. Выберите функциональную проверку с правами, скрыто введите существующий пароль {admin} в поле администратора приложения и запустите с этим паролем. Это не пароль RDP. Проверка только настроек не подтверждает функции.',
            f'2. Funksiya/huquq tekshiruvini tanlang, {admin} mavjud parolini app administratorining yashirin maydoniga kiritib, shu parol bilan tekshiring. Bu RDP paroli emas. Faqat sozlama tekshiruvi funksiyalarni tasdiqlamaydi.')[lang]
    else:
        out += '\n' + T('2. 「この課題を確認する」を押す。', '2. Запустите проверку выбранного задания.', '2. Tanlangan topshiriq tekshiruvini boshlang.')[lang]
    out += '\n' + T(
        '3. 処理中は「結果を更新する」で完了を待ち、課題ID・時刻・各check・保存状態を読む。結果は自動保存され、Mの成績は「保存済み成績を見る」で確認できる。',
        '3. Во время обработки обновляйте результат. Сверьте ID задания, время, каждый check и сохранение. Результат сохраняется автоматически; оценки M доступны в разделе сохранённых оценок.',
        '3. Ishlov davom etsa natijani yangilab kuting. Topshiriq ID, vaqt, har check va saqlash holatini o‘qing. Natija avtomatik saqlanadi; M baholari saqlangan baholar bo‘limida.')[lang]
    return out

WORDS = {
 'practice': T('練習 P0〜P6', 'Практика P0–P6', 'Mashqlar P0–P6'),
 'missions': T('課題 M0〜M6', 'Задания M0–M6', 'Topshiriqlar M0–M6'),
 'full': T('一冊で読む・印刷する', 'Полная версия и печать', 'To‘liq o‘qish va chop etish'),
 'topic': T('テーマ', 'Тема', 'Mavzu'),
 'points': T('素点', 'Баллы', 'Xom ball'),
 'previous': T('前の課題', 'Предыдущее', 'Oldingi'),
 'next': T('次の課題', 'Следующее', 'Keyingi'),
}

ORDER = list(ACTIVE_ORDER)

def nav(lang):
    return ' · '.join(f'[{WORDS[key][lang]}]({name}.md)' for key,name in
        [('practice','practice'),('missions','missions')])

def translations(name):
    return ' · '.join(f'[{label}](../{lang}/{name}.md)' for lang,label in
        [('ja','日本語'),('ru','Русский'),('uz','O‘zbekcha')])

def write_pages(root, lang, registry, revision, distribution_id, render_html, labels, modules):
    docs = root/'docs'/lang
    output = root/'output/html'/lang
    tasks = {t['id']: t for t in registry['tasks']}
    complete = {kind:(docs/(kind+'-full.md')).read_text(encoding='utf-8') for kind in ('practice','missions')}

    def write(name, text):
        text = text.rstrip()+'\n'
        (docs/(name+'.md')).write_text(text,encoding='utf-8',newline='\n')
        (output/(name+'.html')).write_text(render_html(text,lang,name),encoding='utf-8',newline='\n')

    for kind,prefix in [('practice','P'),('missions','M')]:
        value = complete[kind]
        intro = T(
            'Pは詳しい操作例つきの練習です。Mは練習で学んだ設定を別の対象に自分で適用する課題です。サーバーを自分で設定してからブラウザで確認します。',
            'P — практика с подробными шагами. M — самостоятельная настройка других объектов на основе навыков P. Сначала настройте серверы сами, затем проверьте в браузере.',
            'P — batafsil qadamli mashq. M — P da o‘rgangan sozlamani boshqa obyektga mustaqil qo‘llash. Avval serverlarni o‘zingiz sozlang, keyin brauzerda tekshiring.')[lang]
        index = [f'# {WORDS[kind][lang]}', '', f'2026-11-13 · D12 P/M {revision}', '', nav(lang), '', translations(kind), '', intro, '', expiry_text(lang), '',
            '| '+T('練習', 'Практика', 'Mashq')[lang]+' | '+T('自力課題', 'Задание', 'Topshiriq')[lang]+' | '+WORDS['topic'][lang]+' | '+WORDS['points'][lang]+' |', '| --- | --- | --- | --- |']
        for module in modules:
            n = int(module['id'][1:])
            points = tasks[f'M{n}']['raw_points_max'] if n else T('授業で案内','По указанию преподавателя','O‘qituvchi e’lon qiladi')[lang]
            index.append(f'| [P{n}](p{n}.md) | [M{n}](m{n}.md) | {module["title"][lang]} | {points} |')
        index += ['', T('おすすめの順序', 'Рекомендуемый порядок', 'Tavsiya etilgan tartib')[lang]+':', '',
            ' → '.join(f'[{task}]({task.lower()}.md)' for task in ORDER), '',
            T('P5の前にM2、練習から本課題へ切り替える前にP6を終える。',
              'Завершите M2 до P5 и P6 перед переключением practice → mission.',
              'P5 dan oldin M2 ni, practice → mission almashishdan oldin P6 ni tugating.')[lang], '',
            '## '+WORDS['full'][lang], '', f'- [Markdown]({kind}-full.md)', f'- [PDF](../../output/pdf/web_lab_{kind}_{lang}.pdf)', '']
        write(kind,'\n'.join(index))
        # Cross-language links in the complete handbook must keep the reader in that format.
        value = re.sub(r'(\.\./(?:ja|ru|uz)/'+kind+r')\.md',r'\1-full.md',value)
        value = value.replace('\n## '+labels['intro'][lang], '\n'+nav(lang)+'\n\n## '+labels['intro'][lang],1)
        write(kind+'-full',value)
        for n in ACTIVE_NUMBERS:
            task = prefix+str(n)
            match = re.search(r'^## '+task+r' ([^\n]+)\n(.*?)(?=^## |\Z)',complete[kind],re.M|re.S)
            assert match, task
            body = re.sub(r'^(#{3,4}) ',lambda m:m[1][1:]+' ',match[2],flags=re.M)
            counterpart = ('M' if prefix=='P' else 'P')+str(n)
            related = T(
                f'対応する{("自力課題" if prefix=="P" else "詳しい練習")}は[{counterpart}]({counterpart.lower()}.md)。',
                f'Связанное задание: [{counterpart}]({counterpart.lower()}.md).',
                f'Mos topshiriq: [{counterpart}]({counterpart.lower()}.md).')[lang]
            position=ORDER.index(task)
            neighbors=[]
            if position:neighbors.append(f'[{WORDS["previous"][lang]}: {ORDER[position-1]}]({ORDER[position-1].lower()}.md)')
            if position+1<len(ORDER):neighbors.append(f'[{WORDS["next"][lang]}: {ORDER[position+1]}]({ORDER[position+1].lower()}.md)')
            text=f'# {task} {match[1]}\n\n{nav(lang)}\n\n{translations(task.lower())}\n\n2026-11-13 · D12 P/M {revision}\n\n{expiry_text(lang)}\n\n{related}\n\n{body.rstrip()}\n\n---\n\n'+ ' · '.join(neighbors)+'\n'
            write(task.lower(),text)
