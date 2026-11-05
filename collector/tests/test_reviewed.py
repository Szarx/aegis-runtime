import unittest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from aegis_collector.api import create_app
from tests.fixtures.reviewed import payload


class ReviewedAPI(unittest.TestCase):
    def setUp(self):
        self.store=Mock()
        self.client=TestClient(create_app(self.store,api_token="trace",approval_request_token="producer",approval_review_token="review",approval_execution_token="executor"))

    def test_ac1102_roles_and_default_disabled(self):
        self.assertEqual(TestClient(create_app(None)).get('/api/v1/reviewed-actions').status_code,503)
        for method,path,role in (('POST','/api/v1/reviewed-actions','producer'),('GET','/api/v1/reviewed-actions','review'),
                                ('POST','/api/v1/reviewed-actions/'+'1'*32+'/decision','review'),('POST','/api/v1/reviewed-actions/'+'1'*32+'/claim','executor'),
                                ('POST','/api/v1/reviewed-actions/'+'1'*32+'/complete','executor')):
            for token in ('','trace','producer','review','executor'):
                if token==role:continue
                self.assertEqual(self.client.request(method,path,headers={'Authorization':'Bearer '+token},content=b'bad').status_code,401)
        self.store.claim_reviewed.assert_not_called()

    def test_ac1102_execution_configuration_requires_distinct_complete_roles(self):
        for config in (dict(approval_execution_token='x'),dict(approval_request_token='p',approval_review_token='r',approval_execution_token='p'),
                       dict(api_token='t',approval_request_token='p',approval_review_token='r',approval_execution_token='t'),
                       dict(approval_request_token='p',approval_review_token='r',approval_execution_token=''),dict(approval_executor='invalid actor')):
            with self.assertRaises(ValueError):create_app(None,**config)

    def test_ac1102_rejects_invalid_digest_types_fields_and_large_body(self):
        headers={'Authorization':'Bearer producer'}
        for change in ({'review_digest':'c'*64},{'review_arguments':{'value':1.0}},{'review_arguments':{'value':'\x00'}},
                       {'review_arguments':[]},{'tool_revision':'bad version'},{'executor':'spoof'}):
            self.assertEqual(self.client.post('/api/v1/reviewed-actions',headers=headers,json={**payload(),**change}).status_code,400)
        self.assertEqual(self.client.post('/api/v1/reviewed-actions',headers={**headers,'Content-Type':'application/json'},content=b'x'*16385).status_code,413)
        self.store.create_reviewed.assert_not_called()

    def test_ac1102_decision_claim_and_completion_are_strict(self):
        for suffix,token,data in (('decision','review',{'decision':'approved'}),('decision','review',{'decision':'approved','review_digest':'a'*64,'reviewer':'fake'}),
                                  ('claim','executor',{'claim_id':'0'*32}),('complete','executor',{'claim_id':'1'*32,'outcome':'retry'})):
            self.assertEqual(self.client.post('/api/v1/reviewed-actions/'+'1'*32+'/'+suffix,headers={'Authorization':'Bearer '+token},json=data).status_code,400)
        self.store.claim_reviewed.assert_not_called();self.store.complete_reviewed.assert_not_called()
