import base64
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from internal_ssh_guest import public_key, safe_path, append_public, pins, init_bastion, ROLES
from setup_internal_ssh import console_host_key

KEY='ssh-ed25519 '+base64.b64encode(b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20'+b'x'*32).decode()


class InternalSshProtectionTests(unittest.TestCase):
    def test_public_key_rejects_options_comments_and_private_material(self):
        self.assertEqual(public_key(KEY),KEY)
        for bad in ['from="*" '+KEY,KEY+' comment',KEY+'\ncommand=evil',
                    '-----BEGIN OPENSSH PRIVATE KEY-----','ssh-ed25519 eA==']:
            with self.assertRaises(ValueError):public_key(bad)

    def test_host_keys_require_trusted_console_block_and_unique_key(self):
        block='-----BEGIN SSH HOST KEY KEYS-----\n'+KEY+' root@host\n-----END SSH HOST KEY KEYS-----'
        self.assertEqual(console_host_key(block),KEY)
        self.assertEqual(console_host_key(base64.b64encode(block.encode()).decode()),KEY)
        for bad in [KEY,block.replace('END SSH HOST KEY KEYS','MISSING'),
                    block.replace(KEY,KEY+'\n'+KEY.replace('eHh4','eXh4'))]:
            with self.assertRaises(ValueError):console_host_key(bad)

    def test_files_symlinks_hardlinks_modes_and_owner_protected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'file';p.write_text('fixture');p.chmod(0o600)
            safe_path(p,os.getuid(),0o600)
            link=Path(t)/'sym';link.symlink_to(p)
            with self.assertRaises(ValueError):safe_path(link,os.getuid(),0o600)
            with self.assertRaises(ValueError):safe_path(p,os.getuid()+1,0o600)
            p.chmod(0o644)
            with self.assertRaises(ValueError):safe_path(p,os.getuid(),0o600)
            p.chmod(0o600);os.link(p,Path(t)/'hard')
            with self.assertRaises(ValueError):safe_path(p,os.getuid(),0o600)

    def test_authorized_keys_preserved_and_repeated_enrollment_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'authorized_keys';p.write_bytes(b'existing fixture key');p.chmod(0o600)
            line='from="10.20.1.10",no-agent-forwarding '+KEY+' test'
            append_public(p,line,os.getuid(),os.getgid())
            expected=b'existing fixture key\n'+line.encode()+b'\n'
            self.assertEqual(p.read_bytes(),expected)
            append_public(p,line,os.getuid(),os.getgid())
            self.assertEqual(p.read_bytes(),expected)
            p.chmod(0o644)
            with self.assertRaises(ValueError):append_public(p,line,os.getuid(),os.getgid())
            self.assertEqual(p.read_bytes(),expected)

    def test_key_with_different_restrictions_is_not_silently_adopted(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'authorized_keys';p.write_text(KEY+' other\n');p.chmod(0o600)
            before=p.read_bytes()
            with self.assertRaises(ValueError):append_public(p,'from="10.20.1.10" '+KEY+' new',os.getuid(),os.getgid())
            self.assertEqual(p.read_bytes(),before)

    def request(self):
        return {'peers':{r:{'private_ip':ip,'instance_id':'i-'+'a'*17,'host_key':KEY} for r,ip in ROLES.items()}}

    def test_pins_refuse_other_roles_ips_or_unpinned_host_keys(self):
        request=self.request();known,config=pins(request)
        self.assertIn(b'StrictHostKeyChecking yes',config)
        self.assertIn(b'PasswordAuthentication no',config)
        self.assertNotIn(b'StrictHostKeyChecking no',config)
        for mutation in ('role','ip','hostkey'):
            bad=copy.deepcopy(request)
            if mutation=='role':bad['peers']['other']=bad['peers'].pop('repo')
            elif mutation=='ip':bad['peers']['repo']['private_ip']='1.2.3.4'
            else:bad['peers']['repo']['host_key']='invalid'
            with self.assertRaises(ValueError):pins(bad)

    def test_existing_unrelated_key_directory_stops_before_generation(self):
        with tempfile.TemporaryDirectory() as t:
            home=Path(t);home.chmod(0o700);parent=home/'.ssh';parent.mkdir(mode=0o700)
            root=parent/'jdu-web-internal';root.mkdir(mode=0o700)
            for name in ('identity.json','id_ed25519','known_hosts','config'):
                (root/name).write_text('unrelated fixture');(root/name).chmod(0o600)
            (root/'id_ed25519.pub').write_text(KEY);(root/'id_ed25519.pub').chmod(0o644)
            user=type('User',(),{'pw_dir':str(home),'pw_uid':os.getuid(),'pw_gid':os.getgid()})()
            request=dict(self.request(),lab_id='teacher-five-probe',deployment_id='fixture',instance_id='i-fixture')
            with patch('internal_ssh_guest.identity'),patch('internal_ssh_guest.pwd.getpwnam',return_value=user),patch('internal_ssh_guest.subprocess.run') as proc:
                with self.assertRaises(ValueError):init_bastion(request)
                proc.assert_not_called()
            self.assertEqual((root/'id_ed25519').read_text(),'unrelated fixture')


if __name__=='__main__':unittest.main()
