"""Teacher fixture only: replace the reviewed public observer, preserving all credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from app_fixture_controller import DEPLOYMENT, REMOTE, save, send, wait_public


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--old-candidate', required=True)
    p.add_argument('--candidate', required=True)
    p.add_argument('--job', required=True)
    a = p.parse_args()
    import boto3
    if boto3.client('sts').get_caller_identity()['Account'] != '965244652544':
        raise ValueError('Selected student verification account only')
    old, new = Path(a.old_candidate), Path(a.candidate)
    sys.path.insert(0, str(new))
    from transport import sources
    before, after = sources(old), sources(new)
    if {n for n in before if before[n] != after[n]} != {'system_observer.py'} or before.keys() != after.keys():
        raise ValueError('Only the reviewed system observer may change')
    stage = json.loads(Path(a.stage).read_text())
    if stage['deployment_id'] != DEPLOYMENT or Path(a.output).exists() or Path(a.job).exists():
        raise ValueError('Retain original stages and jobs')
    code = '''import hashlib,json,os
from pathlib import Path
p=Path(REMOTE)
raw=(p/'bundle.public.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()==EXPECTED
b=json.loads(raw)
assert hashlib.sha256(b['observer_sources']['system_observer.py'].encode()).hexdigest()==OLD
secret=p/'credentials.private.json';private=secret.read_bytes();metadata=secret.stat()
assert metadata.st_uid==0 and metadata.st_mode&0o777==0o600
b['observer_sources']['system_observer.py']=SOURCE
changed=json.dumps(b,separators=(',',':'),ensure_ascii=False).encode()
for name,data in [('bundle-r7.before.json',raw),('bundle-r8.new',changed)]:
 fd=os.open(p/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(data)
os.replace(p/'bundle-r8.new',p/'bundle.public.json')
assert secret.read_bytes()==private and secret.stat().st_ino==metadata.st_ino
print(json.dumps(dict(bundle_sha256=hashlib.sha256(changed).hexdigest(),credentials_unchanged=True,only_public_observer_changed=True)))
'''
    code = ('REMOTE=' + repr(REMOTE) + '\nEXPECTED=' + repr(stage['bundle_sha256'])
        + '\nOLD=' + repr(hashlib.sha256(before['system_observer.py'].encode()).hexdigest())
        + '\nSOURCE=' + repr(after['system_observer.py']) + '\n' + code)
    ssm = boto3.client('ssm', region_name='us-east-1')
    node = stage['bastion_instance_id']
    cid = send(ssm, node, code, 60)
    save(Path(a.job), dict(command_id=cid, bastion_instance_id=node, deployment_id=DEPLOYMENT))
    wait_public(ssm, node, cid)
    result = json.loads(ssm.get_command_invocation(CommandId=cid, InstanceId=node)['StandardOutputContent'])
    stage.update(bundle_sha256=result['bundle_sha256'], observer_refresh_command_id=cid,
                 observer_refresh_credentials_unchanged=True)
    save(Path(a.output), stage)
    print('D11_FIXTURE_PUBLIC_OBSERVER_REFRESHED; existing credentials unchanged')


if __name__ == '__main__':
    main()
