"""Actual separate-student WEB-02 fixtures; teacher storage checked separately.

Restores the original Nginx package inventory and repository service after the
test. No authentication credential is issued, rotated, copied, or changed.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

DEPLOYMENT = '3ab82943-031d-4806-b4c0-c0b0e4554006'
MANIFEST = 'a00239fa1cb8efc09d8cad214c6e97f5c99f1436c9549c3f66bf09ea9ee4a3d2'


def main():
    import boto3
    sys.dont_write_bytecode = True
    home = Path.home(); base = home / 'jdu-web-class193548'; work = Path(__file__).resolve().parent
    kit = base / 'cross-account-delivery-v1'; sys.path.insert(0, str(kit))
    for name, pin in {
        'class_student_delivery.py': '1bbaf46daa1eed027e17e422e64ff0af5e8f24791d36df2f2379a57ff652a184',
        'web_progress.py': 'a966bbe49eefdb4fc6f9ca1dc39d930532992490923fde155caf3ed5a5aed6a4',
        'release_validation.py': 'e9aebc2f1ed3d54df70e862e5a9aabe8e08970004106c8a89a6260da9e34096c',
        'enroll_class193548_student.py': 'a3d1443aad2ec349da638df742f539957484ada82c99437b05a0911635fb3fba',
    }.items():
        if hashlib.sha256((kit / name).read_bytes()).hexdigest() != pin:
            raise ValueError('Accepted helper changed')
    import class_student_delivery as delivery
    session = boto3.Session(region_name='us-east-1'); delivery.identity(session, delivery.STUDENT)
    verified = delivery.verified_tools(base / 'student-software-v7/student-tools')
    if verified['manifest_sha256'] != MANIFEST:
        raise ValueError('Wrong signed deployment')
    config_path = home / '.jdu-web-student/class193548-test1/command-state.json'
    config = json.loads(config_path.read_text()); state = json.loads(Path(config['state']).read_text())
    from setup_internal_ssh import current_nodes, remote, save_new
    from enroll_class193548_student import require_nodes
    nodes = current_nodes(session.client('ec2'), session.client('cloudformation'), state,
        json.loads(Path(config['baseline_plan']).read_text())); require_nodes(state, nodes)
    checker = home / '.local/share/jdu-web/class193548-v7-bin/jdu-web-check'
    common = ['--command-state', str(config_path), '--expected-deployment', DEPLOYMENT]
    if (work / 'web02-integration.public.json').exists():
        raise ValueError('Completed fixture acceptance retained')
    stages = []; fixture_installed = False; repo_stopped = False
    def fixture(operation):
        job = work / ('fixture-' + operation + '.job.json')
        subprocess.run(['python3', '-B', str(work / 'run_web_fixture.py'), operation,
            '--job', str(job), *common], check=True, timeout=90)
        for _ in range(120):
            result = subprocess.run(['python3', '-B', str(work / 'run_web_fixture.py'), 'poll',
                '--job', str(job), *common], capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise ValueError('Fixture failed; preserve job and node workspace')
            if 'FIXTURE_JOB=Success' in result.stdout:
                print('CLASS193548_FIXTURE_COMPLETE=' + operation, flush=True)
                return
            time.sleep(5)
        raise ValueError('Fixture still pending; inspect saved job before continuing')
    def assess(stage):
        output = work / ('web02-' + stage + '.public.json')
        result = subprocess.run(['python3', '-B', str(work / 'acceptance_web02_stage.py'), stage,
            *common, '--checker-command', str(checker), '--output', str(output), '--defer-teacher-storage'],
            capture_output=True, text=True, timeout=300)
        (work / ('web02-' + stage + '.log')).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise ValueError('Fixture expectation failed; inspect retained stage log')
        value = json.loads(output.read_text()); stages.append(value)
        print('CLASS193548_WEB02_STAGE=' + stage + ' ' + str([(r['task'], r['passed'], r['total'])
            for r in value['results']]), flush=True)
    def repo_service(operation):
        source = ("import json,subprocess\nfrom pathlib import Path\n"
            "c=json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())\n"
            "assert c['deployment_id']==" + repr(DEPLOYMENT) + " and c['instance_id']=="
            + repr(nodes['repo']['instance_id']) + " and c['role']=='repo'\n"
            "subprocess.run(['systemctl'," + repr(operation) + ",'nginx'],check=True)\n"
            "active=subprocess.run(['systemctl','is-active','--quiet','nginx']).returncode==0\n"
            "assert active is " + str(operation == 'start') + "\nprint(json.dumps({'expected_state_verified':True}))\n")
        response = remote(session.client('ssm'), nodes['repo']['instance_id'], source.encode(), {})
        if response['expected_state_verified'] is not True:
            raise ValueError('Repository service operation unverified')
    try:
        assess('initial'); fixture('install'); fixture_installed = True
        fixture('practice'); assess('practice')
        fixture('wrong'); assess('wrong')
        fixture('mission'); assess('mission')
        fixture('loopback'); assess('loopback')
        fixture('normal'); assess('normal')
        repo_stopped = True
        try:
            repo_service('stop'); assess('repo_unavailable')
        finally:
            repo_service('start'); repo_stopped = False
        assess('signed_command')
    finally:
        if repo_stopped:
            repo_service('start')
        if fixture_installed:
            fixture('restore')
    assess('restored')
    save_new(work / 'web02-integration.public.json', dict(scope='actual_separate_student_web02_fixtures',
        deployment_id=DEPLOYMENT, lab_id=state['lab_id'], checked_at=datetime.now(timezone.utc).isoformat(),
        stage_count=len(stages), assessment_count=sum(len(s['results']) for s in stages),
        all_fixture_expectations_passed=True, repository_service_restored=True,
        fixture_package_inventory_restored=True, teacher_storage_verification_pending=True,
        new_credentials_created=False, stages=stages, class_ready=False))
    print('CLASS193548_WEB02_ALL_STAGES_ACCEPTED=9 stages / 13 assessments; teacher storage verification pending', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('CLASS193548_WEB02_ACCEPTANCE_STOPPED=' + type(exc).__name__ + '; preserve jobs and fixture evidence', flush=True)
        raise SystemExit(2)
