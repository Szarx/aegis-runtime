import asyncio
from pathlib import Path
import unittest
import aegis
from aegis_policy.comparison import compare_policies
from aegis_policy.workbench import load_cases,load_policy
from aegis_runtime import Runtime,ActionDenied
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

EXAMPLE=Path(__file__).resolve().parents[2]/'examples/policy-comparison'


class ComparisonRuntime(unittest.TestCase):
    def test_ac2303_real_sync_async_before_after_calls_and_spans_match_impact(self):
        before=load_policy(EXAMPLE/'before.json');after=load_policy(EXAMPLE/'candidate.json');suite=load_cases(EXAMPLE/'cases.json')
        report=compare_policies(before,after,suite)
        aegis.shutdown();exporter=InMemorySpanExporter();aegis.init('policy-change-tests',exporter=exporter);self.addCleanup(aegis.shutdown)
        calls=[]
        def sync():calls.append(1);return 'synthetic'
        async def asynchronous():return sync()
        for mode in (False,True):
            for key,policy,expected_calls in (('before',before,2),('after',after,3)):
                start=len(calls)
                for case,comparison in zip(suite['cases'],report['cases']):
                    fn=Runtime(policy,subject=case['subject']).tool(asynchronous if mode else sync,name=case['tool'],permission=case['permission'])
                    decision=comparison[key]['decision'];count=len(calls)
                    try:
                        self.assertEqual(asyncio.run(fn()) if mode else fn(),'synthetic')
                        self.assertEqual(decision['effect'],'allow')
                    except ActionDenied as error:
                        self.assertEqual({k:getattr(error.decision,k) for k in ('effect','reason','rule_id')},{k:decision[k] for k in ('effect','reason','rule_id')})
                    self.assertEqual(len(calls)-count,int(decision['effect']=='allow'))
                self.assertEqual(len(calls)-start,expected_calls)
        aegis.flush();spans=exporter.get_finished_spans();self.assertEqual(len(spans),32)
        decisions=[case[key]['decision'] for _ in (False,True) for key in ('before','after') for case in report['cases']]
        for span,decision in zip(spans,decisions):
            self.assertEqual(span.attributes['aegis.decision.effect'],decision['effect'])
            self.assertEqual(span.attributes['aegis.decision.reason'],decision['reason'])
            self.assertEqual(span.attributes.get('aegis.decision.rule_id'),decision['rule_id'])
        self.assertEqual(len(calls),10)
