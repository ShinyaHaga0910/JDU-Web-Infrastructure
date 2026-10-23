import copy
import unittest
from apply_candidate_registration import require_context,require_preflight,DEPLOYMENT,MANIFEST,NEW_NODES


class PilotEnrollmentTargets(unittest.TestCase):
    def fixture(self):
        manifest=dict(release_id='release-fixture',grading=dict(fqdn='fixture.execute-api.us-east-1.amazonaws.com',ipv4='44.216.176.215'))
        state=dict(lab_id='teacher-c4-probe',deployment_id=DEPLOYMENT,manifest_sha256=MANIFEST,release_id='release-fixture')
        teacher=dict(release_id='release-fixture',api_base_url='https://'+manifest['grading']['fqdn'],fixed_ingress_ipv4='44.216.176.215',admin_key='fake-fixture-only')
        nodes={r:dict(instance_id=i,root_volumes=[v]) for r,(i,v) in NEW_NODES.items()}
        return state,manifest,teacher,nodes

    def test_only_current_reviewed_deployment_and_signed_teacher(self):
        values=self.fixture();require_context(*values)
        for index,field,value in [(0,'deployment_id','old'),(0,'lab_id','teacher-five-probe'),(0,'manifest_sha256','changed'),
                (2,'api_base_url','https://other.example'),(2,'fixed_ingress_ipv4','1.1.1.1'),(2,'admin_key','')]:
            changed=copy.deepcopy(values);changed[index][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):require_context(*changed)

    def test_old_teacher_instance_duplicates_and_extra_disks_refused(self):
        for change in ('teacher','duplicate','disk'):
            state,manifest,teacher,nodes=self.fixture()
            if change=='teacher':nodes['bastion']['instance_id']='i-0040d8f349c83f2dd'
            elif change=='duplicate':nodes['web']['instance_id']=nodes['bastion']['instance_id']
            else:nodes['web']['root_volumes'].append('vol-other')
            with self.subTest(change=change),self.assertRaises(ValueError):require_context(state,manifest,teacher,nodes)

    def test_wrong_new_instance_or_root_is_not_adopted(self):
        for field,value in [('instance_id','i-'+'f'*17),('root_volumes',['vol-other'])]:
            state,manifest,teacher,nodes=self.fixture();nodes['web'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):require_context(state,manifest,teacher,nodes)

    def test_preflight_requires_actual_pass_and_saved_submission(self):
        import json
        result=dict(stage='PREFLIGHT_OBSERVED',current_foundation_passed=True)
        line='SUBMISSION STORED request_id=11111111-1111-4111-8111-111111111111\n'
        require_preflight(line+json.dumps(result))
        for text in [json.dumps(result),'SUBMISSION PENDING\n'+json.dumps(result),
                line+json.dumps(dict(result,current_foundation_passed=False))]:
            with self.assertRaises(ValueError):require_preflight(text)


if __name__=='__main__':unittest.main()
