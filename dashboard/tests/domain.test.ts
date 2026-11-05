import { describe, expect, it } from 'vitest'
import { decodeDetail, decodeList } from '../src/api/client'
import type { Span } from '../src/api/types'
import { emptyFilters } from '../src/api/types'
import { buildTree, formatDuration, listPath, relativeMillis, validTraceId } from '../src/domain'

const origin = 1791960664304540201n
function node(id: number, parent: number | null = null): Span {
  return { trace_id: '1'.padStart(32, '0'), span_id: id.toString(16).padStart(16, '0'), parent_span_id: parent === null ? null : parent.toString(16).padStart(16, '0'), name: 'invoke_agent demo', operation: 'invoke_agent', kind: 'INTERNAL', status: 'UNSET', service_name: 'orders', agent_name: 'demo', start_time_unix_nano: origin, end_time_unix_nano: origin + 1n, attributes: {}, resource: {}, scope: {}, events: [] }
}
const summary = `{"trace_id":"${'1'.padStart(32, '0')}","start_time_unix_nano":${origin},"end_time_unix_nano":${origin + 1n},"duration_ns":1,"span_count":2,"status":"UNSET","agent_names":["demo"]}`

describe('AC-304 exact integer API boundary', () => {
  it('preserves 19 digits and adjacent 1 ns from real JSON numeric tokens', () => {
    const list = decodeList(`{"items":[${summary}],"total":1,"limit":20,"offset":0}`)
    expect(list.items[0]!.start_time_unix_nano).toBe(origin)
    expect(list.items[0]!.end_time_unix_nano - list.items[0]!.start_time_unix_nano).toBe(1n)
    expect(list.total).toBe(1)
    expect(relativeMillis(origin + 1n, origin)).toBe(0.000001)
  })
  it('preserves span and exception event timestamps without parsing rounded numbers', () => {
    const span = node(1)
    const raw = JSON.stringify(span, (_key, value) => typeof value === 'bigint' ? value.toString() : value).replace(/"(179196066430454020[12])"/g, '$1')
    const detail = decodeDetail(`{"trace":${summary},"spans":[${raw}],"missing_parent_ids":[]}`)
    expect(detail.spans[0]!.end_time_unix_nano).toBe(origin + 1n)
  })
  it('rejects unsafe count conversion, malformed types, duplicates and fractional timestamps', () => {
    const base = `{"items":[],"total":9007199254740993,"limit":20,"offset":0}`
    expect(() => decodeList(base)).toThrow('格式')
    expect(() => decodeList('{"items":[],"total":1,"total":2,"limit":20,"offset":0}')).toThrow('格式')
    expect(() => decodeList(`{"items":[${summary.replace(origin.toString(), '1.2')}],"total":1,"limit":20,"offset":0}`)).toThrow('格式')
    expect(() => decodeList('{}')).toThrow('格式')
  })
  it('formats zero, one nanosecond and maximum database duration without overflow', () => {
    expect(formatDuration(0n)).toBe('0 ns')
    expect(formatDuration(1n)).toBe('1 ns')
    expect(formatDuration(1234567n)).toBe('1.234 ms')
    expect(formatDuration(9223372036854775807n)).toBe('9223372036.854 s')
  })
})

describe('AC-303 graph safety', () => {
  it('orders child-first input under its parent, preserves multiple roots and missing parents', () => {
    const rows = buildTree([node(2, 1), node(3, 99), node(1), node(4)])
    expect(rows.map(row => [Number.parseInt(row.span.span_id, 16), row.depth, row.relation])).toEqual([[3, 0, 'missing'], [1, 0, 'normal'], [2, 1, 'normal'], [4, 0, 'normal']])
  })
  it('terminates cycles and self-parent relationships with every node shown once', () => {
    const rows = buildTree([node(1, 2), node(2, 1), node(3, 2), node(4, 4)])
    expect(rows).toHaveLength(4)
    expect(new Set(rows.map(row => row.span.span_id)).size).toBe(4)
    expect(rows.filter(row => row.relation === 'cycle')).toHaveLength(2)
  })
  it('handles deep chains iteratively', () => {
    const rows = buildTree(Array.from({ length: 1500 }, (_, i) => node(i + 1, i === 0 ? null : i)))
    expect(rows).toHaveLength(1500)
    expect(rows.at(-1)?.depth).toBe(1499)
  })
})

describe('AC-302 query inputs and routes', () => {
  it('encodes filters and timestamp boundaries without sending empty values', () => {
    const filters = { ...emptyFilters(), agent: 'a&b', after: '2026-10-15T12:34', before: '2026-10-15T12:35' }
    const path = listPath(filters, 20), params = new URLSearchParams(path.split('?')[1])
    expect(params.get('agent_name')).toBe('a&b')
    expect(params.has('service_name')).toBe(false)
    expect(params.get('started_after_ns')).toBe((BigInt(new Date(filters.after).getTime()) * 1000000n).toString())
    expect(params.get('offset')).toBe('20')
  })
  it('blocks reversed ranges and offsets beyond the query API contract', () => {
    expect(() => listPath({ ...emptyFilters(), after: '2026-10-15T12:35', before: '2026-10-15T12:34' }, 0)).toThrow('早于')
    expect(() => listPath(emptyFilters(), 10020)).toThrow('范围')
    expect(() => listPath({ ...emptyFilters(), after: 'bad' }, 0)).toThrow('有效')
    expect(validTraceId('0'.repeat(32))).toBe(false)
    expect(validTraceId('1'.padStart(32, '0'))).toBe(true)
    expect(validTraceId('../outside')).toBe(false)
  })
})
