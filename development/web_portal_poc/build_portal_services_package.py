"""Deterministic source-only package for private enrollment/grade services."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from build_grade_package import FILES as GRADE_FILES, HERE

FILES = {**GRADE_FILES, **{name: HERE / name for name in
    ('portal_enrollment.py', 'portal_enrollment_handler.py', 'portal_preparation.py', 'initial_gateway.py', 'initial_registration.py', 'identity_proof.py')}}


def build(destination):
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
