import test from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from './router.mjs';
import { createTeacherClient } from './teacher-progress.mjs';
import { tasks, CHECK_MAXIMA, displayTask } from './checks.mjs';

const env={PORTAL_MODE:'enabled',PUBLIC_ORIGIN:'https://portal.example',GOOGLE_CLIENT_ID:'1234-example.apps.googleusercontent.com',GOOGLE_CLIENT_SECRET:'synthetic-test-only-no-real-key'};
const claims={sub:'1234567890',email:'teacher@jdu.uz',email_verified:true,hd:'jdu.uz'};
const credentials='__Host-jdu-session=valid; __Host-jdu-access=session';
const sessions={check:async(id,token)=>id==='session' && token==='valid',revoke:async()=>{}};
const verify=async token=>{if(token!=='valid')throw Error('No session');return claims;};
const req=path=>new Request('https://portal.example'+path,{headers:{cookie:credentials,'x-teacher-email':'attacker@jdu.uz'}});
const maxima={M1:8,M2:13,M4:9,M5:13,M6:16};
const grade={lab_id:'course-student',raw_earned:59,raw_maximum:59,current_unresolved:['M5'],missing_or_unresolved:[],
  current:{M5:{evaluable:false,checked_at:'2026-10-30T04:00:00Z',received_at:'2026-10-30T04:01:00Z'}},
  selected:Object.fromEntries(Object.entries(maxima).map(([m,n])=>[m,{raw_earned:n,received_at:'2026-10-23T00:00:00Z'}]))};
const progress={classroom:true,context:'course',students:[{lab_id:'course-student',context:'course',status:'ok',grade}],next_after:null};
function app(getTeacher,extra={}){return createApp({env,verify,sessions,getTeacher,...extra});}

test('teacher list uses only verified claims and canonical selected grades',async()=>{
  const calls=[];
  const response=await app(async e=>{calls.push(e);return {status:'ok',teacher:progress};})(req('/teacher'));
  assert.equal(response.status,200);const html=await response.text();
  assert.deepEqual(calls,[{subject:claims.sub,email:claims.email,operation:'teacher_list',context:'course',after:''}]);
  assert.match(html,/59 \/ 59/);assert.match(html,/13 \/ 13/);assert.match(html,/M5/);assert.match(html,/2026-10-30 04:01 UTC/);
  assert.doesNotMatch(html,/teacher@jdu|attacker@jdu|1234567890/);
  assert.match(html,/tabindex="0" role="region" aria-labelledby="teacher-caption"/);
  assert.match(html,/<caption id="teacher-caption">授業用/);assert.match(html,/<th scope="col">M1/);
  assert.match(response.headers.get('cache-control'),/no-store/);
});

test('a school login without teacher access is denied and gets no home link',async()=>{
  const instance=app(async()=>({status:'unauthorized'}));
  assert.equal((await instance(req('/teacher'))).status,403);
  assert.doesNotMatch(await (await instance(req('/'))).text(),/href="\/teacher/);
  let calls=0;
  const missing=app(async()=>{calls++;},{verify:async()=>({sub:'123',email:'teacher@jdu.uz'})});
  assert.equal((await missing(req('/teacher'))).status,403);assert.equal(calls,0);
});

test('only operator-granted teachers get a home link and expiry precedes backend reads',async()=>{
  const instance=app(async()=>({status:'ok',teacher:{class_id:'193548'}}));
  assert.match(await (await instance(req('/'))).text(),/href="\/teacher\?lang=ja"/);
  let calls=0;
  const denied=app(async()=>{calls++;},{sessions:{check:async()=>false}});
  assert.equal((await denied(req('/teacher'))).status,403);assert.equal(calls,0);
});

test('course view and explicit verification view remain separate in all three languages',async()=>{
  const calls=[];const instance=app(async e=>{calls.push(e);return {status:'ok',teacher:{...progress,context:e.context,students:[]}};});
  for(const lang of ['ja','ru','uz']) {
    const response=await instance(req('/teacher?lang='+lang+'&context=verification'));
    assert.equal(response.status,200);const html=await response.text();
    assert.match(html,/context=verification/);assert.match(html,new RegExp(`lang=${lang}`));
    assert.doesNotMatch(html,/59 \/ 59/);
  }
  assert.ok(calls.every(e=>e.context==='verification'));
});

test('teacher detail respects backend authorization and preserves the Lab when switching language',async()=>{
  const instance=app(async e=>e.lab_id==='course-student'?{status:'ok',teacher:{class_id:'193548',student:progress.students[0]}}:{status:'unauthorized'});
  const response=await instance(req('/teacher/student?lang=ru&lab_id=course-student'));
  assert.equal(response.status,200);const html=await response.text();
  assert.match(html,/59 \/ 59/);assert.match(html,/lang=uz&amp;lab_id=course-student/);
  assert.equal((await instance(req('/teacher/student?lab_id=not-assigned'))).status,403);
});

test('never-submitted students show zero points while unavailable students show an error',async()=>{
  const empty={...grade,raw_earned:0,selected:{},current:{},current_unresolved:[],missing_or_unresolved:Object.keys(maxima)};
  const value={...progress,students:[{lab_id:'course-student',context:'course',status:'ok',grade:empty},{lab_id:'unavailable-lab',context:'course',status:'unavailable'}]};
  const response=await app(async()=>({status:'ok',teacher:value}))(req('/teacher'));
  assert.equal(response.status,200);const html=await response.text();
  assert.match(html,/0 \/ 59/);assert.match(html,/取得できません/);
  for(const n of [1,4,8,9,13,16]) assert.ok(html.includes(`0 / ${n}`));
  assert.match(html,/<th scope="col">P5<\/th>/);
});

test('extra caller privileges, invalid cursors and malformed score data are rejected',async()=>{
  let calls=0;const instance=app(async()=>{calls++;return {status:'ok',teacher:progress};});
  for(const path of ['/teacher?role=teacher','/teacher?after=../../','/teacher?context=course&context=verification'])assert.equal((await instance(req(path))).status,403);
  assert.equal(calls,0);
  const bad=app(async()=>({status:'ok',teacher:{...progress,students:[{...progress.students[0],grade:{...grade,raw_earned:0}}]}}));
  assert.equal((await bad(req('/teacher'))).status,503);
});

test('teacher reader client accepts only fixed same-account operations and bounded responses',async()=>{
  const config={PORTAL_AWS_ACCOUNT_ID:'170126527713',GRADE_READER_FUNCTION_ARN:'arn:aws:lambda:us-east-1:170126527713:function:reader'};
  const calls=[];const client=createTeacherClient(config,{send:async command=>{calls.push(command.input);return {StatusCode:200,Payload:Buffer.from(JSON.stringify({status:'ok',teacher:progress}))};}});
  const event={operation:'teacher_list',subject:claims.sub,email:claims.email,context:'course',after:''};
  assert.equal((await client(event)).status,'ok');assert.deepEqual(JSON.parse(Buffer.from(calls[0].Payload).toString()),event);
  await assert.rejects(()=>client({...event,role:'teacher'}));
  assert.throws(()=>createTeacherClient({...config,PORTAL_AWS_ACCOUNT_ID:'000000000000'}));
  assert.equal(calls.length,1);
});

test('selected teacher task reads only the authorized student detail',async()=>{
  const calls=[];
  const instance=app(async e=>{calls.push(e);return {status:'ok',teacher:{class_id:'193548',student:progress.students[0]}};});
  const result=await instance(req('/teacher/student?lang=ja&lab_id=course-student&task_id=M1'));
  assert.equal(result.status,200);
  assert.match(await result.text(),/<h2>M1<\/h2>/);
  assert.equal(calls[0].task_id,'M1');
  assert.equal(calls[0].lab_id,'course-student');
  for(const task of tasks) {
    const response=await instance(req(`/teacher/student?lab_id=course-student&task_id=${task}`));
    assert.equal(response.status,200,task);
    assert.match(await response.text(),new RegExp(`<h2>${displayTask(task)}</h2>`));
    assert.equal(calls.at(-1).task_id,task);
  }
  const count=calls.length;
  for(const task of ['P3','M3','M99'])assert.equal((await instance(req(`/teacher/student?lab_id=course-student&task_id=${task}`))).status,403);
  assert.equal(calls.length,count);
});

test('the teacher service client forwards every active P/M detail and rejects retired tasks',async()=>{
  const client=createTeacherClient({PORTAL_AWS_ACCOUNT_ID:'170126527713',GRADE_READER_FUNCTION_ARN:'arn:aws:lambda:us-east-1:170126527713:function:reader'},
    {send:async()=>({StatusCode:200,Payload:Buffer.from(JSON.stringify({status:'ok',teacher:progress}))})});
  for(const task_id of tasks)assert.equal((await client({subject:claims.sub,email:claims.email,operation:'teacher_detail',lab_id:'course-student',task_id})).status,'ok');
  for(const task_id of ['P3','M3','M99'])await assert.rejects(()=>client({subject:claims.sub,email:claims.email,operation:'teacher_detail',lab_id:'course-student',task_id}));
});

test('teacher overview displays the saved P2 and M2 scores in every language',async()=>{
  const dnsGrade={...grade,current:{...grade.current,P2:{raw_earned:12,raw_maximum:13}},
    selected:{...grade.selected,M2:{raw_earned:11}},raw_earned:57};
  const instance=app(async()=>({status:'ok',teacher:{...progress,students:[{...progress.students[0],grade:dnsGrade}]}}));
  for(const lang of ['ja','ru','uz']) {
    const response=await instance(req(`/teacher?lang=${lang}`));
    const html=await response.text();
    assert.equal(response.status,200);
    assert.match(html,/task_id=P2[\s\S]*?>12 \/ 13<\/a>/);
    assert.match(html,/task_id=M2[\s\S]*?>11 \/ 13<\/a>/);
    assert.equal(CHECK_MAXIMA.P2,13);assert.equal(CHECK_MAXIMA.M2,13);
  }
});

test('teacher overview and student detail count P1 in the 21/123 course total',async()=>{
  const counted={P0:{raw_earned:1},M0:{raw_earned:4},P1:{raw_earned:8},M1:{raw_earned:8}};
  const currentGrade={...grade,raw_earned:21,raw_maximum:123,selected:counted,current:counted};
  const currentProgress={...progress,students:[{...progress.students[0],grade:currentGrade}]};
  const instance=app(async e=>({status:'ok',teacher:e.operation==='teacher_detail'
    ?{classroom:true,student:currentProgress.students[0]}:currentProgress}));
  for(const lang of ['ja','ru','uz']) {
    const list=await instance(req(`/teacher?lang=${lang}`));
    assert.equal(list.status,200);assert.match(await list.text(),/21 \/ 123/);
    const detail=await instance(req(`/teacher/student?lang=${lang}&lab_id=course-student&task_id=P1`));
    assert.equal(detail.status,200);assert.match(await detail.text(),/<strong>8 \/ 8<\/strong>/);
  }
});
