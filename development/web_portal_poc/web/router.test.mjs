import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createApp, MISSION_MAXIMA } from './router.mjs';
import { createGradeClient } from './grade-client.mjs';

const env={PORTAL_MODE:'enabled', PUBLIC_ORIGIN:'https://portal.example', GOOGLE_CLIENT_ID:'1234-example.apps.googleusercontent.com', GOOGLE_CLIENT_SECRET:'example-test-secret-only'};
const subject='1234567890';
const verified=async token => {if(token!=='valid')throw Error('no session');return {sub:subject};};
const sample={raw_earned:34,raw_maximum:62,current_unresolved:['M5'],missing_or_unresolved:['M6'],
              current:{M5:{evaluable:false,checked_at:'2026-10-27T09:00:00Z'}},selected:{M1:{raw_earned:8},M2:{raw_earned:13},M5:{raw_earned:13,received_at:'2026-10-27T09:05:00Z'}}};
const req=(path,options={})=>new Request(`https://portal.example${path}`,options);

test('score bounds match the existing assessment registry',async()=>{
  const registry=JSON.parse(await readFile(new URL('../../01_roles/cyber_security/tools/web_lab_assessment/assessment-registry.json',import.meta.url),'utf8'));
  const maxima=Object.fromEntries(registry.tasks.filter(t=>t.category==='automated_mission').map(t=>[t.id,t.raw_points_max]));
  assert.deepEqual(MISSION_MAXIMA,maxima);
});

test('verified user sees only the server-resolved score and current unknown',async()=>{
  const calls=[];
  const app=createApp({env,verify:verified,getGrade:async s=>{calls.push(s);return {status:'ok',grade:sample};}});
  const res=await app(req('/grades?lang=uz&lab_id=another',{headers:{cookie:'__Host-jdu-session=valid'}}));
  const body=await res.text();
  assert.equal(res.status,200); assert.deepEqual(calls,[subject]);
  assert.match(body,/34 \/ 62/); assert.match(body,/Tekshirib bo‘lmagan/); assert.match(body,/2026-10-27 09:05 UTC/);
  assert.doesNotMatch(body,/another|1234567890/);
  assert.match(res.headers.get('cache-control'),/no-store/);
  assert.match(res.headers.get('content-security-policy'),/frame-ancestors 'none'/);
});

test('unauthenticated and unbound users cannot read grades',async()=>{
  let count=0;
  const app=createApp({env,verify:verified,getGrade:async()=>{count++;return {status:'unauthorized'};}});
  assert.equal((await app(req('/grades'))).status,403); assert.equal(count,0);
  const response=await app(req('/grades?lang=ru',{headers:{cookie:'__Host-jdu-session=valid'}}));
  assert.equal(response.status,403); assert.match(await response.text(),/не зарегистрирована/);
  assert.equal(count,1);
});

test('missing records do not display an invented zero and failures are generic',async()=>{
  let data={...sample,raw_earned:0,current_unresolved:[],missing_or_unresolved:['M1'],current:{},selected:{}};
  const app=createApp({env,verify:verified,getGrade:async()=>({status:'ok',grade:data})});
  let response=await app(req('/grades',{headers:{cookie:'__Host-jdu-session=valid'}}));
  assert.match(await response.text(),/記録なし/);
  data={...data,raw_earned:'<script>alert(1)</script>'};
  response=await app(req('/grades',{headers:{cookie:'__Host-jdu-session=valid'}}));
  assert.equal(response.status,503); assert.doesNotMatch(await response.text(),/<script>/);
});

test('logout requires same origin and invalid deployment stays closed',async()=>{
  const app=createApp({env,verify:verified,getGrade:async()=>({})});
  assert.equal((await app(req('/auth/logout',{method:'POST',headers:{origin:'https://evil.example'}}))).status,403);
  const allowed=await app(req('/auth/logout',{method:'POST',headers:{origin:'https://portal.example'}}));
  assert.equal(allowed.status,303); assert.match(allowed.headers.get('set-cookie'),/Max-Age=0/);
  assert.equal((await createApp({env:{}})(req('/grades'))).status,503);
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
});
