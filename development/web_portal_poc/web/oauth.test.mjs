import test from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPair, exportJWK, createLocalJWKSet, SignJWT } from 'jose';
import { configFrom, login, readFlow, verifyGoogle, callback, FLOW, SESSION } from './auth.mjs';

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
