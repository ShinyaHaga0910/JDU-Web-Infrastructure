import test from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from './router.mjs';
import { preparationToken, checkedPreparation } from './preparation.mjs';

const deployment='f30a05e6-8356-4a65-8765-e5f4f031525b';
const sid='a'.repeat(64),rid='b'.repeat(64),token='synthetic-token-only';
const env={PORTAL_MODE:'enabled',PUBLIC_ORIGIN:'https://portal.example',GOOGLE_CLIENT_ID:'1234-example.apps.googleusercontent.com',
  GOOGLE_CLIENT_SECRET:'synthetic-secret-only',PORTAL_PREPARATION_ENABLED:'true',PORTAL_AWS_ACCOUNT_ID:'111111111111',
  PORTAL_PREPARATION_TEMPLATE_URL:`https://jdu-web-portal-bootstrap-111111111111-${'d'.repeat(12)}.s3.us-east-1.amazonaws.com/bootstrap/${'d'.repeat(64)}/account-link.template.json?versionId=v1`};
const config={origin:env.PUBLIC_ORIGIN,secret:env.GOOGLE_CLIENT_SECRET};
const cookie=`__Host-jdu-access=${sid}; __Host-jdu-session=${token}`;
const identity={sub:'12345678',email:'synthetic@jdu.uz',email_verified:true,hd:'jdu.uz'};
const sessions={check:async id=>id===sid};
const verify=async value=>{if(value!==token)throw Error();return identity;};
const approved={stage:'APPROVED',account:'123456789012',lab_id:'new-student',deployment_id:deployment,
  release_id:'synthetic-release',deadline:Math.floor(Date.now()/1000)+3600,can_continue:true,resources_created:false};
const plan={stage:'PLAN_READY',account:approved.account,lab_id:approved.lab_id,deployment_id:deployment,
  plan_digest:'e'.repeat(64),root_gib:96,new_nodes:5,availability_zone:'us-east-1a',compute_hourly_usd:'0.099',
  instance_types:{Bastion:'t3a.medium',Web:'t3a.small',Dns:'t3a.micro',Db:'t3a.small',Package:'t3a.small'}};
const request=(path='/prepare',options={})=>new Request(env.PUBLIC_ORIGIN+path,options);
const post=(operation,extra={},headers={})=>{
  const context={operation,requestId:rid,deploymentId:deployment,planDigest:operation==='create'?plan.plan_digest:''};
  return {method:'POST',headers:{cookie,origin:env.PUBLIC_ORIGIN,'content-type':'application/x-www-form-urlencoded',...headers},
    body:new URLSearchParams({operation,request_id:rid,deployment_id:deployment,confirmed:'yes',
      csrf:preparationToken(config,sid,token,context),...extra})};
};

test('preparation GET is approved-scope display only and closed by default',async()=>{
  const calls=[];
  const enroll=async e=>{calls.push(e);return {status:'ok',preparation:approved};};
  const app=createApp({env,verify,sessions,enroll});
  const result=await app(request('/prepare?lang=ja',{headers:{cookie}}));
  assert.equal(result.status,200);
  assert.deepEqual(calls.map(e=>e.operation),['prepare_status']);
  const html=await result.text();
  assert.match(html,/自分でサーバーへ入って/);assert.match(html,/name="confirmed"/);
  assert.doesNotMatch(html,/type="password"|synthetic@|synthetic-token/);
  assert.equal(result.headers.get('referrer-policy'),'same-origin');
  const closed=createApp({env:{...env,PORTAL_PREPARATION_ENABLED:'false'},verify,sessions,enroll});
  assert.equal((await closed(request('/prepare',{headers:{cookie}}))).status,404);
});

test('begin redirects to a resumable GET with one approved AWS helper link',async()=>{
  let value=approved;const calls=[];
  const app=createApp({env,verify,sessions,enroll:async e=>{
    calls.push(e);
    if(e.operation==='prepare_begin')value={...approved,pair_id:'f'.repeat(64),expires_at:Math.floor(Date.now()/1000)+300};
    return {status:'ok',preparation:value};
  }});
  const result=await app(request('/prepare?lang=ru',post('begin')));
  assert.equal(result.status,303);assert.equal(result.headers.get('location'),'/prepare?lang=ru');
  const observed=await app(request('/prepare?lang=ru',{headers:{cookie}}));
  const html=await observed.text();
  assert.match(html,/param_PairId=ffffffff/);assert.match(html,/target="_blank" rel="noopener noreferrer"/);
  assert.deepEqual(calls.map(e=>e.operation),['prepare_status','prepare_begin','prepare_status']);
  assert.doesNotMatch(html,/X-Amz-|aws_access_key|synthetic-token/);
});

test('explicit plan and create use only server identity; password POST redirects without echo',async()=>{
  let value={...approved,stage:'AWS_CONFIRMED'};const calls=[];
  const app=createApp({env,verify,sessions,enroll:async e=>{
    calls.push(e);
    if(e.operation==='prepare_plan')value={...approved,stage:'CREATE_REQUESTED',initial:plan};
    if(e.operation==='prepare_create')value={...approved,stage:'CREATE_REQUESTED',resources_created:null,initial:{stage:'CREATE_REQUESTED'}};
    return {status:'ok',preparation:value};
  }});
  assert.equal((await app(request('/prepare',post('plan')))).status,303);
  let html=await (await app(request('/prepare?lang=uz',{headers:{cookie}}))).text();
  assert.match(html,/96 GiB/);assert.match(html,/0\.099/);
  assert.match(html,/type="password" autocomplete="new-password" minlength="12" maxlength="128" required/);
  const password='DisposableFixtureOnly23';
  const response=await app(request('/prepare',post('create',{plan_digest:plan.plan_digest,password,confirmation:password})));
  assert.equal(response.status,303);assert.doesNotMatch(await response.text(),/Disposable/);
  const sent=calls.find(e=>e.operation==='prepare_create');
  assert.equal(sent.subject,identity.sub);assert.equal(sent.password,password);
  assert.equal(sent.plan_digest,plan.plan_digest);assert.equal(sent.email,identity.email);
  html=await (await app(request('/prepare',{headers:{cookie}}))).text();
  assert.doesNotMatch(html,/Disposable|type="password"/);
  assert.equal(calls.filter(e=>e.operation==='prepare_create').length,1);
});

test('different action, plan, identity, duplicate fields and origin cannot reuse a form',async()=>{
  const calls=[];
  const app=createApp({env,verify,sessions,enroll:async e=>{calls.push(e);return {status:'ok',preparation:{...approved,stage:'CREATE_REQUESTED',initial:plan}};}});
  const original=post('begin');
  const cross=new URLSearchParams(original.body);cross.set('operation','plan');
  const duplicates=post('plan');duplicates.body.append('confirmed','yes');
  for(const options of [post('plan',{subject:'9999'}),post('plan',{confirmed:'no'}),post('plan',{deployment_id:'invalid'}),post('plan',{}, {origin:'https://evil.example'}),
      {...original,body:cross},duplicates,post('create',{plan_digest:'f'.repeat(64),password:'DisposableFixtureOnly23',confirmation:'DisposableFixtureOnly23'})]){
    assert.equal((await app(request('/prepare',options))).status,403);
  }
  assert.equal(calls.length,0);
  assert.equal((await app(request('/prepare?account=other',{headers:{cookie}}))).status,403);
  assert.equal((await app(request('/prepare'))).status,403);
  const badPassword=post('create',{plan_digest:plan.plan_digest,password:'DisposableFixtureOnly23',confirmation:'DifferentFixtureOnly23'});
  assert.equal((await app(request('/prepare',badPassword))).status,400);
  assert.equal(calls.length,0);
});

test('expired, unavailable, resource ceiling and running creation are not shown as ready',async()=>{
  const outcomes=[{...approved,can_continue:false},
    {...approved,stage:'CREATE_REQUESTED',initial:{stage:'RESOURCE_BUDGET'}},
    {...approved,stage:'CREATE_REQUESTED',initial:{stage:'STACK_OBSERVED',stack_status:'CREATE_IN_PROGRESS'}}];
  for(const lang of ['ja','ru','uz'])for(const value of outcomes){
    const app=createApp({env,verify,sessions,enroll:async()=>({status:'ok',preparation:value})});
    const result=await app(request(`/prepare?lang=${lang}`,{headers:{cookie}}));
    assert.equal(result.status,200);assert.doesNotMatch(await result.text(),/type="password"|lab_ready/);
  }
  const app=createApp({env,verify,sessions,enroll:async()=>({status:'unavailable',private:'private-error-canary'})});
  const result=await app(request('/prepare',{headers:{cookie}}));
  assert.equal(result.status,503);assert.doesNotMatch(await result.text(),/private-error-canary/);
});

test('setup GET only observes; explicit advance resumes the same deployment without a password',async()=>{
  let value={...approved,stage:'CREATE_REQUESTED',initial:{stage:'SETUP_PENDING',setup_phase:'ssh_verify',
    can_advance:true,lab_ready:false,ssh_completed_roles:2,available_after:Math.floor(Date.now()/1000)+60,setup_result:'pending'}};
  const calls=[];
  const app=createApp({env,verify,sessions,enroll:async e=>{
    calls.push(e);
    if(e.operation==='prepare_advance')value={...value,initial:{...value.initial,stage:'REGISTRATION_PENDING',
      setup_phase:'registration_pending',can_advance:false,ssh_completed_roles:4,foundation_ready:true}};
    return {status:'ok',preparation:value};
  }});
  for(const lang of ['ja','ru','uz']){
    const html=await (await app(request(`/prepare?lang=${lang}`,{headers:{cookie}}))).text();
    assert.match(html,/name="operation" value="advance"/);assert.match(html,/2 \/ 4/);
    assert.doesNotMatch(html,/type="password"|name="plan_digest"/);
  }
  assert.deepEqual(calls.map(e=>e.operation),['prepare_status','prepare_status','prepare_status']);
  const result=await app(request('/prepare',post('advance')));
  assert.equal(result.status,303);
  assert.deepEqual(calls.find(e=>e.operation==='prepare_advance'),{operation:'prepare_advance',
    subject:identity.sub,email:identity.email,session_id:sid,token_hash:await import('./enrollment-client.mjs').then(m=>m.tokenHash(token))});
  const html=await (await app(request('/prepare',{headers:{cookie}}))).text();
  assert.match(html,/採点登録はまだ完了していません/);assert.doesNotMatch(html,/name="operation" value="advance"/);
  assert.equal((await app(request('/prepare',post('advance')))).status,403);
  assert.equal(calls.filter(e=>e.operation==='prepare_advance').length,1);
});

test('busy and invalid setup states cannot display a new mutation button or a ready claim',async()=>{
  const value={...approved,stage:'CREATE_REQUESTED',initial:{stage:'SETUP_OBSERVATION_REQUIRED',setup_phase:'ssh_init',can_advance:false,lab_ready:false}};
  const calls=[];
  const app=createApp({env,verify,sessions,enroll:async e=>{calls.push(e);return {status:'ok',preparation:value};}});
  const html=await (await app(request('/prepare',{headers:{cookie}}))).text();
  assert.match(html,/前の処理の完了を確認/);assert.doesNotMatch(html,/name="operation" value="advance"/);
  assert.equal((await app(request('/prepare',post('advance')))).status,403);
  assert.deepEqual(calls.map(e=>e.operation),['prepare_status','prepare_status']);
  for(const change of [{setup_phase:'arbitrary'},{lab_ready:true},{ssh_completed_roles:5},{can_advance:'yes'},{available_after:-1}])
    assert.throws(()=>checkedPreparation({...value,initial:{...value.initial,...change}}));
});

test('lesson preparation uses an explicit advance and ready links never run checks automatically',async()=>{
  let value={...approved,stage:'CREATE_REQUESTED',registration_complete:true,initial:{stage:'TEACHING_ASSETS_PENDING',
    setup_phase:'teaching_assets_pending',can_advance:true,lab_ready:false,ssh_completed_roles:4,teaching_completed_roles:1}};
  const calls=[];
  const app=createApp({env,verify,sessions,enroll:async e=>{
    calls.push(e);
    if(e.operation==='prepare_advance')value={...value,initial:{stage:'INITIAL_READY',setup_phase:'initial_ready',
      can_advance:false,teaching_completed_roles:2,connectors_ready:true,lab_ready:true}};
    return {status:'ok',preparation:value};
  }});
  let html=await (await app(request('/prepare',{headers:{cookie}}))).text();
  assert.match(html,/教材配置済みサーバー: 1 \/ 2/);assert.match(html,/name="operation" value="advance"/);
  assert.deepEqual(calls.map(e=>e.operation),['prepare_status']);
  assert.equal((await app(request('/prepare',post('advance')))).status,303);
  for(const lang of ['ja','ru','uz']){
    html=await (await app(request(`/prepare?lang=${lang}`,{headers:{cookie}}))).text();
    for(const path of ['status','checks','grades'])assert.match(html,new RegExp(`href="/${path}\\?lang=${lang}"`));
    assert.doesNotMatch(html,/name="operation" value="advance"|type="password"|undefined/);
  }
  assert.equal(calls.filter(e=>e.operation==='prepare_advance').length,1);
  assert.equal(calls.filter(e=>!['prepare_status','prepare_advance'].includes(e.operation)).length,0);
});

test('initial readiness requires own registration, both lesson targets and connectors',()=>{
  const initial={stage:'INITIAL_READY',setup_phase:'initial_ready',lab_ready:true,connectors_ready:true,teaching_completed_roles:2,can_advance:false};
  const value={...approved,stage:'CREATE_REQUESTED',registration_complete:true,initial};
  assert.equal(checkedPreparation(value),value);
  for(const change of [{lab_ready:false},{connectors_ready:false},{teaching_completed_roles:1},{can_advance:true}])
    assert.throws(()=>checkedPreparation({...value,initial:{...initial,...change}}));
  assert.throws(()=>checkedPreparation({...value,registration_complete:false}));
});
