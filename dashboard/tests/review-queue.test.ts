import { expect, it } from 'vitest'
import { filterReviewPage, sortReviewPage, reviewPageCounts } from '../src/reviewQueue'
import type { Approval } from '../src/api/approvals'
const item = (id: string, status: Approval['status'], summary: string): Approval => ({
  action_id: id.repeat(32), subject: 'demo-agent', tool: 'write', permission: 'records.write',
  summary, status, policy_revision: 'v1', policy_digest: 'a'.repeat(64), arguments_hmac: 'b'.repeat(64),
  ttl_seconds: 300, trace_id: null, span_id: null, created_at: '2026-10-26T00:00:00Z', expires_at: '2026-10-26T00:05:00Z',
  decided_at: status === 'pending' ? null : '2026-10-26T00:01:00Z', reviewer: status === 'pending' ? null : 'reviewer',
})
const items = [item('1','pending','Update order'),item('2','approved','合成订单'),item('3','rejected','Blocked'),item('4','expired','Expired')]
it('AC3801 keeps pending records first, orders within groups by deadline and never mutates the page',()=>{
  const later={...item('5','pending','later'),expires_at:'2026-10-26T00:06:00Z'}
  const expired={...items[3]!,expires_at:'2026-10-26T00:01:00Z'}
  const source=[expired,later,items[0]!,items[1]!],before=JSON.stringify(source)
  expect(sortReviewPage(source,'pending')).toEqual([items[0],later,expired,items[1]])
  expect(sortReviewPage(source,'expires')).toEqual([expired,items[0],items[1],later])
  expect(JSON.stringify(source)).toBe(before);expect(sortReviewPage(source,'received')).toEqual(source)
  expect(sortReviewPage(source,'received')).not.toBe(source)
})
it('AC3801 compares actual instants with deterministic Action ties instead of timestamp text',()=>{
  const first={...items[0]!,expires_at:'2026-10-26T00:05:00+00:00'}
  const second={...items[1]!,expires_at:'2026-10-26T00:05:00Z'}
  const earlier={...items[2]!,expires_at:'2026-10-26T00:04:59Z'}
  expect(sortReviewPage([second,first,earlier],'expires')).toEqual([earlier,first,second])
  expect(sortReviewPage([first,second,earlier],'expires')).toEqual([earlier,first,second])
  expect(()=>sortReviewPage([{...first,expires_at:'bad'}],'expires')).toThrow()
})
it('AC3801 sorts only supplied filtered records and leaves page counts independent',()=>{
  expect(sortReviewPage([], 'pending')).toEqual([])
  expect(sortReviewPage(filterReviewPage(items,'approved',''),'pending')).toEqual([items[1]])
  expect(reviewPageCounts(items)).toEqual({total:4,pending:1,approved:1,rejected:1,expired:1})
})
it('searches only the supplied page and intersects with status without changing order or records', () => {
  const before = JSON.stringify(items)
  expect(filterReviewPage(items, 'pending', ' update ')).toEqual([items[0]])
  expect(filterReviewPage(items, 'rejected', 'update')).toEqual([])
  expect(filterReviewPage(items, '', 'WRITE')).toEqual(items)
  expect(JSON.stringify(items)).toBe(before)
})
it('finds exact loaded action, Chinese summary, subject and permission without inspecting disclosed parameters', () => {
  for (const query of ['合成订单','2'.repeat(32)]) expect(filterReviewPage(items,'',query)).toEqual([items[1]])
  expect(filterReviewPage(items,'','demo-agent')).toEqual(items)
  expect(filterReviewPage(items,'','records.write')).toEqual(items)
  expect(filterReviewPage(items,'','not-on-this-page')).toEqual([])
})
it('counts the current page states independently of a filtered result or server total', () => {
  expect(reviewPageCounts(items)).toEqual({total:4,pending:1,approved:1,rejected:1,expired:1})
  expect(reviewPageCounts(filterReviewPage(items,'pending',''))).toEqual({total:1,pending:1,approved:0,rejected:0,expired:0})
})
it('handles empty pages and whitespace without mutating the original array', () => {
  expect(filterReviewPage([], '', '')).toEqual([])
  expect(reviewPageCounts([]).total).toBe(0)
  const result = filterReviewPage(items, '', '  ')
  result.pop();expect(items).toHaveLength(4)
})
