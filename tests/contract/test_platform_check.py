from copy import deepcopy
from email.message import Message
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import platform_check as check

TRACE = '1' * 32
SPAN = '2' * 16


def responses():
    return [{'status': 'ok'}, {'status': 'ok'}, dict(items=[dict(trace_id=TRACE)], total=1, limit=1, offset=0),
            dict(trace=dict(trace_id=TRACE, span_count=1), spans=[dict(trace_id=TRACE, span_id=SPAN, parent_span_id=None,
                attributes={'private': 'do-not-copy'})], missing_parent_ids=[]),
            dict(items=[dict(trace_id=TRACE, span_id=SPAN, subject='private-subject')], total=1, limit=100, offset=0)]


class PlatformDiagnostics(unittest.TestCase):
    def test_actual_socket_redirect_is_not_followed_and_http_statuses_are_classified(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):pass
            def do_GET(self):
                requests.append(self.path)
                code=int(self.path.strip('/')) if self.path.strip('/').isdigit() else 200
                self.send_response(code)
                if code==302:self.send_header('Location','/private-landing')
                self.end_headers()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);worker=Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            fetch=check.transport('http://127.0.0.1:'+str(server.server_port),'private-token',1)
            for code,category in [(302,'redirect_refused'),(401,'unauthorized'),(403,'unauthorized'),(404,'not_found'),(503,'unavailable'),(500,'http_error')]:
                with self.assertRaises(check.DiagnosticError) as error:fetch('/'+str(code),True)
                self.assertEqual(str(error.exception),category)
            self.assertNotIn('/private-landing',requests)
        finally:server.shutdown();server.server_close();worker.join(2)

    def test_invalid_target_and_options_fail_before_network(self):
        for url in ('http://example.com', 'https://user:secret@example.com', 'https://host/path',
                    'http://localhost:0', 'http://localhost/?secret=1', 'http://localhost/#x', 'http://local\nhost'):
            with self.subTest(url=url), self.assertRaises(check.DiagnosticError): check.target(url)
        for url in ('https://example.com/', 'http://127.0.0.1:1234', 'http://[::1]:8000'): self.assertTrue(check.target(url))
        with patch.object(check, 'transport') as network, patch.dict(os.environ, {'AEGIS_API_TOKEN': 'private\nvalue'}), patch('sys.stdout', io.StringIO()) as output:
            self.assertEqual(check.main(['--base-url', 'http://localhost']), 2); network.assert_not_called()
            self.assertNotIn('private', output.getvalue())

    def test_default_is_three_gets_empty_list_passes_without_sdk(self):
        values=responses()[:3]; values[2]=dict(items=[], total=0, limit=1, offset=0)
        with patch.object(check, 'transport', return_value=lambda *args: values.pop(0)), patch.dict(os.environ, {}, clear=True), patch('sys.stdout', io.StringIO()) as output:
            self.assertEqual(check.main(['--base-url', 'http://localhost']), 0)
            report=json.loads(output.getvalue());self.assertEqual(len(report['steps']), 3)
            self.assertEqual(report['trace_total'], 0);self.assertIsNone(report['trace_id'])

    def test_exact_trace_sanitized_counts_and_partial_parent_coverage(self):
        values=responses();values[3]['spans'][0]['parent_span_id']='3'*16;values[3]['missing_parent_ids']=['3'*16]
        with patch.object(check, 'transport', return_value=lambda *args: values.pop(0)), patch.dict(os.environ, {}, clear=True), patch('sys.stdout', io.StringIO()) as output:
            self.assertEqual(check.main(['--base-url', 'http://localhost', '--trace-id', TRACE]), 0)
            report=json.loads(output.getvalue());self.assertEqual(report['missing_parent_count'], 1)
            self.assertEqual(report['security_page_count'], 1);self.assertNotIn('private', output.getvalue())
            self.assertNotIn('do-not-copy', output.getvalue())

    def test_each_failed_stage_stops_and_private_exceptions_are_hidden(self):
        for index in range(5):
            values=responses();calls=[]
            def fetch(*args):
                calls.append(args)
                if len(calls)==index+1: raise check.DiagnosticError('private-exception')
                return values.pop(0)
            report=check.inspect(fetch, TRACE)
            self.assertEqual(len(calls), index+1);self.assertEqual(report['status'], 'failed')
            self.assertEqual(report['steps'][-1]['category'], 'protocol_error');self.assertNotIn('private', json.dumps(report))

    def test_malformed_counts_ids_parent_sets_and_event_association_cannot_pass(self):
        for position, edit in [(2, dict(total=True)), (2, dict(limit=True)), (3, dict(trace=dict(trace_id='4'*32, span_count=1))),
                               (3, dict(missing_parent_ids=['3'*16])), (4, dict(items=[dict(trace_id=TRACE, span_id='4'*16)]))]:
            values=deepcopy(responses());values[position].update(edit)
            self.assertEqual(check.inspect(lambda *args: values.pop(0), TRACE)['status'], 'failed')

    def test_existing_output_blocks_requests_and_new_output_matches_stdout(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {}, clear=True), patch('sys.stdout', io.StringIO()) as output:
            path=Path(temporary)/'report.json';path.write_text('keep')
            with patch.object(check, 'transport') as network:
                self.assertEqual(check.main(['--base-url', 'http://localhost', '--output', str(path)]), 2);network.assert_not_called()
            self.assertEqual(path.read_text(), 'keep');path=path.with_name('new.json');output.seek(0);output.truncate()
            values=responses()
            with patch.object(check, 'transport', return_value=lambda *args: values.pop(0)):
                self.assertEqual(check.main(['--base-url', 'http://localhost', '--output', str(path)]), 0)
            self.assertEqual(json.loads(path.read_text()), json.loads(output.getvalue()))

    def test_transport_bounds_json_and_does_not_send_health_credentials(self):
        class Response:
            status=200
            headers=Message()
            headers['Content-Type']='application/json'
            def __enter__(self):return self
            def __exit__(self, *args):pass
            def read(self, size):return self.body[:size]
        response=Response();requests=[]
        def opening(request, **kwargs):requests.append(request);return response
        with patch('urllib.request.OpenerDirector.open', side_effect=opening):
            fetch=check.transport('http://localhost', 'private-token', 1)
            response.body=b'{"status":"ok"}';fetch('/health/live')
            self.assertIsNone(requests[-1].get_header('Authorization'))
            fetch('/api/v1/traces', True);self.assertEqual(requests[-1].get_header('Authorization'), 'Bearer private-token')
            for body in (b'{"x":1,"x":2}', b'{"x":NaN}', b'x'*(check.MAX_BODY+1), b'invalid'):
                response.body=body
                with self.assertRaises(check.DiagnosticError):fetch('/health/live')
