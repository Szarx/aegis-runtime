export interface TraceSummary {
  trace_id: string
  start_time_unix_nano: bigint
  end_time_unix_nano: bigint
  duration_ns: bigint
  span_count: number
  status: 'UNSET' | 'ERROR'
  agent_names: string[]
  graph_outcome?: 'completed' | 'closed' | 'error' | 'cancelled' | null
}
export interface TraceList { items: TraceSummary[]; total: number; limit: number; offset: number }
export interface Span {
  trace_id: string
  span_id: string
  parent_span_id: string | null
  name: string
  operation: 'invoke_agent' | 'execute_tool' | 'chat'
  kind: 'INTERNAL' | 'CLIENT'
  status: 'UNSET' | 'ERROR'
  service_name: string
  agent_name: string | null
  start_time_unix_nano: bigint
  end_time_unix_nano: bigint
  attributes: Record<string, string | bigint>
  resource: Record<string, string>
  scope: Record<string, string>
  events: { name: string; time_unix_nano: bigint; attributes: Record<string, string> }[]
}
export interface TraceDetail { trace: TraceSummary; spans: Span[]; missing_parent_ids: string[] }
export interface Filters { agent: string; service: string; status: string; after: string; before: string }
export const emptyFilters = (): Filters => ({ agent: '', service: '', status: '', after: '', before: '' })
