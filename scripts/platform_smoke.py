"""Build an isolated local Compose platform and verify synthetic data end to end."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import build_opener, ProxyHandler, Request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as connection:
        connection.bind(('127.0.0.1', 0))
        return connection.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default='aegis-smoke-' + uuid.uuid4().hex[:12])
    parser.add_argument('--http-port', type=int)
    parser.add_argument('--dashboard-port', type=int)
    parser.add_argument('--postgres-port', type=int)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r'aegis-smoke-[a-z0-9-]{1,32}', args.project):
        parser.error('Project must be a new aegis-smoke-* project.')
    ports = [value if value is not None else free_port() for value in
             (args.http_port, args.dashboard_port, args.postgres_port)]
    if len(set(ports)) != 3 or any(not 1024 <= value <= 65535 for value in ports):
        parser.error('Three distinct non-privileged local ports are required.')
    folder = (args.output or ROOT / 'artifacts/platform-smoke' / uuid.uuid4().hex).resolve()
    if not folder.is_relative_to(ROOT / 'artifacts') or folder == ROOT / 'artifacts':
        parser.error('Output must be a new directory under repository artifacts.')
    folder.mkdir(parents=True, exist_ok=False)
    environment = {key: value for key, value in os.environ.items() if not
                   key.upper().startswith(('AEGIS_', 'OPENAI_', 'DEEPSEEK_', 'LANGSMITH_', 'LANGCHAIN_', 'COMPOSE_'))}
    token = secrets.token_urlsafe(32)
    environment.update(
        AEGIS_DB_PASSWORD=secrets.token_urlsafe(24), AEGIS_API_TOKEN=token,
        AEGIS_HTTP_PORT=str(ports[0]), AEGIS_DASHBOARD_PORT=str(ports[1]), AEGIS_POSTGRES_PORT=str(ports[2]),
        AEGIS_APPROVAL_REQUEST_TOKEN='', AEGIS_APPROVAL_REVIEW_TOKEN='', AEGIS_APPROVAL_EXECUTION_TOKEN='',
        AEGIS_APPROVAL_REVIEWER='synthetic-reviewer', AEGIS_APPROVAL_EXECUTOR='synthetic-executor',
        PYTHONIOENCODING='utf-8', LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false',
    )
    compose = ['docker', 'compose', '--env-file', str(ROOT / '.env.example'),
               '-f', str(ROOT / 'docker-compose.yml'), '-p', args.project]
    report = dict(schema_version='aegis.platform-smoke.v1', status='running', project=args.project,
                  ports=ports, stages=[], real_provider_requests=0, database_volume_retained=True)
    started = False

    def save():
        (folder / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')

    def run(stage, command, timeout=120):
        print('Checking platform ' + stage, flush=True)
        begin = time.monotonic()
        with (folder / (stage + '.log')).open('w', encoding='utf-8') as output:
            child = subprocess.run(command, cwd=ROOT, env=environment, stdout=output,
                                   stderr=subprocess.STDOUT, timeout=timeout)
        report['stages'].append(dict(stage=stage, returncode=child.returncode,
                                     seconds=round(time.monotonic() - begin, 3)))
        save()
        if child.returncode:
            raise ValueError('stage failed')
        return (folder / (stage + '.log')).read_text(encoding='utf-8')

    # All HTTP targets are created on loopback by this process; do not use host proxies.
    opener = build_opener(ProxyHandler({}))
    def fetch(port, path, *, authorized=True, status=200):
        headers = {'Authorization': 'Bearer ' + token} if authorized else {}
        request = Request(f'http://127.0.0.1:{port}' + path, headers=headers)
        try:
            with opener.open(request, timeout=5) as response:
                actual, data = response.status, response.read(2_000_000)
        except HTTPError as error:
            actual, data = error.code, error.read(4096)
        if actual != status:
            raise ValueError('unexpected HTTP status')
        return data

    try:
        # Refuse to operate or clean up any existing project, even an exited one.
        inventory = run('project_inventory', compose + ['ps', '-a', '-q']).strip()
        if inventory:
            raise ValueError('project already exists')
        volumes = run('volume_inventory', ['docker', 'volume', 'ls', '-q', '--filter',
                                            'label=com.docker.compose.project=' + args.project]).strip()
        if volumes:
            raise ValueError('project volume already exists')
        run('build', compose + ['build', '--pull', '--no-cache'], 1800)
        started = True
        run('start', compose + ['up', '-d', '--wait', '--wait-timeout', '180'], 240)
        ready = json.loads(fetch(ports[0], '/health/ready', authorized=False))
        initial = json.loads(fetch(ports[0], '/api/v1/traces?limit=20&offset=0'))
        if ready.get('status') != 'ok' or initial['total'] != 0:
            raise ValueError('platform not fresh')
        fetch(ports[0], '/api/v1/traces', authorized=False, status=401)
        versions = run('migrations', compose + ['exec', '-T', 'postgres', 'psql', '-U', 'aegis', '-d', 'aegis',
                       '-Atc', 'SELECT version FROM aegis.schema_version ORDER BY version']).strip().splitlines()
        if versions != ['1', '2', '3', '4']:
            raise ValueError('migration mismatch')
        run('native_agent', [sys.executable, 'examples/native-python/agent.py', '--endpoint',
                            f'http://127.0.0.1:{ports[0]}/v1/traces'])
        run('synthetic_demo', [sys.executable, 'scripts/dashboard_demo.py', '--base-url',
                              f'http://127.0.0.1:{ports[0]}', '--attempts', '12',
                              '--output', str(folder / 'demo')], 180)
        traces = json.loads(fetch(ports[0], '/api/v1/traces?limit=100&offset=0'))
        events = json.loads(fetch(ports[0], '/api/v1/security-events?limit=100&offset=0'))
        if traces['total'] < 3 or events['total'] != 12:
            raise ValueError('synthetic data missing')
        for trace in traces['items']:
            detail = json.loads(fetch(ports[0], '/api/v1/traces/' + trace['trace_id']))
            if not detail['spans'] or detail['missing_parent_ids']:
                raise ValueError('incomplete synthetic trace')
        run('diagnostics', [sys.executable, 'scripts/platform_check.py', '--base-url',
                            f'http://127.0.0.1:{ports[0]}', '--trace-id', traces['items'][0]['trace_id']])
        html = fetch(ports[1], '/', authorized=False).decode('utf-8')
        assets = re.findall(r'(?:src|href)="(/assets/[^"\s]+)"', html)
        if not assets:
            raise ValueError('dashboard assets missing')
        for asset in assets:
            if not fetch(ports[1], asset, authorized=False):
                raise ValueError('empty dashboard asset')
        notices = fetch(ports[1], '/third-party-notices.txt', authorized=False)
        if notices != (ROOT / 'dashboard/public/third-party-notices.txt').read_bytes():
            raise ValueError('distribution notices missing')
        proxied = json.loads(fetch(ports[1], '/api/v1/traces?limit=100&offset=0'))
        fetch(ports[1], '/api/v1/traces', authorized=False, status=401)
        if proxied != traces:
            raise ValueError('dashboard proxy mismatch')
        run('restart', compose + ['restart', 'collector'])
        for attempt in range(40):
            try:
                fetch(ports[0], '/health/ready', authorized=False)
            except (OSError, ValueError):
                time.sleep(0.5)
                continue
            after = json.loads(fetch(ports[0], '/api/v1/traces?limit=100&offset=0'))
            if after != traces:
                raise ValueError('persistence mismatch')
            break
        else:
            raise ValueError('restart unavailable')
        report.update(status='passed', trace_count=traces['total'], security_events=events['total'],
                      migration_versions=[1,2,3,4], dashboard_assets=len(assets),
                      authenticated_proxy=True, restart_persisted=True)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        report.update(status='failed', message='Inspect local stage logs; no automatic retry or data reset.')
    finally:
        if started:
            try:
                run('stop', compose + ['down', '--remove-orphans'], 180)
            except (OSError, ValueError, subprocess.SubprocessError):
                report.update(status='failed', cleanup='Check isolated project containers manually.')
        save()
    print(json.dumps(report))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
