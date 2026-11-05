import concurrent.futures
import copy
import io
import os
import unittest
import uuid

import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
from aegis_collector.api import create_app
from aegis_collector.storage import PostgresSpanStore
from aegis_collector.storage.approvals import ApprovalConflict, ApprovalMissing
from aegis_collector.storage.reviewed import BINDING
from aegis_runtime.approvals import ApprovalUnavailable
from tests.fixtures.reviewed import client, tool, payload
from collector.tests.test_approvals import payload as legacy_payload

DATABASE=os.environ.get('AEGIS_TEST_DATABASE_URL')


@unittest.skipUnless(DATABASE,'dedicated PostgreSQL required')
class ReviewedPostgres(unittest.TestCase):
    def setUp(self):
        self.schema='test_reviewed_'+uuid.uuid4().hex
        self.store=PostgresSpanStore(DATABASE,self.schema);self.store.migrate()
    def tearDown(self):
        with psycopg.connect(DATABASE) as connection:
            connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
    def approve(self,data):
        return self.store.decide_reviewed(data['action_id'],'approved',data['review_digest'],'server-reviewer')
    def binding(self,data,claim=None): return {**{key:data[key] for key in BINDING},'claim_id':claim or uuid.uuid4().hex}
    def expire(self,action):
        with self.store.connection() as connection:
            connection.execute(sql.SQL("UPDATE {}.approvals SET created_at=clock_timestamp()-INTERVAL '601 seconds',expires_at=clock_timestamp()-INTERVAL '1 second' WHERE action_id=%s").format(sql.Identifier(self.schema)),[action])

    def test_ac1103_atomic_creation_idempotency_and_protocol_isolation(self):
        data=payload()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            records=list(pool.map(lambda _:self.store.create_reviewed(data),range(3)))
        self.assertEqual(records[0],records[1]);self.assertEqual(self.store.list_reviewed()['total'],1)
        self.assertEqual(self.store.list_approvals()['total'],0)
        legacy={key:value for key,value in data.items() if key not in ('tool_revision','review_arguments','review_digest')}
        with self.assertRaises(ApprovalConflict):self.store.create_approval(legacy)
        with self.assertRaises(ApprovalMissing):self.store.decide_approval(data['action_id'],'approved','reviewer')
        old=legacy_payload();old['action_id']='2'*32;self.store.create_approval(old)
        upgraded={**data,**old}
        with self.assertRaises(ApprovalConflict):self.store.create_reviewed(upgraded)
        self.assertEqual(self.store.list_reviewed()['total'],1);self.assertEqual(self.store.list_approvals()['total'],1)

    def test_ac1103_binding_and_review_digest_cannot_change(self):
        data=payload();self.store.create_reviewed(data)
        with self.assertRaises(ApprovalConflict):self.store.decide_reviewed(data['action_id'],'approved','c'*64,'reviewer')
        self.approve(data)
        for key in BINDING:
            changed=self.binding(data);changed[key]=301 if key=='ttl_seconds' else 'c'*64 if key.endswith(('digest','hmac')) else 'changed'
            with self.subTest(key=key),self.assertRaises(ApprovalConflict):self.store.claim_reviewed(data['action_id'],changed,'executor')
        for change in ({'tool_revision':'impl-v2'},{'review_arguments':{'record':'other'}},{'summary':'other'}):
            with self.assertRaises(ApprovalConflict):self.store.create_reviewed({**data,**change})
        self.assertEqual(self.store.list_reviewed()['items'][0]['execution_state'],'available')

    def test_ac1103_concurrent_claims_only_one_and_no_repeat_even_same_claim_id(self):
        data=payload();self.store.create_reviewed(data);self.approve(data)
        def claim(_):
            try:return self.store.claim_reviewed(data['action_id'],self.binding(data),'server-executor')
            except ApprovalConflict:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(claim,range(4)))
        winners=[row for row in results if row is not None];self.assertEqual(len(winners),1)
        winner=winners[0]
        self.assertGreater(winner['remaining_ms'],0);self.assertEqual(winner['executor'],'server-executor')
        with self.assertRaises(ApprovalConflict):self.store.claim_reviewed(data['action_id'],self.binding(data,winner['claim_id']),'server-executor')

    def test_ac1103_expiry_rejection_and_pending_cannot_claim(self):
        for index,state in enumerate(('pending','rejected','expired'),1):
            data=payload(f'{index:032x}');self.store.create_reviewed(data)
            if state=='rejected':self.store.decide_reviewed(data['action_id'],'rejected',data['review_digest'],'reviewer')
            if state=='expired':self.approve(data);self.expire(data['action_id'])
            with self.assertRaises(ApprovalConflict):self.store.claim_reviewed(data['action_id'],self.binding(data),'executor')
        self.assertEqual({r['status'] for r in self.store.list_reviewed()['items']},{'pending','rejected','expired'})

    def test_ac1103_completion_idempotent_unknown_never_released_and_late_confirmation(self):
        data=payload();self.store.create_reviewed(data);self.approve(data)
        record=self.store.claim_reviewed(data['action_id'],self.binding(data),'executor')
        self.expire(data['action_id'])
        self.assertEqual(self.store.list_reviewed()['items'][0]['execution_state'],'claimed')
        with self.assertRaises(ApprovalConflict):self.store.complete_reviewed(data['action_id'],'f'*32,'completed','executor')
        with self.assertRaises(ApprovalConflict):self.store.complete_reviewed(data['action_id'],record['claim_id'],'completed','other-executor')
        first=self.store.complete_reviewed(data['action_id'],record['claim_id'],'failed','executor')
        second=self.store.complete_reviewed(data['action_id'],record['claim_id'],'failed','executor')
        self.assertEqual(first,second)
        with self.assertRaises(ApprovalConflict):self.store.complete_reviewed(data['action_id'],record['claim_id'],'completed','executor')
        with self.assertRaises(ApprovalConflict):self.store.claim_reviewed(data['action_id'],self.binding(data),'executor')

    def test_ac1103_schema3_upgrade_preserves_legacy_and_rebuild_preserves_claim(self):
        self.store.create_approval(legacy_payload())
        with self.store.connection() as connection:
            connection.execute(sql.SQL('DROP TABLE {}.reviewed_actions').format(sql.Identifier(self.schema)))
            connection.execute(sql.SQL('DELETE FROM {}.schema_version WHERE version=4').format(sql.Identifier(self.schema)))
        self.store.migrate();self.store.migrate();self.store.ping()
        self.assertEqual(self.store.list_approvals()['total'],1)
        data=payload('2'*32);self.store.create_reviewed(data);self.approve(data)
        first=self.store.claim_reviewed(data['action_id'],self.binding(data),'executor')
        rebuilt=PostgresSpanStore(DATABASE,self.schema);rebuilt.migrate()
        row=rebuilt.list_reviewed()['items'][0]
        self.assertEqual(row['claim_id'],first['claim_id']);self.assertEqual(row['execution_state'],'claimed')
        with self.assertRaises(ApprovalConflict):rebuilt.claim_reviewed(data['action_id'],self.binding(data),'executor')

    def test_ac1104_real_routes_and_runtime_execute_once_with_error_identity(self):
        app=create_app(self.store,approval_request_token='synthetic-producer',approval_review_token='synthetic-reviewer',approval_execution_token='synthetic-executor',approval_executor='server-executor')
        class Response(io.BytesIO):status=200
        with TestClient(app) as http:
            class Opener:
                def open(self,request,**kwargs):
                    response=http.post(request.full_url,content=request.data,headers=dict(request.header_items()))
                    if response.status_code!=200:raise OSError('fixed transport status')
                    return Response(response.content)
            transport=client();transport._opener=Opener();calls=[];value=object()
            def write(record='synthetic-001',value=1):calls.append(record);return returned
            returned=value
            governed=tool(write,transport)
            ticket=governed.prepare({},summary='Synthetic change')
            route='/api/v1/reviewed-actions/'+ticket['action_id']+'/decision'
            approved=http.post(route,headers={'Authorization':'Bearer synthetic-reviewer'},json={'decision':'approved','review_digest':ticket['review_digest']})
            self.assertEqual(approved.status_code,200)
            result=governed.resume(ticket['action_id'],{},summary='Synthetic change')
            self.assertIs(result.value,value);self.assertEqual(result.confirmation,'confirmed')
            with self.assertRaises(ApprovalUnavailable):governed.resume(ticket['action_id'],{},summary='Synthetic change')
            self.assertEqual(calls,['synthetic-001'])
            original=ValueError('private failure')
            def fail(record='synthetic-001',value=1):calls.append('failure');raise original
            failed=tool(fail,transport);ticket=failed.prepare({},summary='Synthetic error')
            self.store.decide_reviewed(ticket['action_id'],'approved',ticket['review_digest'],'reviewer')
            with self.assertRaises(ValueError) as context:failed.resume(ticket['action_id'],{},summary='Synthetic error')
            self.assertIs(context.exception,original)
            states={row['execution_state'] for row in self.store.list_reviewed()['items']}
            self.assertEqual(states,{'completed','failed'});self.assertNotIn('private failure',str(self.store.list_reviewed()))
