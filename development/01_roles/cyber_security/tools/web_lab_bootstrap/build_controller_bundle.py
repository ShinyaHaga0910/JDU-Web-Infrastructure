"""Build public student control tools; the outer manifest pins this archive."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

BOOTSTRAP=('student_controller.py','inspect_teacher_probe.py','lock_teacher_probe.py','setup_internal_ssh.py',
    'internal_ssh_guest.py','prepare_teacher_probe.py','post_restart_guest.py','network_probe.py',
    'payload_runtime.py','release_validation.py','ssm_node_evidence.py','node_evidence_guest.py')
TEACHER=('web_progress.py','web_commands.py','enroll_five_node_progress.py','progress_enrollment_guest.py',
    'http_task.py','http_task_guest.py','check_http.py','check_dispatch.py','check_bootstrap.py',
    'bootstrap_submission_guest.py','submit_five_node_bootstrap.py')


def bundle(root):
    root=Path(root).resolve();files={}
    for base,names in ((root,BOOTSTRAP),(root.parent/'web_lab_teacher',TEACHER)):
        for name in names:
            p=base/name
            if p.is_symlink() or not p.is_file() or p.stat().st_size>256*1024:raise ValueError('Invalid public controller source')
            files[name]=p.read_bytes()
    manifest=dict(artifact='jdu-web-student-controller',schema_version=1,credentials_included=False,
        student_release_ready=False,class_ready=False,
        files=[dict(path=n,sha256=hashlib.sha256(v).hexdigest(),size_bytes=len(v)) for n,v in sorted(files.items())])
    files['CONTROLLER-MANIFEST.json']=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w',format=tarfile.USTAR_FORMAT) as t:
        for name,data in sorted(files.items()):
            i=tarfile.TarInfo('controller/'+name);i.size=len(data);i.mode=0o600;i.mtime=0
            t.addfile(i,io.BytesIO(data))
    return gzip.compress(out.getvalue(),mtime=0),manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    data,m=bundle(Path(__file__).resolve().parent);Path(a.output).open('xb').write(data)
    print(json.dumps(dict(size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),public_files=len(m['files']),class_ready=False)))
