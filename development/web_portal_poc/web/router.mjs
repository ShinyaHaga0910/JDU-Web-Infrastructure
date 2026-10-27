import { configFrom, cookies, cookie, login, callback, verifyGoogle, SESSION, FLOW } from './auth.mjs';
import { ACCESS } from './sessions.mjs';

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
    notice:'環境の状態確認・構築と新しい採点の画面は準備中です。保存済み成績の閲覧ではサーバーを起動しません。',
    shared:'共有PCでは、使い終わったらこの画面とGoogleの両方からログアウトしてください。', signedout:'ログアウトしました。' },
  ru: { title:'Практика Web', grades:'Сохранённые результаты', intro:'Войдите с университетским аккаунтом Google.',
    login:'Войти через Google', logout:'Выйти', total:'Сохранённые баллы', current:'Последняя проверка', unknown:'Есть непроверенные пункты',
    noRecord:'Нет записи', currentOk:'Проверено', back:'На главную', unavailable:'Не удалось получить результат. Повторите попытку позже.',
    unbound:'Ваша учебная среда ещё не зарегистрирована. Обратитесь к преподавателю.', mission:'Задание', score:'Сохранено', home:'Главная', checked:'Время проверки', received:'Время сохранения',
    notice:'Просмотр состояния, создание среды и новая проверка готовятся. Просмотр результатов не запускает серверы.',
    shared:'На общем компьютере после работы выйдите здесь и из аккаунта Google.', signedout:'Вы вышли из системы.' },
  uz: { title:'Web amaliyoti', grades:'Saqlangan natijalar', intro:'Universitet Google hisobingiz bilan kiring.',
    login:'Google orqali kirish', logout:'Chiqish', total:'Saqlangan ball', current:'Oxirgi tekshiruv', unknown:'Tekshirib bo‘lmagan bandlar bor',
    noRecord:'Natija yo‘q', currentOk:'Tekshirilgan', back:'Bosh sahifaga', unavailable:'Natijani olib bo‘lmadi. Keyinroq qayta urinib ko‘ring.',
    unbound:'Sizning amaliy muhitingiz hali ro‘yxatdan o‘tmagan. O‘qituvchiga murojaat qiling.', mission:'Vazifa', score:'Saqlangan', home:'Bosh sahifa', checked:'Tekshirilgan vaqt', received:'Saqlangan vaqt',
    notice:'Holatni ko‘rish, muhit yaratish va yangi tekshiruv tayyorlanmoqda. Natijani ko‘rish serverlarni ishga tushirmaydi.',
    shared:'Umumiy kompyuterda ish tugagach, bu yerdan va Google hisobidan chiqing.', signedout:'Tizimdan chiqdingiz.' },
};
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const MISSION_MAXIMA=Object.freeze({M1:8,M2:13,M3:3,M4:9,M5:13,M6:16});
const language = url => Object.hasOwn(text, url.searchParams.get('lang')) ? url.searchParams.get('lang') : 'ja';
const response = (body, status=200, extras={}) => new Response(body, {status, headers:{...security, 'Content-Type':'text/html; charset=utf-8', ...extras}});
const redirect = (location, values=[]) => { const h=new Headers(security); h.set('Location',location); for(const v of values) h.append('Set-Cookie',v); return new Response(null,{status:303,headers:h}); };

function page(lang, title, content) {
  const nav = ['ja','ru','uz'].map(k => `<a href="?lang=${k}"${k===lang?' aria-current="page"':''}>${k.toUpperCase()}</a>`).join(' ');
  return `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)}</title><style>body{font:1rem/1.6 system-ui,sans-serif;margin:0;background:#f5f7fa;color:#182435}main{max-width:64rem;margin:auto;padding:1.5rem}nav{display:flex;gap:1rem}a,button{color:#064ca4}button{font:inherit;background:white;border:1px solid #64748b;border-radius:.35rem;padding:.65rem 1rem;cursor:pointer}a:focus-visible,button:focus-visible{outline:3px solid #d34800;outline-offset:3px}section{background:white;border:1px solid #d6dee8;border-radius:.5rem;padding:1rem;margin-block:1rem}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:44rem}th,td{padding:.6rem;text-align:left;border-bottom:1px solid #d6dee8}.num{font-size:1.6rem;font-weight:700}footer{margin-top:2rem}</style></head><body><main><nav aria-label="Languages">${nav}</nav><h1>${escape(title)}</h1>${content}</main></body></html>`;
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

export function createApp({env=process.env, verify=verifyGoogle, exchange=fetch, getGrade, sessions}={}) {
  return async request => {
    const url=new URL(request.url), lang=language(url), t=text[lang];
    if (url.pathname === '/healthz') return new Response('ok',{headers:{...security,'Content-Type':'text/plain; charset=utf-8'}});
    let config;
    try { config=configFrom(env); } catch { return response('Unavailable',503); }
    if (url.origin !== config.origin) return response('Forbidden',403);
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
    if (!['GET','HEAD'].includes(request.method)) return response('Method not allowed',405);
    if (url.pathname === '/signed-out') return response(page(lang,t.title,`<p>${escape(t.signedout)}</p><p>${escape(t.shared)}</p><a href="/auth/login">${escape(t.login)}</a>`));
    let identity, jar, token;
    try {jar=cookies(request); token=jar.get(SESSION); identity=await verify(token,config);}
    catch {return url.pathname==='/' ? redirect('/auth/login') : response('Forbidden',403);}
    if (!sessions) return response('Unavailable',503);
    try {if (!await sessions.check(jar.get(ACCESS),token)) return url.pathname==='/' ? redirect('/auth/login') : response('Forbidden',403);}
    catch {return response('Unavailable',503);}
    if (url.pathname === '/') return response(page(lang,t.title,`<section><a href="/grades?lang=${lang}">${escape(t.grades)}</a></section><p>${escape(t.notice)}</p><p>${escape(t.shared)}</p><form action="/auth/logout" method="post"><button type="submit">${escape(t.logout)}</button></form>`));
    if (url.pathname !== '/grades') return response('Not found',404);
    try {
      if (typeof identity?.sub !== 'string' || typeof getGrade !== 'function') throw new Error('Unavailable');
      const result=await getGrade(identity.sub);
      if (result?.status === 'unauthorized') return response(page(lang,t.grades,`<p>${escape(t.unbound)}</p><a href="/?lang=${lang}">${escape(t.back)}</a>`),403);
      if (result?.status !== 'ok') throw new Error('Unavailable');
      return response(page(lang,t.grades,gradeHtml(lang,result.grade)+`<a href="/?lang=${lang}">${escape(t.back)}</a>`));
    } catch {return response(page(lang,t.grades,`<p>${escape(t.unavailable)}</p><a href="/?lang=${lang}">${escape(t.back)}</a>`),503);}
  };
}
