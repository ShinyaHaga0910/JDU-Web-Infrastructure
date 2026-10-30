"""One-job RSA password delivery to the existing bastion, never to SSM logs."""
import base64
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import time
import zlib


def directory(path):
    value=path.lstat()
    if path.is_symlink() or not stat.S_ISDIR(value.st_mode) or value.st_uid!=0 or value.st_mode&0o077:
        raise ValueError('Private root-controlled job directory required')


def job(request,base=Path('/var/lib/jdu-web/browser-functional')):
    import remote_guest
    b=remote_guest.identity(request)
    if b['role']!='bastion' or b['instances']!=request['instances'] or request['task_id'] not in ('P5','M5','P6','M6'):
        raise ValueError('Own functional check required')
    if not re.fullmatch(r'[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}',request['run_id']):
        raise ValueError('Fixed job ID required')
    if not base.exists():base.mkdir(mode=0o700)
    directory(base)
    root=base/request['run_id']
    if not root.exists():root.mkdir(mode=0o700)
    directory(root)
    return root,b


def prepare(request):
    root,b=job(request);private=root/'recipient.pem';context=root/'context.json'
    wanted={k:request[k] for k in ('lab_id','deployment_id','task_id','run_id','instances')}
    if context.exists():
        saved=json.loads(context.read_bytes())
        if saved['context']!=wanted or time.time()-saved['created_at']>900:raise ValueError('Existing or expired job retained')
    else:
        if private.exists() or private.is_symlink():raise ValueError('Inspect incomplete key preparation')
        subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:4096','-out',str(private)],check=True,capture_output=True,timeout=100)
        private.chmod(0o600)
        with context.open('x',encoding='utf-8') as out:json.dump({'context':wanted,'created_at':int(time.time())},out)
        context.chmod(0o600)
    s=private.lstat()
    if private.is_symlink() or not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or stat.S_IMODE(s.st_mode)!=0o600 or s.st_nlink!=1:
        raise ValueError('Private transport key required')
    public=subprocess.run(['openssl','pkey','-in',str(private),'-pubout'],check=True,capture_output=True,timeout=5).stdout.decode()
    from registry import build_report
    identity={k:b[k] for k in ('lab_id','release_id','deployment_id','instances')}
    from datetime import datetime,timezone
    return {'report':build_report(request['task_id'],identity,{},request['run_id'],checked_at=datetime.now(timezone.utc).isoformat()),
            'functional_recipient':{'job_id':request['run_id'],'public_key':public}}


def execute(request,sealed):
    root,b=job(request);private=root/'recipient.pem';context=json.loads((root/'context.json').read_bytes())
    wanted={k:request[k] for k in ('lab_id','deployment_id','task_id','run_id','instances')}
    if context['context']!=wanted or time.time()-context['created_at']>900:raise ValueError('Own current password delivery required')
    s=private.lstat()
    if private.is_symlink() or s.st_uid!=0 or not stat.S_ISREG(s.st_mode) or stat.S_IMODE(s.st_mode)!=0o600 or s.st_nlink!=1:
        raise ValueError('Protected one-job key required')
    raw=base64.b64decode(sealed,validate=True)
    if len(raw)!=512:raise ValueError('Fixed RSA4096 encrypted delivery required')
    result=subprocess.run(['openssl','pkeyutl','-decrypt','-inkey',str(private),'-pkeyopt','rsa_padding_mode:oaep',
        '-pkeyopt','rsa_oaep_md:sha256','-pkeyopt','rsa_mgf1_md:sha256'],input=raw,check=True,capture_output=True,timeout=5)
    value=json.loads(result.stdout)
    if (type(value) is not list or len(value)!=2 or value[0]!=request['run_id'] or not isinstance(value[1],str)
            or not 1<=len(value[1].encode('utf-16-le'))//2<=128 or any(ord(c)<32 or ord(c)==127 for c in value[1])):
        raise ValueError('Wrong password delivery context')
    private.unlink()
    import remote_guest
    return remote_guest.collect(request,password=value[1])


def command(request,*,sealed_password=None,prepare=False):
    from transport import payload,LOADER
    source=Path(__file__).read_text(encoding='utf-8')
    data={'payload':payload(request),'guest':source,'sealed':sealed_password,'prepare':prepare}
    packed=base64.b64encode(zlib.compress(json.dumps(data,separators=(',',':')).encode(),9)).decode()
    loader=LOADER[:LOADER.index('try:\n print(json.dumps(m.run')]
    program=('import base64,io,json,sys,zlib\nx=json.loads(zlib.decompress(base64.b64decode('+repr(packed)+')));'
        'sys.stdin=io.StringIO(json.dumps(x["payload"]))\n'+loader+'\n'
        'g={"__name__":"browser_check_guest"};exec(compile(x["guest"],"<browser-check-guest>","exec"),g);'
        'answer=g["prepare"](p["request"]) if x["prepare"] else g["execute"](p["request"],x["sealed"]);'
        'print(json.dumps(answer,separators=(",",":")))')
    result='python3 -B -c '+shlex.quote(program)
    if len(result.encode())>65536:raise ValueError('Bounded functional command required')
    return result
