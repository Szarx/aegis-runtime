import { describe, expect, it } from 'vitest'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { decodeSecurity, emptySecurityFilters, securityPath } from '../src/api/security'
import { queryHash, readQueryLocation } from '../src/queryLocation'
import { securityPageFile } from '../src/securityPageExport'
import { rankCalls } from '../src/callDuration'
import { decisionReason, statusLabel } from '../src/domain'
import SecurityTable from '../src/components/SecurityTable.vue'
import TraceDetail from '../src/views/TraceDetail.vue'
import type { TraceDetail as Detail } from '../src/api/types'

const event={trace_id:'1'.repeat(32),span_id:'2'.repeat(16),action_id:'3'.repeat(32),tool:'write',subject:'reviewer',permission:'records.write',policy_revision:'v2',rule_id:'review',effect:'require_approval',reason:'explicit_require_approval',outcome:'awaiting_approval',service_name:'synthetic',agent_name:null,status:'UNSET',start_time_unix_nano:1793000000000000000,end_time_unix_nano:1793000000000000000}
const raw=(row=event)=>JSON.stringify({items:[row],total:1,limit:20,offset:0})

describe('AC4504 policy approval projection',()=>{
  it('accepts the third decision only with a consistent outcome/status/reason/rule',()=>{
    expect(decodeSecurity(raw()).items[0]!.effect).toBe('require_approval')
    for (const change of [{reason:'explicit_allow'},{effect:'allow'},{status:'ERROR'},{rule_id:null},{outcome:'denied'}]) expect(()=>decodeSecurity(raw({...event,...change} as typeof event))).toThrow()
    expect(decodeSecurity(raw({...event,outcome:'error',status:'ERROR'})).items[0]!.outcome).toBe('error')
  })
  it('supports exact action, review decision and waiting snapshot queries without changing fields',()=>{
    const filters={...emptySecurityFilters(),action_id:event.action_id,effect:'require_approval',outcome:'awaiting_approval'}
    expect(securityPath(filters,0)).toContain('effect=require_approval')
    expect(readQueryLocation(queryHash('security-events',filters,0))?.filters).toEqual(filters)
    expect(decisionReason('explicit_require_approval')).toBe('策略要求人工审批')
    expect(statusLabel('UNSET','awaiting_approval')).toBe('待审批快照')
  })
  it('renders waiting as a policy requirement and exports its original state without promoting it to completed',async()=>{
    const listing=decodeSecurity(raw()), html=await renderToString(createSSRApp(SecurityTable,{listing,busy:false,error:'',offset:0}))
    expect(html).toContain('需人工审批');expect(html).toContain('待审批');expect(html).toContain('策略要求人工审批')
    const file=securityPageFile(listing,'jsonl')
    expect(file.body).toContain('"outcome":"awaiting_approval"');expect(file.body).toContain('"effect":"require_approval"')
  })
  it('explains request versus execution in the node inspector and retains policy rule/action linkage',async()=>{
    const listing=decodeSecurity(raw()), row=listing.items[0]!
    const attrs={'aegis.mapping.version':'aegis.governance.v2','aegis.approval.phase':'request','aegis.decision.effect':'require_approval','aegis.decision.reason':'explicit_require_approval','aegis.decision.rule_id':'review','aegis.action.id':row.action_id,'aegis.action.outcome':'awaiting_approval'}
    const detail: Detail={trace:{trace_id:row.trace_id,start_time_unix_nano:row.start_time_unix_nano,end_time_unix_nano:row.end_time_unix_nano,duration_ns:0n,span_count:1,status:'UNSET',agent_names:[]},spans:[{trace_id:row.trace_id,span_id:row.span_id,parent_span_id:null,name:'execute_tool write',operation:'execute_tool',kind:'INTERNAL',status:'UNSET',service_name:'synthetic',agent_name:null,start_time_unix_nano:row.start_time_unix_nano,end_time_unix_nano:row.end_time_unix_nano,attributes:attrs,resource:{},scope:{},events:[]}],missing_parent_ids:[]}
    expect(rankCalls(detail).total).toBe(0)
    const request=await renderToString(createSSRApp(TraceDetail,{detail}))
    expect(request).toContain('需人工审批');expect(request).toContain('Agent 返回不代表工具已执行');expect(request).toContain('本节点不执行工具');expect(request).toContain(row.action_id)
    attrs['aegis.approval.phase']='execute';attrs['aegis.action.outcome']='completed'
    expect(rankCalls(detail).total).toBe(1)
    const executed=await renderToString(createSSRApp(TraceDetail,{detail}))
    expect(executed).toContain('单次领取检查后的执行记录')
  })
})
