// The template contains public code only. Read access is granted separately to
// the assigned AWS account. No presigned URL or credential enters browser URLs.
export function bootstrapTemplate(env) {
  const account=env.PORTAL_AWS_ACCOUNT_ID;
  if (!/^[0-9]{12}$/.test(account||'')) throw Error('Invalid bootstrap configuration');
  const url=new URL(env.PORTAL_BOOTSTRAP_TEMPLATE_URL);
  const match=/^\/bootstrap\/([a-f0-9]{64})\/account-link\.template\.json$/.exec(url.pathname);
  if (!match || url.protocol!=='https:' || url.username || url.password || url.port || url.hash
      || url.hostname!==`jdu-web-portal-bootstrap-${account}-${match[1].slice(0,12)}.s3.us-east-1.amazonaws.com`
      || [...url.searchParams.keys()].join(',')!=='versionId' || url.searchParams.get('versionId')==='null'
      || !/^[A-Za-z0-9._~+\/=-]{1,1024}$/.test(url.searchParams.get('versionId')||'')) throw Error('Invalid bootstrap configuration');
  return url.toString();
}

export function createBootstrapLink(env,value,clock=()=>Date.now()) {
  const now=Math.floor(clock()/1000);
  if (!value || value.registered!==false || !/^[a-f0-9]{64}$/.test(value.pair_id||'')
      || !/^[0-9]{12}$/.test(value.account||'') || !/^[a-z0-9][a-z0-9-]{2,31}$/.test(value.lab_id||'')
      || !Number.isSafeInteger(value.expires_at) || value.expires_at<=now || value.expires_at>now+305) throw Error('Invalid registration attempt');
  const url=new URL('https://us-east-1.console.aws.amazon.com/cloudformation/home?region=us-east-1');
  url.hash='/stacks/create/review?'+new URLSearchParams({templateURL:bootstrapTemplate(env),
    stackName:`jdu-web-link-${value.lab_id}-${value.pair_id.slice(0,12)}`,
    param_ExpectedAccount:value.account,param_LabId:value.lab_id,param_PairId:value.pair_id});
  return url.toString();
}
