"""Create an isolated, reproducible student status Lambda ZIP; do not deploy."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

HERE = Path(__file__).resolve().parent
FILES = ('student_status_handler.py', 'status.py')


def build(destination):
    with ZipFile(destination, 'x', compression=ZIP_DEFLATED, compresslevel=9) as output:
        for name in FILES:
            info = ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, (HERE / name).read_bytes(), compresslevel=9)
    return hashlib.sha256(Path(destination).read_bytes()).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.output))
