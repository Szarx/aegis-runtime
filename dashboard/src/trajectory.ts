import { governanceSignals, type GovernanceSignal, type Span } from './api/types'
import { spanOutcome, type TreeRow } from './domain'

export const signalLabels: Record<GovernanceSignal, string> = {
  denied: '工具被阻止',
  tool_error: '受控工具异常或取消',
  approval_requested: '曾请求人工审批',
  review_tool_returned: '审批后工具已返回',
}

export const isGoverned = (span: Span): boolean =>
  span.operation === 'execute_tool' && span.kind === 'INTERNAL' &&
  ['aegis.governance.v1', 'aegis.governance.v2'].includes(String(span.attributes['aegis.mapping.version']))

export function receivedSignal(spans: readonly Span[]): GovernanceSignal | undefined {
  const observed = new Set<GovernanceSignal>()
  for (const span of spans) {
    if (!isGoverned(span)) continue
    const outcome = spanOutcome(span)
    if (outcome === 'denied') observed.add('denied')
    if (outcome === 'error' || outcome === 'cancelled') observed.add('tool_error')
    if (span.attributes['aegis.mapping.version'] !== 'aegis.governance.v2') continue
    const phase = span.attributes['aegis.approval.phase']
    if (phase === 'request' && outcome === 'awaiting_approval') observed.add('approval_requested')
    if (phase === 'execute' && outcome === 'completed') observed.add('review_tool_returned')
  }
  return governanceSignals.find(signal => observed.has(signal))
}

export const trajectoryLanes = ['Agent', '模型', '工具', '治理'] as const
export function laneOf(span: Span): typeof trajectoryLanes[number] {
  if (isGoverned(span)) return '治理'
  if (span.operation === 'invoke_agent') return 'Agent'
  return span.operation === 'chat' ? '模型' : '工具'
}

export function chronological(rows: readonly TreeRow[]): TreeRow[] {
  return [...rows].sort(({ span: a }, { span: b }) => a.start_time_unix_nano < b.start_time_unix_nano ? -1 :
    a.start_time_unix_nano > b.start_time_unix_nano ? 1 : a.span_id.localeCompare(b.span_id))
}

export function position(span: Span, origin: bigint, duration: bigint): { left: number; width: number } | undefined {
  const start = span.start_time_unix_nano - origin
  const end = span.end_time_unix_nano - origin
  if (duration < 0n || start < 0n || end < start || end > duration) return
  if (duration === 0n) return { left: 0, width: 0 }
  const percent = (ns: bigint) => Number(ns * 100000n / duration) / 1000
  const left = Math.min(percent(start), 99.5)
  return { left, width: Math.min(100 - left, Math.max(percent(end - start), 0.5)) }
}
