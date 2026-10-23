"""Receive a named public teaching artifact through CloudShell's terminal.

Send base64 lines of at most 2048 characters, followed by JDU_PUBLIC_FILE_END.
Large paste messages disconnect CloudShell; send one short line per paste call.
This is for public code/metadata only, never private keys or credentials.
"""
import argparse
import base64
import hashlib
import os
from pathlib import Path
import re
import sys
import termios


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name',required=True); p.add_argument('--sha256',required=True); p.add_argument('--size',type=int,required=True)
    a=p.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{1,79}',a.name) or not re.fullmatch(r'[0-9a-f]{64}',a.sha256) or not 0<a.size<=2*1024**2:
        raise ValueError('Invalid public artifact bounds')
    os.umask(0o077)
    root=Path.home()/'jdu-web-capture-20261015'; root.mkdir(mode=0o700,exist_ok=True)
    target=root/a.name; partial=root/(a.name+'.part')
    if target.exists() or partial.exists():
        raise ValueError('Existing artifact retained')
    fd=sys.stdin.fileno(); before=termios.tcgetattr(fd); after=list(before); after[3]&=~termios.ECHO
    total=0; sha=hashlib.sha256()
    termios.tcsetattr(fd,termios.TCSANOW,after)
    print('PUBLIC_ARTIFACT_RECEIVER_READY',flush=True)
    try:
        with partial.open('xb') as stream:
            while True:
                line=sys.stdin.readline()
                if not line:
                    raise ValueError('Truncated public artifact')
                line=line.strip()
                if line=='JDU_PUBLIC_FILE_END':
                    break
                if len(line)>2048:
                    raise ValueError('Send one short line per paste')
                data=base64.b64decode(line,validate=True); total+=len(data)
                if total>a.size:
                    raise ValueError('Public artifact exceeds declared size')
                stream.write(data); sha.update(data)
    finally:
        termios.tcsetattr(fd,termios.TCSANOW,before)
    if total!=a.size or sha.hexdigest()!=a.sha256:
        raise ValueError('Public artifact hash or size mismatch')
    # The validated destination is new; no existing file is replaced.
    os.link(partial,target)
    partial.unlink()
    print('PUBLIC_ARTIFACT_VERIFIED '+a.name+' '+sha.hexdigest(),flush=True)


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print('PUBLIC_ARTIFACT_RECEIVE_FAILED='+type(exc).__name__,flush=True)
        raise SystemExit(2)
