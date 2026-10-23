"""Temporary first-boot network acceptance; stops after a verified close transition.

No token, private key, password or presigned URL is read. This is foundation
connectivity evidence, never an assessment score or CLASS_READY decision.
"""
from datetime import datetime,timezone
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
from urllib.parse import urlsplit


def connects(address):
    try:
        connection=socket.create_connection((address,443),timeout=3)
    except OSError:
        return False
    connection.close(); return True


def teacher_health(config):
    host=urlsplit(config['grading_api_url']).hostname
    connection=socket.create_connection((config['grading_ipv4'],443),timeout=5)
    with ssl.create_default_context().wrap_socket(connection,server_hostname=host) as stream:
        stream.sendall(('GET /healthz HTTP/1.1\r\nHost: '+host+'\r\nConnection: close\r\n\r\n').encode())
        response=http.client.HTTPResponse(stream); response.begin()
        return response.status==200 and json.loads(response.read(64*1024))['service']=='jdu-web-progress'


def repo_health(config):
    connection=http.client.HTTPConnection('10.20.2.30',timeout=5)
    try:
        connection.request('GET','/releases/'+config['release_id']+'/manifests/release.json')
        response=connection.getresponse(); data=response.read(2*1024**2)
        return response.status==200 and json.loads(data)['release_id']==config['release_id']
    finally:
        connection.close()


def main():
    config=json.loads(Path('/etc/jdu-web/bootstrap.json').read_text())
    target=Path('/var/lib/jdu-web/bootstrap/network-probe.json')
    previous=json.loads(target.read_text()) if target.exists() else {}
    s3=connects(config['s3_probe_ipv4'])
    checks={'repo_http':repo_health(config),'direct_api_egress_denied':not connects(config['direct_api_probe_ipv4'])}
    if config['role']=='bastion':
        try: checks['fixed_teacher_https']=teacher_health(config)
        except (OSError,ValueError,http.client.HTTPException): checks['fixed_teacher_https']=False
    else:
        checks['teacher_ingress_denied']=not connects(config['grading_ipv4'])
    seen=previous.get('s3_bootstrap_reachable_seen',False) or s3
    phase='BOOTSTRAP_OBSERVED' if s3 else 'LOCK_TRANSITION_OBSERVED' if seen else 'NO_BOOTSTRAP_BASELINE'
    result={k:config[k] for k in ('lab_id','deployment_id','release_id','role','instance_id','expected_scope')}
    result.update(scope='temporary_foundation_network_only',checked_at=datetime.now(timezone.utc).isoformat(),
        phase=phase,s3_tcp_reachable=s3,s3_bootstrap_reachable_seen=seen,checks=checks,
        all_role_network_checks_passed=all(checks.values()),class_ready=False)
    pending=target.with_suffix('.tmp'); pending.write_text(json.dumps(result,indent=2)+'\n'); os.replace(pending,target)
    # Console output only changes when observed connectivity changes.
    if (previous.get('phase'),previous.get('checks'))!=(phase,checks):
        with Path('/dev/ttyS0').open('a') as console:
            console.write('JDU_NODE_NETWORK_RESULT='+json.dumps(result)+'\n'); console.flush()
    if phase=='LOCK_TRANSITION_OBSERVED' and all(checks.values()):
        subprocess.run(['systemctl','stop','jdu-web-network-probe.timer'],check=True)


if __name__=='__main__':
    try: main()
    except Exception as exc:
        with Path('/dev/ttyS0').open('a') as console:
            console.write('JDU_NODE_NETWORK_FAILED='+type(exc).__name__+'\n')
        raise SystemExit(2)
