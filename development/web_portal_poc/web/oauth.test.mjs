import test from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPair, exportJWK, createLocalJWKSet, SignJWT } from 'jose';
import { configFrom, login, loginTarget, readFlow, verifyGoogle, googleTestConfig, verifyGoogleTest, callback, FLOW, SESSION } from './auth.mjs';

const env={PORTAL_MODE:'enabled',PUBLIC_ORIGIN:'https://portal.example',GOOGLE_CLIENT_ID:'1234-example.apps.googleusercontent.com',GOOGLE_CLIENT_SECRET:'example-test-secret-only'};
const config=configFrom(env), pair=await generateKeyPair('RS256'), jwk=await exportJWK(pair.publicKey);
const keys=createLocalJWKSet({keys:[{...jwk,kid:'test',alg:'RS256'}]});
const sign=claims=>new SignJWT({email:'student@jdu.uz',email_verified:true,hd:'jdu.uz',...claims})
  .setProtectedHeader({alg:'RS256',kid:'test'}).setIssuer('https://accounts.google.com')
  .setAudience(config.clientId).setSubject('1234567890').setIssuedAt().setExpirationTime('1h').sign(pair.privateKey);
const verify=(token,cfg,options={})=>verifyGoogle(token,cfg,{...options,keys});

test('signature, audience, expiry and verified organization are mandatory',async()=>{
  assert.equal((await verify(await sign(),config)).sub,'1234567890');
  for(const claims of [{email:'person@gmail.com'},{email:'person@eviljdu.uz'},{hd:'other.test'},
                       {hd:undefined},{email_verified:false},{azp:'different-client'}]) {
    await assert.rejects(()=>sign(claims).then(token=>verify(token,config)));
  }
  const token=await sign();
  await assert.rejects(()=>verify(token,{...config,clientId:'different'}));
  await assert.rejects(()=>verify(token.slice(0,-10)+'AAAAAAAAAA',config));
  const expired=await new SignJWT({email:'person@jdu.uz',email_verified:true,hd:'jdu.uz'})
    .setProtectedHeader({alg:'RS256',kid:'test'}).setIssuer('https://accounts.google.com')
    .setAudience(config.clientId).setSubject('123').setIssuedAt(1).setExpirationTime(2).sign(pair.privateKey);
  await assert.rejects(()=>verify(expired,config));
});

test('OAuth state, PKCE and nonce bind a callback to the browser flow',async()=>{
  const flow=await login(config), loc=new URL(flow.location), flowCookie=flow.flowCookie.split(';')[0];
  const payload=await readFlow(flowCookie.slice(FLOW.length+1),config);
  assert.equal(loc.searchParams.get('code_challenge_method'),'S256');
  assert.match(flow.flowCookie,/Secure; HttpOnly; SameSite=Lax/);
  let requests=0;
  const exchange=async(url,init)=>{requests++;assert.equal(url,'https://oauth2.googleapis.com/token');
    assert.equal(init.body.get('code_verifier'),payload.verifier);return Response.json({id_token:await sign({nonce:payload.nonce})});};
  const request=state=>new Request(`https://portal.example/auth/callback?code=fake&state=${state}`,{headers:{cookie:flowCookie}});
  await assert.rejects(()=>callback(request('wrong'),config,{exchange,verify}));
  assert.equal(requests,0);
  const good=await callback(request(payload.state),config,{exchange,verify});
  assert.ok(good.sessionCookie.startsWith(SESSION+'='));
  const wrongNonce=async()=>Response.json({id_token:await sign({nonce:'wrong'})});
  await assert.rejects(()=>callback(request(payload.state),config,{exchange:wrongNonce,verify}));
});


test('a same-portal task destination is sealed into OAuth and restored after login',async()=>{
  const target='/checks?lang=ru&task_id=M5&job_id=12345678-1234-4234-8234-123456789abc&check_mode=functional';
  const flow=await login(config,target), flowCookie=flow.flowCookie.split(';')[0];
  const payload=await readFlow(flowCookie.slice(FLOW.length+1),config);
  assert.equal(payload.returnTo,target);
  const request=new Request(`https://portal.example/auth/callback?code=fake&state=${payload.state}`,{headers:{cookie:flowCookie}});
  const result=await callback(request,config,{verify,exchange:async()=>Response.json({id_token:await sign({nonce:payload.nonce})})});
  assert.equal(result.returnTo,target);
});
test('login return links cannot leave the portal or run authentication or POST routes',async()=>{
  for(const target of ['https://evil.example','//evil.example','/\\evil.example','/auth/logout','/auth/callback?code=fake','/checks#fragment','/checks?password=private','/grades?lang=ja&lang=ru','/checks?lang='+'x'.repeat(1100)]){
    assert.throws(()=>loginTarget(target,config));await assert.rejects(()=>login(config,target));
  }
});

test('Google test sign-in accepts only the configured verified Gmail account',async()=>{
  const options={client_id:[4321,'test.apps.googleusercontent.com'].join('-'),email:'allowed.test@gmail.com',
    client_secret:['GOCSPX','synthetic-test-client-secret'].join('-'),lab_id:'lab-'+'a'.repeat(20),expires_at:Math.floor(Date.now()/1000)+600};
  const testConfig=googleTestConfig({GOOGLE_TEST_CONFIG:options},config);
  assert.equal(googleTestConfig({},config),null);
  assert.equal(googleTestConfig({GOOGLE_TEST_CONFIG:{...options,expires_at:1}},config),null);
  const flow=await login(testConfig,'/checks?lang=uz'), loc=new URL(flow.location), flowCookie=flow.flowCookie.split(';')[0];
  assert.equal(loc.origin,'https://accounts.google.com');
  assert.equal(loc.searchParams.get('redirect_uri'),'https://portal.example/auth/google-test/callback');
  assert.equal(loc.searchParams.has('hd'),false);
  await assert.rejects(()=>readFlow(flowCookie.slice(FLOW.length+1),config));
  const mint=({aud=testConfig.clientId,...claims}={})=>new SignJWT({
    email:options.email,email_verified:true,nonce:loc.searchParams.get('nonce'),...claims})
    .setProtectedHeader({alg:'RS256',kid:'test'}).setIssuer('https://accounts.google.com').setAudience(aud).setSubject('1234567890')
    .setIssuedAt().setExpirationTime('1h').sign(pair.privateKey);
  const check=(token,cfg,opts)=>verifyGoogleTest(token,cfg,{...opts,keys});
  const request=new Request('https://portal.example/auth/google-test/callback?code=fake&state='+loc.searchParams.get('state'),{headers:{cookie:flowCookie}});
  const result=await callback(request,testConfig,{verify:check,exchange:async(url,init)=>{
    assert.equal(url,'https://oauth2.googleapis.com/token');
    assert.ok(init.body.get('code_verifier'));
    return Response.json({id_token:await mint()});
  }});
  assert.equal(result.returnTo,'/checks?lang=uz');
  assert.deepEqual(await check(await mint(),testConfig),{sub:'201'+'1234567890'.padStart(39,'0'),
    email:options.email,exp:options.expires_at,testLab:options.lab_id});
  for(const claims of [{email:'other.test@gmail.com'},{email_verified:false},{aud:config.clientId}])
    await assert.rejects(async()=>check(await mint(claims),testConfig));
  await assert.rejects(async()=>check(await mint(),testConfig,{nonce:'wrong'}));
});
