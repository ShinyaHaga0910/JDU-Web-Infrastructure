import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import web_commands
import web_progress


class CommandContract(unittest.TestCase):
    def config(self, root):
        path = Path(root) / 'fixture-config.json'
        web_progress.save_private(path, dict(lab_id='fixture-lab', lab_token='F' * 43,
            release_id='web-2026-10-r1', api_base_url='https://fixture.execute-api.us-east-1.amazonaws.com',
            fixed_ingress_ipv4='44.216.176.215', admin_key='A' * 43))
        return path

    def test_private_session_saved_without_token_output(self):
        with tempfile.TemporaryDirectory() as t:
            config = self.config(t)
            session = dict(url='https://fixture.execute-api.us-east-1.amazonaws.com/dashboard?session='+'S'*43, expires_at=123)
            output = Path(t) / 'session.json'
            stdout = io.StringIO()
            with patch.object(web_commands.client, 'request', return_value=session) as request, contextlib.redirect_stdout(stdout):
                web_commands.main(['my-progress', '--config', str(config), '--save-session', str(output)])
            self.assertNotIn('S'*43, stdout.getvalue())
            self.assertNotIn('F'*43, stdout.getvalue())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(request.call_args.args[1], '/api/web/student/session')

    def test_session_destination_cannot_redirect_to_other_origin(self):
        with tempfile.TemporaryDirectory() as t:
            config = self.config(t)
            with patch.object(web_commands.client, 'request', return_value=dict(url='https://evil.invalid/dashboard?session=fixture')):
                with self.assertRaises(ValueError): web_commands.main(['dashboard', '--config', str(config)])

    def test_email_cancellation_sends_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            config = self.config(t)
            with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', side_effect=['fixture@jdu.uz', 'No']), \
                    patch.object(web_commands.client, 'request') as request, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError): web_commands.main(['link-email', '--config', str(config)])
                request.assert_not_called()


if __name__ == '__main__': unittest.main()
