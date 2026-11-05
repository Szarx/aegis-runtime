import { describe, expect, it, vi } from 'vitest'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { stringify } from 'lossless-json'
import { decodeSecurity, securityPath, emptySecurityFilters, type SecurityEvent } from '../src/api/security'
import { QueryChannel } from '../src/api/client'
import SecurityTable from '../src/components/SecurityTable.vue'

function event(): SecurityEvent {
  return { trace_id:'1'.repeat(32),span_id:'2'.repeat(16),action_id:'3'.repeat(32),tool:'lookup',subject:null,permission:null,policy_revision:null,rule_id:null,effect:'deny',reason:'identity_missing',outcome:'denied',service_name:'synthetic',agent_name:null,status:'ERROR',start_time_unix_nano:1790000000000000101n,end_time_unix_nano:1790000000000000102n }
}
function wire(e = event()) { return stringify({items:[e],total:1,limit:20,offset:0})! }
const render = (props: Record<string,unknown>) => renderToString(createSSRApp(SecurityTable,{busy:false,error:'',offset:0,...props}))

describe('AC2003 security explorer', () => {
  it('decodes exact nanoseconds and preserves nullable missing configuration', () => {
    const result=decodeSecurity(wire()); expect(result.items[0]!.start_time_unix_nano).toBe(1790000000000000101n)
    expect(result.items[0]!.subject).toBeNull(); expect(result.total).toBe(1)
  })
  it('rejects bad IDs, states, timestamps, arbitrary fields and duplicate events', () => {
    for (const change of [{trace_id:'0'.repeat(32)},{action_id:'<script>'},{effect:'allow'},{outcome:'completed'},{start_time_unix_nano:'1790000000000000101'},{permission:'*'},{arguments:'private-body'},{end_time_unix_nano:0n},{subject:'fake-identity'},{rule_id:'fake-rule'}]) {
      expect(() => decodeSecurity(wire({...event(),...change} as SecurityEvent))).toThrow('格式')
    }
    expect(() => decodeSecurity(stringify({items:[event(),event()],total:2,limit:20,offset:0})!)).toThrow('格式')
    expect(() => decodeSecurity('{"items":[],"total":-1,"limit":20,"offset":0}')).toThrow('格式')
  })
  it('encodes all filters and validates bounds and time intervals before requesting', () => {
    const filters={...emptySecurityFilters(),subject:'reader',tool:'lookup',permission:'orders.read',effect:'deny',outcome:'denied',service_name:'service & x',action_id:'1'.repeat(32),trace_id:'2'.repeat(32),after:'2026-10-23T10:00',before:'2026-10-23T11:00'}
    const params=new URL('http://local'+securityPath(filters,20)).searchParams
    expect(params.get('service_name')).toBe('service & x');expect(params.get('offset')).toBe('20');expect(params.get('started_after_ns')).toMatch(/^\d+$/)
    for (const changed of [{subject:'*'},{trace_id:'0'.repeat(32)},{effect:'invalid'},{outcome:'unknown'},{service_name:'\n'},{after:'bad'},{after:'2026-10-24',before:'2026-10-23'}]) expect(() => securityPath({...filters,...changed},0)).toThrow()
    expect(() => securityPath(filters,10001)).toThrow()
  })
  it('suppresses stale event pages and sends only Trace credential in header', async () => {
    const pending: ((r:Response)=>void)[]=[]
    const fetcher=vi.fn((_path:string,_options?:RequestInit)=>new Promise<Response>(resolve=>pending.push(resolve)))
    const channel=new QueryChannel(fetcher as typeof fetch);const commit=vi.fn()
    const first=channel.run(securityPath(emptySecurityFilters(),0),'synthetic-trace',decodeSecurity,commit)
    const second=channel.run(securityPath(emptySecurityFilters(),20),'synthetic-trace',decodeSecurity,commit)
    pending[1]!(new Response(wire()));expect(await second).toBe(true)
    pending[0]!(new Response(wire()));expect(await first).toBe(false);expect(commit).toHaveBeenCalledTimes(1)
    expect(fetcher.mock.calls[0]![0]).not.toContain('synthetic-trace')
    expect(fetcher.mock.calls[0]![1]!.headers).toEqual({Authorization:'Bearer synthetic-trace'})
    expect(fetcher.mock.calls[0]![1]!.cache).toBe('no-store')
  })
  it('cancels leaving the page and keeps server errors free of response bodies', async () => {
    let resolve!: (r:Response)=>void;const commit=vi.fn()
    const channel=new QueryChannel((()=>new Promise<Response>(r=>{resolve=r})) as typeof fetch)
    const query=channel.run('/api/v1/security-events','',decodeSecurity,commit);channel.cancel();resolve(new Response(wire()))
    expect(await query).toBe(false);expect(commit).not.toHaveBeenCalled()
    for (const status of [401,503]) {
      const failed=new QueryChannel((async()=>new Response('private-server-body',{status})) as typeof fetch)
      await expect(failed.run('/api/v1/security-events','',decodeSecurity,commit)).rejects.not.toThrow('private-server-body')
    }
  })
  it('renders missing configuration, decisions and validated Trace association as plain text', async () => {
    const e=event();e.service_name='<script>synthetic</script>'
    const html=await render({listing:{items:[e],total:1,limit:20,offset:0}})
    expect(html).toContain('未绑定身份');expect(html).toContain('未声明权限');expect(html).toContain('策略不可用');expect(html).toContain('已阻止')
    expect(html).toContain('#/traces/'+'1'.repeat(32));expect(html).toContain('&lt;script&gt;');expect(html).not.toContain('<script>')
    expect(html).not.toContain('批准');expect(html).not.toContain('恢复执行')
  })
  it('renders loading, empty, error/retry and bounded pagination states', async () => {
    expect(await render({busy:true})).toContain('正在查询安全事件')
    expect(await render({listing:{items:[],total:0,limit:20,offset:0}})).toContain('没有匹配的治理事件')
    expect(await render({error:'认证失败'})).toContain('重试')
    const html=await render({listing:{items:[event()],total:21,limit:20,offset:20},offset:20})
    expect(html).toContain('第 2 页');expect(html).toMatch(/disabled[^>]*aria-label="下一页事件"|aria-label="下一页事件"[^>]*disabled/)
  })
  it('distinguishes allowed business errors/cancellations from denied attempts', async () => {
    for (const outcome of ['error','cancelled','completed'] as const) {
      const e={...event(),subject:'reader',permission:'orders.read',policy_revision:'v1',rule_id:'allow',effect:'allow' as const,reason:'explicit_allow',outcome,status:outcome==='completed'?'UNSET' as const:'ERROR' as const}
      const list=decodeSecurity(wire(e));const html=await render({listing:list})
      expect(html).toContain('已允许');expect(html).toContain(outcome);expect(html).not.toContain('已阻止')
    }
  })
})
