"""Fixed existing D11 observers, adapted to durable non-interactive jobs.

No shell, expected body, score, network target or secret comes from HTTP input.
The snapshot must be produced by the trusted controller from the retained AWS
stack and existing public SSH enrollment. HTTP public-entry probes run outside
the VPC just as in assessment_check.py; SSM observes through the same bastion.
SpecialChecks coordinates explicit functional entry and stop/retain/restart evidence.
"""
import base64
import copy
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import shlex
import zlib

from assessment_command_jobs import JobDenied, ROLES, canonical, checked_spec, sha,report_mode
from registry import build_report, canonical_checks, validate_report

ROOT = Path(__file__).resolve().parents[1] / '01_roles/cyber_security/tools'
HERE = Path(__file__).resolve().parent
# Deployment packages are flat; the canonical repository keeps the original
# directories. Both paths use the same byte-pinned observer assets.
ASSESSMENT = HERE if (HERE / 'assessment-registry.json').is_file() else ROOT / 'web_lab_assessment'
TEACHER = HERE if (HERE / 'http_task_guest.py').is_file() else ROOT / 'web_lab_teacher'
SNAPSHOT_KEYS = {'spec_sha256', 'private_ips', 'public_web_ipv4', 'root_volumes',
                 'expected_public_key', 'network_baseline'}


def checked_snapshot(spec, snapshot):
    checked_spec(spec)
    if (type(snapshot) is not dict or set(snapshot) != SNAPSHOT_KEYS
            or snapshot['spec_sha256'] != sha(spec)
            or type(snapshot['private_ips']) is not dict or set(snapshot['private_ips']) != ROLES
            or type(snapshot['root_volumes']) is not dict or set(snapshot['root_volumes']) != ROLES
            or snapshot['network_baseline'] is not None and type(snapshot['network_baseline']) is not bool):
        raise JobDenied('Invalid trusted observation snapshot')
    try:
        private = list(snapshot['private_ips'].values())
        if len(set(private)) != 5 or any(ipaddress.ip_address(v) not in ipaddress.ip_network('10.20.0.0/16') for v in private):
            raise ValueError('Wrong private teaching network')
        public = snapshot['public_web_ipv4']
        if public is not None and (not isinstance(public, str) or not isinstance(ipaddress.ip_address(public), ipaddress.IPv4Address)
                                   or not ipaddress.ip_address(public).is_global):
            raise ValueError('Public AWS IPv4 required; never probe a private service')
        volumes = []
        for value in snapshot['root_volumes'].values():
            if type(value) is not list or len(value) != 1 or not isinstance(value[0], str) or not re.fullmatch(r'vol-[a-f0-9]{17}', value[0]):
                raise ValueError('Original root volume required')
            volumes.extend(value)
        if len(set(volumes)) != 5:
            raise ValueError('Distinct original root volumes required')
        public_key = snapshot['expected_public_key']
        if not isinstance(public_key, str) or not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]{68}', public_key):
            raise ValueError('Original public SSH key required')
        raw = base64.b64decode(public_key.split()[1], validate=True)
        if len(raw) != 51 or raw[:19] != b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20':
            raise ValueError('Wrong public key format')
    except (ValueError, TypeError):
        raise JobDenied('Invalid trusted observation snapshot') from None
    # DynamoDB maps do not retain the input's insertion order. The transport
    # embeds JSON in a shell command, so normalize nested public maps before
    # compiling both the initial command and any later reconciliation.
    return json.loads(canonical(snapshot))


class Observation:
    def __init__(self, trusted_spec, trusted_snapshot, *, http_probe=None, http=None,before=None,stopped=None,sealed_password=None):
        self.spec = checked_spec(trusted_spec)
        self.snapshot = checked_snapshot(self.spec, trusted_snapshot)
        if http_probe is None:
            from http_task import http_probe
        if http is None:
            from network_checks import http
        self.http_probe, self.http = http_probe, http
        self.before,self.stopped,self.sealed_password=before,stopped,sealed_password

    def scope(self, spec):
        if checked_spec(spec) != self.spec:
            raise JobDenied('Wrong retained observation')

    def command(self, spec):
        self.scope(spec)
        if spec['task_id'] in ('P1', 'M1'):
            return self.http_command()
        from transport import ssm_command
        request = {k: spec[k] for k in ('lab_id', 'release_id', 'deployment_id', 'instances', 'task_id', 'run_id')}
        request.update(role='bastion', instance_id=spec['instances']['bastion'], operation='collect',
            network_baseline=self.snapshot['network_baseline'], root_volumes=self.snapshot['root_volumes'],
            expected_public_key=self.snapshot['expected_public_key'], web_instance_id=spec['instances']['web'])
        if spec.get('check_mode')=='storage':
            if not self.before or not self.stopped:raise JobDenied('Same stopped Web evidence required')
            request.update(before=self.before,stopped=self.stopped)
        if spec.get('check_mode') in ('functional_prepare','functional'):
            from browser_check_guest import command
            return command(request,sealed_password=self.sealed_password,prepare=spec['check_mode']=='functional_prepare')
        # Same public source/registry transport as the installed CLI, not a shell
        # string or a task implementation selected by a browser parameter.
        return ssm_command(request)

    def http_command(self):
        from http_guest_v2 import LEGACY_SHA256, CONTRACT_SHA256
        original = (TEACHER / 'http_task_guest.py').read_bytes()
        contract = (TEACHER / 'http_task.py').read_bytes()
        if hashlib.sha256(original).hexdigest() != LEGACY_SHA256 or hashlib.sha256(contract).hexdigest() != CONTRACT_SHA256:
            raise JobDenied('Original HTTP observer and contract must be retained')
        guest = ('LEGACY_SOURCE_B64=' + repr(base64.b64encode(original).decode()) + '\n').encode()
        guest += (ASSESSMENT / 'http_guest_v2.py').read_bytes()
        spec, snapshot = self.spec, self.snapshot
        request = {k: spec[k] for k in ('lab_id', 'deployment_id')}
        request.update(role='bastion', instance_id=spec['instances']['bastion'], web_id=spec['instances']['web'],
            web_ip=snapshot['private_ips']['web'], repo_ip=snapshot['private_ips']['repo'],
            bastion_ip=snapshot['private_ips']['bastion'], expected_public_key=snapshot['expected_public_key'],
            mission_id=spec['task_id'], nonce=spec['run_id'].replace('-', ''), operation='collect',
            contract_source_b64=base64.b64encode(contract).decode(), guest_source_b64=base64.b64encode(guest).decode())
        package = {'source': guest.decode('utf-8'), 'request': request}
        packed = base64.b64encode(zlib.compress(canonical(package), 9)).decode()
        loader = ('import base64,io,json,sys,zlib; p=json.loads(zlib.decompress(base64.b64decode(' + repr(packed) + ')));'
                  'sys.stdin=io.StringIO(json.dumps(p["request"]));'
                  'exec(compile(p["source"],"<fixed-d11-http-observer>","exec"),{"__name__":"__main__"})')
        return 'python3 -c ' + shlex.quote(loader)

    def finish(self, spec, output):
        self.scope(spec)
        value = json.loads(output)
        if type(value) is not dict:
            raise JobDenied('Invalid observer output')
        if spec['task_id'] in ('P1', 'M1'):
            return {'report': self.http_report(value)}
        if not {'report'} <= set(value) or set(value) - {'report', 'storage_evidence','functional_recipient'}:
            raise JobDenied('Invalid observer envelope')
        report = copy.deepcopy(value['report'])
        validate_report(report, spec['instances'])
        if (any(report[k] != spec[k] for k in ('lab_id', 'release_id', 'deployment_id', 'run_id'))
                or report['mission_id'] != spec['task_id'] or report['mode'] != report_mode(spec)):
            raise JobDenied('Wrong observer context')
        if spec['task_id'] in ('P6', 'M6') and spec.get('check_mode')!='functional_prepare':
            self.public_denials(report)
        # Only the coordinator consumes preparation metadata; the original
        # collector and registry determine the final scored report.
        return {'report':report,**{k:value[k] for k in ('storage_evidence','functional_recipient') if k in value}}

    def http_report(self, observed):
        from http_task import contract
        spec, snapshot = self.spec, self.snapshot
        if (any(observed.get(k) != spec[k] for k in ('lab_id', 'deployment_id'))
                or observed.get('mission_id') != spec['task_id']
                or observed.get('instance_id') != spec['instances']['web']
                or observed.get('nonce') != spec['run_id'].replace('-', '')
                or type(observed.get('checks')) is not dict
                or set(observed['checks']) != set(canonical_checks(spec['task_id']))):
            raise JobDenied('HTTP observation belongs to another command')
        expected = contract(spec['task_id'])
        checks = dict(observed['checks'])
        public = snapshot['public_web_ipv4']
        checks['WEB02_PUBLIC_HTTP'] = self.http_probe(public, expected['path'], expected['body'],
            spec['run_id'].replace('-', '')) if public else None
        identity = {k: spec[k] for k in ('lab_id', 'release_id', 'deployment_id', 'instances')}
        return build_report(spec['task_id'], identity, checks, spec['run_id'], checked_at=observed['checked_at'])

    def public_denials(self, report):
        # Same external-entry confirmation as assessment_check.py. Unknown never
        # upgrades an internal failure or produces an evaluable new grade.
        address = self.snapshot['public_web_ipv4']
        control = self.http(address, '/', host='web.lab.test') if address else None
        controls_ok = control is not None and control[0] == 200
        groups = {
            'WEB07_PUBLIC_ADMIN_DENIED': ('/admin', '/admin/', '/admin/catalog/item/add/', '//admin/', '/%61dmin/'),
            'WEB07_SECRET_HTTP_DENIED': ('/.env', '/app.env', '/setup.env', '/etc/jdu-catalog/app.env', '/static/app.env')}
        for cid, paths in groups.items():
            values = [self.http(address, path,
                host='admin.lab.test:8080' if cid == 'WEB07_PUBLIC_ADMIN_DENIED' else 'web.lab.test',
                headers={'X-JDU-Entry': 'admin'}) for path in paths] if controls_ok else []
            result = None if not values or any(v is None for v in values) else all(v[0] in (403, 404) for v in values)
            item = next(c for c in report['checks'] if c['id'] == cid)
            if result is False or item['status'] == 'FAIL':
                item['status'] = 'FAIL'
            elif result is None or item['status'] == 'UNKNOWN':
                item['status'] = 'UNKNOWN'
