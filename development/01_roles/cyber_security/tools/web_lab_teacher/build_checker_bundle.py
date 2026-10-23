"""Build immutable public checker + fixture archive. Explicit files only."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

from http_task import TASKS

TEACHER_FILES = ('web_progress.py', 'web_commands.py', 'check_dispatch.py', 'check_http.py',
    'http_task.py', 'http_task_guest.py', 'check_bootstrap.py', 'bootstrap_submission_guest.py',
    'submit_five_node_bootstrap.py', 'progress_enrollment_guest.py', 'bind_checker_commands.py', 'STUDENT-CHECKER.md')
BOOTSTRAP_FILES = ('setup_internal_ssh.py', 'internal_ssh_guest.py', 'post_restart_guest.py',
                   'release_validation.py', 'payload_runtime.py')


def bundle(root):
    root = Path(root).resolve()
    files = {}
    for base, names in ((root, TEACHER_FILES), (root.parent / 'web_lab_bootstrap', BOOTSTRAP_FILES)):
        for name in names:
            path = base / name
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
                raise ValueError('Only reviewed regular public source is allowed')
            files[name] = path.read_bytes()
    for spec in TASKS.values():
        files['fixtures/' + Path(spec['file']).name] = spec['body'].encode()
    manifest = dict(schema_version=1, artifact='jdu-web-checker', release_id='web-2026-10-r1',
        scope='student_checker_candidate_web02_only', supported_tasks=['bootstrap', 'P1', 'M1'],
        credentials_included=False, student_release_ready=False, class_ready=False,
        files=[dict(path=n, sha256=hashlib.sha256(v).hexdigest(), size_bytes=len(v)) for n, v in sorted(files.items())])
    files['CHECKER-MANIFEST.json'] = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for name, raw in sorted(files.items()):
            info = tarfile.TarInfo('jdu-web-checker/' + name)
            info.size = len(raw); info.mode = 0o644; info.mtime = 0
            info.uid = info.gid = 0; info.uname = info.gname = 'root'
            tar.addfile(info, io.BytesIO(raw))
    return gzip.compress(data.getvalue(), mtime=0), manifest


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', required=True)
    a = p.parse_args(); data, manifest = bundle(Path(__file__).resolve().parent)
    with Path(a.output).open('xb') as f: f.write(data)
    print(json.dumps(dict(artifact=manifest['artifact'], sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data), file_count=len(manifest['files']), supported_tasks=manifest['supported_tasks'],
        student_release_ready=False, class_ready=False)))


if __name__ == '__main__': main()
