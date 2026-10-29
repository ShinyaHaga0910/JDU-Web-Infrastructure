import test from 'node:test';
import assert from 'node:assert/strict';
import { bootstrapTemplate,createBootstrapLink } from './bootstrap-link.mjs';

const teacher='111111111111', hash='a'.repeat(64), now=1900000000000;
const template=`https://jdu-web-portal-bootstrap-${teacher}-${hash.slice(0,12)}.s3.us-east-1.amazonaws.com/bootstrap/${hash}/account-link.template.json?versionId=immutable-version`;
const env={PORTAL_AWS_ACCOUNT_ID:teacher,PORTAL_BOOTSTRAP_TEMPLATE_URL:template};
const pending={registered:false,account:'123456789012',lab_id:'test-lab',pair_id:'d'.repeat(64),expires_at:now/1000+300};

test('quick-create carries public approved parameters and one immutable version only',()=>{
  const url=new URL(createBootstrapLink(env,pending,()=>now));
  assert.equal(url.origin,'https://us-east-1.console.aws.amazon.com');
  const params=new URLSearchParams(url.hash.slice(url.hash.indexOf('?')+1));
  assert.equal(params.get('templateURL'),template);
  assert.equal(params.get('param_ExpectedAccount'),pending.account);
  assert.equal(params.get('param_LabId'),pending.lab_id);
  assert.equal(params.get('param_PairId'),pending.pair_id);
  assert.equal(params.get('stackName'),'jdu-web-link-test-lab-'+pending.pair_id.slice(0,12));
  assert.deepEqual([...params.keys()].sort(),['param_ExpectedAccount','param_LabId','param_PairId','stackName','templateURL'].sort());
  assert.equal(createBootstrapLink(env,pending,()=>now),url.toString());
});

test('arbitrary hosts, mutable templates and signed credential URLs never enter the link',()=>{
  for (const value of [template.replace('s3.us-east-1.amazonaws.com','evil.example'),template.replace(teacher,'222222222222'),
                       template.split('?')[0],template+'&X-Amz-Signature=secret',template.replace('immutable-version','null'),
                       template+'&versionId=other',template.replace(hash.slice(0,12)+'.s3','b'.repeat(12)+'.s3'),
                       template.replace('https:','http:'),template+'#fragment']) {
    assert.throws(()=>bootstrapTemplate({...env,PORTAL_BOOTSTRAP_TEMPLATE_URL:value}));
  }
});

test('expired or malformed attempts cannot launch a new helper stack',()=>{
  for (const changes of [{expires_at:now/1000},{expires_at:now/1000+306},{account:'other'},
                        {lab_id:'<script>'},{registered:true},{pair_id:'invalid'}]) {
    assert.throws(()=>createBootstrapLink(env,{...pending,...changes},()=>now));
  }
});
