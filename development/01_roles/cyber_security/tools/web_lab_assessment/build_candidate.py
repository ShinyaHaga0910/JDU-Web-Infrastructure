"""Deterministic D11 candidate; explicit public sources and exact legacy dependencies."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

from freeze_registry import application_bundle

ROOT = Path(__file__).resolve().parent
FILES = ('registry.py', 'grading.py', 'dashboard.py', 'progress_api_v2.py', 'network_checks.py', 'db_observer.py',
         'system_observer.py', 'app_probe.py', 'remote_guest.py', 'transport.py', 'aws_readiness.py',
         'assessment_check.py', 'database_secret.py', 'build_teacher.py', 'upgrade_teacher.py', 'README.md',
         'assessment-registry.json', 'candidate_install.py', 'teacher_cli.py', 'http_guest_v2.py')
TEACHER = ('progress_api.py', 'build_template.py', 'web_progress.py', 'check_http.py', 'http_task.py',
           'http_task_guest.py', 'bootstrap_submission_guest.py', 'check_bootstrap.py', 'submit_five_node_bootstrap.py')
BOOTSTRAP = ('setup_internal_ssh.py', 'internal_ssh_guest.py', 'release_validation.py', 'payload_runtime.py')


def bundle():
    files = {name: (ROOT / name).read_bytes() for name in FILES}
    for folder, names in (('web_lab_teacher', TEACHER), ('web_lab_bootstrap', BOOTSTRAP)):
        for name in names:
            files['legacy/' + name] = (ROOT.parent / folder / name).read_bytes()
    files['legacy/bootstrap_inspection.py'] = (ROOT.parent / 'web_lab_bootstrap/inspect_teacher_probe.py').read_bytes()
    app, manifest = application_bundle()
    registry = json.loads(files['assessment-registry.json'])
    if manifest != registry['application_manifest'] or hashlib.sha256(app).hexdigest() != registry['application_archive_sha256']:
        raise ValueError('Application changed after the registry was frozen; explicitly freeze a new candidate before building')
    files['catalog-app.tar.gz'] = app
    manifest = dict(schema_version=1, artifact='jdu-web-d11', scope='candidate_62_raw_points',
                    contract_id=registry['contract_id'], contract_sha256=hashlib.sha256(files['assessment-registry.json']).hexdigest(),
                    raw_points_max=62, credentials_included=False, class_ready=False,
                    files=[dict(path=n, size_bytes=len(v), sha256=hashlib.sha256(v).hexdigest()) for n, v in sorted(files.items())])
    files['D11-MANIFEST.json'] = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w', format=tarfile.USTAR_FORMAT) as archive:
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo('jdu-web-d11/' + name)
            info.size = len(data); info.mode = 0o644; info.mtime = 0; info.uid = info.gid = 0; info.uname = info.gname = 'root'
            archive.addfile(info, io.BytesIO(data))
    return gzip.compress(output.getvalue(), mtime=0), manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', required=True)
    a = p.parse_args(); data, manifest = bundle()
    with Path(a.output).open('xb') as stream:
        stream.write(data)
    print(json.dumps(dict(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
                         contract_sha256=manifest['contract_sha256'], file_count=len(manifest['files']), class_ready=False)))
