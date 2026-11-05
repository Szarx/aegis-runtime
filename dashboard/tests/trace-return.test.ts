import { describe, expect, it } from 'vitest'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { emptyFilters, type TraceDetail as Detail } from '../src/api/types'
import { emptySecurityFilters, type SecurityList } from '../src/api/security'
import { queryHash } from '../src/queryLocation'
import { readTraceLocation, traceChanged, traceHash, traceNodeLink, traceReturn } from '../src/traceLocation'
import SecurityTable from '../src/components/SecurityTable.vue'
import TraceDetail from '../src/views/TraceDetail.vue'

const trace='1'.repeat(32), span='2'.repeat(16)
const source=queryHash('security-events',{...emptySecurityFilters(),tool:'write_record',after:'2026-10-25T04:34:56.123Z'},20)
const detail: Detail={trace:{trace_id:trace,start_time_unix_nano:1n,end_time_unix_nano:2n,duration_ns:1n,span_count:1,status:'UNSET',agent_names:[]},spans:[{trace_id:trace,span_id:span,parent_span_id:null,name:'invoke_agent synthetic',operation:'invoke_agent',kind:'INTERNAL',status:'UNSET',service_name:'synthetic',agent_name:null,start_time_unix_nano:1n,end_time_unix_nano:2n,attributes:{},resource:{},scope:{},events:[]}],missing_parent_ids:[]}

describe('AC4401–4404 trace source return',()=>{
  it('roundtrips both sources with exact time/page while preserving legacy addresses',()=>{
    for (const origin of [source,queryHash('traces',{...emptyFilters(),agent:'测试 Agent'},20)]) {
      expect(readTraceLocation(traceHash(trace,span,origin))).toEqual({traceId:trace,spanId:span,returnTo:origin})
      expect(readTraceLocation(traceHash(trace,undefined,origin))).toEqual({traceId:trace,returnTo:origin})
    }
    expect(readTraceLocation(traceHash(trace,span))).toEqual({traceId:trace,spanId:span})
    expect(traceReturn()).toEqual({href:'#/traces',label:'返回执行追踪'})
    expect(traceReturn(source)).toEqual({href:source,label:'返回安全事件'})
  })
  it('canonicalizes allowed list state and rejects external, nested, credential and approval destinations',()=>{
    expect(readTraceLocation('#/traces/'+trace+'?return='+encodeURIComponent('#/traces?offset=20&agent=test'))?.returnTo).toBe('#/traces?agent=test&offset=20')
    for (const origin of ['https://outside.example/','//outside.example/','#/approvals','#/reviewed-actions',traceHash(trace),'#/traces?token=private','#/traces?offset=1','#/traces?agent=x&agent=y','#/security-events?effect=invalid']) {
      expect(readTraceLocation('#/traces/'+trace+'?return='+encodeURIComponent(origin))).toBeNull()
      expect(()=>traceHash(trace,span,origin)).toThrow()
    }
  })
  it('rejects malformed outer fields, duplicate return, encoded IDs and oversized addresses',()=>{
    const valid=traceHash(trace,span,source)
    for (const hash of [valid+'&return='+encodeURIComponent(source),valid+'&token=private',valid+'&span='+span,'#/traces/'+trace+'?return=%ZZ','#/traces/'+trace+'?return=',valid.replace('span='+span,'span=%32'+span.slice(1)),valid+'&'+'x'.repeat(16384)]) expect(readTraceLocation(hash)).toBeNull()
  })
  it('keeps the request identity stable on source or node changes and omits source from independent node copy',()=>{
    const previous=traceHash(trace,span,source)
    expect(traceChanged(previous,traceHash(trace,'3'.repeat(16),source))).toBe(false)
    expect(traceChanged(previous,traceHash(trace,span,'#/traces'))).toBe(false)
    expect(traceChanged(previous,traceHash('4'.repeat(32),span,source))).toBe(true)
    const copy=traceNodeLink('https://user:private@dashboard.example/?token=private'+previous,trace,span)
    expect(copy).toBe('https://dashboard.example/'+traceHash(trace,span));expect(copy).not.toMatch(/return|write_record|private/)
  })
  it('renders event links to the exact event node with the applied source and no implicit decisions',async()=>{
    const listing: SecurityList={total:1,limit:20,offset:0,items:[{trace_id:trace,span_id:span,action_id:'3'.repeat(32),tool:'read',subject:null,permission:null,policy_revision:null,rule_id:null,effect:'deny',reason:'identity_missing',outcome:'denied',service_name:'synthetic',agent_name:null,status:'ERROR',start_time_unix_nano:1n,end_time_unix_nano:2n}]}
    const html=await renderToString(createSSRApp(SecurityTable,{listing,busy:false,error:'',offset:0,returnTo:source}))
    expect(html).toContain(traceHash(trace,span,source).replaceAll('&','&amp;'))
    expect(html).not.toMatch(/批准本次动作|记录批准|领取/)
  })
  it('renders an explicit source return in the detail while keeping the old default',async()=>{
    const html=await renderToString(createSSRApp(TraceDetail,{detail,returnTo:source}))
    expect(html).toContain('返回安全事件');expect(html).toContain('href="'+source.replaceAll('&','&amp;')+'"')
    const original=await renderToString(createSSRApp(TraceDetail,{detail}))
    expect(original).toContain('href="#/traces"');expect(original).toContain('返回执行追踪')
  })
})
