"""Build a small deterministic internal Lambda ZIP; never deploy it.

The original registry bytes are copied as-is because their SHA-256 is part of
the existing grading contract. The ZIP contains source only, no credentials,
student records, or generated configuration.
"""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1] / '01_roles/cyber_security/tools'
HERE = Path(__file__).resolve().parent
FILES = {
    **{name: HERE / name for name in ('identity_grade_handler.py', 'identity_grade.py', 'identity_keys.py', 'grade_reader.py', 'status_gateway.py')},
    **{name: ROOT / 'web_lab_assessment' / name for name in
       ('progress_api_v2.py', 'dashboard.py', 'grading.py', 'registry.py', 'assessment-registry.json')},
    'progress_api.py': ROOT / 'web_lab_teacher' / 'progress_api.py',
}


def build(destination):
    """Write a new artifact only; never overwrite an existing file."""
    with ZipFile(destination, 'x', compression=ZIP_DEFLATED, compresslevel=9) as output:
        for name, path in sorted(FILES.items()):
            info = ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, path.read_bytes(), compresslevel=9)
    return hashlib.sha256(Path(destination).read_bytes()).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.output))
