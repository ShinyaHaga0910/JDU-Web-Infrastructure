"""Server-rendered, keyboard-accessible raw progress view (JA/UZ/RU)."""
from html import escape
from urllib.parse import urlencode

from grading import project_course_lab, project_lab
from registry import MAXIMUM, MISSIONS, TASKS, COURSE_MAXIMUM, COURSE_MISSIONS, COURSE_TASKS

TEXT = {
    'ja': dict(title='Web実習・素点と進捗', table='自力課題の素点', practice='練習の進捗',
               ready='準備確認', lab='Lab', total='素点合計', current='最新の確認',
               selected='参照する提出', missing='未提出', unknown='確認待ち', partial='未完了',
               complete='合格', provisional='暫定', detail='確認項目', legacy='旧版の進捗（素点集計外）',
               note='満点は{maximum}点です。準備と練習には成績の点を付けません。25点への換算は教師が行います。',
               status='現在の状態と、最後に採点できた提出を分けて表示しています。',
               verification='検証用・成績出力の対象外', unassigned='成績対象の指定待ち', course='授業用',
               refresh='更新', pause='自動更新を止める', resume='30秒ごとの更新を再開',
               empty='登録されたLabはありません。'),
    'uz': dict(title='Web amaliyoti: ballar va jarayon', table='Mustaqil topshiriq ballari',
               practice='Mashqlar jarayoni', ready='Tayyorgarlik', lab='Lab', total='Jami xom ball',
               current='Oxirgi tekshiruv', selected='Baholash uchun topshirish', missing='Topshirilmagan',
               unknown='Tekshiruv kutilmoqda', partial='Tugallanmagan', complete='Bajarildi',
               provisional='Dastlabki', detail='Tekshiruvlar', legacy='Eski natijalar (ballga kirmaydi)',
               note='Maksimal xom ball {maximum}. Tayyorgarlik va mashqlar bahoga kirmaydi. 25 ballga o‘qituvchi aylantiradi.',
               status='Joriy holat va oxirgi baholash mumkin bo‘lgan topshirish alohida ko‘rsatiladi.',
               verification='Sinov uchun; baho eksportiga kirmaydi', unassigned='Baho turi belgilanmagan',
               course='Dars uchun', refresh='Yangilash', pause='Avtomatik yangilashni to‘xtatish',
               resume='Har 30 soniyada yangilash', empty='Ro‘yxatdan o‘tgan Lab yo‘q.'),
    'ru': dict(title='Веб-практикум: баллы и прогресс', table='Баллы самостоятельных заданий',
               practice='Прогресс упражнений', ready='Подготовка', lab='Lab', total='Сумма сырых баллов',
               current='Последняя проверка', selected='Попытка для оценки', missing='Не отправлено',
               unknown='Ожидает проверки', partial='Не завершено', complete='Выполнено',
               provisional='Предварительно', detail='Проверки', legacy='Старые результаты (без оценки)',
               note='Максимум {maximum} сырых балла. Подготовка и упражнения не оцениваются. В 25 баллов переводит преподаватель.',
               status='Текущее состояние и последняя оцениваемая попытка показаны отдельно.',
               verification='Проверочная среда; исключена из экспорта оценок', unassigned='Тип оценки не назначен',
               course='Учебная среда', refresh='Обновить', pause='Приостановить автообновление',
               resume='Обновлять каждые 30 секунд', empty='Нет зарегистрированных Lab.'),
}


def render(labs, role, token, language='ja', paused=False, *, current_curriculum=False):
    language = language if language in TEXT else 'ja'
    t = TEXT[language]
    projector = project_course_lab if current_curriculum else project_lab
    missions = COURSE_MISSIONS if current_curriculum else MISSIONS
    practices = [task for task in (f'P{i}' for i in range(7)) if not current_curriculum or task in COURSE_TASKS]
    maximum = COURSE_MAXIMUM if current_curriculum else MAXIMUM
    note = t['note'].format(maximum=maximum)
    esc = lambda x: escape(str(x), quote=True)
    url = lambda **kw: '/dashboard?' + urlencode(dict(session=token, lang=language, pause=int(paused)) | kw)

    def cell(value, selected=None):
        if not value:
            return '<td class="missing">' + esc(t['missing']) + '</td>'
        state = 'unknown' if not value.get('evaluable') else 'complete' if value.get('complete') else 'partial'
        details = ''.join('<li>' + esc(c['id']) + ': ' + esc(c['status']) + '</li>' for c in value.get('checks', []))
        body = ('<strong>' + esc(value['raw_earned']) + ' / ' + esc(value['raw_maximum']) + '</strong> '
                + esc(t[state]) + '<br><small>' + esc(value.get('checked_at', value['received_at'])) + '</small>')
        if selected and selected['request_id'] != value['request_id']:
            body += '<br>' + esc(t['selected']) + ': ' + esc(selected['raw_earned']) + ' / ' + esc(selected['raw_maximum'])
            body += '<br><small>' + esc(selected['received_at']) + '</small>'
        body += '<details><summary>' + esc(t['detail']) + '</summary><ul>' + details + '</ul></details>'
        return '<td class="' + state + '">' + body + '</td>'

    mission_rows, practice_rows, historic = [], [], []
    for lab in sorted(labs, key=lambda row: row['lab_id']):
        view = projector(lab)
        context = view['assessment_context'] if view['assessment_context'] in ('course', 'verification') else 'unassigned'
        label = esc(lab['lab_id']) + '<br><small>' + esc(t[context]) + '</small>'
        row = '<tr><th scope="row">' + label + '</th>'
        row += ''.join(cell(view['current'].get(m), view['selected'].get(m)) for m in missions)
        pending = bool(view['missing_or_unresolved'] or view['current_unresolved'])
        row += '<td><strong>' + str(view['raw_earned']) + ' / ' + str(maximum) + '</strong>'
        if pending:
            row += '<br>' + esc(t['provisional'])
        row += '</td></tr>'
        mission_rows.append(row)
        practice_rows.append('<tr><th scope="row">' + label + '</th>'
                             + ''.join(cell(view['current'].get(task)) for task in practices)
                             + cell(view['current'].get('M0')) + '</tr>')
        old = [r for r in lab.get('results', []) if r['sk'].startswith('LATEST#') and 'contract_sha256' not in r]
        if old:
            historic.append('<li>' + esc(lab['lab_id']) + '<ul>' + ''.join(
                '<li>' + esc(r['sk'].removeprefix('LATEST#')) + ': ' + esc(r.get('passed', 0))
                + ' / ' + esc(r.get('total', 0)) + '</li>' for r in old) + '</ul></li>')

    def table(caption, headers, rows):
        head = ''.join('<th scope="col">' + esc(h) + '</th>' for h in headers)
        body = ''.join(rows) or '<tr><td colspan="' + str(len(headers)) + '">' + esc(t['empty']) + '</td></tr>'
        return ('<div class="scroll" role="region" aria-label="' + esc(caption) + '" tabindex="0"><table><caption>'
                + esc(caption) + '</caption><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>')

    links = ' '.join('<a href="' + esc(url(lang=code)) + '" lang="' + code + '">' + label + '</a>'
                     for code, label in [('ja', '日本語'), ('uz', 'O‘zbekcha'), ('ru', 'Русский')])
    refresh = '<a href="' + esc(url()) + '">' + esc(t['refresh']) + '</a> · '
    refresh += '<a href="' + esc(url(pause=0 if paused else 1)) + '">' + esc(t['resume'] if paused else t['pause']) + '</a>'
    meta = '' if paused else '<meta http-equiv="refresh" content="30">'
    return ('<!doctype html><html lang="' + language + '"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">' + meta
            + '<title>' + esc(t['title']) + '</title><style>'
            'body{font:1rem/1.6 system-ui,sans-serif;color:#182638;background:#f4f6fa;margin:0}'
            'header,main,footer{max-inline-size:100rem;margin:auto;padding:1rem}a{color:#154f8c;padding:.4rem}'
            ':focus-visible{outline:3px solid #a04400;outline-offset:3px}.scroll{overflow:auto;margin-block:1rem;background:white}'
            'table{border-collapse:collapse;min-inline-size:60rem;inline-size:100%}th,td{padding:.8rem;vertical-align:top;'
            'text-align:start;border:1px solid #ccd4df}caption{text-align:start;font-weight:700;padding:.7rem}'
            'thead th{background:#e8eef7}tbody th{min-inline-size:12rem}td.complete{background:#e6f5eb}'
            'td.partial{background:#fff1d2}td.unknown{background:#e9efff}small{color:#43516a}'
            'summary{cursor:pointer;min-block-size:1.5rem}details{max-inline-size:22rem;overflow-wrap:anywhere}'
            '.skip{position:absolute;inset-inline-start:-100rem}.skip:focus{inset-inline-start:1rem;background:white}'
            '</style></head><body><header><a class="skip" href="#content">' + esc(t['table'])
            + '</a><nav aria-label="Language">' + links + '</nav><p>' + refresh + '</p></header>'
            '<main id="content" tabindex="-1"><h1>' + esc(t['title']) + '</h1><p>' + esc(note)
            + '</p><p>' + esc(t['status']) + '</p><h2>' + esc(t['table']) + '</h2>'
            + table(t['table'], [t['lab'], *[m + ' / ' + str(TASKS[m]['raw_points_max']) for m in missions], t['total']], mission_rows)
            + '<h2>' + esc(t['practice']) + '</h2>'
            + table(t['practice'], [t['lab'], *practices, 'M0'], practice_rows)
            + ('<details><summary>' + esc(t['legacy']) + '</summary><ul>' + ''.join(historic) + '</ul></details>' if historic else '')
            + '</main><footer>' + esc(note) + '</footer></body></html>')
