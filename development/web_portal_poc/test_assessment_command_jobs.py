"""Moto durable jobs, with fake SSM failures; never connects to real AWS."""
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
import uuid

import boto3
from moto import mock_aws

ROOT = Path(__file__).resolve().parents[1] / '01_roles/cyber_security/tools'
sys.path.insert(0, str(ROOT / 'web_lab_assessment'))
from registry import CONTRACT_SHA256, build_report, canonical_checks
from assessment_command_jobs import CommandJobs, JobDenied, JobBusy, canonical, encoded, key, sha


class Ssm:
    def __init__(self):
        self.meta = SimpleNamespace(config=SimpleNamespace(retries={'total_max_attempts': 1}))
        self.commands, self.sends = [], []
        self.send_error, self.accept_before_error, self.read_error = False, False, False
        self.command_id, self.output = str(uuid.uuid4()), None
        self.list_pages, self.list_calls = None, []
        self.status = 'Success'

    def send_command(self, **kwargs):
        self.sends.append(copy.deepcopy(kwargs))
        if not self.send_error or self.accept_before_error:
            self.commands.append({'CommandId': self.command_id, **copy.deepcopy(kwargs)})
        if self.send_error:
            raise TimeoutError('SYNTHETIC_SECRET_MUST_NOT_BE_LOGGED')
        return {'Command': {'CommandId': self.command_id}}

    def list_commands(self, **kwargs):
        self.list_calls.append(copy.deepcopy(kwargs))
        if self.list_pages:
            index = int(kwargs.get('NextToken', '0'))
            value = {'Commands': self.list_pages[index]}
            if index + 1 < len(self.list_pages):
                value['NextToken'] = str(index + 1)
            return value
        return {'Commands': copy.deepcopy(self.commands)}

    def get_command_invocation(self, **kwargs):
        if self.read_error:
            raise PermissionError('SYNTHETIC_SECRET_MUST_NOT_BE_LOGGED')
        return {**kwargs, 'Status': self.status, 'ResponseCode': 0,
                'StandardOutputContent': self.output,
                'StandardErrorContent': 'SYNTHETIC_SECRET_MUST_NOT_BE_LOGGED'}


class CommandJobsTest(unittest.TestCase):
    def setUp(self):
        self.mock = mock_aws()
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.db = boto3.client('dynamodb', region_name='us-east-1',
            aws_access_key_id='EXAMPLE', aws_secret_access_key='synthetic-test-only')
        self.db.create_table(TableName='jobs', BillingMode='PAY_PER_REQUEST',
            AttributeDefinitions=[{'AttributeName': n, 'AttributeType': 'S'} for n in ('pk', 'sk')],
            KeySchema=[{'AttributeName': 'pk', 'KeyType': 'HASH'}, {'AttributeName': 'sk', 'KeyType': 'RANGE'}])
        self.spec = {'job_id': str(uuid.uuid4()), 'owner_hash': 'a' * 64,
            'account': '123456789012', 'lab_id': 'synthetic-lab',
            'deployment_id': str(uuid.uuid4()), 'run_id': str(uuid.uuid4()),
            'release_id': 'web-2026-10-r1', 'task_id': 'M2', 'contract_sha256': CONTRACT_SHA256,
            'instances': {r: 'i-' + format(i, '017x') for i, r in enumerate(('bastion', 'web', 'dns', 'db', 'repo'), 1)}}
        self.now = int(datetime(2026, 10, 29, 10, 0, tzinfo=timezone.utc).timestamp())
        self.ready, self.preflights = True, []
        self.command_suffix = ''
        self.ssm = Ssm()
        self.jobs = self.new_worker()
        self.ssm.output = json.dumps({'report': self.report()})

    def new_worker(self):
        def preflight(spec):
            self.preflights.append(copy.deepcopy(spec))
            return self.ready
        return CommandJobs(self.db, 'jobs', self.ssm,
            lambda s: 'fixed-teacher-checker ' + s['task_id'] + ' ' + s['run_id'] + self.command_suffix,
            preflight, clock=lambda: self.now)

    def report(self, **updates):
        identity = {k: self.spec[k] for k in ('lab_id', 'release_id', 'deployment_id', 'instances')}
        value = build_report(self.spec['task_id'], identity,
            {k: True for k in canonical_checks(self.spec['task_id'])}, self.spec['run_id'],
            checked_at=datetime.fromtimestamp(self.now, timezone.utc).isoformat())
        value.update(updates)
        return value

    def start(self):
        self.jobs.enqueue(self.spec)
        self.assertEqual(self.jobs.advance(self.spec)['phase'], 'observing')

    def ready_report(self):
        self.start()
        self.assertEqual(self.jobs.advance(self.spec)['phase'], 'report_ready')
        return self.jobs.retained_report(self.spec)

    def test_original_report_and_request_id_survive_worker_recreation(self):
        expected = json.loads(self.ssm.output)['report']
        self.ready_report()
        fresh = self.new_worker()
        actual = fresh.retained_report(self.spec)
        self.assertEqual(actual, expected)
        self.assertIs(type(actual['schema_version']), int)  # Real Dynamo numeric round-trip.
        actual['checks'].clear()
        self.assertEqual(fresh.retained_report(self.spec), expected)
        for _ in range(4):
            self.assertEqual(fresh.advance(self.spec)['phase'], 'report_ready')
            self.assertEqual(fresh.enqueue(self.spec)['phase'], 'report_ready')
        self.assertEqual(len(self.ssm.sends), 1)

    def test_ambiguous_accepted_send_recovers_original_command_without_resend(self):
        self.ssm.send_error = self.ssm.accept_before_error = True
        self.jobs.enqueue(self.spec)
        self.assertEqual(self.jobs.advance(self.spec)['phase'], 'dispatching')
        fresh = self.new_worker()
        self.assertEqual(fresh.advance(self.spec)['phase'], 'observing')
        self.assertEqual(fresh.advance(self.spec)['phase'], 'report_ready')
        self.assertEqual(len(self.ssm.sends), 1)
        self.assertEqual(fresh.get(self.spec)['command_id'], self.ssm.command_id)

    def test_absent_eventually_consistent_command_is_never_a_second_launch(self):
        self.ssm.send_error = True
        self.jobs.enqueue(self.spec)
        self.jobs.advance(self.spec)
        for elapsed in (1, 100, 10000):
            self.now += elapsed
            self.assertEqual(self.new_worker().advance(self.spec)['phase'], 'dispatching')
        self.assertEqual(len(self.ssm.sends), 1)

    def test_concurrent_workers_send_at_most_one_command(self):
        self.jobs.enqueue(self.spec)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: self.new_worker().advance(self.spec), range(2)))
        self.assertEqual(len(self.ssm.sends), 1)
        self.assertIn(self.jobs.current(self.spec)['phase'], ('dispatching', 'observing', 'report_ready'))

    def test_lab_serializes_checks_and_terminal_job_releases_only_its_own_lock(self):
        other = {**copy.deepcopy(self.spec), 'job_id': str(uuid.uuid4()), 'task_id': 'M4', 'run_id': str(uuid.uuid4())}
        self.jobs.enqueue(self.spec)
        with self.assertRaises(JobBusy):
            self.jobs.enqueue(other)
        self.ready_report()
        self.assertEqual(self.jobs.enqueue(other)['phase'], 'queued')
        # Re-reading the old terminal job cannot release the new job's lock.
        self.jobs.advance(self.spec)
        third = {**other, 'job_id': str(uuid.uuid4()), 'run_id': str(uuid.uuid4())}
        with self.assertRaises(JobBusy):
            self.jobs.enqueue(third)

    def test_stopped_or_unavailable_preflight_never_launches_or_erases_job(self):
        self.ready = False
        with self.assertRaises(JobDenied):
            self.jobs.enqueue(self.spec)
        self.assertIsNone(self.jobs.get(self.spec))
        self.ready = True
        self.jobs.enqueue(self.spec)
        self.ready = False
        with self.assertRaises(JobDenied):
            self.jobs.advance(self.spec)
        self.assertEqual(self.jobs.current(self.spec)['phase'], 'queued')
        self.assertEqual(self.ssm.sends, [])

    def test_source_change_does_not_replace_a_retained_pending_command(self):
        self.jobs.enqueue(self.spec)
        self.command_suffix = ' new-version'
        with self.assertRaises(JobDenied):
            self.jobs.advance(self.spec)
        self.assertEqual(self.ssm.sends, [])
        self.command_suffix = ''
        self.assertEqual(self.jobs.advance(self.spec)['phase'], 'observing')

    def test_temporarily_unreadable_invocation_keeps_the_existing_handle(self):
        self.start()
        self.ssm.read_error = True
        for _ in range(3):
            self.assertEqual(self.jobs.advance(self.spec)['phase'], 'observing')
        self.ssm.read_error = False
        self.assertEqual(self.jobs.advance(self.spec)['phase'], 'report_ready')
        self.assertEqual(len(self.ssm.sends), 1)

    def test_accepted_command_recovers_without_recompiling_after_worker_update(self):
        self.start()
        self.jobs.build_command = lambda spec: (_ for _ in ()).throw(ValueError('No recompilation'))
        self.assertEqual(self.jobs.advance(self.spec)['phase'], 'report_ready')
        self.assertEqual(self.jobs.retained_report(self.spec), json.loads(self.ssm.output)['report'])
        self.assertEqual(len(self.ssm.sends), 1)

    def test_pending_and_cancelling_are_not_terminal_or_retry_requests(self):
        self.start()
        for status in ('Pending', 'InProgress', 'Delayed', 'Cancelling', 'unrecognized'):
            self.ssm.status = status
            self.assertEqual(self.jobs.advance(self.spec)['phase'], 'observing')
        self.assertEqual(len(self.ssm.sends), 1)

    def test_failed_command_has_no_report_or_score_and_requires_new_explicit_job(self):
        self.start()
        self.ssm.status = 'Failed'
        result = self.jobs.advance(self.spec)
        self.assertEqual((result['phase'], result['reason']), ('failed', 'observation_unavailable'))
        with self.assertRaises(JobDenied):
            self.jobs.retained_report(self.spec)
        self.assertEqual(self.jobs.enqueue(self.spec)['phase'], 'failed')
        self.assertEqual(len(self.ssm.sends), 1)

    def test_malformed_truncated_or_wrong_task_report_is_never_finalized(self):
        good = json.loads(self.ssm.output)['report']
        for value in ('not json', 'x' * 24001,
                      json.dumps({'report': {**good, 'lab_id': 'someone-else'}}),
                      json.dumps({'report': {**good, 'mission_id': 'M4'}}),
                      json.dumps({'report': {**good, 'run_id': str(uuid.uuid4())}}),
                      json.dumps({'report': good, 'password': 'synthetic-must-not-be-kept'})):
            # New explicit jobs after each known terminal result; no forced unlock.
            self.spec = {**self.spec, 'job_id': str(uuid.uuid4())}
            self.jobs.enqueue(self.spec)
            self.jobs.advance(self.spec)
            self.ssm.output = value
            self.assertEqual(self.jobs.advance(self.spec)['phase'], 'failed')
            self.assertNotIn('report', self.jobs.get(self.spec))

    def test_recovery_rejects_matching_comment_with_wrong_target_or_source(self):
        self.ssm.send_error = self.ssm.accept_before_error = True
        self.jobs.enqueue(self.spec)
        self.jobs.advance(self.spec)
        original = copy.deepcopy(self.ssm.commands[0])
        for change in ({'InstanceIds': [self.spec['instances']['web']]},
                       {'DocumentName': 'other-document'},
                       {'Targets': [{'Key': 'tag:Role', 'Values': ['*']}]},
                       {'Parameters': {'commands': ['arbitrary shell']}}):
            self.ssm.commands = [{**original, **change}]
            with self.assertRaises(JobDenied):
                self.jobs.advance(self.spec)
        self.assertEqual(len(self.ssm.sends), 1)

    def test_recovery_follows_pages_and_refuses_duplicates_or_incomplete_search(self):
        self.ssm.send_error = self.ssm.accept_before_error = True
        self.jobs.enqueue(self.spec)
        self.jobs.advance(self.spec)
        command = copy.deepcopy(self.ssm.commands[0])
        self.ssm.list_pages = [[], [command, {**command, 'CommandId': str(uuid.uuid4())}]]
        with self.assertRaises(JobDenied):
            self.jobs.advance(self.spec)
        self.ssm.list_pages = [[] for _ in range(21)]
        with self.assertRaises(JobDenied):
            self.jobs.advance(self.spec)
        self.ssm.list_pages = [[], [command]]
        self.assertEqual(self.jobs.advance(self.spec)['phase'], 'observing')
        self.assertEqual(len(self.ssm.sends), 1)

    def test_mismatched_invocation_does_not_release_an_unconfirmed_running_job(self):
        self.start()
        real_get = self.ssm.get_command_invocation
        def mismatched(**kwargs):
            return {**real_get(**kwargs), 'CommandId': str(uuid.uuid4()), 'Status': 'Failed'}
        self.ssm.get_command_invocation = mismatched
        self.assertEqual(self.jobs.advance(self.spec)['phase'], 'observing')
        other = {**self.spec, 'job_id': str(uuid.uuid4())}
        with self.assertRaises(JobBusy):
            self.jobs.enqueue(other)
        self.assertEqual(len(self.ssm.sends), 1)

    def test_public_projection_excludes_private_context_raw_output_and_grades(self):
        self.ready_report()
        body = json.dumps(self.jobs.current(self.spec))
        for value in (self.spec['owner_hash'], self.spec['account'], self.spec['lab_id'],
                      self.ssm.command_id, 'report', 'raw_earned', 'SYNTHETIC_SECRET'):
            self.assertNotIn(value, body.replace('report_ready', 'captured'))
        self.assertEqual(self.jobs.current(self.spec)['phase'], 'report_ready')

    def test_same_job_id_cannot_be_rebound_to_other_owner_task_or_instances(self):
        self.jobs.enqueue(self.spec)
        for change in ({'owner_hash': 'b' * 64}, {'account': '999999999999'},
                       {'task_id': 'M4'}, {'deployment_id': str(uuid.uuid4())},
                       {'instances': {**self.spec['instances'], 'web': 'i-' + 'f' * 17}}):
            other = {**copy.deepcopy(self.spec), **change}
            for method in (self.jobs.enqueue, self.jobs.advance, self.jobs.current, self.jobs.retained_report):
                with self.assertRaises(JobDenied):
                    method(other)
        self.assertEqual(self.ssm.sends, [])

    def test_command_or_secret_fields_and_automatic_sdk_retries_are_refused(self):
        for change in ({'command': 'anything'}, {'password': 'synthetic'}, {'raw_earned': 62},
                       {'contract_sha256': '0' * 64}, {'task_id': 'M7'}):
            with self.assertRaises(JobDenied):
                self.jobs.enqueue({**self.spec, **change})
        self.assertEqual(self.preflights, [])
        self.ssm.meta.config.retries = {'total_max_attempts': 3}
        with self.assertRaises(JobDenied):
            self.new_worker()
        self.assertEqual(self.ssm.sends, [])


if __name__ == '__main__':
    unittest.main()
