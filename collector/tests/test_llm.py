"""SPEC-004 typed LLM ingestion boundaries and legacy coexistence."""

import unittest
from pydantic import ValidationError

from aegis_collector.api.models import SpanView
from aegis_collector.ingestion.otlp import decode
from tests.fixtures.llm import llm_request
from tests.fixtures.otlp import combine, first_span, request_for


class LLMProtocol(unittest.TestCase):
    def test_ac406_v1_v2_coexist_and_preserve_integer_zero(self):
        records, rejected = decode(combine(request_for(), llm_request()).SerializeToString())
        self.assertEqual(rejected, 0)
        self.assertEqual([record.kind for record in records], ['INTERNAL', 'CLIENT'])
        self.assertEqual(records[1].attributes['gen_ai.usage.output_tokens'], 0)
        result = SpanView.model_validate(records[1].public()).model_dump()
        self.assertIs(type(result['attributes']['gen_ai.usage.input_tokens']), int)
        result['attributes']['gen_ai.usage.input_tokens'] = True
        with self.assertRaises(ValidationError): SpanView.model_validate(result)

    def test_ac406_invalid_token_types_mapping_kind_and_outcomes_are_rejected(self):
        for value_type, value in (('bool_value', True), ('string_value', '1'), ('double_value', 1.2), ('int_value', -1)):
            request = llm_request()
            count = next(item for item in first_span(request).attributes if item.key == 'gen_ai.usage.input_tokens')
            count.value.Clear(); setattr(count.value, value_type, value)
            self.assertEqual(decode(request.SerializeToString()), ([], 1))
        for key, value in (('aegis.mapping.version','aegis.genai.v1'), ('aegis.call.outcome','error'), ('gen_ai.provider.name','unknown'), ('aegis.call.api','unknown')):
            request = llm_request()
            next(item for item in first_span(request).attributes if item.key == key).value.string_value = value
            self.assertEqual(decode(request.SerializeToString()), ([], 1))
        request = llm_request(); first_span(request).kind = 1
        self.assertEqual(decode(request.SerializeToString()), ([], 1))

    def test_ac405_llm_privacy_whitelist_and_native_mapping_stays_small(self):
        request = llm_request()
        for key in ('gen_ai.input.messages','gen_ai.output.messages','authorization','response.id','gen_ai.tool.name'):
            first_span(request).attributes.add(key=key).value.string_value = 'sensitive'
        records, rejected = decode(request.SerializeToString())
        self.assertEqual(rejected, 0)
        self.assertNotIn('sensitive', str(records))
        native = request_for()
        first_span(native).attributes.add(key='gen_ai.usage.input_tokens').value.int_value = 7
        records, _ = decode(native.SerializeToString())
        self.assertNotIn('gen_ai.usage.input_tokens', records[0].attributes)
