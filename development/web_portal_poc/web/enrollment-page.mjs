// Server-rendered forms: no JavaScript, browser credential storage or GET writes.
const words={
  ja:{title:'自分のAWS環境を登録',account:'割り当てられたAWSアカウント',lab:'演習環境',confirm:'このAWSアカウントが、自分のLearner Labであることを確認しました。',begin:'AWSとの接続確認へ進む',pending:'AWS側での本人確認を待っています。AWSでの操作が完了したら、登録を確認してください。',refresh:'登録を確認する',done:'自分のAWS環境を登録しました。',denied:'登録を確認できません。先生に割り当てと有効期限を確認してください。',unavailable:'登録の確認ができません。しばらくしてから再度お試しください。',back:'トップへ戻る',note:'この確認ではサーバーの起動・停止や成績の変更は行いません。'},
  ru:{title:'Регистрация своей среды AWS',account:'Назначенный аккаунт AWS',lab:'Учебная среда',confirm:'Я проверил(а), что этот аккаунт AWS относится к моему Learner Lab.',begin:'Перейти к проверке AWS',pending:'Ожидается подтверждение со стороны AWS. После завершения действий в AWS проверьте регистрацию.',refresh:'Проверить регистрацию',done:'Ваша среда AWS зарегистрирована.',denied:'Регистрацию подтвердить не удалось. Уточните назначение и срок у преподавателя.',unavailable:'Не удалось проверить регистрацию. Повторите попытку позже.',back:'На главную',note:'Эта проверка не запускает и не останавливает серверы и не изменяет оценки.'},
  uz:{title:'O‘z AWS muhitingizni ro‘yxatdan o‘tkazish',account:'Biriktirilgan AWS hisobi',lab:'Amaliyot muhiti',confirm:'Ushbu AWS hisobi mening Learner Lab muhitimga tegishli ekanini tekshirdim.',begin:'AWS tekshiruviga o‘tish',pending:'AWS tomonidan tasdiqlash kutilmoqda. AWS amallari tugagach, ro‘yxatdan o‘tishni tekshiring.',refresh:'Ro‘yxatdan o‘tishni tekshirish',done:'AWS muhitingiz ro‘yxatdan o‘tkazildi.',denied:'Ro‘yxatdan o‘tish tasdiqlanmadi. Biriktirish va muddatni o‘qituvchidan tekshiring.',unavailable:'Ro‘yxatdan o‘tishni tekshirib bo‘lmadi. Keyinroq qayta urinib ko‘ring.',back:'Bosh sahifaga',note:'Bu tekshiruv serverlarni ishga tushirmaydi yoki to‘xtatmaydi va baholarni o‘zgartirmaydi.'},
};
const escape=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const enrollmentText=lang=>words[lang];
export function checkedEnrollment(value,{pending=false}={}) {
  if (!value || typeof value.registered!=='boolean' || !/^[a-z0-9][a-z0-9-]{2,31}$/.test(value.lab_id||'')
      || !/^[0-9]{12}$/.test(value.account||'') || (pending && !value.registered &&
         (!/^[a-f0-9]{64}$/.test(value.pair_id||'') || !Number.isSafeInteger(value.expires_at)))) throw Error('Invalid registration');
  return value;
}
export function enrollmentHtml(lang,value,{requestId,csrf,pending=false}={}) {
  const t=words[lang]; checkedEnrollment(value,{pending});
  const context=`<dl><dt>${escape(t.account)}</dt><dd>${escape(value.account)}</dd><dt>${escape(t.lab)}</dt><dd>${escape(value.lab_id)}</dd></dl>`;
  let content;
  if (value.registered) content=`<p role="status">${escape(t.done)}</p>`;
  else if (pending) content=`<p role="status">${escape(t.pending)}</p><p><a href="/enroll?lang=${lang}">${escape(t.refresh)}</a></p>`;
  else {
    if (![requestId,csrf].every(v=>typeof v==='string' && /^[a-f0-9]{64}$/.test(v))) throw Error('Invalid form');
    content=`<form action="/enroll?lang=${lang}" method="post"><input type="hidden" name="request_id" value="${requestId}"><input type="hidden" name="csrf" value="${csrf}"><fieldset><legend>${escape(t.title)}</legend><label class="confirm"><input type="checkbox" name="confirmed" value="yes" required> ${escape(t.confirm)}</label></fieldset><button type="submit">${escape(t.begin)}</button></form>`;
  }
  return `<section>${context}${content}<p>${escape(t.note)}</p></section><a href="/?lang=${lang}">${escape(t.back)}</a>`;
}
