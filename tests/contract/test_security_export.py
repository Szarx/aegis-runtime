import contextlib
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from scripts.security_export import (ExportError,FIELDS,LIMIT,collect,csv_bytes,filters,main,
    transport,verify_bundle,write_bundle)


def row(index=1):
    return dict(zip(FIELDS,(f'{index:032x}',f'{index:016x}',f'{1:032x}','lookup','reader','orders.read','v1','read',
        'deny','explicit_deny','denied','synthetic-service',None,'ERROR',1790000000000000001,1790000000000000101)))


def page(rows,query):
    return dict(items=rows[query['offset']:query['offset']+100],total=len(rows),limit=100,offset=query['offset'])


class SecurityExport(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.output=Path(self.tmp.name)/'bundle';self.started=time.time_ns();self.query=filters({},self.started)
    def write(self,rows=None):return write_bundle(self.output,[row()] if rows is None else rows,self.query,self.started)

    def test_ac2101_collects_multiple_pages_and_preserves_same_action_attempts(self):
        rows=[row(i) for i in range(1,102)];calls=[]
        def fetch(query):calls.append(query);return page(rows,query)
        self.assertEqual(collect(fetch,self.query,101),rows);self.assertEqual([p['offset'] for p in calls],[0,100])
        self.assertEqual(len({r['action_id'] for r in rows}),1)

    def test_ac2101_rejects_changed_total_duplicates_wrong_order_and_short_pages(self):
        rows=[row(i) for i in range(1,102)]
        for mode in ('count','duplicate','order','short','limit','offset','extra'):
            def fetch(query):
                result=page(rows,query)
                if mode=='count' and query['offset']:result['total']+=1
                if mode=='duplicate' and query['offset']:result['items']=[row()]
                if mode=='order':result['items']=result['items'][::-1]
                if mode=='short':result['items']=[]
                if mode=='limit':result['limit']=99
                if mode=='offset':result['offset']=True
                if mode=='extra':result['private']='private-body'
                return result
            with self.subTest(mode=mode),self.assertRaises(ExportError):collect(fetch,self.query,200)

    def test_ac2101_refuses_over_limit_and_invalid_filters_before_output(self):
        with self.assertRaises(ExportError):collect(lambda q:page([row()],q),{},0)
        with self.assertRaises(ExportError):collect(lambda q:dict(items=[],total=1001,limit=100,offset=0),{},1000)
        for invalid in (dict(effect='maybe'),dict(subject=' '),dict(trace_id='0'*32),dict(started_after_ns=LIMIT+1),dict(started_after_ns=True),dict(started_before_ns=0),dict(service_name='x\n')):
            with self.subTest(invalid=invalid),self.assertRaises(ExportError):filters(invalid,self.started)
        self.assertEqual(self.query['started_before_ns'],self.started)
        self.assertFalse(self.output.exists())

    def test_ac2102_rejects_rows_outside_filters_and_rehashed_mismatched_csv(self):
        with self.assertRaises(ExportError):collect(lambda q:page([row()],q),{'subject':'different'},1000)
        with self.assertRaises(ExportError):collect(lambda q:page([row()],q),{'started_before_ns':1},1000)
        self.write();manifest=json.loads((self.output/'manifest.json').read_text())
        import hashlib
        changed=b'corrupt csv\n';(self.output/'events.csv').write_bytes(changed)
        manifest['files']['events.csv']=dict(bytes=len(changed),sha256=hashlib.sha256(changed).hexdigest())
        (self.output/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(ExportError):verify_bundle(self.output)

    def test_ac2101_rejects_unsafe_url_and_header_credentials(self):
        for url in ('http://example.com','https://user:secret@example.com','https://example.com/?secret=x','https://example.com/#secret','file:///tmp/x','http://localhost:invalid'):
            with self.subTest(url=url),self.assertRaises(ExportError):transport(url,'synthetic')
        with self.assertRaises(ExportError):transport('http://127.0.0.1','bad\nheader')

    def test_ac2101_never_overwrites_existing_output_and_cleans_write_failure(self):
        self.output.mkdir();(self.output/'keep').write_text('existing')
        with self.assertRaises(FileExistsError):self.write()
        self.assertEqual((self.output/'keep').read_text(),'existing')
        (self.output/'keep').unlink();self.output.rmdir()
        original=Path.open
        def failing(path,*args,**kwargs):
            if path.name=='events.csv':raise OSError('synthetic private filesystem path')
            return original(path,*args,**kwargs)
        with patch.object(Path,'open',failing),self.assertRaises(OSError):self.write()
        self.assertFalse(self.output.exists())

    def test_ac2102_roundtrip_exact_integer_jsonl_and_csv_formula_escaping(self):
        value=row();value['service_name']=' =SYNTHETIC()';value['agent_name']='\tformula'
        manifest=self.write([value]);self.assertEqual(verify_bundle(self.output),manifest)
        parsed=json.loads((self.output/'events.jsonl').read_text());self.assertEqual(parsed['start_time_unix_nano'],1790000000000000001)
        csv=(self.output/'events.csv').read_text();self.assertIn("' =SYNTHETIC()",csv);self.assertIn("'\tformula",csv)
        self.assertEqual(manifest['summary']['outcome'],{'denied':1});self.assertNotIn('token',str(manifest))

    def test_ac2102_rejects_modified_files_and_missing_manifest(self):
        self.write();original=(self.output/'events.csv').read_bytes()
        (self.output/'events.csv').write_bytes(original+b'changed')
        with self.assertRaises(ExportError):verify_bundle(self.output)
        (self.output/'events.csv').write_bytes(original);(self.output/'manifest.json').unlink()
        with self.assertRaises(ExportError):verify_bundle(self.output)

    def test_ac2101_real_http_redirect_and_private_failure_are_not_forwarded_or_echoed(self):
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        from threading import Thread
        visited=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                visited.append(self.path)
                self.send_response(302 if len(visited)==1 else 401)
                self.send_header('Location','/private-redirect-target')
                self.send_header('Content-Type','application/json');self.end_headers()
                self.wfile.write(b'private-error-body')
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);worker=Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            fetch=transport('http://127.0.0.1:'+str(server.server_port),'synthetic-token')
            for _ in range(2):
                with self.assertRaises(ExportError) as caught:fetch({})
                self.assertNotIn('private',str(caught.exception));self.assertNotIn('synthetic-token',str(caught.exception))
            self.assertEqual(len(visited),2);self.assertTrue(all(path.startswith('/api/v1/security-events?') for path in visited))
        finally:server.shutdown();server.server_close();worker.join(5)

    def test_ac2102_empty_bundle_is_valid_and_summary_corruption_rejected(self):
        manifest=self.write([]);self.assertEqual(verify_bundle(self.output)['count'],0)
        manifest['count']=1;(self.output/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(ExportError):verify_bundle(self.output)

    def test_ac2102_rejects_non_whitelist_malformed_and_inconsistent_events(self):
        changes=[{'prompt':'private'}, {'trace_id':'A'*32},{'start_time_unix_nano':True},{'permission':None},{'effect':'allow'},{'rule_id':None},{'subject':None}]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ExportError):self.write([{**row(),**change}])
        self.assertFalse(self.output.exists())

    def test_ac2101_cli_errors_are_fixed_and_do_not_echo_private_values(self):
        capture=io.StringIO()
        with contextlib.redirect_stderr(capture),patch('scripts.security_export.transport',side_effect=RuntimeError('private-secret')):
            self.assertEqual(main(['export','--output',str(self.output)]),1)
        self.assertNotIn('private-secret',capture.getvalue());self.assertFalse(self.output.exists())
