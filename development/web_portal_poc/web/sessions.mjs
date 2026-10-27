import { createHash, randomBytes, timingSafeEqual } from 'node:crypto';
import { DynamoDBClient, GetItemCommand, PutItemCommand, UpdateItemCommand } from '@aws-sdk/client-dynamodb';

export const ACCESS = '__Host-jdu-access';
const digest=value=>createHash('sha256').update(value,'utf8').digest('hex');
const validId=id=>typeof id==='string' && /^[a-f0-9]{64}$/.test(id);
const key=id=>({pk:{S:'SESSION#'+digest(id)},sk:{S:'PORTAL'}});
const tokenHash=token=>typeof token==='string' && token.length>0 && token.length<=3500 ? digest(token) : null;

// Only opaque session/token hashes are stored; neither Google ID nor email is
// persisted. TTL is a cleanup aid: every read checks expiry independently.
export function createSessions(env=process.env,client=new DynamoDBClient({region:'us-east-1'}),clock=()=>Date.now()) {
  const table=env.PORTAL_BINDING_TABLE || '';
  if (!/^[a-zA-Z0-9_.-]{3,255}$/.test(table)) throw new Error('Invalid session table');
  return {
    async issue(token, googleExpires) {
      const hash=tokenHash(token), now=Math.floor(clock()/1000);
      if (!hash || !Number.isSafeInteger(googleExpires)) throw new Error('Invalid session');
      const ttl=Math.min(600,googleExpires-now);
      if (ttl<=0) throw new Error('Expired session');
      const id=randomBytes(32).toString('hex');
      await client.send(new PutItemCommand({TableName:table,Item:{...key(id),token_hash:{S:hash},
        expires_at:{N:String(now+ttl)},active:{BOOL:true}},ConditionExpression:'attribute_not_exists(pk)'}));
      return {id,ttl};
    },
    async check(id,token) {
      const hash=tokenHash(token);
      if (!validId(id) || !hash) return false;
      const answer=await client.send(new GetItemCommand({TableName:table,Key:key(id),ConsistentRead:true}));
      const row=answer.Item, stored=row?.token_hash?.S;
      if (row?.active?.BOOL!==true || !stored || !/^[a-f0-9]{64}$/.test(stored)
          || !/^[0-9]{1,12}$/.test(row?.expires_at?.N||'') || Number(row.expires_at.N)<=Math.floor(clock()/1000)) return false;
      return timingSafeEqual(Buffer.from(stored,'hex'),Buffer.from(hash,'hex'));
    },
    async revoke(id) {
      if (!validId(id)) return;
      try {
        await client.send(new UpdateItemCommand({TableName:table,Key:key(id),UpdateExpression:'SET #active=:no',
          ConditionExpression:'attribute_exists(pk)',ExpressionAttributeNames:{'#active':'active'},
          ExpressionAttributeValues:{':no':{BOOL:false}}}));
      } catch (e) { if (e?.name!=='ConditionalCheckFailedException') throw e; }
    },
  };
}
