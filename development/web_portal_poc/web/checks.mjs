import { createHmac, timingSafeEqual, randomUUID,createPublicKey,publicEncrypt,constants } from 'node:crypto';
import { LambdaClient, InvokeCommand } from '@aws-sdk/client-lambda';
import { readFileSync } from 'node:fs';
const labels=JSON.parse(readFileSync(new URL('./check-labels.json',import.meta.url),'utf8'));

export const tasks=Object.freeze([...[0,1,2,4].flatMap(i=>[`P${i}`,`M${i}`]),'P5','P6','M5','M6']);
const uuid=v=>typeof v==='string' && /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(v);
const escape=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const words={
  ja:{title:'課題の確認',start:'この課題を確認する',refresh:'結果を更新する',pending:'確認を実行中です。通常は1〜2分かかります。',done:'今回の確認結果',fail:'確認を完了できませんでした。Labとサーバーの状態を確認してください。',busy:'別の課題を確認中です。先ほどの確認画面へ戻ってください。',unavailable:'現在は確認できません。教師・学生のLabと5台の管理接続を確認してください。',status:'結果',back:'課題を選び直す',home:'トップへ',denied:'本人の登録またはログインを確認してください。'},
  ru:{title:'Проверка задания',start:'Проверить это задание',refresh:'Обновить результат',pending:'Проверка выполняется. Обычно требуется 1–2 минуты.',done:'Результат этой проверки',fail:'Не удалось завершить проверку. Проверьте Lab и серверы.',busy:'Другая проверка уже выполняется. Вернитесь к её странице.',unavailable:'Проверка недоступна. Проверьте Lab преподавателя и студента и управление пятью серверами.',status:'Результат',back:'Выбрать задание',home:'На главную',denied:'Проверьте вход и регистрацию своей среды.'},
  uz:{title:'Vazifani tekshirish',start:'Ushbu vazifani tekshirish',refresh:'Natijani yangilash',pending:'Tekshiruv bajarilmoqda. Odatda 1–2 daqiqa davom etadi.',done:'Ushbu tekshiruv natijasi',fail:'Tekshiruv tugamadi. Lab va serverlar holatini tekshiring.',busy:'Boshqa tekshiruv bajarilmoqda. Avvalgi sahifaga qayting.',unavailable:'Hozir tekshirib bo‘lmaydi. O‘qituvchi va talaba Lab hamda besh server ulanishini tekshiring.',status:'Natija',back:'Vazifani tanlash',home:'Bosh sahifa',denied:'Kirish va o‘z muhitingiz ro‘yxatini tekshiring.'},
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
  ja:{pending:'結果の保存を確認できません。',retry:'保存を再試行する'},
  ru:{pending:'Сохранение результата не подтверждено.',retry:'Повторить сохранение'},
  uz:{pending:'Natija saqlangani tasdiqlanmadi.',retry:'Qayta saqlash'},
};
function submissionHtml(lang,result,selected,{config,session,token}) {
  const t=receiptWords[lang],saved=result.submission,value=result.result;
  if (saved?.status==='saved') {
    if (!uuid(saved.request_id) || saved.request_id!==value.request_id || !Number.isFinite(Date.parse(saved.received_at))
        || saved.evaluable!==value.score.evaluable || saved.counts_toward_assessment!==value.score.counts_toward_assessment) throw Error('Invalid submission receipt');
    return '';
  }
  if(saved && saved.status!=='pending')throw Error('Invalid submission state');
  const v={...selected,operation:'submit'};
  // Saving an already captured report never runs the checker again. GET only
  // displays this retry form; automatic saving happens in the finishing POST.
  return `<div class="check-save"><p role="alert">${escape(t.pending)}</p>${form(lang,v,checkToken(config,session,token,v),`<input type="hidden" name="task_id" value="${v.task_id}">`,t.retry)}</div>`;
}
export function taskActions(lang,task,{config,session,token}) {
  if(!tasks.includes(task)) throw Error('Invalid task');
  const st=specialWords[lang];
  const render=mode=>{
    const value={operation:'start',task_id:task,job_id:randomUUID(),...(mode?{check_mode:mode}:{})};
    return form(lang,value,checkToken(config,session,token,value),
      `<input type="hidden" name="task_id" value="${task}">`,mode?st.functional:/^[PM][56]$/.test(task)?st.readOnly:words[lang].start);
  };
  return /^[PM][56]$/.test(task)?render('functional')+render():render();
}

const criteriaText={
  ja:{criterion:'採点基準',PASS:'OK',FAIL:'要修正',UNKNOWN:'未確認',NOT_APPLICABLE:'対象外'},
  ru:{criterion:'Критерий оценки',PASS:'Выполнен',FAIL:'Исправить',UNKNOWN:'Не проверен',NOT_APPLICABLE:'Неприменимо'},
  uz:{criterion:'Baholash mezoni',PASS:'Bajarildi',FAIL:'Tuzating',UNKNOWN:'Tekshirilmagan',NOT_APPLICABLE:'Tatbiq etilmaydi'},
};
const outcomes={
  ja:{pass:'合格',fix:'修正が必要',unknown:'確認できない項目があります',practice:'確認完了',count:'項目クリア'},
  ru:{pass:'Зачтено',fix:'Нужны исправления',unknown:'Не всё удалось проверить',practice:'Проверка завершена',count:'критериев выполнено'},
  uz:{pass:'O‘tdi',fix:'Tuzatish kerak',unknown:'Ayrim bandlarni tekshirib bo‘lmadi',practice:'Tekshiruv tugadi',count:'mezon bajarildi'},
};
const checkOrder=['FAIL','UNKNOWN','PASS','NOT_APPLICABLE'];
const validCriterion=c=>c && /^WEB[A-Z0-9_]{1,60}$/.test(c.id||'') && checkOrder.includes(c.status);

function criteriaTable(lang,checks) {
  const t=criteriaText[lang];
  const rows=[...checks].sort((a,b)=>checkOrder.indexOf(a.status)-checkOrder.indexOf(b.status)).map(c=>{
    const style={FAIL:'score-unmet',PASS:'score-full',UNKNOWN:'score-partial'}[c.status]||'score-empty';
    return `<tr data-check-id="${escape(c.id)}"><th scope="row">${escape(labels[lang][c.id]||c.id)}</th>
      <td><span class="check-status ${style}">${escape(t[c.status])}</span></td></tr>`;
  }).join('');
  return `<div class="table-wrap" role="region" aria-label="${escape(t.criterion)}" tabindex="0"><table class="criteria-table">
    <thead><tr><th scope="col">${escape(t.criterion)}</th><th scope="col">${escape(words[lang].status)}</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

export function taskDetailHtml(lang,task,grade,maximum,actions='') {
  const saved=grade?.selected?.[task];
  const [scoreTitle,pending]={
    ja:['保存済みの点数','未採点'],
    ru:['Сохранённые баллы','Без оценки'],
    uz:['Saqlangan ball','Baholanmagan'],
  }[lang];
  const checks=(Array.isArray(grade?.task_checks)?grade.task_checks:[]).slice(0,40).filter(validCriterion);
  const score=saved?`<p class="check-count">${scoreTitle} <strong>${saved.raw_earned} / ${maximum}</strong></p>`:maximum?`<p>${pending}</p>`:'';
  return `<section class="task-detail"><div class="check-heading"><h2>${escape(task)}</h2>${score}</div>
    ${actions?`<div class="task-actions">${actions}</div>`:''}
    ${maximum && checks.length?criteriaTable(lang,checks):''}</section>`;
}

export function checkHtml(lang,{config,session,token,selected,result,grade,maxima={},blocked=false}={}) {
  const t=words[lang];
  const st=specialWords[lang];
  if (!selected) {
    const forms=tasks.map(task_id=>{
      const saved=grade?.selected[task_id];
      const maximum=maxima[task_id];
      const score=saved?`${saved.raw_earned} / ${maximum}`:maximum?
        {ja:'未採点',ru:'Без оценки',uz:'Baholanmagan'}[lang]:'—';
      const status=saved?(saved.raw_earned===maximum?'score-full':'score-partial'):'score-empty';
      const actions=blocked?'':taskActions(lang,task_id,{config,session,token});
      return `<tr><th scope="row"><a href="/checks?lang=${lang}&amp;task_id=${task_id}">${task_id}</a></th><td><span class="task-score ${status}">${score}</span></td><td><div class="task-actions">${actions}</div></td></tr>`;
    }).join('');
    const [taskTitle,scoreTitle,actionTitle]={
      ja:['課題','保存済みの点数','操作'],ru:['Задание','Сохранённые баллы','Действие'],
      uz:['Vazifa','Saqlangan ball','Amal'],
    }[lang];
    return `<div class="table-wrap student-table" role="region" aria-label="${escape(t.title)}" tabindex="0">
      <table><thead><tr><th scope="col">${taskTitle}</th><th scope="col">${scoreTitle}</th><th scope="col">${actionTitle}</th></tr></thead>
      <tbody>${forms}</tbody></table></div>`;
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
  if (!value.checks.every(validCriterion)) throw Error('Invalid check');
  const outcome=!s.evaluable?'unknown':!s.counts_toward_assessment?'practice':s.raw_earned===s.raw_maximum?'pass':'fix';
  const copy=outcomes[lang];
  const count=s.counts_toward_assessment?`<p class="check-count"><strong>${s.raw_earned} / ${s.raw_maximum}</strong> ${escape(copy.count)}</p>`:'';
  const criteria=s.counts_toward_assessment && value.checks.length ? criteriaTable(lang,value.checks) : '';
  return content+`<div class="check-heading check-outcome check-outcome-${outcome}"><h3>${escape(copy[outcome])}</h3>${count}</div>`
    +submissionHtml(lang,result,selected,{config,session,token})+criteria;
}
export const progressScript=`const form=document.querySelector('form[data-check-progress]'); if(form){const key='jdu-check-polls:'+new FormData(form).get('job_id');let n=Number(sessionStorage.getItem(key)||0);if(n<40){setTimeout(()=>{sessionStorage.setItem(key,String(n+1));form.requestSubmit();},4000);}}`;

const specialWords={
  ja:{overview:'P5/M5・P6/M6は既存パスワードを使い、アプリの機能・権限を確認します。',prepare:'停止前の状態を記録する',functional:'機能・権限を含めて確認する',readOnly:'現在の設定だけ確認する',password:'アプリ管理者の既存パスワード',passwordNote:'アプリへのログイン、確認専用の架空データの作成・編集・公開反映、ログアウトとアクセス拒否を確認します。',privatePassword:'パスワードはこの確認だけに使います。確認結果やコマンド履歴に平文で保存しません。',runFunctional:'このパスワードで確認する',stopNote:'停止前の状態を記録しました。AWSでこのWebだけを停止し、停止完了後に下のボタンを押してください。',restartNote:'同じWebの停止を確認しました。AWSでこのWebを開始し、起動後に下のボタンを押してください。',openAws:'AWSでこのWebを開く',observe:'停止完了を確認する',resume:'再開後の保持を確認する'},
  ru:{overview:'P5/M5 и P6/M6 проверяют функции и права с существующим паролем.',prepare:'Записать состояние до остановки',functional:'Проверить функции и права',readOnly:'Проверить только текущие настройки',password:'Существующий пароль администратора приложения',passwordNote:'Проверяются вход, создание и изменение отдельной тестовой записи, публикация, выход и запреты доступа.',privatePassword:'Пароль используется только для этой проверки. В результаты и историю команд он не записывается открытым текстом.',runFunctional:'Проверить с этим паролем',stopNote:'Состояние до остановки записано. Остановите только этот Web в AWS, затем подтвердите остановку ниже.',restartNote:'Остановка того же Web подтверждена. Запустите его в AWS и после запуска выполните проверку ниже.',openAws:'Открыть этот Web в AWS',observe:'Подтвердить остановку',resume:'Проверить сохранность после запуска'},
  uz:{overview:'P5/M5 va P6/M6 mavjud parol bilan funksiya va huquqlarni tekshiradi.',prepare:'To‘xtatishdan oldingi holatni yozish',functional:'Funksiya va huquqlarni tekshirish',readOnly:'Faqat joriy sozlamalarni tekshirish',password:'App administratorining mavjud paroli',passwordNote:'Kirish, alohida sinov yozuvini yaratish va o‘zgartirish, ommaviy aks etishi, chiqish va kirish rad etilishi tekshiriladi.',privatePassword:'Parol faqat shu tekshiruvda ishlatiladi. Natija yoki command tarixiga ochiq matnda saqlanmaydi.',runFunctional:'Shu parol bilan tekshirish',stopNote:'Oldingi holat yozildi. AWS orqali faqat shu Web serverni to‘xtating, keyin quyida tasdiqlang.',restartNote:'Aynan shu Web to‘xtagani tasdiqlandi. Uni AWS orqali ishga tushiring va keyin quyidagi tekshiruvni bajaring.',openAws:'Shu Web serverni AWSda ochish',observe:'To‘xtaganini tasdiqlash',resume:'Qayta ishga tushgandan keyin saqlanishni tekshirish'},
};
