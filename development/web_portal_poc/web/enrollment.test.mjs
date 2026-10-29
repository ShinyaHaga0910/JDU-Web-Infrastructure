import test from 'node:test';
import assert from 'node:assert/strict';
import { Readable } from 'node:stream';
import { createApp } from './router.mjs';
import { formToken, createEnrollmentClient } from './enrollment-client.mjs';
import { readBody } from './request-body.mjs';

const env={PORTAL_MODE:'enabled',PUBLIC_ORIGIN:'https://portal.example',GOOGLE_CLIENT_ID:'1234-example.apps.googleusercontent.com',GOOGLE_CLIENT_SECRET:'synthetic-test-secret-only',PORTAL_ENROLLMENT_ENABLED:'true'};
const config={origin:env.PUBLIC_ORIGIN,secret:env.GOOGLE_CLIENT_SECRET};
const sid='a'.repeat(64), rid='b'.repeat(64), token='valid';
const cookie=`__Host-jdu-access=${sid}; __Host-jdu-session=${token}`;
const identity={sub:'12345678',email:'synthetic@jdu.uz',email_verified:true,hd:'jdu.uz'};
const verify=async t=>{if(t!==token)throw Error();return identity;};
const sessions={check:async id=>id===sid};
const granted={registered:false,account:'123456789012',lab_id:'synthetic-lab'};
const req=(path,options={})=>new Request(`${env.PUBLIC_ORIGIN}${path}`,options);
const form=extra=>new URLSearchParams({confirmed:'yes',request_id:rid,csrf:formToken(config,sid,token,rid),...extra});
const post=(body=form(),headers={})=>({method:'POST',headers:{cookie,origin:env.PUBLIC_ORIGIN,'content-type':'application/x-www-form-urlencoded',...headers},body});

test('registration GET displays only approved scope and never starts a pairing',async()=>{
  const calls=[];
  const app=createApp({env,verify,sessions,enroll:async e=>{calls.push(e);return {status:'ok',enrollment:granted};}});
  const result=await app(req('/enroll?lang=uz&account=other',{headers:{cookie}}));
  const html=await result.text();
  assert.equal(result.status,200);assert.equal(calls[0].operation,'status');
  assert.equal(calls[0].subject,identity.sub);assert.equal(calls[0].email,identity.email);
  assert.match(html,/123456789012/);assert.match(html,/method="post"/);assert.match(html,/required/);
  assert.doesNotMatch(html,/synthetic@|12345678<|account=other|__Host-jdu|valid/);
  assert.match(result.headers.get('cache-control'),/no-store/);
});

test('explicit same-origin form binds server-verified claims, no arbitrary target or raw token',async()=>{
  const calls=[];
  const app=createApp({env,verify,sessions,enroll:async e=>{calls.push(e);return {status:'ok',enrollment:{...granted,pair_id:'d'.repeat(64),expires_at:2000000000}};}});
  const response=await app(req('/enroll',post()));
  assert.equal(response.status,200);assert.equal(calls.length,1);assert.equal(calls[0].operation,'begin');
  assert.equal(calls[0].request_id,rid);assert.equal(calls[0].token_hash.length,64);assert.ok(!JSON.stringify(calls).includes('"valid"'));
  assert.doesNotMatch(await response.text(),new RegExp('d'.repeat(64))); // No nonce/credential in the page.
  assert.equal((await app(req('/enroll',post(form({account:'attacker'}))))).status,403);
  assert.equal((await app(req('/enroll',post(form({subject:'attacker'}))))).status,403);
  assert.equal(calls.length,1);
});

test('CSRF, consent, duplicate fields, session and identity substitutions fail before invocation',async()=>{
  let calls=0;
  const app=createApp({env,verify,sessions,enroll:async()=>{calls++;return {};}});
  const other=formToken(config,'c'.repeat(64),token,rid);
  for (const options of [post(form({csrf:other})),post(form({csrf:'bad'})),post(form({confirmed:'no'})),
                         post(form(),{origin:'https://evil.example'}),post(form()+'&request_id='+rid),
                         post(form(),{cookie:'__Host-jdu-session=valid'}),post(form(),{'content-type':'text/plain'})]) {
    assert.equal((await app(req('/enroll',options))).status,403);
  }
  const noMail=createApp({env,verify:async()=>({sub:identity.sub}),sessions,enroll:async()=>{calls++;}});
  assert.equal((await noMail(req('/enroll',{headers:{cookie}}))).status,403);
  assert.equal(calls,0);
});

test('registration is disabled by default; no anonymous browser identity enrollment',async()=>{
  let calls=0;
  const app=createApp({env:{...env,PORTAL_ENROLLMENT_ENABLED:'false'},verify,sessions,enroll:async()=>{calls++;}});
  assert.equal((await app(req('/enroll',{headers:{cookie}}))).status,404);
  assert.equal((await app(req('/api/enrollment/complete',{method:'POST'}))).status,404);
  const enabled=createApp({env,verify,sessions,enroll:async()=>{calls++;}});
  assert.equal((await enabled(req('/enroll'))).status,403);
  assert.equal(calls,0);
});

test('signed proof transport accepts only bounded exact JSON and returns a generic receipt',async()=>{
  const calls=[];
  const app=createApp({env,enroll:async e=>{calls.push(e);return {status:'ok',enrollment:{registered:true,lab_id:granted.lab_id}};}});
  const send=value=>req('/api/enrollment/complete',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(value)});
  const proof={pair_id:'d'.repeat(64),proof_url:'https://sts.us-east-1.amazonaws.com/?signed-proof'};
  const response=await app(send(proof));
  assert.equal(response.status,200);assert.deepEqual(await response.json(),{registered:true});
  assert.deepEqual(calls[0],{operation:'complete',...proof});
  assert.equal((await app(send({...proof,subject:'attacker'}))).status,403);
  assert.equal((await app(send({...proof,proof_url:'x'.repeat(8193)}))).status,403);
  assert.equal((await app(send({...proof,proof_url:'x'.repeat(17000)}))).status,413);
  assert.equal((await app(req('/api/enrollment/complete'))).status,405);
  assert.equal(calls.length,1);
});

test('fixed enrollment function is same-account and never selected by event',async()=>{
  const calls=[];
  const client={send:async command=>{calls.push(command.input);return {StatusCode:200,Payload:Buffer.from('{"status":"unauthorized"}')};}};
  const settings={PORTAL_AWS_ACCOUNT_ID:'123456789012',PORTAL_ENROLLMENT_FUNCTION_ARN:'arn:aws:lambda:us-east-1:123456789012:function:enrollment'};
  assert.throws(()=>createEnrollmentClient({...settings,PORTAL_AWS_ACCOUNT_ID:'987654321098'},client));
  const enroll=createEnrollmentClient(settings,client);
  assert.equal((await enroll({operation:'status'})).status,'unauthorized');
  assert.equal(calls[0].FunctionName,settings.PORTAL_ENROLLMENT_FUNCTION_ARN);
  await assert.rejects(()=>enroll({operation:'approve'}));
});

test('HTTP body reader bounds both declared and streamed content without destroying socket',async()=>{
  const stream=(chunks,length)=>{const r=Readable.from(chunks);r.method='POST';r.headers=length?{'content-length':length}:{};return r;};
  assert.equal((await readBody(stream([Buffer.from('hello')],'5'))).toString(),'hello');
  for (const r of [stream([Buffer.alloc(20000)],'20000'),stream([Buffer.alloc(8000),Buffer.alloc(9000)])]) {
    await assert.rejects(()=>readBody(r),e=>e.status===413);
    assert.equal(r.destroyed,false);
  }
});
