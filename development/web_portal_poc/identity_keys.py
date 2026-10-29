"""Stable HMAC identity key shared by enrollment and read-only projection."""
import hashlib
import hmac
import re


def subject_key(subject, pepper):
    # Rotation requires migration; the raw Google subject is never persisted.
    if (not isinstance(subject, str) or not re.fullmatch(r'[0-9]{1,128}', subject)
            or not isinstance(pepper, bytes) or len(pepper) < 32):
        raise ValueError('invalid verified identity or key')
    return 'SUBJECT#' + hmac.new(pepper, subject.encode('ascii'), hashlib.sha256).hexdigest()
