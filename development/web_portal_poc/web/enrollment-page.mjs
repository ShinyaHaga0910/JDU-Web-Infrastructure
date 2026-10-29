// Server-rendered forms: no JavaScript, browser credential storage or GET writes.
const words={
  ja:{title:'自分のAWS環境を登録',account:'割り当てられたAWSアカウント',lab:'演習環境',confirm:'このAWSアカウントが、自分のLearner Labであることを確認しました。',begin:'AWSとの接続確認へ進む',pending:'AWS側での本人確認を待っています。AWSでの操作が完了したら、登録を確認してください。',refresh:'登録を確認する',done:'自分のAWS環境を登録しました。',denied:'登録を確認できません。先生に割り当てと有効期限を確認してください。',unavailable:'登録の確認ができません。しばらくしてから再度お試しください。',back:'トップへ戻る',note:'この確認ではサーバーの起動・停止や成績の変更は行いません。'},
  ru:{title:'Регистрация своей среды AWS',account:'Назначенный аккаунт AWS',lab:'Учебная среда',confirm:'Я проверил(а), что этот аккаунт AWS относится к моему Learner Lab.',begin:'Перейти к проверке AWS',pending:'Ожидается подтверждение со стороны AWS. После завершения действий в AWS проверьте регистрацию.',refresh:'Проверить регистрацию',done:'Ваша среда AWS зарегистрирована.',denied:'Регистрацию подтвердить не удалось. Уточните назначение и срок у преподавателя.',unavailable:'Не удалось проверить регистрацию. Повторите попытку позже.',back:'На главную',note:'Эта проверка не запускает и не останавливает серверы и не изменяет оценки.'},
  uz:{title:'O‘z AWS muhitingizni ro‘yxatdan o‘tkazish',account:'Biriktirilgan AWS hisobi',lab:'Amaliyot muhiti',confirm:'Ushbu AWS hisobi mening Learner Lab muhitimga tegishli ekanini tekshirdim.',begin:'AWS tekshiruviga o‘tish',pending:'AWS tomonidan tasdiqlash kutilmoqda. AWS amallari tugagach, ro‘yxatdan o‘tishni tekshiring.',refresh:'Ro‘yxatdan o‘tishni tekshirish',done:'AWS muhitingiz ro‘yxatdan o‘tkazildi.',denied:'Ro‘yxatdan o‘tish tasdiqlanmadi. Biriktirish va muddatni o‘qituvchidan tekshiring.',unavailable:'Ro‘yxatdan o‘tishni tekshirib bo‘lmadi. Keyinroq qayta urinib ko‘ring.',back:'Bosh sahifaga',note:'Bu tekshiruv serverlarni ishga tushirmaydi yoki to‘xtatmaydi va baholarni o‘zgartirmaydi.'},
};
const escape=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const enrollmentText=lang=>words[lang];
const browserWords={
  ja:{open:'AWSの確認画面を開く（別タブ）',review:'AWS画面の右上が、上のAWSアカウント番号と一致することを確認してください。追加するのは接続確認用のLambda・ログ・確認処理です。既存LabRoleの広い権限を使い、従量料金が発生します。内容を確認してから作成してください。',return:'AWSでの作成が終わったら、このタブに戻り「登録を確認する」を押してください。秘密鍵・パスワードの入力やコピーは不要です。',expires:'この確認の有効期限（UTC）',expired:'期限が過ぎたら登録状態を確認し、未登録の場合だけ新しい確認を始めてください。'},
  ru:{open:'Открыть проверку AWS (новая вкладка)',review:'Убедитесь, что аккаунт справа вверху AWS совпадает с номером выше. Добавляются Lambda, журнал и операция проверки. Используется существующая LabRole с широкими правами; возможна плата за использование. Проверьте состав перед созданием.',return:'После создания в AWS вернитесь сюда и нажмите «Проверить регистрацию». Вводить или копировать ключи и пароли не нужно.',expires:'Срок действия проверки (UTC)',expired:'После истечения срока проверьте регистрацию. Начинайте новую проверку только если среда не зарегистрирована.'},
  uz:{open:'AWS tekshiruvini ochish (yangi varaq)',review:'AWS oynasining yuqori o‘ng tomonidagi hisob raqami yuqoridagi raqamga mosligini tekshiring. Lambda, log va tekshiruv amali qo‘shiladi. Keng huquqli mavjud LabRole ishlatiladi; foydalanish uchun to‘lov bo‘lishi mumkin. Yaratishdan oldin tarkibini tekshiring.',return:'AWS yaratish tugagach, bu varaqqa qayting va «Ro‘yxatdan o‘tishni tekshirish»ni bosing. Kalit yoki parol kiritish va nusxalash kerak emas.',expires:'Tekshiruv muddati (UTC)',expired:'Muddat tugagach, ro‘yxatdan o‘tishni tekshiring. Faqat ro‘yxatdan o‘tmagan bo‘lsa, yangi tekshiruvni boshlang.'},
};
export function checkedEnrollment(value,{pending=false}={}) {
  if (!value || typeof value.registered!=='boolean' || !/^[a-z0-9][a-z0-9-]{2,31}$/.test(value.lab_id||'')
      || !/^[0-9]{12}$/.test(value.account||'') || (pending && !value.registered &&
         (!/^[a-f0-9]{64}$/.test(value.pair_id||'') || !Number.isSafeInteger(value.expires_at)))) throw Error('Invalid registration');
  return value;
}
export function enrollmentHtml(lang,value,{requestId,csrf,pending=false,bootstrapLink}={}) {
  const t=words[lang]; checkedEnrollment(value,{pending});
  const context=`<dl><dt>${escape(t.account)}</dt><dd>${escape(value.account)}</dd><dt>${escape(t.lab)}</dt><dd>${escape(value.lab_id)}</dd></dl>`;
  let content;
  if (value.registered) content=`<p role="status">${escape(t.done)}</p>`;
  else if (pending) {
    const b=browserWords[lang];
    const link=new URL(bootstrapLink);
    if (link.origin!=='https://us-east-1.console.aws.amazon.com' || link.pathname!=='/cloudformation/home') throw Error('Invalid AWS link');
    const expires=new Date(value.expires_at*1000).toISOString();
    content=`<p role="status">${escape(t.pending)}</p><ol><li><p>${escape(b.review)}</p><a class="action" href="${escape(link.toString())}" target="_blank" rel="noopener noreferrer">${escape(b.open)}</a></li><li><p>${escape(b.return)}</p><a class="action" href="/enroll?lang=${lang}">${escape(t.refresh)}</a></li></ol><p>${escape(b.expires)}: <time datetime="${expires}">${escape(expires.slice(0,19).replace('T',' '))}</time></p><p>${escape(b.expired)}</p>`;
  }
  else {
    if (![requestId,csrf].every(v=>typeof v==='string' && /^[a-f0-9]{64}$/.test(v))) throw Error('Invalid form');
    content=`<form action="/enroll?lang=${lang}" method="post"><input type="hidden" name="request_id" value="${requestId}"><input type="hidden" name="csrf" value="${csrf}"><fieldset><legend>${escape(t.title)}</legend><label class="confirm"><input type="checkbox" name="confirmed" value="yes" required> ${escape(t.confirm)}</label></fieldset><button type="submit">${escape(t.begin)}</button></form>`;
  }
  return `<section>${context}${content}<p>${escape(t.note)}</p></section><a href="/?lang=${lang}">${escape(t.back)}</a>`;
}
