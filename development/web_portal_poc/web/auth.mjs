import { createHash, hkdfSync, randomBytes, timingSafeEqual } from 'node:crypto';
import { EncryptJWT, jwtDecrypt, createRemoteJWKSet, jwtVerify } from 'jose';

const googleKeys = createRemoteJWKSet(new URL('https://www.googleapis.com/oauth2/v3/certs'), { timeoutDuration: 5000 });
export const SESSION = '__Host-jdu-session';
export const FLOW = '__Host-jdu-flow';
const issuers = ['https://accounts.google.com', 'accounts.google.com'];

export function configFrom(env) {
  if (env.PORTAL_MODE !== 'enabled') throw new Error('Closed');
  const origin = new URL(env.PUBLIC_ORIGIN);
  if (origin.protocol !== 'https:' || origin.username || origin.password || origin.pathname !== '/' || origin.search || origin.hash || origin.port) throw new Error('Invalid origin');
  if (!/^\d+-[a-zA-Z0-9_-]+\.apps\.googleusercontent\.com$/.test(env.GOOGLE_CLIENT_ID || '')) throw new Error('Invalid client');
  if (typeof env.GOOGLE_CLIENT_SECRET !== 'string' || env.GOOGLE_CLIENT_SECRET.length < 16) throw new Error('Missing client secret');
  return { origin: origin.origin, clientId: env.GOOGLE_CLIENT_ID, secret: env.GOOGLE_CLIENT_SECRET, domain: 'jdu.uz', redirect: `${origin.origin}/auth/callback` };
}

export function cookies(request) {
  const result = new Map();
  for (const pair of (request.headers.get('cookie') || '').split(';')) {
    const at = pair.indexOf('=');
    if (at < 0) continue;
    const key = pair.slice(0, at).trim();
    if (result.has(key)) throw new Error('Duplicate cookie');
    result.set(key, pair.slice(at + 1).trim());
  }
  return result;
}
export function cookie(name, value, seconds) {
  return `${name}=${value}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${seconds}`;
}
function flowKey(config) {
  return new Uint8Array(hkdfSync('sha256', config.secret, config.clientId, 'jdu-learning-portal/oauth-flow/v1', 32));
}
const random = () => randomBytes(32).toString('base64url');
export function equal(a, b) {
  return typeof a === 'string' && typeof b === 'string' && a.length <= 512 && a.length === b.length && timingSafeEqual(Buffer.from(a), Buffer.from(b));
}
export function loginTarget(value='/',config) {
  if(typeof value!=='string' || value.length>1024 || !value.startsWith('/') || value.startsWith('//') || /[\\\x00-\x1f\x7f]/u.test(value))throw Error('Invalid login destination');
  const target=new URL(value,config.origin);
  const paths=new Set(['/','/checks','/grades','/status','/teacher','/teacher/student','/enroll','/link','/prepare']);
  const fields=new Set(['lang','task_id','job_id','check_mode','context','lab_id','after']);
  if(target.origin!==config.origin || !paths.has(target.pathname) || target.hash || [...target.searchParams.keys()].some(k=>!fields.has(k)) || new Set(target.searchParams.keys()).size!==[...target.searchParams.keys()].length)throw Error('Invalid login destination');
  return target.pathname+target.search;
}
export async function login(config,returnTo='/') {
  returnTo=loginTarget(returnTo,config);
  const state = random(), nonce = random(), verifier = random();
  const sealed = await new EncryptJWT({ state, nonce, verifier, returnTo }).setProtectedHeader({ alg: 'dir', enc: 'A256GCM' }).setIssuer(config.origin).setAudience('oauth-flow').setIssuedAt().setExpirationTime('5m').encrypt(flowKey(config));
  const location = new URL('https://accounts.google.com/o/oauth2/v2/auth');
  location.search = new URLSearchParams({ client_id: config.clientId, redirect_uri: config.redirect, response_type: 'code', scope: 'openid email', state, nonce, code_challenge: createHash('sha256').update(verifier).digest('base64url'), code_challenge_method: 'S256', hd: config.domain, prompt: 'select_account' }).toString();
  return { location: location.toString(), flowCookie: cookie(FLOW, sealed, 300) };
}
export async function readFlow(token, config) {
  const { payload } = await jwtDecrypt(token, flowKey(config), { issuer: config.origin, audience: 'oauth-flow', keyManagementAlgorithms: ['dir'], contentEncryptionAlgorithms: ['A256GCM'], requiredClaims: ['exp', 'iat', 'state', 'nonce', 'verifier'], maxTokenAge: '5m' });
  return payload;
}
export async function verifyGoogle(token, config, { nonce, keys = googleKeys } = {}) {
  const { payload } = await jwtVerify(token, keys, { issuer: issuers, audience: config.clientId, algorithms: ['RS256'], requiredClaims: ['sub', 'iat', 'exp', 'email', 'email_verified', 'hd'], maxTokenAge: '1h', clockTolerance: 5 });
  if (payload.email_verified !== true || payload.hd !== config.domain || typeof payload.email !== 'string' || !/^[^\s@]+@jdu\.uz$/i.test(payload.email) || (payload.azp && payload.azp !== config.clientId) || (nonce !== undefined && !equal(payload.nonce, nonce))) throw new Error('Organization identity required');
  return payload;
}
export async function callback(request, config, { exchange = fetch, verify = verifyGoogle } = {}) {
  const url = new URL(request.url);
  if (url.searchParams.getAll('state').length !== 1 || url.searchParams.getAll('code').length !== 1 || url.searchParams.has('error')) throw new Error('Invalid callback');
  const flow = await readFlow(cookies(request).get(FLOW), config);
  if (!equal(url.searchParams.get('state'), flow.state)) throw new Error('Invalid state');
  const response = await exchange('https://oauth2.googleapis.com/token', { method: 'POST', signal: AbortSignal.timeout(5000), headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ grant_type: 'authorization_code', code: url.searchParams.get('code'), redirect_uri: config.redirect, client_id: config.clientId, client_secret: config.secret, code_verifier: flow.verifier }) });
  if (!response.ok) throw new Error('Exchange failed');
  const result = await response.json();
  if (typeof result.id_token !== 'string' || result.id_token.length > 3500) throw new Error('Invalid token');
  const payload = await verify(result.id_token, config, { nonce: flow.nonce });
  const ttl = Math.min(3600, Math.floor(payload.exp - Date.now() / 1000));
  if (ttl <= 0) throw new Error('Expired');
  return { sessionCookie: cookie(SESSION, result.id_token, ttl), clearFlow: cookie(FLOW, '', 0), returnTo:loginTarget(flow.returnTo,config) };
}
