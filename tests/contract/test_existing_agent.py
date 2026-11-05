import ast
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import aegis
from examples.existing_agent.run import ROOT,host_delta,run_case
from examples.existing_agent.verify import VerificationError,verify


class ExistingAgent(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='aegis recipe ');self.addCleanup(self.temporary.cleanup)
        self.directory=Path(self.temporary.name)
        self.addCleanup(aegis.shutdown)

    def test_ac1601_actual_eight_cli_cases(self):
        receipts=[]
        for asynchronous in (False,True):
            for mode in ('baseline','observe','allow','deny'):
                with self.subTest(mode=mode,asynchronous=asynchronous):
                    command=[sys.executable,str(ROOT/'examples/existing_agent/run.py'),'--mode',mode,'--runs-dir',str(self.directory)]
                    if asynchronous:command.append('--async')
                    env=dict(os.environ,PYTHONIOENCODING='utf-8',LANGSMITH_TRACING='false',LANGCHAIN_TRACING_V2='false')
                    result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    path=Path(json.loads(result.stdout)['receipt']);receipt=json.loads(path.read_text(encoding='utf-8'))
                    self.assertEqual(receipt['status'],'passed');self.assertEqual(receipt['provider_requests'],0)
                    self.assertEqual(receipt['counts'],dict(model_calls=2,tool_calls=0 if mode=='deny' else 1))
                    self.assertEqual(receipt['equivalent_to_baseline'],mode!='deny')
                    self.assertEqual(receipt['verification']['span_count'],0 if mode=='baseline' else 4)
                    self.assertEqual(len(receipt['verification']['llm_duration_ms']),0 if mode=='baseline' else 2)
                    self.assertEqual(receipt['human_onboarding'],'not_run')
                    receipts.append(receipt)
        artifact=ROOT/'artifacts/existing-agent/matrix.json';artifact.parent.mkdir(parents=True,exist_ok=True)
        artifact.write_text(json.dumps(receipts,indent=2)+'\n',encoding='utf-8')

    def test_ac1602_corrupted_real_evidence_and_diagnostics_rejected(self):
        receipt=run_case('observe',False,self.directory);self.assertEqual(receipt['status'],'passed')
        original=[json.loads(line) for line in (self.directory/'traces.jsonl').read_text(encoding='utf-8').splitlines()]
        diagnostics=dict(accepted_spans=4,exported_spans=4,failed_spans=0,dropped_spans=0,pending_spans=0,export_failures=0,instrumentation_failures=0)
        for kind in ('missing','parent','duplicate','time','usage','private','counts','export','lifecycle'):
            rows=copy.deepcopy(original);diag=diagnostics.copy();counts=dict(model_calls=2,tool_calls=1)
            if kind=='missing':rows.pop()
            if kind=='parent':rows[0]['parent_span_id']=None
            if kind=='duplicate':rows[0]['span_id']=rows[1]['span_id']
            if kind=='time':rows[0]['end_time_unix_nano']=0
            if kind=='usage':rows[0]['attributes']['gen_ai.usage.input_tokens']=None
            if kind=='private':rows[0]['attributes']['input']='demo-order'
            if kind=='counts':counts['tool_calls']=True
            if kind=='export':diag['dropped_spans']=1
            with self.subTest(kind=kind),self.assertRaisesRegex(VerificationError,'^existing agent verification failed$'):
                verify(rows,mode='observe',counts=counts,equivalent=True,diagnostics=diag,flushed=kind!='lifecycle',closed=True)

    def test_ac1603_application_independent_and_host_delta_reproducible(self):
        path=ROOT/'examples/existing_agent/application.py';tree=ast.parse(path.read_text(encoding='utf-8'))
        imports=[node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
        imports += [alias.name for node in ast.walk(tree) if isinstance(node,ast.Import) for alias in node.names]
        self.assertFalse(any(name and name.startswith('aegis') for name in imports))
        delta=host_delta();self.assertEqual((delta['added_lines'],delta['deleted_lines'],delta['application_lines_changed']),(1,1,0))

    def test_ac1603_failure_receipt_contains_no_private_exception_or_environment(self):
        with patch('examples.existing_agent.run.execute',side_effect=RuntimeError('private-content credential-value')):
            receipt=run_case('observe',False,self.directory)
        self.assertEqual(receipt['status'],'failed')
        raw=(self.directory/'receipt.json').read_text(encoding='utf-8')
        self.assertNotIn('private-content',raw);self.assertNotIn('credential-value',raw)
        self.assertNotIn(str(self.directory),raw)
