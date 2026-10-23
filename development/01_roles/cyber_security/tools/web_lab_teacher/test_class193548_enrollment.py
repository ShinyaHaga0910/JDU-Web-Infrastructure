import copy
import unittest

import enroll_class193548_student as enrollment


class StudentEnrollmentBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.state = dict(account=enrollment.ACCOUNT, lab_id=enrollment.LAB,
            deployment_id=enrollment.DEPLOYMENT, manifest_sha256=enrollment.MANIFEST)
        self.nodes = {r: dict(instance_id=i, root_volumes=[v]) for r, (i, v) in enrollment.NODES.items()}

    def test_exact_student_five_and_original_roots_are_accepted(self):
        enrollment.require_nodes(self.state, self.nodes)

    def test_other_account_lab_deployment_manifest_node_or_root_is_rejected(self):
        for field in self.state:
            bad = dict(self.state); bad[field] = 'another-value'
            with self.subTest(field=field), self.assertRaises(ValueError): enrollment.require_nodes(bad, self.nodes)
        for role in self.nodes:
            for field in ('instance_id', 'root_volumes'):
                bad = copy.deepcopy(self.nodes); bad[role][field] = 'i-' + 'f' * 17 if field == 'instance_id' else ['vol-' + 'f' * 17]
                with self.subTest(role=role, field=field), self.assertRaises(ValueError): enrollment.require_nodes(self.state, bad)
        bad = dict(self.nodes); del bad['dns']
        with self.assertRaises(ValueError): enrollment.require_nodes(self.state, bad)


if __name__ == '__main__': unittest.main()
