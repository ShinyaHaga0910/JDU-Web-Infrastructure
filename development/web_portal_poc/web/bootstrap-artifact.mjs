import { createHash } from 'node:crypto';
import { S3Client,GetObjectCommand } from '@aws-sdk/client-s3';
import { bootstrapTemplate } from './bootstrap-link.mjs';

// Read the fixed same-owner, hash-addressed public-code artifact. The browser
// receives an immutable version URL, never an AWS signature or credential.
export function createBootstrapEnv(env=process.env,client=new S3Client({region:'us-east-1',maxAttempts:1}),clock=()=>Date.now()) {
  const base={...env};
  let cached,until=0,pending;
  return async()=>{
    if (base.PORTAL_MODE!=='enabled' || base.PORTAL_ENROLLMENT_ENABLED!=='true') return {...base};
    const digest=base.PORTAL_BOOTSTRAP_TEMPLATE_DIGEST,account=base.PORTAL_AWS_ACCOUNT_ID;
    if (digest==='disabled' || digest===undefined) return {...base}; // Explicit-version development/preview setting.
    if (!/^[a-f0-9]{64}$/.test(digest) || !/^[0-9]{12}$/.test(account||'')) throw Error('Registration configuration unavailable');
    if (cached && clock()<until) return {...base,PORTAL_BOOTSTRAP_TEMPLATE_URL:cached};
    if (!pending) pending=(async()=>{
      let body;
      try {
        const bucket=`jdu-web-portal-bootstrap-${account}-${digest.slice(0,12)}`;
        const key=`bootstrap/${digest}/account-link.template.json`;
        const result=await client.send(new GetObjectCommand({Bucket:bucket,Key:key,ExpectedBucketOwner:account}),
                                       {abortSignal:AbortSignal.timeout(5000)});
        body=result.Body;
        if (!Number.isSafeInteger(result.ContentLength) || result.ContentLength<1 || result.ContentLength>51200
            || typeof result.VersionId!=='string' || !body?.[Symbol.asyncIterator]) throw Error();
        const chunks=[];let size=0;
        for await (const part of body) {
          const chunk=Buffer.from(part);size+=chunk.length;
          if (size>51200) throw Error();
          chunks.push(chunk);
        }
        const bytes=Buffer.concat(chunks);
        if (size!==result.ContentLength || createHash('sha256').update(bytes).digest('hex')!==digest) throw Error();
        const url=`https://${bucket}.s3.us-east-1.amazonaws.com/${key}?versionId=${encodeURIComponent(result.VersionId)}`;
        cached=bootstrapTemplate({...base,PORTAL_BOOTSTRAP_TEMPLATE_URL:url});
        until=clock()+300000;
        return cached;
      } catch {throw Error('Registration configuration unavailable');}
      finally {if (typeof body?.destroy==='function') body.destroy();}
    })().finally(()=>{pending=undefined;});
    return {...base,PORTAL_BOOTSTRAP_TEMPLATE_URL:await pending};
  };
}
