import { configFrom, cookies, cookie, login, loginTarget, callback, verifyGoogle, googleTestConfig, verifyGoogleTest, SESSION, FLOW } from './auth.mjs';
import { ACCESS } from './sessions.mjs';
import { formToken, checkForm, operationId, tokenHash } from './enrollment-client.mjs';
import { enrollmentHtml, enrollmentText, checkedEnrollment } from './enrollment-page.mjs';
import { preparationText, checkPreparationToken, checkedPreparation, preparationHtml,
  preparationTemplate, createPreparationLink } from './preparation.mjs';
import { bootstrapTemplate, createBootstrapLink } from './bootstrap-link.mjs';
import { words as checkWords, validOperation, verifyCheckToken, checkHtml, taskActions, taskDetailHtml, tasks as checkTasks, progressScript,sealApplicationPassword } from './checks.mjs';
import { teacherText, checkedTeacher, teacherListHtml } from './teacher-progress.mjs';
import { createInitialDelivery } from './initial-delivery.mjs';

const security = {
  'Cache-Control': 'private, no-store, max-age=0', 'Referrer-Policy': 'no-referrer',
  'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'X-Robots-Tag': 'noindex, nofollow, noarchive',
  'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
};
const text = {
  ja: { title:'Web演習', grades:'保存済みの成績', intro:'自分の学内Googleアカウントでログインしてください。',
    login:'Googleでログイン', logout:'ログアウト', total:'保存済みの素点', current:'最新の確認', unknown:'確認できない項目があります',
    noRecord:'記録なし', currentOk:'確認済み', back:'トップへ戻る', unavailable:'成績を取得できません。しばらくしてから再度お試しください。',
    unbound:'本人の演習環境がまだ登録されていません。先生に確認してください。', mission:'課題', score:'保存済み', home:'トップ', checked:'確認日時', received:'保存日時',
    status:'環境の状態', role:'サーバー', ec2:'稼働状態', ssm:'管理接続', publicIp:'公開IP', observed:'確認日時', statusUnavailable:'状態を確認できません。Learner Labと接続を確認してください。',
    notice:'環境の構築と新しい採点の画面は準備中です。成績や状態の確認ではサーバーを起動しません。',
    shared:'共有PCでは、使い終わったらこの画面とGoogleの両方からログアウトしてください。', signedout:'ログアウトしました。' },
  ru: { title:'Практика Web', grades:'Сохранённые результаты', intro:'Войдите с университетским аккаунтом Google.',
    login:'Войти через Google', logout:'Выйти', total:'Сохранённые баллы', current:'Последняя проверка', unknown:'Есть непроверенные пункты',
    noRecord:'Нет записи', currentOk:'Проверено', back:'На главную', unavailable:'Не удалось получить результат. Повторите попытку позже.',
    unbound:'Ваша учебная среда ещё не зарегистрирована. Обратитесь к преподавателю.', mission:'Задание', score:'Сохранено', home:'Главная', checked:'Время проверки', received:'Время сохранения',
    status:'Состояние среды', role:'Сервер', ec2:'Состояние', ssm:'Управление', publicIp:'Публичный IP', observed:'Время проверки', statusUnavailable:'Не удалось проверить состояние. Проверьте Learner Lab и подключение.',
    notice:'Создание среды и новая проверка готовятся. Просмотр результатов и состояния не запускает серверы.',
    shared:'На общем компьютере после работы выйдите здесь и из аккаунта Google.', signedout:'Вы вышли из системы.' },
  uz: { title:'Web amaliyoti', grades:'Saqlangan natijalar', intro:'Universitet Google hisobingiz bilan kiring.',
    login:'Google orqali kirish', logout:'Chiqish', total:'Saqlangan ball', current:'Oxirgi tekshiruv', unknown:'Tekshirib bo‘lmagan bandlar bor',
    noRecord:'Natija yo‘q', currentOk:'Tekshirilgan', back:'Bosh sahifaga', unavailable:'Natijani olib bo‘lmadi. Keyinroq qayta urinib ko‘ring.',
    unbound:'Sizning amaliy muhitingiz hali ro‘yxatdan o‘tmagan. O‘qituvchiga murojaat qiling.', mission:'Vazifa', score:'Saqlangan', home:'Bosh sahifa', checked:'Tekshirilgan vaqt', received:'Saqlangan vaqt',
    status:'Muhit holati', role:'Server', ec2:'Ishlash holati', ssm:'Boshqaruv', publicIp:'Ommaviy IP', observed:'Tekshirilgan vaqt', statusUnavailable:'Holatni tekshirib bo‘lmadi. Learner Lab va ulanishni tekshiring.',
    notice:'Muhit yaratish va yangi tekshiruv tayyorlanmoqda. Natija va holatni ko‘rish serverlarni ishga tushirmaydi.',
    shared:'Umumiy kompyuterda ish tugagach, bu yerdan va Google hisobidan chiqing.', signedout:'Tizimdan chiqdingiz.' },
};
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const LEGACY_MAXIMA=Object.freeze({M1:8,M2:13,M4:9,M5:13,M6:16});
export const MISSION_MAXIMA=Object.freeze({P0:1,M0:4,...LEGACY_MAXIMA});
const stateText={
  ja:{running:'稼働中',stopped:'停止中',pending:'起動中',stopping:'停止処理中','shutting-down':'終了処理中',terminated:'終了済み',unknown:'確認できない',Online:'接続可',ConnectionLost:'接続なし',Inactive:'非アクティブ'},
  ru:{running:'Работает',stopped:'Остановлен',pending:'Запускается',stopping:'Останавливается','shutting-down':'Завершается',terminated:'Завершён',unknown:'Неизвестно',Online:'Доступно',ConnectionLost:'Нет связи',Inactive:'Неактивно'},
  uz:{running:'Ishlayapti',stopped:'To‘xtagan',pending:'Ishga tushmoqda',stopping:'To‘xtamoqda','shutting-down':'Tugatilmoqda',terminated:'Tugatilgan',unknown:'Noma’lum',Online:'Ulangan',ConnectionLost:'Aloqa yo‘q',Inactive:'Faol emas'},
};
const language = url => Object.hasOwn(text, url.searchParams.get('lang')) ? url.searchParams.get('lang') : 'ja';
const response = (body, status=200, extras={}) => new Response(body, {status, headers:{...security, 'Content-Type':'text/html; charset=utf-8', ...extras}});
const redirect = (location, values=[]) => { const h=new Headers(security); h.set('Location',location); for(const v of values) h.append('Set-Cookie',v); return new Response(null,{status:303,headers:h}); };

function page(lang, title, content, selection) {
  const tail=selection?.teacher ? Object.entries(selection.params).map(([k,v])=>`&amp;${k}=${encodeURIComponent(v)}`).join('') : selection?.task?`&amp;task_id=${selection.task}`:selection?`&amp;task_id=${selection.task_id}&amp;job_id=${selection.job_id}${selection.check_mode?`&amp;check_mode=${selection.check_mode}`:''}`:'';
  const nav = ['ja','ru','uz'].map(k => `<a href="?lang=${k}${tail}"${k===lang?' aria-current="page"':''}>${k.toUpperCase()}</a>`).join(' ');
  return `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)}</title><style>body{overflow-wrap:break-word;font:1rem/1.6 system-ui,sans-serif;margin:0;background:#f5f7fa;color:#182435}main{max-width:64rem;margin:auto;padding:1.5rem}nav{display:flex;flex-wrap:wrap;gap:1rem}a,button{color:#064ca4}button{font:inherit;background:white;border:1px solid #64748b;border-radius:.35rem;padding:.65rem 1rem;cursor:pointer}a:focus-visible,button:focus-visible{outline:3px solid #d34800;outline-offset:3px}section{background:white;border:1px solid #d6dee8;border-radius:.5rem;padding:1rem;margin-block:1rem}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:44rem}th,td{padding:.6rem;text-align:left;border-bottom:1px solid #d6dee8}.num{font-size:1.6rem;font-weight:700}footer{margin-top:2rem}li[aria-current=step]{font-weight:700}fieldset{border:1px solid #a9b6c7;border-radius:.35rem;padding:1rem;margin-block:1rem}.confirm{display:flex;align-items:flex-start;gap:.5rem;min-height:48px;padding-block:.5rem}input[type=password]{display:block;font:inherit;box-sizing:border-box;inline-size:min(100%,28rem);min-block-size:48px;padding:.6rem;margin-block:.4rem 1rem;border:1px solid #64748b;border-radius:.35rem}input[type=checkbox]{width:1.25rem;height:1.25rem;margin:.2rem 0;flex-shrink:0}a.action{display:inline-flex;align-items:center;min-height:48px;padding:0 .75rem;border:1px solid #64748b;border-radius:.35rem}a.action:focus-visible,input:focus-visible{outline:3px solid #d34800;outline-offset:3px}.page-toolbar{display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;margin-block:0 1rem}.score-overview{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.4rem 1.5rem;padding:1.15rem 1.5rem;background:#173454;color:white;border-color:#173454}.score-overview h2,.score-overview p{margin:0}.score-overview h2{font-size:1.05rem}.score-overview p{font-variant-numeric:tabular-nums;line-height:1.15;white-space:nowrap}.score-overview strong{font-size:clamp(2.4rem,6vw,4rem)}.score-overview span{font-size:1.25rem;color:#dae6f2}.student-table,.teacher-table{background:white;border:1px solid #d6dee8;border-radius:.5rem}.student-table table{min-width:24rem}.student-table thead th{background:#eaf0f7}.student-table th,.student-table td{padding:.5rem .85rem}.task-score{display:inline-block;padding:.16rem .5rem;border-radius:.25rem;font-size:1.13rem;font-weight:750;font-variant-numeric:tabular-nums;white-space:nowrap}.task-score.score-empty{color:#526576;font-size:1rem;font-weight:500}.task-detail h2{margin-top:0}.task-detail dl{display:grid;grid-template-columns:max-content 1fr;align-items:baseline;gap:.4rem 1rem}.task-detail dd{margin:0}.criteria-table{min-width:24rem}.criteria-table th[scope=row]{font-weight:500}.criteria-table td{width:1%;white-space:nowrap}.check-status{display:inline-block;border-radius:.25rem;padding:.12rem .4rem}.score-unmet{background:#fde8e7;color:#8d2725}.task-detail :is(th,td){padding:.5rem .75rem}.teacher-table td a{color:inherit;text-decoration-line:underline;text-underline-offset:.2em}.task-actions{display:flex;flex-wrap:wrap;gap:.35rem}.task-actions button{min-height:36px;padding:.3rem .75rem}.task-actions form:first-child button{background:#174f83;color:white;border-color:#174f83}.score-full{background:#e5f5ea;color:#176238}.score-partial{background:#fff1d7;color:#704900}.table-wrap:focus-visible{outline:3px solid #d34800;outline-offset:3px}summary{cursor:pointer;min-height:24px}#link-number{display:block;width:100%;box-sizing:border-box;font:1rem/1.5 monospace;padding:.6rem;margin-block:.4rem 1rem;overflow:auto}.teacher-table{max-block-size:70vh;overflow:auto}.teacher-table td{font-variant-numeric:tabular-nums}.teacher-table table{border-collapse:separate;border-spacing:0;min-width:57rem}.teacher-table .teacher-total{font-size:1.12rem;font-weight:750;color:#153d64;background:#edf4fa;white-space:nowrap}.teacher-table td:not(:first-child),.teacher-table thead th:not(:first-child){text-align:center}.teacher-table caption{text-align:left;font-weight:700;padding-block:.75rem}.teacher-table thead th{position:sticky;inset-block-start:0;background:#eaf0f7;z-index:2}.teacher-table tbody th{position:sticky;inset-inline-start:0;background:white;z-index:1}.teacher-table thead th:first-child{inset-inline-start:0;z-index:3}.teacher-table:focus-visible{outline:3px solid #d34800;outline-offset:3px}.registration-steps{max-inline-size:48rem}.registration-steps h2{margin-block-start:0}.registration-steps{padding-inline-start:1.75rem}.registration-steps li::marker{font-weight:700;color:#174f83}.registration-steps h2{font-size:1.25rem}button.primary-action{background:#174f83;border-color:#174f83;color:white;font-weight:700;text-decoration:none}button.primary-action:hover{background:#12395e}.registration-error{margin-block:0 1rem;padding:.75rem 1rem;background:#fff1f0;color:#7c201c;border:1px solid #c9564e;border-inline-start-width:4px;border-radius:.4rem}.registration-error p{margin-block:.25rem 0}#link-code[aria-invalid=true]{border:2px solid #ae322c}</style></head><body><main><nav aria-label="Languages">${nav}</nav><h1>${escape(title)}</h1>${content}</main></body></html>`;
}

const firstRegistration={
  ja:{title:'初回登録',run:'学生側のCloudShellで実行',paste:'連携コードを貼り付ける'},
  ru:{title:'Первичная регистрация',run:'Выполните команду в CloudShell студента',paste:'Вставьте код привязки'},
  uz:{title:'Birinchi ro‘yxatdan o‘tish',run:'Buyruqni talaba CloudShell muhitida bajaring',paste:'Bog‘lash kodini kiriting'},
};

export function portalExpired(env) {
  const limit=env.PORTAL_EXPIRES_AT;
  if (limit===undefined || limit==='') return false;
  return !/^[0-9]{10}$/.test(limit) || Date.now()>=Number(limit)*1000;
}

export function checkedGrade(grade) {
  if (!grade || !Number.isInteger(grade.raw_earned) || ![59,61,64].includes(grade.raw_maximum) || grade.raw_earned < 0 || grade.raw_earned > grade.raw_maximum || !Array.isArray(grade.current_unresolved) || !Array.isArray(grade.missing_or_unresolved) || !grade.selected || typeof grade.selected !== 'object') throw new Error('Invalid grade');
  const maxima=grade.raw_maximum===59?LEGACY_MAXIMA:grade.raw_maximum===61?{...MISSION_MAXIMA,M0:1}:MISSION_MAXIMA;
  if (Object.keys(grade.selected).some(id => !Object.hasOwn(maxima,id) || !Number.isInteger(grade.selected[id]?.raw_earned) || grade.selected[id].raw_earned < 0 || grade.selected[id].raw_earned > maxima[id]) || Object.values(grade.selected).reduce((sum,row)=>sum+row.raw_earned,0)!==grade.raw_earned) throw new Error('Invalid selected scores');
  return grade;
}

function gradeHtml(lang, grade) {
  const t=text[lang];
  checkedGrade(grade);
  const date = value => typeof value==='string' && value.length<=40 && Number.isFinite(Date.parse(value)) ? new Date(value).toISOString().slice(0,16).replace('T',' ')+' UTC' : t.noRecord;
  const rows = Object.keys(grade.raw_maximum===59?LEGACY_MAXIMA:MISSION_MAXIMA).map(id => {
    const saved=grade.selected[id];
    const score=saved && Number.isInteger(saved.raw_earned) ? String(saved.raw_earned) : t.noRecord;
    return `<tr><th scope="row">${id}</th><td>${escape(score)}</td><td>${escape(grade.current_unresolved.includes(id) ? t.unknown : grade.current?.[id] ? t.currentOk : t.noRecord)}</td><td>${escape(date(grade.current?.[id]?.checked_at))}</td><td>${escape(date(saved?.received_at))}</td></tr>`;
  }).join('');
  const total = Object.keys(grade.selected).length ? `${grade.raw_earned} / ${grade.raw_maximum}` : t.noRecord;
  const summary = grade.current_unresolved.length || grade.missing_or_unresolved.length ? t.unknown : t.currentOk;
  return `<section><h2>${escape(t.total)}</h2><p class="num">${escape(total)}</p><p>${escape(summary)}</p><div class="table-wrap"><table><thead><tr><th scope="col">${escape(t.mission)}</th><th scope="col">${escape(t.score)}</th><th scope="col">${escape(t.current)}</th><th scope="col">${escape(t.checked)}</th><th scope="col">${escape(t.received)}</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
}

function statusHtml(lang, observation) {
  const t=text[lang], roles=['bastion','web','dns','db','repo'];
  const states=new Set(['pending','running','shutting-down','terminated','stopping','stopped','unknown']);
  const ssm=new Set(['Online','ConnectionLost','Inactive','unknown']);
  if (!observation || !Array.isArray(observation.instances) || observation.instances.length!==5 ||
      typeof observation.observed_at!=='string' || !Number.isFinite(Date.parse(observation.observed_at))) throw new Error('Invalid status');
  const rows=new Map();
  for(const node of observation.instances) {
    if (!node || !roles.includes(node.role) || rows.has(node.role) || !states.has(node.ec2_state) || !ssm.has(node.ssm_state) ||
        (node.public_ip!==null && (typeof node.public_ip!=='string' || node.public_ip.length>45))) throw new Error('Invalid status');
    rows.set(node.role,node);
  }
  const timestamp=new Date(observation.observed_at).toISOString().slice(0,16).replace('T',' ')+' UTC';
  const body=roles.map(role=>{const node=rows.get(role);return `<tr><th scope="row">${escape(role)}</th><td>${escape(stateText[lang][node.ec2_state])}</td><td>${escape(stateText[lang][node.ssm_state])}</td><td>${escape(node.public_ip || '—')}</td></tr>`;}).join('');
  return `<section><p>${escape(t.observed)}: ${escape(timestamp)}</p><div class="table-wrap"><table><thead><tr><th scope="col">${escape(t.role)}</th><th scope="col">${escape(t.ec2)}</th><th scope="col">${escape(t.ssm)}</th><th scope="col">${escape(t.publicIp)}</th></tr></thead><tbody>${body}</tbody></table></div></section>`;
}

export function createApp({env=process.env, verify=verifyGoogle, verifyTestStudent=verifyGoogleTest, exchange=fetch, getGrade, getStatus, sessions, getAcceptanceHealth, enroll, checker, getTeacher}={}) {
  return async request => {
    const url=new URL(request.url), lang=language(url), t=text[lang];
    if (url.pathname === '/healthz') return new Response('ok',{headers:{...security,'Content-Type':'text/plain; charset=utf-8'}});
    if (portalExpired(env)) {
      const ended={ja:'採点ポータルの利用期間は終了しました。',ru:'Период работы портала завершён.',uz:'Baholash portalidan foydalanish muddati tugadi.'}[lang];
      return response(page(lang,t.title,`<p>${escape(ended)}</p>`),410);
    }
    if (url.pathname==='/check-progress.js' && request.method==='GET') return new Response(progressScript,{headers:{...security,'Content-Type':'text/javascript; charset=utf-8'}});
    if (url.pathname === '/healthz/acceptance') {
      if (env.PORTAL_MODE!=='closed' || env.PORTAL_ACCEPTANCE_ENABLED!=='true' || typeof getAcceptanceHealth!=='function') return response('Not found',404);
      if (!['GET','HEAD'].includes(request.method)) return response('Method not allowed',405);
      let result;
      try { result=await getAcceptanceHealth(); } catch { result={}; }
      const clean=Object.fromEntries(['storage','savedGrades','gradeService'].map(key=>[key,result?.[key]===true]));
      const healthy=Object.values(clean).every(Boolean);
      clean.checkedAt=typeof result?.checkedAt==='string' && result.checkedAt.length<=40 && Number.isFinite(Date.parse(result.checkedAt)) ? new Date(result.checkedAt).toISOString() : null;
      return new Response(JSON.stringify(clean),{status:healthy && clean.checkedAt?200:503,
        headers:{...security,'Content-Type':'application/json; charset=utf-8'}});
    }
    let config;
    try { config=configFrom(env); } catch { return response('Unavailable',503); }
    if (url.origin !== config.origin) return response('Forbidden',403);
    const enrollmentEnabled=env.PORTAL_ENROLLMENT_ENABLED==='true' && typeof enroll==='function';
    const selfLink=env.PORTAL_SELF_LINK_ENABLED==='true' && typeof enroll==='function';
    const testGoogle=selfLink ? googleTestConfig(env,config) : null;
    const preparationEnabled=env.PORTAL_PREPARATION_ENABLED==='true' && typeof enroll==='function';
    if (url.pathname==='/api/enrollment/complete' || url.pathname==='/api/preparation/complete') {
      // Server-to-server signed proof only. The nonce was minted by an active,
      // approved Google session; no self-declared Google identity is accepted.
      const preparing=url.pathname==='/api/preparation/complete';
      if (!(preparing?preparationEnabled:enrollmentEnabled)) return response('Not found',404);
      if (request.method!=='POST') return response('Method not allowed',405);
      if (url.search || request.headers.get('content-type')?.split(';')[0]!=='application/json') return response('Forbidden',403);
      try {
        const body=await request.text();
        if (Buffer.byteLength(body)>16384) return response('Payload too large',413);
        const value=JSON.parse(body);
        if (!value || Array.isArray(value) || Object.keys(value).sort().join(',')!=='pair_id,proof_url'
            || !/^[a-f0-9]{64}$/.test(value.pair_id||'') || typeof value.proof_url!=='string' || value.proof_url.length>8192) return response('Forbidden',403);
        const result=await enroll({operation:preparing?'prepare_complete':'complete',pair_id:value.pair_id,proof_url:value.proof_url});
        if (result?.status==='unauthorized') return response('Forbidden',403);
        const outcome=preparing?result?.preparation:result?.enrollment;
        if (result?.status!=='ok' || (preparing?outcome?.aws_confirmed!==true:outcome?.registered!==true)
            || !/^[a-z0-9][a-z0-9-]{2,31}$/.test(outcome?.lab_id||'')) return response('Unavailable',503);
        return new Response(JSON.stringify(preparing?{aws_confirmed:true}:{registered:true}),{headers:{...security,'Content-Type':'application/json; charset=utf-8'}});
      } catch {return response('Unavailable',503);}
    }
    const testRoute=url.pathname==='/auth/google-test' || url.pathname==='/auth/google-test/callback';
    if (testRoute && !testGoogle) return response('Not found',404);
    if ((url.pathname === '/auth/login' || url.pathname==='/auth/google-test') && request.method === 'GET') {
      try {
        const flow=await login(testRoute?testGoogle:config,testRoute?`/checks?lang=${lang}`:url.searchParams.get('next')||'/');
        return redirect(flow.location,[flow.flowCookie]);
      } catch {return response('Unavailable',503);}
    }
    if ((url.pathname === '/auth/callback' || url.pathname==='/auth/google-test/callback') && request.method === 'GET') {
      if (!sessions) return response('Unavailable',503,{'Set-Cookie':cookie(FLOW,'',0)});
      const providerConfig=testRoute?testGoogle:config, verifyLogin=testRoute?verifyTestStudent:verify;
      let result;
      try {result=await callback(request,providerConfig,{exchange,verify:verifyLogin});}
      catch {return response('Sign-in failed',403,{'Set-Cookie':cookie(FLOW,'',0)});}
      try {
        const prefix=SESSION+'=';
        if (!result.sessionCookie.startsWith(prefix)) throw new Error('Invalid login');
        const token=result.sessionCookie.slice(prefix.length).split(';',1)[0];
        const identity=await verifyLogin(token,providerConfig);
        const access=await sessions.issue(token,identity.exp);
        return redirect(result.returnTo,[cookie(SESSION,token,access.ttl),cookie(ACCESS,access.id,access.ttl),result.clearFlow]);
      } catch {return response('Unavailable',503,{'Set-Cookie':cookie(FLOW,'',0)});}
    }
    if (url.pathname === '/auth/logout' && request.method === 'POST') {
      const origin=request.headers.get('origin');
      if (origin !== config.origin && !((origin===null||origin==='null') && request.headers.get('sec-fetch-site')==='same-origin')) return response('Forbidden',403);
      try {
        const id=cookies(request).get(ACCESS);
        if (id) {if (!sessions) throw new Error('Session store unavailable'); await sessions.revoke(id);}
        return redirect('/signed-out',[cookie(SESSION,'',0),cookie(ACCESS,'',0),cookie(FLOW,'',0)]);
      } catch {
        const h=new Headers(security); for (const name of [SESSION,ACCESS,FLOW]) h.append('Set-Cookie',cookie(name,'',0));
        h.set('Content-Type','text/plain; charset=utf-8'); return new Response('Unavailable',{status:503,headers:h});
      }
    }
    const linkPost=url.pathname==='/link' && request.method==='POST' && selfLink;
    const enrollmentPost=url.pathname==='/enroll' && request.method==='POST' && enrollmentEnabled;
    const preparationPost=url.pathname==='/prepare' && request.method==='POST' && preparationEnabled;
    const checkerEnabled=env.PORTAL_CHECKER_ENABLED==='true' && typeof checker==='function';
    const checkerPost=url.pathname==='/checks' && request.method==='POST' && checkerEnabled;
    if (!['GET','HEAD'].includes(request.method) && !linkPost && !enrollmentPost && !preparationPost && !checkerPost) return response('Method not allowed',405);
    if (url.pathname === '/signed-out') return response(page(lang,t.title,`<p>${escape(t.signedout)}</p><p>${escape(t.shared)}</p><a href="/auth/login">${escape(t.login)}</a>`));
    const signInAgain=()=>{
      const copy={ja:['ログインの有効期限が切れました。再ログインして確認を続けてください。','ログインし直す'],ru:['Срок входа истёк. Войдите снова, чтобы продолжить проверку.','Войти снова'],uz:['Kirish muddati tugadi. Tekshiruvni davom ettirish uchun qayta kiring.','Qayta kirish']}[lang];
      let next='/';try {next=loginTarget(url.pathname+url.search,config);} catch {}
      return response(page(lang,t.title,`<p role="alert">${copy[0]}</p><a href="/auth/login?next=${encodeURIComponent(next)}">${copy[1]}</a>`),403);
    };
    let identity, jar, token;
    try {
      jar=cookies(request); token=jar.get(SESSION);
      try {identity=await verify(token,config);}
      catch (error) {
        if (!testGoogle) throw error;
        identity=await verifyTestStudent(token,testGoogle);
      }
    }
    catch {return url.pathname==='/' ? redirect('/auth/login') : signInAgain();}
    if (!sessions) return response('Unavailable',503);
    try {if (!await sessions.check(jar.get(ACCESS),token)) return url.pathname==='/' ? redirect('/auth/login') : signInAgain();}
    catch {return response('Unavailable',503);}
    const schoolIdentity=typeof identity?.sub==='string' && typeof identity?.email==='string' && identity.email_verified===true && identity.hd==='jdu.uz';
    const testIdentity=Boolean(testGoogle && identity.testLab===testGoogle.labId);
    const registration=(schoolIdentity || testIdentity) && (selfLink ? '/link' : enrollmentEnabled ? '/enroll' : null);
    if (testIdentity && ['/checks','/grades','/status'].includes(url.pathname)) {
      try {
        const registered=await getGrade(identity.sub);
        if (registered?.status==='unauthorized') return redirect(`/link?lang=${lang}`);
        if (registered?.status!=='ok') return response('Unavailable',503);
        if (registered.grade?.lab_id!==testGoogle.labId) return response('Forbidden',403);
      } catch {return response('Unavailable',503);}
    }
    if (url.pathname==='/teacher' || url.pathname==='/teacher/student') {
      const tt=teacherText[lang];
      const fail=(message,status)=>response(page(lang,tt.title,`<p role="alert">${escape(message)}</p><a href="/?lang=${lang}">${escape(tt.home)}</a>`),status);
      if(!schoolIdentity || typeof getTeacher!=='function')return fail(tt.denied,403);
      const detail=url.pathname==='/teacher/student',context=url.searchParams.get('context')||'course',after=url.searchParams.get('after')||'';
      const task=detail?url.searchParams.get('task_id'):null;
      const fields=detail?['lang','lab_id','task_id']:['lang','context','after'];
      if([...url.searchParams.keys()].some(k=>!fields.includes(k)) || [...url.searchParams.keys()].some(k=>url.searchParams.getAll(k).length!==1)
          || (!detail && (!['course','verification'].includes(context) || (after!=='' && !/^[a-z0-9][a-z0-9-]{2,31}$/.test(after))))
          || (task!==null && !Object.hasOwn(MISSION_MAXIMA,task))
          || (detail && !/^[a-z0-9][a-z0-9-]{2,31}$/.test(url.searchParams.get('lab_id')||'')))return fail(tt.denied,403);
      try {
        const event={subject:identity.sub,email:identity.email,operation:detail?'teacher_detail':'teacher_list',...(detail?{lab_id:url.searchParams.get('lab_id'),...(task?{task_id:task}:{})}:{context,after})};
        const result=await getTeacher(event);
        if(result?.status==='unauthorized')return fail(tt.denied,403);
        if(result?.status!=='ok')throw Error('Unavailable');
        const value=checkedTeacher(result.teacher,{detail,context,after});
        if(detail) {
          const row=value.student;
          if(row.lab_id!==event.lab_id)throw Error('Wrong student');
          if(row.status!=='ok')return fail(tt.error,503);
          if(row.grade?.lab_id!==row.lab_id)throw Error('Wrong grade');
          const grade=checkedGrade(row.grade);
          const summary=task ? taskDetailHtml(lang,task,grade,(grade.raw_maximum===59?LEGACY_MAXIMA:MISSION_MAXIMA)[task]) : gradeHtml(lang,grade);
          return response(page(lang,tt.title,`<p class="detail-back"><a href="/teacher?lang=${lang}&amp;context=${row.context}">${escape(tt.back)}</a></p><p>${escape(row.lab_id)}</p>`
            +summary,{teacher:true,params:{lab_id:row.lab_id,...(task?{task_id:task}:{})}}));
        }
        for(const row of value.students)if(row.status==='ok' && row.grade?.lab_id!==row.lab_id)throw Error('Wrong grade');
        return response(page(lang,tt.title,teacherListHtml(lang,value,{validateGrade:checkedGrade,maxima:MISSION_MAXIMA}),{teacher:true,params:{context,after}}),200,{'Referrer-Policy':'same-origin'});
      } catch {return fail(tt.error,503);}
    }
    if (url.pathname==='/checks') {
      if (!checkerEnabled) return response('Not found',404);
      const ct=checkWords[lang],extras={'Referrer-Policy':'same-origin','Content-Security-Policy':security['Content-Security-Policy']+"; script-src 'self'"};
      let selected;
      const detailTask=!checkerPost && !url.searchParams.has('job_id') ? url.searchParams.get('task_id') : null;
      const fail=(message,status=503)=>response(page(lang,ct.title,`<p role="alert">${escape(message)}</p>${validOperation(selected)?`<p><a href="/checks?lang=${lang}&amp;task_id=${selected.task_id}&amp;job_id=${selected.job_id}${selected.check_mode?`&amp;check_mode=${selected.check_mode}`:''}">${escape(ct.refresh)}</a></p>`:''}<a href="/checks?lang=${lang}">${escape(ct.back)}</a>`),status,extras);
      try {
        let result;
        if (detailTask!==null && (!checkTasks.includes(detailTask) || url.searchParams.getAll('task_id').length!==1
            || [...url.searchParams.keys()].some(key=>!['lang','task_id'].includes(key)))) return fail(ct.denied,403);
        if (checkerPost) {
          if (request.headers.get('origin')!==config.origin || request.headers.get('content-type')?.split(';')[0]!=='application/x-www-form-urlencoded') return fail(ct.denied,403);
          const body=await request.text(); if(Buffer.byteLength(body)>4096)return fail(ct.denied,403);
          const fields=new URLSearchParams(body);
          const allowed=['csrf','job_id','operation','task_id',...(fields.has('check_mode')?['check_mode']:[]),...(fields.get('operation')==='functional_start'?['password']:[])];
          if ([...fields.keys()].sort().join(',')!==allowed.sort().join(',')) return fail(ct.denied,403);
          selected=Object.fromEntries(['operation','task_id','job_id'].map(k=>[k,fields.get(k)]));
          if(fields.has('check_mode'))selected.check_mode=fields.get('check_mode');
          if (!validOperation(selected) || ['result','functional_context'].includes(selected.operation) || !verifyCheckToken(config,jar.get(ACCESS),token,selected,fields.get('csrf'))) return fail(ct.denied,403);
          let sealed;
          if(selected.operation==='functional_start') {
            const context=await checker({subject:identity.sub,...selected,operation:'functional_context'});
            if(context?.status!=='ok' || context.job?.job_id!==selected.job_id || context.job?.task_id!==selected.task_id)throw Error('Own password recipient unavailable');
            sealed=sealApplicationPassword(fields.get('password'),context.functional_recipient,selected.job_id);
            fields.delete('password');
          }
          result=await checker({subject:identity.sub,...selected,...(sealed?{sealed_password:sealed}:{})});
          if(result?.status==='ok') return redirect(`/checks?lang=${lang}&task_id=${selected.task_id}&job_id=${selected.job_id}${selected.check_mode?`&check_mode=${selected.check_mode}`:''}`);
          if(result?.status!=='ok') return fail(result?.status==='busy'?ct.busy:result?.status==='unauthorized'?ct.denied:ct.unavailable,result?.status==='unauthorized'?403:503);
        } else if (url.searchParams.has('job_id')) {
          selected={operation:'result',task_id:url.searchParams.get('task_id'),job_id:url.searchParams.get('job_id')};
          if(url.searchParams.has('check_mode'))selected.check_mode=url.searchParams.get('check_mode');
          if(!validOperation(selected))return fail(ct.denied,403);
          result=await checker({subject:identity.sub,...selected});
        }
        let grade, warning='', unbound=false;
        if (typeof getGrade==='function') {
          try {
            const saved=await getGrade(identity.sub,detailTask||undefined);
            if (saved?.status==='ok') grade=checkedGrade(saved.grade);
            else if (saved?.status==='unauthorized') {
              if (registration) return redirect(`${registration}?lang=${lang}`);
              unbound=true; warning=t.unbound;
            }
            else warning=t.unavailable;
          } catch { warning=t.unavailable; }
        }
        const session=jar.get(ACCESS);
        const maxima=grade?.raw_maximum===59?LEGACY_MAXIMA:MISSION_MAXIMA;
        const sumLabel={ja:'合計点',ru:'Сумма баллов',uz:'Jami ball'}[lang];
        const total=grade ? `<section class="score-overview" aria-labelledby="score-total-title">
          <h2 id="score-total-title">${sumLabel}</h2>
          <p><strong>${Object.keys(grade.selected).length?grade.raw_earned:'—'}</strong> <span>/ ${grade.raw_maximum}</span></p>
        </section>` : '';
        const bar=`<div class="page-toolbar"><form action="/auth/logout" method="post"><button type="submit">${escape(t.logout)}</button></form></div>`;
        const report=selected ? `<section aria-label="${escape(ct.done)}">${checkHtml(lang,{config,session,token,selected,result})}</section>` : '';
        const notice=warning?`<p role="status">${escape(warning)}</p>`:'';
        if (detailTask) {
          const actions=unbound?'':taskActions(lang,detailTask,{config,session,token});
          const back=`<p class="detail-back"><a href="/checks?lang=${lang}">${escape(ct.back)}</a></p>`;
          return response(page(lang,ct.title,back+notice+taskDetailHtml(lang,detailTask,grade,maxima[detailTask],actions),{task:detailTask}),200,extras);
        }
        const tasks=checkHtml(lang,{config,session,token,grade,maxima,blocked:unbound});
        return response(page(lang,ct.title,total+bar+notice+report+tasks,selected),result?.status==='unauthorized'?403:result && result.status!=='ok'?503:200,extras);
      } catch {return fail(ct.unavailable);}
    }
    if (url.pathname==='/prepare') {
      if (!preparationEnabled) return response('Not found',404);
      const pt=preparationText[lang];
      const fail=(message,status=503)=>response(page(lang,pt.title,`<p role="alert">${escape(message)}</p><a href="/prepare?lang=${lang}">${escape(pt.refresh)}</a>`),status);
      try {
        if (!schoolIdentity || [...url.searchParams.keys()].some(k=>k!=='lang') || url.searchParams.getAll('lang').length>1) return fail(pt.denied,403);
        const session=jar.get(ACCESS);
        const claims={subject:identity.sub,email:identity.email,session_id:session,token_hash:tokenHash(token)};
        let fields,operation,requestId=operationId();
        if (preparationPost) {
          if (request.headers.get('origin')!==config.origin || request.headers.get('content-type')?.split(';')[0]!=='application/x-www-form-urlencoded') return fail(pt.denied,403);
          const body=await request.text();
          if (Buffer.byteLength(body)>4096) return fail(pt.denied,403);
          fields=new URLSearchParams(body);operation=fields.get('operation');
          const expected=['confirmed','csrf','deployment_id','operation','request_id',...(operation==='create'?['confirmation','password','plan_digest']:[])].sort().join(',');
          if (!['begin','plan','create','advance','register'].includes(operation) || [...fields.keys()].sort().join(',')!==expected || fields.get('confirmed')!=='yes') return fail(pt.denied,403);
          requestId=fields.get('request_id');
          const context={operation,requestId,deploymentId:fields.get('deployment_id'),planDigest:operation==='create'?fields.get('plan_digest'):''};
          if (!checkPreparationToken(config,session,token,context,fields.get('csrf'))) return fail(pt.denied,403);
          if (operation==='create' && (fields.get('password')!==fields.get('confirmation') || fields.get('password').length<12 || fields.get('password').length>128 || /[\r\n\u0000]/.test(fields.get('password')))) return fail(pt.passwordInvalid,400);
        }
        const observed=await enroll({operation:'prepare_status',...claims});
        if (observed?.status==='unauthorized') return fail(pt.denied,403);
        if (observed?.status!=='ok') return fail(pt.unavailable);
        const value=checkedPreparation(observed.preparation);
        if (preparationPost) {
          if (value.deployment_id!==fields.get('deployment_id') || !value.can_continue) return fail(pt.denied,403);
          if (operation==='advance' && value.initial?.can_advance!==true) return fail(pt.denied,403);
          if (operation==='register') {
            if(value.registration_complete===true)return redirect(`/prepare?lang=${lang}`);
            if(!['REGISTRATION_PENDING','TEACHING_ASSETS_PENDING'].includes(value.initial?.stage))return fail(pt.denied,403);
            const context=await enroll({operation:'prepare_registration_context',...claims});
            if(context?.status==='unauthorized')return fail(pt.denied,403);
            if(context?.status!=='ok' || typeof context.preparation?.issued!=='boolean')return fail(pt.unavailable);
            const recipient=context.preparation.recipient;
            if(!context.preparation.issued && (!recipient || recipient.account!==value.account || recipient.lab_id!==value.lab_id || recipient.deployment_id!==value.deployment_id))return fail(pt.denied,403);
            const delivery=context.preparation.issued?null:createInitialDelivery(recipient);
            const registered=await enroll({operation:'prepare_register',...claims,delivery});
            if(registered?.status==='unauthorized')return fail(pt.denied,403);
            if(registered?.status!=='ok')return fail(pt.unavailable);
            return redirect(`/prepare?lang=${lang}`);
          }
          const event={operation:`prepare_${operation}`,...claims};
          if (operation==='begin')event.request_id=requestId;
          if (operation==='create')Object.assign(event,{plan_digest:fields.get('plan_digest'),password:fields.get('password'),confirmation:fields.get('confirmation')});
          const result=await enroll(event);
          if (result?.status==='unauthorized')return fail(pt.denied,403);
          if (result?.status!=='ok')return fail(pt.unavailable);
          // Redirect clears a submitted password from the reload path. GET
          // observes the durable original request and never resumes execution.
          return redirect(`/prepare?lang=${lang}`);
        }
        if (value.stage==='APPROVED' && value.can_continue)preparationTemplate(env);
        const bootstrapLink=value.pair_id?createPreparationLink(env,value):undefined;
        return response(page(lang,pt.title,preparationHtml(lang,value,{config,session,token,requestId,bootstrapLink})),200,{'Referrer-Policy':'same-origin'});
      } catch {return fail(pt.unavailable);}
    }

    if (url.pathname==='/link') {
      if (!selfLink || (!schoolIdentity && !testIdentity)) return response('Forbidden',403);
      const labels={
        ja:{command:'CloudShellで実行するコマンド',code:'連携コード',submit:'連携する',error:'連携エラー',
          format:'CloudShellに表示された jdu-link1. から始まるコードを、1行まるごと貼り付けてください。',
          lab:'このコードは、今回のテストに設定されたAWS演習環境のものではありません。CloudShellで対象のAWSアカウントを開いてから、上のコマンドを実行してください。',
          expired:'コードの有効期限（10分）が過ぎました。上のコマンドを実行して、新しいコードを貼り付けてください。',
          denied:'この画面のコードとして確認できませんでした。上のコマンドを対象の学生側CloudShellで実行し、出力されたコードを貼り付けてください。',
          unavailable:'連携サービスに接続できませんでした。少し待ってから上のコマンドで新しいコードを発行してください。'},
        ru:{command:'Команда CloudShell',code:'Код привязки',submit:'Привязать',error:'Ошибка привязки',
          format:'Вставьте целиком строку из CloudShell, которая начинается с jdu-link1.',
          lab:'Код выдан для другой среды AWS. Откройте нужный аккаунт AWS и выполните команду выше.',
          expired:'Срок действия кода (10 минут) истёк. Выполните команду выше и вставьте новый код.',
          denied:'Не удалось подтвердить код для этой страницы. Выполните команду выше в CloudShell нужного студента и вставьте полученный код.',
          unavailable:'Сервис привязки недоступен. Подождите немного и получите новый код командой выше.'},
        uz:{command:'CloudShell buyrug‘i',code:'Bog‘lash kodi',submit:'Bog‘lash',error:'Bog‘lash xatosi',
          format:'CloudShell natijasidagi jdu-link1. bilan boshlanadigan qatorni to‘liq kiriting.',
          lab:'Kod boshqa AWS muhiti uchun berilgan. Tegishli AWS hisobini oching va yuqoridagi buyruqni bajaring.',
          expired:'Kodning 10 daqiqalik muddati tugagan. Yuqoridagi buyruqni bajarib, yangi kodni kiriting.',
          denied:'Kod ushbu sahifa uchun tasdiqlanmadi. Yuqoridagi buyruqni tegishli talaba CloudShell muhitida bajarib, olingan kodni kiriting.',
          unavailable:'Bog‘lash xizmatiga ulanib bo‘lmadi. Biroz kutib, yuqoridagi buyruq orqali yangi kod oling.'},
      }[lang];
      const sessionId=jar.get(ACCESS);
      let failure='';
      if (linkPost) {
        if (request.headers.get('origin')!==config.origin || request.headers.get('content-type')?.split(';')[0]!=='application/x-www-form-urlencoded') return response('Forbidden',403);
        try {
          const raw=await request.text();
          if (Buffer.byteLength(raw)>1024) return response('Payload too large',413);
          const fields=new URLSearchParams(raw), requestId=fields.get('request_id'), code=fields.get('code')?.trim();
          if ([...fields.keys()].sort().join(',')!=='code,csrf,request_id'
              || !checkForm(config,sessionId,token,requestId,fields.get('csrf'))) return response('Forbidden',403);
          const supplied=/^jdu-link1\.(lab-[a-f0-9]{20})\.[0-9]{12}\.([0-9]{10})\.[a-f0-9]{64}$/.exec(code||'');
          if (!supplied) failure='format';
          else if (testIdentity && supplied[1]!==identity.testLab) failure='lab';
          else if (Math.floor(Date.now()/1000)-Number(supplied[2])>600) failure='expired';
          else {
            const result=await enroll({operation:testIdentity?'claim_test_student':'claim',subject:identity.sub,
              email:identity.email,session_id:sessionId,
              token_hash:tokenHash(token),request_id:requestId,code});
            if (result?.status==='ok' && result.enrollment?.registered===true) return redirect(`/checks?lang=${lang}`);
            failure=result?.status==='unauthorized'?'denied':'unavailable';
          }
        } catch {failure='unavailable';}
      }
      const requestId=operationId(), csrf=formToken(config,sessionId,token,requestId);
      const command=`setup=$(mktemp)
curl -q -fsS https://raw.githubusercontent.com/ShinyaHaga0910/JDU-Web-Infrastructure/refs/heads/main/development/setup-classroom.sh -o "$setup" &&
  bash "$setup" portal-link-code --lang ${lang} --challenge ${requestId}${testIdentity?` --lab-id ${identity.testLab}`:''}`;
      const r=firstRegistration[lang];
      const errorBox=failure?`<div id="link-error" class="registration-error" role="alert"><strong>${escape(labels.error)}</strong>
        <p>${escape(labels[failure])}</p></div>`:'';
      const invalid=failure && failure!=='unavailable'?' aria-invalid="true" aria-describedby="link-error"':'';
      const body=`<ol class="registration-steps">
        <li><section><h2>${escape(r.run)}</h2><label for="link-number">${escape(labels.command)}</label>
        <textarea id="link-number" rows="5" readonly>${escape(command)}</textarea></section></li>
        <li><section><h2>${escape(r.paste)}</h2>${errorBox}
        <form action="/link?lang=${lang}" method="post"><input type="hidden" name="request_id" value="${requestId}">
        <input type="hidden" name="csrf" value="${csrf}"><label for="link-code">${escape(labels.code)}</label>
        <input id="link-code" type="password" name="code" required maxlength="180" autocomplete="off"${invalid}>
        <button class="primary-action" type="submit">${escape(labels.submit)}</button></form></section></li></ol>
        <form action="/auth/logout" method="post"><button type="submit">${escape(t.logout)}</button></form>`;
      return response(page(lang,r.title,body),failure==='unavailable'?503:failure?403:200,{'Referrer-Policy':'same-origin'});
    }
    if (url.pathname==='/enroll') {
      if (!enrollmentEnabled) return response('Not found',404);
      const et=enrollmentText(lang);
      const failure=(message,status)=>response(page(lang,et.title,`<p role="alert">${escape(message)}</p><a href="/?lang=${lang}">${escape(et.back)}</a>`),status);
      try {
        if (typeof identity?.sub!=='string' || typeof identity?.email!=='string' || identity.email_verified!==true || identity.hd!=='jdu.uz') return failure(et.denied,403);
        const sessionId=jar.get(ACCESS);
        const event={operation:enrollmentPost?'begin':'status',subject:identity.sub,email:identity.email,session_id:sessionId,token_hash:tokenHash(token)};
        let requestId;
        if (enrollmentPost) {
          if (request.headers.get('origin')!==config.origin || request.headers.get('content-type')?.split(';')[0]!=='application/x-www-form-urlencoded') return failure(et.denied,403);
          const body=await request.text();
          if (Buffer.byteLength(body)>4096) return failure(et.denied,403);
          const fields=new URLSearchParams(body);
          if ([...fields.keys()].sort().join(',')!=='confirmed,csrf,request_id' || fields.get('confirmed')!=='yes') return failure(et.denied,403);
          requestId=fields.get('request_id');
          if (!checkForm(config,sessionId,token,requestId,fields.get('csrf'))) return failure(et.denied,403);
          event.request_id=requestId;
        }
        const result=await enroll(event);
        if (result?.status==='unauthorized') return failure(et.denied,403);
        if (result?.status!=='ok') throw Error('Unavailable');
        const pending=!result.enrollment?.registered && Object.hasOwn(result.enrollment||{},'pair_id');
        const value=checkedEnrollment(result.enrollment,{pending:enrollmentPost||pending});
        // An unregistered student never receives a form that ends at a dead
        // waiting screen. GET resumes an active attempt without creating one.
        if (!value.registered) bootstrapTemplate(env);
        const bootstrapLink=pending?createBootstrapLink(env,value):undefined;
        requestId ||= operationId();
        const csrf=formToken(config,sessionId,token,requestId);
        // Native POST under no-referrer sends Origin: null (Fetch standard).
        // Keep exact Origin/CSRF checks; reveal referrers only to this same origin.
        // OAuth pages and all cross-origin navigation retain no referrer disclosure.
        return response(page(lang,et.title,enrollmentHtml(lang,value,{requestId,csrf,pending,bootstrapLink})),200,{'Referrer-Policy':'same-origin'});
      } catch {return failure(et.unavailable,503);}
    }
    if (url.pathname === '/') {
      let teacherLink='';
      if(schoolIdentity && typeof getTeacher==='function') {
        try {const result=await getTeacher({operation:'teacher_access',subject:identity.sub,email:identity.email});if(result?.status==='ok' && /^[0-9]{1,12}$/.test(result.teacher?.class_id||''))teacherLink=`<p><a href="/teacher?lang=${lang}">${escape(teacherText[lang].title)}</a></p>`;} catch {}
      }
      if (checkerEnabled && !preparationEnabled) return redirect(teacherLink?`/teacher?lang=${lang}`:`/checks?lang=${lang}`);
      return response(page(lang,t.title,`<section>${preparationEnabled?`<p><a href="/prepare?lang=${lang}">${escape(preparationText[lang].title)}</a></p>`:''}${enrollmentEnabled?`<p><a href="/enroll?lang=${lang}">${escape(enrollmentText(lang).title)}</a></p>`:''}<p><a href="/grades?lang=${lang}">${escape(t.grades)}</a></p><p><a href="/status?lang=${lang}">${escape(t.status)}</a></p>${checkerEnabled?`<p><a href="/checks?lang=${lang}">${escape(checkWords[lang].title)}</a></p>`:''}${teacherLink}</section>${checkerEnabled?'':`<p>${escape(t.notice)}</p>`}<p>${escape(t.shared)}</p><form action="/auth/logout" method="post"><button type="submit">${escape(t.logout)}</button></form>`));
    }
    if (url.pathname !== '/grades' && url.pathname !== '/status') return response('Not found',404);
    if (url.pathname === '/status') {
      try {
        if (typeof identity?.sub !== 'string' || typeof getStatus !== 'function') throw new Error('Unavailable');
        const result=await getStatus(identity.sub);
        if (result?.status === 'unauthorized') return registration ? redirect(`${registration}?lang=${lang}`) : response(page(lang,t.status,`<p>${escape(t.unbound)}</p><a href="/?lang=${lang}">${escape(t.back)}</a>`),403);
        if (result?.status !== 'ok') throw new Error('Unavailable');
        return response(page(lang,t.status,statusHtml(lang,result.observation)+`<a href="/?lang=${lang}">${escape(t.back)}</a>`));
      } catch {return response(page(lang,t.status,`<p>${escape(t.statusUnavailable)}</p><a href="/?lang=${lang}">${escape(t.back)}</a>`),503);}
    }
    try {
      if (typeof identity?.sub !== 'string' || typeof getGrade !== 'function') throw new Error('Unavailable');
      const result=await getGrade(identity.sub);
      if (result?.status === 'unauthorized') return registration ? redirect(`${registration}?lang=${lang}`) : response(page(lang,t.grades,`<p>${escape(t.unbound)}</p><a href="/?lang=${lang}">${escape(t.back)}</a>`),403);
      if (result?.status !== 'ok') throw new Error('Unavailable');
      return response(page(lang,t.grades,gradeHtml(lang,result.grade)+`<a href="/?lang=${lang}">${escape(t.back)}</a>`));
    } catch {return response(page(lang,t.grades,`<p>${escape(t.unavailable)}</p><a href="/?lang=${lang}">${escape(t.back)}</a>`),503);}
  };
}
