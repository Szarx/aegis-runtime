<script setup lang="ts">
import { computed } from 'vue'
import type { TraceDetail } from '../api/types'
import { summarizeUsage } from '../usage'
const props = defineProps<{ detail: TraceDetail }>()
const usage = computed(() => summarizeUsage(props.detail.spans, props.detail.trace.trace_id))
</script>

<template>
  <section class="panel usage-summary" aria-label="已接收模型用量汇总">
    <div class="usage-summary-grid">
      <div class="usage-title"><h2>模型用量汇总</h2><span class="muted">{{ usage.calls }} 个已接收模型调用</span></div>
      <div v-for="[key, label] in ([['input', '输入 Token'], ['output', '输出 Token']] as const)" :key="key">
        <span class="muted">{{ label }}</span>
        <strong class="mono" :data-testid="`total-${key}-tokens`">{{ !usage.calls ? '无模型调用' : usage[key].total === null ? '未知' : usage[key].total.toString() }}</strong>
        <small v-if="usage.calls">{{ usage[key].known }} / {{ usage.calls }} 个调用有此项数据</small>
      </div>
    </div>
    <details class="usage-coverage"><summary>统计范围与覆盖说明</summary><p class="panel-foot">仅汇总当前已接收、已接入的模型节点；不保证 Trace 到齐或覆盖内部重试、未接入调用。缺失用量不按零计算。</p></details>
  </section>
</template>

<style scoped>
.usage-summary{margin-bottom:16px}.usage-summary-grid{display:grid;grid-template-columns:1.2fr repeat(2,minmax(0,1fr));gap:18px;padding:12px 16px;align-items:center}.usage-summary-grid>div{min-width:0}.usage-title h2{margin-bottom:5px}.usage-title span{font-size:10px}.usage-summary-grid strong{display:inline-block;font-size:16px;overflow-wrap:anywhere;margin:0 0 3px 10px}.usage-summary-grid small{display:block;color:var(--muted);font-size:10px}.usage-summary-grid>div>span{font-size:11px}.usage-coverage{border-top:1px solid var(--border);font-size:10px;color:var(--muted)}.usage-coverage summary{padding:7px 16px;cursor:pointer}.usage-summary .panel-foot{font-size:11px;line-height:1.6;white-space:normal;border-top:0;padding-top:0}@media(max-width:600px){.usage-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.usage-title{grid-column:span 2}.usage-title h2{display:inline;margin-right:10px}.usage-summary-grid strong{display:block;margin:4px 0}}
</style>
