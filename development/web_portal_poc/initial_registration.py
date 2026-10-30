"""Own pre-provisioned Lab issuance, encrypted delivery and reader binding.

Only the verified portal backend can call these methods. No plaintext token is
accepted or saved here. Existing credentials, grades and bindings are never
adopted or overwritten by an initial-preparation assignment.
"""
import base64
from datetime import datetime,timezone
from decimal import Decimal
import re

from portal_enrollment import EnrollmentDenied,checked_grant,encoded,key,grant_digest


def checked_delivery(value):
    if (type(value) is not dict or set(value)!={'schema_version','certificate_sha256','ciphertext_b64','token_hash'}
            or isinstance(value['schema_version'],bool) or not isinstance(value['schema_version'],(int,Decimal)) or value['schema_version']!=1
            or any(not isinstance(value[k],str) or not re.fullmatch(r'[a-f0-9]{64}',value[k])
                   for k in ('certificate_sha256','token_hash'))
            or not isinstance(value['ciphertext_b64'],str) or not re.fullmatch(r'[A-Za-z0-9+/]{512}',value['ciphertext_b64'])
            or len(base64.b64decode(value['ciphertext_b64'],validate=True))!=384):
        raise EnrollmentDenied('Fixed encrypted student credential required')
    return dict(value,schema_version=1)


def checked_registration(value,assignment):
    if type(value) is not dict or set(value)!={'grant','release_id','delivery'}:
        raise EnrollmentDenied('Registration changed')
    grant=checked_grant(value['grant']);delivery=checked_delivery(value['delivery'])
    if (any(grant[k]!=assignment[k] for k in ('account','lab_id','deployment_id'))
            or value['release_id']!=assignment['release']['release_id'] or grant['token_hash']!=delivery['token_hash']):
        raise EnrollmentDenied('Registration changed')
    return {'grant':grant,'release_id':value['release_id'],'delivery':delivery}


class InitialRegistration:
    def __init__(self,preparation):
        self.prep=preparation
        self.auth=preparation.auth

    def current(self,claims):
        row,person,session=self.prep.current(**claims)
        self.prep.live(row)
        if self.prep.initial is None or row['stage']!='CREATE_REQUESTED' or row.get('bound_subject')!=person:
            raise EnrollmentDenied('Own confirmed preparation required')
        return row,person,session

    def context(self,**claims):
        row,_,_=self.current(claims)
        if row.get('registration'):
            checked_registration(row['registration'],row['grant'])
            return {'issued':True,'registered':row.get('registration_complete') is True}
        value=self.prep.initial(row['grant'],'recipient')
        required={'account','lab_id','deployment_id','release_id','instance_id','instances','certificate_pem','certificate_sha256'}
        if (type(value) is not dict or set(value)!=required
                or any(value[k]!=row['grant'][k] for k in ('account','lab_id','deployment_id'))
                or value['release_id']!=row['grant']['release']['release_id']
                or not isinstance(value['certificate_pem'],str) or len(value['certificate_pem'])>8192):
            raise EnrollmentDenied('Fixed recipient unavailable')
        checked_grant({**{k:value[k] for k in ('account','lab_id','deployment_id','instances')},'token_hash':'0'*64})
        from hashlib import sha256
        if (value['instance_id']!=value['instances']['bastion']
                or sha256(value['certificate_pem'].encode()).hexdigest()!=value['certificate_sha256']):
            raise EnrollmentDenied('Recipient context changed')
        return {'issued':False,'recipient':{k:v for k,v in value.items() if k!='instances'}}

    def issue(self,claims,delivery):
        row,person,session=self.current(claims)
        if row.get('registration'):
            return row
        delivery=checked_delivery(delivery)
        recipient=self.prep.initial(row['grant'],'recipient')
        # Recheck all trusted fields, not the browser-supplied token hash alone.
        context=self.context(**claims)
        if context['issued']:return self.current(claims)[0]
        expected=context['recipient']
        if (recipient.get('certificate_sha256')!=delivery['certificate_sha256']
                or any(recipient.get(k)!=expected[k] for k in expected)):
            raise EnrollmentDenied('Retained recipient differs')
        grant=checked_grant({**{k:row['grant'][k] for k in ('account','lab_id','deployment_id')},
                             'instances':recipient['instances'],'token_hash':delivery['token_hash']})
        registration={'grant':grant,'release_id':recipient['release_id'],'delivery':delivery}
        checked_registration(registration,row['grant'])
        now=int(self.auth.clock());stamp=datetime.fromtimestamp(now,timezone.utc).isoformat()
        meta={'pk':'LAB#'+grant['lab_id'],'sk':'META','lab_id':grant['lab_id'],
              'release_id':registration['release_id'],'token_hash':grant['token_hash'],'active':True,
              'deployment_id':grant['deployment_id'],'instances':grant['instances'],
              'created_at':stamp,'updated_at':stamp}
        update=self.prep.assignment_check(row)['ConditionCheck']
        update['UpdateExpression']='SET registration=:registration'
        update['ConditionExpression']+=' AND bound_subject=:subject AND attribute_not_exists(registration)'
        update['ExpressionAttributeValues'].update(encoded({':subject':person,':registration':registration}))
        # A transaction cannot ConditionCheck and Put the same META item.
        guards=[g for g in self.prep.context_guards(row,person)
                if g['ConditionCheck']['TableName']!=self.auth.grades]
        try:
            self.auth.client.transact_write_items(TransactItems=[{'Update':update},
                self.auth.session_condition({'session_pk':session,'session_token_hash':claims['token_hash']},now),
                *guards,{'Put':{'TableName':self.auth.grades,'Item':encoded(meta),
                               'ConditionExpression':'attribute_not_exists(pk)'}}])
        except self.auth.client.exceptions.TransactionCanceledException:
            latest=self.current(claims)[0]
            if not latest.get('registration'):raise EnrollmentDenied('Original Lab retained') from None
            return latest
        return self.current(claims)[0]

    def register(self,delivery=None,**claims):
        row=self.issue(claims,delivery)
        if row.get('registration_complete') is True:
            return {'registered':True,'lab_id':row['grant']['lab_id']}
        saved=checked_registration(row['registration'],row['grant'])
        answer=self.prep.initial(row['grant'],'register',delivery=saved['delivery'])
        if (type(answer) is not dict or answer.get('registered') is not True or answer.get('instance_count')!=5
                or answer.get('private_credential_exported') is not False or answer.get('transport_private_key_retired') is not True
                or answer.get('token_hash')!=saved['grant']['token_hash']
                or any(answer.get(k)!=saved['grant'][k] for k in ('lab_id','deployment_id'))
                or answer.get('release_id')!=saved['release_id']):
            raise EnrollmentDenied('Own bastion registration not confirmed')
        return self.finish(claims)

    def finish(self,claims):
        row,person,session=self.current(claims)
        saved=checked_registration(row.get('registration'),row['grant']);grant=saved['grant']
        if row.get('registration_complete') is True:
            return {'registered':True,'lab_id':grant['lab_id']}
        now=int(self.auth.clock())
        approval={'pk':row['pk'],'sk':'LAB','active':True,'grant':grant,'grant_digest':grant_digest(grant),
            'bound_subject':person,'enrollment_deadline':int(row['deadline']),'created_at':now}
        records=[approval,*self.auth.binding_records(person,grant,row['pk'])]
        update=self.prep.assignment_check(row)['ConditionCheck']
        update['UpdateExpression']='SET registration_complete=:yes'
        update['ConditionExpression']+=' AND bound_subject=:subject AND registration=:registration AND attribute_not_exists(registration_complete)'
        update['ExpressionAttributeValues'].update(encoded({':yes':True,':subject':person,':registration':saved}))
        meta_condition=self.auth.meta_condition(grant)
        check=meta_condition['ConditionCheck']
        check['ConditionExpression']+=' AND #release=:release'
        check['ExpressionAttributeNames']['#release']='release_id'
        check['ExpressionAttributeValues'].update(encoded({':release':saved['release_id']}))
        try:
            self.auth.client.transact_write_items(TransactItems=[{'Update':update},meta_condition,
                self.auth.session_condition({'session_pk':session,'session_token_hash':claims['token_hash']},now),
                *[{'Put':{'TableName':self.auth.table,'Item':encoded(r),'ConditionExpression':'attribute_not_exists(pk)'}} for r in records]])
        except self.auth.client.exceptions.TransactionCanceledException:
            latest=self.current(claims)[0]
            if latest.get('registration_complete') is not True:raise EnrollmentDenied('Registration conflict') from None
        return {'registered':True,'lab_id':grant['lab_id']}
