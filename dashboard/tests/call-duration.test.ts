import { describe, expect, it } from 'vitest'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
import type { Span, TraceDetail } from '../src/api/types'
import { rankCalls } from '../src/callDuration'
import CallDurationRank from '../src/components/CallDurationRank.vue'

const trace = '1'.repeat(32)
function call(id: number, duration: bigint, operation: Span['operation'] = 'chat'): Span {
  return { trace_id:trace, span_id:id.toString(16).padStart(16,'0'), parent_span_id:null, name:operation+' synthetic',
    operation, kind:operation === 'chat' ? 'CLIENT' : 'INTERNAL', status:'UNSET', service_name:'synthetic',agent_name:null,
    start_time_unix_nano:1n,end_time_unix_nano:1n+duration,attributes:{},resource:{},scope:{},events:[] }
}
function detail(spans: Span[], duration = 100n): TraceDetail {
  return {trace:{trace_id:trace,start_time_unix_nano:1n,end_time_unix_nano:1n+duration,duration_ns:duration,span_count:spans.length,status:'UNSET',agent_names:[]},spans,missing_parent_ids:[]}
}

describe('AC4001–4004 received call duration',()=>{
  it('sorts exact durations above safe Number precision with deterministic ties without mutating source records',()=>{
    const first=call(1,9007199254740992n),second=call(2,9007199254740993n),tie=call(3,9007199254740993n)
    const input=[tie,first,second],snapshot=input.map(span=>({...span}))
    const result=rankCalls(detail(input,9223372036854775806n))
    expect(result.rows.map(row=>row.span.span_id)).toEqual([second.span_id,tie.span_id,first.span_id])
    expect(result.rows[0]!.duration-result.rows[2]!.duration).toBe(1n)
    expect(result.rows[0]!.span).toBe(second);expect(input).toEqual(snapshot)
  })
  it('deduplicates the first received ID, excludes Agent/other traces and reports invalid times or IDs separately',()=>{
    const zero=call(1,0n),tool=call(2,3n,'execute_tool')
    const invalid=[{...call(3,0n),end_time_unix_nano:0n},{...call(4,1n),span_id:'0'.repeat(16)},{...call(5,1n),end_time_unix_nano:9223372036854775808n}]
    const result=rankCalls(detail([zero,{...zero,end_time_unix_nano:999n},tool,call(6,100n,'invoke_agent'),{...call(7,10n),trace_id:'2'.repeat(32)},...invalid]))
    expect(result.total).toBe(5);expect(result.invalid).toBe(3)
    expect(result.rows.map(row=>row.duration)).toEqual([3n,0n])
    expect(result.rows[1]!.span).toBe(zero)
  })
  it('distinguishes zero, unknown denominator, tiny positive ratios and over-100 percent without numeric overflow',()=>{
    const result=rankCalls(detail([call(1,0n),call(2,1n)],100000n))
    expect(result.rows[0]!.share).toBe('<0.01%');expect(result.rows[1]!.share).toBe('0.00%')
    expect(rankCalls(detail([call(1,0n)],0n)).rows[0]).toMatchObject({duration:0n,share:'未知',barWidth:0})
    expect(rankCalls(detail([call(1,150n)],100n)).rows[0]).toMatchObject({share:'150.00%',barWidth:100})
    const huge=rankCalls(detail([call(1,9223372036854775806n)],1n)).rows[0]!
    expect(huge.share).toBe('922337203685477580600.00%');expect(huge.barWidth).toBe(100)
  })
  it('bounds displayed rows to the longest 20 while retaining the total received count',()=>{
    const result=rankCalls(detail(Array.from({length:25},(_,index)=>call(index+1,BigInt(index)))))
    expect(result.total).toBe(25);expect(result.rows).toHaveLength(20)
    expect(result.rows[0]!.duration).toBe(24n);expect(result.rows[19]!.duration).toBe(5n)
  })
  it('renders native disclosure, exact zero, row-specific navigation, exclusions and honest empty states',async()=>{
    const render=(spans:Span[])=>renderToString(createSSRApp(CallDurationRank,{detail:detail(spans)}))
    const zero=call(1,0n,'execute_tool'),html=await render([zero])
    expect(html).toMatch(/<details[^>]*class="duration-rank"/);expect(html).not.toMatch(/<details[^>]*\bopen/)
    expect(html).toContain('title="0 ns"');expect(html).toContain('>0 ns</')
    expect(html).toContain('定位调用 execute_tool synthetic '+zero.span_id)
    expect(html).toContain('不能相加当总执行时间或关键路径')
    expect(await render([call(2,100n,'invoke_agent')])).toContain('暂无已接收的模型或工具调用')
    const bad=await render([{...zero,end_time_unix_nano:0n}])
    expect(bad).toContain('1 个调用的时间或 ID 无效');expect(bad).toContain('没有可排序的有效调用')
    expect(bad).not.toContain('定位调用')
  })
})
