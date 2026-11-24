import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';

// Only a trusted deployment selects this ARN. Never read secrets from HTTP,
// mutate process.env, log upstream errors or fall back to plaintext variables.
export function createRuntimeEnv(env=process.env,
  client=new SecretsManagerClient({region:'us-east-1',maxAttempts:1}), clock=()=>Date.now()) {
  const base={...env};
  delete base.GOOGLE_CLIENT_ID;
  delete base.GOOGLE_CLIENT_SECRET;
  delete base.GOOGLE_TEST_CONFIG;
  let cached, expires=0, pending;
  return async () => {
    if (base.PORTAL_MODE!=='enabled') return {...base};
    if (cached && clock()<expires) return {...cached};
    if (!pending) pending=(async()=>{
      try {
        const account=base.PORTAL_AWS_ACCOUNT_ID || '', arn=base.PORTAL_GOOGLE_OAUTH_SECRET_ARN || '';
        if (!/^[0-9]{12}$/.test(account) ||
            !new RegExp('^arn:aws:secretsmanager:us-east-1:'+account+':secret:jdu/web-portal/[a-z0-9-]+/google-oauth-[A-Za-z0-9]{6}$').test(arn)) throw new Error();
        const origin=new URL(base.PUBLIC_ORIGIN);
        if (origin.protocol!=='https:' || origin.username || origin.password || origin.port || origin.pathname!=='/' || origin.search || origin.hash) throw new Error();
        const value=await client.send(new GetSecretValueCommand({SecretId:arn,VersionStage:'AWSCURRENT'}),
          {abortSignal:AbortSignal.timeout(5000)});
        if (value.ARN!==arn || typeof value.SecretString!=='string' || value.SecretString.length>4096) throw new Error();
        const secret=JSON.parse(value.SecretString);
        if (!secret || Array.isArray(secret) || Object.keys(secret).sort().join(',')!=='client_id,client_secret,redirect_uri,schema_version'
            || secret.schema_version!==1 || typeof secret.client_id!=='string'
            || !/^[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$/.test(secret.client_id)
            || typeof secret.client_secret!=='string' || !/^GOCSPX-[A-Za-z0-9_-]{16,256}$/.test(secret.client_secret)
            || secret.redirect_uri!==origin.origin+'/auth/callback') throw new Error();
        cached={...base,GOOGLE_CLIENT_ID:secret.client_id,GOOGLE_CLIENT_SECRET:secret.client_secret};
        const testArn=base.PORTAL_GOOGLE_TEST_SECRET_ARN || '';
        if (new RegExp('^arn:aws:secretsmanager:us-east-1:'+account+':secret:jdu/web-portal/[a-z0-9-]+/google-test-[A-Za-z0-9]{6}$').test(testArn)) {
          try {
            const test=await client.send(new GetSecretValueCommand({SecretId:testArn,VersionStage:'AWSCURRENT'}),
              {abortSignal:AbortSignal.timeout(5000)});
            if (test.ARN===testArn && typeof test.SecretString==='string' && test.SecretString.length<=4096)
              cached.GOOGLE_TEST_CONFIG=JSON.parse(test.SecretString);
          } catch {} // Failure closes the test route; Google sign-in remains available.
        }
        expires=clock()+300000;
        return cached;
      } catch { throw new Error('Login configuration unavailable'); }
    })().finally(()=>{pending=undefined;});
    return {...await pending};
  };
}
