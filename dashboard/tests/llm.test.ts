import { describe, expect, it } from 'vitest'
import { decodeDetail } from '../src/api/client'
import { operationClass, operationSymbol, spanColor, statusLabel, tokenLabel } from '../src/domain'

const origin = 1790000000000000101n
function payload(tokens: unknown = 9007199254740993n, kind = 'CLIENT') {
  const value = {
    trace: { trace_id: '1'.padStart(32, '0'), start_time_unix_nano: origin, end_time_unix_nano: origin + 1n, duration_ns: 1n, span_count: 1, status: 'UNSET', agent_names: ['demo'] },
    spans: [{ trace_id: '1'.padStart(32, '0'), span_id: '1'.padStart(16, '0'), parent_span_id: null, name: 'chat model', operation: 'chat', kind, status: 'UNSET', service_name: 'demo', agent_name: 'demo', start_time_unix_nano: origin, end_time_unix_nano: origin + 1n, attributes: { 'gen_ai.request.model': 'model', 'gen_ai.usage.input_tokens': tokens, 'gen_ai.usage.output_tokens': 0n, 'aegis.call.outcome': 'completed' }, resource: {}, scope: {}, events: [] }], missing_parent_ids: [],
  }
  return JSON.stringify(value, (_key, value) => typeof value === 'bigint' ? '__bigint_' + value : value).replace(/"__bigint_(-?\d+)"/g, '$1')
}
describe('AC-407 typed LLM rendering data', () => {
  it('preserves large token integers and zero, while missing values stay unknown', () => {
    const model = decodeDetail(payload()).spans[0]!
    expect(tokenLabel(model.attributes['gen_ai.usage.input_tokens'])).toBe('9007199254740993')
    expect(tokenLabel(model.attributes['gen_ai.usage.output_tokens'])).toBe('0')
    expect(tokenLabel(undefined)).toBe('未知')
  })
  it('rejects string/bool/negative token counts and wrong kind/operation pairs', () => {
    for (const value of ['7', true, -1n]) expect(() => decodeDetail(payload(value))).toThrow('格式')
    expect(() => decodeDetail(payload(7n, 'INTERNAL'))).toThrow('格式')
  })
  it('identifies LLM distinctly and never calls early close or incomplete completed', () => {
    const model = decodeDetail(payload()).spans[0]!
    expect(operationSymbol(model.operation)).toBe('L')
    expect(operationClass(model.operation)).toBe('llm')
    expect(spanColor(model)).toBe('#d4ba78')
    expect(statusLabel('UNSET', 'closed')).toBe('提前关闭')
    expect(statusLabel('UNSET', 'incomplete')).toBe('不完整')
    expect(statusLabel('ERROR', 'cancelled')).toBe('已取消')
  })
})
