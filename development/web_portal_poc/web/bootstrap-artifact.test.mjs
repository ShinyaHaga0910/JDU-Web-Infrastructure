import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { Readable } from 'node:stream';
import { createBootstrapEnv } from './bootstrap-artifact.mjs';

const code=Buffer.from('{"synthetic":"public code only"}');
const digest=createHash('sha256').update(code).digest('hex');
const base={PORTAL_MODE:'enabled',PORTAL_ENROLLMENT_ENABLED:'true',PORTAL_AWS_ACCOUNT_ID:'111111111111',PORTAL_BOOTSTRAP_TEMPLATE_DIGEST:digest};
const output=(changes={})=>({ContentLength:code.length,VersionId:'v+1/=',Body:Readable.from([code]),...changes});

test('hash-verified code resolves one immutable same-owner version without credential URLs',async()=>{
  const calls=[];const client={send:async c=>{calls.push(c.input);return output();}};
  const read=createBootstrapEnv(base,client);
  const result=await read();await read();
  assert.equal(calls.length,1);
  assert.deepEqual(calls[0],{Bucket:`jdu-web-portal-bootstrap-111111111111-${digest.slice(0,12)}`,Key:`bootstrap/${digest}/account-link.template.json`,ExpectedBucketOwner:'111111111111'});
  const url=new URL(result.PORTAL_BOOTSTRAP_TEMPLATE_URL);
  assert.equal(url.searchParams.get('versionId'),'v+1/=');
  assert.deepEqual([...url.searchParams.keys()],['versionId']);
  assert.equal(result.PORTAL_BOOTSTRAP_TEMPLATE_DIGEST,digest);
  assert.equal(base.PORTAL_BOOTSTRAP_TEMPLATE_URL,undefined);
});

test('closed and disabled operation never accesses S3',async()=>{
  let calls=0;const client={send:async()=>{calls++;throw Error();}};
  for (const env of [{...base,PORTAL_MODE:'closed'},{...base,PORTAL_ENROLLMENT_ENABLED:'false'},{...base,PORTAL_BOOTSTRAP_TEMPLATE_DIGEST:'disabled'}]) {
    assert.equal((await createBootstrapEnv(env,client)()).PORTAL_BOOTSTRAP_TEMPLATE_URL,undefined);
  }
  assert.equal(calls,0);
});

test('wrong body, version, size or streamed overflow fails without upstream data disclosure',async()=>{
  for (const changes of [{VersionId:'null'},{ContentLength:51201},{Body:Readable.from([Buffer.from('different')])},
                        {Body:Readable.from([Buffer.alloc(30000),Buffer.alloc(30000)])},{ContentLength:code.length+1}]) {
    const read=createBootstrapEnv(base,{send:async()=>output(changes)});
    await assert.rejects(()=>read(),e=>e.message==='Registration configuration unavailable');
  }
  await assert.rejects(()=>createBootstrapEnv(base,{send:async()=>{throw Error('private-source-canary');}})(),e=>e.message==='Registration configuration unavailable');
});

test('concurrent requests share a read and failed refresh does not serve expired metadata',async()=>{
  let now=0,calls=0,fail=false;
  const client={send:async()=>{calls++;if(fail)throw Error();return output();}};
  const read=createBootstrapEnv(base,client,()=>now);
  const values=await Promise.all([read(),read(),read()]);
  assert.equal(calls,1);assert.equal(values.length,3);
  now=300001;fail=true;
  await assert.rejects(()=>read());assert.equal(calls,2);
});
