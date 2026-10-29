import test from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from './router.mjs';
import { checkToken,verifyCheckToken } from './checks.mjs';
import { configFrom } from './auth.mjs';
const env={PORTAL_MODE:'enabled',PORTAL_CHECKER_ENABLED:'true',PUBLIC_ORIGIN:'https://portal.example',GOOGLE_CLIENT_ID:'123-example.apps.googleusercontent.com',GOOGLE_CLIENT_SECRET:'synthetic-secret-only'};
const session='a'.repeat(64),token='valid',cookie=`__Host-jdu-session=${token}; __Host-jdu-access=${session}`;
const value={operation:'start',task_id:'M1',job_id:'11111111-1111-4111-8111-111111111111'};
const headers={cookie,origin:env.PUBLIC_ORIGIN,'content-type':'application/x-www-form-urlencoded'};
const credentials={env,verify:async t=>{if(t!==token)throw Error();return{sub:'1234567890'};},sessions:{check:async s=>s===session}};
const request=(path,options={})=>new Request(env.PUBLIC_ORIGIN+path,{headers:{cookie},...options});
function body(v=value){return new URLSearchParams({...v,csrf:checkToken(configFrom(env),session,token,v)}).toString();}
test('GET lists fixed tasks without invoking a checker; POST uses verified subject and redirects',async()=>{
  const calls=[];const app=createApp({...credentials,checker:async event=>{calls.push(event);return {status:'ok'};}});
  const get=await app(request('/checks'));assert.equal(get.status,200);assert.equal(calls.length,0);
  assert.equal(get.headers.get('referrer-policy'),'same-origin');assert.match(await get.text(),/M6|P0/);
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
  assert.doesNotMatch(text,/今回の素点: 0/);
});
test('completed checks show actual task points, UNKNOWN and escaped rows in all languages',async()=>{
  const result={status:'ok',job:{...value,phase:'report_ready'},result:{task_id:'M1',checked_at:'2026-10-29T12:00:00Z',saved_grade_changed:false,
    checks:[{id:'WEB02_PUBLIC_HTTP',status:'UNKNOWN'}],score:{raw_earned:7,raw_maximum:8,counts_toward_assessment:true,evaluable:false}}};
  const app=createApp({...credentials,checker:async()=>result});
  for(const lang of ['ja','ru','uz']){
    const res=await app(request(`/checks?lang=${lang}&task_id=M1&job_id=${value.job_id}`));assert.equal(res.status,200);const text=await res.text();assert.match(text,/7 \/ 8/);assert.match(text,/WEB02_PUBLIC_HTTP/);assert.doesNotMatch(text,/data-check-progress/);
  }
  result.result.checks[0].id='<script>';
  const malformed=await app(request(`/checks?task_id=M1&job_id=${value.job_id}`));assert.equal(malformed.status,503);assert.doesNotMatch(await malformed.text(),/<script>/);
});
