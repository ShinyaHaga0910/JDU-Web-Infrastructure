# CloudFormationの初期設定後に使う課題画面

[学生用の入口](https://d9r6gn83y8wkl4xl.gpb.lambda-web.us-east-1.on.aws)

教師はLabを開始した状態で使用します。学生の構築・登録は、教師が渡す既存CloudFormationと初期接続・採点登録手順で完了します。その後、学生は学校Googleでログインし、本人AWSとの連携を一度済ませます。共有Windowsへ秘密鍵を保存しません。

## 日本語

1. 課題の手順に従い、自分のサーバー内で設定を変更します。課題画面は解答を自動設定しません。
2. 入口の「課題の確認」でP0〜P6/M0〜M6から選び、確認を開始します。通常は1〜2分です。結果の更新が止まった場合は同じ画面の更新ボタンを押します。
3. P3/M3は、停止前の記録が完了したら画面のリンクからAWSを開き、表示された同じWebだけを停止します。stoppedになったら課題画面で停止を記録します。同じWebを起動し、SSMがOnlineに戻ったら、同じ課題画面で再開後を確認します。インスタンスの終了・置換は行いません。
4. P5/M5/P6/M6は、準備完了後に対象アプリの既存管理者パスワードを非表示欄へ入力します。RDP用とは別です。パスワードを教師や会話へ送る必要はありません。確認は専用の架空データCK-P/CK-Mだけを作成・編集し、ログアウトや拒否も試します。確認だけなら「現在の設定だけ確認」も使えます。
5. 完了した結果は成績原本へ自動保存されます。「保存済み成績を見る」で確認します。PとM0は成績外、M1〜M6は62素点です。未確認は0点へ変換せず、確定済み点を保持します。学生Lab終了中は保存成績を閲覧できても、新しい実機確認はできません。

教師は同じ入口の教師一覧から、担当学生の合計・課題別点数・最終確認を確認します。検証用と授業用の一覧を区別します。

## Русский

1. Сначала завершите начальную настройку по CloudFormation и инструкции преподавателя, затем войдите через школьный Google и один раз свяжите свой AWS. Изменяйте настройки внутри своих серверов по заданию: страница проверки не устанавливает ответы.
2. Откройте «Проверка задания», выберите P0–P6/M0–M6 и запустите проверку. Обычно нужно 1–2 минуты. Если обновление остановилось, используйте кнопку обновления на этой же странице.
3. Для P3/M3 дождитесь записи состояния до остановки. По ссылке откройте AWS и остановите только указанный Web. Когда он станет stopped, запишите остановку на странице задания. Запустите тот же Web, дождитесь SSM Online и выполните проверку после запуска на той же странице. Не завершайте и не заменяйте экземпляр.
4. Для P5/M5/P6/M6 после подготовки введите существующий пароль администратора нужного приложения в скрытое поле. Это не пароль RDP. Не передавайте пароль преподавателю. Проверка создаёт и изменяет только учебные записи CK-P/CK-M, проверяет выход и отказ в доступе. Отдельная кнопка позволяет проверить только текущие настройки.
5. Результат автоматически сохраняется в основном журнале; откройте «Сохранённые оценки». P и M0 не оцениваются; M1–M6 дают 62 балла. Непроверенные пункты сохраняют ранее подтверждённые баллы. После End Lab студента доступны сохранённые оценки, но новая проверка серверов невозможна. Lab преподавателя должен работать.

## O‘zbekcha

1. Dastlab CloudFormation va o‘qituvchi bergan boshlang‘ich ulanish hamda ro‘yxatdan o‘tkazish yo‘riqnomasini bajaring. Maktab Google hisobida kiring va o‘z AWS hisobingizni bir marta bog‘lang. Vazifaga ko‘ra o‘z serverlaringiz ichida sozlamalarni o‘zgartiring: tekshiruv sahifasi tayyor javobni o‘rnatmaydi.
2. «Vazifani tekshirish» orqali P0–P6/M0–M6 ni tanlab tekshiruvni boshlang. Odatda 1–2 daqiqa kerak. Yangilanish to‘xtasa, shu sahifadagi yangilash tugmasini bosing.
3. P3/M3 uchun to‘xtatishdan oldingi holat yozilishini kuting. Havola orqali AWS ni ochib, faqat ko‘rsatilgan Web ni to‘xtating. Holat stopped bo‘lgach, vazifa sahifasida to‘xtashni qayd eting. O‘sha Web ni ishga tushiring; SSM Online qaytgach, shu sahifada qayta ishga tushgandan keyingi holatni tekshiring. Instance ni terminate qilmang yoki almashtirmang.
4. P5/M5/P6/M6 uchun tayyorlash tugagach, tegishli ilovaning mavjud administrator parolini yashirin maydonga kiriting. Bu RDP paroli emas. Parolni o‘qituvchiga yubormang. Tekshiruv faqat CK-P/CK-M o‘quv yozuvlarini yaratib/tahrirlaydi, logout va kirish rad etilishini ham tekshiradi. Alohida tugma faqat joriy sozlamalarni tekshiradi.
5. Natija asosiy jurnalga avtomatik saqlanadi. «Saqlangan baholar» orqali ko‘ring. P va M0 baholanmaydi; M1–M6 jami 62 ball. Tekshirilmagan bandlar avvalgi tasdiqlangan ballni saqlaydi. Talaba End Lab qilgach, saqlangan baholar ko‘rinadi, ammo serverlarni yangidan tekshirib bo‘lmaydi. O‘qituvchi Lab ishga tushgan bo‘lishi kerak.

## 配備・検証の範囲

既存の教師/学生checkerとWebをコードだけ更新します。新しい資源・IAM・ネットワーク許可は追加しません。指定された検証5台と先生Googleの学生役を使用します。独立した学生Googleでの通し試験、母語校閲は未実施です。最新の実配備状況は[完成条件](PORTAL-ACCEPTANCE.md)で確認してください。
