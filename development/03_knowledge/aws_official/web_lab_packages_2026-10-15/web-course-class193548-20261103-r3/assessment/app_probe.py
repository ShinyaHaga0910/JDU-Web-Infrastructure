"""Real HTTP authentication and own-record probes. Passwords/cookies never enter reports."""
import http.client as http_client
from http.cookies import SimpleCookie
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit

from network_checks import inventory, http, normal_resolve
from registry import REGISTRY


class Form(HTMLParser):
    def __init__(self):
        super().__init__(); self.token = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'input' and a.get('name') == 'csrfmiddlewaretoken':
            self.token = a.get('value')


class AdminClient:
    def __init__(self, address='admin.lab.test', port=8080):
        if address == 'admin.lab.test':
            if normal_resolve(address, '10.20.1.20') is not True:
                raise ValueError('Resolve the private administrator to the registered Web before authentication')
            address = '10.20.1.20'
        self.address, self.port, self.cookies = address, port, {}
        self.origin = 'http://admin.lab.test:8080'
        self.token = None

    def request(self, path, fields=None):
        if not path.startswith('/admin/') or path.startswith('//') or any(c in path for c in '\r\n'):
            raise ValueError('Only the private admin routes are permitted')
        conn = http_client.HTTPConnection(self.address, self.port, timeout=8)
        try:
            headers = {'Host': 'admin.lab.test:8080', 'Origin': self.origin, 'Referer': self.origin + path,
                       'Cookie': '; '.join(k + '=' + v for k, v in self.cookies.items()), 'Connection': 'close'}
            body = None
            if fields is not None:
                if not self.token:
                    raise ValueError('Real CSRF token required before POST')
                fields = dict(fields, csrfmiddlewaretoken=self.token)
                body = urlencode(fields)
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
            conn.request('GET' if fields is None else 'POST', path, body=body, headers=headers)
            response = conn.getresponse()
            for name, value in response.getheaders():
                if name.lower() == 'set-cookie':
                    cookie = SimpleCookie(); cookie.load(value)
                    for key, entry in cookie.items():
                        if entry['max-age'] == '0':
                            self.cookies.pop(key, None)
                        else:
                            self.cookies[key] = entry.value
            raw = response.read(512 * 1024 + 1)
            if len(raw) > 512 * 1024:
                raise ValueError('Admin response too large')
            text = raw.decode('utf-8', errors='replace')
            parser = Form(); parser.feed(text)
            self.token = parser.token or self.cookies.get('csrftoken')
            return response.status, response.getheader('Location', ''), text
        finally:
            conn.close()

    def login(self, username, password):
        status, _, _ = self.request('/admin/login/')
        if status != 200:
            return False
        status, target, _ = self.request('/admin/login/', {'username': username, 'password': password, 'next': '/admin/'})
        if status != 302 or target != '/admin/':
            return False
        status, _, text = self.request('/admin/catalog/item/')
        return status == 200 and username in text and 'sessionid' in self.cookies


def public_match(code, expected, *, address='web.lab.test', port=80):
    response = http(address, '/', host='web.lab.test', port=port)
    if response is None:
        return None
    if response[0] != 200:
        return False
    rows = inventory(response[2])
    return rows.get(code, [])[:3] == [expected['name'], str(expected['quantity']), expected['location']]


def probe(profile, nonce, password, lookup, *, client_factory=AdminClient, public=public_match):
    """lookup queries PostgreSQL through the existing pinned SSH management path."""
    p = REGISTRY['profiles'][profile]
    code = 'CK-' + ('P' if profile == 'practice' else 'M') + '-' + nonce[:12]
    if lookup(code) is not None:
        raise ValueError('Existing probe record retained; use a new run ID')
    client = client_factory()
    out = dict.fromkeys(('WEB06_PASSWORD_LOGIN', 'WEB06_CREATE_REFLECT', 'WEB06_EDIT_REFLECT',
                         'WEB06_LOGOUT', 'WEB07_ANONYMOUS_DENIED', 'WEB07_BAD_PASSWORD_DENIED'))
    logged_in = False
    try:
        logged_in = client.login(p['app_admin'], password)
        out['WEB06_PASSWORD_LOGIN'] = logged_in
        if not logged_in:
            return out
        record = dict(code=code, name='Automated check item', quantity=1, location='Check shelf', is_public=True)
        client.request('/admin/catalog/item/add/')
        fields = dict(code=code, name=record['name'], quantity=1, location=record['location'],
                      description='', is_public='on', _save='Save')
        status, _, _ = client.request('/admin/catalog/item/add/', fields)
        saved = lookup(code)
        out['WEB06_CREATE_REFLECT'] = (status == 302 and saved is not None and all(saved.get(k) == v for k, v in record.items())
                                      and public(code, record) is True)
        if not saved or type(saved.get('id')) is not int:
            return out
        path = '/admin/catalog/item/' + str(saved['id']) + '/change/'
        client.request(path)
        fields['quantity'] = 2; record['quantity'] = 2
        status, _, _ = client.request(path, fields)
        updated = lookup(code)
        out['WEB06_EDIT_REFLECT'] = (status == 302 and updated is not None and all(updated.get(k) == v for k, v in record.items())
                                    and public(code, record) is True)
        # A valid CSRF token comes from this anonymous client's own login page.
        anon = client_factory(); anon.request('/admin/login/')
        denied_code = 'CK-D-' + nonce[:12]
        if lookup(denied_code) is not None:
            raise ValueError('Existing denial probe record retained')
        denied_fields = dict(fields, code=denied_code)
        status_add, target_add, _ = anon.request('/admin/catalog/item/add/', denied_fields)
        status_edit, target_edit, _ = anon.request(path, dict(fields, quantity=99))
        after = lookup(code)
        out['WEB07_ANONYMOUS_DENIED'] = (out['WEB06_CREATE_REFLECT'] is True
            and status_add == status_edit == 302 and target_add.startswith('/admin/login/') and target_edit.startswith('/admin/login/')
            and lookup(denied_code) is None and after == updated)
        bad = client_factory()
        import secrets
        bad_login = bad.login(p['app_admin'], 'incorrect-' + secrets.token_urlsafe(24))
        status, target, _ = bad.request('/admin/catalog/item/')
        out['WEB07_BAD_PASSWORD_DENIED'] = not bad_login and status == 302 and target.startswith('/admin/login/') and 'sessionid' not in bad.cookies
        return out
    finally:
        if logged_in:
            try:
                client.request('/admin/catalog/item/')
                original_cookies = client.cookies.copy()
                status, _, _ = client.request('/admin/logout/', {})
                replay = client_factory(); replay.cookies = original_cookies
                replay_status, target, _ = replay.request('/admin/catalog/item/')
                out['WEB06_LOGOUT'] = status in (200, 302) and replay_status == 302 and target.startswith('/admin/login/')
            except (OSError, ValueError, http_client.HTTPException):
                out['WEB06_LOGOUT'] = None
        client.cookies.clear()
