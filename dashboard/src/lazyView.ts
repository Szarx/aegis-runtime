import { defineAsyncComponent, h, type Component } from 'vue'
import AsyncViewState from './components/AsyncViewState.vue'
export function lazyView(loader: () => Promise<Component | { default: Component }>) {
  return defineAsyncComponent({ loader, delay: 120, timeout: 15000,
    loadingComponent: { inheritAttrs: false, render: () => h(AsyncViewState) },
    errorComponent: { inheritAttrs: false, render: () => h(AsyncViewState, { failed: true }) },
    onError: (_error, _retry, fail) => fail(),
  })
}
