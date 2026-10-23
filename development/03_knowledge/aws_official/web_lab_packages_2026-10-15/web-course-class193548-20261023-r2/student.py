"""Student-owned CloudShell installation; never recreates servers or credentials."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys

sys.dont_write_bytecode = True
from release_tools import digest, encoded, parse, read, save, tree, verify

ROOT = Path(__file__).resolve().parent
ROLES = {'bastion', 'web', 'dns', 'db', 'repo'}


def personal_directory(path):
    path = Path(path).absolute()
    home = Path.home().absolute()
    relative = path.relative_to(home)
    current = home
    home_info = home.lstat()
    if home.is_symlink() or not stat.S_ISDIR(home_info.st_mode) or home_info.st_uid != os.geteuid():
        raise ValueError('Your own CloudShell home directory is required')
    # CloudShell can initially expose a 0777 home. Close other-user writes before
    # creating personal launchers; do not loosen any permission or change files.
    if home_info.st_mode & 0o077:
        home.chmod(0o700)
    for part in ('', *relative.parts):
        if part:
            current = current / part
        if current.is_symlink():
            raise ValueError('Personal directories cannot be links')
        if not current.exists():
            current.mkdir(mode=0o700)
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ValueError('Use your own protected CloudShell home directory')
    return path


def identity(context, config_path, actual_account):
    config_path = Path(config_path).absolute()
    config_path.relative_to(Path.home())
    raw = read(config_path, private=True)
    config = parse(raw)
    state_path = Path(config['state'])
    state_path.relative_to(Path.home())
    state = parse(read(state_path, private=True))
    baseline_path = Path(config['baseline_plan'])
    baseline_raw = read(baseline_path, private=True)
    baseline = parse(baseline_raw)
    release, foundation = context['release'], context['foundation']
    home = Path.home()
    if (config['scope'] != 'signed_student_candidate_commands'
            or state['account'] != actual_account or actual_account == release['teacher_account']
            or not re.fullmatch('[0-9]{12}', actual_account)
            or not re.fullmatch('[a-z0-9][a-z0-9-]{2,31}', state['lab_id'])
            or state['region'] != release['region'] or state['manifest_sha256'] != release['core_manifest_sha256']
            or state['release_id'] != foundation['core']['manifest']['release_id']
            or state['stack_name'] != 'jdu-web-' + state['lab_id']
            or any(state[k] != baseline[k] for k in ('account', 'stack_id', 'deployment_id'))
            or set(baseline['nodes']) != ROLES
            or baseline_path != Path(str(state_path) + '.baseline.json')
            or config_path != home / '.jdu-web-student' / state['lab_id'] / 'command-state.json'
            or config['pending_directory'] != str(config_path.parent / 'pending')
            or Path(config['bootstrap_tools']) != foundation['controller']
            or Path(config['ssh_enrollment']) != Path(str(state_path) + '.ssh.json.enrolled.public.json')):
        raise ValueError('Wrong personal account, foundation or retained deployment')
    controller = foundation['controller']
    for key, name in (('guest_source', 'post_restart_guest.py'), ('submission_source', 'bootstrap_submission_guest.py')):
        if Path(config[key]) != controller / name or digest(read(config[key])) != config[key + '_sha256']:
            raise ValueError('Original signed command configuration differs')
    if digest(read(controller / 'network_probe.py')) != config['network_source_sha256']:
        raise ValueError('Original network observer differs')
    enrollment = parse(read(config['ssh_enrollment'], private=True))
    if enrollment['deployment_id'] != state['deployment_id']:
        raise ValueError('Retain the existing internal SSH enrollment')
    return dict(config=config, state=state, baseline=baseline, binding=dict(
        schema_version=1, scope='personal_signed_course_commands', account=actual_account,
        lab_id=state['lab_id'], deployment_id=state['deployment_id'],
        distribution_sha256=context['sha256'], core_manifest_sha256=release['core_manifest_sha256'],
        contract_sha256=release['contract_sha256'], command_state=str(config_path),
        command_state_sha256=digest(raw), baseline_sha256=digest(baseline_raw),
        trusted_fingerprint=context['fingerprint']))


def current(context, selected, session):
    sys.path[:0] = [str(context['root'] / 'assessment'), str(context['root'] / 'assessment/legacy')]
    from setup_internal_ssh import current_nodes
    from aws_readiness import verify as ready
    clients = {n: session.client(n, region_name='us-east-1') for n in ('ec2', 'cloudformation', 'ssm')}
    nodes = current_nodes(clients['ec2'], clients['cloudformation'], selected['state'], selected['baseline'])
    template = clients['cloudformation'].get_template(StackName=selected['state']['stack_id'], TemplateStage='Original')['TemplateBody']
    if isinstance(template, str):
        template = json.loads(template)
    if not ready(clients['ec2'], clients['cloudformation'], clients['ssm'], selected['state'], template, nodes):
        raise ValueError('Start your original five nodes and retain the approved network and SSM')


def launcher(target):
    return ('#!/bin/sh\nset -eu\nexec python3 -B ' + shlex.quote(str(target / 'kit/student.py'))
            + ' run --binding ' + shlex.quote(str(target / 'binding.private.json')) + ' -- "$@"\n').encode()


def install(context, config_path, target, session, live=current):
    selected = identity(context, config_path, session.client('sts').get_caller_identity()['Account'])
    target = Path(target).absolute() if target else (Path.home() / '.local/share/jdu-web/courses'
        / context['release']['distribution_id'] / selected['state']['lab_id'])
    target.relative_to(Path.home())
    if target.is_relative_to(context['root']):
        raise ValueError('Installation must be outside the signed source tree')
    personal_directory(target.parent)
    binding = selected['binding']
    activation = ('export PATH=' + shlex.quote(str(target / 'bin')) + ':"$PATH"\n').encode()
    source = tree(context['root'])
    expected = dict(source)
    if target.exists() or target.is_symlink():
        personal_directory(target)
        if (parse(read(target / 'binding.private.json', private=True)) != binding
                or tree(target / 'kit') != expected or read(target / 'bin/jdu-web-check', private=True) != launcher(target)
                or read(target / 'activate.sh', private=True) != activation
                or set(p.name for p in target.iterdir()) != {'kit', 'bin', 'binding.private.json', 'activate.sh'}):
            raise ValueError('Existing installation differs; retained without overwrite')
        return target, True
    live(context, selected, session)
    target.mkdir(mode=0o700)
    (target / 'kit').mkdir(mode=0o700)
    for name, data in expected.items():
        path = target / 'kit' / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        save(path, data)
    (target / 'bin').mkdir(mode=0o700)
    save(target / 'binding.private.json', encoded(binding))
    save(target / 'bin/jdu-web-check', launcher(target), 0o700)
    save(target / 'activate.sh', activation)
    return target, False


def run(argv):
    parser = argparse.ArgumentParser(description='Use the signature-bound personal D11 checker')
    parser.add_argument('--binding', required=True)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    a = parser.parse_args(argv)
    path = Path(a.binding).absolute()
    binding = parse(read(path, private=True))
    if path.parent / 'kit' != ROOT:
        raise ValueError('Binding belongs to another installation')
    context = verify(ROOT, binding['trusted_fingerprint'])
    import boto3
    selected = identity(context, binding['command_state'], boto3.client('sts').get_caller_identity()['Account'])
    if selected['binding'] != binding:
        raise ValueError('Original binding changed; keep state and request a reviewed update')
    arguments = a.arguments[1:] if a.arguments[:1] == ['--'] else a.arguments
    if any(s == '--command-state' or s.startswith('--command-state=') for s in arguments):
        raise ValueError('This command uses only your bound configuration')
    return subprocess.run([sys.executable, '-B', str(ROOT / 'assessment/assessment_check.py'), *arguments,
        '--command-state', binding['command_state']]).returncode


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['run']:
        return run(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('verify', 'install'))
    parser.add_argument('--trusted-fingerprint', required=True)
    parser.add_argument('--command-state')
    parser.add_argument('--output')
    a = parser.parse_args(argv)
    context = verify(ROOT, a.trusted_fingerprint)
    if a.command == 'verify':
        print(json.dumps(dict(distribution_id=context['release']['distribution_id'],
            class_id=context['release']['class_id'], teacher_account=context['release']['teacher_account'],
            expires_at=context['release']['expires_at'], raw_maximum=62, distribution_ready=True, class_ready=False)))
        return 0
    if not a.command_state:
        raise ValueError('Specify your existing personal command-state file')
    import boto3
    target, retained = install(context, a.command_state, a.output, boto3.Session(region_name='us-east-1'))
    print('D11_STUDENT_COMMANDS_READY; personal home protected; original state/servers/credentials retained; existing=' + str(retained))
    print('source ' + shlex.quote(str(target / 'activate.sh')))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('COURSE_COMMAND_STOPPED=' + type(exc).__name__ + '; retain existing state and credentials')
        raise SystemExit(2)
