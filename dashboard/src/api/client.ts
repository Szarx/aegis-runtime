import { parse } from 'lossless-json'
import type { Span, TraceDetail, TraceList, TraceSummary } from './types'

export class ApiError extends Error {
  constructor(public kind: 'auth' | 'missing' | 'network' | 'timeout' | 'invalid' | 'server') {
    super({ auth: '认证失败，请检查 Bearer token 后重新连接。', missing: '未找到这条 Trace，它可能尚未到达 Collector。', network: '无法连接 Collector，请检查服务后重试。', timeout: '请求超时，请稍后重试。', invalid: 'Collector 返回的数据格式不受支持。', server: 'Collector 暂时无法完成查询，请稍后重试。' }[kind])
  }
}

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ApiError('invalid')
  return value as Record<string, unknown>
}
function array(value: unknown): unknown[] { if (!Array.isArray(value)) throw new ApiError('invalid'); return value }
function text(value: unknown): string { if (typeof value !== 'string') throw new ApiError('invalid'); return value }
function integer(value: unknown, min = 0n): bigint {
  if (typeof value !== 'bigint' || value < min || value > 9223372036854775807n) throw new ApiError('invalid')
  return value
}
function count(value: unknown): number {
  const n = integer(value)
  if (n > BigInt(Number.MAX_SAFE_INTEGER)) throw new ApiError('invalid')
  return Number(n)
}
function dictionary(value: unknown): Record<string, string> {
  return Object.fromEntries(Object.entries(object(value)).map(([key, val]) => [key, text(val)]))
}
function spanAttributes(value: unknown): Record<string, string | bigint> {
  const tokens = new Set(['gen_ai.usage.input_tokens', 'gen_ai.usage.output_tokens'])
  return Object.fromEntries(Object.entries(object(value)).map(([key, val]) => [key, tokens.has(key) ? integer(val) : text(val)]))
}
function status(value: unknown): 'UNSET' | 'ERROR' {
  if (value !== 'UNSET' && value !== 'ERROR') throw new ApiError('invalid')
  return value
}
function summary(value: unknown): TraceSummary {
  const v = object(value)
  const outcome = v.graph_outcome
  if (outcome != null && outcome !== 'completed' && outcome !== 'closed' && outcome !== 'error' && outcome !== 'cancelled') throw new ApiError('invalid')
  return { trace_id: text(v.trace_id), start_time_unix_nano: integer(v.start_time_unix_nano, 1n), end_time_unix_nano: integer(v.end_time_unix_nano, 1n), duration_ns: integer(v.duration_ns), span_count: count(v.span_count), status: status(v.status), agent_names: array(v.agent_names).map(text), graph_outcome: outcome ?? null }
}
function span(value: unknown): Span {
  const v = object(value)
  if (v.operation !== 'invoke_agent' && v.operation !== 'execute_tool' && v.operation !== 'chat') throw new ApiError('invalid')
  const kind: Span['kind'] = v.operation === 'chat' ? 'CLIENT' : 'INTERNAL'
  if (v.kind !== kind) throw new ApiError('invalid')
  return {
    trace_id: text(v.trace_id), span_id: text(v.span_id), parent_span_id: v.parent_span_id === null ? null : text(v.parent_span_id), name: text(v.name), operation: v.operation, kind, status: status(v.status), service_name: text(v.service_name), agent_name: v.agent_name === null ? null : text(v.agent_name),
    start_time_unix_nano: integer(v.start_time_unix_nano, 1n), end_time_unix_nano: integer(v.end_time_unix_nano, 1n), attributes: spanAttributes(v.attributes), resource: dictionary(v.resource), scope: dictionary(v.scope),
    events: array(v.events).map(value => { const e = object(value); return { name: text(e.name), time_unix_nano: integer(e.time_unix_nano, 1n), attributes: dictionary(e.attributes) } }),
  }
}
export function decode(text: string): unknown {
  try {
    return parse(text, undefined, { parseNumber: value => { if (!/^-?\d+$/.test(value)) throw new ApiError('invalid'); return BigInt(value) } })
  } catch { throw new ApiError('invalid') }
}
export function decodeList(raw: string): TraceList {
  const v = object(decode(raw))
  return { items: array(v.items).map(summary), total: count(v.total), limit: count(v.limit), offset: count(v.offset) }
}
export function decodeDetail(raw: string): TraceDetail {
  const v = object(decode(raw))
  return { trace: summary(v.trace), spans: array(v.spans).map(span), missing_parent_ids: array(v.missing_parent_ids).map(text) }
}

/** Each channel has one active request. Replaced responses cannot commit state. */
export class QueryChannel {
  private controller?: AbortController
  private generation = 0
  constructor(private fetcher: typeof fetch = (input, init) => fetch(input, init), private timeout = 10000) {}
  cancel() { this.generation++; this.controller?.abort() }
  async run<T>(path: string, token: string, parser: (text: string) => T, commit: (value: T) => void): Promise<boolean> {
    if (!/^\/api\/v1\/(?:traces(?:\?|$|\/[0-9a-f]{32}$)|security-events(?:\?|$))/.test(path)) throw new ApiError('invalid')
    this.cancel()
    const generation = this.generation
    const controller = new AbortController()
    this.controller = controller
    let timedOut = false
    const timer = setTimeout(() => { timedOut = true; controller.abort() }, this.timeout)
    try {
      const response = await this.fetcher(path, { signal: controller.signal, cache: 'no-store', credentials: 'omit', redirect: 'error', headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (generation !== this.generation) return false
      if (!response.ok) throw new ApiError(response.status === 401 ? 'auth' : response.status === 404 ? 'missing' : 'server')
      const raw = await response.text()
      if (generation !== this.generation) return false
      if (timedOut) throw new ApiError('timeout')
      const value = parser(raw)
      commit(value)
      return true
    } catch (error) {
      if (generation !== this.generation) return false
      if (timedOut) throw new ApiError('timeout')
      throw error instanceof ApiError ? error : new ApiError('network')
    } finally { clearTimeout(timer) }
  }
}
