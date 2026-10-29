"""Build the private acceptance probe with unchanged assessment registry bytes."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
from build_grade_package import FILES, HERE


def build(destination):
    files = {**FILES, 'teacher_probe_handler.py': HERE / 'teacher_probe_handler.py'}
    with ZipFile(destination, 'x', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, source in sorted(files.items()):
            info = ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes(), compresslevel=9)
    return hashlib.sha256(Path(destination).read_bytes()).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(build(parser.parse_args().output))
