import { describe, expect, it } from 'vitest'
import { emptyFilters } from '../src/api/types'
import { emptySecurityFilters } from '../src/api/security'
import { applyQueryDraft, localTime, queryDraft, queryHash, queryLink, readQueryLocation } from '../src/queryLocation'

describe('AC4301 reproducible query addresses',()=>{
  it('roundtrips both lists, all allowed conditions and bounded page positions',()=>{
    for (const [page,filters] of [
      ['traces',{...emptyFilters(),agent:'订单 Agent',service:'service/a&b',status:'ERROR',after:'2026-10-28T01:02:03.123Z',before:'2026-10-29T01:02:03.123Z'}],
      ['security-events',{...emptySecurityFilters(),subject:'reader',tool:'read',permission:'records.read',service_name:'服务 A',effect:'deny',outcome:'denied',trace_id:'1'.repeat(32),action_id:'2'.repeat(32),after:'2026-10-28T01:02:03.123Z'}],
    ] as const) {
      for (const offset of [0,20,10000]) expect(readQueryLocation(queryHash(page,filters,offset))).toEqual({page,filters,offset})
    }
    expect(queryHash('traces',emptyFilters(),0)).toBe('#/traces')
    expect(readQueryLocation('#/security-events')).toEqual({page:'security-events',filters:emptySecurityFilters(),offset:0})
  })
  it('rejects unknown, duplicate, empty, malformed, overlong and invalid query parameters',()=>{
    for (const query of ['token=private','agent=a&agent=b','agent=','offset=1','offset=-20','offset=10020','offset=020','offset=2e1','status=bad','agent=%ZZ','agent=%FF','agent=%00','after=2026-10-28T00:00','after=2026-02-30T00:00:00.000Z','agent='+'a'.repeat(129)]) expect(readQueryLocation('#/traces?'+query)).toBeNull()
    for (const query of ['subject=bad%20id','trace_id='+'0'.repeat(32),'effect=maybe','offset=true']) expect(readQueryLocation('#/security-events?'+query)).toBeNull()
    expect(readQueryLocation('#/traces?')).toBeNull();expect(readQueryLocation('#/traces/'+'1'.repeat(32))).toBeNull()
    expect(readQueryLocation('#/approvals')).toBeNull()
    expect(()=>queryHash('traces',{...emptyFilters(),agent:'\n'},0)).toThrow()
  })
  it('keeps absolute UTC milliseconds through local drafts and unchanged reapplication',()=>{
    const filters={...emptyFilters(),after:'2026-11-01T06:30:00.123Z',before:'2026-11-02T07:00:00.999Z'}
    const draft=queryDraft(filters)
    expect(draft.after).toBe(localTime(filters.after));expect(draft.after).not.toContain('Z')
    expect(applyQueryDraft(draft,filters)).toEqual(filters)
    const changed=applyQueryDraft({...draft,after:'2026-11-01T09:00:00.123'},filters)
    const parsed=readQueryLocation(queryHash('traces',changed,20))!
    expect(parsed.filters.after).toBe(new Date(changed.after).toISOString())
    expect(parsed.filters.before).toBe(filters.before)
  })
  it('rejects reversed time boundaries rather than weakening the query',()=>{
    const filters={...emptyFilters(),after:'2026-10-29T00:00:00.000Z',before:'2026-10-28T00:00:00.000Z'}
    expect(()=>queryHash('traces',filters,0)).toThrow()
    expect(readQueryLocation('#/traces?after=2026-10-29T00%3A00%3A00.000Z&before=2026-10-28T00%3A00%3A00.000Z')).toBeNull()
  })
  it('copies only applied conditions and strips source credentials/search/hash',()=>{
    const applied={...emptyFilters(),agent:'published'},draft={...applied,agent:'unapplied'}
    const url=queryLink('https://user:private@dashboard.example/work/?token=private#/else','traces',applied,20)
    expect(url).toBe('https://dashboard.example/work/#/traces?agent=published&offset=20')
    expect(url).not.toContain(draft.agent);expect(url).not.toContain('private')
    expect(()=>queryLink('javascript:alert(1)','traces',applied,0)).toThrow()
  })
})
