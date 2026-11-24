import { createHmac, timingSafeEqual, randomUUID,createPublicKey,publicEncrypt,constants } from 'node:crypto';
import { LambdaClient, InvokeCommand } from '@aws-sdk/client-lambda';
import { readFileSync } from 'node:fs';
const labels=JSON.parse(readFileSync(new URL('./check-labels.json',import.meta.url),'utf8'));

export const tasks=Object.freeze([...[0,1,2,4].flatMap(i=>[`P${i}`,`M${i}`]),'P5','P6','M5','M6']);
const uuid=v=>typeof v==='string' && /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(v);
const escape=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const words={
  ja:{title:'課題の確認',select:'確認する課題',start:'この課題を確認する',refresh:'結果を更新する',pending:'確認を実行中です。通常は1〜2分かかります。',done:'今回の確認結果',fail:'確認を完了できませんでした。Labとサーバーの状態を確認してください。',busy:'別の課題を確認中です。先ほどの確認画面へ戻ってください。',unavailable:'現在は確認できません。教師・学生のLabと5台の管理接続を確認してください。',note:'確認後、結果を成績原本へ自動保存します。未確認がある場合は確定済みの点数を維持します。P0とM0は各1点です。サーバーは自動起動しません。',limits:'M5・M6の機能確認には、アプリ管理者の既存パスワードを使います。',points:'今回の素点',practice:'練習・準備（成績外）',unknown:'未確認を含みます。確定点ではありません。',check:'確認項目',status:'結果',PASS:'合格',FAIL:'不合格',UNKNOWN:'未確認',back:'課題を選び直す',grades:'保存済み成績を見る',home:'トップへ',denied:'本人の登録またはログインを確認してください。'},
  ru:{title:'Проверка задания',select:'Задание для проверки',start:'Проверить это задание',refresh:'Обновить результат',pending:'Проверка выполняется. Обычно требуется 1–2 минуты.',done:'Результат этой проверки',fail:'Не удалось завершить проверку. Проверьте Lab и серверы.',busy:'Другая проверка уже выполняется. Вернитесь к её странице.',unavailable:'Проверка недоступна. Проверьте Lab преподавателя и студента и управление пятью серверами.',note:'После проверки результат автоматически сохраняется в журнале. При непроверенных пунктах прежняя оценка сохраняется. За P0 и M0 начисляется по 1 баллу. Серверы автоматически не запускаются.',limits:'Для функциональных проверок M5/M6 используется существующий пароль администратора приложения.',points:'Баллы этой проверки',practice:'Практика/подготовка (без оценки)',unknown:'Есть непроверенные пункты. Баллы не окончательные.',check:'Пункт проверки',status:'Результат',PASS:'Пройдено',FAIL:'Не пройдено',UNKNOWN:'Не проверено',back:'Выбрать задание',grades:'Сохранённые оценки',home:'На главную',denied:'Проверьте вход и регистрацию своей среды.'},
  uz:{title:'Vazifani tekshirish',select:'Tekshiriladigan vazifa',start:'Ushbu vazifani tekshirish',refresh:'Natijani yangilash',pending:'Tekshiruv bajarilmoqda. Odatda 1–2 daqiqa davom etadi.',done:'Ushbu tekshiruv natijasi',fail:'Tekshiruv tugamadi. Lab va serverlar holatini tekshiring.',busy:'Boshqa tekshiruv bajarilmoqda. Avvalgi sahifaga qayting.',unavailable:'Hozir tekshirib bo‘lmaydi. O‘qituvchi va talaba Lab hamda besh server ulanishini tekshiring.',note:'Tekshiruvdan keyin natija asosiy jurnalga avtomatik saqlanadi. Tekshirilmagan bandlar bo‘lsa, avvalgi ball saqlanadi. P0 va M0 uchun 1 balldan beriladi. Serverlar avtomatik ishga tushmaydi.',limits:'M5/M6 funksional tekshiruvlari app administratorining mavjud parolidan foydalanadi.',points:'Ushbu tekshiruv bali',practice:'Mashq/tayyorgarlik (baholanmaydi)',unknown:'Tekshirilmagan bandlar mavjud. Ball yakuniy emas.',check:'Tekshiruv bandi',status:'Natija',PASS:'O‘tdi',FAIL:'O‘tmadi',UNKNOWN:'Tekshirilmagan',back:'Vazifani tanlash',grades:'Saqlangan baholar',home:'Bosh sahifa',denied:'Kirish va o‘z muhitingiz ro‘yxatini tekshiring.'},
};
export function validOperation(value) {
  const mode=value?.check_mode||'read_only';
  return value && tasks.includes(value.task_id) && uuid(value.job_id)
    && ['read_only','functional'].includes(mode)
    && (mode!=='storage' || /^[PM]3$/.test(value.task_id))
    && (mode!=='functional' || /^[PM][56]$/.test(value.task_id))
    && (['start','advance','result','submit'].includes(value.operation)
        || mode==='storage' && ['storage_observe','storage_resume'].includes(value.operation)
        || mode==='functional' && ['functional_context','functional_start'].includes(value.operation));
}
export function checkToken(config,session,token,value) {
  if (!validOperation(value) || !/^[a-f0-9]{64}$/.test(session||'') || typeof token!=='string') throw Error('Invalid check');
  return createHmac('sha256',config.secret).update(JSON.stringify(['jdu-portal/check/v1',config.origin,session,token,value.operation,value.task_id,value.job_id,...(value.check_mode?[value.check_mode]:[])])).digest('hex');
}

export function sealApplicationPassword(password,recipient,jobId) {
  if(typeof password!=='string' || password.length<1 || password.length>128 || /[\x00-\x1f\x7f]/u.test(password)
      || recipient?.job_id!==jobId || !uuid(jobId) || typeof recipient.public_key!=='string' || recipient.public_key.length>2048)throw Error('Invalid password recipient');
  const key=createPublicKey(recipient.public_key);
  if(key.asymmetricKeyType!=='rsa' || key.asymmetricKeyDetails?.modulusLength!==4096)throw Error('Invalid password recipient');
  const raw=Buffer.from(JSON.stringify([jobId,password]));
  if(raw.length>446)throw Error('Password delivery exceeds RSA4096 bound');
  return publicEncrypt({key,padding:constants.RSA_PKCS1_OAEP_PADDING,oaepHash:'sha256'},raw).toString('base64');
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
  return `<form action="/checks?lang=${lang}" method="post"${auto?' data-check-progress="true"':''}><input type="hidden" name="operation" value="${value.operation}"><input type="hidden" name="job_id" value="${value.job_id}"><input type="hidden" name="csrf" value="${csrf}">${value.check_mode?`<input type="hidden" name="check_mode" value="${value.check_mode}">`:''}${content}<button type="submit">${escape(label)}</button></form>`;
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
export function checkHtml(lang,{config,session,token,selected,result,grade,maxima={},blocked=false}={}) {
  const t=words[lang];
  const st=specialWords[lang];
  if (!selected) {
    const value={operation:'start',task_id:'P0',job_id:randomUUID()};
    // Each task has its own action-bound token. No client script is required.
    const forms=tasks.map(task_id=>{
      const mode=/^[PM]3$/.test(task_id)?'storage':/^[PM][56]$/.test(task_id)?'functional':null;
      const v={...value,task_id,job_id:randomUUID(),...(mode?{check_mode:mode}:{})};
      const normal={...value,task_id,job_id:randomUUID()};
      const saved=grade?.selected[task_id];
      const points=Object.hasOwn(maxima,task_id) ? `<span class="task-score" aria-label="${escape(t.grades)}: ${saved?`${saved.raw_earned} / ${maxima[task_id]}`:'—'}">${saved?`${saved.raw_earned} / ${maxima[task_id]}`:'—'}</span>` : '';
      const heading=`<div class="task-heading"><h2>${task_id}</h2>${points}</div>`;
      if(blocked) return `<section>${heading}</section>`;
      return `<section>${heading}${form(lang,v,checkToken(config,session,token,v),`<input type="hidden" name="task_id" value="${task_id}">`,mode==='storage'?st.prepare:mode==='functional'?st.functional:t.start)}${mode?form(lang,normal,checkToken(config,session,token,normal),`<input type="hidden" name="task_id" value="${task_id}">`,st.readOnly):''}</section>`;
    }).join('');
    return '<div class="check-tasks">'+forms+'</div>';
  }
  if (!validOperation(selected)) throw Error('Invalid selection');
  if (result?.status!=='ok') return `<p role="alert">${escape(result?.status==='busy'?t.busy:result?.status==='unauthorized'?t.denied:t.unavailable)}</p>`;
  const job=result.job;
  if (!job || job.job_id!==selected.job_id || job.task_id!==selected.task_id || !['queued','dispatching','observing','report_ready','failed','awaiting_password','awaiting_stop','awaiting_restart'].includes(job.phase)
      || selected.check_mode && job.check_mode!==selected.check_mode) throw Error('Invalid job');
  let content=`<h2>${escape(selected.task_id)}</h2>`;
  if(job.phase==='awaiting_password') {
    if(selected.check_mode!=='functional')throw Error('Invalid functional step');
    const v={...selected,operation:'functional_start'};
    return content+`<p>${escape(st.passwordNote)}</p>`+form(lang,v,checkToken(config,session,token,v),
      `<input type="hidden" name="task_id" value="${v.task_id}"><label for="application-password">${escape(st.password)}</label><input id="application-password" name="password" type="password" autocomplete="current-password" minlength="1" maxlength="128" required aria-describedby="application-password-note"><p id="application-password-note">${escape(st.privatePassword)}</p>`,st.runFunctional);
  }
  if(job.phase==='awaiting_stop' || job.phase==='awaiting_restart') {
    if(selected.check_mode!=='storage' || !/^i-[a-f0-9]{17}$/.test(job.web_instance_id||''))throw Error('Invalid storage step');
    const stopped=job.phase==='awaiting_restart',v={...selected,operation:stopped?'storage_resume':'storage_observe'};
    return content+`<p role="status">${escape(stopped?st.restartNote:st.stopNote)}</p><p>Web: ${escape(job.web_instance_id)}</p><p><a href="https://us-east-1.console.aws.amazon.com/ec2/home?region=us-east-1#InstanceDetails:instanceId=${job.web_instance_id}" target="_blank" rel="noopener noreferrer">${escape(st.openAws)}</a></p>`
      +form(lang,v,checkToken(config,session,token,v),`<input type="hidden" name="task_id" value="${v.task_id}">`,stopped?st.resume:st.observe);
  }
  if (job.phase==='failed') return content+`<p role="alert">${escape(t.fail)}</p>`;
  if (job.phase!=='report_ready') {
    const v={...selected,operation:'advance'};
    return content+`<p role="status">${escape(t.pending)}</p>`+form(lang,v,checkToken(config,session,token,v),`<input type="hidden" name="task_id" value="${v.task_id}">`,t.refresh,true)+'<script src="/check-progress.js" defer></script>';
  }
  const value=result.result,s=value?.score;
  if (!value || value.task_id!==selected.task_id || !Array.isArray(value.checks) || value.checks.length>40 || !Number.isInteger(s?.raw_earned) || !Number.isInteger(s?.raw_maximum) || s.raw_earned<0 || s.raw_earned>s.raw_maximum || !Number.isFinite(Date.parse(value.checked_at))) throw Error('Invalid result');
  const rows=value.checks.map(c=>{if (!/^WEB[A-Z0-9_]{1,60}$/.test(c.id||'') || !['PASS','FAIL','UNKNOWN','NOT_APPLICABLE'].includes(c.status)) throw Error('Invalid check');return `<tr data-check-id="${escape(c.id)}"><th scope="row">${escape(labels[lang]?.[c.id] || c.id)}</th><td>${escape(t[c.status]||t.UNKNOWN)}</td></tr>`;}).join('');
  content+=`<h3>${escape(t.done)}</h3><p>${escape(new Date(value.checked_at).toISOString())}</p><p class="num">${escape(s.counts_toward_assessment?`${t.points}: ${s.raw_earned} / ${s.raw_maximum}`:t.practice)}</p>${s.evaluable?'':`<p role="status">${escape(t.unknown)}</p>`}<details><summary>${escape(t.check)}</summary><div class="table-wrap"><table><thead><tr><th>${escape(t.check)}</th><th>${escape(t.status)}</th></tr></thead><tbody>${rows}</tbody></table></div></details>`;
  return content+submissionHtml(lang,result,selected,{config,session,token});
}
export const progressScript=`const form=document.querySelector('form[data-check-progress]'); if(form){const key='jdu-check-polls:'+new FormData(form).get('job_id');let n=Number(sessionStorage.getItem(key)||0);if(n<40){setTimeout(()=>{sessionStorage.setItem(key,String(n+1));form.requestSubmit();},4000);}}`;

const specialWords={
  ja:{overview:'P5/M5・P6/M6は既存パスワードを使い、アプリの機能・権限を確認します。',prepare:'停止前の状態を記録する',functional:'機能・権限を含めて確認する',readOnly:'現在の設定だけ確認する',password:'アプリ管理者の既存パスワード',passwordNote:'アプリへのログイン、確認専用の架空データの作成・編集・公開反映、ログアウトとアクセス拒否を確認します。',privatePassword:'パスワードはこの確認だけに使います。確認結果やコマンド履歴に平文で保存しません。',runFunctional:'このパスワードで確認する',stopNote:'停止前の状態を記録しました。AWSでこのWebだけを停止し、停止完了後に下のボタンを押してください。',restartNote:'同じWebの停止を確認しました。AWSでこのWebを開始し、起動後に下のボタンを押してください。',openAws:'AWSでこのWebを開く',observe:'停止完了を確認する',resume:'再開後の保持を確認する'},
  ru:{overview:'P5/M5 и P6/M6 проверяют функции и права с существующим паролем.',prepare:'Записать состояние до остановки',functional:'Проверить функции и права',readOnly:'Проверить только текущие настройки',password:'Существующий пароль администратора приложения',passwordNote:'Проверяются вход, создание и изменение отдельной тестовой записи, публикация, выход и запреты доступа.',privatePassword:'Пароль используется только для этой проверки. В результаты и историю команд он не записывается открытым текстом.',runFunctional:'Проверить с этим паролем',stopNote:'Состояние до остановки записано. Остановите только этот Web в AWS, затем подтвердите остановку ниже.',restartNote:'Остановка того же Web подтверждена. Запустите его в AWS и после запуска выполните проверку ниже.',openAws:'Открыть этот Web в AWS',observe:'Подтвердить остановку',resume:'Проверить сохранность после запуска'},
  uz:{overview:'P5/M5 va P6/M6 mavjud parol bilan funksiya va huquqlarni tekshiradi.',prepare:'To‘xtatishdan oldingi holatni yozish',functional:'Funksiya va huquqlarni tekshirish',readOnly:'Faqat joriy sozlamalarni tekshirish',password:'App administratorining mavjud paroli',passwordNote:'Kirish, alohida sinov yozuvini yaratish va o‘zgartirish, ommaviy aks etishi, chiqish va kirish rad etilishi tekshiriladi.',privatePassword:'Parol faqat shu tekshiruvda ishlatiladi. Natija yoki command tarixiga ochiq matnda saqlanmaydi.',runFunctional:'Shu parol bilan tekshirish',stopNote:'Oldingi holat yozildi. AWS orqali faqat shu Web serverni to‘xtating, keyin quyida tasdiqlang.',restartNote:'Aynan shu Web to‘xtagani tasdiqlandi. Uni AWS orqali ishga tushiring va keyin quyidagi tekshiruvni bajaring.',openAws:'Shu Web serverni AWSda ochish',observe:'To‘xtaganini tasdiqlash',resume:'Qayta ishga tushgandan keyin saqlanishni tekshirish'},
};
