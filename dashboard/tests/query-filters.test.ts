import { afterEach, describe, expect, it, vi } from 'vitest'
import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import QueryFilters from '../src/components/QueryFilters.vue'

const render=(activeCount:number)=>renderToString(createSSRApp({render:()=>h(QueryFilters,{title:'筛选事件',activeCount},{default:()=>h('form',null,[h('label',null,['工具',h('input',{value:'synthetic-draft'})])])})}))
afterEach(()=>vi.unstubAllGlobals())

describe('AC3701 query disclosure',()=>{
  it('defaults to expanded for SSR/desktop with an applied count and real labeled form',async()=>{
    const html=await render(2)
    expect(html).toMatch(/<details[^>]*open/);expect(html).toMatch(/<summary\b[^>]*>/)
    expect(html).toContain('已应用 2 项筛选');expect(html).toMatch(/<label[^>]*>工具/)
    expect(html).toContain('value="synthetic-draft"');expect(html).not.toContain('role="button"')
  })
  it('starts collapsed for a narrow viewport while keeping form values in the DOM',async()=>{
    const matchMedia=vi.fn(()=>({matches:true}));vi.stubGlobal('window',{matchMedia})
    const html=await render(0)
    expect(matchMedia).toHaveBeenCalledWith('(max-width: 760px)')
    expect(html).not.toMatch(/<details[^>]*open/);expect(html).toContain('未应用筛选')
    expect(html).toMatch(/<form\b[^>]*>/);expect(html).toContain('value="synthetic-draft"')
  })
})
