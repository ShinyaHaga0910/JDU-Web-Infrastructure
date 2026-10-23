"""Web progress commands matching the OS/Linux classroom workflow."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

import web_progress as client


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('dashboard', 'my-progress', 'id', 'register', 'submit', 'link-email'):
        q = sub.add_parser(name)
        default = Path.home() / ('.jdu-web-teacher/teacher.credentials.json' if name == 'dashboard'
                                  else '.jdu-web-student/progress.credentials.json')
        q.add_argument('--config', default=str(default))
        if name in ('dashboard', 'my-progress'):
            q.add_argument('--save-session', help='Save privately instead of displaying the temporary URL')
        if name == 'register':
            q.add_argument('--state', default='/etc/jdu-web/bootstrap.json')
        if name == 'submit':
            q.add_argument('--report', required=True)
            q.add_argument('--receipt', required=True)
    a = p.parse_args(argv)
    os.umask(0o077)
    if a.command == 'id':
        public = Path('/etc/jdu-web/bootstrap.json')
        config = json.loads(public.read_text()) if public.is_file() else client.private_json(a.config)
        print(config['lab_id'])
        return
    config = client.private_json(a.config)
    if a.command in ('dashboard', 'my-progress'):
        teacher = a.command == 'dashboard'
        result = client.request(config, '/api/web/admin/session' if teacher else '/api/web/student/session',
            {} if teacher else {'lab_id': config['lab_id']}, config['admin_key'] if teacher else config['lab_token'], fixed=not teacher)
        # Validate the exact destination before displaying or saving a bearer URL.
        from urllib.parse import urlsplit, parse_qs
        url = urlsplit(result['url']); base = urlsplit(config['api_base_url'])
        if (url.scheme != 'https' or url.netloc != base.netloc or url.path != '/dashboard'
                or set(parse_qs(url.query)) != {'session'} or url.fragment):
            raise ValueError('Unexpected dashboard destination')
        if a.save_session:
            client.save_private(a.save_session, result)
            print('DASHBOARD_SESSION_SAVED; temporary private URL not displayed')
        else:
            print(result['url'])
    elif a.command == 'register':
        result = client.register(config, json.loads(Path(a.state).read_text()))
        print('REGISTERED Lab ID: ' + result['lab_id'])
    elif a.command == 'submit':
        report = json.loads(Path(a.report).read_text())
        result = client.submit(config, report)
        path = Path(a.receipt)
        if path.exists():
            if client.private_json(path) != result:
                raise ValueError('Existing receipt differs')
        else:
            client.save_private(path, result)
        print('SUBMITTED request_id=' + result['request_id'])
    else:
        if not sys.stdin.isatty():
            raise ValueError('Enter the student email in an interactive terminal')
        email = input('JDU Classroom email (@jdu.uz): ').strip().lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@jdu[.]uz", email):
            raise ValueError('Use a JDU Classroom email')
        print('Teacher and your own progress page will show: ' + email)
        if input('Confirm this email (Yes): ').strip() != 'Yes':
            raise ValueError('Email confirmation cancelled; nothing transmitted')
        result = client.request(config, '/api/web/link-email', dict(lab_id=config['lab_id'], student_email=email), config['lab_token'])
        if result != dict(ok=True, lab_id=config['lab_id'], email_linked=True):
            raise ValueError('Email receipt differs')
        print('EMAIL_LINKED; no tasks or existing results were reset')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Local checking and transmission are separate; callers retain their local
        # result/exit code and pending original report when this command fails.
        print('WEB_PROGRESS_STOPPED=' + type(exc).__name__ + '; pending local report retained', file=sys.stderr)
        raise SystemExit(2)
