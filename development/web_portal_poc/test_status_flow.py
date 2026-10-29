"""Cross-component local flow using synthetic identities and AWS responses."""
import copy
import io
import json
import unittest
from unittest.mock import Mock

from test_enrollment import EnrollmentTests
from test_grade_reader import GradeTest
from test_identity_proof import ACCOUNT
from test_status import StatusTest
from test_subject_binding import Store as SubjectStore
from identity_grade import subject_key
from student_status_handler import serve
from subject_binding import bind_subject
from status_gateway import student_status


def unpack(value):
    kind, body = next(iter(value.items()))
    if kind == 'M': return {k: unpack(v) for k, v in body.items()}
    if kind == 'N': return int(body)
    return body


class StatusFlowTest(unittest.TestCase):
    def test_enrollment_and_verified_student_status_flow(self):
        enrollment = EnrollmentTests('test_success_preserves_grade_metadata_and_replay_is_refused')
        enrollment.setUp()
        grades = GradeTest('test_saved_score_and_unknown_current_use_existing_projection')
        grades.setUp()
        grades.row['deployment_id'] = enrollment.grant['deployment_id']
        for row in grades.row['results']:
            if 'deployment_id' in row: row['deployment_id'] = enrollment.grant['deployment_id']
        enrollment.grant['token_hash'] = grades.row['token_hash']
        enrollment.client.meta['token_hash'] = grades.row['token_hash']
        self.assertTrue(enrollment.run_enroll()['bound'])
        rows = {(pk, sk): {name: unpack(value) for name, value in item.items()}
                for (_, pk, sk), item in enrollment.client.rows.items()}
        lab = rows[('LAB#test-lab', 'BINDING')]
        account = rows[('ACCOUNT#' + ACCOUNT, 'BINDING')]
        meta = dict(enrollment.grant, active=True)
        subject_store = SubjectStore(meta, {'LAB#test-lab': lab, 'ACCOUNT#' + ACCOUNT: account})
        context = {**lab, 'token_hash': enrollment.grant['token_hash']}
        subject, pepper = '1234567890', b'synthetic-key-only-for-testing!!'
        self.assertTrue(bind_subject(subject_store, 'bindings', 'grades', subject, pepper, context)['bound'])
        rows.update({key: {name: unpack(value) for name, value in item.items()}
                     for key, item in subject_store.rows.items()})
        grades.row['instances'] = dict(enrollment.grant['instances'])

        class Bindings:
            def get(self, pk, sk): return copy.deepcopy(rows.get((pk, sk)))

        student = StatusTest('test_stopped_instances_are_reported_without_starting')
        student.setUp()
        b = student.binding
        env = {'STUDENT_ACCOUNT': b['account'], 'LAB_ID': b['lab_id'],
               'DEPLOYMENT_ID': b['deployment_id'], 'STACK_ARN': b['stack_id'],
               **{'INSTANCE_' + role.upper(): node['instance_id'] for role, node in b['nodes'].items()}}
        client = Mock()
        def invoke(**request):
            result = serve(json.loads(request['Payload']), env, student.sts, student.cfn, student.ec2, student.ssm)
            return {'StatusCode': 200, 'Payload': io.BytesIO(json.dumps(result).encode())}
        client.invoke.side_effect = invoke
        result = student_status(subject, pepper, Bindings(), grades.store, client)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual({node['ec2_state'] for node in result['observation']['instances']}, {'stopped'})
        self.assertEqual(client.invoke.call_count, 1)
        self.assertTrue(client.invoke.call_args.kwargs['FunctionName'].endswith('jdu-web-status-test-lab'))
        self.assertEqual(student_status('22222222', pepper, Bindings(), grades.store, client), {'status': 'unauthorized'})
        self.assertEqual(client.invoke.call_count, 1)
        student.ec2.start_instances.assert_not_called()
        student.ssm.send_command.assert_not_called()
