import copy
import unittest
from reuse_node_diagnostic import validate_resume


class ResumeTests(unittest.TestCase):
    def fixtures(self):
        return ({'phase':'pause_restored_detach_requested'},
            {'State':{'Name':'stopped'},'BlockDeviceMappings':[{}]},
            {'State':'available','Attachments':[]})

    def test_restored_paused_state_can_resume(self):
        s,n,v=self.fixtures();validate_resume(s,n,v,b'previous',b'previous')

    def test_changed_userdata_is_preserved(self):
        s,n,v=self.fixtures()
        with self.assertRaisesRegex(ValueError,'user data changed'):validate_resume(s,n,v,b'previous',b'changed')

    def test_active_or_attached_state_is_rejected(self):
        s,n,v=self.fixtures()
        for changed in ({'State':{'Name':'running'},'BlockDeviceMappings':[{}]},
                        {'State':{'Name':'stopped'},'BlockDeviceMappings':[{},{}]}):
            with self.assertRaises(ValueError):validate_resume(s,changed,v,b'previous',b'previous')
        for changed in ({'State':'in-use','Attachments':[{}]}, {'State':'available','Attachments':[{}]}):
            with self.assertRaises(ValueError):validate_resume(s,n,changed,b'previous',b'previous')
        with self.assertRaises(ValueError):validate_resume({'phase':'booting'},n,v,b'previous',b'previous')


if __name__=='__main__':unittest.main()
