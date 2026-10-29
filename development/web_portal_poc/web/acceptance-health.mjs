import { DynamoDBClient, GetItemCommand, QueryCommand } from '@aws-sdk/client-dynamodb';
import { LambdaClient, InvokeCommand } from '@aws-sdk/client-lambda';

// Temporary closed-mode acceptance only. No HTTP input selects a Lab, table,
// function or identity. Public output contains availability booleans only.
export function createAcceptanceHealth(env=process.env,
  db=new DynamoDBClient({region:'us-east-1'}), lam=new LambdaClient({region:'us-east-1'}), clock=()=>Date.now()) {
  if (env.PORTAL_MODE!=='closed' || env.PORTAL_ACCEPTANCE_ENABLED!=='true') return undefined;
  const table=env.PORTAL_ACCEPTANCE_GRADE_TABLE || '', lab=env.PORTAL_ACCEPTANCE_LAB_ID || '';
  const deployment=env.PORTAL_ACCEPTANCE_DEPLOYMENT_ID || '', arn=env.PORTAL_ACCEPTANCE_PROBE_ARN || '';
  if (!/^[A-Za-z0-9_.-]{3,255}$/.test(table) || !/^[a-z0-9][a-z0-9-]{2,31}$/.test(lab)
      || !/^[a-f0-9-]{36}$/.test(deployment)
      || !/^arn:aws:lambda:us-east-1:[0-9]{12}:function:[A-Za-z0-9_-]+$/.test(arn)) throw new Error('Invalid acceptance configuration');
  let cached, expires=0, pending;
  async function observe() {
    let storage=false, savedGrades=false, gradeService=false;
    try {
      const item=await db.send(new GetItemCommand({TableName:table,Key:{pk:{S:'LAB#'+lab},sk:{S:'META'}},
        ProjectionExpression:'lab_id,deployment_id,#active',ExpressionAttributeNames:{'#active':'active'},ConsistentRead:true}),
        {abortSignal:AbortSignal.timeout(5000)});
      storage=item.Item?.lab_id?.S===lab && item.Item?.deployment_id?.S===deployment && item.Item?.active?.BOOL===true;
      if (storage) {
        const count=await db.send(new QueryCommand({TableName:table,KeyConditionExpression:'pk=:p AND begins_with(sk,:s)',
          ExpressionAttributeValues:{':p':{S:'LAB#'+lab},':s':{S:'GRADE#'}},Select:'COUNT',Limit:1,ConsistentRead:true}),
          {abortSignal:AbortSignal.timeout(5000)});
        savedGrades=Number.isInteger(count.Count) && count.Count>0;
      }
    } catch { /* No raw errors, metadata or credentials in HTTP or logs. */ }
    try {
      const result=await lam.send(new InvokeCommand({FunctionName:arn,Payload:Buffer.from('{"operation":"grade"}'),InvocationType:'RequestResponse'}),
        {abortSignal:AbortSignal.timeout(12000)});
      if (result.StatusCode===200 && !result.FunctionError && result.Payload?.length<=65536) {
        const value=JSON.parse(Buffer.from(result.Payload).toString('utf8'));
        gradeService=value.status==='ok' && value.grade?.lab_id===lab && value.grade?.raw_maximum===62
          && Number.isInteger(value.grade?.raw_earned) && value.grade.raw_earned>=0 && value.grade.raw_earned<=62;
      }
    } catch { /* Availability only; never return a score or upstream body. */ }
    return {storage,savedGrades,gradeService,checkedAt:new Date(clock()).toISOString()};
  }
  return async () => {
    if (cached && clock()<expires) return {...cached};
    // Coalesce requests; no personal information is retained in this cache.
    if (!pending) pending=observe().then(value=>{cached=value;expires=clock()+30000;return value;}).finally(()=>{pending=undefined;});
    return {...await pending};
  };
}
