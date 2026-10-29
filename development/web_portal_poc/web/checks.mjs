import { createHmac, timingSafeEqual, randomUUID } from 'node:crypto';
import { LambdaClient, InvokeCommand } from '@aws-sdk/client-lambda';
import { readFileSync } from 'node:fs';
const labels=JSON.parse(readFileSync(new URL('./check-labels.json',import.meta.url),'utf8'));

export const tasks=Object.freeze(Array.from({length:7},(_,i)=>[`P${i}`,`M${i}`]).flat());
const uuid=v=>typeof v==='string' && /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(v);
const escape=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const words={
  ja:{title:'課題の確認',select:'確認する課題',start:'この課題を確認する',refresh:'結果を更新する',pending:'確認を実行中です。通常は1〜2分かかります。',done:'今回の確認結果',fail:'確認を完了できませんでした。Labとサーバーの状態を確認してください。',busy:'別の課題を確認中です。先ほどの確認画面へ戻ってください。',unavailable:'現在は確認できません。教師・学生のLabと5台の管理接続を確認してください。',note:'確認後、結果を成績原本へ自動保存します。未確認がある場合は確定済みの点数を維持します。PとM0は成績外です。サーバーは自動起動しません。',limits:'M3の停止前後の証拠、M5・M6のパスワードを使う機能確認は、この画面では未確認になります。',points:'今回の素点',practice:'練習・準備（成績外）',unknown:'未確認を含みます。確定点ではありません。',check:'確認項目',status:'結果',PASS:'合格',FAIL:'不合格',UNKNOWN:'未確認',back:'課題を選び直す',grades:'保存済み成績を見る',home:'トップへ',denied:'本人の登録またはログインを確認してください。'},
  ru:{title:'Проверка задания',select:'Задание для проверки',start:'Проверить это задание',refresh:'Обновить результат',pending:'Проверка выполняется. Обычно требуется 1–2 минуты.',done:'Результат этой проверки',fail:'Не удалось завершить проверку. Проверьте Lab и серверы.',busy:'Другая проверка уже выполняется. Вернитесь к её странице.',unavailable:'Проверка недоступна. Проверьте Lab преподавателя и студента и управление пятью серверами.',note:'После проверки результат автоматически сохраняется в журнале. При непроверенных пунктах прежняя оценка сохраняется. P и M0 не оцениваются. Серверы автоматически не запускаются.',limits:'Свидетельства остановки M3 и функциональные проверки с паролем M5/M6 здесь остаются непроверенными.',points:'Баллы этой проверки',practice:'Практика/подготовка (без оценки)',unknown:'Есть непроверенные пункты. Баллы не окончательные.',check:'Пункт проверки',status:'Результат',PASS:'Пройдено',FAIL:'Не пройдено',UNKNOWN:'Не проверено',back:'Выбрать задание',grades:'Сохранённые оценки',home:'На главную',denied:'Проверьте вход и регистрацию своей среды.'},
  uz:{title:'Vazifani tekshirish',select:'Tekshiriladigan vazifa',start:'Ushbu vazifani tekshirish',refresh:'Natijani yangilash',pending:'Tekshiruv bajarilmoqda. Odatda 1–2 daqiqa davom etadi.',done:'Ushbu tekshiruv natijasi',fail:'Tekshiruv tugamadi. Lab va serverlar holatini tekshiring.',busy:'Boshqa tekshiruv bajarilmoqda. Avvalgi sahifaga qayting.',unavailable:'Hozir tekshirib bo‘lmaydi. O‘qituvchi va talaba Lab hamda besh server ulanishini tekshiring.',note:'Tekshiruvdan keyin natija asosiy jurnalga avtomatik saqlanadi. Tekshirilmagan bandlar bo‘lsa, avvalgi ball saqlanadi. P va M0 baholanmaydi. Serverlar avtomatik ishga tushmaydi.',limits:'M3 to‘xtatish dalili va M5/M6 parol bilan funksional tekshiruvlar bu sahifada tekshirilmagan bo‘lib qoladi.',points:'Ushbu tekshiruv bali',practice:'Mashq/tayyorgarlik (baholanmaydi)',unknown:'Tekshirilmagan bandlar mavjud. Ball yakuniy emas.',check:'Tekshiruv bandi',status:'Natija',PASS:'O‘tdi',FAIL:'O‘tmadi',UNKNOWN:'Tekshirilmagan',back:'Vazifani tanlash',grades:'Saqlangan baholar',home:'Bosh sahifa',denied:'Kirish va o‘z muhitingiz ro‘yxatini tekshiring.'},
};
export function validOperation(value) {
  return value && tasks.includes(value.task_id) && uuid(value.job_id) && ['start','advance','result','submit'].includes(value.operation);
}
export function checkToken(config,session,token,value) {
  if (!validOperation(value) || !/^[a-f0-9]{64}$/.test(session||'') || typeof token!=='string') throw Error('Invalid check');
  return createHmac('sha256',config.secret).update(JSON.stringify(['jdu-portal/check/v1',config.origin,session,token,value.operation,value.task_id,value.job_id])).digest('hex');
}
export function verifyCheckToken(config,session,token,value,supplied) {
  return typeof supplied==='string' && /^[a-f0-9]{64}$/.test(supplied) && timingSafeEqual(Buffer.from(supplied,'hex'),Buffer.from(checkToken(config,session,token,value),'hex'));
}
export function createCheckerClient(env=process.env,client=new LambdaClient({region:'us-east-1'})) {
  const account=env.PORTAL_AWS_ACCOUNT_ID,arn=env.CHECKER_FUNCTION_ARN;
  if (!/^[0-9]{12}$/.test(account||'') || !new RegExp(`^arn:aws:lambda:us-east-1:${account}:function:[A-Za-z0-9_-]+$`).test(arn||'')) throw Error('Invalid checker');
  return async event=>{
    if (!validOperation(event) || !/^[0-9]{1,128}$/.test(event.subject||'')) throw Error('Invalid check');
    const result=await client.send(new InvokeCommand({FunctionName:arn,InvocationType:'RequestResponse',Payload:Buffer.from(JSON.stringify(event))}),{abortSignal:AbortSignal.timeout(38000)});
    if (result.FunctionError || result.StatusCode!==200 || !result.Payload || result.Payload.length>65536) throw Error('Unavailable');
    const value=JSON.parse(Buffer.from(result.Payload).toString('utf8'));
    if (!['ok','busy','unauthorized','unavailable'].includes(value?.status)) throw Error('Unavailable');
    return value;
  };
}
function form(lang,value,csrf,content,label,auto=false) {
  return `<form action="/checks?lang=${lang}" method="post"${auto?' data-check-progress="true"':''}><input type="hidden" name="operation" value="${value.operation}"><input type="hidden" name="job_id" value="${value.job_id}"><input type="hidden" name="csrf" value="${csrf}">${content}<button type="submit">${escape(label)}</button></form>`;
}
const receiptWords={
  ja:{saved:'成績原本に保存しました。',unconfirmed:'未確認を含む結果を記録しました。確定済みの成績は維持しています。',practice:'練習・準備の記録を保存しました（成績外）。',pending:'確認は完了しましたが、成績原本への保存はまだ確認できません。',retry:'同じ結果の保存を再試行する',received:'原本への保存日時'},
  ru:{saved:'Результат сохранён в журнале оценок.',unconfirmed:'Результат с непроверенными пунктами записан. Прежняя оценка сохранена.',practice:'Результат практики/подготовки сохранён без оценки.',pending:'Проверка завершена, но сохранение в журнале пока не подтверждено.',retry:'Повторить сохранение того же результата',received:'Время сохранения в журнале'},
  uz:{saved:'Natija asosiy baholar jurnaliga saqlandi.',unconfirmed:'Tekshirilmagan bandlari bor natija yozildi. Avvalgi baho saqlandi.',practice:'Mashq/tayyorgarlik natijasi bahosiz saqlandi.',pending:'Tekshiruv tugadi, lekin asosiy jurnalga saqlash hali tasdiqlanmadi.',retry:'Aynan shu natijani saqlashni qayta urinish',received:'Jurnalga saqlangan vaqt'},
};
function submissionHtml(lang,result,selected,{config,session,token}) {
  const t=receiptWords[lang],saved=result.submission,value=result.result;
  if (saved?.status==='saved') {
    if (!uuid(saved.request_id) || saved.request_id!==value.request_id || !Number.isFinite(Date.parse(saved.received_at))
        || saved.evaluable!==value.score.evaluable || saved.counts_toward_assessment!==value.score.counts_toward_assessment) throw Error('Invalid submission receipt');
    const message=!saved.counts_toward_assessment?t.practice:saved.evaluable?t.saved:t.unconfirmed;
    return `<section><p role="status">${escape(message)}</p><p>${escape(t.received)}: ${escape(new Date(saved.received_at).toISOString())}</p></section>`;
  }
  if(saved && saved.status!=='pending')throw Error('Invalid submission state');
  const v={...selected,operation:'submit'};
  // Saving an already captured report never runs the checker again. GET only
  // displays this retry form; automatic saving happens in the finishing POST.
  return `<section><p role="status">${escape(t.pending)}</p>${form(lang,v,checkToken(config,session,token,v),`<input type="hidden" name="task_id" value="${v.task_id}">`,t.retry)}</section>`;
}
export function checkHtml(lang,{config,session,token,selected,result}={}) {
  const t=words[lang],links=`<p><a href="/checks?lang=${lang}">${escape(t.back)}</a> · <a href="/grades?lang=${lang}">${escape(t.grades)}</a> · <a href="/?lang=${lang}">${escape(t.home)}</a></p>`;
  const note=`<p>${escape(t.note)}</p><p>${escape(t.limits)}</p>`;
  if (!selected) {
    const value={operation:'start',task_id:'P0',job_id:randomUUID()};
    // Each task has its own action-bound token. No client script is required.
    const forms=tasks.map(task_id=>{const v={...value,task_id,job_id:randomUUID()};return `<section><h2>${task_id}</h2>${form(lang,v,checkToken(config,session,token,v),`<input type="hidden" name="task_id" value="${task_id}">`,t.start)}</section>`;}).join('');
    return note+'<div class="check-tasks">'+forms+'</div>'+links;
  }
  if (!validOperation(selected)) throw Error('Invalid selection');
  if (result?.status!=='ok') return `<p role="alert">${escape(result?.status==='busy'?t.busy:result?.status==='unauthorized'?t.denied:t.unavailable)}</p>`+links;
  const job=result.job;
  if (!job || job.job_id!==selected.job_id || job.task_id!==selected.task_id || !['queued','dispatching','observing','report_ready','failed'].includes(job.phase)) throw Error('Invalid job');
  let content=`<h2>${escape(selected.task_id)}</h2>`;
  if (job.phase==='failed') return content+`<p role="alert">${escape(t.fail)}</p>`+links;
  if (job.phase!=='report_ready') {
    const v={...selected,operation:'advance'};
    return content+`<p role="status">${escape(t.pending)}</p>`+form(lang,v,checkToken(config,session,token,v),`<input type="hidden" name="task_id" value="${v.task_id}">`,t.refresh,true)+note+links+'<script src="/check-progress.js" defer></script>';
  }
  const value=result.result,s=value?.score;
  if (!value || value.task_id!==selected.task_id || !Array.isArray(value.checks) || value.checks.length>40 || !Number.isInteger(s?.raw_earned) || !Number.isInteger(s?.raw_maximum) || s.raw_earned<0 || s.raw_earned>s.raw_maximum || !Number.isFinite(Date.parse(value.checked_at))) throw Error('Invalid result');
  const rows=value.checks.map(c=>{if (!/^WEB[A-Z0-9_]{1,60}$/.test(c.id||'') || !['PASS','FAIL','UNKNOWN','NOT_APPLICABLE'].includes(c.status)) throw Error('Invalid check');return `<tr><th scope="row">${escape(c.id)}${labels[lang]?.[c.id]?`<br><small>${escape(labels[lang][c.id])}</small>`:''}</th><td>${escape(t[c.status]||t.UNKNOWN)}</td></tr>`;}).join('');
  content+=`<h3>${escape(t.done)}</h3><p>${escape(new Date(value.checked_at).toISOString())}</p><p class="num">${escape(s.counts_toward_assessment?`${t.points}: ${s.raw_earned} / ${s.raw_maximum}`:t.practice)}</p>${s.evaluable?'':`<p role="status">${escape(t.unknown)}</p>`}<div class="table-wrap"><table><thead><tr><th>${escape(t.check)}</th><th>${escape(t.status)}</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  return content+submissionHtml(lang,result,selected,{config,session,token})+note+links;
}
export const progressScript=`const form=document.querySelector('form[data-check-progress]'); if(form){const key='jdu-check-polls:'+new FormData(form).get('job_id');let n=Number(sessionStorage.getItem(key)||0);if(n<40){setTimeout(()=>{sessionStorage.setItem(key,String(n+1));form.requestSubmit();},4000);}}`;
