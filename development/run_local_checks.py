"""Run the selected offline/mock regressions. No deployment or live AWS acceptance."""
import argparse
import ast
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
TOOLS=ROOT/'01_roles/cyber_security/tools'
GROUPS={
 'web_lab_instance_selector':['test_select_instances','test_collect_price_catalog'],
 'web_lab_bootstrap':['test_web_lab','test_five_node_template','test_all_nodes_ssm','test_student_create',
                      'test_student_controller','test_internal_ssh','test_checker_cache','test_bootstrap_failure_detail'],
 'web_lab_teacher':['test_progress_api','test_web_commands','test_http_checker','test_checker_binding',
                    'test_class_student_delivery','test_refresh_class_delivery'],
 'web_lab_assessment':['test_assessment','test_observers'],
 'web_lab_distribution':['test_distribution','test_publication'],
 'web_lab_release':['test_release'],
 'web_lab_catalog':['tests.test_configuration','tests.test_bundle'],
}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-import',action='store_true',help='Also require the initial imported baseline bytes, for migration audits only.')
    args=parser.parse_args()
    if os.name!='posix':
        raise SystemExit('Use Linux/WSL Python3 with GPG; tests exercise POSIX permissions.')
    imported=json.loads((ROOT/'IMPORT-MANIFEST.json').read_text())
    if args.verify_import:
        for entry in imported['files']:
            data=(ROOT/entry['path']).read_bytes()
            if hashlib.sha256(data).hexdigest()!=entry['sha256']:
                raise ValueError('Imported baseline differs: '+entry['path'])
    python_files=list(TOOLS.rglob('*.py'))
    for p in python_files:
        ast.parse(p.read_text(encoding='utf-8-sig'))
    env={k:v for k,v in os.environ.items() if not k.startswith('AWS_')}
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',AWS_EC2_METADATA_DISABLED='true')
    outcomes=[]
    for folder,modules in GROUPS.items():
        start=time.monotonic()
        result=subprocess.run([sys.executable,'-B','-m','unittest',*modules],cwd=TOOLS/folder,env=env,capture_output=True,text=True)
        # Only local unittest summaries are printed; no cloud input is used.
        print(folder+': '+('PASS' if result.returncode==0 else 'FAIL'),flush=True)
        print(result.stderr[-6000:],flush=True)
        count=re.search(r'Ran (\d+) tests?',result.stderr)
        skipped=re.search(r'skipped=(\d+)',result.stderr)
        outcomes.append(dict(group=folder,modules=modules,passed=result.returncode==0,
            tests_run=int(count.group(1)) if count else None, skipped=int(skipped.group(1)) if skipped else 0,
            seconds=round(time.monotonic()-start,2)))
    target=ROOT/'local-checks.public.json'
    target.write_text(json.dumps(dict(scope='imported_source_offline_regression_not_AWS',date='2026-10-23',
        import_baseline_checked=args.verify_import,source_files_verified=len(imported['files']) if args.verify_import else 0,
        python_files_parsed=len(python_files),groups=outcomes,
        tests_run=sum(x['tests_run'] or 0 for x in outcomes),tests_skipped=sum(x['skipped'] for x in outcomes),
        all_passed=all(x['passed'] for x in outcomes),aws_mutations=False),indent=2)+'\n',encoding='utf-8')
    if not all(x['passed'] for x in outcomes):raise SystemExit(1)

if __name__=='__main__':main()
