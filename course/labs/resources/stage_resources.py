"""Stage public teaching resources from the accepted personal signed kit; no services or secrets."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import zlib
import shlex
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent

GUEST = '''import base64,hashlib,json,os,stat
from pathlib import Path
p=json.load(__import__('sys').stdin)
b=json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
if os.geteuid()!=0 or any(b[k]!=p[k] for k in ('lab_id','deployment_id','instance_id','role')):
 raise ValueError('Wrong registered node')
root=Path('/var/lib/jdu-web/lesson-resources-r1')
for parent in (root,*root.parents):
 if parent.is_symlink(): raise ValueError('Linked destination refused')
 if parent.exists() and (parent.stat().st_uid!=0 or parent.stat().st_mode&0o022):
  raise ValueError('Root-controlled destination required')
files={name:base64.b64decode(value,validate=True) for name,value in p['files'].items()}
if any(Path(name).name!=name for name in files): raise ValueError('Invalid name')
if root.exists():
 for name,data in files.items():
  target=root/name
  s=target.lstat()
  if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or stat.S_IMODE(s.st_mode)!=0o644 or s.st_nlink!=1 or target.read_bytes()!=data:
   raise ValueError('Existing different resource retained')
else:
 root.mkdir(mode=0o755)
 for name,data in files.items():
  fd=os.open(root/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
  with os.fdopen(fd,'wb') as f: os.fchmod(f.fileno(),0o644);f.write(data)
print(json.dumps(dict(public_resources_ready=True,role=b['role'],file_count=len(files),services_changed=False)))
'''


def packed_command(request):
    data=json.dumps(dict(source=GUEST,request=request)).encode()
    packed=base64.b64encode(zlib.compress(data,9)).decode()
    program=("import base64,zlib,json,io,sys;p=json.loads(zlib.decompress(base64.b64decode("
             + repr(packed) + ")));sys.stdin=io.StringIO(json.dumps(p['request']));exec(p['source'])")
    command='python3 -B -c '+shlex.quote(program)
    if len(command.encode())>60000:
        raise ValueError('Public resource command exceeds the bounded staging size')
    return command


def send_stage(ssm,instance_id,request):
    command_id=ssm.send_command(InstanceIds=[instance_id],DocumentName='AWS-RunShellScript',
        Parameters={'commands':[packed_command(request)],'executionTimeout':['90']},
        TimeoutSeconds=30)['Command']['CommandId']
    for _ in range(45):
        try:
            r=ssm.get_command_invocation(CommandId=command_id,InstanceId=instance_id)
        except ssm.exceptions.InvocationDoesNotExist:
            time.sleep(1);continue
        if r['Status']=='Success':
            return json.loads(r['StandardOutputContent'])
        if r['Status'] in ('Failed','Cancelled','TimedOut','Cancelling'):
            raise ValueError('Inspect failed SSM command '+command_id+' before retrying')
        time.sleep(1)
    raise ValueError('SSM command '+command_id+' is still pending; inspect before retrying')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--installation', required=True, type=Path)
    a = p.parse_args()
    pins = json.loads((ROOT / 'release-map.json').read_text())
    installation = a.installation.absolute()
    installation.relative_to(Path.home())
    kit = installation / 'kit'
    for name, digest in pins['import_pins'].items():
        if hashlib.sha256((kit / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Use the accepted signed course installation')
    sys.path.insert(0, str(kit))
    from release_tools import verify, read, parse
    context = verify(kit, pins['fingerprint'])
    if context['release']['distribution_id'] != pins['distribution_id']:
        raise ValueError('This teaching resource is for the recorded distribution')
    import student
    import boto3
    session = boto3.Session(region_name='us-east-1')
    binding = parse(read(installation / 'binding.private.json', private=True))
    selected = student.identity(context, binding['command_state'], session.client('sts').get_caller_identity()['Account'])
    if selected['binding'] != binding:
        raise ValueError('Use your existing personal binding')
    student.current(context, selected, session)
    from setup_internal_ssh import current_nodes
    nodes = current_nodes(session.client('ec2'), session.client('cloudformation'), selected['state'], selected['baseline'])
    files = {name: read(kit / 'assessment' / name) for name in
             ('catalog-app.tar.gz', 'registry.py', 'assessment-registry.json', 'database_secret.py')}
    for name in ('offline_assets.py',):
        data = (ROOT / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != pins['resource_pins'][name]:
            raise ValueError('Teaching resource differs from the reviewed copy')
        files[name] = data
    for role in ('web', 'db'):
        request = {key: selected['state'][key] for key in ('lab_id', 'deployment_id')}
        request.update(role=role, instance_id=nodes[role]['instance_id'],
                       files={name: base64.b64encode(raw).decode() for name, raw in files.items()})
        result = send_stage(session.client('ssm'), nodes[role]['instance_id'], request)
        if result.get('public_resources_ready') is not True or result.get('role') != role:
            raise ValueError('Inspect the SSM command before retrying')
        print('PUBLIC_LESSON_RESOURCES_READY=' + role)
    print('No packages, database roles, passwords, services, SSH keys or grading registration were changed.')


if __name__ == '__main__':
    main()
