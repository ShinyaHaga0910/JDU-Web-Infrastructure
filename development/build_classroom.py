"""Assemble the classroom launcher and AWS code packages from one commit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZipFile

DEVELOPMENT = Path(__file__).resolve().parent
ROOT = DEVELOPMENT.parent
PORTAL = DEVELOPMENT / 'web_portal_poc'
ASSESSMENT = DEVELOPMENT / '01_roles/cyber_security/tools/web_lab_assessment'
PACKAGES = (
    (ASSESSMENT / 'build_teacher.py', 'teacher-template.json'),
    (PORTAL / 'build_checker_package.py', 'checker.zip'),
    (PORTAL / 'build_portal_services_package.py', 'portal-services.zip'),
    (PORTAL / 'web/build_web_package.py', 'portal-web.zip'),
)
PORTAL_TEMPLATES = ('teacher-checker.template.json', 'student-checker.template.json',
                    'portal-services.template.json', 'web/portal-web.template.json')


def build(output):
    # The launcher fetches the commit from GitHub, so tracked local edits cannot
    # be included in the ZIPs alongside a launcher for different source bytes.
    subprocess.run(['git', 'diff', '--exit-code', '--quiet', 'HEAD', '--',
                    'development', 'course/curriculum.json'], cwd=ROOT, check=True)
    ref = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if not re.fullmatch('[0-9a-f]{40}', ref):
        raise ValueError('Expected a full Git commit')
    launcher = (DEVELOPMENT / 'setup-classroom.sh').read_text(encoding='utf-8')
    if launcher.count("\nref=''\n") != 1:
        raise ValueError('Cannot pin the classroom launcher')
    output.mkdir(parents=True)
    (output / 'setup-classroom.sh').write_text(
        launcher.replace("\nref=''\n", f"\nref='{ref}'\n"), encoding='utf-8', newline='\n')

    for builder, filename in PACKAGES:
        subprocess.run([sys.executable, '-B', str(builder), '--output', str(output / filename)], check=True)
    for relative in PORTAL_TEMPLATES:
        template = PORTAL / relative
        (output / template.name).write_bytes(template.read_bytes())

    grade_sources = ('registry.py', 'assessment-registry.json', 'grading.py', 'progress_api_v2.py')
    for filename, sources in (
        ('checker.zip', grade_sources + ('remote_guest.py', 'system_observer.py', 'transport.py')),
        ('portal-services.zip', grade_sources),
    ):
        with ZipFile(output / filename) as package:
            for source in sources:
                if package.read(source) != (ASSESSMENT / source).read_bytes():
                    raise ValueError(f'{filename} does not contain the current {source}')
    with ZipFile(output / 'portal-web.zip') as package:
        for source in ('checks.mjs', 'check-labels.json', 'router.mjs', 'teacher-progress.mjs'):
            if package.read(source) != (PORTAL / 'web' / source).read_bytes():
                raise ValueError(f'portal-web.zip does not contain the current {source}')

    manifest = {
        'commit': ref,
        'sha256': {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(output.iterdir())},
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    build(parser.parse_args().output.resolve())
