"""Internal grade projection for a verified portal identity; not an HTTP handler.

The caller must verify the Google signature, issuer, audience and organization
and pass the verified `sub` claim, never a browser-supplied identity. A trusted
teacher-side process must create SUBJECT bindings; this module never creates or
changes any binding or grades. Do not expose it as a public Lambda endpoint.
"""
import hmac
import re

import progress_api as legacy
from grade_reader import project_student
from identity_keys import subject_key


def resolve_student(verified_subject, pepper, bindings, grade_store):
    """Resolve one subject to its current authorized Lab and metadata.

    `bindings.get` and `grade_store.get` must use strongly consistent reads;
    `grade_store.labs` is the existing assessment store's projection source.
    Teacher approval, Google verification and secure service access are separate
    prerequisites. This read does not establish a binding or grant access.
    """
    try:
        subject_pk = subject_key(verified_subject, pepper)
    except ValueError:
        raise legacy.ApiError(401, 'unauthorized') from None

    def denied():
        raise legacy.ApiError(401, 'unauthorized')

    person = bindings.get(subject_pk, 'BINDING')
    if not isinstance(person, dict) or person.get('active') is not True:
        denied()
    lab, account = person.get('lab_id'), person.get('account')
    deployment, token, connector = person.get('deployment_id'), person.get('token_hash'), person.get('connector')
    if (not isinstance(lab, str) or not legacy.LAB_RE.fullmatch(lab)
            or not isinstance(account, str) or not re.fullmatch(r'[0-9]{12}', account)
            or not isinstance(deployment, str) or not deployment
            or not isinstance(token, str) or not re.fullmatch(r'[a-f0-9]{64}', token)
            or not isinstance(connector, str) or not re.fullmatch(r'[a-f0-9]{64}', connector)):
        denied()
    expected = {'lab_id': lab, 'account': account, 'deployment_id': deployment, 'connector': connector}
    mirror = bindings.get('LAB#' + lab, 'SUBJECT')
    if not isinstance(mirror, dict) or mirror.get('subject_pk') != subject_pk:
        denied()
    for pk in ('LAB#' + lab, 'ACCOUNT#' + account):
        row = bindings.get(pk, 'BINDING')
        if not isinstance(row, dict) or any(row.get(k) != v for k, v in expected.items()):
            denied()
    meta = grade_store.get('LAB#' + lab, 'META')
    if (not isinstance(meta, dict) or meta.get('active') is not True
            or meta.get('lab_id') != lab or meta.get('deployment_id') != deployment
            or not isinstance(meta.get('token_hash'), str)
            or not hmac.compare_digest(meta['token_hash'], token)):
        denied()
    approval = None
    approval_pk = person.get('approval_pk')
    if approval_pk is not None:
        if not isinstance(approval_pk, str) or not re.fullmatch(r'APPROVAL#[a-f0-9]{64}', approval_pk):
            denied()
        approval = bindings.get(approval_pk, 'LAB')
        grant = approval.get('grant') if isinstance(approval, dict) else None
        if (not isinstance(approval, dict) or approval.get('active') is not True
                or approval.get('bound_subject') != subject_pk or not isinstance(grant, dict)
                or grant.get('account') != account
                or any(grant.get(k) != meta.get(k) for k in ('lab_id', 'deployment_id', 'token_hash', 'instances'))):
            denied()
    labs = grade_store.labs(lab)
    if len(labs) != 1:
        raise legacy.ApiError(503, 'grade unavailable')
    latest = labs[0]
    if (latest.get('active') is not True or latest.get('lab_id') != lab
            or latest.get('deployment_id') != deployment or not isinstance(latest.get('token_hash'), str)
            or not hmac.compare_digest(latest['token_hash'], token)):
        denied()
    # Recheck revocation and binding changes after the projection read.
    if bindings.get(subject_pk, 'BINDING') != person:
        denied()
    if bindings.get('LAB#' + lab, 'SUBJECT') != mirror:
        denied()
    if approval is not None and bindings.get(approval_pk, 'LAB') != approval:
        denied()
    for pk in ('LAB#' + lab, 'ACCOUNT#' + account):
        row = bindings.get(pk, 'BINDING')
        if not isinstance(row, dict) or any(row.get(k) != v for k, v in expected.items()):
            denied()
    return expected, latest


def identity_grade(verified_subject, pepper, bindings, grade_store, task_id=None):
    """Read the existing grade projection for one resolved student."""
    _, latest = resolve_student(verified_subject, pepper, bindings, grade_store)
    return project_student(latest, task_id)
