import type { Filters, Span } from './api/types'

export const validTraceId = (id: string): boolean => /^[0-9a-f]{32}$/.test(id) && /[1-9a-f]/.test(id)
export function statusLabel(status: string, outcome?: unknown): string {
  if (outcome === 'awaiting_approval') return '待审批快照'
  if (outcome === 'denied') return '已阻止'
  if (outcome === 'cancelled') return '已取消'
  if (status === 'ERROR') return '异常'
  if (outcome === 'closed') return '提前关闭'
  if (outcome === 'incomplete') return '不完整'
  return '已完成'
}
export const spanOutcome = (span: Span): string | bigint | undefined => ['aegis.governance.v1','aegis.governance.v2'].includes(String(span.attributes['aegis.mapping.version'])) ? span.attributes['aegis.action.outcome'] : span.attributes['aegis.graph.outcome'] ?? span.attributes['aegis.call.outcome']
export function decisionReason(reason: unknown): string {
  const labels: Record<string, string> = { explicit_require_approval: '策略要求人工审批', explicit_allow: '匹配允许规则', explicit_deny: '匹配拒绝规则', no_match: '无匹配规则，默认拒绝', identity_missing: '未绑定身份', permission_missing: '未声明权限', policy_unavailable: '策略不可用', policy_error: '策略求值失败' }
  return typeof reason === 'string' ? labels[reason] || reason : '未知'
}
export const operationLabel = (operation: string): string => operation === 'chat' ? 'LLM' : operation === 'invoke_agent' ? 'Agent' : 'Tool'
export const operationClass = (operation: string): string => operation === 'chat' ? 'llm' : operation === 'invoke_agent' ? 'agent' : 'tool'
export const operationSymbol = (operation: string): string => operation === 'chat' ? 'L' : operation === 'invoke_agent' ? 'A' : 'T'
export const displayName = (name: string): string => name.replace(/^(invoke_agent|execute_tool|chat) /, '')
export const tokenLabel = (value: unknown): string => typeof value === 'bigint' ? value.toString() : '未知'
export const spanColor = (span: Span): string => span.status === 'ERROR' ? '#ed897c' : spanOutcome(span) === 'awaiting_approval' ? '#d4ba78' : span.operation === 'chat' ? '#d4ba78' : span.operation === 'invoke_agent' ? '#b5a1e3' : '#75c6b4'
export function formatDuration(ns: bigint): string {
  for (const [scale, unit] of [[1000000000n, 's'], [1000000n, 'ms'], [1000n, 'µs']] as const) {
    if (ns >= scale) {
      const decimals = ((ns % scale) * 1000n / scale).toString().padStart(3, '0').replace(/0+$/, '')
      return `${ns / scale}${decimals ? '.' + decimals : ''} ${unit}`
    }
  }
  return `${ns} ns`
}
export function formatDate(ns: bigint): string {
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(Number(ns / 1000000n)))
}
export function exactDate(ns: bigint): string { return new Date(Number(ns / 1000000n)).toISOString() }
export function relativeMillis(ns: bigint, origin: bigint): number { return Number(ns - origin) / 1000000 }

export interface TreeRow { span: Span; depth: number; relation: 'normal' | 'missing' | 'cycle' }
export function buildTree(spans: Span[]): TreeRow[] {
  const byId = new Map(spans.map(span => [span.span_id, span]))
  const children = new Map<string, Span[]>()
  for (const span of spans) {
    if (span.parent_span_id && byId.has(span.parent_span_id)) {
      const siblings = children.get(span.parent_span_id) || []
      siblings.push(span); children.set(span.parent_span_id, siblings)
    }
  }
  const rows: TreeRow[] = [], visited = new Set<string>()
  const visit = (root: Span, relation: TreeRow['relation']) => {
    const stack: TreeRow[] = [{ span: root, depth: 0, relation }]
    while (stack.length) {
      const row = stack.pop()!
      if (visited.has(row.span.span_id)) continue
      visited.add(row.span.span_id); rows.push(row)
      for (const child of [...(children.get(row.span.span_id) || [])].reverse()) stack.push({ span: child, depth: row.depth + 1, relation: 'normal' })
    }
  }
  for (const span of spans) if (!span.parent_span_id || !byId.has(span.parent_span_id)) visit(span, span.parent_span_id ? 'missing' : 'normal')
  for (const span of spans) if (!visited.has(span.span_id)) visit(span, 'cycle')
  return rows
}

export function listPath(filters: Filters, offset: number): string {
  const params = new URLSearchParams({ limit: '20', offset: String(offset) })
  if (offset < 0 || offset > 10000 || !Number.isInteger(offset)) throw new Error('页码超出范围。')
  for (const [key, value] of [['agent_name', filters.agent], ['service_name', filters.service], ['status', filters.status]]) if (value) params.set(key!, value!)
  let after: bigint | undefined, before: bigint | undefined
  for (const [key, value] of [['started_after_ns', filters.after], ['started_before_ns', filters.before]]) {
    if (!value) continue
    const ms = new Date(value).getTime()
    if (!Number.isSafeInteger(ms) || ms <= 0) throw new Error('请选择有效的开始时间范围。')
    const ns = BigInt(ms) * 1000000n
    if (ns > 9223372036854775807n) throw new Error('时间超出支持范围。')
    params.set(key!, ns.toString())
    if (key === 'started_after_ns') after = ns; else before = ns
  }
  if (after !== undefined && before !== undefined && after > before) throw new Error('结束边界不能早于开始边界。')
  return '/api/v1/traces?' + params.toString()
}
