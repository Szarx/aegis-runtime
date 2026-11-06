<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowRef } from 'vue'
import { ApiError, decodeDetail, decodeList, QueryChannel } from './api/client'
import { emptyFilters } from './api/types'
import type { Filters, TraceDetail as Detail, TraceList } from './api/types'
import QueryFilters from './components/QueryFilters.vue'
import { formatDate, formatDuration, listPath } from './domain'
import { readTraceLocation, traceChanged, traceHash, traceReturn } from './traceLocation'
import StatusBadge from './components/StatusBadge.vue'
import Icon from './components/Icon.vue'
import CopyValue from './components/CopyValue.vue'
import { applyQueryDraft, queryDraft, queryHash, queryLink, readQueryLocation } from './queryLocation'
import { lazyView } from './lazyView'
import { readReviewLocation } from './approvalLocation'
import { signalLabels } from './trajectory'
const ApprovalInbox = lazyView(() => import('./views/ApprovalInbox.vue'))
const TraceDetail = lazyView(() => import('./views/TraceDetail.vue'))
const SecurityEvents = lazyView(() => import('./views/SecurityEvents.vue'))
const TrajectoryDemo = lazyView(() => import('./views/TrajectoryDemo.vue'))
const RuntimeHealth = lazyView(() => import('./views/RuntimeHealth.vue'))

const density = ref<'standard' | 'compact'>('standard')
const draftToken = ref(''), token = ref(''), connected = ref(false), connecting = ref(false)
const draft = reactive<Filters>(emptyFilters()), applied = ref(emptyFilters()), offset = ref(0)
const listing = shallowRef<TraceList>(), detail = shallowRef<Detail>()
const updatedAt = ref('')
const listBusy = ref(false), detailBusy = ref(false), listError = ref(''), detailError = ref('')
const route = ref(window.location.hash || '#/traces')
const pageUrl = window.location.origin + window.location.pathname
const listChannel = new QueryChannel(), detailChannel = new QueryChannel()
let listSequence = 0, detailSequence = 0
const isSecurity = computed(() => route.value.split('?')[0] === '#/security-events')
const isHealth = computed(() => route.value === '#/health')
const isReviewed = computed(() => route.value.split('?')[0] === '#/reviewed-actions')
const reviewLocation = computed(() => isReviewed.value ? readReviewLocation(route.value) : null)
const isDemo = computed(() => ['#/demo', '#/demo/execution', '#/demo/approval'].includes(route.value))
const isApproval = computed(() => route.value === '#/approvals' || isReviewed.value)
const isList = computed(() => route.value.split('?')[0] === '#/traces' || route.value === '#' || !route.value)
const queryLocation = computed(() => readQueryLocation(route.value === '#' ? '#/traces' : route.value))
const invalidQuery = computed(() => (isList.value || isSecurity.value) && !queryLocation.value)
const queryUrl = computed(() => queryLink(pageUrl,'traces',applied.value,offset.value))
const traceLocation = computed(() => readTraceLocation(route.value))
const traceId = computed(() => traceLocation.value?.traceId || '')
const returnLink = computed(() => traceReturn(traceLocation.value?.returnTo))
const activeFilterCount = computed(() => Object.values(applied.value).filter(Boolean).length)
const pageErrors = computed(() => listing.value?.items.filter(item => item.status === 'ERROR').length || 0)
const pageSpans = computed(() => listing.value?.items.reduce((sum, item) => sum + item.span_count, 0) || 0)
const message = (error: unknown) => error instanceof ApiError ? error.message : '无法完成请求，请重试。'

function focusMain() { document.getElementById('main-content')?.focus() }
function disconnect() {
  listSequence++; detailSequence++; listChannel.cancel(); detailChannel.cancel()
  updatedAt.value = ''; token.value = ''; draftToken.value = ''; connected.value = false; connecting.value = false
  listing.value = undefined; detail.value = undefined; listBusy.value = false; detailBusy.value = false; listError.value = ''; detailError.value = ''
}
async function loadList(connection = false) {
  const seq = ++listSequence
  listBusy.value = true; listError.value = ''
  try {
    await listChannel.run(listPath(applied.value, offset.value), token.value, decodeList, value => { listing.value = value; updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false }); if (connection) connected.value = true })
  } catch (error) { if (seq === listSequence) { listError.value = message(error); listing.value = undefined; updatedAt.value = '' } }
  finally { if (seq === listSequence) listBusy.value = false }
}
async function connect() {
  if (invalidQuery.value) return
  const candidate = draftToken.value.trim()
  disconnect(); draftToken.value = candidate; token.value = candidate; connecting.value = true
  const seq = ++listSequence
  try {
    await listChannel.run('/api/v1/traces?limit=1&offset=0',token.value,decodeList,() => { connected.value = true })
    if (seq !== listSequence || !connected.value) return
    draftToken.value = ''; connecting.value = false
    if (isList.value && !invalidQuery.value) await loadList()
    await loadDetail()
  } catch (error) { if (seq === listSequence) listError.value = message(error) }
  finally { connecting.value = false }
}
async function loadDetail() {
  const seq = ++detailSequence
  detailChannel.cancel(); detail.value = undefined; detailError.value = ''; detailBusy.value = false
  if (!connected.value || !traceId.value) return
  detailBusy.value = true
  try { await detailChannel.run('/api/v1/traces/' + traceId.value, token.value, decodeDetail, value => { detail.value = value }) }
  catch (error) { if (seq === detailSequence) detailError.value = message(error) }
  finally { if (seq === detailSequence) detailBusy.value = false }
}
function navigateQuery(hash: string) {
  if (window.location.hash === hash) { if (isList.value && !invalidQuery.value) void loadList(); return }
  window.location.hash = hash
}
function applyFilters() {
  try { navigateQuery(queryHash('traces',applyQueryDraft({...draft},applied.value),0)) }
  catch (error) { listError.value = error instanceof Error ? error.message : '筛选无效' }
}
function clearFilters() { Object.assign(draft,emptyFilters()); navigateQuery('#/traces') }
function page(delta: number) { navigateQuery(queryHash('traces',applied.value,offset.value + delta * 20)) }
function syncQuery() {
  const location = queryLocation.value
  if (location?.page === 'traces') {
    applied.value = location.filters as Filters; offset.value = location.offset
    Object.assign(draft,queryDraft(applied.value))
  }
}
function onRoute() {
  const previous = route.value
  route.value = window.location.hash || '#/traces'
  if (previous === route.value) return
  if (!connecting.value) { listSequence++; listChannel.cancel(); listBusy.value = false }
  syncQuery()
  if (isList.value || invalidQuery.value) {
    listing.value = undefined; updatedAt.value = ''; listError.value = ''
    if (isList.value && connected.value && !invalidQuery.value) void loadList()
  }
  if (traceChanged(previous,route.value)) void loadDetail()
}
syncQuery()
function selectSpan(spanId: string) {
  if (!traceId.value) return
  const hash = traceHash(traceId.value,spanId,traceLocation.value?.returnTo)
  window.history.replaceState(null,'',hash); route.value = hash
}
onMounted(() => window.addEventListener('hashchange', onRoute))
onBeforeUnmount(() => { window.removeEventListener('hashchange', onRoute); disconnect() })
</script>

<template>
  <div class="app-shell" :data-density="density">
    <a class="skip-link" href="#main-content" @click.prevent="focusMain">跳至主要内容</a>
    <aside class="sidebar">
      <a href="#/traces" class="brand" aria-label="Aegis 首页"><span class="brand-mark"><Icon name="shield" :size="23" /></span><span>Aegis<small>Runtime governance</small></span></a>
      <p class="nav-label">工作台</p>
      <nav aria-label="主导航">
        <a href="#/traces" title="执行追踪" :aria-current="!isApproval && !isSecurity && !isHealth ? 'page' : undefined" :class="['nav-item', { active: !isApproval && !isSecurity && !isHealth }]"><Icon name="activity" /><span>执行追踪</span></a>
        <a href="#/security-events" title="安全事件" :aria-current="isSecurity ? 'page' : undefined" :class="['nav-item', { active: isSecurity }]"><Icon name="shield" /><span>安全事件</span></a>
        <a href="#/health" title="运行与采集健康" :aria-current="isHealth ? 'page' : undefined" :class="['nav-item', { active: isHealth }]"><Icon name="activity" /><span>运行与采集健康</span></a>
        <span class="nav-label nav-section">人工审核</span>
        <a href="#/reviewed-actions" title="执行审批" :aria-current="isReviewed ? 'page' : undefined" :class="['nav-item', { active: isReviewed }]"><Icon name="check" /><span>执行审批</span></a>
        <a href="#/approvals" title="审批准备" :aria-current="isApproval && !isReviewed ? 'page' : undefined" :class="['nav-item', { active: isApproval && !isReviewed }]"><Icon name="clock" /><span>审批准备</span></a>
      </nav>
      <div class="sidebar-note"><span class="environment-label"><span class="tiny-dot" />本地工作区</span><span class="version">v0.1 · 开发预览</span></div>
      <div class="sidebar-footer"><span class="tiny-dot" :class="{ online: connected }" />{{ connected ? 'Trace 会话已连接' : 'Trace 未连接' }}</div>
    </aside>
    <div class="workspace">
      <header class="topbar"><div class="breadcrumb">工作台 <span>/</span> <strong>{{ isDemo ? '合成轨迹演示' : isHealth ? '运行与采集健康' : isSecurity ? '安全事件' : isReviewed ? '执行审批' : isApproval ? '审批准备' : '执行追踪' }}</strong><span v-if="traceId">/ 详情</span></div><div class="topbar-actions"><div class="density-switch" role="group" aria-label="显示密度"><button type="button" :aria-pressed="density === 'standard'" @click="density = 'standard'">标准</button><button type="button" :aria-pressed="density === 'compact'" @click="density = 'compact'">紧凑</button></div><span v-if="isDemo" class="connection-indicator">离线示例</span><div v-else-if="!isApproval" class="connection-indicator"><span class="tiny-dot" :class="{ online: connected }" /><span>{{ connected ? '会话已连接' : '未连接 Collector' }}</span><button v-if="connected" class="text-button" @click="disconnect">断开</button></div></div></header>
      <main id="main-content" tabindex="-1">
        <TrajectoryDemo v-if="isDemo" :hash="route" />
        <section v-else-if="isReviewed && !reviewLocation" class="panel detail-state"><h1>审批地址无效</h1><a class="back-link" href="#/reviewed-actions">打开执行审批</a></section>
        <ApprovalInbox v-else-if="isApproval" :key="route" :reviewed="isReviewed" :action-id="reviewLocation?.actionId" :return-to="reviewLocation?.returnTo" />
        <section v-else-if="invalidQuery" class="panel detail-state"><h1>查询地址无效</h1><p>请从列表重新选择筛选条件。</p><a class="back-link" :href="isSecurity ? '#/security-events' : '#/traces'">清空地址条件</a></section>
        <SecurityEvents v-else-if="isSecurity && connected" :token="token" :hash="route" :page-url="pageUrl" @navigate="navigateQuery" />
        <RuntimeHealth v-else-if="isHealth && connected" :token="token" />
        <template v-else-if="!connected">
          <div class="page-heading"><div><h1>{{ isHealth ? '运行与采集健康' : isSecurity ? '安全事件' : '执行追踪' }}</h1><p class="subtitle">查询 Agent、模型与工具的执行记录。</p></div></div>
          <section class="connect-card panel"><div class="connect-icon"><Icon name="plug" :size="22" /></div><h2>连接数据源</h2><p>使用当前工作区的 Collector 凭证。连接后可查询追踪和安全事件。</p><form class="connect-form" @submit.prevent="connect"><label for="token">Bearer token <span>仅保存在当前页面</span></label><div><input id="token" v-model="draftToken" type="password" autocomplete="off" placeholder="未配置认证时可留空" :disabled="connecting" /><button class="primary-button" :disabled="connecting">{{ connecting ? '正在连接…' : '连接 Collector' }}</button></div></form><p v-if="listError" class="notice error-notice" role="alert">{{ listError }}</p><div class="connect-meta"><span><i class="tiny-dot" />同源 API</span><span>Agent / LLM / Tool 追踪</span><span>默认不采集原始内容</span></div></section>
          <p class="connection-help">尚未接入？先<a href="#/demo" class="demo-link">打开合成轨迹演示 ↗</a>，体验模型耗时、人工审批和恢复执行。</p>
        </template>
        <template v-else-if="isList">
          <div class="page-heading"><div><h1>执行追踪</h1><p class="subtitle">查询 Agent、模型与工具的执行记录。</p></div><button class="secondary-button" :disabled="listBusy" @click="loadList()"><Icon name="refresh" :class="{ spinning: listBusy }" :size="15" /> {{ listBusy ? '刷新中…' : '刷新追踪' }}</button></div>
          <div class="metrics"><div><span class="metric-label">匹配记录</span><strong>{{ listing?.total ?? '—' }}</strong><span class="metric-foot">当前筛选范围</span></div><div><span class="metric-label">本页异常</span><strong :class="{ coral: pageErrors }">{{ listing ? pageErrors : '—' }}<span v-if="listing" class="metric-denominator"> / {{ listing.items.length }}</span></strong><span class="metric-foot">执行中出现异常的记录</span></div><div><span class="metric-label">本页节点</span><strong>{{ listing ? pageSpans : '—' }}</strong><span class="metric-foot">Agent、模型与工具</span></div></div>
          <section class="panel trace-list"><div class="panel-heading"><h2>执行记录 <span class="count-pill">{{ listing?.total ?? '—' }}</span></h2><CopyValue :value="queryUrl" label="追踪查询链接" :show-value="false" button-text="复制查询链接" /><span class="muted small" role="status">{{ listBusy && listing ? '正在刷新，暂时显示上次结果' : updatedAt ? `页面更新 ${updatedAt} · 按开始时间倒序` : '按开始时间倒序' }}</span></div>
            <QueryFilters title="筛选追踪" :active-count="activeFilterCount"><form class="filter-form" @submit.prevent="applyFilters"><div class="filter-fields primary-filters"><label>Agent<input v-model="draft.agent" maxlength="128" placeholder="全部 Agent" /></label><label>Service<input v-model="draft.service" maxlength="128" placeholder="全部 Service" /></label><label>状态<select v-model="draft.status"><option value="">全部状态</option><option value="UNSET">无异常</option><option value="ERROR">异常</option></select></label></div>
              <details class="advanced-filters"><summary>时间范围</summary><div class="filter-fields"><label>开始时间 · 从<input v-model="draft.after" type="datetime-local" step="0.001" /></label><label>开始时间 · 至<input v-model="draft.before" type="datetime-local" step="0.001" /></label></div></details>
              <div class="filter-actions"><span class="filter-applied">{{ activeFilterCount ? `已应用 ${activeFilterCount} 项筛选` : '未应用筛选' }}</span><button type="button" class="text-button" @click="clearFilters">清空</button><button class="secondary-button">应用筛选</button></div></form></QueryFilters>
            <p v-if="listError" class="notice error-notice" role="alert">{{ listError }} <button class="text-button" @click="loadList()">重试</button></p>
            <div class="table-scroll" :aria-busy="listBusy"><table><thead><tr><th>Agent / Trace ID</th><th>Trace 状态</th><th>治理信号</th><th>开始时间 · 本地</th><th>执行时长</th><th>节点</th><th><span class="sr-only">打开</span></th></tr></thead><tbody><tr v-for="trace in listing?.items" :key="trace.trace_id"><td><a class="trace-link" :href="traceHash(trace.trace_id,undefined,queryHash('traces',applied,offset))"><span class="list-agent-icon"><Icon name="layers" :size="15" /></span><span><strong>{{ trace.agent_names.join(' / ') || '未命名 Agent' }}</strong><small class="mono">{{ trace.trace_id.slice(0, 12) }}<span>…</span></small></span></a></td><td><StatusBadge :status="trace.status" :outcome="trace.graph_outcome" /></td><td><span v-if="trace.governance_signal" class="trace-signal">{{ signalLabels[trace.governance_signal] }}</span><span v-else class="muted" aria-label="无可用治理信号">—</span></td><td class="mono time-cell" :title="trace.start_time_unix_nano.toString()">{{ formatDate(trace.start_time_unix_nano) }}</td><td class="mono">{{ formatDuration(trace.duration_ns) }}</td><td><span class="span-count mono">{{ trace.span_count }}</span></td><td><a :href="traceHash(trace.trace_id,undefined,queryHash('traces',applied,offset))" :aria-label="'查看 Trace ' + trace.trace_id" class="arrow-link"><Icon name="arrow" :size="15" /></a></td></tr></tbody></table></div>
            <div v-if="!listing?.items.length && !listError" class="empty-state"><Icon name="activity" :size="25" /><h3>{{ listBusy ? '正在查询执行记录' : '还没有匹配的 Trace' }}</h3><p v-if="!listBusy">运行原生示例，或调整筛选条件后刷新。</p></div>
            <footer class="table-footer"><span>{{ listing?.items.length ? `${offset + 1}–${offset + listing.items.length}` : '0' }} / {{ listing?.total ?? '—' }} 条记录</span><div><button class="page-button" :disabled="offset === 0 || listBusy" aria-label="上一页" @click="page(-1)">←</button><span>第 {{ offset / 20 + 1 }} 页</span><button class="page-button" :disabled="!listing || offset + 20 >= listing.total || offset + 20 > 10000 || listBusy" aria-label="下一页" @click="page(1)">→</button></div></footer>
          </section><p class="page-note"><span class="tiny-dot" />查询链接包含已应用条件和页码；打开后仍需连接。仅展示已记录的执行，用量未知时保持未知。</p>
        </template>
        <template v-else-if="traceId"><TraceDetail v-if="detail" :detail="detail" :dense="density === 'compact'" :span-id="traceLocation?.spanId" :page-url="pageUrl" :return-to="traceLocation?.returnTo" @select="selectSpan" /><div v-else class="panel detail-state"><a :href="returnLink.href" class="back-link">← {{ returnLink.label }}</a><h2>{{ detailBusy ? '正在加载执行链路…' : '无法显示执行详情' }}</h2><p v-if="detailError" role="alert">{{ detailError }}</p><button v-if="!detailBusy" class="secondary-button" @click="loadDetail">重试</button></div></template>
        <div v-else class="panel detail-state"><h1>无效的 Trace 地址</h1><p>请从列表选择有效的执行记录。</p><a class="back-link" href="#/traces">← 返回执行追踪</a></div>
      </main><footer class="workspace-footer"><span>Aegis · Runtime governance</span><span>当前工作区 · 本地时间</span></footer>
    </div>
  </div>
</template>

<style scoped>.trace-list>.panel-heading{flex-wrap:wrap}.trace-list>.panel-heading>.copy-value{margin-left:auto}.trace-list>.panel-heading>.muted{margin-left:auto}.trace-signal{color:#d4ba78}.demo-link{margin:0 4px;color:#bdb4e7;text-decoration:underline;text-underline-offset:3px}@media(max-width:440px){.trace-list>.panel-heading>.muted{flex-basis:100%}}</style>
