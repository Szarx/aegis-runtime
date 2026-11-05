<script setup lang="ts">
defineProps<{ failed?: boolean }>()
function reload() { window.location.reload() }
</script>
<template><section class="panel async-view-state" :aria-busy="!failed" :role="failed ? 'alert' : 'status'"><template v-if="failed"><h2>页面暂时无法打开</h2><p>页面模块加载失败，请重新加载后再试。</p><button type="button" class="secondary-button" @click="reload">重新加载页面</button><small>重新加载会清除当前页面的连接凭证。</small></template><template v-else><p>正在打开页面…</p><div class="loading-lines" aria-hidden="true"><i /><i /><i /></div></template></section></template>
