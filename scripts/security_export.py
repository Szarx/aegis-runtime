"""Export received governance events and verify an offline investigation bundle."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

FIELDS = ('trace_id','span_id','action_id','tool','subject','permission','policy_revision','rule_id',
          'effect','reason','outcome','service_name','agent_name','status','start_time_unix_nano','end_time_unix_nano')
FILTERS = ('subject','tool','permission','service_name','action_id','trace_id','effect','outcome',
           'started_after_ns','started_before_ns')
LIMIT = 2**63-1
MAX_FILE = 64*1024*1024
NOTICE = 'Received telemetry only; not an authenticated or complete audit, nor a cross-page database snapshot. Hashes do not authenticate the manifest.'


class ExportError(ValueError):
    pass


def require(condition):
    if not condition: raise ExportError('invalid or inconsistent export data')


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def identifier(value):
    return type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}',value) is not None


def hex_id(value, width):
    return type(value) is str and re.fullmatch('[0-9a-f]{'+str(width)+'}',value) is not None and int(value,16)>0


def event(value):
    require(type(value) is dict and set(value)==set(FIELDS))
    require(hex_id(value['trace_id'],32) and hex_id(value['span_id'],16) and hex_id(value['action_id'],32))
    require(identifier(value['tool']))
    require(all(value[k] is None or identifier(value[k]) for k in ('subject','permission','policy_revision','rule_id')))
    require(type(value['service_name']) is str and 0<len(value['service_name'])<=128 and bool(value['service_name'].strip()))
    require(value['agent_name'] is None or type(value['agent_name']) is str and len(value['agent_name'])<=128)
    require(integer(value['start_time_unix_nano'],1,LIMIT) and integer(value['end_time_unix_nano'],value['start_time_unix_nano'],LIMIT))
    reason=value['reason']; outcome=value['outcome']
    if value['effect']=='require_approval':
        require(reason=='explicit_require_approval' and outcome in ('awaiting_approval','completed','error','cancelled'))
    elif value['effect']=='allow':
        require(reason=='explicit_allow' and outcome in ('completed','error','cancelled'))
    else:
        require(value['effect']=='deny' and outcome=='denied' and reason in ('explicit_deny','no_match','identity_missing','permission_missing','policy_unavailable','policy_error'))
    require(value['status']==('UNSET' if outcome in ('completed','awaiting_approval') else 'ERROR'))
    require((reason=='identity_missing')==(value['subject'] is None))
    require(reason!='permission_missing' or value['permission'] is None)
    require(reason in ('identity_missing','permission_missing') or value['permission'] is not None)
    require(reason!='policy_unavailable' or value['policy_revision'] is None)
    require(reason not in ('explicit_allow','explicit_deny','explicit_require_approval','no_match','policy_error') or value['policy_revision'] is not None)
    require((reason in ('explicit_allow','explicit_deny','explicit_require_approval'))==(value['rule_id'] is not None))
    return value


def order(row):
    return (-row['start_time_unix_nano'],row['trace_id'],row['span_id'])


def validate_rows(rows):
    require(type(rows) is list and len(rows)<=10000)
    seen=set(); previous=None
    for raw in rows:
        row=event(raw); key=(row['trace_id'],row['span_id']); current=order(row)
        require(key not in seen and (previous is None or previous<current))
        seen.add(key); previous=current


def matches(row, query):
    for key,value in query.items():
        if key=='started_after_ns':require(row['start_time_unix_nano']>=value)
        elif key=='started_before_ns':require(row['start_time_unix_nano']<=value)
        else:require(row[key]==value)


def filters(values, now):
    require(type(values) is dict and set(values)<=set(FILTERS))
    result={k:v for k,v in values.items() if v is not None}
    for k in ('subject','tool','permission'):
        require(k not in result or identifier(result[k]))
    for k in ('action_id','trace_id'):require(k not in result or hex_id(result[k],32))
    require('effect' not in result or result['effect'] in ('allow','deny','require_approval'))
    require('outcome' not in result or result['outcome'] in ('denied','completed','error','cancelled','awaiting_approval'))
    if 'service_name' in result:
        v=result['service_name']; require(type(v) is str and bool(v.strip()) and len(v)<=128 and not any(ord(c)<32 for c in v))
    for k in ('started_after_ns','started_before_ns'):require(k not in result or integer(result[k],1,LIMIT))
    result['started_before_ns']=min(result.get('started_before_ns',now),now)
    require(result.get('started_after_ns',1)<=result['started_before_ns'])
    return result


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None


def transport(base_url, token):
    try: parts=urlsplit(base_url); port=parts.port
    except ValueError: raise ExportError('invalid Collector URL') from None
    require(parts.scheme in ('http','https') and parts.hostname and not parts.username and not parts.password and not parts.query and not parts.fragment and parts.path in ('','/'))
    require(parts.scheme=='https' or parts.hostname in ('localhost','127.0.0.1','::1'))
    require(type(token) is str and all(33<=ord(c)<=126 for c in token))
    opener=build_opener(NoRedirect())
    def fetch(query):
        request=Request(base_url.rstrip('/')+'/api/v1/security-events?'+urlencode(query),
            headers={'Accept':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
        try:
            with opener.open(request,timeout=10) as response:
                require(response.status==200 and response.headers.get_content_type()=='application/json')
                data=response.read(4*1024*1024+1); require(len(data)<=4*1024*1024)
            return json.loads(data)
        except Exception: raise ExportError('Collector query failed; check address, credentials, filters and availability') from None
    return fetch


def collect(fetch, query, max_events):
    require(integer(max_events,1,10000)); rows=[]; total=None
    while True:
        offset=len(rows); page=fetch({**query,'limit':100,'offset':offset})
        require(type(page) is dict and set(page)=={'items','total','limit','offset'})
        if integer(page['total'],max_events+1,LIMIT):
            raise ExportError('Export exceeds --max-events; narrow filters or raise the bounded limit')
        require(integer(page['total'],0,max_events) and type(page['items']) is list and page['limit']==100 and type(page['limit']) is int and type(page['offset']) is int and page['offset']==offset)
        if total is None:total=page['total']
        require(total==page['total'] and len(page['items'])==min(100,total-offset))
        rows.extend(page['items']); validate_rows(rows)
        for row in page['items']:matches(row,query)
        if len(rows)==total:return rows


def csv_bytes(rows):
    stream=io.StringIO(newline=''); writer=csv.writer(stream); writer.writerow(FIELDS)
    for row in rows:
        values=[]
        for key in FIELDS:
            value=row[key]
            if value is None:value=''
            if isinstance(value,str) and value.lstrip().lstrip('\ufeff').lstrip().startswith(('=','+','-','@')):value="'"+value
            elif isinstance(value,str) and value.startswith(('\t','\r','\n')):value="'"+value
            values.append(value)
        writer.writerow(values)
    return stream.getvalue().encode('utf-8')


def summary(rows):
    return {key:dict(sorted(Counter(row[key] for row in rows).items())) for key in ('effect','outcome','reason')}


def json_bytes(value): return (json.dumps(value,ensure_ascii=False,sort_keys=True)+'\n').encode('utf-8')


def write_bundle(output, rows, query, started):
    validate_rows(rows)
    require(filters(query,started)==query)
    for row in rows:matches(row,query)
    payloads={'events.jsonl':b''.join(json_bytes(row) for row in rows),'events.csv':csv_bytes(rows)}
    manifest=dict(format=1,started_at_ns=started,finished_at_ns=time.time_ns(),filters=query,
        count=len(rows),summary=summary(rows),notice=NOTICE,
        files={name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in payloads.items()})
    output=Path(output); output.mkdir()  # Exclusive reservation: never reuse any existing output.
    created=[]
    try:
        for name,data in (*payloads.items(),('manifest.json',json_bytes(manifest))):
            path=output/name
            with path.open('xb') as stream:
                created.append(path); stream.write(data)
    except BaseException:
        for path in reversed(created):path.unlink()
        output.rmdir();raise
    return manifest


def read_bundle(output):
    """Return a verified snapshot from the same bounded file reads."""
    output=Path(output); require(not output.is_symlink() and output.is_dir())
    def read(name,limit=MAX_FILE):
        path=output/name; require(not path.is_symlink() and path.is_file())
        with path.open('rb') as stream:data=stream.read(limit+1)
        require(len(data)<=limit);return data
    manifest=json.loads(read('manifest.json',65536))
    require(type(manifest) is dict and type(manifest.get('format')) is int and manifest['format']==1 and manifest.get('notice')==NOTICE)
    require(integer(manifest.get('started_at_ns'),1,LIMIT) and integer(manifest.get('finished_at_ns'),manifest['started_at_ns'],LIMIT))
    query=manifest.get('filters'); require(filters(query,manifest['started_at_ns'])==query)
    require(type(manifest.get('files')) is dict and set(manifest['files'])=={'events.jsonl','events.csv'})
    data={name:read(name) for name in manifest['files']}
    for name,raw in data.items():
        require(manifest['files'][name]==dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    lines=data['events.jsonl'].splitlines(); require(len(lines)<=10000)
    rows=[json.loads(line) for line in lines];validate_rows(rows)
    for row in rows:matches(row,query)
    require(integer(manifest.get('count'),0,10000) and manifest['count']==len(rows) and manifest.get('summary')==summary(rows))
    require(data['events.csv']==csv_bytes(rows))
    return manifest,rows


def verify_bundle(output):
    return read_bundle(output)[0]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    export=sub.add_parser('export');export.add_argument('--base-url',default='http://127.0.0.1:8000')
    export.add_argument('--output',required=True);export.add_argument('--max-events',type=int,default=1000)
    for key in FILTERS:export.add_argument('--'+key.replace('_','-'),type=int if key.endswith('_ns') else str)
    verify=sub.add_parser('verify');verify.add_argument('directory')
    args=parser.parse_args(argv)
    try:
        if args.command=='export':
            started=time.time_ns();query=filters({key:getattr(args,key) for key in FILTERS},started)
            rows=collect(transport(args.base_url,os.environ.get('AEGIS_API_TOKEN','')),query,args.max_events)
            manifest=write_bundle(args.output,rows,query,started)
        else:manifest=verify_bundle(args.directory)
        print(json.dumps(dict(status='passed',count=manifest['count'],summary=manifest['summary'],notice=NOTICE)))
        return 0
    except Exception as error:
        message=str(error) if isinstance(error,ExportError) else 'Output already exists; choose a new directory' if isinstance(error,FileExistsError) else 'Export or verification failed; check configuration and bundle integrity'
        print(json.dumps(dict(status='failed',error=message)),file=sys.stderr)
        return 1


if __name__=='__main__':sys.exit(main())
