// Server-only credential delivery. Nothing returned here is a browser field.
import {constants,createHash,publicEncrypt,randomBytes,X509Certificate} from 'node:crypto';

const hex=v=>typeof v==='string' && /^[a-f0-9]{64}$/.test(v);
export function createInitialDelivery(context,{now=Date.now()}={}) {
  if (!context || !/^[0-9]{12}$/.test(context.account||'')
      || !/^[a-z0-9][a-z0-9-]{2,31}$/.test(context.lab_id||'')
      || !/^web-[0-9]{4}-[0-9]{2}-r[1-9][0-9]*$/.test(context.release_id||'') || context.release_id.length>64
      || !/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(context.deployment_id||'')
      || !/^i-[a-f0-9]{17}$/.test(context.instance_id||'') || !hex(context.certificate_sha256)
      || typeof context.certificate_pem!=='string' || context.certificate_pem.length>8192
      || createHash('sha256').update(context.certificate_pem).digest('hex')!==context.certificate_sha256) throw Error('Invalid delivery recipient');
  const cert=new X509Certificate(context.certificate_pem),key=cert.publicKey;
  if (key.asymmetricKeyType!=='rsa' || key.asymmetricKeyDetails?.modulusLength!==3072
      || cert.subject!==`CN=jdu-web-envelope-${context.deployment_id}` || !cert.verify(key)
      || !(Date.parse(cert.validFrom)<=now && now<Date.parse(cert.validTo))) throw Error('Invalid delivery recipient');
  const entropy=randomBytes(32);
  try {
    const token=entropy.toString('base64url');
    const plaintext=Buffer.from(JSON.stringify(['jdu-progress-oaep-v1',context.lab_id,context.release_id,
      context.deployment_id,context.instance_id,token]));
    try {
      // One standard RSA-OAEP block; all purpose/deployment context is inside
      // the encrypted plaintext. No homemade cipher, padding or ASN.1 codec.
      if(plaintext.length>318)throw Error('Delivery exceeds RSA-OAEP capacity');
      const ciphertext=publicEncrypt({key,padding:constants.RSA_PKCS1_OAEP_PADDING,oaepHash:'sha256'},plaintext);
      return {schema_version:1,certificate_sha256:context.certificate_sha256,
        ciphertext_b64:ciphertext.toString('base64'),token_hash:createHash('sha256').update(token).digest('hex')};
    } finally {plaintext.fill(0);}
  } finally {entropy.fill(0);}
}
