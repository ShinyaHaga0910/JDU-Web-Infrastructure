import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createApp, MISSION_MAXIMA } from './router.mjs';
import { createGradeClient, createStatusClient } from './grade-client.mjs';

const env={PORTAL_MODE:'enabled', PUBLIC_ORIGIN:'https://portal.example', GOOGLE_CLIENT_ID:'1234-example.apps.googleusercontent.com', GOOGLE_CLIENT_SECRET:'example-test-secret-only'};
const subject='1234567890';
const verified=async token => {if(token!=='valid')throw Error('no session');return {sub:subject};};
const sessions={check:async(id,token)=>id==='session' && token==='valid',revoke:async()=>{}};
const credentials='__Host-jdu-session=valid; __Host-jdu-access=session';
const sample={raw_earned:34,raw_maximum:59,current_unresolved:['M5'],missing_or_unresolved:['M6'],
              current:{M5:{evaluable:false,checked_at:'2026-10-27T09:00:00Z'}},selected:{M1:{raw_earned:8},M2:{raw_earned:13},M5:{raw_earned:13,received_at:'2026-10-27T09:05:00Z'}}};
const req=(path,options={})=>new Request(`https://portal.example${path}`,options);

test('score bounds match the course points and signed mission weights',async()=>{
  const registry=JSON.parse(await readFile(new URL('../../01_roles/cyber_security/tools/web_lab_assessment/assessment-registry.json',import.meta.url),'utf8'));
  const curriculum=JSON.parse(await readFile(new URL('../../../course/curriculum.json',import.meta.url),'utf8'));
  const maxima=Object.fromEntries(registry.tasks.filter(t=>t.category==='automated_mission' && t.id!=='M3').map(t=>[t.id,t.raw_points_max]));
  assert.deepEqual(MISSION_MAXIMA,{...curriculum.intro_points,...maxima});
  assert.equal(Object.values(MISSION_MAXIMA).reduce((sum,value)=>sum+value,0),curriculum.raw_maximum);
});

test('saved connection grades appear in the current course total',async()=>{
  const grade={...sample,raw_maximum:61,raw_earned:36,
    selected:{...sample.selected,P0:{raw_earned:1},M0:{raw_earned:1}}};
  const app=createApp({env,verify:verified,sessions,getGrade:async()=>({status:'ok',grade})});
  const body=await (await app(req('/grades',{headers:{cookie:credentials}}))).text();
  assert.match(body,/36 \/ 61/);
  assert.match(body,/>P0<\/th><td>1 \/ 1<\/td>/);
  assert.match(body,/>M0<\/th><td>1 \/ 1<\/td>/);
});

test('verified user sees only the server-resolved score and current unknown',async()=>{
  const calls=[];
  const app=createApp({env,verify:verified,sessions,getGrade:async s=>{calls.push(s);return {status:'ok',grade:sample};}});
  const res=await app(req('/grades?lang=uz&lab_id=another',{headers:{cookie:credentials}}));
  const body=await res.text();
  assert.equal(res.status,200); assert.deepEqual(calls,[subject]);
  assert.match(body,/34 \/ 59/); assert.match(body,/Tekshirib bo‘lmagan/); assert.match(body,/2026-10-27 09:05 UTC/);
  assert.doesNotMatch(body,/another|1234567890/);
  assert.match(res.headers.get('cache-control'),/no-store/);
  assert.match(res.headers.get('content-security-policy'),/frame-ancestors 'none'/);
});

test('unauthenticated and unbound users cannot read grades',async()=>{
  let count=0;
  const app=createApp({env,verify:verified,sessions,getGrade:async()=>{count++;return {status:'unauthorized'};}});
  assert.equal((await app(req('/grades'))).status,403); assert.equal(count,0);
  const response=await app(req('/grades?lang=ru',{headers:{cookie:credentials}}));
  assert.equal(response.status,403); assert.match(await response.text(),/не зарегистрирована/);
  assert.equal(count,1);
});

test('missing records do not display an invented zero and failures are generic',async()=>{
  let data={...sample,raw_earned:0,current_unresolved:[],missing_or_unresolved:['M1'],current:{},selected:{}};
  const app=createApp({env,verify:verified,sessions,getGrade:async()=>({status:'ok',grade:data})});
  let response=await app(req('/grades',{headers:{cookie:credentials}}));
  assert.match(await response.text(),/記録なし/);
  data={...data,raw_earned:'<script>alert(1)</script>'};
  response=await app(req('/grades',{headers:{cookie:credentials}}));
  assert.equal(response.status,503); assert.doesNotMatch(await response.text(),/<script>/);
});

test('logout requires same origin and invalid deployment stays closed',async()=>{
  const app=createApp({env,verify:verified,sessions,getGrade:async()=>({})});
  assert.equal((await app(req('/auth/logout',{method:'POST',headers:{origin:'https://evil.example'}}))).status,403);
  const allowed=await app(req('/auth/logout',{method:'POST',headers:{origin:'https://portal.example'}}));
  assert.equal(allowed.status,303); assert.match(allowed.headers.get('set-cookie'),/Max-Age=0/);
  assert.equal((await createApp({env:{}})(req('/grades'))).status,503);
});

test('a Google token alone or unavailable session store never grants grade access',async()=>{
  let calls=0;
  const app=createApp({env,verify:verified,sessions,getGrade:async()=>{calls++;return {status:'ok',grade:sample};}});
  assert.equal((await app(req('/grades',{headers:{cookie:'__Host-jdu-session=valid'}}))).status,403);
  assert.equal((await createApp({env,verify:verified,getGrade:async()=>{calls++;}})(req('/grades',{headers:{cookie:credentials}}))).status,503);
  const broken={...sessions,check:async()=>{throw Error('unavailable');}};
  assert.equal((await createApp({env,verify:verified,sessions:broken})(req('/grades',{headers:{cookie:credentials}}))).status,503);
  assert.equal(calls,0);
});

test('login binds a short session and logout invalidates a copied cookie',async()=>{
  let active=false;
  const id='a'.repeat(64);
  const sessionStore={issue:async(token,exp)=>{assert.equal(token,'valid');assert.equal(exp,2000000000);active=true;return {id,ttl:600};},
    check:async(sid,token)=>active && sid===id && token==='valid',revoke:async(sid)=>{assert.equal(sid,id);active=false;}};
  const verify=async(token,config,options)=>{assert.equal(token,'valid');if(options?.nonce)assert.ok(options.nonce);return {sub:subject,exp:2000000000};};
  const exchange=async()=>Response.json({id_token:'valid'});
  const app=createApp({env,verify,exchange,sessions:sessionStore,getGrade:async()=>({status:'ok',grade:sample})});
  const start=await app(req('/auth/login'));
  const flow=start.headers.getSetCookie()[0].split(';')[0];
  const state=new URL(start.headers.get('location')).searchParams.get('state');
  const end=await app(req(`/auth/callback?code=fake&state=${state}`,{headers:{cookie:flow}}));
  assert.equal(end.status,303);
  const headers=end.headers.getSetCookie();
  assert.equal(headers.length,3);
  assert.ok(headers.slice(0,2).every(v=>v.includes('Max-Age=600')&&v.includes('HttpOnly')&&v.includes('Secure')));
  const jar=headers.slice(0,2).map(v=>v.split(';')[0]).join('; ');
  assert.equal((await app(req('/grades',{headers:{cookie:jar}}))).status,200);
  const logout=await app(req('/auth/logout',{method:'POST',headers:{origin:'https://portal.example',cookie:jar}}));
  assert.equal(logout.status,303); assert.equal(logout.headers.getSetCookie().length,3);
  assert.equal((await app(req('/grades',{headers:{cookie:jar}}))).status,403);
});

test('failed server revocation clears browser cookies but signals failure',async()=>{
  const broken={...sessions,revoke:async()=>{throw Error('database failed');}};
  const app=createApp({env,verify:verified,sessions:broken});
  const response=await app(req('/auth/logout',{method:'POST',headers:{origin:'https://portal.example',cookie:credentials}}));
  assert.equal(response.status,503); assert.equal(response.headers.getSetCookie().length,3);
  assert.ok(response.headers.getSetCookie().every(v=>v.includes('Max-Age=0')));
});

test('grade client invokes only fixed function with verified subject',async()=>{
  const calls=[];
  const client={send:async command=>{calls.push(command.input);return {StatusCode:200,Payload:Buffer.from('{"status":"ok","grade":{}}')};}};
  const read=createGradeClient({GRADE_READER_FUNCTION_ARN:'arn:aws:lambda:us-east-1:123456789012:function:grade-read'},client);
  assert.equal((await read(subject)).status,'ok');
  assert.equal(calls[0].FunctionName,'arn:aws:lambda:us-east-1:123456789012:function:grade-read');
  assert.deepEqual(JSON.parse(Buffer.from(calls[0].Payload).toString()),{subject});
  await assert.rejects(()=>read('invalid'));
  assert.throws(()=>createGradeClient({GRADE_READER_FUNCTION_ARN:'https://example.com'},client));
  const status=createStatusClient({GRADE_READER_FUNCTION_ARN:'arn:aws:lambda:us-east-1:123456789012:function:grade-read'},client);
  await status(subject);
  assert.deepEqual(JSON.parse(Buffer.from(calls[1].Payload).toString()),{subject,operation:'status'});
});

test('status page requests only the verified identity and does not start a stopped server',async()=>{
  const calls=[];
  const observation={observed_at:'2026-10-27T09:00:00Z',instances:['bastion','web','dns','db','repo'].map(role=>
    ({role,ec2_state:'stopped',ssm_state:'unknown',public_ip:null}))};
  const app=createApp({env,verify:verified,sessions,getStatus:async s=>{calls.push(s);return {status:'ok',observation};}});
  const result=await app(req('/status?lang=uz&account=other',{headers:{cookie:credentials}}));
  assert.equal(result.status,200); const html=await result.text();
  assert.match(html,/Muhit holati/); assert.match(html,/To‘xtagan/); assert.match(html,/Noma’lum/); assert.match(html,/2026-10-27 09:00 UTC/);
  assert.doesNotMatch(html,/account=other/); assert.deepEqual(calls,[subject]);
});

test('malformed or unavailable status is shown as unavailable, not stopped',async()=>{
  const app=createApp({env,verify:verified,sessions,getStatus:async()=>({status:'ok',observation:{instances:[],observed_at:'2026-10-27T09:00:00Z'}})});
  const result=await app(req('/status',{headers:{cookie:credentials}}));
  assert.equal(result.status,503); const html=await result.text();
  assert.match(html,/状態を確認できません/); assert.doesNotMatch(html,/stopped/);
});


test('an expired check login offers a safe return link without executing or saving',async()=>{
  let calls=0;
  const app=createApp({env:{...env,PORTAL_CHECKER_ENABLED:'true'},verify:verified,sessions:{...sessions,check:async()=>false},checker:async()=>{calls++;}});
  const path='/checks?lang=ja&task_id=M5&job_id=12345678-1234-4234-8234-123456789abc&check_mode=functional';
  const result=await app(req(path,{headers:{cookie:credentials}}));
  assert.equal(result.status,403);assert.equal(calls,0);
  const html=await result.text();assert.match(html,/ログインし直す/);
  assert.ok(html.includes('/auth/login?next='+encodeURIComponent(path)));
  assert.doesNotMatch(html,/<input[^>]*name="password"|<form|type="submit"/);
});


test('semester expiry blocks sign-in, grades and check POST before any backend is called', async()=>{
  let calls=0;
  const app=createApp({env:{...env,PORTAL_EXPIRES_AT:'1000000000'},verify:async()=>{calls++;},
    getGrade:async()=>{calls++;},checker:async()=>{calls++;},getTeacher:async()=>{calls++;}});
  for (const path of ['/','/auth/login','/auth/callback','/checks','/grades','/teacher','/enroll']) {
    const result=await app(new Request('https://portal.example'+path,{method:path==='/checks'?'POST':'GET'}));
    assert.equal(result.status,410,path);
  }
  assert.equal(calls,0);
});

test('opening a student assignment shows only its saved detail without running a check', async()=>{
  const calls=[];
  const checkSession='a'.repeat(64);
  const cookie='__Host-jdu-session=valid; __Host-jdu-access='+checkSession;
  const app=createApp({env:{...env,PORTAL_CHECKER_ENABLED:'true'},verify:verified,sessions:{...sessions,check:async(id,token)=>id===checkSession && token==='valid'},
    getGrade:async (...args)=>{calls.push(args);return {status:'ok',grade:{...sample,task_checks:[{id:'WEB02_PUBLIC_HTTP',status:'PASS'},{id:'WEB02_FILE',status:'FAIL'},{id:'WEB02_ACCESS_LOG',status:'UNKNOWN'}]}};},
    checker:async()=>{throw Error('GET must not run a checker');}});
  const result=await app(req('/checks?lang=ja&task_id=M1',{headers:{cookie}}));
  assert.equal(result.status,200);
  const html=await result.text();
  assert.match(html,/<h2>M1<\/h2>/);
  assert.match(html,/8 \/ 8/);
  assert.match(html,/公開IPで指定URL[^<]+<\/th>\s*<td><span[^>]*>OK/);
  assert.match(html,/指定の配信ファイル[^<]+<\/th>\s*<td><span[^>]*>要修正/);
  assert.match(html,/今回確認したリクエスト[^<]+<\/th>\s*<td><span[^>]*>未確認/);
  assert.ok(html.indexOf('data-check-id="WEB02_FILE"') < html.indexOf('data-check-id="WEB02_PUBLIC_HTTP"'));
  assert.match(html,/lang=ru&amp;task_id=M1/);
  assert.doesNotMatch(html,/<h2>M2<\/h2>/);
  assert.deepEqual(calls,[[subject,'M1']]);
  const rejected=await app(req('/checks?task_id=P3',{headers:{cookie}}));
  assert.equal(rejected.status,403);
  assert.equal(calls.length,1);
});

test('unregistered school students are redirected to registration before grading', async()=>{
  const access='b'.repeat(64);
  const cookie='__Host-jdu-session=valid; __Host-jdu-access='+access;
  let status='unauthorized';
  const app=createApp({env:{...env,PORTAL_CHECKER_ENABLED:'true',PORTAL_SELF_LINK_ENABLED:'true'},
    verify:async()=>({sub:subject,email:'student@jdu.uz',email_verified:true,hd:'jdu.uz'}),
    sessions:{...sessions,check:async(id,token)=>id===access && token==='valid'},
    getGrade:async()=>({status,grade:sample}),getStatus:async()=>({status}),
    enroll:async()=>assert.fail('Registration executes only after submission'),
    checker:async()=>assert.fail('Checking executes only after submission')});
  for(const lang of ['ja','ru','uz']){
    for(const path of ['/checks','/checks?task_id=M1','/grades','/status']){
      const url=path+(path.includes('?')?'&':'?')+'lang='+lang;
      const result=await app(req(url,{headers:{cookie}}));
      assert.equal(result.status,303,url);
      assert.equal(result.headers.get('location'),'/link?lang='+lang,url);
    }
  }
  status='ok';
  const registered=await (await app(req('/checks',{headers:{cookie}}))).text();
  assert.match(registered,/<table/);
  assert.doesNotMatch(registered,/初回登録を始める/);
  status='unavailable';
  const unavailable=await app(req('/checks',{headers:{cookie}}));
  assert.equal(unavailable.status,200);
});

test('the Google test student can open enrollment but cannot reach teacher or preparation routes', async()=>{
  const lab='lab-'+'a'.repeat(20), access='b'.repeat(64), subject='201'+'0'.repeat(38)+'1';
  const cookie='__Host-jdu-session=test-token; __Host-jdu-access='+access;
  let gradeResult={status:'unauthorized'};
  const envWithTest={...env,PORTAL_CHECKER_ENABLED:'true',PORTAL_SELF_LINK_ENABLED:'true',
    GOOGLE_TEST_CONFIG:{client_id:[4321,'test.apps.googleusercontent.com'].join('-'),email:'allowed.test@gmail.com',
      client_secret:['GOCSPX','synthetic-test-client-secret'].join('-'),lab_id:lab,expires_at:Math.floor(Date.now()/1000)+600}};
  const app=createApp({env:envWithTest,verify:async()=>{throw Error('Not a Google token');},
    verifyTestStudent:async()=>({sub:subject,testLab:lab}),sessions:{check:async()=>true},
    getGrade:async()=>gradeResult,checker:async()=>assert.fail('No check should run'),
    getTeacher:async()=>assert.fail('No teacher lookup for Google test identity'),
    enroll:async()=>assert.fail('No enrollment on GET')});
  assert.equal((await app(req('/auth/google-test?lang=ru'))).status,303);
  const checks=await app(req('/checks?lang=ru',{headers:{cookie}}));
  assert.equal(checks.headers.get('location'),'/link?lang=ru');
  const link=await app(req('/link?lang=ru',{headers:{cookie}}));
  assert.equal(link.status,200);
  const linkPage=await link.text();
  assert.ok(linkPage.includes('--lab-id '+lab));
  const requestId=linkPage.match(/name="request_id" value="([a-f0-9]{64})"/)[1];
  const csrf=linkPage.match(/name="csrf" value="([a-f0-9]{64})"/)[1];
  const wrongCode='jdu-link1.lab-'+'b'.repeat(20)+'.123456789012.'+Math.floor(Date.now()/1000)+'.'+'c'.repeat(64);
  const wrongLab=await app(req('/link?lang=ru',{method:'POST',
    headers:{cookie,origin:env.PUBLIC_ORIGIN,'content-type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({request_id:requestId,csrf,code:wrongCode})}));
  assert.equal(wrongLab.status,403);
  assert.match(await wrongLab.text(),/Код выдан для другой среды AWS/);
  assert.equal((await app(req('/teacher',{headers:{cookie}}))).status,403);
  assert.equal((await app(req('/prepare',{headers:{cookie}}))).status,404);
  assert.equal((await createApp({env})(req('/auth/google-test'))).status,404);
  gradeResult={status:'ok',grade:{...sample,lab_id:'lab-'+'b'.repeat(20)}};
  for(const path of ['/checks','/grades','/status']) assert.equal((await app(req(path,{headers:{cookie}}))).status,403);
});
