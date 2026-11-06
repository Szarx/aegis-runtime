<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { QueryChannel } from '../api/client'
import { decodeHealth, heartbeatState, type HealthList } from '../api/health'
import { traceHash } from '../traceLocation'
import CopyValue from '../components/CopyValue.vue'

const props = defineProps<{ token: string }>()
const listing = shallowRef<HealthList>()
const busy = ref(false), error = ref(''), elapsed = ref(0)
const channel = new QueryChannel()
let received = performance.now(), sequence = 0
let refreshTimer: ReturnType<typeof setInterval>, clockTimer: ReturnType<typeof setInterval>
const stale = computed(() => listing.value?.items.filter(row => heartbeatState(row, elapsed.value) === '心跳中断').length ?? 0)
async function refresh() {
  const seq = ++sequence
  busy.value = true
  try {
    await channel.run('/api/v1/health', props.token, decodeHealth, value => {
      listing.value = value; received = performance.now(); elapsed.value = 0; error.value = ''
    })
  } catch (e) {
    if (seq === sequence) error.value = e instanceof Error ? e.message : '健康查询失败'
  } finally { if (seq === sequence) busy.value = false }
}
onMounted(() => {
  void refresh()
  refreshTimer = setInterval(() => { if (!busy.value) void refresh() }, 10000)
  clockTimer = setInterval(() => { elapsed.value = performance.now() - received }, 1000)
})
onBeforeUnmount(() => { sequence++; channel.cancel(); clearInterval(refreshTimer); clearInterval(clockTimer) })
</script>

<template>
  <div class="page-heading"><div><h1>运行与采集健康</h1><p class="subtitle">查看宿主活动与采集诊断，按 10 秒刷新。</p></div>
    <button class="secondary-button" :disabled="busy" @click="refresh">刷新健康状态</button></div>
  <p class="notice">单 Collector 进程快照，最多 1024 个实例。心跳中断表示超过 45 秒未收到新快照，业务结果需查询对应系统。Collector 重启后重新建立快照。</p>
  <p v-if="error" class="notice error-notice" role="alert">{{ error }} <span v-if="listing">当前保留上次快照。</span></p>
  <p v-if="listing" class="health-summary">{{ listing.items.length }} 个实例 · {{ stale }} 个心跳中断 · 累计淘汰 {{ listing.evicted_instances }} 个实例</p>
  <div class="health-grid">
    <article v-for="row in listing?.items" :key="row.instance_id" class="panel health-card">
      <div class="health-heading"><h2>{{ row.service_name }}</h2><strong :class="{ warning: heartbeatState(row, elapsed) === '心跳中断' }">{{ heartbeatState(row, elapsed) }}</strong></div>
      <CopyValue :value="row.instance_id" label="实例 ID" />
      <p class="muted small">最后收到 {{ row.last_received_at }} · 序号 {{ row.sequence }}</p>
      <dl>
        <div><dt>当前活动 Span</dt><dd>{{ row.active_spans }}</dd></div>
        <div><dt>待导出</dt><dd>{{ row.diagnostics.pending_spans }}</dd></div>
        <div><dt>累计已导出</dt><dd>{{ row.diagnostics.exported_spans }}</dd></div>
        <div><dt>累计丢弃</dt><dd :class="{ warning: row.diagnostics.dropped_spans > 0 }">{{ row.diagnostics.dropped_spans }}</dd></div>
        <div><dt>累计失败 Span</dt><dd>{{ row.diagnostics.failed_spans }}</dd></div>
        <div><dt>导出失败次数</dt><dd>{{ row.diagnostics.export_failures }}</dd></div>
        <div><dt>采集异常次数</dt><dd>{{ row.diagnostics.instrumentation_failures }}</dd></div>
        <div><dt>健康上报失败次数</dt><dd>{{ row.health_failures }}</dd></div>
      </dl>
      <p v-if="row.activity_truncated" class="warning">活动明细已截断，请结合总数检查。</p>
      <div v-if="row.active_traces.length" class="health-traces"><strong>活动 Trace</strong><a v-for="id in row.active_traces" :key="id" :href="traceHash(id)" class="mono">{{ id }} ↗</a><small>运行中尚未结束的 Span 可能尚未出现在详情。</small></div>
      <p v-else class="muted small">本次快照没有可列出的活动 Trace。</p>
    </article>
  </div>
  <section v-if="listing && !listing.items.length" class="panel empty-state"><h2>尚无宿主上报</h2><p>在 SDK 初始化后显式启用健康上报。</p><code>sdk.start_health_reporting(collector_url + "/v1/health", token=trace_token)</code></section>
</template>

<style scoped>
.health-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:14px}
.health-summary{font-size:12px;color:var(--muted);margin:14px 0}
.health-card{padding:16px;min-width:0}
.health-heading{display:flex;justify-content:space-between;gap:12px;margin-bottom:8px}
.health-heading h2{overflow-wrap:anywhere}.health-heading strong{white-space:nowrap;font-size:12px;color:#a1c3b7}
.health-card p{margin:9px 0;overflow-wrap:anywhere}.health-card dl{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:15px 0}
.health-card dt{color:var(--muted);font-size:11px}.health-card dd{margin-top:3px;font-size:18px}
.health-card .warning{color:#d4ba78}.health-traces{display:grid;gap:7px;font-size:11px}
.health-traces a{overflow-wrap:anywhere;text-decoration:underline}.health-traces small{color:var(--muted)}
.empty-state code{display:block;white-space:normal;overflow-wrap:anywhere;margin-top:12px}
</style>
