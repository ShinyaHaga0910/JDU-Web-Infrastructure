"""Validate the five-node dependency graph and the teaching-only network update."""
import hashlib
import json
import re
import unittest

import make_five_node_template as builder


class FiveNodeTests(unittest.TestCase):
    def setUp(self):
        self.template=builder.make_template(); self.resources=self.template['Resources']

    def test_all_roles_sizes_ips_and_public_subnets(self):
        instances={k:v for k,v in self.resources.items() if v['Type']=='AWS::EC2::Instance'}
        self.assertEqual(len(instances),5)
        self.assertEqual(sum(v['Properties']['BlockDeviceMappings'][0]['Ebs']['VolumeSize'] for v in instances.values()),96)
        for role,label in builder.NAMES.items():
            p=instances[label+'Instance']['Properties']
            self.assertEqual(p['PrivateIpAddress'],builder.IPS[role]); self.assertNotIn('IamInstanceProfile',p)
            self.assertEqual(p['SubnetId'],{'Ref':'PublicSubnet' if role in ('bastion','web') else 'PrivateSubnet'})
            self.assertEqual(p['SecurityGroupIds'],[{'Ref':label+'Sg'},{'Ref':'BootstrapSg'}])
            self.assertEqual(p['MetadataOptions']['HttpTokens'],'required')
            text=p['UserData']['Fn::Base64']['Fn::Sub']; self.assertLess(len(text.encode()),16384)
            self.assertNotIn('DeploymentPhase',text); self.assertNotIn('IsBootstrap',text)
            config=json.loads(json.loads(text.split('\n',1)[1])['write_files'][0]['content'])
            self.assertEqual('rdp_hash' in config,role=='bastion')
            self.assertEqual('bundle_url' in config,role=='repo')
            for name,sha in config['script_pins'].items():
                self.assertEqual(sha,hashlib.sha256((builder.HERE/name).read_bytes()).hexdigest())

    def test_security_rules_and_teaching_change_scope(self):
        groups={k:v['Properties'] for k,v in self.resources.items() if v['Type']=='AWS::EC2::SecurityGroup'}
        self.assertEqual(len(groups),6)
        incoming=groups['BastionSg']['SecurityGroupIngress']; self.assertEqual(len(incoming),50)
        self.assertTrue(all(p['FromPort']==3389 and p['ToPort']==3389 and p['CidrIp']!='0.0.0.0/0' for p in incoming))
        for p in groups.values():
            self.assertIn({'IpProtocol':'-1','CidrIp':'127.0.0.1/32'},p['SecurityGroupEgress'])
        phase_resources={k for k,v in self.resources.items() if 'IsBootstrap' in json.dumps(v)}
        self.assertEqual(phase_resources,{'BootstrapSg','S3Endpoint'})
        statements=self.resources['S3Endpoint']['Properties']['PolicyDocument']['Fn::If']
        self.assertEqual(statements[2]['Statement'],[{'Effect':'Deny','Principal':'*','Action':'s3:*','Resource':'*'}])
        self.assertEqual(statements[1]['Statement'][0]['Condition'],{'IpAddress':{'aws:VpcSourceIp':'10.20.2.30/32'}})
        self.assertTrue(self.template['Parameters']['RdpPasswordHash']['NoEcho'])
        self.assertTrue(self.template['Parameters']['BundleUrl']['NoEcho'])

    def test_dependency_graph_has_no_cycle_and_waits_for_guest_results(self):
        names=set(self.resources)
        def refs(value):
            found=set()
            if isinstance(value,dict):
                if 'Ref' in value and value['Ref'] in names: found.add(value['Ref'])
                if 'Fn::Sub' in value and isinstance(value['Fn::Sub'],str):
                    found.update(x for x in re.findall(r'\$\{([A-Za-z0-9]+)\}',value['Fn::Sub']) if x in names)
                for child in value.values(): found.update(refs(child))
            elif isinstance(value,list):
                for child in value: found.update(refs(child))
            return found
        graph={}
        for name,resource in self.resources.items():
            depends=resource.get('DependsOn',[]); depends=[depends] if isinstance(depends,str) else depends
            graph[name]=refs(resource)|set(depends)
        done=set()
        while len(done)<len(names):
            ready={name for name,deps in graph.items() if name not in done and deps<=done}
            self.assertTrue(ready,'Dependency cycle: '+str(names-done)); done.update(ready)
        self.assertEqual(self.resources['RepoReady']['Properties']['Count'],1)
        self.assertEqual(self.resources['AllNodesReady']['Properties']['Count'],4)
        for label in ('Bastion','Web','Dns','Db'):
            self.assertIn('RepoReady',self.resources[label+'Instance']['DependsOn'])


if __name__=='__main__': unittest.main()
