"""Existing synthetic API lab only: latest per-task progress and scoped dashboards."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from urllib.parse import urlsplit

import web_progress as client
from progress_api import DynamoStore


def main():
    import boto3
    root = Path.home() / '.jdu-web-teacher'
    teacher = client.private_json(root / 'teacher.credentials.json')
    student = client.private_json(root / 'private/api-smoke.credentials.json')
    deployment = client.private_json(root / 'private/api-smoke-deployment.json')
    if student['lab_id'] != 'api-smoke-20261015' or deployment['lab_id'] != student['lab_id']:
        raise ValueError('Only the existing synthetic API lab may be used')
    cfn = boto3.client('cloudformation', region_name='us-east-1')
    stack = cfn.describe_stacks(StackName='jdu-web-progress-2026')['Stacks'][0]
    if stack['StackStatus'] != 'UPDATE_COMPLETE':
        raise ValueError('Wait for the reviewed Web update')
    outputs = {x['OutputKey']: x['OutputValue'] for x in stack['Outputs']}
    store = DynamoStore(outputs['TableName'])
    actual_before = store.get('LAB#teacher-five-probe', 'META')
    cases = {}

    def report(mission, status):
        return dict(schema_version=1, kind='assessment', mission_id=mission,
            lab_id=student['lab_id'], release_id=student['release_id'],
            deployment_id=deployment['deployment_id'], request_id=str(uuid.uuid4()),
            checks=[dict(id='FIXTURE_TRACKING_ONLY', role='repo',
                         instance_id=deployment['instances']['repo'], status=status)])

    passed = report('P1', 'PASS')
    first = client.submit(student, passed)
    failed = report('M1', 'FAIL')
    client.submit(student, failed)
    unknown = report('P1', 'UNKNOWN')
    latest_receipt = client.submit(student, unknown)
    assert client.submit(student, passed) == first
    assert client.submit(student, unknown) == latest_receipt
    cases['exact_retry_and_old_retry_do_not_replace_latest'] = True
    p1 = store.get('LAB#' + student['lab_id'], 'LATEST#P1')
    m1 = store.get('LAB#' + student['lab_id'], 'LATEST#M1')
    assert p1['request_id'] == unknown['request_id'] and p1['unknown'] == 1
    assert m1['request_id'] == failed['request_id'] and m1['passed'] == 0
    cases['per_task_latest_results_kept_independently'] = True
    cases['later_unknown_replaces_pass'] = True
    assert actual_before == store.get('LAB#teacher-five-probe', 'META')
    cases['actual_five_node_registration_and_47_checks_retained'] = True

    def reject(path, body, secret, status):
        try:
            client.request(student, path, body, secret)
        except client.ProgressError as exc:
            assert 'HTTP ' + str(status) in str(exc)
        else:
            raise AssertionError('Expected authenticated rejection')

    changed = copy.deepcopy(passed); changed['checks'][0]['status'] = 'FAIL'
    reject('/api/web/submit', changed, student['lab_token'], 409)
    reject('/api/web/link-email', dict(lab_id=student['lab_id'], student_email='fixture@example.invalid'), student['lab_token'], 400)
    reject('/api/web/link-email', dict(lab_id='teacher-five-probe', student_email='fixture.api-smoke@jdu.uz'), student['lab_token'], 401)
    cases['changed_retry_other_lab_and_invalid_email_rejected'] = True
    linked = client.request(student, '/api/web/link-email',
        dict(lab_id=student['lab_id'], student_email='fixture.api-smoke@jdu.uz'), student['lab_token'])
    assert linked == dict(ok=True, lab_id=student['lab_id'], email_linked=True)
    cases['synthetic_jdu_email_link_without_echo'] = True

    host = urlsplit(teacher['api_base_url']).hostname
    for role in ('teacher', 'student'):
        config = teacher if role == 'teacher' else student
        session = client.request(config, '/api/web/' + ('admin' if role == 'teacher' else 'student') + '/session',
            {} if role == 'teacher' else {'lab_id': student['lab_id']},
            config['admin_key'] if role == 'teacher' else config['lab_token'])
        client.save_private(root / ('private/progress-tracking-v2-' + role + '-' + str(uuid.uuid4()) + '.session.json'), session)
        url = urlsplit(session['url'])
        assert url.scheme == 'https' and url.hostname == host and url.path == '/dashboard'
        for language in ('ja', 'uz', 'ru'):
            conn = client.PinnedHTTPSConnection(host, teacher['fixed_ingress_ipv4'])
            conn.request('GET', url.path + '?' + url.query + '&lang=' + language)
            response = conn.getresponse(); page = response.read(2*1024*1024).decode(); conn.close()
            assert response.status == 200 and '<html lang="' + language + '"' in page
            assert 'fixture.api-smoke@jdu.uz' in page and 'P1' in page and 'M1' in page and 'UNKNOWN' in page
            assert student['lab_token'] not in page and teacher['admin_key'] not in page
            assert all(instance not in page for instance in deployment['instances'].values())
            assert ('teacher-five-probe' in page) == (role == 'teacher')
        cases[role + '_three_language_dashboard_scope_and_no_host_ids'] = True
    result = dict(scope='live_synthetic_tracking_api_not_mission_or_class_acceptance',
        checked_at=datetime.now(timezone.utc).isoformat(), cases=cases, all_passed=all(cases.values()),
        existing_credentials_reused=True, actual_student_emails_used=False, class_ready=False)
    output = Path.home() / 'jdu-web-capture-20261015/progress-tracking-v2.public.json'
    client.save_private(output, result)
    print('WEB_PROGRESS_TRACKING_ACCEPTANCE=' + json.dumps(result, separators=(',', ':')))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('WEB_PROGRESS_TRACKING_CHECK_STOPPED=' + type(exc).__name__)
        raise SystemExit(2)
