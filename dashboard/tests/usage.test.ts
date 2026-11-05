import { describe, expect, it } from 'vitest'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
import type { Span, TraceDetail as Detail } from '../src/api/types'
import { summarizeUsage } from '../src/usage'
import { decodeDetail } from '../src/api/client'
import UsageSummary from '../src/components/UsageSummary.vue'
import TraceDetail from '../src/views/TraceDetail.vue'

const trace = '1'.repeat(32)
const origin = 1790000000000000101n
function model(id: string, input?: bigint, output?: bigint): Span {
  return { trace_id: trace, span_id: id.padStart(16, '0'), parent_span_id: null, name: 'chat synthetic', operation: 'chat', kind: 'CLIENT', status: 'UNSET', service_name: 'demo', agent_name: 'demo', start_time_unix_nano: origin, end_time_unix_nano: origin + 1n, attributes: {
    'aegis.mapping.version': 'aegis.genai.v2', ...(input === undefined ? {} : { 'gen_ai.usage.input_tokens': input }), ...(output === undefined ? {} : { 'gen_ai.usage.output_tokens': output }),
  }, resource: {}, scope: {}, events: [] }
}
function detail(spans: Span[]): Detail {
  return { trace: { trace_id: trace, start_time_unix_nano: origin, end_time_unix_nano: origin + 1n, duration_ns: 1n, span_count: spans.length, status: 'UNSET', agent_names: ['demo'] }, spans, missing_parent_ids: [] }
}
const render = (spans: Span[]) => renderToString(createSSRApp(UsageSummary, { detail: detail(spans) }))

describe('AC1901 received Trace usage', () => {
  it('sums beyond int64 without precision loss and preserves real zero', () => {
    const result = summarizeUsage([model('1', 9223372036854775807n, 0n), model('2', 9223372036854775807n, 0n)], trace)
    expect(result).toEqual({ calls: 2, input: { total: 18446744073709551614n, known: 2 }, output: { total: 0n, known: 2 } })
  })
  it('keeps each dimension unknown independently instead of showing a partial sum', () => {
    const result = summarizeUsage([model('1', 7n, 3n), model('2', undefined, 0n)], trace)
    expect(result.input).toEqual({ total: null, known: 1 })
    expect(result.output).toEqual({ total: 3n, known: 2 })
    expect(summarizeUsage([model('1')], trace).output).toEqual({ total: null, known: 0 })
  })
  it('does not invent zero usage when there are no model calls', () => {
    expect(summarizeUsage([], trace)).toEqual({ calls: 0, input: { total: null, known: 0 }, output: { total: null, known: 0 } })
  })
  it('excludes agent/tool attributes, other traces and mappings, and deduplicates IDs', () => {
    const llm = model('1', 7n, 3n)
    const agent = { ...model('2', 99n, 99n), operation: 'invoke_agent', kind: 'INTERNAL' } as Span
    const tool = { ...model('3', 99n, 99n), operation: 'execute_tool', kind: 'INTERNAL' } as Span
    const other = { ...model('4', 99n, 99n), trace_id: '2'.repeat(32) }
    const unknown = model('5', 99n, 99n); unknown.attributes['aegis.mapping.version'] = 'other'
    expect(summarizeUsage([llm, { ...llm }, agent, tool, other, unknown], trace)).toEqual(summarizeUsage([llm], trace))
  })
  it('includes reported usage from error/cancelled calls without treating status as billing', () => {
    const failed = model('1', 2n, 0n); failed.status = 'ERROR'; failed.attributes['aegis.call.outcome'] = 'cancelled'
    expect(summarizeUsage([failed, model('2', 3n, 4n)], trace).input.total).toBe(5n)
  })
  it('does not coerce malformed or out-of-range individual counts', () => {
    for (const value of ['7', true, -1n, 9223372036854775808n]) {
      const llm = model('1'); llm.attributes['gen_ai.usage.input_tokens'] = value as unknown as bigint
      expect(summarizeUsage([llm], trace).input).toEqual({ total: null, known: 0 })
    }
  })
})

describe('AC1902 detail presentation', () => {
  it('AC3902 selects an explicitly linked received node ahead of the default error selection',async()=>{
    const first=model('1',7n,3n);first.status='ERROR'
    const second=model('2',10n,0n)
    const html=await renderToString(createSSRApp(TraceDetail,{detail:detail([first,second]),spanId:second.span_id,pageUrl:'https://dashboard.example/'}))
    expect(html).toMatch(/data-span-id="0000000000000002"[^>]*aria-pressed="true"/)
    expect(html).toMatch(/data-testid="input-tokens"[^>]*>10</)
    expect(html).toContain('复制节点链接');expect(html).not.toContain('指定节点尚未到达')
    expect(html).toContain('17')
  })
  it('AC3902 explains a missing linked node without inventing a Span or replacing received usage',async()=>{
    const html=await renderToString(createSSRApp(TraceDetail,{detail:detail([model('1',7n,3n)]),spanId:'f'.repeat(16)}))
    expect(html).toContain('指定节点尚未到达或不在此 Trace 中')
    expect(html).toContain('未额外查询或创建节点')
    expect(html).toMatch(/data-testid="total-input-tokens"[^>]*>7</)
    expect(html).not.toContain('data-span-id="ffffffffffffffff"')
  })
  it('AC3702 keeps values and coverage visible while disclosing the longer explanation separately', async () => {
    const html=await render([model('1',7n,0n),model('2',undefined,0n)])
    expect(html).toContain('模型用量汇总');expect(html).toContain('1 / 2 个调用有此项数据')
    expect(html).toMatch(/data-testid="total-input-tokens"[^>]*>未知</)
    expect(html).toMatch(/data-testid="total-output-tokens"[^>]*>0</)
    expect(html).toMatch(/<details class="usage-coverage"[^>]*><summary[^>]*>统计范围与覆盖说明/)
    expect(html).not.toMatch(/<details class="usage-coverage"[^>]*open/)
    expect(html).toContain('不保证 Trace 到齐');expect(html).toContain('缺失用量不按零计算')
  })
  it('AC3702 removes the duplicate usage placeholder and keeps native details without an empty model card', async () => {
    const html=await renderToString(createSSRApp(TraceDetail,{detail:detail([])}))
    expect(html).not.toContain('下方汇总');expect(html).not.toContain('已接收模型用量汇总')
    expect(html).toContain('执行时长');expect(html).toContain('关联节点');expect(html).toContain('开始时间 · UTC')
    expect(html).toContain(trace);expect(html).toContain('执行链路')
  })
  it('renders exact wire integers in the actual detail view and retains node usage', async () => {
    const wire = JSON.stringify(detail([model('1', 9223372036854775807n, 0n), model('2', 9223372036854775807n, 0n)]), (_key, value) => typeof value === 'bigint' ? '__bigint_' + value : value).replace(/"__bigint_(-?\d+)"/g, '$1')
    const html = await renderToString(createSSRApp(TraceDetail, { detail: decodeDetail(wire) }))
    expect(html).toContain('18446744073709551614')
    expect(html).toMatch(/data-testid="total-output-tokens"[^>]*>0</)
    expect(html).toContain('2 / 2 个调用有此项数据')
    expect(html).toContain('data-testid="input-tokens"')
    expect(html).toContain('未估算')
  })
  it('renders unknown, zero and no calls distinctly with explicit coverage limits', async () => {
    const html = await render([model('1', 7n, 0n), model('2', undefined, 0n)])
    expect(html).toMatch(/data-testid="total-input-tokens"[^>]*>未知</)
    expect(html).toMatch(/data-testid="total-output-tokens"[^>]*>0</)
    expect(html).toContain('1 / 2 个调用有此项数据')
    expect(html).toContain('不保证 Trace 到齐')
    expect(await render([])).toContain('无模型调用')
  })
})
