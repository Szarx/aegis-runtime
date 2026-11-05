import { expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
const css=readFileSync(new URL('../src/style.css',import.meta.url),'utf8')
const tokens=Object.fromEntries([...css.matchAll(/--([\w-]+):\s*(#[\da-f]{6})/gi)].map(match=>[match[1],match[2]!]))
function luminance(hex: string) {
  const rgb=[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255).map(c=>c<=0.04045?c/12.92:((c+0.055)/1.055)**2.4)
  return rgb[0]!*0.2126+rgb[1]!*0.7152+rgb[2]!*0.0722
}
function ratio(a:string,b:string) {const x=luminance(a),y=luminance(b);return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05)}
it('calibrates relative luminance against black/white and equal colors',()=>{
  expect(ratio('#000000','#ffffff')).toBeCloseTo(21,6);expect(ratio('#ffffff','#ffffff')).toBe(1)
})
it('keeps the actual shipped neutral text tokens readable on declared workspace surfaces',()=>{
  for(const foreground of ['text-primary','text-muted','text-subtle']) for(const background of ['canvas','surface','surface-subtle','surface-hover']) {
    expect(tokens[foreground]).toBeDefined();expect(tokens[background]).toBeDefined()
    expect(ratio(tokens[foreground]!,tokens[background]!)).toBeGreaterThanOrEqual(4.5)
  }
})
it('keeps semantic state text readable and the focus accent distinguishable',()=>{
  for(const state of ['success','error','warning']) expect(ratio(tokens[state+'-text']!,tokens[state+'-bg']!)).toBeGreaterThanOrEqual(4.5)
  expect(ratio(tokens.accent!,tokens.canvas!)).toBeGreaterThanOrEqual(3)
})
