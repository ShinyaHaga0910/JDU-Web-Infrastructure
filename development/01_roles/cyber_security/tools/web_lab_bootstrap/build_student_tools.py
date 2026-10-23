"""Build/sign a small, candidate-only student control distribution for c4."""
import argparse
from datetime import datetime,timedelta,timezone
import gzip
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from urllib.parse import urlsplit

from build_controller_bundle import bundle
from release_validation import file_digest,verify_release


def teacher_endpoint(facts, account, class_id, now):
    """Bind each new archive to freshly reviewed teacher facts, never an old IP."""
    required={'scope','account','class_id','region','checked_at','api_base_url',
              'fixed_ingress_ipv4','https_health_verified'}
    if (set(facts)!=required or facts['scope']!='teacher_endpoint_public_facts'
            or not re.fullmatch(r'[0-9]{12}',account)
            or facts['account']!=account or facts['class_id']!=class_id
            or class_id<=0 or facts['region']!='us-east-1'
            or facts['https_health_verified'] is not True):
        raise ValueError('Fresh facts for the intended teacher account and Class are required')
    checked=datetime.fromisoformat(facts['checked_at'])
    if checked.tzinfo is None or not timedelta(0)<=now-checked<=timedelta(hours=24):
        raise ValueError('Teacher endpoint facts are expired or future dated')
    endpoint=urlsplit(facts['api_base_url'])
    if (endpoint.scheme!='https' or endpoint.username or endpoint.password or endpoint.port
            or endpoint.path not in ('','/') or endpoint.query or endpoint.fragment
            or not re.fullmatch(r'[a-z0-9]{10}\.execute-api\.us-east-1\.amazonaws\.com',endpoint.hostname or '')
            or facts['api_base_url']!='https://'+endpoint.hostname+endpoint.path):
        raise ValueError('One exact AWS-issued us-east-1 HTTPS API endpoint is required')
    if not ipaddress.IPv4Address(facts['fixed_ingress_ipv4']).is_global:
        raise ValueError('A reviewed public teacher IPv4 is required')
    return dict(ipv4=facts['fixed_ingress_ipv4'],fqdn=endpoint.hostname,submit_path='/api/web/submit')


def payload_location(facts, account, class_id, now, accepted_payload):
    required={'scope','account','class_id','region','checked_at','private_bucket',
              'object_key','bundle_sha256','bundle_size_bytes','signed_tree_verified'}
    if (set(facts)!=required or facts['scope']!='teacher_payload_public_facts'
            or facts['account']!=account or facts['class_id']!=class_id
            or facts['region']!='us-east-1' or facts['signed_tree_verified'] is not True):
        raise ValueError('Payload facts must belong to the intended teacher and Class')
    checked=datetime.fromisoformat(facts['checked_at'])
    if checked.tzinfo is None or not timedelta(0)<=now-checked<=timedelta(hours=24):
        raise ValueError('Payload facts are expired or future dated')
    bucket=facts['private_bucket'];key=facts['object_key']
    if (not isinstance(bucket,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]',bucket)
            or not isinstance(key,str) or not re.fullmatch(r'[a-zA-Z0-9/_\-.]+/repo-bundle\.tar\.gz',key)
            or key.startswith('/') or any(part in ('','.','..') for part in key.split('/'))):
        raise ValueError('An exact private bucket and immutable payload key are required')
    if any(facts[k]!=accepted_payload[k] for k in ('bundle_sha256','bundle_size_bytes')):
        raise ValueError('Relocation cannot silently replace the accepted signed payload')
    return dict(private_bucket=bucket,object_key=key,bundle_sha256=facts['bundle_sha256'],
                bundle_size_bytes=facts['bundle_size_bytes'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('output','signing-home','fingerprint'):p.add_argument('--'+n,required=True)
    p.add_argument('--teacher-facts',required=True,type=Path)
    p.add_argument('--payload-facts',required=True,type=Path)
    p.add_argument('--teacher-account',required=True)
    p.add_argument('--class-id',required=True,type=int)
    p.add_argument('--all-nodes-ssm',action='store_true')
    a=p.parse_args();here=Path(__file__).resolve().parent;project=here.parents[3]
    now=datetime.now(timezone.utc)
    grading=teacher_endpoint(json.loads(a.teacher_facts.read_text()),a.teacher_account,a.class_id,now)
    evidence=project/'03_knowledge/aws_official/web_lab_packages_2026-10-15/candidate-c4'
    proof=json.loads((evidence/'integration-acceptance.json').read_text());facts=json.loads((evidence/'deployment-facts.json').read_text())
    payload=payload_location(json.loads(a.payload_facts.read_text()),a.teacher_account,a.class_id,now,proof['payload'])
    output=Path(a.output);output.mkdir(mode=0o700,parents=True,exist_ok=False)
    sources={'wrapper':here/'web_lab.py','validation':here/'release_validation.py','schema':here/'deployment-manifest.schema.json',
        'selector':here.parent/'web_lab_instance_selector/select_instances.py',
        'public_key':project/'03_knowledge/aws_official/web_lab_packages_2026-10-15/package-signing-public.asc',
        'template':project/'03_knowledge/aws_official/web_lab_packages_2026-10-15/candidate-c3/web-lab-ssm-c3.template.json',
        'controller_validation':here/'controller_runtime.py',
        'price_catalog':project/'03_knowledge/aws_official/web_lab_ami_2026-10-15/teacher-price-catalog.json'}
    paths={}
    for role,source in sources.items():
        if role=='template' and a.all_nodes_ssm:
            from all_nodes_ssm import template
            target=output/'web-lab-ssm-all-nodes-c5.template.json'
            target.write_text(json.dumps(template(json.loads(source.read_text())),separators=(',',':'))+'\n')
        else:
            target=output/source.name;shutil.copyfile(source,target)
        paths[role]=target
    controller,inventory=bundle(here);paths['controller_bundle']=output/'student-controller.tar.gz';paths['controller_bundle'].write_bytes(controller)
    artifacts={role:dict(path=v.name,sha256=file_digest(v)[0],size_bytes=v.stat().st_size) for role,v in paths.items()}
    artifacts['repo_bundle']=dict(path='repo-bundle.tar.gz',sha256=payload['bundle_sha256'],size_bytes=payload['bundle_size_bytes'])
    cidrs=json.loads((project/'03_knowledge/network/2026-10-15_isp_rdp_allowlist/rdp_ingress_ip_permissions.json').read_text())[0]['IpRanges']
    manifest=dict(schema_version=1,release_id='web-2026-10-r1',created_at=now.isoformat(),expires_at=(now+timedelta(days=7)).isoformat(),region='us-east-1',
        ami=facts['ami'],network=dict(vpc_cidr='10.20.0.0/16',public_subnet_cidr='10.20.1.0/24',private_subnet_cidr='10.20.2.0/24',
            s3_prefix_list_id=facts['s3_prefix_list_id'],rdp_ipv4_cidrs=[x['CidrIp'] for x in cidrs]),
        grading=grading,
        bootstrap=dict(bucket=payload['private_bucket'],release_prefix=payload['object_key'].rsplit('/',1)[0]+'/'),
        signing=dict(primary_fingerprint=a.fingerprint),artifacts=artifacts)
    manifest_path=output/'deployment-manifest.json';manifest_path.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    signing=['gpg','--no-options','--homedir',a.signing_home,'--batch','--digest-algo','SHA256','--local-user',a.fingerprint,'--armor','--detach-sign']
    subprocess.run(signing+['--output',str(manifest_path)+'.asc',str(manifest_path)],capture_output=True,check=True)
    (output/'jdu-web-lab').write_text('#!/usr/bin/env bash\nset -euo pipefail\nDIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"\n'
        'exec python3 -B "$DIR/web_lab.py" student "$@" --deployment-manifest "$DIR/deployment-manifest.json" --signature "$DIR/deployment-manifest.json.asc" '
        '--public-key "$DIR/'+paths['public_key'].name+'" --trusted-fingerprint '+a.fingerprint+' --artifact-root "$DIR"\n')
    (output/'jdu-web-lab').chmod(0o700)
    (output/'README.txt').write_text('''Web Lab student tools - CANDIDATE\nNot a formal release. CLASS_READY remains false pending fresh acceptance.\nVerify this archive signature with the independently supplied full fingerprint before extraction.\nNever download a private SSH key to Windows. Run in your individual Academy CloudShell.\n\nPlan only (no resources or credentials are created):\n./jdu-web-lab plan --lab-id YOUR-LAB-ID --output PRIVATE-PLAN.json --price-catalog ./teacher-price-catalog.json\n\nHuman-run create requires reviewed access and a resource plan, then hidden RDP password input:\n./jdu-web-lab create --plan PRIVATE-PLAN.json --state PRIVATE-STATE.json --confirmed-access\nFor another account's private S3, the teacher supplies a short-lived URL directly into an individual 0600 CloudShell file; use --bootstrap-url-file FILE.\nTeacher admin credentials are never given to students.\n\nUse the same --state thereafter. status/diagnose use AWS reads and bounded public guest checks through existing SSM.\nstatus --output NEW-PUBLIC-REPORT.json\nlock-prepare, lock-review, lock-apply; status\nssm --role bastion|web|dns|db|repo (interactive ssm-user; signed template must enable that role; no PEM)\nssh-plan, ssh-apply (human-run), wait at least 62 seconds, ssh-verify\nregister-plan, register-apply (human-run), register-verify: each requires --student-config OWN-LAB-CREDENTIAL.json\ninstall-commands --student-config OWN-LAB-CREDENTIAL.json [--bin-directory PERSONAL-NEW-BIN]\npreflight [--gui-confirmed after checking RDP desktop and Firefox yourself]\n\nNew create never overwrites existing state and is blocked above the conservative nine-instance pilot budget.\nA failed or unknown create retains state: inspect status; never launch duplicate stacks.\nClosure changes only the bootstrap SG and S3 policy; all other parameters remain previous values.\nPrivate SSM endpoints stay available after S3 closure; internal SSH remains a separate exercise path.\nP1/M1 are a WEB-02 candidate pair, with no course points.\n''')
    checked=verify_release(manifest_path,str(manifest_path)+'.asc',paths['public_key'],a.fingerprint,output,include_bundle=False)
    archive=output.with_name(output.name+'.tar.gz')
    with tarfile.open(archive,'x:gz') as t:
        for source in sorted(output.iterdir()):t.add(source,arcname='student-tools/'+source.name,recursive=False)
    subprocess.run(signing+['--output',str(archive)+'.asc',str(archive)],capture_output=True,check=True)
    print(json.dumps(dict(stage='SIGNED_STUDENT_TOOLS_CANDIDATE',size_bytes=archive.stat().st_size,sha256=file_digest(archive)[0],
        manifest_sha256=checked['manifest_sha256'],controller_public_files=len(inventory['files']),
        repo_bundle_deferred_in_cloudshell=True,private_credentials_included=False,student_release_ready=False,class_ready=False)))


if __name__=='__main__':main()
