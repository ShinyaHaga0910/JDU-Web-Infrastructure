import test from 'node:test';
import assert from 'node:assert/strict';
import { createRuntimeEnv } from './secrets.mjs';

const arn='arn:aws:secretsmanager:us-east-1:123456789012:secret:jdu/web-portal/class-test/google-oauth-abc123';
const env={PORTAL_MODE:'enabled',PUBLIC_ORIGIN:'https://portal.example',PORTAL_AWS_ACCOUNT_ID:'123456789012',PORTAL_GOOGLE_OAUTH_SECRET_ARN:arn};
const doc={schema_version:1,client_id:'123456789012-example.apps.googleusercontent.com',client_secret:'GOCSPX-'+'a'.repeat(32),redirect_uri:'https://portal.example/auth/callback'};
const response=()=>({ARN:arn,SecretString:JSON.stringify(doc)});

test('closed mode never loads credentials or accepts plaintext secret variables',async()=>{
  const get=createRuntimeEnv({...env,PORTAL_MODE:'closed',GOOGLE_CLIENT_SECRET:'plaintext',GOOGLE_CLIENT_ID:'plaintext'},
    {send:()=>assert.fail('closed deployment read a secret')});
  const result=await get();
  assert.equal(result.PORTAL_MODE,'closed');
  assert.equal(result.GOOGLE_CLIENT_SECRET,undefined);
  assert.equal(result.GOOGLE_CLIENT_ID,undefined);
});

test('one same-account secret is loaded and cached without modifying deployment variables',async()=>{
  let count=0, now=0;
  const original={...env};
  const get=createRuntimeEnv(original,{send:async command=>{
    count++; assert.deepEqual(command.input,{SecretId:arn,VersionStage:'AWSCURRENT'}); return response();
  }},()=>now);
  const first=await get();
  assert.equal(first.GOOGLE_CLIENT_SECRET,doc.client_secret);
  first.GOOGLE_CLIENT_SECRET='tampered';
  assert.equal((await get()).GOOGLE_CLIENT_SECRET,doc.client_secret);
  assert.equal(original.GOOGLE_CLIENT_SECRET,undefined);
  assert.equal(count,1);
  now=300001;
  await get();
  assert.equal(count,2);
});

test('concurrent reads share one pending request',async()=>{
  let count=0, resolve;
  const get=createRuntimeEnv(env,{send:()=>{count++; return new Promise(r=>resolve=r);}});
  const a=get(), b=get();
  resolve(response());
  await Promise.all([a,b]);
  assert.equal(count,1);
});

test('cross-account and arbitrary secret selections fail before any read',async()=>{
  for(const override of [{PORTAL_AWS_ACCOUNT_ID:'000000000000'},
    {PORTAL_GOOGLE_OAUTH_SECRET_ARN:arn.replace('/google-oauth-','/another-secret-')},
    {PUBLIC_ORIGIN:'http://portal.example'}, {PUBLIC_ORIGIN:'https://portal.example/?x=y'}]) {
    const get=createRuntimeEnv({...env,...override},{send:()=>assert.fail('invalid selection made a read')});
    await assert.rejects(get(),/^Error: Login configuration unavailable$/);
  }
});

test('wrong schema, origin or credential is rejected without error-body disclosure',async()=>{
  for(const value of [
    {ARN:arn,SecretString:'not-json'}, {...response(),ARN:arn+'other'},
    {ARN:arn,SecretString:JSON.stringify({...doc,redirect_uri:'https://other.example/auth/callback'})},
    {ARN:arn,SecretString:JSON.stringify({...doc,client_secret:'invalid'})},
    {ARN:arn,SecretString:JSON.stringify({...doc,extra:'unexpected'})}]) {
    await assert.rejects(createRuntimeEnv(env,{send:async()=>value})(),/^Error: Login configuration unavailable$/);
  }
});

test('failed refresh never serves expired credentials or includes upstream error data',async()=>{
  let now=0, count=0;
  const get=createRuntimeEnv(env,{send:async()=>{
    if(++count>1) throw new Error(doc.client_secret);
    return response();
  }},()=>now);
  await get(); now=300001;
  await assert.rejects(get(),/^Error: Login configuration unavailable$/);
});
