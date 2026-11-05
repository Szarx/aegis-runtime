"""Read-only Collector connectivity checks; never executes an Agent."""
import argparse
import json
import os
from pathlib import Path
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MAX_BODY = 1024 * 1024
NOT_CHECKED = ['SDK export and instrumentation', 'Agent business behavior', 'model calls',
               'Dashboard rendering', 'approval roles and execution', 'trusted identity', 'complete audit']


class DiagnosticError(ValueError):
    pass


def require(value):
    if not value:
        raise DiagnosticError('protocol_error')


def hex_id(value, width=32):
    return type(value) is str and re.fullmatch('[0-9a-f]{'+str(width)+'}', value) is not None and int(value, 16) > 0


def integer(value):
    return type(value) is int and value >= 0


def target(value):
    try:
        parts = urlsplit(value)
        require(not any(ord(c) <= 32 or ord(c) >= 127 for c in value))
        require(parts.scheme in ('http', 'https') and parts.hostname and parts.port != 0 and
                parts.username is None and parts.password is None and not parts.query and not parts.fragment and
                parts.path in ('', '/') and (parts.scheme == 'https' or parts.hostname in ('localhost', '127.0.0.1', '::1')))
    except (ValueError, TypeError):
        raise DiagnosticError('invalid_options') from None
    return value.rstrip('/')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def transport(base, token, timeout):
    opener = build_opener(ProxyHandler({}), NoRedirect())
    def fetch(path, protected=False):
        headers = {'Accept': 'application/json'}
        if protected and token:
            headers['Authorization'] = 'Bearer ' + token
        try:
            with opener.open(Request(base + path, headers=headers), timeout=timeout) as response:
                require(response.status == 200 and response.headers.get_content_type() == 'application/json')
                raw = response.read(MAX_BODY + 1)
                require(len(raw) <= MAX_BODY)
                return json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                                  parse_constant=lambda value: require(False))
        except HTTPError as error:
            code = error.code
            error.close()
            category = {401: 'unauthorized', 403: 'unauthorized', 404: 'not_found', 503: 'unavailable'}.get(code)
            raise DiagnosticError(category or ('redirect_refused' if 300 <= code < 400 else 'http_error')) from None
        except (TimeoutError, socket.timeout):
            raise DiagnosticError('network_timeout') from None
        except URLError as error:
            raise DiagnosticError('network_timeout' if isinstance(error.reason, TimeoutError) else 'network_unavailable') from None
        except (OSError, UnicodeError, ValueError) as error:
            if isinstance(error, DiagnosticError):
                raise
            raise DiagnosticError('protocol_error') from None
    return fetch


def page(value, limit):
    require(type(value) is dict and type(value.get('items')) is list and integer(value.get('total')) and
            type(value.get('limit')) is int and value['limit'] == limit and type(value.get('offset')) is int and value['offset'] == 0)
    require(len(value['items']) == min(limit, value['total']))
    return value['items']


def inspect(fetch, trace_id=None):
    report = dict(schema_version='aegis.platform-check.v1', status='failed', steps=[],
                  trace_id=trace_id, not_checked=list(NOT_CHECKED), scope='Selected read-only requests; no ingestion or business acceptance.')
    def step(name, operation):
        row = dict(stage=name, status='running')
        report['steps'].append(row)
        value = operation()
        row['status'] = 'passed'
        return value
    def health(path):
        require(fetch(path) == {'status': 'ok'})
    try:
        step('live', lambda: health('/health/live'))
        step('ready', lambda: health('/health/ready'))
        def listing():
            value = fetch('/api/v1/traces?limit=1&offset=0', True)
            rows = page(value, 1)
            require(all(type(row) is dict and hex_id(row.get('trace_id')) for row in rows))
            report['trace_total'] = value['total']
        step('trace_query', listing)
        if trace_id:
            span_ids = set()
            def detail():
                value = fetch('/api/v1/traces/' + trace_id, True)
                require(type(value) is dict and type(value.get('trace')) is dict and value['trace'].get('trace_id') == trace_id)
                spans, missing = value.get('spans'), value.get('missing_parent_ids')
                require(type(spans) is list and len(spans) > 0 and type(value['trace'].get('span_count')) is int and value['trace']['span_count'] == len(spans))
                require(type(missing) is list and all(hex_id(v, 16) for v in missing) and len(set(missing)) == len(missing))
                for span in spans:
                    require(type(span) is dict and span.get('trace_id') == trace_id and hex_id(span.get('span_id'), 16) and span['span_id'] not in span_ids)
                    require(span.get('parent_span_id') is None or hex_id(span['parent_span_id'], 16))
                    span_ids.add(span['span_id'])
                parents = {s['parent_span_id'] for s in spans if s['parent_span_id'] is not None} - span_ids
                require(parents == set(missing))
                report.update(span_count=len(spans), missing_parent_count=len(missing))
            step('trace_detail', detail)
            def events():
                value = fetch('/api/v1/security-events?trace_id=' + trace_id + '&limit=100&offset=0', True)
                rows = page(value, 100)
                require(all(type(row) is dict and row.get('trace_id') == trace_id and row.get('span_id') in span_ids for row in rows))
                report.update(security_page_count=len(rows), security_total=value['total'], security_has_more=value['total'] > len(rows))
            step('security_query', events)
        report['status'] = 'passed'
    except Exception as error:
        report['steps'][-1].update(status='failed', category=str(error) if isinstance(error, DiagnosticError) and str(error) in {'protocol_error', 'unauthorized', 'not_found', 'unavailable', 'redirect_refused', 'http_error', 'network_timeout', 'network_unavailable'} else 'protocol_error')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--trace-id')
    parser.add_argument('--timeout-seconds', type=int, default=3)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    output = None
    try:
        base = target(args.base_url)
        token = os.environ.get('AEGIS_API_TOKEN', '')
        if not 1 <= args.timeout_seconds <= 30 or (args.trace_id is not None and not hex_id(args.trace_id)) or ('AEGIS_API_TOKEN' in os.environ and not token) or len(token) > 4096 or any(not 33 <= ord(c) <= 126 for c in token):
            raise ValueError()
        if args.output is not None:
            output = args.output.open('x', encoding='utf-8')
    except (ValueError, OSError):
        print(json.dumps(dict(status='blocked', category='invalid_options_or_output', guide='docs/platform-diagnostics.md')))
        return 2
    report = inspect(transport(base, token, args.timeout_seconds), args.trace_id)
    try:
        if output is not None:
            with output:
                output.write(json.dumps(report, indent=2) + '\n')
    except OSError:
        report.update(status='failed', report_save_status='unavailable')
    print(json.dumps(report))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
