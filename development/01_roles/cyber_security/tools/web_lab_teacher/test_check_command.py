import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import check_bootstrap


class CheckCommandBehavior(unittest.TestCase):
    def test_transport_failure_retains_original_report_and_local_pass_exit_status(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            state = dict(account='000000000000', stack_id='fixture-stack', deployment_id='00000000-0000-4000-8000-000000000001', lab_id='fixture-lab')
            nodes = {r: dict(instance_id='i-' + str(i)*17) for i, r in enumerate(['bastion','web','dns','db','repo'], 1)}
            observed = dict(scope='fresh_post_stop_start_guest_acceptance', lab_id=state['lab_id'], deployment_id=state['deployment_id'],
                nodes={r: dict(role=r, **v, checks={'chrony_active': True}, network={'repo_http': True},
                               probe_ipv4s=['192.0.2.1','192.0.2.2']) for r,v in nodes.items()})
            config = dict(bootstrap_tools=t, network_source_sha256='fixture-only', pending_directory=str(root/'pending'))
            for key, data in [('state', state), ('baseline_plan', state), ('ssh_enrollment', dict(public_key='public-fixture-only'))]:
                path = root/(key+'.json'); path.write_text(json.dumps(data));config[key]=str(path)
            for key in ('guest_source','submission_source'):
                path = root/(key+'.py');path.write_bytes(b'public-fixture-source')
                config[key]=str(path);config[key+'_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            path=root/'command-state.json';path.write_text(json.dumps(config))
            def save(path, value):
                with Path(path).open('x') as f: json.dump(value,f)
            calls=[]
            def remote(*args):
                calls.append(args)
                if len(calls)==1:return observed
                raise OSError('fixture network unavailable')
            setup=SimpleNamespace(current_nodes=lambda *args:nodes,remote=remote,save_new=save)
            boto=SimpleNamespace(client=lambda name,**kwargs:SimpleNamespace(get_caller_identity=lambda:dict(Account=state['account'])))
            stdout=io.StringIO()
            with patch.dict(sys.modules,{'boto3':boto,'setup_internal_ssh':setup}),patch('socket.create_connection'),contextlib.redirect_stdout(stdout):
                result=check_bootstrap.main(['bootstrap','--command-state',str(path)])
            self.assertEqual(result,0)
            self.assertIn('SUBMISSION PENDING',stdout.getvalue())
            reports=list((root/'pending').glob('*.report.json'))
            self.assertEqual(len(reports),1)
            report=json.loads(reports[0].read_text())
            self.assertEqual(calls[1][-1]['report'],report)
            self.assertFalse(list((root/'pending').glob('*.receipt.json')))

    def test_unknown_does_not_pass_even_when_successfully_sent(self):
        report=dict(checks=[dict(status='UNKNOWN',role='web',id='WEB_FIXTURE')])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(check_bootstrap.print_result(report,'STORED fixture'),1)
            with self.assertRaises(ValueError):check_bootstrap.print_result({'checks':[]},'SKIPPED')

    def test_unavailable_control_or_missing_address_never_proves_denial(self):
        for addresses in (['192.0.2.1','192.0.2.2'], []):
            node=dict(checks={'chrony':True},network={'s3_denied':True,'direct_api_egress_denied':True},
                      probe_ipv4s=addresses,all_checks_passed=True)
            observed=dict(nodes={'web':node},all_five_guest_checks_passed=True)
            check_bootstrap.validate_network_controls(observed,lambda address:False)
            self.assertIsNone(node['network']['s3_denied'])
            self.assertFalse(node['all_checks_passed'])
            self.assertFalse(observed['all_five_guest_checks_passed'])


if __name__=='__main__':unittest.main()
