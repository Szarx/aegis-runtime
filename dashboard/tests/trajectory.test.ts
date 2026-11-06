import { describe, expect, it, vi } from 'vitest'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { ApprovalChannel } from '../src/api/approvals'
import { readReviewLocation, reviewActionLink } from '../src/approvalLocation'
import { decodeList } from '../src/api/client'
import type { Span } from '../src/api/types'
import { buildTree } from '../src/domain'
import { approvalDecisionLabel } from '../src/reviewQueue'
import { chronological, laneOf, position, receivedSignal } from '../src/trajectory'
import TrajectoryDemo from '../src/views/TrajectoryDemo.vue'
import Trajectory from '../src/components/Trajectory.vue'
import { filterTraceRows } from '../src/traceExplorer'

const action = 'a'.repeat(32), trace = '1'.repeat(32), origin = 1793577600000000000n
const approvalSpan = (id: string, start: bigint, phase: string, outcome: string): Span => ({
  trace_id: trace, span_id: id.repeat(16), parent_span_id: null, name: 'write',
  operation: 'execute_tool', kind: 'INTERNAL', service_name: 'demo', agent_name: null, status: 'UNSET',
  start_time_unix_nano: start, end_time_unix_nano: start, attributes: {
    'aegis.mapping.version': 'aegis.governance.v2', 'aegis.approval.phase': phase, 'aegis.action.outcome': outcome,
  }, events: [], scope: {}, resource: {},
})

describe('SPEC-047', () => {
  it('orders overlapping and equal starts by exact nanoseconds and preserves zero duration', () => {
    const later = approvalSpan('1', origin + 1n, 'execute', 'completed')
    const earlier = approvalSpan('2', origin, 'request', 'awaiting_approval')
    const tie = approvalSpan('3', origin, 'request', 'awaiting_approval')
    expect(chronological(buildTree([later, tie, earlier])).map(row => row.span.span_id[0])).toEqual(['2', '3', '1'])
    expect(laneOf(earlier)).toBe('治理')
    expect(position(earlier, origin, 0n)).toEqual({ left: 0, width: 0 })
    expect(position(later, origin, 0n)).toBeUndefined()
    expect(position({ ...later, end_time_unix_nano: origin }, origin, 3n)).toBeUndefined()
    expect(receivedSignal([later, earlier])).toBe('approval_requested')
    expect(receivedSignal([later, earlier, approvalSpan('4', origin, 'request', 'denied')])).toBe('denied')
  })

  it('accepts an older list and rejects unknown governance signals', () => {
    const row = { trace_id: trace, start_time_unix_nano: 100, end_time_unix_nano: 200, duration_ns: 100,
      span_count: 1, status: 'UNSET', agent_names: [] }
    const payload = (governance_signal?: string) => JSON.stringify({ items: [{ ...row, governance_signal }], total: 1, limit: 20, offset: 0 })
    expect(decodeList(payload()).items[0]?.governance_signal).toBeUndefined()
    expect(decodeList(payload('review_tool_returned')).items[0]?.governance_signal).toBe('review_tool_returned')
    expect(() => decodeList(payload('confirmed'))).toThrow()
  })

  it('returns to the selected trace, rejects unsafe locations and verifies exact responses', async () => {
    const returnTo = '#/traces/' + trace + '?span=' + '2'.repeat(16)
    expect(readReviewLocation(reviewActionLink(action, returnTo)!)).toEqual({ actionId: action, returnTo })
    expect(readReviewLocation('#/reviewed-actions?action_id=' + action + '&return=https%3A%2F%2Fexample.org')).toBeNull()
    expect(readReviewLocation('#/reviewed-actions?action_id=' + action + '&action_id=' + action)).toBeNull()
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response('{"items":[],"total":0,"limit":1,"offset":0}'))
    const channel = new ApprovalChannel(fetcher, 5000, true)
    const commit = vi.fn()
    await channel.run('synthetic-reviewer', 0, commit, undefined, action)
    expect(fetcher.mock.calls[0]?.[0]).toBe('/api/v1/reviewed-actions?limit=1&offset=0&action_id=' + action)
    expect(commit).toHaveBeenCalledOnce()
    fetcher.mockResolvedValue(new Response('{"items":[],"total":7,"limit":20,"offset":0}'))
    await expect(channel.run('synthetic-reviewer', 0, commit, undefined, action)).rejects.toThrow()
    expect(commit).toHaveBeenCalledOnce()
  })

  it('renders the offline request, confirmed approval and recovery as separate stages', async () => {
    const render = (hash: string) => renderToString(createSSRApp(TrajectoryDemo, { hash }))
    const request = await render('#/demo')
    expect(request).toContain('曾请求人工审批')
    expect(request).toContain('判断退款流程')
    expect(request).toContain('待审批快照')
    expect(request).toMatch(/data-testid="total-input-tokens"[^>]*>120</)
    expect(await render('#/demo/approval')).toContain('已确认完成')
    expect(await render('#/demo/execution')).toContain('审批后工具已返回')
  })

  it('retains the recorded decision after the claim window expires', () => {
    expect(approvalDecisionLabel({ status: 'expired', decided_at: '2026-11-05T00:00:00Z' })).toBe('已记录批准 · 领取窗口已结束')
    expect(approvalDecisionLabel({ status: 'expired', decided_at: null })).toBe('审核已过期')
  })

  it('reveals a deep-linked step after the first 50 and supports Action ID or rule search', async () => {
    const spans = Array.from({ length: 62 }, (_, i) => {
      const span = approvalSpan('1', origin + BigInt(i), 'request', 'awaiting_approval')
      span.span_id = (i + 1).toString(16).padStart(16, '0')
      span.name = 'synthetic-step-' + i
      if (i === 60) {
        span.attributes['aegis.action.id'] = action
        span.attributes['aegis.decision.rule_id'] = 'refund-review'
      }
      return span
    })
    const rows = buildTree(spans)
    const selected = spans[60]!.span_id
    for (const term of [action, 'refund-review']) {
      expect(filterTraceRows(rows, 'all', term).map(row => row.span.span_id)).toEqual([selected])
    }
    const html = await renderToString(createSSRApp(Trajectory, { rows, selected, origin, duration: 61n }))
    expect(html).toMatch(new RegExp('data-span-id="' + selected + '"[^>]*aria-pressed="true"'))
    expect(html).not.toContain('synthetic-step-0')
    expect(html).toContain('51–62 / 62')
  })
})
