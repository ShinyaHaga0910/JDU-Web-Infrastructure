"""Build a code-only teacher upgrade with two existing-admin-authenticated routes."""
import base64
import json
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parent
LEGACY = ROOT / 'legacy' if (ROOT / 'legacy').is_dir() else ROOT.parent / 'web_lab_teacher'
sys.path.insert(0, str(LEGACY))
from build_template import build as legacy_build

ROUTES = ('POST /api/web/admin/assessment-context', 'POST /api/web/admin/grades')


def admin_route(route):
    return dict(Type='AWS::ApiGatewayV2::Route', Properties=dict(
        ApiId={'Ref': 'ProgressApi'}, RouteKey=route,
        Target={'Fn::Join': ['/', ['integrations', {'Ref': 'Integration'}]]}))


def inline_source():
    sources = {name: (ROOT / (name + '.py')).read_text() for name in ('registry', 'grading', 'dashboard', 'progress_api_v2')}
    sources['progress_api'] = (LEGACY / 'progress_api.py').read_text()
    sources['registry_data'] = (ROOT / 'assessment-registry.json').read_text()
    encoded = base64.b64encode(zlib.compress(json.dumps(sources).encode(), 9)).decode()
    return ("import base64,json,sys,types,zlib\n_s=json.loads(zlib.decompress(base64.b64decode(" + repr(encoded) + ")))\n"
            "for _n in ('registry','grading','dashboard','progress_api','progress_api_v2'):\n"
            " _m=types.ModuleType(_n);_m.__file__='/public/'+_n+'.py';sys.modules[_n]=_m\n"
            " if _n=='registry':_m.__dict__['_REGISTRY_BYTES']=_s['registry_data'].encode()\n"
            " exec(compile(_s[_n],_m.__file__,'exec'),_m.__dict__)\n"
            "handler=sys.modules['progress_api_v2'].handler\n")


def build():
    template = legacy_build()
    template['Resources']['ProgressFunction']['Properties']['Code'] = dict(ZipFile=inline_source())
    for index, route in enumerate(ROUTES, 8):
        template['Resources']['Route' + str(index)] = admin_route(route)
    if len(json.dumps(template, separators=(',', ':')).encode()) > 51200:
        raise ValueError('Teacher template must fit the existing direct inline path')
    return template


def validate_upgrade(old, proposed):
    restored = json.loads(json.dumps(proposed))
    old_code = old['Resources']['ProgressFunction']['Properties']['Code']
    for index, route in enumerate(ROUTES, 8):
        name = 'Route' + str(index)
        if restored['Resources'].get(name) != admin_route(route):
            raise ValueError('Only the canonical authenticated teacher operations are allowed')
        if name in old['Resources']:
            if old['Resources'][name] != admin_route(route):
                raise ValueError('Existing admin route differs from the reviewed definition')
        else:
            restored['Resources'].pop(name)
    restored['Resources']['ProgressFunction']['Properties']['Code'] = old_code
    if restored != old:
        raise ValueError('Resource identity, credentials, networking, IAM or storage differs')


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True)
    a = p.parse_args()
    with Path(a.output).open('x') as stream:
        json.dump(build(), stream, separators=(',', ':')); stream.write('\n')
