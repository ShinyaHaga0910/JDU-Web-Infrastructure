"""Short-lived, session-bound proof of possession of an existing Lab token."""
import hashlib
import hmac
import re

CHALLENGE = re.compile(r'[a-f0-9]{64}\Z')
TOKEN_HASH = CHALLENGE
CODE = re.compile(r'jdu-link1\.(lab-[a-f0-9]{20})\.([0-9]{12})\.([0-9]{10})\.([a-f0-9]{64})\Z')
CODE_WINDOW = 600


def signed_code(challenge, lab, account, stamp, token_hash):
    if not CHALLENGE.fullmatch(challenge) or not TOKEN_HASH.fullmatch(token_hash):
        raise ValueError('Invalid Lab proof')
    payload = f'jdu-link1.{lab}.{account}.{stamp}'
    mac = hmac.new(bytes.fromhex(token_hash), f'{payload}.{challenge}'.encode('ascii'), hashlib.sha256)
    code = f'{payload}.{mac.hexdigest()}'
    if not CODE.fullmatch(code):
        raise ValueError('Invalid Lab proof')
    return code


def verify_code(challenge, code, token_hash, now):
    match = CODE.fullmatch(code)
    if not match:
        return False
    lab, account, stamp, _ = match.groups()
    return -30 <= now-int(stamp) <= CODE_WINDOW and hmac.compare_digest(
        code, signed_code(challenge, lab, account, stamp, token_hash))
