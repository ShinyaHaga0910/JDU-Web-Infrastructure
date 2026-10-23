"""Teacher-only read-only acceptance of actual reports, grades and fixture exclusion."""
import argparse
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys


def plain(value):
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise ValueError('Canonical report numbers must be integral')
        return int(value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', required=True)
    p.add_argument('--expected', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--current-unknown', action='store_true')
    a = p.parse_args()
    import boto3
    if boto3.client('sts').get_caller_identity()['Account'] != '170126527713':
        raise ValueError('Selected teacher verification account only')
    candidate = Path(a.candidate)
    sys.path[:0] = [str(candidate), str(candidate / 'legacy')]
    from progress_api_v2 import AssessmentStore
    from progress_api import encoded, digest
    from grading import project_lab, export_labs
    from registry import MISSIONS, CONTRACT_SHA256
    from web_progress import private_json, request
    resources = boto3.client('cloudformation', region_name='us-east-1').describe_stacks(
        StackName='jdu-web-progress-2026')['Stacks'][0]
    outputs = {v['OutputKey']: v['OutputValue'] for v in resources['Outputs']}
    store = AssessmentStore(outputs['TableName'])
    expected = json.loads(Path(a.expected).read_text())
    for row in expected:
        actual = store.get('LAB#class193548-test1', 'REQUEST#' + row['request_id'])
        if (not actual or actual['body_sha256'] != row['body_sha256']
                or digest(encoded(plain(actual['report']))) != row['body_sha256']
                or digest(encoded(plain(actual['receipt']))) != row['receipt_sha256']):
            raise ValueError('Independent student report/receipt differs in teacher storage')
    lab = store.labs('class193548-test1')[0]
    if lab['assessment_context'] != 'verification' or lab['deployment_id'] != '3ab82943-031d-4806-b4c0-c0b0e4554006':
        raise ValueError('Keep the retained fixture separate from course Labs')
    view = project_lab(lab)
    if view['raw_earned'] != 62 or any(not view['selected'][m]['complete'] for m in MISSIONS):
        raise ValueError('The six complete latest eligible reports must total 62')
    if a.current_unknown:
        if set(view['current_unresolved']) != {'M5', 'M6'} or view['fully_evaluated']:
            raise ValueError('Current health must remain distinct from selected scores')
    elif not view['fully_evaluated'] or not view['complete']:
        raise ValueError('All current mission reports must be complete')
    # This real DynamoDB numeric projection is in memory only. No fixture is
    # reclassified and no test grade enters the course API or exports.
    simulated = copy.deepcopy(lab)
    simulated['assessment_context'] = 'course'
    projected = export_labs([simulated])
    json.dumps(projected)
    if len(projected['students']) != 1 or projected['students'][0]['raw_earned'] != 62:
        raise ValueError('Real DynamoDB numeric score export failed')
    config = private_json(Path.home() / '.jdu-web-teacher/teacher.credentials.json')
    exported = request(config, '/api/web/admin/grades', {}, config['admin_key'], fixed=False)
    if exported['contract_sha256'] != CONTRACT_SHA256 or exported['students']:
        raise ValueError('Verification-only course export must be empty')
    result = dict(exact_report_and_receipt_pairs_verified=len(expected), raw_earned=62, raw_maximum=62,
        mission_points={m: int(view['selected'][m]['raw_earned']) for m in MISSIONS},
        current_unknown=view['current_unresolved'], actual_decimal_export_projection_passed=True,
        verification_context_retained=True, actual_course_export_count=0, database_modified=False,
        grade_request_ids={m: view['selected'][m]['request_id'] for m in MISSIONS})
    with Path(a.output).open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
