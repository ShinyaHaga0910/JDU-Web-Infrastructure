"""WEB-02 P1/M1 contract and bounded HTTP observation. No configuration changes."""
import errno
import hashlib
import http.client
import ipaddress
import json
from pathlib import Path
import socket

TASKS = {
    'P1': {'module': 'WEB-02', 'path': '/practice.txt', 'file': '/var/www/html/practice.txt',
           'body': 'JDU WEB-02 practice: HTTP response verified.\n'},
    'M1': {'module': 'WEB-02', 'path': '/mission.txt', 'file': '/var/www/html/mission.txt',
           'body': 'JDU WEB-02 mission: independent HTTP delivery.\n'},
}
CHECKS = ('WEB02_IDENTITY', 'WEB02_NGINX_ACTIVE', 'WEB02_CONFIG_VALID',
          'WEB02_LISTEN_80', 'WEB02_FILE', 'WEB02_LOCAL_HTTP',
          'WEB02_BASTION_HTTP', 'WEB02_PUBLIC_HTTP', 'WEB02_ACCESS_LOG',
          'WEB02_REPO_PREREQUISITE')


def contract(task):
    return dict(TASKS[task])  # Fixed by teacher source; never accept expected values from CLI.


def http_probe(address, path, body, nonce, port=80):
    ipaddress.ip_address(address)
    if path not in {v['path'] for v in TASKS.values()} or len(nonce) != 32 or any(c not in '0123456789abcdef' for c in nonce):
        raise ValueError('Invalid HTTP probe target')
    connection = http.client.HTTPConnection(address, port, timeout=5)
    try:
        connection.request('GET', path + '?jdu_check=' + nonce,
                           headers={'Connection': 'close', 'Cache-Control': 'no-cache'})
        response = connection.getresponse()
        raw = response.read(65537)
        return response.status == 200 and raw == body.encode()
    except ConnectionRefusedError:
        return False
    except OSError as exc:
        # Refusal is an observed closed service; silence/unreachable is inconclusive.
        return False if exc.errno == errno.ECONNREFUSED else None
    except (http.client.HTTPException, socket.timeout):
        return None
    finally:
        connection.close()


def build_report(observed, state, nodes, request_id):
    if (observed['mission_id'] not in TASKS or observed['lab_id'] != state['lab_id']
            or observed['deployment_id'] != state['deployment_id']
            or observed['instance_id'] != nodes['web']['instance_id']
            or set(observed['checks']) != set(CHECKS)):
        raise ValueError('Wrong task observation or deployment')
    checks = []
    for name in CHECKS:
        value = observed['checks'][name]
        if value is not None and type(value) is not bool:
            raise ValueError('Expected boolean or UNKNOWN')
        role = 'bastion' if name == 'WEB02_BASTION_HTTP' else 'web'
        checks.append(dict(id=name, role=role, instance_id=nodes[role]['instance_id'],
                           status='UNKNOWN' if value is None else 'PASS' if value else 'FAIL'))
    return dict(schema_version=1, kind='assessment', mission_id=observed['mission_id'],
                lab_id=state['lab_id'], release_id=state['release_id'],
                deployment_id=state['deployment_id'], request_id=request_id, checks=checks)
