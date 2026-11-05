import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from tests.fixtures.application_config import ROOT,write_application


class ConfiguredOnboarding(unittest.TestCase):
    def test_ac2501_actual_inspect_cli_is_read_only_private_and_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);config=write_application(folder);output=folder/'inspection.json'
            def cli(code,*extras):
                result=subprocess.run([sys.executable,'-m','aegis_runtime','inspect',str(config),'--subject','reader',*extras],cwd=ROOT,
                    env={**os.environ,'SYNTHETIC_TRACE_TOKEN':'synthetic-private-token'},capture_output=True,text=True,encoding='utf-8',timeout=15)
                self.assertEqual(result.returncode,code,result.stdout+result.stderr);return result
            report=json.loads(cli(0,'--output',str(output)).stdout)
            self.assertEqual(report['status'],'valid');self.assertFalse((folder/'traces.jsonl').exists())
            original=output.read_bytes();cli(2,'--output',str(output));self.assertEqual(output.read_bytes(),original)
            config=write_application(folder,endpoint='http://127.0.0.1:9/v1/traces')
            result=cli(0);self.assertNotIn('synthetic-private',result.stdout);self.assertNotIn('127.0.0.1',result.stdout)
            doc=json.loads(config.read_text());doc['telemetry']['token_env']='MISSING_CONFIGURED_TEST_TOKEN';config.write_text(json.dumps(doc))
            self.assertEqual(json.loads(cli(1).stdout)['checks']['token'],'invalid')
            config.write_text('synthetic-private-invalid-config');result=cli(2);self.assertNotIn('synthetic-private',result.stderr)

    def test_ac2503_eight_real_native_langgraph_sync_async_allow_deny_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            for framework in ('native','langgraph'):
                for asynchronous in (False,True):
                    for subject in ('reader','blocked'):
                        with self.subTest(framework=framework,asynchronous=asynchronous,subject=subject):
                            folder=Path(directory)/f'{framework}-{asynchronous}-{subject}';config=write_application(folder)
                            result=subprocess.run([sys.executable,'examples/configured-agent/run.py','--config',str(config),'--framework',framework,'--subject',subject,*(['--async'] if asynchronous else [])],
                                cwd=ROOT,env={**os.environ,'PYTHONIOENCODING':'utf-8','LANGSMITH_TRACING':'false','LANGCHAIN_TRACING_V2':'false'},capture_output=True,text=True,encoding='utf-8',timeout=30)
                            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                            report=json.loads(result.stdout);self.assertEqual(report['baseline_calls'],1)
                            self.assertEqual(report['business_calls'],int(subject=='reader'));self.assertEqual(report['equivalent_to_baseline'],subject=='reader')
                            self.assertEqual(report['application']['state'],'closed');self.assertEqual(report['application']['unbound_tools'],['write_record'])
                            spans=[json.loads(line) for line in (folder/'traces.jsonl').read_text().splitlines()];self.assertEqual(len(spans),2)
                            tool=next(s for s in spans if s['attributes']['gen_ai.operation.name']=='execute_tool')
                            agent=next(s for s in spans if s['attributes']['gen_ai.operation.name']=='invoke_agent')
                            self.assertEqual(tool['parent_span_id'],agent['span_id']);self.assertEqual(tool['trace_id'],agent['trace_id'])
                            self.assertEqual(tool['attributes']['aegis.decision.effect'],'allow' if subject=='reader' else 'deny')

    def test_ac2503_example_config_paths_are_independent_of_process_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);config=write_application(folder/'configuration');other=folder/'other';other.mkdir()
            result=subprocess.run([sys.executable,str(ROOT/'examples/configured-agent/run.py'),'--config',str(config)],cwd=other,
                capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertTrue((config.parent/'traces.jsonl').exists());self.assertFalse((other/'traces.jsonl').exists())
