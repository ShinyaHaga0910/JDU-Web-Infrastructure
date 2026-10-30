"""R1 SDK planning/worker integration: real selector, Moto, fake AWS/crypt."""
import base64
from datetime import timedelta
import json
from unittest.mock import Mock, patch
import unittest

import test_initial_stack as fixtures
from initial_plan import make_plan
from initial_worker import InitialWorker
from portal_enrollment import grant_digest


class InitialWorkerTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.InitialStackTest(methodName='test_double_click_and_status_only_observe_same_stack')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        f = self.f
        self.data = fixtures.fixture()
        public = 'ssh-ed25519 ' + base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20' + b'x'*32).decode()
        f.ec2.describe_key_pairs.return_value = {'KeyPairs': [{'KeyName': 'vockey', 'PublicKey': public}]}
        pages = {'describe_instances': [],
                 'describe_instance_types': [{'InstanceTypes': self.data['instance_types']}],
                 'describe_instance_type_offerings': [{'InstanceTypeOfferings': self.data['offerings']}],
                 'get_managed_prefix_list_entries': [{'Entries': [{'Cidr': '52.216.0.0/15'}]}]}
        self.pages = pages
        f.ec2.get_paginator.side_effect = lambda operation: Mock(paginate=Mock(side_effect=lambda **kw: pages[operation]))
        f.ec2.describe_availability_zones.return_value = {'AvailabilityZones': self.data['zones']}
        f.ec2.describe_managed_prefix_lists.return_value = {'PrefixLists': [
            {'OwnerId': 'AWS', 'PrefixListName': 'com.amazonaws.us-east-1.s3'}]}
        catalog = f.path.parent / 'prices.json'
        catalog.write_text(json.dumps({'region': 'us-east-1', 'currency': 'USD', 'source': 'AWS Price List',
            'collected_at': f.now.isoformat(), 'prices': self.data['prices']}), encoding='utf-8')
        f.verified['files']['price_catalog'] = catalog
        def resolve(host, *args, **kw):
            ip = '52.216.0.1' if host == 's3.us-east-1.amazonaws.com' else '203.0.113.10'
            return [(None, None, None, None, (ip, 443))]
        self.planner = Mock(side_effect=lambda stack: make_plan(stack, resolve=resolve))
        self.hasher = Mock(return_value=f.password_hash)
        self.worker = InitialWorker(f.worker, planner=self.planner, password_hasher=self.hasher)
        self.context = {'grant_digest': grant_digest(f.grant)}

    def event(self, operation, **fields):
        return {'operation': operation, **self.context, **fields}

    def test_sdk_discovery_uses_real_lowest_cost_selector_and_no_private_key(self):
        result = self.worker.serve(self.event('plan'))
        self.assertEqual(result['status'], 'ok')
        view = result['initial']
        self.assertEqual(view['instance_types']['Bastion'], 't3a.medium')
        self.assertEqual(view['instance_types']['Package'], 't3a.small')
        self.assertEqual(view['new_nodes'], 5)
        self.assertEqual(view['root_gib'], 96)
        self.assertFalse(view['price_includes_disks_ipv4_endpoints'])
        self.assertNotIn('student_public_key', view)
        self.f.ec2.create_key_pair.assert_not_called()
        self.f.cfn.create_stack.assert_not_called()

    def test_observe_cannot_make_a_plan_or_create_and_existing_plan_is_stable(self):
        self.assertEqual(self.worker.serve(self.event('observe'))['initial']['stage'], 'NOT_REQUESTED')
        self.planner.assert_not_called()
        first = self.worker.serve(self.event('plan'))
        self.assertEqual(self.worker.serve(self.event('plan')), first)
        self.assertEqual(self.worker.serve(self.event('observe')), first)
        self.assertEqual(self.planner.call_count, 1)
        self.f.cfn.create_stack.assert_not_called()

    def test_hash_is_ephemeral_and_duplicate_create_only_observes_original_stack(self):
        plan = self.worker.serve(self.event('plan'))['initial']
        create = self.event('create', plan_digest=plan['plan_digest'],
                            password='DisposableFixtureOnly23', confirmation='DisposableFixtureOnly23')
        self.assertEqual(self.worker.serve(create)['initial']['stage'], 'CREATE_REQUESTED')
        self.assertEqual(self.worker.serve(create)['initial']['stack_id'], self.f.stack_id)
        self.assertEqual(self.f.cfn.create_stack.call_count, 1)
        self.assertEqual(self.hasher.call_count, 1)
        saved = json.dumps(self.f.db.scan(TableName='initial-jobs')['Items'])
        for secret in ('DisposableFixtureOnly23', self.f.password_hash, self.f.url):
            self.assertNotIn(secret, saved)

    def test_retained_five_exceed_pilot_ceiling_before_planning_or_writing(self):
        self.pages['describe_instances'] = [{'Reservations': [{'Instances': [{}]*5}]}]
        result = self.worker.serve(self.event('plan'))
        self.assertEqual(result['status'], 'resource_budget')
        self.assertEqual(result['resource_budget']['projected'], 10)
        self.assertIsNone(self.worker.saved_plan())
        self.f.cfn.create_stack.assert_not_called()

    def test_stale_catalog_wrong_context_and_unreviewed_create_cannot_start(self):
        f = self.f
        p = f.verified['files']['price_catalog']
        catalog = json.loads(p.read_text())
        catalog['collected_at'] = (f.now-timedelta(days=8)).isoformat()
        p.write_text(json.dumps(catalog))
        self.assertEqual(self.worker.serve(self.event('plan'))['status'], 'unavailable')
        self.assertEqual(self.worker.serve(dict(self.event('observe'), grant_digest='0'*64))['status'], 'unauthorized')
        self.assertEqual(self.worker.serve(self.event('create', plan_digest='f'*64, password='canary', confirmation='canary'))['status'], 'unauthorized')
        self.assertEqual(self.worker.serve(self.event('terminate'))['status'], 'unauthorized')
        self.hasher.assert_not_called()
        self.f.cfn.create_stack.assert_not_called()

    def test_hashing_or_transport_failure_never_returns_password_or_raw_error(self):
        view = self.worker.serve(self.event('plan'))['initial']
        self.hasher.side_effect = RuntimeError('private-password-canary')
        result = self.worker.serve(self.event('create', plan_digest=view['plan_digest'],
                                  password='private-password-canary', confirmation='private-password-canary'))
        self.assertEqual(result, {'status': 'unavailable'})
        self.assertIsNone(self.f.worker.saved())


if __name__ == '__main__': unittest.main()
