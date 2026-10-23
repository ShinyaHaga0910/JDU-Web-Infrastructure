"""Store a verified D08 release in its existing private teacher bucket.

No bucket policy, ACL, IAM, public access, EC2, or student credential changes.
Existing object names are never overwritten; identical bytes are idempotent.
"""
import argparse
import io
import json
import os
from pathlib import Path
import sys
import tarfile

sys.dont_write_bytecode = True
from distribution import account, digest, read, save_json, verify


def archive_matches(root, data):
    expected = {p.relative_to(root).as_posix(): read(p, 4 * 1048576) for p in root.rglob('*') if p.is_file()}
    observed = {}; total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive:
            if (not member.isfile() or not member.name.startswith('jdu-web-distribution/')
                    or member.size < 0 or member.size > 4 * 1048576 or len(observed) >= 100):
                raise ValueError('Unexpected publication archive entry')
            name = member.name.removeprefix('jdu-web-distribution/')
            total += member.size
            if name not in expected or name in observed or total > 4 * 1048576:
                raise ValueError('Unexpected publication archive inventory')
            observed[name] = archive.extractfile(member).read()
    if observed != expected:
        raise ValueError('Archive does not contain the verified distribution')


def store(s3, bucket, key, data, owner):
    try:
        old = s3.get_object(Bucket=bucket, Key=key, ExpectedBucketOwner=owner)
    except s3.exceptions.ClientError as exc:
        if exc.response['Error']['Code'] not in {'NoSuchKey', '404'}:
            raise
    else:
        if old['Body'].read(len(data) + 1) != data:
            raise ValueError('Existing immutable publication differs; choose a new release ID')
        return
    s3.put_object(Bucket=bucket, Key=key, Body=data, ExpectedBucketOwner=owner,
        IfNoneMatch='*', ServerSideEncryption='AES256', ContentType='application/octet-stream',
        Metadata={'sha256': digest(data)})
    result = s3.get_object(Bucket=bucket, Key=key, ExpectedBucketOwner=owner)
    if result['Body'].read(len(data) + 1) != data or result.get('ServerSideEncryption') != 'AES256':
        raise ValueError('Private publication GET or encryption differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--trusted-fingerprint', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    context = verify(args.root, args.trusted_fingerprint)
    import boto3
    session = boto3.Session(region_name=context['release']['region'])
    owner = context['release']['teacher_account']
    account(session, owner)
    data = read(args.archive, 4 * 1048576)
    signature = read(str(args.archive) + '.asc', 65536)
    from distribution import load_module
    validation = load_module('jdu_publication_signature_validation', args.root / 'core/release_validation.py')
    validation.verify_signature(data, signature, read(args.root / 'package-signing-public.asc'), args.trusted_fingerprint)
    archive_matches(args.root, data)
    bucket = context['core']['manifest']['bootstrap']['bucket']
    s3 = session.client('s3')
    blocked = s3.get_public_access_block(Bucket=bucket, ExpectedBucketOwner=owner)['PublicAccessBlockConfiguration']
    if not all(blocked.get(k) is True for k in ('BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets')):
        raise ValueError('Use the existing fully private teacher bucket')
    prefix = 'distributions/' + context['release']['distribution_id'] + '/'
    files = {'jdu-web-distribution.tar.gz': data, 'jdu-web-distribution.tar.gz.asc': signature,
        'package-signing-public.asc': read(args.root / 'package-signing-public.asc')}
    inventory = [dict(key=prefix + name, sha256=digest(value), size_bytes=len(value)) for name, value in files.items()]
    result = dict(scope='d08_private_distribution_publication', distribution_id=context['release']['distribution_id'],
        teacher_account=owner, class_id=context['release']['class_id'], bucket=bucket,
        distribution_sha256=context['release_sha256'], expires_at=context['release']['expires_at'],
        archive_sha256=digest(data), objects=inventory, distribution_ready=True, class_ready=False,
        public_access_enabled=False, student_credentials_changed=False, aws_resources_created=False)
    for name, value in files.items():
        store(s3, bucket, prefix + name, value, owner)
    store(s3, bucket, prefix + 'publication.json', (json.dumps(result, sort_keys=True, indent=2) + '\n').encode(), owner)
    save_json(args.output, result)
    print('D08_DISTRIBUTION_PUBLISHED_PRIVATE; signed objects GET verified; student state and credentials unchanged')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('DISTRIBUTION_PUBLICATION_STOPPED=' + type(exc).__name__ + '; retain immutable objects for inspection')
        raise SystemExit(2)
