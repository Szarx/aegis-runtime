export interface Approval {
  action_id: string; subject: string; tool: string; permission: string; policy_revision: string
  policy_digest: string; arguments_hmac: string; summary: string; ttl_seconds: number
  trace_id: string | null; span_id: string | null; status: 'pending' | 'approved' | 'rejected' | 'expired'
  created_at: string; expires_at: string; decided_at: string | null; reviewer: string | null
}
export interface ApprovalList { items: Approval[]; total: number; limit: number; offset: number }
export class ApprovalError extends Error {
  constructor() { super('审批请求未完成。请检查独立凭证与服务，并刷新确认当前状态。') }
}
const hex = (v: unknown, width: number): v is string => typeof v === 'string' && new RegExp(`^[0-9a-f]{${width}}$`).test(v) && !/^0+$/.test(v)
const identifier = (v: unknown): v is string => typeof v === 'string' && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(v)
const date = (v: unknown): v is string => typeof v === 'string' && /(?:Z|\+00:00)$/.test(v) && Number.isFinite(Date.parse(v))
export function approvalRecord(value: unknown): Approval {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ApprovalError()
  const v = value as Approval
  if (!hex(v.action_id, 32) || ![v.subject, v.tool, v.permission, v.policy_revision].every(identifier) ||
      ![v.policy_digest, v.arguments_hmac].every(x => typeof x === 'string' && /^[a-f0-9]{64}$/.test(x)) ||
      typeof v.summary !== 'string' || !v.summary.trim() || v.summary.length > 512 || /[\x00-\x1f]/.test(v.summary) ||
      !Number.isInteger(v.ttl_seconds) || v.ttl_seconds < 30 || v.ttl_seconds > 600 ||
      !['pending', 'approved', 'rejected', 'expired'].includes(v.status) || !date(v.created_at) || !date(v.expires_at) ||
      (Date.parse(v.expires_at) - Date.parse(v.created_at)) !== v.ttl_seconds * 1000 ||
      !((v.trace_id === null && v.span_id === null) || (hex(v.trace_id, 32) && hex(v.span_id, 16))) ||
      !((v.decided_at === null && v.reviewer === null) || (date(v.decided_at) && identifier(v.reviewer))) ||
      (v.status === 'pending' && v.decided_at !== null) || (['approved', 'rejected'].includes(v.status) && v.decided_at === null)) throw new ApprovalError()
  return v
}
export function decodeApprovals(raw: string): ApprovalList {
  try {
    const v = JSON.parse(raw)
    if (!v || !Array.isArray(v.items) || v.items.length > 100 || !Number.isSafeInteger(v.total) || v.total < 0 ||
        !Number.isInteger(v.limit) || v.limit < 1 || v.limit > 100 || !Number.isInteger(v.offset) || v.offset < 0 || v.offset > 10000 || v.items.length > v.limit) throw new ApprovalError()
    return { ...v, items: v.items.map(approvalRecord) }
  } catch { throw new ApprovalError() }
}

export interface ReviewedApproval extends Approval {
  tool_revision: string; review_arguments: Record<string, unknown>; review_digest: string
  execution_state: 'available' | 'claimed' | 'completed' | 'failed'
  claim_id: string | null; executor: string | null; claimed_at: string | null; finished_at: string | null
}
export function isReviewed(item: Approval): item is ReviewedApproval { return 'execution_state' in item }
export function reviewText(value: unknown): string { return stringify(value, null, 2) ?? '' }
export const executionLabels = { available: '尚未领取', claimed: '已领取 · 结果未知', completed: '已确认完成', failed: '已确认失败 · 不可重试' }
function reviewedRecord(value: unknown): ReviewedApproval {
  if (!value || typeof value !== 'object') throw new ApprovalError()
  const raw = value as Record<string, unknown>
  if (typeof raw.ttl_seconds !== 'bigint' || raw.ttl_seconds < 30n || raw.ttl_seconds > 600n) throw new ApprovalError()
  const v = { ...raw, ttl_seconds: Number(raw.ttl_seconds) } as unknown as ReviewedApproval
  approvalRecord(v)
  if (!identifier(v.tool_revision) || !/^[a-f0-9]{64}$/.test(v.review_digest) || !Object.hasOwn(executionLabels, v.execution_state) || !v.review_arguments || typeof v.review_arguments !== 'object' || Array.isArray(v.review_arguments)) throw new ApprovalError()
  function validate(value: unknown, depth = 0) {
    if (depth > 16) throw new ApprovalError()
    if (value === null || typeof value === 'boolean') return
    if (typeof value === 'bigint' && value >= -9223372036854775808n && value <= 9223372036854775807n) return
    if (typeof value === 'string' && Array.from(value).length <= 2048 && !value.includes('\0')) return
    if (value && typeof value === 'object' && Object.keys(value).length <= 128) {
      if (Array.isArray(value)) value.forEach(child => validate(child, depth + 1))
      else Object.entries(value).forEach(([key, child]) => { if (Array.from(key).length > 2048 || key.includes('\0')) throw new ApprovalError(); validate(child, depth + 1) })
      return
    }
    throw new ApprovalError()
  }
  validate(v.review_arguments)
  if (new TextEncoder().encode(stringify(v.review_arguments)).length > 4096) throw new ApprovalError()
  if (v.execution_state === 'available') {
    if ([v.claim_id, v.executor, v.claimed_at, v.finished_at].some(x => x !== null)) throw new ApprovalError()
  } else {
    if (!hex(v.claim_id, 32) || !identifier(v.executor) || !date(v.claimed_at) || Date.parse(v.claimed_at) < Date.parse(v.created_at) || Date.parse(v.claimed_at) >= Date.parse(v.expires_at)) throw new ApprovalError()
    if (v.execution_state === 'claimed' ? v.finished_at !== null : !date(v.finished_at) || Date.parse(v.finished_at) < Date.parse(v.claimed_at)) throw new ApprovalError()
  }
  return v
}
export function decodeReviewed(raw: string): ApprovalList {
  try {
    const v = decode(raw) as { items: unknown[]; total: bigint; limit: bigint; offset: bigint }
    if (!v || !Array.isArray(v.items) || v.items.length > 100 || typeof v.total !== 'bigint' || v.total < 0n || v.total > BigInt(Number.MAX_SAFE_INTEGER) || typeof v.limit !== 'bigint' || v.limit < 1n || v.limit > 100n || typeof v.offset !== 'bigint' || v.offset < 0n || v.offset > 10000n || BigInt(v.items.length) > v.limit) throw new ApprovalError()
    return { items: v.items.map(reviewedRecord), total: Number(v.total), limit: Number(v.limit), offset: Number(v.offset) }
  } catch { throw new ApprovalError() }
}

/** Independent reviewer channel. Never reads Trace credentials or browser storage. */
export class ApprovalChannel {
  private generation = 0
  private controller?: AbortController
  constructor(private fetcher: typeof fetch = (input, init) => fetch(input, init), private timeout = 5000, private reviewed = false) {}
  cancel() { this.generation++; this.controller?.abort() }
  async run(token: string, offset: number, commit: (list: ApprovalList) => void, decision?: { action: string; value: 'approved' | 'rejected'; reviewDigest?: string }): Promise<boolean> {
    if (!token || !Number.isInteger(offset) || offset < 0 || offset > 10000 || (decision && (!hex(decision.action, 32) || !['approved', 'rejected'].includes(decision.value)))) throw new ApprovalError()
    if (this.reviewed && decision && !/^[a-f0-9]{64}$/.test(decision.reviewDigest ?? '')) throw new ApprovalError()
    this.cancel()
    const generation = this.generation, controller = new AbortController()
    this.controller = controller
    let timeout = false
    const timer = setTimeout(() => { timeout = true; controller.abort() }, this.timeout)
    const root = this.reviewed ? '/api/v1/reviewed-actions' : '/api/v1/approvals'
    const path = decision ? `${root}/${decision.action}/decision` : `${root}?limit=20&offset=${offset}`
    try {
      const response = await this.fetcher(path, { method: decision ? 'POST' : 'GET', signal: controller.signal, credentials: 'omit', cache: 'no-store', redirect: 'error',
        headers: { Authorization: `Bearer ${token}`, ...(decision ? { 'Content-Type': 'application/json' } : {}) },
        ...(decision ? { body: JSON.stringify({ decision: decision.value, ...(this.reviewed ? { review_digest: decision.reviewDigest } : {}) }) } : {}) })
      if (generation !== this.generation) return false
      if (!response.ok) throw new ApprovalError()
      const raw = await response.text()
      if (generation !== this.generation) return false
      if (timeout || raw.length > 524288) throw new ApprovalError()
      if (decision) {
        const result = this.reviewed ? reviewedRecord(decode(raw)) : approvalRecord(JSON.parse(raw))
        if (result.action_id !== decision.action || result.status !== decision.value) throw new ApprovalError()
        if (this.reviewed && (!isReviewed(result) || result.review_digest !== decision.reviewDigest)) throw new ApprovalError()
      } else commit(this.reviewed ? decodeReviewed(raw) : decodeApprovals(raw))
      return true
    } catch (error) {
      if (generation !== this.generation) return false
      throw new ApprovalError()
    } finally { clearTimeout(timer) }
  }
}
import { stringify } from 'lossless-json'
import { decode } from './client'
