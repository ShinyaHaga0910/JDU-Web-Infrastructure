"""Reject a snapshot clone accidentally selected as the running root filesystem."""
import json
import unittest
from unittest.mock import MagicMock,patch

from diagnose_teacher_node import GUEST


class CloneGuardTests(unittest.TestCase):
    def test_mounted_clone_never_reaches_mount_command(self):
        for mountpoint in ('/','/another-mount'):
            tree={'blockdevices':[{'path':'/dev/nvme1n1','serial':'vol0123456789abcdef0','children':[
                {'path':'/dev/nvme1n1p1','mountpoints':[mountpoint]}]}]}
            path=MagicMock();path.read_text.return_value=json.dumps({'volume_id':'vol-0123456789abcdef0'})
            with patch('pathlib.Path',return_value=path),patch('subprocess.check_output',return_value=json.dumps(tree)),patch('subprocess.run') as run:
                with self.assertRaisesRegex(ValueError,'already mounted'):exec(compile(GUEST,'diagnostic-guest','exec'),{})
                run.assert_not_called()

    def test_another_volume_is_never_selected(self):
        tree={'blockdevices':[{'path':'/dev/nvme0n1','serial':'vol99999999999999999','children':[
            {'path':'/dev/nvme0n1p1','mountpoints':[None]}]}]}
        path=MagicMock();path.read_text.return_value=json.dumps({'volume_id':'vol-0123456789abcdef0'})
        with patch('pathlib.Path',return_value=path),patch('subprocess.check_output',return_value=json.dumps(tree)),patch('subprocess.run') as run,patch('time.sleep',side_effect=RuntimeError('fixture stop')):
            with self.assertRaisesRegex(RuntimeError,'fixture stop'):exec(compile(GUEST,'diagnostic-guest','exec'),{})
            run.assert_not_called()


if __name__=='__main__':unittest.main()
