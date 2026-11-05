import { describe, expect, it } from 'vitest'
import { createSSRApp } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { readTraceLocation, traceChanged, traceHash, traceNodeLink } from '../src/traceLocation'
import CopyValue from '../src/components/CopyValue.vue'

const trace='1'.repeat(32),other='2'.repeat(32),span='3'.repeat(16)
describe('AC3901 trace node addresses',()=>{
  it('roundtrips old Trace addresses and exact nonzero Span addresses',()=>{
    expect(readTraceLocation(traceHash(trace))).toEqual({traceId:trace})
    expect(readTraceLocation(traceHash(trace,span))).toEqual({traceId:trace,spanId:span})
    expect(traceHash(trace,span)).toBe('#/traces/'+trace+'?span='+span)
  })
  it('rejects extra, duplicate, encoded, malformed and zero identifiers instead of forwarding them',()=>{
    for (const hash of ['#/traces/'+trace+'?span='+span+'&token=private','#/traces/'+trace+'?span='+span+'&span='+span,'#/traces/'+trace+'?span=%33'+span.slice(1),'#/traces/'+trace+'?span='+'0'.repeat(16),'#/traces/'+'0'.repeat(32),'#/traces/'+trace+'?span='+span.toUpperCase().replace('3','A'),'#/traces/'+trace+'?span=../tool','#/traces/'+trace+'?other=value','#/traces/'+trace+'/extra']) expect(readTraceLocation(hash)).toBeNull()
    expect(()=>traceHash(trace,'0'.repeat(16))).toThrow();expect(()=>traceHash('bad',span)).toThrow()
  })
  it('cleans credentials and original search/hash while retaining only the current page path and node',()=>{
    const link=traceNodeLink('https://name:synthetic-private-password@dashboard.example/workspace/?token=synthetic-private-token#/unrelated',trace,span)
    expect(link).toBe('https://dashboard.example/workspace/#/traces/'+trace+'?span='+span)
    expect(link).not.toMatch(/synthetic-private|name:|token=/)
    expect(()=>traceNodeLink('javascript:alert(1)',trace,span)).toThrow()
  })
  it('only changes query identity when the Trace changes or an existing detail address becomes invalid',()=>{
    expect(traceChanged(traceHash(trace),traceHash(trace,span))).toBe(false)
    expect(traceChanged(traceHash(trace,span),traceHash(trace,'4'.repeat(16)))).toBe(false)
    expect(traceChanged(traceHash(trace),traceHash(other))).toBe(true)
    expect(traceChanged('#/traces',traceHash(trace))).toBe(true)
    expect(traceChanged(traceHash(trace),'#/traces')).toBe(true)
    expect(traceChanged(traceHash(trace),traceHash(trace)+'?token=private')).toBe(true)
    expect(traceChanged('#/traces','#/security-events')).toBe(false)
  })
  it('renders an explicit link-copy action without expanding the long URL into the inspector',async()=>{
    const link=traceNodeLink('https://dashboard.example/',trace,span)
    const html=await renderToString(createSSRApp(CopyValue,{value:link,label:'节点链接',showValue:false,buttonText:'复制节点链接'}))
    expect(html).toContain('aria-label="复制 节点链接"');expect(html).toContain('复制节点链接')
    expect(html).not.toContain(link)
    const normal=await renderToString(createSSRApp(CopyValue,{value:span,label:'Span ID'}));expect(normal).toContain(span)
  })
})
