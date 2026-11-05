<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { traceHash } from '../traceLocation'
import type { SecurityList } from '../api/security'
import { decisionReason, exactDate, statusLabel } from '../domain'
import { securityPageFile, type SecurityExportFormat } from '../securityPageExport'
const props = defineProps<{ listing?: SecurityList; busy: boolean; error: string; offset: number; returnTo?: string }>()
defineEmits<{ retry: []; page: [delta: number] }>()
const exportFeedback = ref('')
const canExport = computed(() => !props.busy && !props.error && !!props.listing?.items.length)
const pendingUrls = new Map<string, ReturnType<typeof setTimeout>>()
function release(url: string) { clearTimeout(pendingUrls.get(url)); pendingUrls.delete(url); URL.revokeObjectURL(url) }
function download(format: SecurityExportFormat) {
  if (!canExport.value || !props.listing) return
  let url: string | undefined, link: HTMLAnchorElement | undefined
  try {
    const file = securityPageFile(props.listing,format)
    url = URL.createObjectURL(new Blob([file.body],{type:file.mime}))
    link = document.createElement('a'); link.href = url; link.download = file.filename; link.hidden = true
    document.body.append(link); link.click()
    exportFeedback.value = `已请求下载本页 ${props.listing.items.length} 条 ${format.toUpperCase()}，请查看浏览器下载。`
  } catch { exportFeedback.value = '无法生成本页文件，请重试或使用命令行导出。' }
  finally {
    link?.remove()
    if (url) { const value = url; pendingUrls.set(value,setTimeout(() => release(value),1000)) }
  }
}
watch(() => [props.listing,props.busy,props.error,props.offset], () => { exportFeedback.value = '' })
onBeforeUnmount(() => { for (const url of pendingUrls.keys()) release(url) })
</script>
<template>
  <section class="panel">
    <div class="panel-heading security-heading"><h2>安全事件 <span class="count-pill">{{ listing?.total ?? '—' }}</span></h2><div class="export-actions" role="group" aria-label="导出当前页"><button class="secondary-button" :disabled="!canExport" @click="download('jsonl')">导出本页 JSONL</button><button class="secondary-button" :disabled="!canExport" @click="download('csv')">CSV</button></div></div>
    <div class="export-scope"><span>按开始时间倒序 · 仅导出本页已载入记录（{{ listing?.items.length ?? '—' }} 条）</span><span>精确保留纳秒请选 JSONL；CSV 导入时请将列设为文本。</span></div>
    <p v-if="exportFeedback" class="export-feedback" role="status">{{ exportFeedback }}</p>
    <p v-if="error" class="notice error-notice" role="alert">{{ error }} <button class="text-button" @click="$emit('retry')">重试</button></p>
    <div class="table-scroll" :aria-busy="busy"><table><thead><tr><th>决策 / 结果</th><th>工具 / 权限</th><th>应用上报身份</th><th>原因 / 策略</th><th>时间 · UTC</th><th>关联</th></tr></thead><tbody>
      <tr v-for="event in listing?.items" :key="event.trace_id + event.span_id">
        <td><strong :class="event.effect === 'deny' ? 'coral' : ''">{{ event.effect === 'require_approval' ? '需人工审批' : event.effect === 'deny' ? '已阻止' : '已允许' }}</strong><small class="security-small">{{ statusLabel(event.status,event.outcome) }} · {{ event.outcome }}</small></td>
        <td>{{ event.tool }}<small class="security-small">{{ event.permission ?? '未声明权限' }}</small></td>
        <td>{{ event.subject ?? '未绑定身份' }}<small class="security-small">{{ event.service_name }} / {{ event.agent_name ?? '未命名 Agent' }}</small></td>
        <td>{{ decisionReason(event.reason) }}<small class="security-small">{{ event.policy_revision ?? '策略不可用' }} / {{ event.rule_id ?? '无匹配规则' }}</small></td>
        <td class="mono small" :title="event.start_time_unix_nano.toString()">{{ exactDate(event.start_time_unix_nano) }}</td>
        <td><a class="trace-link" :href="traceHash(event.trace_id,event.span_id,returnTo)">查看 Trace ↗</a><small class="security-small mono">Action {{ event.action_id }}</small><small class="security-small mono">Span {{ event.span_id }}</small></td>
      </tr>
    </tbody></table></div>
    <div v-if="!listing?.items.length && !error" class="empty-state"><h3>{{ busy ? '正在查询安全事件…' : '没有匹配的治理事件' }}</h3><p v-if="!busy">仅展示已接入 Runtime 并成功上报的治理节点，普通工具标签不会出现在此处。</p></div>
    <footer class="table-footer"><span>{{ listing?.items.length ? `${offset + 1}–${offset + listing.items.length}` : '0' }} / {{ listing?.total ?? '—' }} 条事件</span><div><button class="page-button" :disabled="!offset || busy" aria-label="上一页事件" @click="$emit('page',-1)">←</button><span>第 {{ offset / 20 + 1 }} 页</span><button class="page-button" :disabled="!listing || offset + 20 >= listing.total || offset + 20 > 10000 || busy" aria-label="下一页事件" @click="$emit('page',1)">→</button></div></footer>
  </section>
</template>
<style scoped>
.security-small{display:block;color:var(--muted);font-size:10px;margin-top:5px;overflow-wrap:anywhere}td{vertical-align:top;max-width:300px}td:nth-child(5){white-space:nowrap}
.security-heading{flex-wrap:wrap;gap:12px}.export-actions{display:flex;gap:6px}.export-actions button{font-size:11px;min-height:28px;padding:5px 9px}.export-scope{display:flex;justify-content:space-between;gap:6px 18px;flex-wrap:wrap;padding:10px 16px;border-bottom:1px solid var(--border);color:var(--muted);font-size:10px}.export-feedback{padding:10px 16px;color:var(--text-primary);font-size:11px;border-bottom:1px solid var(--border)}
@media(max-width:760px){.security-heading h2{width:100%}.export-actions{flex-wrap:wrap}}
</style>
