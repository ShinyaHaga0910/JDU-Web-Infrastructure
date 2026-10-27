import test from 'node:test';
import assert from 'node:assert/strict';
import { PutItemCommand, GetItemCommand, UpdateItemCommand } from '@aws-sdk/client-dynamodb';
import { createSessions } from './sessions.mjs';

class FakeDynamo {
  rows=new Map();
  async send(command) {
    const a=command.input, id=a.Item?.pk.S || a.Key?.pk.S;
    if (command instanceof PutItemCommand) {if(this.rows.has(id))throw Error('collision');this.rows.set(id,structuredClone(a.Item));return {};}
    if (command instanceof GetItemCommand) return {Item:structuredClone(this.rows.get(id))};
    if (command instanceof UpdateItemCommand) {const r=this.rows.get(id); if(!r){const e=Error('missing');e.name='ConditionalCheckFailedException';throw e;} r.active.BOOL=false;return {};}
    throw Error('unexpected command');
  }
}

test('session stores only hashes, expires, rejects other tokens and can be revoked',async()=>{
  let now=1000000; const db=new FakeDynamo(), s=createSessions({PORTAL_BINDING_TABLE:'binding-table'},db,()=>now);
  const issued=await s.issue('synthetic-google-token',1000+3600);
  assert.equal(issued.ttl,600); assert.match(issued.id,/^[a-f0-9]{64}$/);
  const stored=JSON.stringify([...db.rows.values()]);
  assert.doesNotMatch(stored,/synthetic-google-token/); assert.doesNotMatch(stored,new RegExp(issued.id));
  assert.equal(await s.check(issued.id,'synthetic-google-token'),true);
  assert.equal(await s.check(issued.id,'different'),false);
  await s.revoke(issued.id);
  assert.equal(await s.check(issued.id,'synthetic-google-token'),false);
  const second=await s.issue('synthetic-google-token',1000+20); assert.equal(second.ttl,20);
  now+=21000;
  assert.equal(await s.check(second.id,'synthetic-google-token'),false);
});

test('invalid inputs and missing session fail closed before database access',async()=>{
  const db=new FakeDynamo(), s=createSessions({PORTAL_BINDING_TABLE:'binding-table'},db,()=>1000000);
  await assert.rejects(()=>s.issue('',2000));
  await assert.rejects(()=>s.issue('token',999));
  assert.equal(await s.check('invalid','token'),false);
  await s.revoke('invalid');
  assert.equal(db.rows.size,0);
  assert.throws(()=>createSessions({PORTAL_BINDING_TABLE:'../bad'},db));
});
