import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {mkdtempSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash,privateDecrypt,constants} from 'node:crypto';
import {createInitialDelivery} from './initial-delivery.mjs';
import {createApp} from './router.mjs';
import {preparationToken} from './preparation.mjs';

const deployment='05342512-1a55-4e11-b2d3-cd450487a138';
const directory=mkdtempSync(join(tmpdir(),'jdu-delivery-test-'));
const openssl=process.env.OPENSSL_TEST_COMMAND||(process.platform==='win32'?'C:/Program Files/Git/usr/bin/openssl.exe':'openssl');
let cert,key;
try{
  execFileSync(openssl,['req','-x509','-newkey','rsa:3072','-noenc','-batch','-days','1','-subj',`/CN=jdu-web-envelope-${deployment}`,
    '-keyout',join(directory,'key'),'-out',join(directory,'cert')],{stdio:'pipe'});
  cert=readFileSync(join(directory,'cert'),'utf8');key=readFileSync(join(directory,'key'));
}finally{rmSync(directory,{recursive:true,force:true});}
const recipient={account:'123456789012',lab_id:'synthetic-student',release_id:'web-2026-10-r1',deployment_id:deployment,
  instance_id:'i-'+'a'.repeat(17),certificate_pem:cert,certificate_sha256:createHash('sha256').update(cert).digest('hex')};
const sid='a'.repeat(64),rid='b'.repeat(64),token='synthetic-google-token-only';
const env={PORTAL_MODE:'enabled',PUBLIC_ORIGIN:'https://portal.example',GOOGLE_CLIENT_ID:'1234-example.apps.googleusercontent.com',
  GOOGLE_CLIENT_SECRET:'synthetic-secret-only',PORTAL_PREPARATION_ENABLED:'true',PORTAL_AWS_ACCOUNT_ID:'111111111111'};
const cookie=`__Host-jdu-access=${sid}; __Host-jdu-session=${token}`;
const identity={sub:'12345678',email:'synthetic@jdu.uz',email_verified:true,hd:'jdu.uz'};
const base={stage:'CREATE_REQUESTED',account:recipient.account,lab_id:recipient.lab_id,deployment_id:deployment,
  deadline:Math.floor(Date.now()/1000)+3600,can_continue:true,registration_complete:false,
  initial:{stage:'REGISTRATION_PENDING',setup_phase:'registration_pending',can_advance:false,lab_ready:false,ssh_completed_roles:4}};
const request=(method='GET',extra={})=>new Request(env.PUBLIC_ORIGIN+'/prepare?lang=ja',{method,
  headers:{cookie,...(method==='POST'?{origin:env.PUBLIC_ORIGIN,'content-type':'application/x-www-form-urlencoded'}:{})},
  ...(method==='POST'?{body:new URLSearchParams({operation:'register',request_id:rid,deployment_id:deployment,confirmed:'yes',
    csrf:preparationToken({origin:env.PUBLIC_ORIGIN,secret:env.GOOGLE_CLIENT_SECRET},sid,token,
      {operation:'register',requestId:rid,deploymentId:deployment}),...extra})}:{})});
const appFor=enroll=>createApp({env,enroll,sessions:{check:async()=>true},verify:async()=>identity});

test('standard RSA-OAEP packet binds deployment and never returns the raw credential',()=>{
  const delivery=createInitialDelivery(recipient);
  const plain=privateDecrypt({key,padding:constants.RSA_PKCS1_OAEP_PADDING,oaepHash:'sha256'},Buffer.from(delivery.ciphertext_b64,'base64'));
  const tuple=JSON.parse(plain);
  assert.deepEqual(tuple.slice(0,5),['jdu-progress-oaep-v1',recipient.lab_id,recipient.release_id,deployment,recipient.instance_id]);
  assert.equal(tuple[5].length,43);assert.equal(createHash('sha256').update(tuple[5]).digest('hex'),delivery.token_hash);
  assert.doesNotMatch(JSON.stringify(delivery),new RegExp(tuple[5]));
  assert.throws(()=>createInitialDelivery({...recipient,certificate_sha256:'0'.repeat(64)}));
  assert.throws(()=>createInitialDelivery({...recipient,deployment_id:'f30a05e6-8356-4a65-8765-e5f4f031525b'}));
  assert.throws(()=>createInitialDelivery(recipient,{now:Date.now()+86400000*2}));
});

test('registration GET only observes and POST encrypts server-side before same-page redirect',async()=>{
  const calls=[];let state=base;
  const app=appFor(async e=>{
    calls.push(e);
    if(e.operation==='prepare_status')return {status:'ok',preparation:state};
    if(e.operation==='prepare_registration_context')return {status:'ok',preparation:{issued:false,recipient}};
    assert.equal(e.operation,'prepare_register');assert.equal(e.subject,identity.sub);
    assert.equal(e.email,identity.email);assert.equal(e.delivery.ciphertext_b64.length,512);
    assert.equal(e.delivery.lab_token,undefined);
    state={...base,registration_complete:true,initial:{...base.initial,stage:'TEACHING_ASSETS_PENDING',setup_phase:'teaching_assets_pending'}};
    return {status:'ok',preparation:{registered:true,lab_id:base.lab_id}};
  });
  let response=await app(request());let html=await response.text();
  assert.match(html,/自分の環境を採点に登録する/);assert.doesNotMatch(html,/BEGIN CERTIFICATE|ciphertext_b64|type="password"/);
  assert.deepEqual(calls.map(e=>e.operation),['prepare_status']);
  response=await app(request('POST'));assert.equal(response.status,303);
  html=await (await app(request())).text();
  assert.match(html,/採点登録が完了しました/);assert.match(html,/教材資源と課題確認の接続は準備中/);
  assert.doesNotMatch(html,/name="operation" value="register"|ciphertext_b64|BEGIN CERTIFICATE|undefined/);
  assert.deepEqual(calls.map(e=>e.operation),['prepare_status','prepare_status','prepare_registration_context','prepare_register','prepare_status']);
});

test('issued registration resumes without minting another delivery and completed POST only redirects',async()=>{
  const calls=[];let complete=false;
  const app=appFor(async e=>{
    calls.push(e);
    if(e.operation==='prepare_status')return {status:'ok',preparation:{...base,registration_complete:complete}};
    if(e.operation==='prepare_registration_context')return {status:'ok',preparation:{issued:true,registered:false}};
    assert.equal(e.operation,'prepare_register');assert.equal(e.delivery,null);complete=true;
    return {status:'ok',preparation:{registered:true}};
  });
  assert.equal((await app(request('POST'))).status,303);
  assert.equal((await app(request('POST'))).status,303);
  assert.equal(calls.filter(e=>e.operation==='prepare_register').length,1);
  assert.equal(calls.filter(e=>e.operation==='prepare_registration_context').length,1);
});

test('caller delivery fields and another recipient cannot reach registration',async()=>{
  const calls=[];
  const app=appFor(async e=>{calls.push(e);return e.operation==='prepare_status'?{status:'ok',preparation:base}
    :{status:'ok',preparation:{issued:false,recipient:{...recipient,account:'999999999999'}}};});
  assert.equal((await app(request('POST',{delivery:'arbitrary'}))).status,403);assert.equal(calls.length,0);
  assert.equal((await app(request('POST'))).status,403);
  assert.equal(calls.filter(e=>e.operation==='prepare_register').length,0);
});
