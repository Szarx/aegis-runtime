<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue'
import { ApiError, QueryChannel } from '../api/client'
import { decodeSecurity, emptySecurityFilters, securityPath, type SecurityList } from '../api/security'
import SecurityTable from '../components/SecurityTable.vue'
import QueryFilters from '../components/QueryFilters.vue'
import CopyValue from '../components/CopyValue.vue'
import { applyQueryDraft, queryDraft, queryHash, queryLink, readQueryLocation } from '../queryLocation'
import type { SecurityFilters } from '../api/security'
const props = defineProps<{ token: string; hash: string; pageUrl: string }>()
const emit = defineEmits<{navigate:[hash:string]}>()
const queryUrl = computed(() => queryLink(props.pageUrl,'security-events',applied.value,offset.value))
const draft = reactive(emptySecurityFilters()), applied = ref(emptySecurityFilters()), offset = ref(0)
const activeFilterCount = computed(() => Object.values(applied.value).filter(Boolean).length)
const listing = shallowRef<SecurityList>(), busy = ref(false), error = ref('')
const channel = new QueryChannel(); let sequence = 0
async function load() {
  const seq = ++sequence; busy.value = true; error.value = ''; listing.value = undefined
  try { await channel.run(securityPath(applied.value,offset.value),props.token,decodeSecurity,value => { listing.value = value }) }
  catch (e) { if (seq === sequence) error.value = e instanceof ApiError ? e.message : e instanceof Error ? e.message : '无法查询安全事件。' }
  finally { if (seq === sequence) busy.value = false }
}
function apply() {
  try {
    const hash = queryHash('security-events',applyQueryDraft({...draft},applied.value),0)
    if (hash === props.hash) void load(); else emit('navigate',hash)
  } catch (e) { error.value = e instanceof Error ? e.message : '筛选无效' }
}
function clear() { Object.assign(draft,emptySecurityFilters()); if (props.hash === '#/security-events') void load(); else emit('navigate','#/security-events') }
function page(delta: number) { emit('navigate',queryHash('security-events',applied.value,offset.value + delta * 20)) }
function restore() {
  const location = readQueryLocation(props.hash)
  if (location?.page !== 'security-events') return
  applied.value = location.filters as SecurityFilters; offset.value = location.offset
  Object.assign(draft,queryDraft(applied.value)); void load()
}
watch(() => [props.hash,props.token],restore,{immediate:true})
onBeforeUnmount(() => { sequence++; channel.cancel(); listing.value = undefined })
</script>
<template>
  <div class="page-heading"><div><p class="eyebrow">RUNTIME GOVERNANCE</p><h1>安全事件</h1><p class="subtitle">查询已接收的工具治理决策，关联执行链路。</p></div><div class="query-heading-actions"><CopyValue :value="queryUrl" label="安全事件查询链接" :show-value="false" button-text="复制查询链接" /><button class="secondary-button" :disabled="busy" @click="load">{{ busy ? '查询中…' : '刷新事件' }}</button></div></div>
  <p class="notice warning">身份与决策来自应用上报，不作为服务端认证或不可篡改审计证明。未接入、未成功导出的调用不会出现在此处。</p>
  <QueryFilters class="panel" title="筛选事件" :active-count="activeFilterCount"><form class="filter-form security-query" @submit.prevent="apply"><div class="filter-fields primary-filters">
    <label>上报身份<input v-model="draft.subject" maxlength="128" placeholder="全部身份" /></label><label>工具<input v-model="draft.tool" maxlength="128" placeholder="全部工具" /></label><label>权限<input v-model="draft.permission" maxlength="128" placeholder="全部权限" /></label><label>服务<input v-model="draft.service_name" maxlength="128" placeholder="全部服务" /></label>
    <label>决策<select v-model="draft.effect"><option value="">全部决策</option><option value="allow">允许</option><option value="deny">拒绝</option><option value="require_approval">需人工审批</option></select></label>
    <label>结果<select v-model="draft.outcome"><option value="">全部结果</option><option value="denied">已阻止</option><option value="completed">已完成</option><option value="error">异常</option><option value="awaiting_approval">待审批快照</option><option value="cancelled">已取消</option></select></label>

  </div><details class="advanced-filters"><summary>更多条件 · ID 与时间</summary><div class="filter-fields">    <label>Action ID<input v-model="draft.action_id" maxlength="32" placeholder="完整 Action ID" /></label><label>Trace ID<input v-model="draft.trace_id" maxlength="32" placeholder="完整 Trace ID" /></label>
    <label>开始时间 · 从<input v-model="draft.after" type="datetime-local" step="0.001" /></label><label>开始时间 · 至<input v-model="draft.before" type="datetime-local" step="0.001" /></label></div></details><div class="filter-actions"><span class="filter-applied">{{ activeFilterCount ? `已应用 ${activeFilterCount} 项筛选` : '未应用筛选' }}</span><button type="button" class="text-button" @click="clear">清空筛选</button><button class="secondary-button">应用事件筛选</button></div></form></QueryFilters>
  <SecurityTable :listing="listing" :busy="busy" :error="error" :offset="offset" :return-to="queryHash('security-events',applied,offset)" @retry="load" @page="page" />
  <p class="page-note">查询链接包含已应用条件和页码，打开后仍需连接。同一个 Action 可对应多次治理尝试；一条事件由 Trace / Span 标识。跨页查询时新事件可能改变页边界。</p>
</template>

<style scoped>.page-heading{flex-wrap:wrap}.query-heading-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap}</style>
