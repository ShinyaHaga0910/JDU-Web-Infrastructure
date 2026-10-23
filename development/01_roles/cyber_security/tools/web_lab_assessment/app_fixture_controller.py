"""Teacher-only public staging/apply/probe controller for the retained student five nodes.

Stage makes no credentials. The human starts Apply; new secrets are generated
inside the bastion and travel only through the existing pinned private SSH path.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import time
import uuid
import zlib

ROOT = Path(__file__).resolve().parent
REMOTE = '/var/lib/jdu-web/d11-app-manager-r1'
DEPLOYMENT = '3ab82943-031d-4806-b4c0-c0b0e4554006'


def save(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2)


def public_bundle(candidate, state, nodes, enrollment, public_ip):
    sys.path.insert(0, str(candidate))
    from registry import REGISTRY, CONTRACT_SHA256
    from transport import sources
    from app_fixture_guest import extract_app
    archive = (candidate / 'catalog-app.tar.gz').read_bytes()
    files = extract_app(dict(application_b64=base64.b64encode(archive).decode(), registry=REGISTRY))
    sql = {}
    mission, practice = REGISTRY['profiles']['mission'], REGISTRY['profiles']['practice']
    for profile in ('mission', 'practice'):
        sql[profile] = {}
        for name in ('01_create_roles.sql', '02_prepare_schema.sql', '03_runtime_grants.sql', '04_disable_setup.sql'):
            text = files['sql/' + name].decode()
            if profile == 'practice':
                for key in ('db_name', 'setup_role', 'runtime_role'):
                    text = text.replace(mission[key], practice[key])
            sql[profile][name] = text
    identity = {k: state[k] for k in ('lab_id', 'deployment_id')}
    identity.update(instance_id=nodes['bastion']['instance_id'], instances={r: n['instance_id'] for r, n in nodes.items()})
    return dict(identity=identity, registry=REGISTRY, contract_sha256=CONTRACT_SHA256,
        expected_public_key=enrollment['public_key'], public_ipv4=public_ip,
        application_b64=base64.b64encode(archive).decode(), sql=sql, observer_sources=sources(candidate),
        foundation_source=(ROOT / 'foundation_fixture_guest.py').read_text(),
        guest_source=(ROOT / 'app_fixture_guest.py').read_text(), manager_source=(ROOT / 'app_fixture_manager.py').read_text())


def packed(code):
    return 'python3 -c ' + shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('
        + repr(base64.b64encode(zlib.compress(code.encode(), 9)).decode()) + ')))')


def send(ssm, bastion, code, timeout=3600):
    command = packed(code)
    if len(command) > 60000:
        raise ValueError('Public command is too large')
    return ssm.send_command(InstanceIds=[bastion], DocumentName='AWS-RunShellScript',
        Parameters={'commands': [command], 'executionTimeout': [str(timeout)]}, TimeoutSeconds=30)['Command']['CommandId']


def wait_public(ssm, bastion, command):
    for _ in range(90):
        time.sleep(1)
        try:
            result = ssm.get_command_invocation(CommandId=command, InstanceId=bastion)
        except ssm.exceptions.InvocationDoesNotExist:
            continue
        if result['Status'] == 'Success':
            return
        if result['Status'] in ('Failed', 'TimedOut', 'Cancelled'):
            raise ValueError('Public staging failed; inspect retained command ' + command)
    raise ValueError('Public staging still pending; inspect ' + command)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('stage', 'apply', 'poll', 'switch', 'probe', 'status'))
    parser.add_argument('--command-state', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--stage', required=True)
    parser.add_argument('--job')
    parser.add_argument('--profile', choices=('practice', 'mission'))
    parser.add_argument('--task', choices=('P5', 'P6', 'M5', 'M6'))
    a = parser.parse_args()
    import boto3
    os.umask(0o077)
    if boto3.client('sts').get_caller_identity()['Account'] != '965244652544':
        raise ValueError('Selected student verification account only')
    c = json.loads(Path(a.command_state).read_text())
    state, baseline = [json.loads(Path(c[k]).read_text()) for k in ('state', 'baseline_plan')]
    if state['deployment_id'] != baseline['deployment_id'] or state['deployment_id'] != DEPLOYMENT:
        raise ValueError('Selected retained verification deployment only')
    candidate = Path(a.candidate)
    sys.path[:0] = [str(candidate), c['bootstrap_tools']]
    from setup_internal_ssh import current_nodes
    from registry import CONTRACT_SHA256, validate_report, score
    from assessment_check import save_once, invoke
    ec2, cfn, ssm = [boto3.client(n, region_name='us-east-1') for n in ('ec2', 'cloudformation', 'ssm')]
    nodes = current_nodes(ec2, cfn, state, baseline)
    bastion = nodes['bastion']['instance_id']
    stage = Path(a.stage)
    if a.operation in ('stage', 'apply'):
        from aws_readiness import verify
        template = cfn.get_template(StackName=state['stack_id'], TemplateStage='Original')['TemplateBody']
        if isinstance(template, str):
            template = json.loads(template)
        if not verify(ec2, cfn, ssm, state, template, nodes):
            raise ValueError('Keep the exact original management and network boundaries')
    if a.operation == 'stage':
        if stage.exists():
            raise ValueError('Existing public stage retained')
        for role in ('db', 'web'):
            code = ('import json,pwd,subprocess\nfrom pathlib import Path\nb=json.loads(Path("/etc/jdu-web/bootstrap.json").read_text())\n'
                'assert b["role"]==' + repr(role) + ' and b["instance_id"]==' + repr(nodes[role]['instance_id'])
                + ' and b["deployment_id"]==' + repr(DEPLOYMENT) + '\n'
                'ports=subprocess.run(["ss","-H","-ltn"],capture_output=True,text=True,check=True).stdout\n'
                'try:pwd.getpwnam("catalog");catalog=True\nexcept KeyError:catalog=False\n'
                'package=subprocess.run(["dpkg-query","-W","-f=${db:Status-Status}","postgresql-16"],capture_output=True,text=True)\n'
                'v=dict(role=' + repr(role) + ',catalog_user=catalog,app_exists=Path("/opt/jdu-catalog").exists() or Path("/etc/jdu-catalog").exists(),'
                'pg16=package.returncode==0 and package.stdout.strip()=="installed",pg16_data=Path("/var/lib/postgresql/16/main").exists(),'
                'occupied=any(line.split()[3].rsplit(":",1)[-1] in ' + repr(['5432'] if role == 'db' else ['8000', '8080'])
                + ' for line in ports.splitlines() if len(line.split())>=4))\nprint(json.dumps(v))\n')
            cid = send(ssm, nodes[role]['instance_id'], code, 60)
            wait_public(ssm, nodes[role]['instance_id'], cid)
            value = json.loads(ssm.get_command_invocation(CommandId=cid, InstanceId=nodes[role]['instance_id'])['StandardOutputContent'])
            if value['occupied'] or (role == 'db' and (value['pg16'] or value['pg16_data'])) or (role == 'web' and (value['catalog_user'] or value['app_exists'])):
                raise ValueError('Existing student DB/app state retained')
            print('D11_APP_PREFLIGHT_CLEAN=' + role, flush=True)
        enrollment = json.loads(Path(c['ssh_enrollment']).read_text())
        web = ec2.describe_instances(InstanceIds=[nodes['web']['instance_id']])['Reservations'][0]['Instances'][0]
        bundle = public_bundle(candidate, state, nodes, enrollment, web.get('PublicIpAddress'))
        raw = json.dumps(bundle, separators=(',', ':'), ensure_ascii=False).encode()
        digest = hashlib.sha256(raw).hexdigest()
        encoded = base64.b64encode(zlib.compress(raw, 9)).decode()
        parts = [encoded[i:i + 16000] for i in range(0, len(encoded), 16000)]
        commands = []
        for index, part in enumerate(parts):
            code = ('import os,json\nfrom pathlib import Path\nb=json.loads(Path("/etc/jdu-web/bootstrap.json").read_text())\n'
                'assert b["role"]=="bastion" and b["instance_id"]==' + repr(bastion) + ' and b["deployment_id"]==' + repr(DEPLOYMENT) + '\n'
                'p=Path(' + repr(REMOTE) + ')\n')
            if index == 0:
                code += 'p.mkdir(mode=0o700,exist_ok=False)\n'
            code += ('fd=os.open(p/' + repr('part-' + str(index) + '.public') + ',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)\n'
                'with os.fdopen(fd,"w") as f:f.write(' + repr(part) + ')\nprint("PUBLIC_PART_STAGED")\n')
            cid = send(ssm, bastion, code, 90); commands.append(cid); wait_public(ssm, bastion, cid)
            print('D11_APP_PUBLIC_PART=' + str(index + 1) + '/' + str(len(parts)), flush=True)
        final = ('import base64,hashlib,json,os,zlib\nfrom pathlib import Path\np=Path(' + repr(REMOTE) + ')\n'
            'raw=zlib.decompress(base64.b64decode("".join((p/("part-"+str(i)+".public")).read_text() for i in range(' + str(len(parts)) + '))))\n'
            'assert hashlib.sha256(raw).hexdigest()==' + repr(digest) + '\nb=json.loads(raw)\n'
            'for name,data in [("bundle.public.json",raw),("manager.py",b["manager_source"].encode())]:\n'
            ' fd=os.open(p/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)\n'
            ' with os.fdopen(fd,"wb") as f:f.write(data)\n'
            'assert not (p/"credentials.private.json").exists()\nprint("PUBLIC_STAGE_READY_NO_CREDENTIALS")\n')
        cid = send(ssm, bastion, final, 90); commands.append(cid); wait_public(ssm, bastion, cid)
        save(stage, dict(deployment_id=DEPLOYMENT, bastion_instance_id=bastion, bundle_sha256=digest,
            contract_sha256=CONTRACT_SHA256, manager_sha256=hashlib.sha256(bundle['manager_source'].encode()).hexdigest(),
            stage_command_ids=commands, credentials_created=False))
        print('D11_APP_PUBLIC_STAGE_COMPLETE; human starts apply; no credentials created', flush=True)
        return
    prepared = json.loads(stage.read_text())
    if prepared['deployment_id'] != DEPLOYMENT or prepared['bastion_instance_id'] != bastion or prepared['contract_sha256'] != CONTRACT_SHA256:
        raise ValueError('Prepared public stage belongs to another identity/registry')
    if not a.job:
        raise ValueError('Retain a unique job path')
    job = Path(a.job)
    if a.operation == 'poll':
        info = json.loads(job.read_text())
        if info['deployment_id'] != DEPLOYMENT or info['bastion_instance_id'] != bastion:
            raise ValueError('Wrong retained job')
        result = ssm.get_command_invocation(CommandId=info['command_id'], InstanceId=bastion)
        print('D11_APP_JOB=' + result['Status'])
        if result['Status'] not in ('Success', 'Failed', 'TimedOut', 'Cancelled'):
            phases = [line for line in result.get('StandardErrorContent', '').splitlines() if line.startswith('D11_APP_STEP=')]
            if phases:
                print(phases[-1])
            return
        if result['Status'] != 'Success':
            print('D11_APP_FAILED; inspect root-only state/journal; no automatic apply retry')
            raise SystemExit(2)
        value = json.loads(result['StandardOutputContent'])
        save_once(Path(str(job) + '.public.json'), value)
        if info['operation'] == 'probe':
            report = value['report']; validate_report(report, {r: n['instance_id'] for r, n in nodes.items()})
            pending = Path(c['pending_directory']); save_once(pending / (report['request_id'] + '.report.json'), report)
            request = {k: report[k] for k in ('lab_id', 'release_id', 'deployment_id', 'run_id')}
            request.update(role='bastion', instance_id=bastion, task_id=report['mission_id'], operation='submit', report=report)
            receipt = invoke(ssm, bastion, request)
            save_once(pending / (report['request_id'] + '.receipt.json'), receipt)
            print(json.dumps(dict(task=report['mission_id'], submission='STORED', **score(report))))
        else:
            print(json.dumps(value))
        return
    if job.exists() or job.is_symlink():
        raise ValueError('Existing job retained; poll it')
    payload = {}
    if a.operation == 'switch':
        if not a.profile:
            raise ValueError('Choose the known retained profile')
        payload['profile'] = a.profile
    if a.operation == 'probe':
        if not a.task:
            raise ValueError('Choose a fixed functional task')
        from aws_readiness import verify
        template = cfn.get_template(StackName=state['stack_id'], TemplateStage='Original')['TemplateBody']
        if isinstance(template, str):
            template = json.loads(template)
        enrollment = json.loads(Path(c['ssh_enrollment']).read_text())
        identity = {k: state[k] for k in ('lab_id', 'deployment_id')}; identity['release_id'] = state.get('release_id', 'web-2026-10-r1')
        request = dict(identity, instances={r: n['instance_id'] for r, n in nodes.items()},
            role='bastion', instance_id=bastion, operation='collect', task_id=a.task, run_id=str(uuid.uuid4()),
            network_baseline=verify(ec2, cfn, ssm, state, template, nodes),
            root_volumes={r: n['root_volumes'] for r, n in nodes.items()}, expected_public_key=enrollment['public_key'],
            web_instance_id=nodes['web']['instance_id'])
        payload['request'] = request
    code = ('import hashlib,json\nfrom pathlib import Path\np=Path(' + repr(REMOTE) + ')\n'
        'assert hashlib.sha256((p/"bundle.public.json").read_bytes()).hexdigest()==' + repr(prepared['bundle_sha256']) + '\n'
        'source=(p/"manager.py").read_bytes();assert hashlib.sha256(source).hexdigest()==' + repr(prepared['manager_sha256']) + '\n'
        'n={"__name__":"trusted_app_fixture_manager"};exec(compile(source,"<trusted-app-fixture>","exec"),n)\n'
        'print(json.dumps(n["run"](' + repr(a.operation) + ',' + repr(payload) + '),separators=(",",":")))\n')
    cid = send(ssm, bastion, code)
    save(job, dict(command_id=cid, deployment_id=DEPLOYMENT, bastion_instance_id=bastion, operation=a.operation,
        task=a.task, profile=a.profile))
    print('D11_APP_REQUESTED=' + a.operation + '; use poll with this exact job')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('D11_APP_CONTROLLER_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
