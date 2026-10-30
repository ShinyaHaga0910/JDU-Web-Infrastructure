"""Fixed new-Lab runtime context from its own immutable package and journal."""
import hashlib
import json
from pathlib import Path
import re
from boto3.dynamodb.types import TypeDeserializer
from initial_worker import runtime_files,native,plan_digest
from portal_enrollment import EnrollmentDenied,key,grant_digest


def get(db,table,grant,sk):
    item=db.get_item(TableName=table,Key=key('INITIAL#'+grant['deployment_id'],sk),ConsistentRead=True).get('Item')
    row=native({k:TypeDeserializer().deserialize(v) for k,v in item.items()}) if item else None
    if row and row.get('grant_digest')!=grant_digest(grant):raise EnrollmentDenied('Journal assignment changed')
    return row


def context(root,env,db,*,require_ready=False):
    root=Path(root);verified,grant=runtime_files(root,env)
    table=env['INITIAL_PROGRESS_TABLE']
    setup=get(db,table,grant,'SETUP');enrolled=get(db,table,grant,'ENROLLED')
    if (not setup or setup.get('phase')!='registration_pending' or setup.get('busy')
            or setup.get('verified_peers')!=4 or not enrolled or enrolled.get('receipt',{}).get('registered') is not True):
        raise EnrollmentDenied('Registered initial foundation required')
    state,baseline=setup['state'],setup['baseline']
    if (any(state.get(k)!=grant[k] or baseline.get(k)!=grant[k] for k in ('account','lab_id','deployment_id'))
            or baseline.get('stack_id')!=state.get('stack_id')
            or not re.fullmatch(r'arn:aws:cloudformation:us-east-1:'+grant['account']+r':stack/jdu-web-'+grant['lab_id']+r'/[a-f0-9-]{36}',state.get('stack_id',''))
            or set(baseline.get('nodes',{}))!={'bastion','web','dns','db','repo'}):
        raise EnrollmentDenied('Registered initial context changed')
    receipt=enrolled['receipt']
    if (any(receipt.get(k)!=grant[k] for k in ('lab_id','deployment_id'))
            or receipt.get('release_id')!=verified['manifest']['release_id']
            or receipt.get('instance_count')!=5 or receipt.get('private_credential_exported') is not False
            or receipt.get('transport_private_key_retired') is not True):
        raise EnrollmentDenied('Registration receipt changed')
    raw=json.loads(verified['files']['template'].read_bytes())
    canonical=(json.dumps(raw,separators=(',',':'))+'\n').encode()
    if hashlib.sha256(canonical).hexdigest()!=baseline.get('proposed_sha256'):
        raise EnrollmentDenied('Reviewed initial template changed')
    data={'state':{**{k:state[k] for k in ('account','lab_id','deployment_id','stack_id')},
                   'release_id':verified['manifest']['release_id']},
        'baseline':{k:baseline[k] for k in ('nodes','proposed_sha256')},'public_key':setup['public_key']}
    if require_ready:
        ready=get(db,table,grant,'READY')
        teaching=(root/'initial-teaching.json').read_bytes()
        if (not ready or ready.get('ready') is not True or ready.get('config_sha256')!=plan_digest(data)
                or ready.get('asset_manifest_sha256')!=hashlib.sha256(teaching).hexdigest()):
            raise EnrollmentDenied('Initial teaching resources and connectors not ready')
    return verified,grant,data
