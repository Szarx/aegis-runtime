import { expect, it } from 'vitest'
import { adjacentNode, filterTraceRows } from '../src/traceExplorer'
import type { Span } from '../src/api/types'
import type { TreeRow } from '../src/domain'
const row = (id: string, operation: Span['operation'], status: Span['status'], depth: number): TreeRow => ({depth,relation:'normal',
  span:{span_id:id, parent_span_id:depth ? 'root' : null, name:operation+' customer',service_name:'orders',operation,status} as Span})
const rows=[row('root','invoke_agent','UNSET',0),row('model','chat','UNSET',2),row('tool','execute_tool','ERROR',3)]
it('intersects case-insensitive node lookup with operation or error without changing depth or references', () => {
  const result=filterTraceRows(rows,'execute_tool','ORDERS')
  expect(result).toEqual([rows[2]]);expect(result[0]).toBe(rows[2]);expect(result[0]?.depth).toBe(3)
  expect(filterTraceRows(rows,'error','customer')).toEqual([rows[2]])
  expect(filterTraceRows(rows,'chat','tool')).toEqual([])
})
it('searches node IDs and parent IDs, preserving original order and empty results', () => {
  expect(filterTraceRows(rows,'all','root')).toEqual(rows)
  expect(filterTraceRows(rows,'all','model')).toEqual([rows[1]])
  expect(filterTraceRows(rows,'all','absent')).toEqual([])
  const result=filterTraceRows(rows,'all',' ');result.pop();expect(rows).toHaveLength(3)
})
it('moves only within visible rows and clamps at boundaries without wrapping', () => {
  expect(adjacentNode(rows,'root','ArrowDown')).toBe('model')
  expect(adjacentNode(rows,'root','ArrowUp')).toBe('root')
  expect(adjacentNode(rows,'tool','ArrowDown')).toBe('tool')
  expect(adjacentNode(rows,'model','Home')).toBe('root');expect(adjacentNode(rows,'model','End')).toBe('tool')
  expect(adjacentNode([rows[2]!],'root','ArrowDown')).toBe('tool')
})
it('ignores unrelated keys and empty views without inventing selection', () => {
  expect(adjacentNode(rows,'root','Enter')).toBeUndefined()
  expect(adjacentNode([],'root','End')).toBeUndefined()
})
