"""Fixed student-side progress recipient and encrypted registration adapters."""
import base64
import hashlib
import json
from pathlib import Path
import re

from boto3.dynamodb.types import TypeDeserializer
from initial_ssm import JournaledSsm
from portal_enrollment import EnrollmentDenied, encoded, key, grant_digest


class InitialRegistrationGuest:
    def __init__(self,setup):
        self.setup=setup
        self.s=setup.s

    def saved(self,sk):
        s=self.s
        item=s.db.get_item(TableName=s.table,Key=key(s.pk,sk),ConsistentRead=True).get('Item')
        row={k:TypeDeserializer().deserialize(v) for k,v in item.items()} if item else None
        if row and row.get('grant_digest')!=grant_digest(s.grant):raise EnrollmentDenied('Registration context changed')
        from initial_worker import native
        return native(row)

    def context(self):
        setup=self.setup
        setup.row=setup.get()
        if not setup.row or setup.row['phase']!='registration_pending' or setup.row.get('busy'):
            raise EnrollmentDenied('Foundation and permanent internal SSH required')
        nodes=setup.teaching_nodes()
        return nodes,{**{k:self.s.grant[k] for k in ('lab_id','deployment_id')},
            'release_id':self.s.verified['manifest']['release_id'],'instance_id':nodes['bastion']['instance_id']}

    def remote(self,phase,request):
        import progress_enrollment_guest
        from setup_internal_ssh import remote
        source=Path(progress_enrollment_guest.__file__).read_bytes()
        request=json.loads(json.dumps(request,sort_keys=True))
        return remote(JournaledSsm(self.s,self.setup.ssm,phase,self.setup.remaining),
                      request['instance_id'],source,request)

    def store(self,sk,body):
        s=self.s
        row={'pk':s.pk,'sk':sk,'grant_digest':grant_digest(s.grant),**body}
        try:s.db.put_item(TableName=s.table,Item=encoded(row),ConditionExpression='attribute_not_exists(pk)')
        except s.db.exceptions.ConditionalCheckFailedException:
            if self.saved(sk)!=row:raise EnrollmentDenied('Existing registration retained') from None
        return row

    def recipient(self):
        nodes,common=self.context()
        old=self.saved('RECIPIENT')
        instances={r:n['instance_id'] for r,n in nodes.items()}
        if old:
            if old['context']!={**common,'account':self.s.grant['account'],'instances':instances}:
                raise EnrollmentDenied('Existing recipient belongs to another environment')
            return old['recipient']
        public=self.remote('progress-recipient',{**common,'command':'recipient'})
        cert=public.get('certificate_pem')
        if (type(public) is not dict or set(public)!={'certificate_pem','certificate_sha256'}
                or not isinstance(cert,str) or not 64<=len(cert)<=8192 or not cert.startswith('-----BEGIN CERTIFICATE-----\n')
                or hashlib.sha256(cert.encode()).hexdigest()!=public['certificate_sha256']):
            raise EnrollmentDenied('Invalid recipient certificate')
        value={**common,'account':self.s.grant['account'],'instances':instances}
        recipient={**value,**public}
        self.store('RECIPIENT',{'context':value,'recipient':recipient})
        return recipient

    def register(self,delivery):
        previous=self.saved('ENROLLED')
        if previous:
            if type(delivery) is not dict or previous['delivery_digest']!=grant_digest(delivery):
                raise EnrollmentDenied('Existing credential retained')
            return previous['receipt']
        nodes,common=self.context()
        old=self.saved('RECIPIENT')
        if (not old or type(delivery) is not dict
                or set(delivery)!={'schema_version','certificate_sha256','ciphertext_b64','token_hash'}
                or type(delivery['schema_version']) is not int or delivery['schema_version']!=1
                or delivery['certificate_sha256']!=old['recipient']['certificate_sha256']
                or not isinstance(delivery['token_hash'],str) or not re.fullmatch(r'[a-f0-9]{64}',delivery['token_hash'])
                or not isinstance(delivery['ciphertext_b64'],str) or len(delivery['ciphertext_b64'])!=512
                or len(base64.b64decode(delivery['ciphertext_b64'],validate=True))!=384
                or old['context']!={**common,'account':self.s.grant['account'],
                                   'instances':{r:n['instance_id'] for r,n in nodes.items()}}):
            raise EnrollmentDenied('Own retained recipient and encrypted credential required')
        import web_progress
        client=Path(web_progress.__file__).read_bytes()
        answer=self.remote('progress-register',{**common,'command':'register_oaep',
            'certificate_sha256':delivery['certificate_sha256'],'ciphertext_b64':delivery['ciphertext_b64'],
            'client_source_b64':base64.b64encode(client).decode(),'client_sha256':hashlib.sha256(client).hexdigest()})
        if (any(answer.get(k)!=common[k] for k in ('lab_id','release_id','deployment_id'))
                or answer.get('registered') is not True or answer.get('instance_count')!=5
                or answer.get('private_credential_exported') is not False or answer.get('transport_private_key_retired') is not True
                or answer.get('token_hash')!=delivery['token_hash']):
            raise EnrollmentDenied('Registration acknowledgment differs')
        receipt={**{k:common[k] for k in ('lab_id','release_id','deployment_id')},
            'registered':True,'instance_count':5,'private_credential_exported':False,
            'transport_private_key_retired':True,'token_hash':delivery['token_hash']}
        self.store('ENROLLED',{'delivery_digest':grant_digest(delivery),'receipt':receipt})
        return receipt
