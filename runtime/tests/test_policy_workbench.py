import asyncio
from pathlib import Path
import unittest
import aegis
from aegis_policy.workbench import check_cases,load_cases,load_policy
from aegis_runtime import ActionDenied,Runtime
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

ROOT=Path(__file__).resolve().parents[2]


class WorkbenchRuntime(unittest.TestCase):
    def test_ac2203_sync_async_decisions_and_observed_rule_match_validated_cases(self):
        policy=load_policy(ROOT/'examples/policy-workbench/policy.json');suite=load_cases(ROOT/'examples/policy-workbench/cases.json')
        self.assertEqual(check_cases(policy,suite)['status'],'passed')
        aegis.shutdown();exporter=InMemorySpanExporter();aegis.init('workbench-test',exporter=exporter);self.addCleanup(aegis.shutdown)
        calls=[]
        def sync():calls.append(1);return 'synthetic'
        async def asynchronous():return sync()
        for mode in (False,True):
            for case in suite['cases']:
                fn=Runtime(policy,subject=case['subject']).tool(asynchronous if mode else sync,name=case['tool'],permission=case['permission'])
                before=len(calls)
                try:
                    result=asyncio.run(fn()) if mode else fn()
                    self.assertEqual(case['expected']['effect'],'allow');self.assertEqual(result,'synthetic')
                except ActionDenied as e:
                    self.assertEqual({k:getattr(e.decision,k) for k in ('effect','reason','rule_id')},case['expected'])
                self.assertEqual(len(calls)-before,int(case['expected']['effect']=='allow'))
        aegis.flush();spans=exporter.get_finished_spans();self.assertEqual(len(spans),14)
        for span,case in zip(spans,suite['cases']*2):
            self.assertEqual(span.attributes['aegis.decision.effect'],case['expected']['effect'])
            self.assertEqual(span.attributes['aegis.decision.reason'],case['expected']['reason'])
            self.assertEqual(span.attributes.get('aegis.decision.rule_id'),case['expected']['rule_id'])
        self.assertEqual(len(calls),2)
