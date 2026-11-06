import { describe, expect, it } from 'vitest'
import { decodeHealth, heartbeatState, diagnosticNames } from '../src/api/health'

const report = () => ({ instance_id: '1'.repeat(32), service_name: 'agent', sequence: 1, active_spans: 1,
  active_traces: ['2'.repeat(32)], activity_truncated: false, health_failures: 0, age_ms: 0,
  last_received_at: '2026-11-05T00:00:00Z', state: 'reporting',
  diagnostics: Object.fromEntries(diagnosticNames.map(key => [key, 0])) })
const raw = (row: unknown) => JSON.stringify({items: [row], evicted_instances: 0, stale_after_ms: 45000, scope: 'collector_process'})

describe('runtime health', () => {
  it('decodes only bounded consistent snapshots and ages a retained snapshot', () => {
    const row = decodeHealth(raw(report())).items[0]!
    expect(heartbeatState(row, 44999)).toBe('心跳正常')
    expect(heartbeatState(row, 45000)).toBe('心跳中断')
    for (const change of [{ active_spans: 0 }, { instance_id: '0'.repeat(32) }, { sequence: 0 },
      { state: 'stopped' }, { age_ms: 45000 }, { service_name: 'bad\nvalue' }]) {
      expect(() => decodeHealth(raw({ ...report(), ...change }))).toThrow()
    }
    expect(() => decodeHealth(raw({ ...report(), diagnostics: { ...report().diagnostics, accepted_spans: 1 } }))).toThrow()
  })
})
