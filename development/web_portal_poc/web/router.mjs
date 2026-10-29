import { configFrom, cookies, cookie, login, callback, verifyGoogle, SESSION, FLOW } from './auth.mjs';
import { ACCESS } from './sessions.mjs';
import { formToken, checkForm, operationId, tokenHash } from './enrollment-client.mjs';
import { enrollmentHtml, enrollmentText, checkedEnrollment } from './enrollment-page.mjs';
import { bootstrapTemplate, createBootstrapLink } from './bootstrap-link.mjs';
import { words as checkWords, validOperation, verifyCheckToken, checkHtml, progressScript } from './checks.mjs';

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
export const MISSION_MAXIMA=Object.freeze({M1:8,M2:13,M3:3,M4:9,M5:13,M6:16});
const stateText={
  ja:{running:'稼働中',stopped:'停止中',pending:'起動中',stopping:'停止処理中','shutting-down':'終了処理中',terminated:'終了済み',unknown:'確認できない',Online:'接続可',ConnectionLost:'接続なし',Inactive:'非アクティブ'},
  ru:{running:'Работает',stopped:'Остановлен',pending:'Запускается',stopping:'Останавливается','shutting-down':'Завершается',terminated:'Завершён',unknown:'Неизвестно',Online:'Доступно',ConnectionLost:'Нет связи',Inactive:'Неактивно'},
  uz:{running:'Ishlayapti',stopped:'To‘xtagan',pending:'Ishga tushmoqda',stopping:'To‘xtamoqda','shutting-down':'Tugatilmoqda',terminated:'Tugatilgan',unknown:'Noma’lum',Online:'Ulangan',ConnectionLost:'Aloqa yo‘q',Inactive:'Faol emas'},
};
const language = url => Object.hasOwn(text, url.searchParams.get('lang')) ? url.searchParams.get('lang') : 'ja';
const response = (body, status=200, extras={}) => new Response(body, {status, headers:{...security, 'Content-Type':'text/html; charset=utf-8', ...extras}});
const redirect = (location, values=[]) => { const h=new Headers(security); h.set('Location',location); for(const v of values) h.append('Set-Cookie',v); return new Response(null,{status:303,headers:h}); };

function page(lang, title, content, selection) {
  const tail=selection?`&amp;task_id=${selection.task_id}&amp;job_id=${selection.job_id}`:'';
  const nav = ['ja','ru','uz'].map(k => `<a href="?lang=${k}${tail}"${k===lang?' aria-current="page"':''}>${k.toUpperCase()}</a>`).join(' ');
  return `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)}</title><style>body{font:1rem/1.6 system-ui,sans-serif;margin:0;background:#f5f7fa;color:#182435}main{max-width:64rem;margin:auto;padding:1.5rem}nav{display:flex;gap:1rem}a,button{color:#064ca4}button{font:inherit;background:white;border:1px solid #64748b;border-radius:.35rem;padding:.65rem 1rem;cursor:pointer}a:focus-visible,button:focus-visible{outline:3px solid #d34800;outline-offset:3px}section{background:white;border:1px solid #d6dee8;border-radius:.5rem;padding:1rem;margin-block:1rem}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:44rem}th,td{padding:.6rem;text-align:left;border-bottom:1px solid #d6dee8}.num{font-size:1.6rem;font-weight:700}footer{margin-top:2rem}fieldset{border:1px solid #a9b6c7;border-radius:.35rem;padding:1rem;margin-block:1rem}.confirm{display:flex;align-items:flex-start;gap:.5rem;min-height:48px;padding-block:.5rem}input[type=checkbox]{width:1.25rem;height:1.25rem;margin:.2rem 0;flex-shrink:0}a.action{display:inline-flex;align-items:center;min-height:48px;padding:0 .75rem;border:1px solid #64748b;border-radius:.35rem}a.action:focus-visible,input:focus-visible{outline:3px solid #d34800;outline-offset:3px}.check-tasks{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr));gap:1rem}.check-tasks section{margin:0}</style></head><body><main><nav aria-label="Languages">${nav}</nav><h1>${escape(title)}</h1>${content}</main></body></html>`;
}

function gradeHtml(lang, grade) {
  const t=text[lang];
  if (!grade || !Number.isInteger(grade.raw_earned) || grade.raw_maximum !== 62 || grade.raw_earned < 0 || grade.raw_earned > 62 || !Array.isArray(grade.current_unresolved) || !Array.isArray(grade.missing_or_unresolved) || !grade.selected || typeof grade.selected !== 'object') throw new Error('Invalid grade');
  if (Object.keys(grade.selected).some(id => !Object.hasOwn(MISSION_MAXIMA,id) || !Number.isInteger(grade.selected[id]?.raw_earned) || grade.selected[id].raw_earned < 0 || grade.selected[id].raw_earned > MISSION_MAXIMA[id]) || Object.values(grade.selected).reduce((sum,row)=>sum+row.raw_earned,0)!==grade.raw_earned) throw new Error('Invalid selected scores');
  const date = value => typeof value==='string' && value.length<=40 && Number.isFinite(Date.parse(value)) ? new Date(value).toISOString().slice(0,16).replace('T',' ')+' UTC' : t.noRecord;
  const rows = ['M1','M2','M3','M4','M5','M6'].map(id => {
    const saved=grade.selected[id];
    const score=saved && Number.isInteger(saved.raw_earned) ? String(saved.raw_earned) : t.noRecord;
    return `<tr><th scope="row">${id}</th><td>${escape(score)}</td><td>${escape(grade.current_unresolved.includes(id) ? t.unknown : grade.current?.[id] ? t.currentOk : t.noRecord)}</td><td>${escape(date(grade.current?.[id]?.checked_at))}</td><td>${escape(date(saved?.received_at))}</td></tr>`;
  }).join('');
  const total = Object.keys(grade.selected).length ? `${grade.raw_earned} / 62` : t.noRecord;
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

export function createApp({env=process.env, verify=verifyGoogle, exchange=fetch, getGrade, getStatus, sessions, getAcceptanceHealth, enroll, checker}={}) {
  return async request => {
    const url=new URL(request.url), lang=language(url), t=text[lang];
    if (url.pathname === '/healthz') return new Response('ok',{headers:{...security,'Content-Type':'text/plain; charset=utf-8'}});
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
    if (url.pathname==='/api/enrollment/complete') {
      // Server-to-server signed proof only. The nonce was minted by an active,
      // approved Google session; no self-declared Google identity is accepted.
      if (!enrollmentEnabled) return response('Not found',404);
      if (request.method!=='POST') return response('Method not allowed',405);
      if (url.search || request.headers.get('content-type')?.split(';')[0]!=='application/json') return response('Forbidden',403);
      try {
        const body=await request.text();
        if (Buffer.byteLength(body)>16384) return response('Payload too large',413);
        const value=JSON.parse(body);
        if (!value || Array.isArray(value) || Object.keys(value).sort().join(',')!=='pair_id,proof_url'
            || !/^[a-f0-9]{64}$/.test(value.pair_id||'') || typeof value.proof_url!=='string' || value.proof_url.length>8192) return response('Forbidden',403);
        const result=await enroll({operation:'complete',pair_id:value.pair_id,proof_url:value.proof_url});
        if (result?.status==='unauthorized') return response('Forbidden',403);
        if (result?.status!=='ok' || result.enrollment?.registered!==true
            || !/^[a-z0-9][a-z0-9-]{2,31}$/.test(result.enrollment?.lab_id||'')) return response('Unavailable',503);
        return new Response(JSON.stringify({registered:true}),{headers:{...security,'Content-Type':'application/json; charset=utf-8'}});
      } catch {return response('Unavailable',503);}
    }
    if (url.pathname === '/auth/login' && request.method === 'GET') {
      try {const flow=await login(config); return redirect(flow.location,[flow.flowCookie]);} catch {return response('Unavailable',503);}
    }
    if (url.pathname === '/auth/callback' && request.method === 'GET') {
      if (!sessions) return response('Unavailable',503,{'Set-Cookie':cookie(FLOW,'',0)});
      let result;
      try {result=await callback(request,config,{exchange,verify});}
      catch {return response('Sign-in failed',403,{'Set-Cookie':cookie(FLOW,'',0)});}
      try {
        const prefix=SESSION+'=';
        if (!result.sessionCookie.startsWith(prefix)) throw new Error('Invalid login');
        const token=result.sessionCookie.slice(prefix.length).split(';',1)[0];
        const identity=await verify(token,config);
        const access=await sessions.issue(token,identity.exp);
        return redirect('/',[cookie(SESSION,token,access.ttl),cookie(ACCESS,access.id,access.ttl),result.clearFlow]);
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
    const enrollmentPost=url.pathname==='/enroll' && request.method==='POST' && enrollmentEnabled;
    const checkerEnabled=env.PORTAL_CHECKER_ENABLED==='true' && typeof checker==='function';
    const checkerPost=url.pathname==='/checks' && request.method==='POST' && checkerEnabled;
    if (!['GET','HEAD'].includes(request.method) && !enrollmentPost && !checkerPost) return response('Method not allowed',405);
    if (url.pathname === '/signed-out') return response(page(lang,t.title,`<p>${escape(t.signedout)}</p><p>${escape(t.shared)}</p><a href="/auth/login">${escape(t.login)}</a>`));
    let identity, jar, token;
    try {jar=cookies(request); token=jar.get(SESSION); identity=await verify(token,config);}
    catch {return url.pathname==='/' ? redirect('/auth/login') : response('Forbidden',403);}
    if (!sessions) return response('Unavailable',503);
    try {if (!await sessions.check(jar.get(ACCESS),token)) return url.pathname==='/' ? redirect('/auth/login') : response('Forbidden',403);}
    catch {return response('Unavailable',503);}
    if (url.pathname==='/checks') {
      if (!checkerEnabled) return response('Not found',404);
      const ct=checkWords[lang],extras={'Referrer-Policy':'same-origin','Content-Security-Policy':security['Content-Security-Policy']+"; script-src 'self'"};
      let selected;
      const fail=(message,status=503)=>response(page(lang,ct.title,`<p role="alert">${escape(message)}</p>${validOperation(selected)?`<p><a href="/checks?lang=${lang}&amp;task_id=${selected.task_id}&amp;job_id=${selected.job_id}">${escape(ct.refresh)}</a></p>`:''}<a href="/checks?lang=${lang}">${escape(ct.back)}</a>`),status,extras);
      try {
        let result;
        if (checkerPost) {
          if (request.headers.get('origin')!==config.origin || request.headers.get('content-type')?.split(';')[0]!=='application/x-www-form-urlencoded') return fail(ct.denied,403);
          const body=await request.text(); if(Buffer.byteLength(body)>4096)return fail(ct.denied,403);
          const fields=new URLSearchParams(body);
          if ([...fields.keys()].sort().join(',')!=='csrf,job_id,operation,task_id') return fail(ct.denied,403);
          selected=Object.fromEntries(['operation','task_id','job_id'].map(k=>[k,fields.get(k)]));
          if (!validOperation(selected) || selected.operation==='result' || !verifyCheckToken(config,jar.get(ACCESS),token,selected,fields.get('csrf'))) return fail(ct.denied,403);
          result=await checker({subject:identity.sub,...selected});
          if(result?.status==='ok') return redirect(`/checks?lang=${lang}&task_id=${selected.task_id}&job_id=${selected.job_id}`);
          if(result?.status!=='ok') return fail(result?.status==='busy'?ct.busy:result?.status==='unauthorized'?ct.denied:ct.unavailable,result?.status==='unauthorized'?403:503);
        } else if (url.searchParams.has('task_id') || url.searchParams.has('job_id')) {
          selected={operation:'result',task_id:url.searchParams.get('task_id'),job_id:url.searchParams.get('job_id')};
          if(!validOperation(selected))return fail(ct.denied,403);
          result=await checker({subject:identity.sub,...selected});
        }
        return response(page(lang,ct.title,checkHtml(lang,{config,session:jar.get(ACCESS),token,selected,result}),selected),result?.status==='unauthorized'?403:result && result.status!=='ok'?503:200,extras);
      } catch {return fail(ct.unavailable);}
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
    if (url.pathname === '/') return response(page(lang,t.title,`<section>${enrollmentEnabled?`<p><a href="/enroll?lang=${lang}">${escape(enrollmentText(lang).title)}</a></p>`:''}<p><a href="/grades?lang=${lang}">${escape(t.grades)}</a></p><p><a href="/status?lang=${lang}">${escape(t.status)}</a></p>${checkerEnabled?`<p><a href="/checks?lang=${lang}">${escape(checkWords[lang].title)}</a></p>`:''}</section>${checkerEnabled?'':`<p>${escape(t.notice)}</p>`}<p>${escape(t.shared)}</p><form action="/auth/logout" method="post"><button type="submit">${escape(t.logout)}</button></form>`));
    if (url.pathname !== '/grades' && url.pathname !== '/status') return response('Not found',404);
    if (url.pathname === '/status') {
      try {
        if (typeof identity?.sub !== 'string' || typeof getStatus !== 'function') throw new Error('Unavailable');
        const result=await getStatus(identity.sub);
        if (result?.status === 'unauthorized') return response(page(lang,t.status,`<p>${escape(t.unbound)}</p><a href="/?lang=${lang}">${escape(t.back)}</a>`),403);
        if (result?.status !== 'ok') throw new Error('Unavailable');
        return response(page(lang,t.status,statusHtml(lang,result.observation)+`<a href="/?lang=${lang}">${escape(t.back)}</a>`));
      } catch {return response(page(lang,t.status,`<p>${escape(t.statusUnavailable)}</p><a href="/?lang=${lang}">${escape(t.back)}</a>`),503);}
    }
    try {
      if (typeof identity?.sub !== 'string' || typeof getGrade !== 'function') throw new Error('Unavailable');
      const result=await getGrade(identity.sub);
      if (result?.status === 'unauthorized') return response(page(lang,t.grades,`<p>${escape(t.unbound)}</p><a href="/?lang=${lang}">${escape(t.back)}</a>`),403);
      if (result?.status !== 'ok') throw new Error('Unavailable');
      return response(page(lang,t.grades,gradeHtml(lang,result.grade)+`<a href="/?lang=${lang}">${escape(t.back)}</a>`));
    } catch {return response(page(lang,t.grades,`<p>${escape(t.unavailable)}</p><a href="/?lang=${lang}">${escape(t.back)}</a>`),503);}
  };
}
