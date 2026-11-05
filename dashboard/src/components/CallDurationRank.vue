<script setup lang="ts">
import { computed } from 'vue'
import type { TraceDetail } from '../api/types'
import { displayName, formatDuration, operationLabel } from '../domain'
import { rankCalls } from '../callDuration'
const props = defineProps<{ detail: TraceDetail }>()
defineEmits<{ select: [id: string] }>()
const ranking = computed(() => rankCalls(props.detail))
</script>

<template>
  <details class="duration-rank">
    <summary>调用耗时排行 <span>{{ ranking.total }} 个已接收模型 / 工具调用</span></summary>
    <p class="duration-scope">取完整已接收 Trace 中最长的 20 个调用；审批请求阶段不计入工具执行排行。调用可能嵌套或重叠，不能相加当总执行时间或关键路径；不代表模型服务端纯推理时间。</p>
    <p v-if="ranking.invalid" class="duration-invalid" role="status">{{ ranking.invalid }} 个调用的时间或 ID 无效，未参与排行。</p>
    <div v-if="ranking.rows.length" class="table-scroll"><table class="duration-table"><thead><tr><th>调用 / 服务</th><th>记录耗时</th><th>占 Trace 时长 · 约</th><th>定位</th></tr></thead><tbody>
      <tr v-for="row in ranking.rows" :key="row.span.span_id"><td><strong>{{ displayName(row.span.name) }}</strong><small>{{ operationLabel(row.span.operation) }} · {{ row.span.service_name }}</small></td><td class="mono" :title="row.duration.toString() + ' ns'">{{ formatDuration(row.duration) }}</td><td><span class="duration-bar" aria-hidden="true"><i :style="{width:row.barWidth + '%'}" /></span><span class="mono duration-share">{{ row.share }}</span></td><td><button class="text-button" type="button" :aria-label="'定位调用 ' + row.span.name + ' ' + row.span.span_id" @click="$emit('select',row.span.span_id)">定位</button></td></tr>
    </tbody></table></div>
    <p v-else class="duration-empty">{{ ranking.total ? '没有可排序的有效调用。' : '暂无已接收的模型或工具调用。' }}</p>
  </details>
</template>

<style scoped>
.duration-rank{border-top:1px solid var(--border)}.duration-rank>summary{cursor:pointer;padding:11px 16px;font-size:11px;min-height:42px}.duration-rank>summary>span{font-size:10px;color:var(--muted);margin-left:12px}.duration-scope{padding:8px 16px 12px;color:var(--muted);font-size:10px;line-height:1.7}.duration-invalid{padding:0 16px 12px;color:var(--warning-text);font-size:11px}.duration-table{min-width:540px}.duration-table td{font-size:11px}.duration-table strong{font-weight:500;overflow-wrap:anywhere}.duration-table small{display:block;color:var(--muted);font-size:10px;margin-top:4px}.duration-table td:nth-child(2){white-space:nowrap}.duration-bar{display:inline-block;width:70px;height:4px;background:var(--surface-subtle);vertical-align:middle;margin-right:8px}.duration-bar i{display:block;height:100%;background:#9e99ba;border-radius:2px}.duration-share{font-size:10px;color:var(--muted)}.duration-empty{padding:0 16px 18px;color:var(--muted);font-size:11px}
@media(max-width:760px){.duration-rank>summary>span{display:block;margin:5px 0 0 14px}.duration-table{min-width:500px}}
</style>
