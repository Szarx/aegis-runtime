import json
from pathlib import Path
import unittest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from aegis_collector.api import create_app
from aegis_collector.storage import StorageError

ROOT=Path(__file__).resolve().parents[2]


class SecurityProtocol(unittest.TestCase):
    def setUp(self):
        self.store=Mock();self.store.list_security_events.side_effect=lambda **kwargs:dict(items=[],total=0,limit=kwargs['limit'],offset=kwargs['offset'])
        self.client=TestClient(create_app(self.store,api_token='synthetic-trace',approval_request_token='synthetic-producer',approval_review_token='synthetic-reviewer',approval_execution_token='synthetic-executor'))
        self.addCleanup(self.client.close)
    def get(self,**params):return self.client.get('/api/v1/security-events',params=params,headers={'Authorization':'Bearer synthetic-trace'})

    def test_ac2001_trace_credentials_only_no_store_and_read_only(self):
        for token in ('','synthetic-producer','synthetic-reviewer','synthetic-executor'):
            response=self.client.get('/api/v1/security-events',headers={'Authorization':'Bearer '+token})
            self.assertEqual(response.status_code,401);self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(self.get().status_code,200)
        self.assertEqual(self.client.post('/api/v1/security-events',headers={'Authorization':'Bearer synthetic-trace'}).status_code,405)
        self.assertEqual(self.get().headers['vary'],'Authorization')

    def test_ac2001_defaults_and_all_filters_forwarded_exactly(self):
        params=dict(limit=2,offset=3,subject='reader',tool='lookup',permission='orders.read',service_name='service test',effect='deny',outcome='denied',action_id='1'*32,trace_id='2'*32,started_after_ns=1,started_before_ns=9223372036854775807)
        response=self.get(**params);self.assertEqual(response.status_code,200)
        self.assertEqual(self.store.list_security_events.call_args.kwargs,params)
        self.assertEqual(response.json(),dict(items=[],total=0,limit=2,offset=3))

    def test_ac2001_invalid_filters_are_fixed_errors_before_storage(self):
        cases=[dict(limit=0),dict(limit=101),dict(offset=-1),dict(offset=10001),dict(subject=' '),dict(tool='a*'),dict(permission='a\x00b'),dict(effect='maybe'),dict(outcome='unknown'),dict(action_id='0'*32),dict(trace_id='A'*32),dict(service_name=' '),dict(service_name='x\n'),dict(started_after_ns=2,started_before_ns=1),dict(started_before_ns=2**63),dict(started_after_ns=0)]
        for params in cases:
            with self.subTest(params=params):
                response=self.get(**params);self.assertEqual(response.status_code,400)
                self.assertEqual(response.json(),{'error':'invalid query or path parameter'})
        self.store.list_security_events.assert_not_called()

    def test_ac2001_storage_failure_does_not_echo_configuration(self):
        self.store.list_security_events.side_effect=StorageError('private-database-credential')
        response=self.get();self.assertEqual(response.status_code,503)
        self.assertEqual(response.json(),{'error':'storage unavailable'})
        self.assertNotIn('private',response.text)

    def test_ac2001_local_optional_auth_and_empty_data(self):
        with TestClient(create_app(self.store)) as client:
            self.assertEqual(client.get('/api/v1/security-events').json()['total'],0)

    def test_ac2001_openapi_additive_and_matches_new_snapshot(self):
        current=create_app(None).openapi()
        self.assertEqual(current,json.loads((ROOT/'specs/049-runtime-health/contracts/openapi.json').read_text(encoding='utf-8')))
        current['paths'].pop('/v1/health')
        current['paths'].pop('/api/v1/health')
        self.assertEqual(current,json.loads((ROOT/'specs/047-execution-trajectory/contracts/openapi.json').read_text(encoding='utf-8')))
        trace_schema = current['components']['schemas']['TraceSummary']
        self.assertNotIn('governance_signal', trace_schema['required'])
        trace_schema['properties'].pop('governance_signal')
        parameters = current['paths']['/api/v1/reviewed-actions']['get']['parameters']
        self.assertEqual([p['name'] for p in parameters].count('action_id'), 1)
        self.assertFalse(next(p['required'] for p in parameters if p['name'] == 'action_id'))
        parameters[:] = [p for p in parameters if p['name'] != 'action_id']
        self.assertEqual(current,json.loads((ROOT/'specs/045-policy-approval/contracts/openapi.json').read_text(encoding='utf-8')))
        # Only the two intentional security-event enum additions may differ from 020.
        def legacy(value):
            if isinstance(value,dict):return {key:([item for item in child if item not in ('require_approval','awaiting_approval')] if key=='enum' else legacy(child)) for key,child in value.items()}
            if isinstance(value,list):return [legacy(item) for item in value]
            return value
        self.assertEqual(legacy(current),json.loads((ROOT/'specs/020-security-events/contracts/openapi.json').read_text(encoding='utf-8')))
        current['paths'].pop('/api/v1/security-events')
        for name in ('SecurityEvent','SecurityEventList'):current['components']['schemas'].pop(name)
        self.assertEqual(current,json.loads((ROOT/'specs/011-reviewed-execution/contracts/openapi.json').read_text(encoding='utf-8')))
