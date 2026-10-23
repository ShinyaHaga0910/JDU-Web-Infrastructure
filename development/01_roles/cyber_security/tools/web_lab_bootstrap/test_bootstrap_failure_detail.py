"""The failure report must remain useful without exposing subprocess secrets."""
import json
import subprocess
import unittest

import node_bootstrap as bootstrap


class FailureDetailTests(unittest.TestCase):
    def test_command_arguments_and_output_never_exported(self):
        secret='credential-material-that-must-stay-private'
        exc=subprocess.CalledProcessError(255,['sshd','-t',secret],output=secret,stderr=secret)
        result=bootstrap.failure_detail(exc,'ssh')
        self.assertEqual(result,{'stage':'ssh','error_class':'CalledProcessError','command':'sshd','returncode':255})
        self.assertNotIn(secret,json.dumps(result))

    def test_unknown_command_and_stage_never_exported(self):
        exc=subprocess.CalledProcessError(2,['https://private.example/credential','argument'])
        self.assertEqual(bootstrap.failure_detail(exc,'private-user-input'),
            {'stage':'configuration','error_class':'CalledProcessError','returncode':2})

    def test_exception_text_and_shell_command_never_exported(self):
        for exc in (ValueError('secret'),subprocess.CalledProcessError(1,'bash -c secret')):
            result=bootstrap.failure_detail(exc,'repo_install')
            self.assertNotIn('secret',json.dumps(result));self.assertNotIn('command',result)

    def test_invalid_stage_does_not_change_stage(self):
        bootstrap.enter_stage('identity')
        with self.assertRaises(ValueError):bootstrap.enter_stage('secret')
        self.assertEqual(bootstrap.BOOTSTRAP_STAGE,'identity')


if __name__=='__main__':unittest.main()
