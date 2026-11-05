import { ApiError, decode } from './client'

export interface SecurityEvent {
  trace_id: string; span_id: string; action_id: string; tool: string; subject: string | null
  permission: string | null; policy_revision: string | null; rule_id: string | null
  effect: 'allow' | 'deny' | 'require_approval'; reason: string; outcome: 'denied' | 'completed' | 'error' | 'cancelled' | 'awaiting_approval'
  service_name: string; agent_name: string | null; status: 'UNSET' | 'ERROR'
  start_time_unix_nano: bigint; end_time_unix_nano: bigint
}
export interface SecurityList { items: SecurityEvent[]; total: number; limit: number; offset: number }
export interface SecurityFilters { subject: string; tool: string; permission: string; service_name: string; action_id: string; trace_id: string; effect: string; outcome: string; after: string; before: string }
export const emptySecurityFilters = (): SecurityFilters => ({ subject: '', tool: '', permission: '', service_name: '', action_id: '', trace_id: '', effect: '', outcome: '', after: '', before: '' })
const identifier = (v: unknown): v is string => typeof v === 'string' && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(v)
const hex = (v: unknown, width: number): v is string => typeof v === 'string' && new RegExp(`^[0-9a-f]{${width}}$`).test(v) && !/^0+$/.test(v)
const nano = (v: unknown): v is bigint => typeof v === 'bigint' && v > 0n && v <= 9223372036854775807n
export const securityEventFields = ['trace_id','span_id','action_id','tool','subject','permission','policy_revision','rule_id','effect','reason','outcome','service_name','agent_name','status','start_time_unix_nano','end_time_unix_nano'] as const
export function decodeSecurity(raw: string): SecurityList {
  try {
    const v = decode(raw) as { items: SecurityEvent[]; total: bigint; limit: bigint; offset: bigint }
    if (!v || !Array.isArray(v.items) || typeof v.total !== 'bigint' || v.total < 0n || v.total > BigInt(Number.MAX_SAFE_INTEGER) || typeof v.limit !== 'bigint' || v.limit < 1n || v.limit > 100n || typeof v.offset !== 'bigint' || v.offset < 0n || v.offset > 10000n || BigInt(v.items.length) > v.limit || BigInt(v.items.length) > v.total) throw new Error()
    const ids = new Set<string>()
    for (const e of v.items) {
      if (!e || Object.keys(e).length !== securityEventFields.length || !securityEventFields.every(key => Object.hasOwn(e, key)) || !hex(e.trace_id,32) || !hex(e.span_id,16) || !hex(e.action_id,32) || !identifier(e.tool) ||
          ![e.subject,e.permission,e.policy_revision,e.rule_id].every(x => x === null || identifier(x)) || typeof e.service_name !== 'string' || !e.service_name.trim() || e.service_name.length > 128 || (e.agent_name !== null && (typeof e.agent_name !== 'string' || e.agent_name.length > 128)) ||
          !nano(e.start_time_unix_nano) || !nano(e.end_time_unix_nano) || e.end_time_unix_nano < e.start_time_unix_nano) throw new Error()
      if (e.effect === 'require_approval') {
        if (e.reason !== 'explicit_require_approval' || !['awaiting_approval','completed','error','cancelled'].includes(e.outcome) || e.status !== (['completed','awaiting_approval'].includes(e.outcome) ? 'UNSET' : 'ERROR')) throw new Error()
      } else if (e.effect === 'deny' ? (e.outcome !== 'denied' || e.status !== 'ERROR' || !['explicit_deny','no_match','identity_missing','permission_missing','policy_unavailable','policy_error'].includes(e.reason)) :
          (e.effect !== 'allow' || e.reason !== 'explicit_allow' || !['completed','error','cancelled'].includes(e.outcome) || e.status !== (e.outcome === 'completed' ? 'UNSET' : 'ERROR'))) throw new Error()
      if ((e.reason === 'identity_missing') !== (e.subject === null) ||
          (e.reason === 'permission_missing' && e.permission !== null) ||
          (!['identity_missing','permission_missing'].includes(e.reason) && e.permission === null) ||
          (e.reason === 'policy_unavailable' && e.policy_revision !== null) ||
          (['explicit_allow','explicit_deny','explicit_require_approval','no_match','policy_error'].includes(e.reason) && e.policy_revision === null) ||
          (['explicit_allow','explicit_deny','explicit_require_approval'].includes(e.reason) !== (e.rule_id !== null))) throw new Error()
      const id = e.trace_id + e.span_id
      if (ids.has(id)) throw new Error()
      ids.add(id)
    }
    return { items: v.items, total: Number(v.total), limit: Number(v.limit), offset: Number(v.offset) }
  } catch { throw new ApiError('invalid') }
}
export function securityPath(filters: SecurityFilters, offset: number): string {
  if (!Number.isInteger(offset) || offset < 0 || offset > 10000) throw new Error('页码超出范围。')
  const params = new URLSearchParams({ limit: '20', offset: String(offset) })
  for (const key of ['subject','tool','permission'] as const) {
    if (filters[key] && !identifier(filters[key])) throw new Error('身份、工具和权限须为有效标识。')
    if (filters[key]) params.set(key,filters[key])
  }
  for (const key of ['action_id','trace_id'] as const) {
    if (filters[key] && !hex(filters[key],32)) throw new Error('Action / Trace ID须为非零32位小写十六进制。')
    if (filters[key]) params.set(key,filters[key])
  }
  if (filters.effect && !['allow','deny','require_approval'].includes(filters.effect) || filters.outcome && !['denied','completed','error','cancelled','awaiting_approval'].includes(filters.outcome)) throw new Error('无效的决策或结果。')
  if (filters.service_name && (filters.service_name.length > 128 || !filters.service_name.trim() || /[\x00-\x1f]/.test(filters.service_name))) throw new Error('无效的服务名称。')
  for (const key of ['service_name','effect','outcome'] as const) if (filters[key]) params.set(key,filters[key])
  let after: bigint | undefined, before: bigint | undefined
  for (const [key,value] of [['started_after_ns',filters.after],['started_before_ns',filters.before]]) {
    if (!value) continue
    const ms = new Date(value).getTime()
    if (!Number.isSafeInteger(ms) || ms <= 0) throw new Error('请选择有效的时间范围。')
    const ns = BigInt(ms) * 1000000n
    if (!nano(ns)) throw new Error('时间超出支持范围。')
    params.set(key!,ns.toString()); if (key === 'started_after_ns') after = ns; else before = ns
  }
  if (after !== undefined && before !== undefined && after > before) throw new Error('结束边界不能早于开始边界。')
  return '/api/v1/security-events?' + params.toString()
}
