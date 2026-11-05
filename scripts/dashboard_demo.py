"""Populate a user-selected Aegis Collector with bounded synthetic UI examples."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import uuid

ROOT=Path(__file__).resolve().parents[1]


def validate_target(value):
    try:
        url=urlsplit(value);port=url.port
        valid=(url.scheme in ('http','https') and url.hostname and url.username is None and url.password is None and
            not url.path and not url.query and not url.fragment and port!=0 and
            (url.scheme=='https' or url.hostname in ('localhost','127.0.0.1','::1')))
    except ValueError:valid=False
    if not valid:raise ValueError('invalid demo Collector target')
    return value


def run_example(arguments,environment):
    result=subprocess.run([sys.executable,*arguments],cwd=ROOT,env=environment,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
    if result.returncode:raise RuntimeError('synthetic example did not complete')
    report=json.loads(result.stdout.strip().splitlines()[-1])
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000');parser.add_argument('--attempts',type=int,default=25)
    parser.add_argument('--with-approvals',action='store_true');parser.add_argument('--approval-count',type=int,default=2)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        target=validate_target(args.base_url)
        if not 1<=args.attempts<=100 or not 1<=args.approval_count<=5:raise ValueError()
        if args.with_approvals and any(not os.environ.get(name) for name in ('AEGIS_APPROVAL_REQUEST_TOKEN','AEGIS_APPROVAL_EXECUTION_TOKEN')):raise ValueError()
        if args.with_approvals and urlsplit(target).scheme!='http':raise ValueError()
        names=['AEGIS_API_TOKEN']+(['AEGIS_APPROVAL_REQUEST_TOKEN','AEGIS_APPROVAL_EXECUTION_TOKEN'] if args.with_approvals else [])
        for name in names:
            value=os.environ.get(name)
            if value is not None and (not value or len(value)>4096 or any(not 33<=ord(c)<=126 for c in value)):raise ValueError()
    except ValueError:
        print(json.dumps(dict(status='blocked',error='Check loopback/HTTPS target, counts and explicit approval role environment variables')));return 2
    folder=(args.output or ROOT/'artifacts/dashboard-demo'/uuid.uuid4().hex).resolve()
    try:folder.mkdir(parents=True,exist_ok=False)
    except OSError:
        print(json.dumps(dict(status='blocked',error='Demo output directory must be new and writable')));return 2
    report=dict(schema_version='aegis.dashboard-demo.v1',status='failed',stages=[],action_ids=[],real_provider_requests=0,automatic_review=False,execution_host_provided=False,report_file=str(folder/'report.json'))
    try:
        environment={**os.environ,'PYTHONIOENCODING':'utf-8','LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false'}
        tools=run_example(['examples/security-events/agent.py','--endpoint',target+'/v1/traces','--count',str(args.attempts)],environment)
        if tools.get('flush') is not True or tools.get('shutdown') is not True:raise RuntimeError()
        report['stages'].append(dict(stage='governance',attempts=args.attempts,exported_spans=tools['diagnostics']['exported_spans']))
        with tempfile.TemporaryDirectory(prefix='aegis-dashboard-demo-') as temporary:
            config=json.loads((ROOT/'examples/managed-graph/application.json').read_text(encoding='utf-8'))
            config['policy_file']=str(ROOT/'examples/managed-graph/policy.json')
            config['telemetry']=dict(mode='otlp',endpoint=target+'/v1/traces',token_env='AEGIS_API_TOKEN' if environment.get('AEGIS_API_TOKEN') else None)
            path=Path(temporary)/'application.json';path.write_text(json.dumps(config),encoding='utf-8')
            graph=run_example(['examples/managed-graph/run.py','--config',str(path),'--mode','astream'],environment)
            if graph.get('status')!='passed':raise RuntimeError()
        report['stages'].append(dict(stage='model_graph',model_calls=graph['model_calls'],business_calls=graph['business_calls'],exported_spans=graph['application']['diagnostics']['exported_spans']))
        if args.with_approvals:
            from aegis_policy import Policy,Rule
            from aegis_runtime.reviewed_execution import ReviewedClient,ReviewedTool
            connection=ReviewedClient(target,token=environment['AEGIS_APPROVAL_REQUEST_TOKEN'],execution_token=environment['AEGIS_APPROVAL_EXECUTION_TOKEN'],binding_key=secrets.token_bytes(32))
            policy=Policy('dashboard-demo-v1',(Rule('permit','allow',('demo-agent',),('write',),('records.write',)),))
            def write(*,record_id=9223372036854775807,value='synthetic-demo-value'):raise AssertionError('demo never executes reviewed tools')
            governed=ReviewedTool(write,client=connection,policy=policy,subject='demo-agent',permission='records.write',tool='write',tool_revision='demo-v1',disclose_arguments=True)
            for index in range(args.approval_count):
                record=governed.prepare({},summary=f'合成演示：更新订单状态 {index+1}',ttl_seconds=600);report['action_ids'].append(record['action_id'])
            report['stages'].append(dict(stage='review_preparation',created=len(report['action_ids']),ttl_seconds=600))
        report['status']='passed'
    except Exception:
        report['error']='Demo incomplete; inspect completed stages and platform before another run. No automatic retry or rollback.'
    try:(folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    except OSError:report['status']='failed';report['error']='Could not persist demo report; inspect completed stages before another run'
    print(json.dumps(report,ensure_ascii=False));return 0 if report['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
