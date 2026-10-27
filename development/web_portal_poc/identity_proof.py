"""Experimental STS identity proof; not a production enrollment endpoint.

The challenge store must be created by an authenticated teacher-side session,
and its consume operation must be atomic. This module does not authenticate
students, bind an endpoint, or establish that a caller owns a particular lab.
Never log proof URLs: they contain short-lived signed authentication material.
"""
from datetime import datetime, timedelta, timezone
import http.client
import re
from urllib.parse import parse_qsl, urlsplit
import xml.etree.ElementTree as ET

HOST = 'sts.us-east-1.amazonaws.com'
MAX_URL = 8192
NONCE = re.compile(r'[a-f0-9]{64}\Z')
ACCOUNT = re.compile(r'[0-9]{12}\Z')


class ProofError(ValueError):
    pass


def validate(proof_url, nonce, now=None):
    """Constrain the signed request before sending it to the fixed AWS host."""
    if not isinstance(nonce, str) or not NONCE.fullmatch(nonce):
        raise ProofError('invalid challenge')
    if not isinstance(proof_url, str) or len(proof_url) > MAX_URL:
        raise ProofError('invalid proof')
    try:
        url = urlsplit(proof_url)
        if (url.scheme != 'https' or url.netloc != HOST or url.path != '/'
                or url.fragment or not url.query or '%' in url.netloc):
            raise ProofError('invalid endpoint')
        pairs = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True, max_num_fields=16)
        params = dict(pairs)
        if len(params) != len(pairs):
            raise ProofError('duplicate parameters')
        required = {'Action', 'Version', 'X-Amz-Algorithm', 'X-Amz-Credential',
                    'X-Amz-Date', 'X-Amz-Expires', 'X-Amz-SignedHeaders', 'X-Amz-Signature'}
        if (not required <= set(params) or set(params) - required - {'X-Amz-Security-Token'}
                or params['Action'] != 'GetCallerIdentity' or params['Version'] != '2011-06-15'
                or params['X-Amz-Algorithm'] != 'AWS4-HMAC-SHA256'
                or params['X-Amz-SignedHeaders'] != 'host;x-jdu-nonce'
                or not re.fullmatch(r'[a-f0-9]{64}', params['X-Amz-Signature'])
                or not re.fullmatch(r'[1-9][0-9]?', params['X-Amz-Expires'])):
            raise ProofError('invalid signed request')
        expires = int(params['X-Amz-Expires'])
        stamp = datetime.strptime(params['X-Amz-Date'], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        scope = params['X-Amz-Credential'].split('/')
        if (expires > 60 or len(scope) != 5 or not scope[0]
                or scope[1:] != [stamp.strftime('%Y%m%d'), 'us-east-1', 'sts', 'aws4_request']):
            raise ProofError('invalid signature scope')
        now = now or datetime.now(timezone.utc)
        if now < stamp - timedelta(seconds=5) or now >= stamp + timedelta(seconds=expires):
            raise ProofError('expired proof')
    except (ValueError, TypeError, OverflowError) as exc:
        if isinstance(exc, ProofError):
            raise
        raise ProofError('invalid proof') from None
    return '/?' + url.query


def fetch_sts(path, nonce):
    """Contact the single fixed AWS STS host; never follow redirects."""
    connection = http.client.HTTPSConnection(HOST, timeout=5)
    try:
        connection.request('GET', path, headers={'x-jdu-nonce': nonce})
        response = connection.getresponse()
        body = response.read(16385)
        if response.status != 200 or len(body) > 16384:
            raise ProofError('identity verification failed')
        root = ET.fromstring(body)
        found = root.findall('.//{https://sts.amazonaws.com/doc/2011-06-15/}Account')
        if len(found) != 1 or not ACCOUNT.fullmatch(found[0].text or ''):
            raise ProofError('invalid identity response')
        return found[0].text
    except (OSError, ET.ParseError, http.client.HTTPException):
        raise ProofError('identity verification unavailable') from None
    finally:
        connection.close()


def verify(proof_url, nonce, session_id, expected_account, challenge_store, *, now=None, fetch=fetch_sts):
    """Verify a caller account and atomically consume its session-bound challenge."""
    if not isinstance(expected_account, str) or not ACCOUNT.fullmatch(expected_account):
        raise ProofError('invalid expected account')
    path = validate(proof_url, nonce, now)
    if not challenge_store.is_pending(nonce, session_id, expected_account):
        raise ProofError('challenge unavailable')
    account = fetch(path, nonce)
    if account != expected_account:
        raise ProofError('wrong AWS account')
    if not challenge_store.consume(nonce, session_id, expected_account):
        raise ProofError('challenge already used or expired')
    return account
