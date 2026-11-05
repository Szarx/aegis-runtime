import unittest

from aegis_collector.ingestion.otlp import decode
from tests.fixtures.llm import llm_request
from tests.fixtures.otlp import first_span


def deepseek_request():
    request = llm_request()
    for attr in first_span(request).attributes:
        if attr.key == 'gen_ai.provider.name': attr.value.string_value = 'deepseek'
        if attr.key == 'aegis.call.api': attr.value.string_value = 'chat.completions'
    return request


class DeepSeekProtocol(unittest.TestCase):
    def test_ac503_deepseek_keeps_provider_and_typed_usage(self):
        records,rejected = decode(deepseek_request().SerializeToString())
        self.assertEqual(rejected,0)
        self.assertEqual(records[0].attributes['gen_ai.provider.name'],'deepseek')
        self.assertEqual(records[0].attributes['gen_ai.usage.output_tokens'],0)

    def test_ac503_deepseek_responses_and_unknown_provider_rejected(self):
        for key,value in [('aegis.call.api','responses'),('gen_ai.provider.name','unknown')]:
            request = deepseek_request()
            next(a for a in first_span(request).attributes if a.key==key).value.string_value=value
            self.assertEqual(decode(request.SerializeToString()),([],1))
