import copy
import unittest
from adopt_checker_cache_fix import permitted_change


class SameDeploymentOnly(unittest.TestCase):
    def fixture(self):
        old=dict(created_at='old',expires_at='later',grading=dict(ipv4='44.216.176.215'),
            artifacts=dict(template={'sha256':'same'},repo_bundle={'sha256':'same'},controller_bundle={'sha256':'old'}))
        new=copy.deepcopy(old);new.update(created_at='new',expires_at='newer');new['artifacts']['controller_bundle']['sha256']='new'
        a={'student_controller.py':b"command='exec python3 tool'",'check_dispatch.py':b'import sys\n# imports\n',
            'CONTROLLER-MANIFEST.json':b'old','other.py':b'unchanged'}
        b=dict(a,**{'student_controller.py':b"command='exec python3 -B tool'",'check_dispatch.py':b'import sys\nsys.dont_write_bytecode = True\n# imports\n','CONTROLLER-MANIFEST.json':b'new'})
        return old,new,a,b

    def test_exact_fix_accepted(self):permitted_change(*self.fixture())

    def test_infrastructure_or_unrelated_code_change_refused(self):
        for change in ('teacher','template','source','new_file'):
            old,new,a,b=self.fixture()
            if change=='teacher':new['grading']['ipv4']='1.1.1.1'
            elif change=='template':new['artifacts']['template']['sha256']='different'
            elif change=='source':b['student_controller.py']+=b'\nunsafe()'
            else:b['extra.py']=b'unknown'
            with self.subTest(change=change),self.assertRaises(ValueError):permitted_change(old,new,a,b)


if __name__=='__main__':unittest.main()
