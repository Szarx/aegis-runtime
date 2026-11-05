import type { TreeRow } from './domain'
export type NodeFilter = 'all' | 'error' | 'invoke_agent' | 'chat' | 'execute_tool'
export function filterTraceRows(rows: readonly TreeRow[], filter: NodeFilter, query: string): TreeRow[] {
  const needle = query.trim().toLowerCase()
  return rows.filter(({ span }) => (filter === 'all' || (filter === 'error' ? span.status === 'ERROR' : span.operation === filter)) &&
    (!needle || [span.name, span.service_name, span.span_id, span.parent_span_id ?? ''].some(value => value.toLowerCase().includes(needle))))
}
export function adjacentNode(rows: readonly TreeRow[], selected: string, key: string): string | undefined {
  if (!rows.length || !['ArrowUp','ArrowDown','Home','End'].includes(key)) return undefined
  const index = rows.findIndex(row => row.span.span_id === selected)
  const target = key === 'Home' ? 0 : key === 'End' ? rows.length - 1 : index < 0 ? 0 :
    Math.max(0,Math.min(rows.length - 1,index + (key === 'ArrowDown' ? 1 : -1)))
  return rows[target]?.span.span_id
}
