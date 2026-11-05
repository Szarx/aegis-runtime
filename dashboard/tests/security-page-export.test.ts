import { describe, expect, it } from 'vitest'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { parse } from 'lossless-json'
import { securityPageFile } from '../src/securityPageExport'
import { securityEventFields, type SecurityEvent, type SecurityList } from '../src/api/security'
import SecurityTable from '../src/components/SecurityTable.vue'

const event = (): SecurityEvent => ({trace_id:'1'.repeat(32),span_id:'2'.repeat(16),action_id:'3'.repeat(32),tool:'lookup',subject:null,permission:null,policy_revision:null,rule_id:null,effect:'deny',reason:'identity_missing',outcome:'denied',service_name:'synthetic',agent_name:null,status:'ERROR',start_time_unix_nano:9223372036854775806n,end_time_unix_nano:9223372036854775807n})
const page = (): SecurityList => ({items:[event()],total:21,limit:20,offset:20})
const now = new Date('2026-10-26T12:34:56.789Z')

describe('AC3601–3604 security page export', () => {
  it('keeps exact integers, nulls and row identity/order while excluding arbitrary extensions', () => {
    const first = {...event(),arguments:'synthetic-private-params',token:'synthetic-private-token'}
    const second = {...event(),span_id:'4'.repeat(16)}
    const file=securityPageFile({...page(),items:[first,second]},'jsonl',now)
    expect(file.filename).toBe('aegis-security-page-offset-20-count-2-2026-10-26T12-34-56-789Z.jsonl')
    expect(file.body).toContain('"end_time_unix_nano":9223372036854775807')
    expect(file.body).not.toMatch(/synthetic-private|arguments|token/)
    expect(file.body.endsWith('\n')).toBe(true)
    const rows=file.body.trimEnd().split('\n').map(line => parse(line,undefined,{parseNumber:value=>BigInt(value)}) as SecurityEvent)
    expect(rows).toHaveLength(2);expect(Object.keys(rows[0]!)).toEqual([...securityEventFields])
    expect(rows.map(row=>row.span_id)).toEqual([first.span_id,second.span_id])
    expect(rows[0]!.end_time_unix_nano).toBe(9223372036854775807n);expect(rows[0]!.subject).toBeNull()
    expect(rows[0]!.action_id).toBe(rows[1]!.action_id)
  })
  it('quotes CSV cell boundaries and guards ASCII/fullwidth formula prefixes and leading controls', () => {
    for (const input of ['=1+2','+1','-1','@SUM(A1)','＝1','＋1','－1','＠SUM(A1)',' \uFEFF =1','\tplain','\nplain','\rplain']) {
      const file=securityPageFile({...page(),items:[{...event(),service_name:input}]},'csv',now)
      expect(file.body).toContain('"\''+input+'"')
    }
    const file=securityPageFile({...page(),items:[{...event(),service_name:'中,"文"\n下一行'}]},'csv',now)
    expect(file.body).toContain('"中,""文""\n下一行"');expect(file.body.endsWith('\r\n')).toBe(true)
    expect(file.body.split('\r\n')[0]).toBe(securityEventFields.map(key=>'"'+key+'"').join(','))
    expect(file.body).toContain('"9223372036854775807"');expect(file.body).not.toContain('9.223')
  })
  it('refuses empty, inconsistent or out of contract pages before producing files', () => {
    for (const change of [{items:[]},{total:0},{offset:10001},{limit:0},{items:[{...event(),end_time_unix_nano:0n}]}]) {
      expect(()=>securityPageFile({...page(),...change},'jsonl',now)).toThrow()
    }
    expect(()=>securityPageFile(page(),'jsonl',new Date('bad'))).toThrow()
    expect(()=>securityPageFile(page(),'zip' as 'jsonl',now)).toThrow()
  })
  it('only enables explicit current-page downloads for successfully loaded nonempty records', async () => {
    const render=(props:Record<string,unknown>)=>renderToString(createSSRApp(SecurityTable,{busy:false,error:'',offset:20,...props}))
    for (const props of [{},{listing:page(),busy:true},{listing:page(),error:'认证失败'},{listing:{...page(),items:[]}}]) {
      const html=await render(props)
      expect(html).toMatch(/<button[^>]*disabled[^>]*>导出本页 JSONL/)
      expect(html).toMatch(/<button[^>]*disabled[^>]*>CSV/)
    }
    const html=await render({listing:page()})
    expect(html).not.toMatch(/<button[^>]*disabled[^>]*>导出本页 JSONL/)
    expect(html).toContain('仅导出本页已载入记录（1 条）');expect(html).toContain('精确保留纳秒请选 JSONL')
  })
})
