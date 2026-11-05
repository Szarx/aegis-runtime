import { afterEach, expect, it, vi } from 'vitest'
import { ApprovalChannel, ApprovalError, decodeApprovals } from '../src/api/approvals'

const record = { action_id: '1'.repeat(32), subject: 'agent', tool: 'write', permission: 'records.write', policy_revision: 'r1', policy_digest: 'a'.repeat(64), arguments_hmac: 'b'.repeat(64), summary: 'Synthetic only', ttl_seconds: 300, trace_id: null, span_id: null, status: 'pending', created_at: '2026-10-18T00:00:00Z', expires_at: '2026-10-18T00:05:00Z', decided_at: null, reviewer: null }
const listing = JSON.stringify({ items: [record], total: 1, limit: 20, offset: 0 })
afterEach(() => vi.useRealTimers())

it('validates approval bindings, paired trace, expiry and explicit statuses', () => {
  expect(decodeApprovals(listing).items[0]).toEqual(record)
  for (const change of [{ action_id: '0'.repeat(32) }, { ttl_seconds: true }, { status: 'executed' }, { expires_at: 'bad' }, { trace_id: '1'.repeat(32) }, { reviewer: 'fake' }, { policy_digest: 'bad' }]) {
    expect(() => decodeApprovals(JSON.stringify({ items: [{ ...record, ...change }], total: 1, limit: 20, offset: 0 }))).toThrow(ApprovalError)
  }
})

it('uses only fixed same-origin routes and explicit independent reviewer credentials', async () => {
  const fetcher = vi.fn(async () => new Response(listing)), commit = vi.fn(), channel = new ApprovalChannel(fetcher as typeof fetch)
  expect(await channel.run('review-only', 0, commit)).toBe(true)
  expect(fetcher).toHaveBeenCalledExactlyOnceWith('/api/v1/approvals?limit=20&offset=0', expect.objectContaining({ method: 'GET', credentials: 'omit', redirect: 'error', cache: 'no-store', headers: { Authorization: 'Bearer review-only' } }))
  await expect(channel.run('', 0, commit)).rejects.toThrow(ApprovalError)
  await expect(channel.run('x', 10001, commit)).rejects.toThrow(ApprovalError)
  await expect(channel.run('x', 0, commit, { action: '../traces', value: 'approved' })).rejects.toThrow(ApprovalError)
  expect(fetcher).toHaveBeenCalledTimes(1)
})

it('discards late responses on disconnect and replacement including writes', async () => {
  const pending: ((response: Response) => void)[] = [], commit = vi.fn()
  const channel = new ApprovalChannel(vi.fn(() => new Promise<Response>(resolve => pending.push(resolve))) as typeof fetch)
  const old = channel.run('old-reviewer', 0, commit)
  const newer = channel.run('new-reviewer', 0, commit)
  pending[1]!(new Response(listing)); expect(await newer).toBe(true)
  pending[0]!(new Response(listing)); expect(await old).toBe(false)
  expect(commit).toHaveBeenCalledTimes(1)
  const write = channel.run('new-reviewer', 0, commit, { action: record.action_id, value: 'approved' })
  channel.cancel(); pending[2]!(new Response('private stale error', { status: 500 }))
  expect(await write).toBe(false); expect(commit).toHaveBeenCalledTimes(1)
})

it('posts only a decision, never retries uncertain writes and hides server details', async () => {
  const fetcher = vi.fn(async () => new Response('private detail', { status: 409 })), commit = vi.fn()
  const channel = new ApprovalChannel(fetcher as typeof fetch)
  await expect(channel.run('review', 0, commit, { action: record.action_id, value: 'approved' })).rejects.toThrow(ApprovalError)
  expect(fetcher).toHaveBeenCalledTimes(1); expect(commit).not.toHaveBeenCalled()
  expect(fetcher.mock.calls[0]).toEqual([`/api/v1/approvals/${record.action_id}/decision`, expect.objectContaining({ method: 'POST', body: '{"decision":"approved"}' })])
})

it('aborts at deadline without committing or retrying', async () => {
  vi.useFakeTimers()
  const fetcher = vi.fn((_path: string, options?: RequestInit) => new Promise<Response>((_, reject) => options?.signal?.addEventListener('abort', () => reject(new Error('private')))))
  const commit = vi.fn(), channel = new ApprovalChannel(fetcher as typeof fetch, 10)
  const check = expect(channel.run('review', 0, commit)).rejects.toThrow(ApprovalError)
  await vi.advanceTimersByTimeAsync(11); await check
  expect(fetcher).toHaveBeenCalledTimes(1); expect(commit).not.toHaveBeenCalled()
})
