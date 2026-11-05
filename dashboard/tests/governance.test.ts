import { describe, expect, it } from 'vitest'
import { decisionReason, spanOutcome, statusLabel } from '../src/domain'
import type { Span } from '../src/api/types'

describe('tool authorization decisions', () => {
  it('distinguishes blocked attempts from completed calls and tool errors', () => {
    const span = { attributes: { 'aegis.mapping.version': 'aegis.governance.v1', 'aegis.action.outcome': 'denied' } } as unknown as Span
    expect(statusLabel('ERROR', spanOutcome(span))).toBe('已阻止')
    expect(statusLabel('ERROR', 'error')).toBe('异常')
    expect(statusLabel('UNSET', 'completed')).toBe('已完成')
  })
  it('does not treat an ungoverned permission label as authorization', () => {
    const span = { attributes: { 'aegis.mapping.version': 'aegis.genai.v1', 'aegis.action.outcome': 'denied', 'aegis.tool.permission': 'orders.read' } } as unknown as Span
    expect(spanOutcome(span)).toBeUndefined()
    expect(statusLabel('UNSET', spanOutcome(span))).toBe('已完成')
  })
  it('explains all fixed denial reasons and retains unknown metadata safely as text', () => {
    for (const reason of ['explicit_deny','no_match','identity_missing','permission_missing','policy_unavailable','policy_error']) {
      expect(decisionReason(reason)).not.toBe(reason)
    }
    expect(decisionReason('explicit_allow')).toBe('匹配允许规则')
    expect(decisionReason(undefined)).toBe('未知')
  })
})
