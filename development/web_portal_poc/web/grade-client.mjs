import { LambdaClient, InvokeCommand } from '@aws-sdk/client-lambda';

// The ARN is fixed server-side; neither the browser nor an HTTP header selects
// a function, account, Lab or subject. Invocation permissions must be scoped
// by the operator before any public deployment.
function createClient(operation, env=process.env, client=new LambdaClient({region:'us-east-1'})) {
  const arn=env.GRADE_READER_FUNCTION_ARN || '';
  if (!/^arn:aws:lambda:us-east-1:[0-9]{12}:function:[A-Za-z0-9_-]+(?::[A-Za-z0-9_-]+)?$/.test(arn)) throw new Error('Invalid grade service');
  return async (subject,task) => {
    if (typeof subject !== 'string' || !/^[0-9]{1,128}$/.test(subject)) throw new Error('Invalid identity');
    if (task!==undefined && (operation!=='grade' || !/^[PM][012456]$/.test(task))) throw new Error('Invalid task');
    const payload=Buffer.from(JSON.stringify(operation === 'status' ? {subject,operation} : {subject,...(task?{task_id:task}:{})}));
    const result=await client.send(new InvokeCommand({FunctionName:arn,InvocationType:'RequestResponse',Payload:payload}),
                                   {abortSignal:AbortSignal.timeout(operation==='status' ? 38000 : 10000)});
    if (result.FunctionError || result.StatusCode !== 200 || !result.Payload || result.Payload.length > 65536) throw new Error('Grade unavailable');
    const data=JSON.parse(Buffer.from(result.Payload).toString('utf8'));
    if (!data || !['ok','unauthorized','unavailable'].includes(data.status)) throw new Error('Grade unavailable');
    return data;
  };
}

export function createGradeClient(env=process.env, client) { return createClient('grade',env,client); }
export function createStatusClient(env=process.env, client) { return createClient('status',env,client); }
