"""Refresh approved ISP organizations/ASNs and exact IPv4 sets from RIPE."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import gzip
import ipaddress
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request

ORGS={'ORG-UNCN1-RIPE':'Uztelecom','ORG-JC7-RIPE':'Uztelecom','ORG-ET10-RIPE':'ISTTelecom'}


def request(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url,timeout=45) as response: return json.load(response)
        except Exception:
            if attempt==2: raise
            time.sleep(1+attempt)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',required=True); p.add_argument('--snapshot',default='2026-10-15T00:00:00'); a=p.parse_args()
    output=Path(a.output); output.mkdir(parents=True,exist_ok=False)
    registrations=[]; by_provider={name:set() for name in ORGS.values()}
    for org,provider in ORGS.items():
        url='https://rest.db.ripe.net/search.json?'+urllib.parse.urlencode({'inverse-attribute':'org','query-string':org,'type-filter':'aut-num','flags':'no-referenced'})
        response=request(url); asns=[]
        for item in response['objects']['object']:
            attrs=item['attributes']['attribute']; values={x['name']:x['value'] for x in attrs}
            if item['type']!='aut-num' or values.get('org')!=org or not re.fullmatch(r'AS[0-9]+',values.get('aut-num','')):
                raise ValueError('RIPE organization registration differs')
            asns.append(values['aut-num'])
        if not asns: raise ValueError('Approved ISP organization has no registered ASNs')
        by_provider[provider].update(asns); registrations.append({'organization':org,'provider':provider,'asns':sorted(asns),'source':url})
    def prefixes(asn):
        url='https://stat.ripe.net/data/ris-prefixes/data.json?'+urllib.parse.urlencode({'resource':asn,'list_prefixes':'true','types':'o','af':'v4','noise':'filter','query_time':a.snapshot})
        response=request(url)
        if response.get('status')!='ok': raise ValueError('RIPE prefix observation did not succeed')
        networks=[ipaddress.IPv4Network(x,strict=True) for x in response['data']['prefixes']['v4']['originating']]
        if len(networks)!=response['data']['counts']['v4']['originating'] or any(n.prefixlen<8 or not n.network_address.is_global or not n.broadcast_address.is_global for n in networks):
            raise ValueError('Invalid or overbroad ISP prefixes')
        return asn,response,networks,url
    files={}; all_networks={}; sources=[]
    with ThreadPoolExecutor(max_workers=3) as executor:
        for asn,response,networks,url in executor.map(prefixes,sorted(set.union(*by_provider.values()))):
            files[asn+'_ris_prefixes.json']=response; all_networks[asn]=networks
            sources.append({'asn':asn,'prefixes':[str(n) for n in networks],'source':url})
    summary={'snapshot_utc':a.snapshot+'Z','checked_at':datetime.now(timezone.utc).isoformat(),'providers':{}}
    combined=[]
    for provider,asns in by_provider.items():
        original=[n for asn in asns for n in all_networks[asn]]; collapsed=list(ipaddress.collapse_addresses(original)); combined.extend(collapsed)
        summary['providers'][provider]={'asns':sorted(asns),'raw_prefixes':len(original),'collapsed_cidrs':len(collapsed),'ipv4_addresses':sum(n.num_addresses for n in collapsed)}
    combined=list(ipaddress.collapse_addresses(combined)); summary['combined_cidrs']=len(combined); summary['ipv4_addresses']=sum(n.num_addresses for n in combined)
    # Exact collapse preserves the address union; no approximate supernetting.
    original_union={int(address) for prefixes in all_networks.values() for network in prefixes for address in network}
    collapsed_union={int(address) for network in combined for address in network}
    if original_union!=collapsed_union: raise ValueError('Collapsed range expanded or lost addresses')
    files.update({'organization_asn_registration.json':registrations,'asn_origin_prefixes.json':sources,'summary.json':summary,
        'coverage_validation.json':{'exact_union_match':True,'ipv4_addresses':len(original_union)},
        'rdp_ingress_ip_permissions.json':[{'IpProtocol':'tcp','FromPort':3389,'ToPort':3389,'IpRanges':[{'CidrIp':str(n),'Description':'Uztelecom IST Telecom '+a.snapshot[:10]} for n in combined]}]})
    for name,data in files.items(): (output/name).write_text(json.dumps(data,indent=2)+'\n')
    print('RDP_REFRESH_SUMMARY='+json.dumps(summary),flush=True)
    packed=gzip.compress(json.dumps(files,separators=(',',':')).encode(),mtime=0)
    print('RDP_REFRESH_FILES_BEGIN'+base64.b64encode(packed).decode()+'RDP_REFRESH_FILES_END',flush=True)


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('RDP_REFRESH_FAILED='+type(exc).__name__,flush=True)
        raise SystemExit(2)
