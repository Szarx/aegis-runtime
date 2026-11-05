import type { Approval } from './api/approvals'

export type QueueStatus = '' | Approval['status']
export type QueueOrder = 'received' | 'pending' | 'expires'

export function sortReviewPage(items: readonly Approval[], order: QueueOrder): Approval[] {
  const rows = [...items]
  if (order === 'received') return rows
  if (!['pending','expires'].includes(order) || rows.some(item => !Number.isFinite(Date.parse(item.expires_at)))) throw new Error('Invalid review page sort')
  return rows.sort((a,b) => (order === 'pending' ? Number(b.status === 'pending') - Number(a.status === 'pending') : 0) ||
    Date.parse(a.expires_at) - Date.parse(b.expires_at) || (a.action_id < b.action_id ? -1 : a.action_id > b.action_id ? 1 : 0))
}
/** Current loaded page only. Never substitutes for a server-wide query. */
export function filterReviewPage(items: readonly Approval[], status: QueueStatus, query: string): Approval[] {
  const needle = query.trim().toLocaleLowerCase()
  return items.filter(item => (!status || item.status === status) && (!needle ||
    [item.summary, item.subject, item.tool, item.permission, item.action_id].some(value => value.toLocaleLowerCase().includes(needle))))
}
export function reviewPageCounts(items: readonly Approval[]) {
  return { total: items.length, pending: items.filter(item => item.status === 'pending').length,
    approved: items.filter(item => item.status === 'approved').length, rejected: items.filter(item => item.status === 'rejected').length,
    expired: items.filter(item => item.status === 'expired').length }
}
