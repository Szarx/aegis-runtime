import { describe, expect, it } from 'vitest'
import { decodeDetail, decodeList } from '../src/api/client'
import { spanOutcome, statusLabel } from '../src/domain'

const trace = { trace_id: '1'.padStart(32, '0'), start_time_unix_nano: 1790000000000000101n, end_time_unix_nano: 1790000000000000102n, duration_ns: 1n, span_count: 1, status: 'UNSET', agent_names: ['stream-agent'] }
function encode(value: unknown) {
  return JSON.stringify(value, (_key, value) => typeof value === 'bigint' ? '__int_' + value : value).replace(/"__int_(-?\d+)"/g, '$1')
}
describe('graph stream lifecycle', () => {
  it('decodes nullable and legacy summaries without inventing an outcome', () => {
    for (const item of [trace, { ...trace, graph_outcome: null }]) {
      const result = decodeList(encode({ items: [item], total: 1, limit: 20, offset: 0 }))
      expect(result.items[0]!.graph_outcome).toBeNull()
    }
  })
  it('retains closed/cancelled while rejecting unknown lifecycle metadata', () => {
    for (const outcome of ['closed', 'completed', 'cancelled', 'error']) {
      const result = decodeList(encode({ items: [{ ...trace, graph_outcome: outcome }], total: 1, limit: 20, offset: 0 }))
      expect(result.items[0]!.graph_outcome).toBe(outcome)
    }
    expect(() => decodeList(encode({ items: [{ ...trace, graph_outcome: 'running' }], total: 1, limit: 20, offset: 0 }))).toThrow('格式')
  })
  it('uses graph outcome for Agent nodes and preserves error status precedence', () => {
    const detail = decodeDetail(encode({ trace: { ...trace, graph_outcome: 'closed' }, spans: [{ trace_id: trace.trace_id, span_id: '1'.padStart(16, '0'), parent_span_id: null, name: 'invoke_agent stream-agent', operation: 'invoke_agent', kind: 'INTERNAL', status: 'UNSET', service_name: 'demo', agent_name: 'stream-agent', start_time_unix_nano: trace.start_time_unix_nano, end_time_unix_nano: trace.end_time_unix_nano, attributes: { 'aegis.mapping.version': 'aegis.graph.v1', 'aegis.graph.mode': 'stream', 'aegis.graph.outcome': 'closed' }, resource: {}, scope: {}, events: [] }], missing_parent_ids: [] }))
    expect(spanOutcome(detail.spans[0]!)).toBe('closed')
    expect(statusLabel(detail.trace.status, detail.trace.graph_outcome)).toBe('提前关闭')
    expect(statusLabel('ERROR', 'closed')).toBe('异常')
    expect(statusLabel('ERROR', 'cancelled')).toBe('已取消')
  })
})
