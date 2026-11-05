import type { Span, TraceDetail } from './api/types'

export interface RankedCall { span: Span; duration: bigint; share: string; barWidth: number }

export function rankCalls(detail: TraceDetail): { total: number; invalid: number; rows: RankedCall[] } {
  const received = new Map<string,Span>()
  for (const span of detail.spans) {
    if (span.attributes['aegis.mapping.version'] === 'aegis.governance.v2' && span.attributes['aegis.approval.phase'] === 'request') continue
    if (span.trace_id === detail.trace.trace_id && ((span.operation === 'chat' && span.kind === 'CLIENT') ||
        (span.operation === 'execute_tool' && span.kind === 'INTERNAL')) && !received.has(span.span_id)) received.set(span.span_id,span)
  }
  const rows: RankedCall[] = []; let invalid = 0
  for (const span of received.values()) {
    const start = span.start_time_unix_nano, end = span.end_time_unix_nano
    if (!/^[0-9a-f]{16}$/.test(span.span_id) || /^0+$/.test(span.span_id) || typeof start !== 'bigint' || typeof end !== 'bigint' ||
        start <= 0n || end < start || end > 9223372036854775807n) { invalid++; continue }
    const duration = end - start, total = detail.trace.duration_ns
    const basis = typeof total === 'bigint' && total > 0n ? duration * 10000n / total : null
    rows.push({span,duration,share:basis === null ? '未知' : duration > 0n && basis === 0n ? '<0.01%' :
      `${basis / 100n}.${(basis % 100n).toString().padStart(2,'0')}%`,barWidth:basis === null ? 0 : Number(basis > 10000n ? 10000n : basis) / 100})
  }
  rows.sort((a,b) => a.duration > b.duration ? -1 : a.duration < b.duration ? 1 : a.span.span_id < b.span.span_id ? -1 : a.span.span_id > b.span.span_id ? 1 : 0)
  return {total:received.size,invalid,rows:rows.slice(0,20)}
}
