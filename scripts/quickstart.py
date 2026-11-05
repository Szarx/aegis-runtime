"""Install a local SDK profile in a new venv and verify its first offline traces."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    'native': ('', 'examples/native-python/agent.py', 2, 4),
    'langgraph': ('[langgraph,deepseek]', 'examples/langgraph/agent.py', 1, 4),
}
DIAGNOSTICS = ('accepted_spans', 'exported_spans', 'failed_spans', 'dropped_spans',
               'pending_spans', 'export_failures', 'instrumentation_failures')


class AcceptanceError(Exception):
    """A fixed failure category safe to include in a metadata-only receipt."""


def child_environment():
    environment = dict(os.environ)
    for key in tuple(environment):
        if key.upper() in {'PYTHONPATH', 'PYTHONHOME'} or any(
            key.upper().startswith(prefix) for prefix in ('OPENAI_', 'DEEPSEEK_', 'AEGIS_', 'LANGSMITH_', 'LANGCHAIN_')
        ):
            del environment[key]
    environment.update(LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false', PYTHONUTF8='1')
    return environment


def run_stage(receipt, name, command, *, environment, timeout, cwd=ROOT):
    stage = {'name': name, 'status': 'failed'}
    receipt['stages'].append(stage)
    started = time.perf_counter()
    print(f'{name}...', flush=True)
    try:
        result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=timeout)
        if result.returncode:
            stage['exit_code'] = result.returncode
            raise AcceptanceError('process_failed')
        stage['status'] = 'passed'
        return result.stdout
    except subprocess.TimeoutExpired:
        raise AcceptanceError('process_timeout') from None
    except OSError:
        raise AcceptanceError('process_unavailable') from None
    finally:
        stage['elapsed_ms'] = round((time.perf_counter() - started) * 1000, 3)


def validate_traces(path, profile, stdout):
    def require(condition):
        if not condition:
            raise ValueError('invalid trace acceptance data')

    try:
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        summaries = [json.loads(line) for line in stdout.splitlines() if line.startswith('{')]
        diagnostics = next(row['diagnostics'] for row in summaries if 'diagnostics' in row)
        _, _, trace_count, span_count = PROFILES[profile]
        require(len(rows) == span_count and len({row['trace_id'] for row in rows}) == trace_count)
        require(all(type(diagnostics[key]) is int and diagnostics[key] >= 0 for key in DIAGNOSTICS))
        require(diagnostics['accepted_spans'] == diagnostics['exported_spans'] == span_count)
        require(all(diagnostics[key] == 0 for key in DIAGNOSTICS[2:]))
        identifiers = {(row['trace_id'], row['span_id']) for row in rows}
        require(len(identifiers) == span_count)
        for row in rows:
            require(len(row['trace_id']) == 32 and int(row['trace_id'], 16) > 0)
            require(len(row['span_id']) == 16 and int(row['span_id'], 16) > 0)
            require(row['start_time_unix_nano'] <= row['end_time_unix_nano'])
            require(row['scope']['name'] == 'aegis')
        operations = Counter(row['attributes']['gen_ai.operation.name'] for row in rows)
        agents = [row for row in rows if row['attributes']['gen_ai.operation.name'] == 'invoke_agent']
        require(len(agents) == trace_count and all(row['parent_span_id'] is None for row in agents))
        for agent in agents:
            children = [row for row in rows if row['trace_id'] == agent['trace_id'] and row is not agent]
            require(all(row['parent_span_id'] == agent['span_id'] for row in children))
            if profile == 'native':
                require(len(children) == 1 and children[0]['status'] == agent['status'])
        if profile == 'native':
            require(operations == Counter(invoke_agent=2, execute_tool=2))
            require(Counter(row['status'] for row in agents) == Counter(UNSET=1, ERROR=1))
        else:
            require(operations == Counter(invoke_agent=1, chat=2, execute_tool=1))
            require(all(row['status'] == 'UNSET' for row in rows))
            comparison = next(row for row in summaries if 'equivalent' in row)
            require(comparison['equivalent'] is True)
            require(comparison['before_counts'] == comparison['after_counts'] == {'model_calls':2, 'tool_calls':1})
            lifecycle = next(row for row in summaries if 'flush' in row)
            require(lifecycle['flush'] is True and lifecycle['shutdown'] is True)
            for row in rows:
                if row['attributes']['gen_ai.operation.name'] == 'chat':
                    require(row['attributes']['gen_ai.provider.name'] == 'deepseek')
                    require(row['attributes']['gen_ai.usage.input_tokens'] == 7)
                    require(row['attributes']['gen_ai.usage.output_tokens'] == 3)
        return {'trace_count': trace_count, 'span_count': span_count,
                'parentage_verified': True, 'diagnostics': {key: diagnostics[key] for key in DIAGNOSTICS},
                'business_comparison_verified': True if profile == 'langgraph' else None}
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        raise AcceptanceError('trace_validation_failed') from None


def parser():
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument('--profile', choices=PROFILES, default='native')
    arguments.add_argument('--wheelhouse', type=Path, help='Local cache; disables package-index access')
    arguments.add_argument('--runs-dir', type=Path, default=ROOT / 'artifacts/onboarding')
    arguments.add_argument('--timeout-seconds', type=int, default=180, help='Maximum time for each subprocess (1–1800)')
    return arguments


def main(argv=None):
    arguments = parser()
    args = arguments.parse_args(argv)
    if sys.version_info < (3, 11):
        arguments.error('Python 3.11 or later is required')
    if not 1 <= args.timeout_seconds <= 1800:
        arguments.error('--timeout-seconds must be between 1 and 1800')
    if args.wheelhouse is not None and not args.wheelhouse.is_dir():
        arguments.error('--wheelhouse must be an existing directory')
    args.runs_dir.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix=args.profile + '-', dir=args.runs_dir)).resolve()
    receipt = {
        'schema_version': 'aegis.onboarding.v1', 'profile': args.profile, 'status': 'failed',
        'started_at_utc': datetime.now(timezone.utc).isoformat(), 'python_version': platform.python_version(),
        'platform': sys.platform, 'install_source': 'local-wheel-cache' if args.wheelhouse else 'official-pypi',
        'stages': [], 'new_provider_requests': 0, 'platform_acceptance': 'not_run', 'human_onboarding_acceptance': 'not_run',
    }
    started = time.perf_counter()
    environment = child_environment()
    execute = lambda name, command: run_stage(receipt, name, command, environment=environment, timeout=args.timeout_seconds)
    try:
        execute('venv', [sys.executable, '-I', '-m', 'venv', str(run / 'venv')])
        python = run / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        pip = [str(python), '-I', '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check', '--no-input', '--no-cache-dir']
        if args.wheelhouse:
            source = ['--no-index', '--find-links', str(args.wheelhouse.resolve())]
        else:
            source = ['--index-url', 'https://pypi.org/simple']
        constraints = ['--constraint', str(ROOT / 'requirements-dev.lock')]
        execute('build-prerequisite', pip + source + constraints + ['setuptools'])
        extras, example, _, _ = PROFILES[args.profile]
        execute('sdk-install', pip + source + constraints + ['--no-build-isolation', str(ROOT / 'sdk/python') + extras])
        execute('dependency-check', [str(python), '-I', '-m', 'pip', '--isolated', 'check'])
        output = execute('example', [str(python), '-I', str(ROOT / example), '--output', str(run / 'traces.jsonl')])
        stage = {'name': 'validation', 'status': 'failed'}
        receipt['stages'].append(stage)
        validation_started = time.perf_counter()
        try:
            receipt['verification'] = validate_traces(run / 'traces.jsonl', args.profile, output)
            stage['status'] = 'passed'
        finally:
            stage['elapsed_ms'] = round((time.perf_counter() - validation_started) * 1000, 3)
        receipt['status'] = 'passed'
        receipt['first_valid_trace_ms'] = round((time.perf_counter() - started) * 1000, 3)
    except AcceptanceError as error:
        receipt['error_category'] = str(error)
        print(f'Quickstart failed: {error}. See docs/quickstart.md for troubleshooting.', flush=True)
    finally:
        receipt['total_ms'] = round((time.perf_counter() - started) * 1000, 3)
        (run / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f"Result: {receipt['status']}; receipt: {run / 'receipt.json'}", flush=True)
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
