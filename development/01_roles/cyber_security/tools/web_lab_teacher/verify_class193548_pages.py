"""Verify real teacher/student progress pages without exporting bearer URLs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import parse_qs, urlsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=('teacher', 'student'))
    args = parser.parse_args()
    import boto3
    account = '170126527713' if args.role == 'teacher' else '965244652544'
    if boto3.client('sts').get_caller_identity()['Account'] != account:
        raise ValueError('Selected role requires its own AWS account')
    home = Path.home(); base = home / 'jdu-web-class193548'; kit = base / 'cross-account-delivery-v1'
    if hashlib.sha256((kit / 'web_progress.py').read_bytes()).hexdigest() != 'a966bbe49eefdb4fc6f9ca1dc39d930532992490923fde155caf3ed5a5aed6a4':
        raise ValueError('Accepted progress client changed')
    sys.path.insert(0, str(kit)); import web_progress as client
    path = (home / '.jdu-web-teacher/teacher.credentials.json' if args.role == 'teacher' else
        base / 'student-delivery-renewal-20261022/received/own-student.credentials.json')
    config = client.private_json(path)
    if (config['api_base_url'] != 'https://7ilp8ph6ki.execute-api.us-east-1.amazonaws.com'
            or config['fixed_ingress_ipv4'] != '50.16.41.7' or config['release_id'] != 'web-2026-10-r1'
            or (args.role == 'student' and config['lab_id'] != 'class193548-test1')):
        raise ValueError('Intended Class teacher and student required')
    work = base / 'progress-pages-20261022'; work.mkdir(mode=0o700, exist_ok=True)
    output = work / (args.role + '.public.json')
    if output.exists():
        raise ValueError('Completed page acceptance retained')
    session_path = work / (args.role + '.session.private.json')
    if session_path.exists():
        session = client.private_json(session_path)
    else:
        teacher = args.role == 'teacher'
        session = client.request(config, '/api/web/' + ('admin' if teacher else 'student') + '/session',
            {} if teacher else {'lab_id': config['lab_id']}, config['admin_key'] if teacher else config['lab_token'],
            fixed=not teacher)
        client.save_private(session_path, session)
    url = urlsplit(session['url'])
    if (url.scheme != 'https' or url.netloc != '7ilp8ph6ki.execute-api.us-east-1.amazonaws.com'
            or url.path != '/dashboard' or set(parse_qs(url.query)) != {'session'} or url.fragment
            or not 0 < session['expires_at'] - time.time() <= (1805 if args.role == 'teacher' else 905)):
        raise ValueError('Unexpected or expired private viewing session')
    results = []
    for language in ('ja', 'uz', 'ru'):
        connection = client.PinnedHTTPSConnection(url.hostname, config['fixed_ingress_ipv4'])
        try:
            connection.request('GET', url.path + '?' + url.query + '&lang=' + language)
            response = connection.getresponse(); raw = response.read(2 * 1024 * 1024 + 1)
            if response.status != 200 or len(raw) > 2 * 1024 * 1024 or response.getheader('Cache-Control') != 'no-store':
                raise ValueError('Progress page response differs')
            page = raw.decode(); body = re.search(r'<tbody>(.*?)</tbody>', page, re.S).group(1)
            rows = re.findall(r'<tr>(.*?)</tr>', body, re.S)
            intended = [row for row in rows if 'Lab ID: class193548-test1</small>' in row]
            if (len(intended) != 1 or (args.role == 'student' and len(rows) != 1)
                    or '<html lang="' + language + '"' not in page
                    or '<meta http-equiv="refresh" content="30">' not in page
                    or '<th scope="col">P1</th>' not in page or '<th scope="col">M1</th>' not in page):
                raise ValueError('Progress page identity, language or refresh differs')
            row = intended[0]
            if (row.count('<strong>47 / 47</strong>') != 1 or row.count('<strong>2 / 10</strong>') != 2
                    or '<td>0 / 2</td>' not in row or config.get('lab_token', '\x00') in page
                    or config.get('admin_key', '\x00') in page or re.search(r'i-[0-9a-f]{17}', page)):
                raise ValueError('Current results or privacy scope differ')
            results.append(dict(language=language, http_status=200, cache_control_no_store=True,
                current_foundation_passed=47, foundation_total=47, practice_passed=2, mission_passed=2,
                assessment_checks_each=10, completed_tasks=0, submitted_tasks=2,
                automatic_refresh_seconds=30, own_lab_present=True, lab_token_or_admin_key_visible=False))
            print('CLASS193548_PROGRESS_PAGE_PASS', args.role, language, flush=True)
        finally:
            connection.close()
    client.save_private(output, dict(scope='actual_class193548_progress_pages', role=args.role,
        account=account, lab_id='class193548-test1', deployment_id='3ab82943-031d-4806-b4c0-c0b0e4554006',
        checked_at=datetime.now(timezone.utc).isoformat(), pages=results, all_three_languages_passed=True,
        bearer_urls_exported=False, private_credentials_exported=False, class_ready=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('CLASS193548_PROGRESS_PAGE_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
