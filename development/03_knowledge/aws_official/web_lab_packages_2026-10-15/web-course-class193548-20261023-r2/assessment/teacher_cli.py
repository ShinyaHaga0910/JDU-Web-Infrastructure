"""Existing teacher credential: classify verification Labs, export raw scores only."""
import argparse
import csv
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'legacy' if (ROOT / 'legacy').is_dir() else ROOT.parent / 'web_lab_teacher'))
from web_progress import private_json, request, save_private
from registry import CONTRACT_ID, CONTRACT_SHA256, MISSIONS, TASKS


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default=str(Path.home() / '.jdu-web-teacher/teacher.credentials.json'))
    sub = p.add_subparsers(dest='command', required=True)
    classify = sub.add_parser('context')
    classify.add_argument('--lab-id', required=True); classify.add_argument('--deployment-id', required=True)
    classify.add_argument('--context', choices=('verification', 'course'), required=True)
    export = sub.add_parser('export'); export.add_argument('--output', required=True)
    export.add_argument('--csv', action='store_true')
    a = p.parse_args(); os.umask(0o077)
    config = private_json(a.config)
    if a.command == 'context':
        result = request(config, '/api/web/admin/assessment-context', dict(lab_id=a.lab_id,
            deployment_id=a.deployment_id, context=a.context, contract_id=CONTRACT_ID), config['admin_key'], fixed=False)
        print(json.dumps(result)); return
    rows, after, cursors = [], None, set()
    while True:
        page = request(config, '/api/web/admin/grades', {'after': after} if after else {}, config['admin_key'], fixed=False)
        if page['contract_sha256'] != CONTRACT_SHA256 or page['raw_maximum'] != 62:
            raise ValueError('Wrong teacher grading registry')
        rows += page['students']; after = page['next_after']
        if not after:
            break
        if after in cursors:
            raise ValueError('Repeated export cursor')
        cursors.add(after)
    if not a.csv:
        save_private(a.output, dict(contract_id=CONTRACT_ID, contract_sha256=CONTRACT_SHA256,
            raw_maximum=62, normalized_course_points_included=False, students=rows))
    else:
        header = ['lab_id', 'known_raw_points', 'raw_maximum', 'fully_evaluated', 'current_unresolved', 'missing']
        for mid in MISSIONS:
            header += [mid + '_earned', mid + '_max', mid + '_request_id', mid + '_received_at']
        with os.fdopen(os.open(a.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w', newline='') as stream:
            writer = csv.writer(stream); writer.writerow(header)
            for row in rows:
                values = [row['lab_id'], row['raw_earned'], 62, row['fully_evaluated'],
                          ' '.join(row['current_unresolved']), ' '.join(row['missing_or_unresolved'])]
                for mid in MISSIONS:
                    chosen = row['missions'][mid]['selected']
                    values += [chosen['raw_earned'] if chosen else '', TASKS[mid]['raw_points_max'],
                               chosen['request_id'] if chosen else '', chosen['received_at'] if chosen else '']
                writer.writerow(values)
    print('D11_RAW_EXPORT_SAVED; course Labs=' + str(len(rows)) + '; no 25-point conversion; verification Labs excluded')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('D11_TEACHER_COMMAND_STOPPED=' + type(exc).__name__); raise SystemExit(2)
