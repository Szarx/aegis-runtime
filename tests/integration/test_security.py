import os
import unittest
import uuid
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from tests.fixtures.governance import governance_request
from tests.fixtures.otlp import request_for,first_span,combine

DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class SecurityPostgres(unittest.TestCase):
    def setUp(self):
        self.schema='test_security_'+uuid.uuid4().hex;self.store=PostgresSpanStore(DATABASE,self.schema);self.store.migrate()
        self.client=TestClient(create_app(self.store,api_token='synthetic-trace'))
        self.headers={'Authorization':'Bearer synthetic-trace'}
    def tearDown(self):
        self.client.close()
        with psycopg.connect(DATABASE) as connection:connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
    def seed(self,trace,**kwargs):
        request=governance_request(trace=trace,**kwargs)
        for key in ('arguments','prompt','authorization','exception.message'):
            first_span(request).attributes.add(key=key).value.string_value='private-body-do-not-retain'
        for _ in range(2):
            response=self.client.post('/v1/traces',headers={**self.headers,'Content-Type':'application/x-protobuf'},content=request.SerializeToString())
            self.assertEqual(response.status_code,200)
        return request
    def get(self,**params):return self.client.get('/api/v1/security-events',headers=self.headers,params=params).json()

    def test_ac2002_stable_pagination_dedup_same_action_and_legacy_exclusion(self):
        for trace in (3,1,2):self.seed(trace)
        self.client.post('/v1/traces',headers={**self.headers,'Content-Type':'application/x-protobuf'},content=request_for(trace=9,operation='execute_tool').SerializeToString())
        rows=[self.get(limit=1,offset=i)['items'][0] for i in range(3)]
        self.assertEqual([row['trace_id'] for row in rows],[f'{i:032x}' for i in (1,2,3)])
        self.assertEqual(len({row['action_id'] for row in rows}),1)
        self.assertEqual(self.get()['total'],3);self.assertEqual(self.get(offset=10)['items'],[])
        rebuilt=PostgresSpanStore(DATABASE,self.schema);self.assertEqual(rebuilt.list_security_events()['total'],3)

    def test_ac2002_all_filters_time_bounds_nulls_and_sql_parameters(self):
        request=self.seed(1);start=first_span(request).start_time_unix_nano
        self.seed(2,effect='allow',reason='explicit_allow',outcome='completed')
        for params in (dict(subject='reader'),dict(tool='lookup'),dict(permission='orders.read'),dict(effect='deny'),dict(outcome='denied'),dict(trace_id=f'{1:032x}'),dict(action_id=f'{2:032x}'),dict(started_after_ns=start,started_before_ns=start)):
            with self.subTest(params=params):self.assertGreaterEqual(self.get(**params)['total'],1)
        row=self.get(trace_id=f'{1:032x}')['items'][0]
        params=dict(subject='reader',tool='lookup',permission='orders.read',effect='deny',outcome='denied',trace_id=row['trace_id'],action_id=row['action_id'],service_name=row['service_name'],started_after_ns=start,started_before_ns=start)
        self.assertEqual(self.get(**params)['total'],1)
        self.assertEqual(self.get(started_before_ns=start-1)['total'],0)
        self.assertEqual(self.get(started_after_ns=start+1)['total'],0)
        self.assertEqual(self.store.list_security_events(subject="reader' OR true --")['total'],0)
        self.seed(3,reason='identity_missing');self.seed(4,reason='permission_missing');self.seed(5,reason='policy_unavailable')
        self.assertIsNone(self.get(trace_id=f'{3:032x}')['items'][0]['subject'])
        self.assertIsNone(self.get(trace_id=f'{4:032x}')['items'][0]['permission'])
        self.assertIsNone(self.get(trace_id=f'{5:032x}')['items'][0]['policy_revision'])

    def test_ac2002_outcomes_privacy_and_trace_association(self):
        for trace,outcome in enumerate(('completed','error','cancelled'),1):self.seed(trace,effect='allow',reason='explicit_allow',outcome=outcome)
        self.seed(4)
        for outcome in ('completed','error','cancelled','denied'):
            row=self.get(outcome=outcome)['items'][0]
            self.assertEqual(row['status'],'UNSET' if outcome=='completed' else 'ERROR')
            detail=self.client.get('/api/v1/traces/'+row['trace_id'],headers=self.headers).json()
            self.assertTrue(any(span['span_id']==row['span_id'] for span in detail['spans']))
        raw=str(self.get());self.assertNotIn('private-body',raw);self.assertNotIn('arguments',raw)

    def test_ac2002_corrupt_query_database_fault_and_old_routes_preserved(self):
        self.seed(1)
        self.assertEqual(self.client.get('/api/v1/traces',headers=self.headers).json()['total'],1)
        with psycopg.connect(DATABASE) as connection:connection.execute(sql.SQL('DROP TABLE {}.spans').format(sql.Identifier(self.schema)))
        response=self.client.get('/api/v1/security-events',headers=self.headers)
        self.assertEqual(response.status_code,503);self.assertEqual(response.json(),{'error':'storage unavailable'})
