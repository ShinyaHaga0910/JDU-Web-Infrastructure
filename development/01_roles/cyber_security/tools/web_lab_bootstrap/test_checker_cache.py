"""Real checker imports must leave the strictly verified controller reloadable."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from build_controller_bundle import bundle
from controller_runtime import install_controller


class CheckerCacheRegression(unittest.TestCase):
    def test_short_checker_import_then_strict_controller_reload(self):
        data,_=bundle(Path(__file__).resolve().parent)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);target=install_controller(data,root/'controller')
            # Help imports the actual dispatcher, HTTP/bootstrap implementation
            # and its dependencies, but does not call AWS or read credentials.
            mocks=root/'mocks';mocks.mkdir();(mocks/'boto3.py').write_text('# No AWS calls in --help.\n')
            env=dict(os.environ,PYTHONPATH=str(mocks));env.pop('PYTHONDONTWRITEBYTECODE',None)
            for task in ('P1','M1','bootstrap'):
                result=subprocess.run([sys.executable,str(target/'check_dispatch.py'),task,'--help'],
                    env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertFalse((target/'__pycache__').exists())
                install_controller(data,target)


if __name__=='__main__':unittest.main()
