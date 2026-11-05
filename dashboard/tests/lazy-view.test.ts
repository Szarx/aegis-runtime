import { expect, it, vi } from 'vitest'
import { createSSRApp, defineComponent, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { lazyView } from '../src/lazyView'
it('renders the loaded view without retries', async () => {
  const loader=vi.fn(async () => defineComponent({ render: () => h('h2','Loaded test view') }))
  const html=await renderToString(createSSRApp(lazyView(loader)))
  expect(html).toContain('Loaded test view');expect(loader).toHaveBeenCalledTimes(1)
})
it('renders a fixed failure and explicit reload without leaking the loader error or retrying', async () => {
  const loader=vi.fn(async () => { throw new Error('synthetic-private-loader-address') })
  const app=createSSRApp(lazyView(loader));app.config.errorHandler=()=>{}
  const html=await renderToString(app)
  expect(html).toContain('页面暂时无法打开');expect(html).toContain('重新加载会清除')
  expect(html).not.toContain('synthetic-private-loader-address');expect(loader).toHaveBeenCalledTimes(1)
})
