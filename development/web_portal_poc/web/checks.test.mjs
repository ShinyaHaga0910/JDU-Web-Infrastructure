import test from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from './router.mjs';
import { checkToken,verifyCheckToken,displayTask,tasks,checkHtml,taskDetailHtml } from './checks.mjs';
import { readFileSync } from 'node:fs';
import { configFrom } from './auth.mjs';
import {generateKeyPairSync,privateDecrypt,constants} from 'node:crypto';
import {sealApplicationPassword} from './checks.mjs';
const env={PORTAL_MODE:'enabled',PORTAL_CHECKER_ENABLED:'true',PUBLIC_ORIGIN:'https://portal.example',GOOGLE_CLIENT_ID:'123-example.apps.googleusercontent.com',GOOGLE_CLIENT_SECRET:'synthetic-secret-only'};
const session='a'.repeat(64),token='valid',cookie=`__Host-jdu-session=${token}; __Host-jdu-access=${session}`;
const value={operation:'start',task_id:'M1',job_id:'11111111-1111-4111-8111-111111111111'};
const headers={cookie,origin:env.PUBLIC_ORIGIN,'content-type':'application/x-www-form-urlencoded'};
const credentials={env,verify:async t=>{if(t!==token)throw Error();return{sub:'1234567890'};},sessions:{check:async s=>s===session}};
const request=(path,options={})=>new Request(env.PUBLIC_ORIGIN+path,{headers:{cookie},...options});
test('practice list and detail retain partial points without adding them to the course total',()=>{
  const grade={raw_earned:5,raw_maximum:64,selected:{P0:{raw_earned:1},M0:{raw_earned:4}},
    current:{P1:{raw_earned:3,raw_maximum:8,evaluable:false}}};
  for(const lang of ['ja','ru','uz']) {
    const list=checkHtml(lang,{grade,maxima:{P0:1,M0:4},blocked:true});
    assert.match(list,/task_id=P1[\s\S]*?3 \/ 8/);
    assert.match(taskDetailHtml(lang,'P1',grade),/<strong>3 \/ 8<\/strong>/);
  }
  assert.equal(grade.raw_earned,5);
  assert.deepEqual(Object.keys(grade.selected),['P0','M0']);
  grade.current.P1.raw_earned='<script>';
  assert.doesNotMatch(checkHtml('ja',{grade,blocked:true}),/<script>/);
});
function body(v=value){return new URLSearchParams({...v,csrf:checkToken(configFrom(env),session,token,v)}).toString();}
test('displayed P and M labels are consecutive and match the course',()=>{
  const policy=JSON.parse(readFileSync(new URL('../../../course/curriculum.json',import.meta.url),'utf8'));
  const labels={...policy.practice_display_ids,...policy.mission_display_ids};
  assert.deepEqual(tasks,policy.active_order);
  for(const prefix of ['P','M']){
    assert.deepEqual(tasks.filter(id=>id.startsWith(prefix)).map(displayTask),
      [0,1,2,3,4,5].map(number=>prefix+number));
  }
  for(const id of tasks) assert.equal(displayTask(id),labels[id]??id);
});
test('GET lists fixed tasks without invoking a checker; POST uses verified subject and redirects',async()=>{
  const calls=[];const app=createApp({...credentials,checker:async event=>{calls.push(event);return {status:'ok'};}});
  const get=await app(request('/checks'));assert.equal(get.status,200);assert.equal(calls.length,0);
  assert.equal(get.headers.get('referrer-policy'),'same-origin');
  const html=await get.text();
  assert.match(html,/task_id=P4">P3<\/a>/);
  assert.match(html,/task_id=P5">P4<\/a>/);
  assert.match(html,/task_id=P6">P5<\/a>/);
  assert.doesNotMatch(html,/>P6<\/a>/);
  assert.match(html,/task_id=M4">M3<\/a>/);
  assert.match(html,/task_id=M5">M4<\/a>/);
  assert.match(html,/task_id=M6">M5<\/a>/);
  assert.doesNotMatch(html,/>M6<\/a>/);
  const post=await app(request('/checks',{method:'POST',headers,body:body()}));
  assert.equal(post.status,303);assert.match(post.headers.get('location'),/task_id=M1&job_id=/);
  assert.deepEqual(calls,[{subject:'1234567890',...value}]);
});
test('no authentication, wrong origin, altered task/action/session, extra fields denied',async()=>{
  let calls=0;const app=createApp({...credentials,checker:async()=>{calls++;}});
  assert.equal((await app(request('/checks',{headers:{}}))).status,403);
  for(const opts of [
    {headers:{...headers,origin:'https://evil.example'},body:body()},
    {headers,body:body().replace('task_id=M1','task_id=M2')},
    {headers,body:body()+'&score=62'},
    {headers,body:body().replace('operation=start','operation=advance')},
  ]) assert.equal((await app(request('/checks',{method:'POST',...opts}))).status,403);
  assert.equal(calls,0);
  assert.equal(verifyCheckToken(configFrom(env),'b'.repeat(64),token,value,checkToken(configFrom(env),session,token,value)),false);
});
test('GET result cannot advance; pending has manual fallback and bounded automatic POST',async()=>{
  const calls=[];const app=createApp({...credentials,checker:async event=>{calls.push(event);return {status:'ok',job:{...value,phase:'observing'}};}});
  const res=await app(request(`/checks?task_id=M1&job_id=${value.job_id}`));
  assert.equal(res.status,200);const text=await res.text();
  assert.equal(calls[0].operation,'result');assert.match(text,/data-check-progress/);assert.match(text,/method="post"/);assert.match(text,/check-progress.js/);
  assert.match(text,/<progress class="check-spinner"/);
  assert.match(text,/課題を選び直す/);
  assert.match(res.headers.get('content-security-policy'),/connect-src 'self'/);
  assert.doesNotMatch(text,/今回の素点: 0/);
});
test('an interrupted POST retains a link to the same job rather than a second start',async()=>{
  const app=createApp({...credentials,checker:async()=>{throw Error('temporary network loss');}});
  const res=await app(request('/checks',{method:'POST',headers,body:body()}));
  assert.equal(res.status,503);const text=await res.text();
  assert.ok(text.includes(`task_id=M1&amp;job_id=${value.job_id}`));assert.doesNotMatch(text,/operation" value="start/);
});
test('completed checks show actual task points, UNKNOWN and escaped rows in all languages',async()=>{
  const result={status:'ok',job:{...value,phase:'report_ready'},result:{task_id:'M1',checked_at:'2026-10-29T12:00:00Z',saved_grade_changed:false,
    checks:[{id:'WEB02_PUBLIC_HTTP',status:'UNKNOWN'}],score:{raw_earned:7,raw_maximum:8,counts_toward_assessment:true,evaluable:false}}};
  const app=createApp({...credentials,checker:async()=>result});
  for(const lang of ['ja','ru','uz']){
    const res=await app(request(`/checks?lang=${lang}&task_id=M1&job_id=${value.job_id}`));assert.equal(res.status,200);const text=await res.text();assert.match(text,/7 \/ 8/);assert.match(text,/WEB02_PUBLIC_HTTP/);assert.doesNotMatch(text,/data-check-progress/);
    assert.ok(text.includes(`?lang=ru&amp;task_id=M1&amp;job_id=${value.job_id}`));
  }
  result.result.checks[0].id='<script>';
  const malformed=await app(request(`/checks?task_id=M1&job_id=${value.job_id}`));assert.equal(malformed.status,503);assert.doesNotMatch(await malformed.text(),/<script>/);
});
test('saved results show a compact outcome and counts without timestamps or a receipt banner',async()=>{
  const id='22222222-2222-4222-8222-222222222222';
  for(const [task,counted,evaluable,earned,word] of [
    ['M1',true,true,8,'合格'],['M0',true,true,2,'修正が必要'],
    ['M5',true,false,8,'確認できない項目があります'],['P1',false,true,8,'確認完了'],
  ]){
    const maximum=task==='M0'?4:8;
    const result={status:'ok',job:{...value,task_id:task,phase:'report_ready'},result:{task_id:task,request_id:id,checked_at:'2026-10-29T12:00:00Z',
      checks:[{id:'WEB02_PUBLIC_HTTP',status:'PASS'}],score:{raw_earned:earned,raw_maximum:maximum,counts_toward_assessment:counted,evaluable}},
      submission:{status:'saved',request_id:id,received_at:'2026-10-29T12:01:00Z',counts_toward_assessment:counted,evaluable}};
    const app=createApp({...credentials,checker:async()=>result});
    const res=await app(request(`/checks?task_id=${task}&job_id=${value.job_id}`));
    assert.equal(res.status,200);const text=await res.text();
    assert.ok(text.includes(`<h3>${word}</h3>`));
    assert.equal(text.includes(`<strong>${earned} / ${maximum}</strong> 項目クリア`),counted || task==='P1');
    assert.doesNotMatch(text,/2026-10-29T12:0|成績原本に保存|name="operation" value="submit"/);
    result.submission.request_id='33333333-3333-4333-8333-333333333333';
    assert.equal((await app(request(`/checks?task_id=${task}&job_id=${value.job_id}`))).status,503);
  }
});
test('pending result offers a same-report POST retry without automatic GET writes',async()=>{
  const calls=[];const ready={status:'ok',job:{...value,phase:'report_ready'},result:{task_id:'M1',checked_at:'2026-10-29T12:00:00Z',
    checks:[{id:'WEB02_PUBLIC_HTTP',status:'PASS'}],score:{raw_earned:8,raw_maximum:8,counts_toward_assessment:true,evaluable:true}},submission:{status:'pending'}};
  const app=createApp({...credentials,checker:async event=>{calls.push(event);return ready;}});
  const get=await app(request(`/checks?task_id=M1&job_id=${value.job_id}`));const text=await get.text();
  assert.match(text,/name="operation" value="submit"/);assert.doesNotMatch(text,/data-check-progress/);assert.equal(calls[0].operation,'result');
  const submit={...value,operation:'submit'};
  assert.equal((await app(request('/checks',{method:'POST',headers,body:body(submit)}))).status,303);
  assert.deepEqual(calls[1],{subject:'1234567890',...submit});
});

test('functional browser POST sends only an owned RSA ciphertext to the private checker',async()=>{
  const keys=generateKeyPairSync('rsa',{modulusLength:4096});
  const recipient={job_id:value.job_id,public_key:keys.publicKey.export({type:'spki',format:'pem'})};
  const selected={...value,task_id:'M5',check_mode:'functional',operation:'functional_start'};
  const password='SyntheticアプリPassword2026',calls=[];
  const app=createApp({...credentials,checker:async event=>{
    calls.push(event);
    return {status:'ok',job:{...selected,phase:'awaiting_password'},functional_recipient:recipient};
  }});
  const payload=new URLSearchParams(body(selected));payload.set('password',password);
  const response=await app(request('/checks?lang=ja',{method:'POST',headers,body:payload.toString()}));
  assert.equal(response.status,303);assert.match(response.headers.get('location'),/check_mode=functional/);
  assert.equal(calls.length,2);assert.equal(calls[0].operation,'functional_context');
  assert.equal(calls[1].operation,'functional_start');
  assert.ok(!JSON.stringify(calls).includes(password));assert.ok(!Object.hasOwn(calls[1],'password'));
  const plain=privateDecrypt({key:keys.privateKey,padding:constants.RSA_PKCS1_OAEP_PADDING,oaepHash:'sha256'},Buffer.from(calls[1].sealed_password,'base64'));
  assert.deepEqual(JSON.parse(plain),[selected.job_id,password]);
  const get=await app(request(`/checks?task_id=M5&job_id=${value.job_id}&check_mode=functional`));
  const html=await get.text();assert.equal(get.status,200);assert.match(html,/type="password"/);assert.match(html,/name="check_mode" value="functional"/);
  assert.ok(!html.includes(password));assert.ok(!html.includes('BEGIN PUBLIC KEY'));assert.doesNotMatch(html,/data-check-progress/);
  assert.ok(html.includes(`lang=ru&amp;task_id=M5&amp;job_id=${value.job_id}&amp;check_mode=functional`));
});

test('retired storage tasks cannot be selected or execute any checker',async()=>{
  let calls=0;
  const app=createApp({...credentials,checker:async()=>{calls++;return {status:'ok'};}});
  for(const task of ['P3','M3']) {
    const response=await app(request(`/checks?task_id=${task}&job_id=${value.job_id}&check_mode=storage`));
    assert.equal(response.status,403);
    const input=new URLSearchParams({operation:'start',task_id:task,job_id:value.job_id,csrf:'a'.repeat(64)});
    assert.equal((await app(request('/checks',{method:'POST',headers,body:input.toString()}))).status,403);
  }
  const html=await (await app(request('/checks'))).text();
  assert.doesNotMatch(html,/name="task_id" value="[PM]3"/);
  assert.equal(calls,0);
});

test('mode changes and plaintext or ciphertext injection cannot bypass the form action',async()=>{
  let calls=0;const app=createApp({...credentials,checker:async()=>{calls++;return {status:'ok'};}});
  for(const selected of [
    {...value,task_id:'M1',check_mode:'functional'},
    {...value,task_id:'M5',check_mode:'storage'},
  ]) {
    const input=new URLSearchParams({...selected,csrf:'a'.repeat(64)});
    assert.equal((await app(request('/checks',{method:'POST',headers,body:input.toString()}))).status,403);
  }
  assert.equal((await app(request('/checks',{method:'POST',headers,body:body()+'&password=SyntheticOnly'}))).status,403);
  assert.equal((await app(request('/checks',{method:'POST',headers,body:body()+'&sealed_password=SyntheticOnly'}))).status,403);
  const changed={...value,task_id:'M5',check_mode:'functional'};
  const input=new URLSearchParams(body(changed));input.set('check_mode','read_only');
  assert.equal((await app(request('/checks',{method:'POST',headers,body:input.toString()}))).status,403);
  assert.equal(calls,0);
});

test('password seal rejects a different job or key and bounds Unicode without storing a password',()=>{
  const keys=generateKeyPairSync('rsa',{modulusLength:4096});
  const recipient={job_id:value.job_id,public_key:keys.publicKey.export({type:'spki',format:'pem'})};
  assert.equal(Buffer.from(sealApplicationPassword('あ'.repeat(128),recipient,value.job_id),'base64').length,512);
  assert.throws(()=>sealApplicationPassword('SyntheticOnly',recipient,'22222222-2222-4222-8222-222222222222'));
  for(const password of ['', 'a'.repeat(129),'contains\ncontrol','contains\0control'])assert.throws(()=>sealApplicationPassword(password,recipient,value.job_id));
  assert.throws(()=>sealApplicationPassword('SyntheticOnly',{...recipient,public_key:'invalid'},value.job_id));
});
