import unittest
from fastapi.testclient import TestClient
from aegis_collector.api import create_app
from aegis_collector.api.health import HealthRegistry, HealthReport


def payload(instance='1'):
    return dict(instance_id=instance * 32, sequence=1, service_name='synthetic', active_spans=1,
                active_traces=['a' * 32], activity_truncated=False, health_failures=0,
                diagnostics={key: 0 for key in ('accepted_spans', 'exported_spans', 'failed_spans',
                    'dropped_spans', 'pending_spans', 'export_failures', 'instrumentation_failures')})


class HealthProtocol(unittest.TestCase):
    def test_strict_body_auth_and_privacy(self):
        client = TestClient(create_app(None, api_token='synthetic-token'))
        self.assertEqual(client.post('/v1/health', json=payload()).status_code, 401)
        self.assertEqual(client.get('/api/v1/health').status_code, 401)
        headers = {'Authorization': 'Bearer synthetic-token'}
        for change in ({'secret': 'private'}, {'sequence': True}, {'active_spans': 0},
                       {'active_traces': ['0' * 32]}, {'service_name': 'bad\nlabel'}):
            response = client.post('/v1/health', headers=headers, json={**payload(), **change})
            self.assertEqual(response.status_code, 400)
            self.assertNotIn('private', response.text)
        self.assertEqual(client.post('/v1/health', headers=headers, json=payload()).status_code, 200)
        response = client.get('/api/v1/health', headers=headers)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(response.json()['items'][0]['state'], 'reporting')
        self.assertEqual(client.post('/v1/health', headers={**headers,'Content-Type':'application/json'}, content=b'x'*16385).status_code, 413)

    def test_old_sequences_do_not_renew_lease_and_capacity_is_bounded(self):
        now = [0]
        registry = HealthRegistry(capacity=2, clock=lambda: now[0])
        registry.receive(HealthReport(**payload()))
        now[0] = 46
        registry.receive(HealthReport(**payload()))
        self.assertEqual(registry.listing()['items'][0]['state'], 'stale')
        registry.receive(HealthReport(**{**payload(), 'sequence': 2}))
        self.assertEqual(registry.listing()['items'][0]['state'], 'reporting')
        with self.assertRaises(ValueError):
            registry.receive(HealthReport(**{**payload(), 'sequence': 3, 'service_name': 'changed'}))
        registry.receive(HealthReport(**payload('2')))
        registry.receive(HealthReport(**payload('3')))
        result = registry.listing()
        self.assertEqual((len(result['items']), result['evicted_instances']), (2, 1))
