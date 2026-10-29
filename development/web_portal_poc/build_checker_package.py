"""Source-only fixed checker package; no fixtures, passwords or private state."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo
from build_portal_services_package import FILES as SERVICES, HERE

TOOLS = HERE.parent / '01_roles/cyber_security/tools'
FILES = {**SERVICES, **{n: HERE / n for n in ('assessment_command_jobs.py', 'assessment_observation.py',
    'student_checker_handler.py', 'portal_checker_handler.py')}}
for name in ('transport.py', 'network_checks.py', 'db_observer.py', 'system_observer.py',
             'app_probe.py', 'remote_guest.py', 'http_guest_v2.py', 'aws_readiness.py'):
    FILES[name] = TOOLS / 'web_lab_assessment' / name
for name in ('http_task_guest.py', 'http_task.py'):
    FILES[name] = TOOLS / 'web_lab_teacher' / name
for name in ('setup_internal_ssh.py', 'internal_ssh_guest.py', 'inspect_teacher_probe.py'):
    FILES[name] = TOOLS / 'web_lab_bootstrap' / name


def build(destination):
    with ZipFile(destination, 'x', compression=ZIP_DEFLATED, compresslevel=9) as output:
        for name, path in sorted(FILES.items()):
            info = ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, path.read_bytes(), compresslevel=9)
    return hashlib.sha256(Path(destination).read_bytes()).hexdigest()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    print(build(p.parse_args().output))
