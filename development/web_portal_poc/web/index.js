import { createServer } from 'node:http';
import { Readable } from 'node:stream';
import { createApp } from './router.mjs';
import { createGradeClient, createStatusClient } from './grade-client.mjs';
import { createSessions } from './sessions.mjs';
import { createAcceptanceHealth } from './acceptance-health.mjs';
import { createRuntimeEnv } from './secrets.mjs';

// A missing backend fails closed at request time; the server can still start
// in the closed deployment mode without credentials or an active Lab.
let getGrade, getStatus, sessions, getAcceptanceHealth;
try { getGrade=createGradeClient(); } catch { getGrade=undefined; }
try { getStatus=createStatusClient(); } catch { getStatus=undefined; }
try { sessions=createSessions(); } catch { sessions=undefined; }
try { getAcceptanceHealth=createAcceptanceHealth(); } catch { getAcceptanceHealth=undefined; }
const getRuntimeEnv=createRuntimeEnv();
const endpoint=process.env.AWS_LAMBDA_HTTP_ENDPOINT;
const address=endpoint ? new URL(endpoint.includes('://') ? endpoint : `http://${endpoint}`) : new URL(`http://127.0.0.1:${process.env.PORT||8080}`);
createServer(async (req,res) => {
  try {
    const origin=process.env.PUBLIC_ORIGIN || 'https://closed.invalid';
    const request=new Request(new URL(req.url,origin),{method:req.method,headers:req.headers});
    // Static liveness remains available when the Lab's secret store is offline.
    // The acceptance endpoint independently rejects enabled deployments.
    const path=new URL(request.url).pathname;
    const env=['/healthz','/healthz/acceptance'].includes(path) ? process.env : await getRuntimeEnv();
    const app=createApp({env,getGrade,getStatus,sessions,getAcceptanceHealth});
    const result=await app(request);
    res.statusCode=result.status;
    for (const [key,value] of result.headers) if (key!=='set-cookie') res.setHeader(key,value);
    if (result.headers.getSetCookie().length) res.setHeader('Set-Cookie',result.headers.getSetCookie());
    if (result.body && req.method!=='HEAD') Readable.fromWeb(result.body).pipe(res); else res.end();
  } catch {res.writeHead(503,{'Cache-Control':'no-store'});res.end('Unavailable');}
}).listen(Number(address.port||80),address.hostname);
