"""Store an existing Google OAuth client in owner-account Secrets Manager.

Never accepts a secret in argv, environment, files, logs or normal stdin.
Existing secrets are never overwritten. No role/policy or public route changes.
"""
import argparse
import getpass
import hmac
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


class StorageError(ValueError):
    pass


def validate(account, client_id, origin, name):
    u = urlsplit(origin)
    if (not re.fullmatch(r'[0-9]{12}', account or '')
            or not re.fullmatch(r'[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com', client_id or '')
            or u.scheme != 'https' or not u.hostname or u.username or u.password
            or u.port or u.path or u.query or u.fragment
            or not re.fullmatch(r'jdu/web-portal/[a-z0-9-]+/google-oauth', name or '')):
        raise StorageError('Invalid storage selection')


def preflight(sts, client, account, client_id, origin, name):
    validate(account, client_id, origin, name)
    if sts.get_caller_identity()['Account'] != account:
        raise StorageError('Wrong AWS account')
    try:
        client.describe_secret(SecretId=name)
    except client.exceptions.ResourceNotFoundException:
        return
    raise StorageError('Existing secret: refusing overwrite')


def store(client, account, client_id, origin, name, secret, request_token):
    validate(account, client_id, origin, name)
    if (not isinstance(secret, str) or not re.fullmatch(r'GOCSPX-[A-Za-z0-9_-]{16,256}', secret)
            or not re.fullmatch(r'[a-f0-9]{32}', request_token or '')):
        raise StorageError('Invalid credential format')
    document = {'schema_version': 1, 'client_id': client_id, 'client_secret': secret,
                'redirect_uri': origin + '/auth/callback'}
    result = client.create_secret(Name=name, ClientRequestToken=request_token,
        Description='WEB-PORTAL-001 student Google login; existing credential only',
        SecretString=json.dumps(document, separators=(',', ':')),
        Tags=[{'Key': 'Purpose', 'Value': 'WEB-PORTAL-001'}, {'Key': 'Owner', 'Value': 'JDU'}])
    arn, version = result['ARN'], result['VersionId']
    if not arn.startswith(f'arn:aws:secretsmanager:us-east-1:{account}:secret:{name}-'):
        raise StorageError('Unexpected storage receipt')
    # Read exactly the created version, never print its contents.
    saved = client.get_secret_value(SecretId=arn, VersionId=version)
    if saved.get('VersionId') != version or not isinstance(saved.get('SecretString'), str):
        raise StorageError('Stored version could not be verified')
    try:
        data = json.loads(saved['SecretString'])
    except (ValueError, TypeError):
        raise StorageError('Stored version could not be verified') from None
    if (type(data) is not dict or set(data) != set(document)
            or any(data.get(k) != v for k, v in document.items() if k != 'client_secret')
            or not isinstance(data.get('client_secret'), str)
            or not hmac.compare_digest(data['client_secret'], secret)):
        raise StorageError('Stored version could not be verified')
    return {'stored': True, 'readback_verified': True, 'secret_arn': arn,
            'version_id': version, 'schema_version': 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-account', required=True)
    parser.add_argument('--client-id', required=True)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--secret-name', required=True)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    import boto3
    import os
    import uuid
    s = boto3.client('secretsmanager', region_name='us-east-1')
    preflight(boto3.client('sts', region_name='us-east-1'), s, args.expected_account,
              args.client_id, args.origin, args.secret_name)
    if not args.apply:
        print('PLAN_ONLY: new encrypted secret; no overwrite, policy changes or public access')
        return
    if not sys.stdin.isatty() or args.receipt.exists():
        raise StorageError('Interactive terminal and a new receipt path are required')
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    fd = os.open(args.receipt, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump({'phase': 'prepared', 'request_token': token, 'secret_name': args.secret_name}, out)
    secret = getpass.getpass('Existing Google client secret (hidden): ')
    result = store(s, args.expected_account, args.client_id, args.origin, args.secret_name, secret, token)
    secret = None
    args.receipt.write_text(json.dumps({'phase': 'stored-and-verified', **result}, indent=2))
    print('GOOGLE_OAUTH_STORED_AND_VERIFIED')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Unknown-outcome failures must be inspected before retry; no cleanup,
        # overwrite, SDK error text or traceback containing credential arguments.
        raise SystemExit('Storage did not complete verification. Inspect the private receipt and secret metadata; no overwrite was attempted.') from None
