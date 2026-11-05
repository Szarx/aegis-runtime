import { expect, it, vi } from 'vitest'
import { ApprovalChannel, ApprovalError, decodeReviewed, executionLabels, isReviewed, reviewText } from '../src/api/approvals'
const base = { action_id: '1'.repeat(32), subject: 'agent', tool: 'write', permission: 'records.write', policy_revision: 'r1', policy_digest: 'a'.repeat(64), arguments_hmac: 'b'.repeat(64), summary: 'Synthetic only', ttl_seconds: 300, trace_id: null, span_id: null, status: 'pending', created_at: '2026-10-20T00:00:00Z', expires_at: '2026-10-20T00:05:00Z', decided_at: null, reviewer: null, tool_revision: 'impl-v1', review_arguments: { record: 'demo', value: true }, review_digest: 'c'.repeat(64), execution_state: 'available', claim_id: null, executor: null, claimed_at: null, finished_at: null }
const listing = (item: unknown = base) => JSON.stringify({ items: [item], total: 1, limit: 20, offset: 0 })

it('preserves all signed 64-bit arguments and their JSON types during review', () => {
  const raw = listing().replace('"value":true', '"value":9223372036854775807,"minimum":-9223372036854775808,"text":"9223372036854775807"')
  const item = decodeReviewed(raw).items[0]!
  expect(isReviewed(item)).toBe(true)
  if (!isReviewed(item)) throw new Error('expected reviewed action')
  expect(item.review_arguments.value).toBe(9223372036854775807n)
  const shown = reviewText(item.review_arguments)
  expect(shown).toContain('"value": 9223372036854775807')
  expect(shown).toContain('"minimum": -9223372036854775808')
  expect(shown).toContain('"text": "9223372036854775807"')
})

it('rejects invalid reviewed argument types, integer range and incomplete claim records', () => {
  for (const change of [{ execution_state: 'retry' }, { claim_id: '1'.repeat(32) }, { review_arguments: [] }, { review_digest: 'wrong' }, { tool_revision: 'bad revision' }, { execution_state: 'claimed' }]) {
    expect(() => decodeReviewed(listing({ ...base, ...change } as typeof base))).toThrow(ApprovalError)
  }
  expect(() => decodeReviewed(listing().replace('"value":true', '"value":1.1'))).toThrow(ApprovalError)
  expect(() => decodeReviewed(listing().replace('"value":true', '"value":9223372036854775808'))).toThrow(ApprovalError)
})

it('requires the displayed review digest and sends only reviewer decisions', async () => {
  const approved = { ...base, status: 'approved', reviewer: 'server-reviewer', decided_at: '2026-10-20T00:00:01Z' }
  const fetcher = vi.fn(async () => new Response(JSON.stringify(approved)))
  const channel = new ApprovalChannel(fetcher as typeof fetch, 5000, true)
  await expect(channel.run('review', 0, vi.fn(), { action: base.action_id, value: 'approved' })).rejects.toThrow(ApprovalError)
  expect(fetcher).not.toHaveBeenCalled()
  expect(await channel.run('review', 0, vi.fn(), { action: base.action_id, value: 'approved', reviewDigest: base.review_digest })).toBe(true)
  expect(fetcher).toHaveBeenCalledExactlyOnceWith(`/api/v1/reviewed-actions/${base.action_id}/decision`, expect.objectContaining({ method: 'POST', body: JSON.stringify({ decision: 'approved', review_digest: base.review_digest }), headers: { Authorization: 'Bearer review', 'Content-Type': 'application/json' } }))
  const corrupt = new ApprovalChannel(vi.fn(async () => new Response(JSON.stringify({ ...approved, review_digest: 'd'.repeat(64) }))) as typeof fetch, 5000, true)
  await expect(corrupt.run('review', 0, vi.fn(), { action: base.action_id, value: 'approved', reviewDigest: base.review_digest })).rejects.toThrow(ApprovalError)
})

it('labels consumed claims as unknown and never exposes a claim or execution operation', async () => {
  const record = { ...base, status: 'approved', reviewer: 'reviewer', decided_at: '2026-10-20T00:00:01Z', execution_state: 'claimed', claim_id: '2'.repeat(32), executor: 'executor', claimed_at: '2026-10-20T00:00:02Z' }
  const fetcher = vi.fn(async () => new Response(listing(record))), commit = vi.fn()
  const channel = new ApprovalChannel(fetcher as typeof fetch, 5000, true)
  expect(await channel.run('review', 0, commit)).toBe(true)
  expect(executionLabels.claimed).toContain('结果未知')
  expect(fetcher).toHaveBeenCalledExactlyOnceWith('/api/v1/reviewed-actions?limit=20&offset=0', expect.objectContaining({ method: 'GET' }))
  expect(commit).toHaveBeenCalledTimes(1)
})
