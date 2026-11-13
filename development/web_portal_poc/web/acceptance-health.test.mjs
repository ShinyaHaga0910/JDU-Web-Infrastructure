import test from 'node:test';
import assert from 'node:assert/strict';
import {createAcceptanceHealth} from './acceptance-health.mjs';
import {createApp} from './router.mjs';

const env={PORTAL_MODE:'closed',PORTAL_ACCEPTANCE_ENABLED:'true',PORTAL_ACCEPTANCE_GRADE_TABLE:'test-grades',
  PORTAL_ACCEPTANCE_LAB_ID:'test-lab',PORTAL_ACCEPTANCE_DEPLOYMENT_ID:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  PORTAL_ACCEPTANCE_PROBE_ARN:'arn:aws:lambda:us-east-1:123456789012:function:test-private-probe'};
function fixture() {
  const queries=[], invokes=[];
  const db={send:async command=>{queries.push(command.input);return command.constructor.name==='GetItemCommand'
    ? {Item:{lab_id:{S:'test-lab'},deployment_id:{S:env.PORTAL_ACCEPTANCE_DEPLOYMENT_ID},active:{BOOL:true}}} : {Count:1};}};
  const lam={send:async command=>{invokes.push(command.input);return {StatusCode:200,Payload:Buffer.from(JSON.stringify({status:'ok',
    grade:{lab_id:'test-lab',raw_earned:59,raw_maximum:59,privateDetail:'must not be returned'}}))};}};
  return {db,lam,queries,invokes};
}

test('acceptance health is disabled by default and in student operation mode',()=>{
  const f=fixture();
  assert.equal(createAcceptanceHealth({},f.db,f.lam),undefined);
  assert.equal(createAcceptanceHealth({...env,PORTAL_MODE:'enabled'},f.db,f.lam),undefined);
  assert.equal(createAcceptanceHealth({...env,PORTAL_ACCEPTANCE_ENABLED:'false'},f.db,f.lam),undefined);
  assert.equal(f.queries.length+f.invokes.length,0);
});

test('closed acceptance reads only fixed metadata and grade availability; never exposes a score',async()=>{
  const f=fixture(); const health=createAcceptanceHealth(env,f.db,f.lam,()=>100000);
  const result=await health();
  assert.deepEqual(result,{storage:true,savedGrades:true,gradeService:true,checkedAt:new Date(100000).toISOString()});
  assert.equal(f.queries[0].TableName,'test-grades');
  assert.deepEqual(f.queries[0].Key,{pk:{S:'LAB#test-lab'},sk:{S:'META'}});
  assert.doesNotMatch(f.queries[0].ProjectionExpression,/token|password/);
  assert.equal(f.queries[1].Select,'COUNT'); assert.equal(f.queries[1].Limit,1);
  assert.equal(f.invokes[0].FunctionName,env.PORTAL_ACCEPTANCE_PROBE_ARN);
  assert.deepEqual(JSON.parse(f.invokes[0].Payload.toString()),{operation:'grade'});
  assert.doesNotMatch(JSON.stringify(result),/59|privateDetail|test-lab/);
});

test('concurrent health requests coalesce and new checks have an explicit timestamp',async()=>{
  const f=fixture(); let now=100000;
  const health=createAcceptanceHealth(env,f.db,f.lam,()=>now);
  const [a,b]=await Promise.all([health(),health()]); assert.deepEqual(a,b); assert.equal(f.invokes.length,1);
  now+=10000; assert.deepEqual(await health(),a); assert.equal(f.invokes.length,1);
  now+=21000; const fresh=await health(); assert.notEqual(fresh.checkedAt,a.checkedAt); assert.equal(f.invokes.length,2);
});

test('storage or Lambda failure is availability loss, not a grade or exception disclosure',async()=>{
  const f=fixture(); f.db.send=async()=>{throw Error('private storage details');}; f.lam.send=async()=>{throw Error('private Lambda details');};
  const result=await createAcceptanceHealth(env,f.db,f.lam)();
  assert.equal(result.storage,false);assert.equal(result.savedGrades,false);assert.equal(result.gradeService,false);
  assert.doesNotMatch(JSON.stringify(result),/private|score|raw_earned/);
});

test('public acceptance route strips all upstream fields and ignores user targets',async()=>{
  let calls=0;
  const app=createApp({env,getAcceptanceHealth:async()=>{calls++;return {storage:true,savedGrades:true,gradeService:true,
    checkedAt:'2026-10-29T00:00:00Z',token:'secret',grade:59};}});
  const response=await app(new Request('https://portal.example/healthz/acceptance?lab_id=another'));
  assert.equal(response.status,200); assert.equal(calls,1);
  assert.deepEqual(await response.json(),{storage:true,savedGrades:true,gradeService:true,checkedAt:'2026-10-29T00:00:00.000Z'});
  assert.match(response.headers.get('cache-control'),/no-store/);
  assert.equal((await app(new Request('https://portal.example/grades'))).status,503);
});

test('student operation mode and disabled acceptance never expose this endpoint',async()=>{
  for(const settings of [{...env,PORTAL_MODE:'enabled'},{...env,PORTAL_ACCEPTANCE_ENABLED:'false'}]) {
    let calls=0; const app=createApp({env:settings,getAcceptanceHealth:async()=>{calls++;}});
    assert.equal((await app(new Request('https://portal.example/healthz/acceptance'))).status,404); assert.equal(calls,0);
  }
});
