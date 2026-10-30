import { createHash, createHmac, randomBytes, timingSafeEqual } from 'node:crypto';
import { LambdaClient, InvokeCommand } from '@aws-sdk/client-lambda';

const hex=value=>typeof value==='string' && /^[a-f0-9]{64}$/.test(value);
export const operationId=()=>randomBytes(32).toString('hex');
export const tokenHash=token=>createHash('sha256').update(token,'utf8').digest('hex');

// Domain-separated, bound to this session, token and one explicit form action.
// Never put the session ID, Google token or CSRF value into a URL.
export function formToken(config,session,token,requestId) {
  if (!hex(session) || !hex(requestId) || typeof token!=='string') throw Error('Invalid form');
  return createHmac('sha256',config.secret).update(JSON.stringify(['jdu-portal/enroll/v1',config.origin,session,tokenHash(token),requestId])).digest('hex');
}
export function checkForm(config,session,token,requestId,supplied) {
  return hex(supplied) && timingSafeEqual(Buffer.from(formToken(config,session,token,requestId),'hex'),Buffer.from(supplied,'hex'));
}

// Only the server selects this fixed same-account private Lambda. Trusted
// verified Google claims are supplied by router.mjs, never copied from a form.
export function createEnrollmentClient(env=process.env,client=new LambdaClient({region:'us-east-1'})) {
  const account=env.PORTAL_AWS_ACCOUNT_ID, arn=env.PORTAL_ENROLLMENT_FUNCTION_ARN;
  if (!/^[0-9]{12}$/.test(account||'') || typeof arn!=='string'
      || !new RegExp(`^arn:aws:lambda:us-east-1:${account}:function:[A-Za-z0-9_-]+$`).test(arn)) throw Error('Invalid registration service');
  return async event=>{
    if (!event || !['begin','status','complete','prepare_begin','prepare_status','prepare_complete','prepare_confirm','prepare_plan','prepare_create','prepare_advance','prepare_registration_context','prepare_register'].includes(event.operation)) throw Error('Invalid registration');
    const payload=Buffer.from(JSON.stringify(event));
    if (payload.length>16384) throw Error('Invalid registration');
    const result=await client.send(new InvokeCommand({FunctionName:arn,InvocationType:'RequestResponse',Payload:payload}),
                                  {abortSignal:AbortSignal.timeout(['prepare_plan','prepare_create','prepare_advance','prepare_registration_context','prepare_register'].includes(event.operation)?100000:18000)});
    if (result.FunctionError || result.StatusCode!==200 || !result.Payload || result.Payload.length>4096) throw Error('Registration unavailable');
    const value=JSON.parse(Buffer.from(result.Payload).toString('utf8'));
    if (!value || !['ok','unauthorized','unavailable'].includes(value.status)) throw Error('Registration unavailable');
    return value;
  };
}
