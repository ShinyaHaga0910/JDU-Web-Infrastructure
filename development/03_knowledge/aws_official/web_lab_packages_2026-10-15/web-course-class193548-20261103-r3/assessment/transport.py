"""Public, compressed source transport; existing pinned SSH and SSM only."""
import base64
import json
from pathlib import Path
import shlex
import zlib

MODULES = ('registry', 'network_checks', 'db_observer', 'system_observer', 'app_probe', 'remote_guest')
LOADER = '''import base64,json,sys,types,zlib
p=json.load(sys.stdin)
s=p['sources']
for name in ('registry','network_checks','db_observer','system_observer','app_probe','remote_guest'):
 m=types.ModuleType(name);m.__file__='/trusted-public/'+name+'.py';sys.modules[name]=m
 if name=='registry':m.__dict__['_REGISTRY_BYTES']=s['assessment-registry.json'].encode()
 exec(compile(s[name+'.py'],m.__file__,'exec'),m.__dict__)
m=sys.modules['remote_guest'];m.PUBLIC_SOURCES=s;m.LOADER_SOURCE=s['loader']
try:
 print(json.dumps(m.run(p['request']),separators=(',',':')))
except Exception as exc:
 print(json.dumps({'observer_error':type(exc).__name__}));raise SystemExit(2)
'''


def sources(root=None):
    root = Path(root) if root else Path(__file__).resolve().parent
    result = {m + '.py': (root / (m + '.py')).read_text() for m in MODULES}
    result['assessment-registry.json'] = (root / 'assessment-registry.json').read_text()
    result['loader'] = LOADER
    return result


def payload(request):
    return dict(request=request, sources=sources())


def ssm_command(request):
    # Compress the entire source+registry envelope before crossing the API boundary.
    raw = zlib.compress(json.dumps(payload(request), separators=(',', ':')).encode(), 9)
    prefix = 'import base64,io,sys,zlib;sys.stdin=io.StringIO(zlib.decompress(base64.b64decode(' + repr(base64.b64encode(raw).decode()) + ')).decode());'
    return 'python3 -c ' + shlex.quote(prefix + LOADER)
