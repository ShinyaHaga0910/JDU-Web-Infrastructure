import copy
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from bootstrap_submission_guest import retained, validate
from submit_five_node_bootstrap import build_report


class SubmissionGuards(unittest.TestCase):
    def fixture(self):
        state = dict(lab_id='fixture-lab', deployment_id=str(uuid.uuid4()))
        nodes = {r: {'instance_id': 'i-' + str(i) * 17} for i, r in enumerate(['bastion', 'web', 'dns', 'db', 'repo'], 1)}
        evidence = dict(scope='fresh_post_stop_start_guest_acceptance', **state, nodes={
            r: dict(role=r, **n, checks={'chrony_active': True}, network={'repo_http': True}) for r, n in nodes.items()})
        bootstrap = dict(**state, release_id='web-2026-10-r1', role='bastion', instances={r: n['instance_id'] for r, n in nodes.items()})
        return state, nodes, evidence, bootstrap

    def test_observed_false_and_unknown_never_promoted(self):
        state, nodes, e, b = self.fixture()
        e['nodes']['db']['checks']['chrony_active'] = False
        e['nodes']['web']['network']['repo_http'] = None
        report = build_report(e, state, nodes, str(uuid.uuid4()))
        validate(report, b)
        self.assertEqual(sum(c['status'] == 'PASS' for c in report['checks']), 8)
        self.assertEqual({c['status'] for c in report['checks']}, {'PASS', 'FAIL', 'UNKNOWN'})
        self.assertNotIn('mission_id', report)

    def test_foreign_node_or_deployment_rejected_before_submit(self):
        state, nodes, e, b = self.fixture()
        e['nodes']['db']['instance_id'] = nodes['web']['instance_id']
        with self.assertRaises(ValueError): build_report(e, state, nodes, str(uuid.uuid4()))
        e['nodes']['db']['instance_id'] = nodes['db']['instance_id']
        report = build_report(e, state, nodes, str(uuid.uuid4()))
        report['deployment_id'] = str(uuid.uuid4())
        with self.assertRaises(ValueError): validate(report, b)

    def test_duplicate_and_score_payload_rejected(self):
        state, nodes, e, b = self.fixture()
        report = build_report(e, state, nodes, str(uuid.uuid4()))
        duplicate = copy.deepcopy(report)
        duplicate['checks'].append(duplicate['checks'][0])
        with self.assertRaises(ValueError): validate(duplicate, b)
        report['points'] = 100
        with self.assertRaises(ValueError): validate(report, b)

    def test_existing_pending_preserved_on_changed_body(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / 'pending.json'
            retained(path, {'request_id': 'fixture'})
            before = path.read_bytes()
            retained(path, {'request_id': 'fixture'})
            with self.assertRaises(ValueError): retained(path, {'request_id': 'different'})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(json.loads(before), {'request_id': 'fixture'})


if __name__ == '__main__': unittest.main()
