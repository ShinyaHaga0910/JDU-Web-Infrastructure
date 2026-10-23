"""Bounded read-only DNS/resolver/HTTP observations. No service or network changes."""
import http.client as http_client
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
import socket
import struct
import subprocess


def command(args, *, env=None, timeout=12, input=None):
    try:
        return subprocess.run(args, input=input, env=env, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return None


def active(service):
    p = command(['systemctl', 'is-active', '--quiet', service])
    return p is not None and p.returncode == 0


def dig(name, kind='A', *, tcp=False, server='10.20.2.10', port=53):
    # UDP must not silently retry over TCP after a truncated answer.
    p = command(['dig', '@' + server, '-p', str(port), name, kind, '+tcp' if tcp else '+notcp', '+ignore',
                 '+time=2', '+tries=1', '+comments', '+answer', '+noauthority', '+noadditional'])
    if p is None or p.returncode != 0:
        return None
    status = re.search(r'status: ([A-Z]+)', p.stdout)
    flags = re.search(r'flags: ([^;]+);', p.stdout)
    rows = [re.split(r'\s+', line.strip(), maxsplit=4) for line in p.stdout.splitlines()
            if line and not line.startswith(';')]
    return dict(status=status[1] if status else None,
                authoritative=bool(flags and 'aa' in flags[1].split()),
                answers=[row for row in rows if len(row) == 5])


def required_records(records, *, tcp=False, server='10.20.2.10', port=53):
    results = [dig(name, tcp=tcp, server=server, port=port) for name in records]
    if any(r is None for r in results):
        return None
    return all(r['status'] == 'NOERROR' and r['authoritative']
               and {row[4] for row in r['answers'] if row[3] == 'A'} == {expected}
               for r, expected in zip(results, records.values()))


def normal_resolve(name, expected):
    p = command(['getent', 'ahostsv4', name], timeout=5)
    if p is None:
        return None
    return p.returncode == 0 and {line.split()[0] for line in p.stdout.splitlines() if line.split()} == {expected}


def resolver_policy(names, *, firefox=False):
    try:
        for line in Path('/etc/hosts').read_text().splitlines():
            tokens = line.split('#', 1)[0].split()
            if set(tokens[1:]) & set(names):
                return False
        resolv = Path('/etc/resolv.conf').read_text()
        servers = re.findall(r'^nameserver\s+(\S+)', resolv, re.M)
        if servers == ['127.0.0.53']:
            p = command(['resolvectl', 'dns'])
            if p is None or p.returncode != 0:
                return None
            servers = [v for line in p.stdout.splitlines() for v in line.partition(':')[2].split()]
        if not servers or set(servers) != {'10.20.2.10'}:
            return False
        if firefox:
            policy = json.loads(Path('/etc/firefox/policies/policies.json').read_text())['policies']['DNSOverHTTPS']
            if policy.get('Enabled') is not False or policy.get('Locked') is not True:
                return False
        return True
    except (OSError, ValueError, KeyError):
        return False


def named_blocks(text):
    """Parse named-checkconf -p output; quoted names and nested ACL blocks stay structured."""
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[{};]|[^\s{};]+', text)
    cursor = 0

    def parse(nested=False):
        nonlocal cursor
        result, head = [], []
        while cursor < len(tokens):
            token = tokens[cursor]; cursor += 1
            if token == '}':
                if not nested or head:
                    raise ValueError('Unbalanced named block')
                return result
            if token == '{':
                children = parse(True)
                result.append((tuple(head), children)); head = []
            elif token == ';':
                if head:
                    result.append((tuple(head), None)); head = []
            else:
                head.append(token.strip('"'))
        if nested or head:
            raise ValueError('Incomplete named block')
        return result
    return parse()


def named_policy(tree):
    if any(head and head[0] == 'view' for head, _ in tree):
        return False, False
    groups = {head[1]: children for head, children in tree if head and head[0] == 'acl' and len(head) == 2}
    opts = [children for head, children in tree if head == ('options',)]
    if len(opts) != 1:
        return False, False
    options = {head[0]: (head[1:], children) for head, children in opts[0] if head}

    def addresses(children, seen=()):
        result = set()
        if children is None:
            raise ValueError('ACL block required')
        for head, nested in children:
            if len(head) != 1 or nested is not None:
                raise ValueError('Complex ACL not accepted without independent verification')
            key = head[0]
            if key in groups:
                if key in seen:
                    raise ValueError('ACL cycle')
                result |= addresses(groups[key], seen + (key,))
            elif key == 'localhost':
                result |= {'127.0.0.1/32', '::1/128'}
            else:
                result.add(str(ipaddress.ip_network(key, strict=False)))
        return result
    try:
        acl = True
        allowed = {'10.20.1.10/32', '10.20.1.20/32', '127.0.0.1/32', '::1/128'}
        for key in ('allow-query', 'allow-recursion', 'allow-query-cache'):
            values = addresses(options[key][1])
            acl &= {'10.20.1.10/32', '10.20.1.20/32'} <= values <= allowed
        for head, children in tree:
            if head and head[0] == 'zone' and len(head) > 1 and head[1] == 'lab.test':
                for child_head, child in children:
                    if child_head and child_head[0] in ('allow-query', 'allow-query-cache', 'allow-recursion'):
                        values = addresses(child)
                        acl &= {'10.20.1.10/32', '10.20.1.20/32'} <= values <= allowed
        forwarders = addresses(options['forwarders'][1])
        forward = options['forward'][0] == ('only',) and forwarders == {'10.20.0.2/32'}
        return bool(acl), bool(forward)
    except (ValueError, KeyError):
        return False, False


def dns_server(records, nonce, *, server='127.0.0.1', port=53):
    out = {'WEB03_SERVICE': active('named')}
    check = command(['named-checkconf', '-z'])
    out['WEB03_CONFIG_VALID'] = check is not None and check.returncode == 0
    # The DNS host itself is an allowed localhost client, not a third private-IP client.
    soa, ns = dig('lab.test', 'SOA', server=server, port=port), dig('lab.test', 'NS', server=server, port=port)
    out['WEB03_ZONE_AUTHORITY'] = None if soa is None or ns is None else (
        soa['status'] == ns['status'] == 'NOERROR' and soa['authoritative'] and ns['authoritative']
        and any(r[3] == 'SOA' and r[4].split()[0] == 'dns.lab.test.' for r in soa['answers'])
        and {r[4] for r in ns['answers'] if r[3] == 'NS'} == {'dns.lab.test.'})
    out['WEB03_REQUIRED_RECORDS'] = required_records(records, server=server, port=port)
    printed = command(['named-checkconf', '-p', '-x'])
    if printed is not None and printed.returncode == 0:
        try:
            acl, forward = named_policy(named_blocks(printed.stdout))
        except ValueError:
            acl, forward = False, False
        out['WEB03_CLIENT_ACL'] = acl
        external = dig('aws.amazon.com', server=server, port=port)
        out['WEB03_FORWARD_ONLY'] = None if external is None else forward and external['status'] == 'NOERROR' and bool(external['answers'])
    else:
        out.update(WEB03_CLIENT_ACL=False, WEB03_FORWARD_ONLY=False)
    absent = dig('absent-' + nonce[:16] + '.lab.test', server=server, port=port)
    out['WEB03_NXDOMAIN'] = None if absent is None else absent['authoritative'] and absent['status'] == 'NXDOMAIN'
    return out


def dns_client(records):
    udp, tcp = required_records(records), required_records(records, tcp=True)
    refused = axfr_refused() if udp is True and tcp is True else None
    return dict(udp=udp, tcp=tcp, axfr=refused)


def axfr_refused(address='10.20.2.10', port=53):
    """An explicit DNS REFUSED/NOTAUTH response, never a timeout/transfer-failed message."""
    import secrets
    transaction = secrets.randbelow(65536)
    question = struct.pack('!HHHHHH', transaction, 0, 1, 0, 0, 0) + b'\x03lab\x04test\0' + struct.pack('!HH', 252, 1)
    try:
        with socket.create_connection((address, port), timeout=3) as connection:
            connection.sendall(struct.pack('!H', len(question)) + question)
            def exact(length):
                result = b''
                while len(result) < length:
                    chunk = connection.recv(length - len(result))
                    if not chunk:
                        raise OSError('Short DNS response')
                    result += chunk
                return result
            length = struct.unpack('!H', exact(2))[0]
            if not 12 <= length <= 65535:
                return None
            response = exact(length)
            received, flags, _, answers, _, _ = struct.unpack('!HHHHHH', response[:12])
            if received != transaction or not flags & 0x8000:
                return None
            return flags & 15 in (5, 9) and answers == 0
    except OSError:
        return None


def http(address, path='/', *, host=None, port=80, fields=None, headers=None):
    original = address
    try:
        ipaddress.ip_address(address)
    except ValueError:
        resolved = command(['getent', 'ahostsv4', address], timeout=5)
        if resolved is None or resolved.returncode != 0 or not resolved.stdout.split():
            return None
        address = resolved.stdout.split()[0]
    conn = http_client.HTTPConnection(address, port, timeout=5)
    try:
        from urllib.parse import urlencode
        h = {'Connection': 'close', 'Cache-Control': 'no-cache', 'Host': host or original}
        h.update(headers or {})
        body = None
        if fields is not None:
            body = urlencode(fields)
            h['Content-Type'] = 'application/x-www-form-urlencoded'
        conn.request('GET' if fields is None else 'POST', path, body=body, headers=h)
        res = conn.getresponse()
        raw = res.read(512 * 1024 + 1)
        if len(raw) > 512 * 1024:
            return None
        return res.status, dict((k.lower(), v) for k, v in res.getheaders()), raw.decode('utf-8', errors='replace')
    except (OSError, http_client.HTTPException):
        return None
    finally:
        conn.close()


class Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        if tag in ('th', 'td') and self.row is not None:
            self.cell = []

    def handle_data(self, text):
        if self.cell is not None:
            self.cell.append(text)

    def handle_endtag(self, tag):
        if tag in ('th', 'td') and self.cell is not None:
            self.row.append(''.join(self.cell).strip()); self.cell = None
        if tag == 'tr' and self.row is not None:
            if len(self.row) == 5:
                self.rows.append(self.row)
            self.row = None


def inventory(html):
    parser = Inventory(); parser.feed(html)
    if len({r[0] for r in parser.rows}) != len(parser.rows):
        raise ValueError('Duplicate inventory codes')
    return {r[0]: r[1:] for r in parser.rows}
