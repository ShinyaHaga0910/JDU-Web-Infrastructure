"""Create an ephemeral STS proof inside the student's AWS execution context.

Return the signed URL only to the trusted enrollment client over HTTPS. It
contains temporary AWS authentication material and must never enter logs, a
browser URL, shell history, files, or shared Windows storage.
"""
import identity_proof


def create_proof(session, nonce):
    """Create a 60-second proof without issuing or storing AWS credentials."""
    if not isinstance(nonce, str) or not identity_proof.NONCE.fullmatch(nonce):
        raise ValueError('invalid challenge')
    from botocore.auth import SigV4QueryAuth
    from botocore.awsrequest import AWSRequest

    credentials = session.get_credentials()
    if credentials is None:
        raise ValueError('student AWS credentials unavailable')
    request = AWSRequest(method='GET',
        url='https://' + identity_proof.HOST + '/?Action=GetCallerIdentity&Version=2011-06-15',
        headers={'x-jdu-nonce': nonce})
    SigV4QueryAuth(credentials.get_frozen_credentials(), 'sts', 'us-east-1', expires=60).add_auth(request)
    identity_proof.validate(request.url, nonce)
    return request.url
