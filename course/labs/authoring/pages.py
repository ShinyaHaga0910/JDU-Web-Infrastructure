from curriculum import ACTIVE_NUMBERS, ACTIVE_ORDER, display_task, task_page
"""Task-sized student pages derived from the complete handbooks, without duplicating steps."""
from pathlib import Path
import re

from content import T

def browser_check(task, lang):
    out = T(
        f'1. P0で使った課題画面に学校のGoogleアカウントでログインし、自分のLabと **{task}** を選ぶ。',
        f'1. Откройте страницу заданий, которую использовали в P0. Войдите через учебный аккаунт Google и выберите свой Lab и **{task}**.',
        f'1. P0 da ishlatgan topshiriqlar sahifasiga ta’lim muassasasining Google hisobi bilan kiring va o‘z Lab muhitingiz hamda **{task}** ni tanlang.')[lang]
    mission = task.startswith('M') and task not in ('M0','M3')
    if mission:
        out = T(f'1. 採点ページを開き、**{task}** を選ぶ。',
                f'1. Откройте страницу оценок и выберите **{task}**.',
                f'1. Baholash sahifasini oching va **{task}** ni tanlang.')[lang]
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
    if mission:
        out += '\n' + T(
            '3. 確認が終わると、満たした項目数と項目ごとの結果が表示される。「要修正」は該当する設定を直して再度確認する。「未確認」は、その項目を判定できなかった状態を表す。点数は課題一覧で確認する。',
            '3. По завершении появятся число выполненных критериев и результат каждого. Исправьте пункты с пометкой «Исправить» и запустите проверку снова. «Не проверен» означает, что результат определить не удалось. Баллы отображаются в списке заданий.',
            '3. Tekshiruv tugagach, bajarilgan mezonlar soni va har bir natija chiqadi. «Tuzating» deb belgilangan sozlamani to‘g‘rilab, yana tekshiring. «Tekshirilmagan» band natijasi aniqlanmagan. Ballarni topshiriqlar ro‘yxatidan ko‘ring.')[lang]
        return out
    out += '\n' + T(
        '3. 処理中は「結果を更新する」で完了を待ち、クリアした項目数を確認する。「要修正」の項目があれば直してからもう一度確認する。結果は自動保存される。',
        '3. Во время обработки обновляйте результат. Посмотрите, сколько критериев выполнено. Внесите нужные исправления и проверьте снова. Результат сохраняется автоматически.',
        '3. Ishlov davom etsa natijani yangilab kuting. Nechta band bajarilganini ko‘ring. Tuzatish kerak bo‘lgan bandlarni tuzatib, yana tekshiring. Natija avtomatik saqlanadi.')[lang]
    return out

WORDS = {
 'practice': T('練習 P0〜P5', 'Практика P0–P5', 'Mashqlar P0–P5'),
 'missions': T('課題 M0〜M5', 'Задания M0–M5', 'Topshiriqlar M0–M5'),
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

def write_pages(root, lang, registry, render_html, labels, modules):
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
        index = [f'# {WORDS[kind][lang]}', '', nav(lang), '', translations(kind), '', intro, '',
            '| '+T('練習', 'Практика', 'Mashq')[lang]+' | '+T('自力課題', 'Задание', 'Topshiriq')[lang]+' | '+WORDS['topic'][lang]+' | '+WORDS['points'][lang]+' |', '| --- | --- | --- | --- |']
        for module in modules:
            n = int(module['id'][1:])
            points = tasks[f'M{n}']['raw_points_max']
            practice=f'P{n}'
            mission=f'M{n}'
            index.append(f'| [{display_task(practice)}]({task_page(practice)}) | [{display_task(mission)}]({task_page(mission)}) | {module["title"][lang]} | {points} |')
        index += ['', T('おすすめの順序', 'Рекомендуемый порядок', 'Tavsiya etilgan tartib')[lang]+':', '',
            ' → '.join(f'[{display_task(task)}]({task_page(task)})' for task in ORDER), '',
            T('P4の前にM2、練習から本課題へ切り替える前にP5を終える。',
              'Завершите M2 до P4 и P5 перед переключением practice → mission.',
              'P4 dan oldin M2 ni, practice → mission almashishdan oldin P5 ni tugating.')[lang], '',
            '## '+WORDS['full'][lang], '', f'- [Markdown]({kind}-full.md)', f'- [PDF](../../output/pdf/web_lab_{kind}_{lang}.pdf)', '']
        write(kind,'\n'.join(index))
        # Cross-language links in the complete handbook must keep the reader in that format.
        value = re.sub(r'(\.\./(?:ja|ru|uz)/'+kind+r')\.md',r'\1-full.md',value)
        value = value.replace('\n## '+labels['intro'][lang], '\n'+nav(lang)+'\n\n## '+labels['intro'][lang],1)
        write(kind+'-full',value)
        for n in ACTIVE_NUMBERS:
            task = prefix+str(n)
            shown = display_task(task)
            match = re.search(r'^## '+shown+r' ([^\n]+)\n(.*?)(?=^## |\Z)',complete[kind],re.M|re.S)
            assert match, task
            body = re.sub(r'^(#{3,4}) ',lambda m:m[1][1:]+' ',match[2],flags=re.M)
            counterpart = ('M' if prefix=='P' else 'P')+str(n)
            link=f'[{display_task(counterpart)}]({task_page(counterpart)})'
            related = T(
                f'対応する{("自力課題" if prefix=="P" else "詳しい練習")}は{link}。',
                f'Связанное задание: {link}.',
                f'Mos topshiriq: {link}.')[lang]
            position=ORDER.index(task)
            neighbors=[]
            if position:
                previous=ORDER[position-1]
                neighbors.append(f'[{WORDS["previous"][lang]}: {display_task(previous)}]({task_page(previous)})')
            if position+1<len(ORDER):
                following=ORDER[position+1]
                neighbors.append(f'[{WORDS["next"][lang]}: {display_task(following)}]({task_page(following)})')
            text=f'# {shown} {match[1]}\n\n{nav(lang)}\n\n{translations(shown.lower())}\n\n{related}\n\n{body.rstrip()}\n\n---\n\n'+ ' · '.join(neighbors)+'\n'
            write(shown.lower(),text)
