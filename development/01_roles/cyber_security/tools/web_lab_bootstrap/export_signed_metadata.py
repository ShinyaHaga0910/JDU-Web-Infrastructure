"""Export public signed metadata only; reuse captured package bytes in AWS."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();root=Path(args.root);output=Path(args.output)
    if output.exists(): raise ValueError('Existing signed transfer retained')
    with tarfile.open(output,'x:gz') as archive:
        for path in sorted(root.rglob('*')):
            relative=path.relative_to(root)
            if relative.parts[:2]==('apt','pool') or relative.parts[:3]==('artifacts','python','wheelhouse'): continue
            if path.is_symlink(): raise ValueError('Metadata links are not allowed')
            archive.add(path,arcname='release/'+relative.as_posix(),recursive=False)
    with output.open('rb') as stream: sha=hashlib.file_digest(stream,'sha256').hexdigest()
    print(json.dumps({'name':output.name,'sha256':sha,'size_bytes':output.stat().st_size}))


if __name__=='__main__':main()
