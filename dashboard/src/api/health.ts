import { decode, ApiError } from './client'
import { validTraceId } from '../domain'

export const diagnosticNames = ['accepted_spans', 'exported_spans', 'failed_spans', 'dropped_spans',
  'pending_spans', 'export_failures', 'instrumentation_failures'] as const
export interface HealthInstance {
  instance_id: string; sequence: number; service_name: string; active_spans: number; active_traces: string[]
  activity_truncated: boolean; health_failures: number; age_ms: number; last_received_at: string
  state: 'reporting' | 'stale'; diagnostics: Record<typeof diagnosticNames[number], number>
}
export interface HealthList { items: HealthInstance[]; evicted_instances: number; stale_after_ms: number; scope: string }

function count(value: unknown): number {
  if (typeof value !== 'bigint' || value < 0n || value > BigInt(Number.MAX_SAFE_INTEGER)) throw new ApiError('invalid')
  return Number(value)
}
export function decodeHealth(raw: string): HealthList {
  const v = decode(raw) as HealthList
  if (!v || v.scope !== 'collector_process' || !Array.isArray(v.items) || v.items.length > 1024 ||
      count(v.stale_after_ms) !== 45000) throw new ApiError('invalid')
  const seen = new Set<string>()
  const items = v.items.map(row => {
    if (!row || typeof row.instance_id !== 'string' || !validTraceId(row.instance_id) || seen.has(row.instance_id) ||
        typeof row.service_name !== 'string' || !row.service_name || row.service_name.length > 128 ||
        /[\x00-\x1f\x7f]/.test(row.service_name) || typeof row.activity_truncated !== 'boolean' ||
        !Array.isArray(row.active_traces) || row.active_traces.length > 16 ||
        row.active_traces.some(id => typeof id !== 'string' || !validTraceId(id)) ||
        new Set(row.active_traces).size !== row.active_traces.length ||
        typeof row.last_received_at !== 'string' || !Number.isFinite(Date.parse(row.last_received_at)) ||
        !row.diagnostics) throw new ApiError('invalid')
    seen.add(row.instance_id)
    const age_ms = count(row.age_ms), active_spans = count(row.active_spans), sequence = count(row.sequence)
    if (!sequence || row.active_traces.length > active_spans ||
        row.state !== (age_ms >= 45000 ? 'stale' : 'reporting')) throw new ApiError('invalid')
    const diagnostics = Object.fromEntries(diagnosticNames.map(key => [key, count(row.diagnostics[key])])) as HealthInstance['diagnostics']
    if (diagnostics.accepted_spans !== diagnostics.exported_spans + diagnostics.failed_spans + diagnostics.pending_spans) throw new ApiError('invalid')
    return { ...row, age_ms, active_spans, sequence, diagnostics, health_failures: count(row.health_failures) }
  })
  return { items, evicted_instances: count(v.evicted_instances), stale_after_ms: 45000, scope: v.scope }
}

export function heartbeatState(row: HealthInstance, elapsedMs: number): string {
  return row.age_ms + Math.max(0, elapsedMs) >= 45000 ? '心跳中断' : '心跳正常'
}
