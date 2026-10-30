"""Publish the browser-check addendum beside the unchanged P/M handbooks."""
import html
from pathlib import Path
from markdown_it import MarkdownIt


def write_guides(root, css):
    source=(root.parents[1]/'development/web_portal_poc/BROWSER-CHECKS.md').read_text(encoding='utf-8')
    headings={'ja':'日本語','ru':'Русский','uz':'O‘zbekcha'}
    titles={'ja':'ブラウザで課題を確認する','ru':'Проверка заданий в браузере','uz':'Vazifalarni brauzerda tekshirish'}
    notices={
      'ja':'初期設定は教師から渡された有効なCloudFormation・登録手順を使います。P/M本文のサーバー設定手順はそのまま実行し、jdu-web-check / jdu-web-my-progressによる課題確認・点数閲覧をこの手順へ置き換えてください。配布版の期限が切れている場合は教師から更新版を受け取ります。',
      'ru':'Для начальной настройки используйте актуальные CloudFormation и инструкцию регистрации преподавателя. Выполняйте настройки серверов из пособий P/M; вместо jdu-web-check / jdu-web-my-progress проверяйте задания и баллы по этой инструкции. Если срок комплекта истёк, получите обновление у преподавателя.',
      'uz':'Boshlang‘ich sozlash uchun o‘qituvchi bergan amaldagi CloudFormation va ro‘yxatdan o‘tish yo‘riqnomasidan foydalaning. P/M qo‘llanmasidagi server sozlamalarini bajaring; jdu-web-check / jdu-web-my-progress o‘rniga vazifa va ballarni ushbu yo‘riqnoma orqali tekshiring. Tarqatma muddati tugagan bo‘lsa, o‘qituvchidan yangisini oling.'}
    expiry={'ja':'ログイン期限が切れたら「ログインし直す」を押します。Googleで再ログインすると、同じ確認画面へ戻れます。確認準備後のアプリパスワード入力は15分以内に行います。時間が過ぎた場合は課題を選び直します。','ru':'Если срок входа истёк, нажмите «Войти снова». После Google вы вернётесь на ту же страницу. Введите пароль приложения в течение 15 минут после подготовки; иначе выберите задание заново.','uz':'Kirish muddati tugasa, «Qayta kirish» ni bosing. Google orqali kirgach, shu sahifaga qaytasiz. Tayyorlashdan keyin ilova parolini 15 daqiqa ichida kiriting; vaqt o‘tgan bo‘lsa, vazifani qayta tanlang.'}
    parser=MarkdownIt('commonmark',{'html':False})
    for lang,heading in headings.items():
        body=source.split('## '+heading+'\n',1)[1].split('\n## ',1)[0].strip()
        if lang=='ja':
            body='教師Labは開始中で使います。学校Googleでログインし、本人AWSとの連携を一度完了します。共有Windowsへ秘密鍵を保存しません。\n\n'+body
        nav='[日本語](../ja/portal.md) · [Русский](../ru/portal.md) · [O‘zbekcha](../uz/portal.md)'
        md=f'# {titles[lang]}\n\n2026-10-30\n\n{nav}\n\n[Web Portal](https://d9r6gn83y8wkl4xl.gpb.lambda-web.us-east-1.on.aws)\n\n> {notices[lang]}\n\n{body}\n\n{expiry[lang]}\n'
        (root/'docs'/lang/'portal.md').write_text(md,encoding='utf-8',newline='\n')
        rendered=parser.render(md).replace('portal.md','portal.html')
        content='<!doctype html><html lang="'+lang+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(titles[lang])+'</title><style>'+css+'</style></head><body><main>'+rendered+'</main></body></html>'
        (root/'output/html'/lang/'portal.html').write_text(content,encoding='utf-8',newline='\n')
