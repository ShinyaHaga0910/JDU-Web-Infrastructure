"""Publish signed software and use existing teacher grading authorization."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True
from release_tools import checked_archive, digest, encoded, parse, read, save, tree, verifier, verify

ROOT = Path(__file__).resolve().parent


def store(s3, bucket, key, raw, owner):
    try:
        old = s3.get_object(Bucket=bucket, Key=key, ExpectedBucketOwner=owner)
    except s3.exceptions.ClientError as exc:
        if exc.response['Error']['Code'] not in ('NoSuchKey', '404'):
            raise
    else:
        if old.get('ServerSideEncryption') != 'AES256' or old['Body'].read(len(raw) + 1) != raw:
            raise ValueError('Existing immutable publication differs')
        return
    s3.put_object(Bucket=bucket, Key=key, ExpectedBucketOwner=owner, Body=raw, IfNoneMatch='*',
        ServerSideEncryption='AES256', Metadata={'sha256': digest(raw)}, ContentType='application/octet-stream')
    result = s3.get_object(Bucket=bucket, Key=key, ExpectedBucketOwner=owner)
    if result.get('ServerSideEncryption') != 'AES256' or result['Body'].read(len(raw) + 1) != raw:
        raise ValueError('Publication GET differs')


def publish(context, session, archive_path, output):
    release = context['release']
    owner = release['teacher_account']
    raw, signature = read(archive_path), read(str(archive_path) + '.asc')
    verifier(context['root']).verify_signature(raw, signature,
        read(context['root'] / 'package-signing-public.asc'), context['fingerprint'])
    if checked_archive(raw) != tree(context['root']):
        raise ValueError('Archive differs from the verified release tree')
    bucket = context['foundation']['core']['manifest']['bootstrap']['bucket']
    s3 = session.client('s3', region_name=release['region'])
    block = s3.get_public_access_block(Bucket=bucket, ExpectedBucketOwner=owner)['PublicAccessBlockConfiguration']
    if not all(block.get(k) is True for k in ('BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets')):
        raise ValueError('Keep all public access blocked')
    prefix = 'distributions/' + release['distribution_id'] + '/'
    assets = {'jdu-web-course.tar.gz': raw, 'jdu-web-course.tar.gz.asc': signature,
              'package-signing-public.asc': read(context['root'] / 'package-signing-public.asc')}
    result = dict(scope='web_course_private_publication', distribution_id=release['distribution_id'],
        release_sha256=context['sha256'], class_id=release['class_id'], teacher_account=owner,
        bucket=bucket, archive_sha256=digest(raw), archive_size_bytes=len(raw),
        expires_at=release['expires_at'], raw_maximum=62, distribution_ready=True, class_ready=False,
        public_access_enabled=False, credentials_included=False, aws_resources_created=False,
        objects=[dict(key=prefix + k, sha256=digest(v), size_bytes=len(v)) for k, v in assets.items()])
    for name, value in assets.items():
        store(s3, bucket, prefix + name, value, owner)
    store(s3, bucket, prefix + 'publication.json', encoded(result), owner)
    save(output, encoded(result))
    print('WEB_COURSE_PUBLISHED_PRIVATE; 4 immutable objects; GET verified; original state/credentials retained')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('publish', 'software-links', 'context', 'export'))
    parser.add_argument('--trusted-fingerprint', required=True)
    parser.add_argument('--archive')
    parser.add_argument('--output', required=True)
    parser.add_argument('--config', default=str(Path.home() / '.jdu-web-teacher/teacher.credentials.json'))
    parser.add_argument('--lab-id')
    parser.add_argument('--deployment-id')
    parser.add_argument('--context', choices=('verification', 'course'))
    parser.add_argument('--csv', action='store_true')
    a = parser.parse_args()
    if Path(a.output).exists() or Path(a.output).is_symlink():
        raise ValueError('Choose a new output file before any external action')
    context = verify(ROOT, a.trusted_fingerprint)
    import boto3
    session = boto3.Session(region_name=context['release']['region'])
    if session.client('sts').get_caller_identity()['Account'] != context['release']['teacher_account']:
        raise ValueError('Use the teacher individual CloudShell')
    if a.command == 'publish':
        if not a.archive:
            raise ValueError('Signed public archive required')
        publish(context, session, Path(a.archive), Path(a.output))
        return
    if a.command == 'software-links':
        bucket = context['foundation']['core']['manifest']['bootstrap']['bucket']
        prefix = 'distributions/' + context['release']['distribution_id'] + '/'
        s3 = session.client('s3'); owner = context['release']['teacher_account']
        proof = parse(s3.get_object(Bucket=bucket, Key=prefix + 'publication.json', ExpectedBucketOwner=owner)['Body'].read(65536))
        if proof['release_sha256'] != context['sha256']:
            raise ValueError('Publish this exact release first')
        if {r['key'] for r in proof['objects']} != {prefix + n for n in (
                'jdu-web-course.tar.gz', 'jdu-web-course.tar.gz.asc', 'package-signing-public.asc')}:
            raise ValueError('Only the three common software objects may be delivered')
        from release_tools import time_value
        duration = min(3600, int((time_value(context['release']['expires_at']) - datetime.now(timezone.utc)).total_seconds()))
        if duration <= 0:
            raise ValueError('Distribution expired')
        assets = {}
        for row in proof['objects']:
            value = s3.get_object(Bucket=bucket, Key=row['key'], ExpectedBucketOwner=owner)['Body'].read(row['size_bytes'] + 1)
            if digest(value) != row['sha256'] or len(value) != row['size_bytes']:
                raise ValueError('Published software differs')
            assets[row['key'].split('/')[-1]] = dict(sha256=row['sha256'], size_bytes=len(value),
                url=s3.generate_presigned_url('get_object', Params=dict(Bucket=bucket, Key=row['key']), ExpiresIn=duration))
        save(a.output, encoded(dict(software_only=True, expires_in_seconds=duration, assets=assets)))
        print('SOFTWARE_LINKS_SAVED_PRIVATE; public software only; 1 hour; no credential issuance')
        return
    config = parse(read(a.config, private=True))
    m = context['foundation']['core']['manifest']
    if config['api_base_url'] != 'https://' + m['grading']['fqdn'] or config['fixed_ingress_ipv4'] != m['grading']['ipv4']:
        raise ValueError('Use the signed teacher destination')
    command = [sys.executable, '-B', str(ROOT / 'assessment/teacher_cli.py'), '--config', a.config, a.command]
    if a.command == 'context':
        if not all((a.lab_id, a.deployment_id, a.context)):
            raise ValueError('Registered anonymous Lab, deployment and explicit context required')
        command += ['--lab-id', a.lab_id, '--deployment-id', a.deployment_id, '--context', a.context]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode:
            raise ValueError('Teacher context update failed; original state retained')
        save(a.output, result.stdout.encode())
    else:
        command += ['--output', a.output] + (['--csv'] if a.csv else [])
        if subprocess.run(command).returncode:
            raise ValueError('Teacher export failed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('COURSE_TEACHER_STOPPED=' + type(exc).__name__ + '; inspect retained files without repeating issuance')
        raise SystemExit(2)
