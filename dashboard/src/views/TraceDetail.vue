<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { TraceDetail } from '../api/types'
import { buildTree, exactDate, formatDuration, displayName, operationClass, operationLabel, operationSymbol, tokenLabel, statusLabel, spanOutcome, decisionReason } from '../domain'
import Timeline from '../components/Timeline.vue'
import Trajectory from '../components/Trajectory.vue'
import StatusBadge from '../components/StatusBadge.vue'
import UsageSummary from '../components/UsageSummary.vue'
import CopyValue from '../components/CopyValue.vue'
import CallDurationRank from '../components/CallDurationRank.vue'
import { adjacentNode, filterTraceRows, type NodeFilter } from '../traceExplorer'
import { traceHash, traceNodeLink, traceReturn } from '../traceLocation'
import { reviewActionLink } from '../approvalLocation'
import { isGoverned, receivedSignal, signalLabels } from '../trajectory'

const props = defineProps<{ detail: TraceDetail; dense?: boolean; spanId?: string; pageUrl?: string; returnTo?: string; demo?: boolean }>()
const emit = defineEmits<{ select: [id: string] }>()
const returnLink = computed(() => traceReturn(props.returnTo))
const selectedId = ref(''), nodeQuery = ref(''), nodeFilter = ref<NodeFilter>('all')
const treeContainer = ref<HTMLElement>()
const view = ref<'trajectory' | 'tree'>('trajectory')
const trajectory = ref<InstanceType<typeof Trajectory>>()
const rowHeight = computed(() => props.dense ? 34 : 46)
const rows = computed(() => buildTree(props.detail.spans))
function requestedSelection() {
  return props.detail.spans.find(span => span.span_id === props.spanId)?.span_id ||
    props.detail.spans.find(span => span.status === 'ERROR' && span.operation !== 'invoke_agent')?.span_id || props.detail.spans[0]?.span_id || ''
}
watch(() => props.detail, () => { clearNodes(); selectedId.value = requestedSelection() }, { immediate: true })
watch(() => props.spanId, id => { if (id !== selectedId.value) { clearNodes(); selectedId.value = requestedSelection() } })
function selectNode(id: string) { selectedId.value = id; if (id) emit('select',id) }
const visibleRows = computed(() => filterTraceRows(rows.value, nodeFilter.value, nodeQuery.value))
watch(visibleRows, visible => { if (!visible.some(row => row.span.span_id === selectedId.value)) selectNode(visible[0]?.span.span_id || '') })
function clearNodes() { nodeQuery.value = ''; nodeFilter.value = 'all' }
async function locateRanked(id: string) {
  clearNodes(); selectNode(id); await nextTick()
  if (view.value === 'trajectory') await trajectory.value?.focusNode(id)
  else treeContainer.value?.querySelector<HTMLButtonElement>(`[data-span-id="${id}"]`)?.focus()
}
async function onNodeKey(event: KeyboardEvent) {
  const id = adjacentNode(visibleRows.value, selectedId.value, event.key)
  if (!id) return
  event.preventDefault(); selectNode(id)
  await nextTick()
  treeContainer.value?.querySelector<HTMLButtonElement>(`[data-span-id="${id}"]`)?.focus()
}
const selected = computed(() => props.detail.spans.find(span => span.span_id === selectedId.value))
const missingRequestedSpan = computed(() => !!props.spanId && !props.detail.spans.some(span => span.span_id === props.spanId))
const selectedLink = computed(() => props.pageUrl && selected.value ? traceNodeLink(props.pageUrl,props.detail.trace.trace_id,selected.value.span_id) : '')
const warnings = computed(() => rows.value.filter(row => row.relation !== 'normal'))
const approvalRequests = computed(() => props.detail.spans.filter(span => span.attributes['aegis.mapping.version'] === 'aegis.governance.v2' && span.attributes['aegis.approval.phase'] === 'request').length)
const hasLlm = computed(() => props.detail.spans.some(span => span.operation === 'chat'))
const attrs = computed(() => Object.entries(selected.value?.attributes || {}))
const governed = computed(() => !!selected.value && isGoverned(selected.value))
const signal = computed(() => props.detail.trace.governance_signal ?? receivedSignal(props.detail.spans))
const approvalLink = computed(() => {
  const span = selected.value
  if (!span || !governed.value || span.attributes['aegis.decision.effect'] !== 'require_approval') return
  if (props.demo) return '#/demo/approval'
  return reviewActionLink(span.attributes['aegis.action.id'], traceHash(props.detail.trace.trace_id, span.span_id, props.returnTo))
})
</script>

<template>
  <div class="detail-view">
    <a v-if="!demo" class="back-link" :href="returnLink.href">← {{ returnLink.label }}</a>
    <div class="detail-heading"><div><h1>{{ detail.trace.agent_names.join(' / ') || '执行详情' }}</h1><p class="trace-id"><CopyValue :value="detail.trace.trace_id" label="Trace ID" /></p></div><div class="trace-outcomes"><span>Trace 状态 <StatusBadge :status="detail.trace.status" :outcome="detail.trace.graph_outcome" /></span><strong v-if="signal">{{ signalLabels[signal] }}</strong></div></div>
    <div class="detail-metrics">
      <div><span>执行时长</span><strong>{{ formatDuration(detail.trace.duration_ns) }}</strong></div>
      <div><span>关联节点</span><strong>{{ detail.trace.span_count }} <small>spans</small></strong></div>
      <div><span>开始时间 · UTC</span><strong class="date-value mono">{{ exactDate(detail.trace.start_time_unix_nano) }}</strong></div>
    </div>
    <p v-if="warnings.length" class="notice warning" role="status">执行关系不完整：{{ warnings.filter(row => row.relation === 'missing').length }} 个缺失 / 外部父节点，{{ warnings.filter(row => row.relation === 'cycle').length }} 个循环关系已断开展示。原始 parent ID 保留。</p>
    <p v-if="missingRequestedSpan" class="notice warning" role="status">指定节点尚未到达或不在此 Trace 中，当前显示已接收链路；未额外查询或创建节点。</p>
    <p v-if="approvalRequests" class="notice warning" role="status">本次 Agent 调用含 {{ approvalRequests }} 个审批请求快照；Agent 返回不代表工具已执行。当前决定与执行状态请在审批收件箱核对。</p>
    <UsageSummary v-if="hasLlm" :detail="detail" />
    <div class="detail-grid">
      <section class="panel execution-panel">
        <div class="panel-heading"><h2>执行链路</h2><div class="density-switch" role="group" aria-label="执行链路视图"><button type="button" :aria-pressed="view === 'trajectory'" @click="view = 'trajectory'">轨迹</button><button type="button" :aria-pressed="view === 'tree'" @click="view = 'tree'">树视图</button></div></div>
        <div class="node-filters"><label>查找节点<input v-model="nodeQuery" maxlength="128" placeholder="名称、服务、规则或 ID" /></label><label>节点类型<select v-model="nodeFilter"><option value="all">全部节点</option><option value="error">仅异常</option><option value="invoke_agent">Agent</option><option value="chat">LLM</option><option value="execute_tool">Tool</option></select></label><button class="text-button" @click="clearNodes">重置节点筛选</button></div>
        <Trajectory v-if="visibleRows.length && view === 'trajectory'" ref="trajectory" :rows="visibleRows" :origin="detail.trace.start_time_unix_nano" :duration="detail.trace.duration_ns" :selected="selectedId" @select="selectNode" />
        <div v-else-if="visibleRows.length" class="execution-body">
          <div ref="treeContainer" class="tree-column" role="group" aria-label="执行节点"><div class="axis-label">SPAN / DURATION</div><button v-for="row in visibleRows" :key="row.span.span_id" class="tree-row" :class="{ selected: selectedId === row.span.span_id }" :data-span-id="row.span.span_id" :tabindex="selectedId === row.span.span_id ? 0 : -1" @keydown="onNodeKey" :style="{ height: `${rowHeight}px`, paddingLeft: `${12 + Math.min(row.depth, 6) * 15}px` }" :aria-pressed="selectedId === row.span.span_id" @click="selectNode(row.span.span_id)">
            <span class="node-icon" :class="operationClass(row.span.operation)">{{ operationSymbol(row.span.operation) }}</span><span class="node-title" :title="row.span.name">{{ displayName(row.span.name) }}<small v-if="['closed', 'incomplete', 'cancelled', 'denied', 'awaiting_approval'].includes(String(spanOutcome(row.span)))">{{ statusLabel(row.span.status, spanOutcome(row.span)) }}</small><small v-if="row.relation !== 'normal'">{{ row.relation === 'missing' ? '父节点未到达' : '循环关系' }}</small></span><span v-if="row.span.status === 'ERROR'" class="error-dot" title="异常">!</span><span class="node-duration mono">{{ formatDuration(row.span.end_time_unix_nano - row.span.start_time_unix_nano) }}</span>
          </button></div>
          <Timeline :rows="visibleRows" :row-height="rowHeight" :origin="detail.trace.start_time_unix_nano" :duration="detail.trace.duration_ns" :selected="selectedId" @select="selectNode" />
        </div>
        <div v-else class="empty-state"><h3>没有匹配的节点</h3><p>筛选只影响视图，完整 Trace 和用量保持。</p><button class="text-button" @click="clearNodes">显示全部节点</button></div>
        <div class="panel-foot">显示 {{ visibleRows.length }} / {{ rows.length }} 个节点 · 相对 Trace 起点 · ↑ ↓ 切换，Home / End 首尾 · 0 ns 保留标记</div>
        <CallDurationRank :detail="detail" @select="locateRanked" />
      </section>
      <section v-if="selected" class="panel span-panel">
        <div class="panel-heading"><h2>节点详情</h2><StatusBadge :status="selected.status" :outcome="spanOutcome(selected)" /></div>
        <div v-if="selectedLink" class="node-link-action"><CopyValue :value="selectedLink" label="节点链接" :show-value="false" button-text="复制节点链接" /></div>
        <div class="span-content"><span class="operation-label">{{ operationLabel(selected.operation).toUpperCase() }}</span><h3>{{ displayName(selected.name) }}</h3>
          <dl class="properties"><dt>服务</dt><dd>{{ selected.service_name }}</dd><dt>Span ID</dt><dd><CopyValue :value="selected.span_id" label="Span ID" /></dd><dt>Parent ID</dt><dd><CopyValue v-if="selected.parent_span_id" :value="selected.parent_span_id" label="Parent ID" /><span v-else>—</span></dd><dt>时长</dt><dd>{{ formatDuration(selected.end_time_unix_nano - selected.start_time_unix_nano) }}</dd></dl>
          <section v-if="governed" class="llm-usage" aria-label="工具权限决策">
            <p>工具权限决策 · {{ selected.attributes['aegis.decision.effect'] === 'require_approval' ? '需人工审批' : selected.attributes['aegis.decision.effect'] === 'deny' ? '已阻止' : '已允许' }}</p>
            <dl class="properties">
              <dt>原因</dt><dd>{{ decisionReason(selected.attributes['aegis.decision.reason']) }}</dd>
              <dt>绑定身份</dt><dd>{{ selected.attributes['aegis.subject.id'] || '未绑定' }}</dd>
              <dt>权限</dt><dd>{{ selected.attributes['aegis.tool.permission'] || '未声明' }}</dd>
              <dt>策略版本</dt><dd>{{ selected.attributes['aegis.policy.revision'] || '不可用' }}</dd>
              <dt>匹配规则</dt><dd>{{ selected.attributes['aegis.decision.rule_id'] || '无' }}</dd>
              <dt>Action ID</dt><dd class="mono">{{ selected.attributes['aegis.action.id'] }}</dd>
              <dt>结束原因</dt><dd>{{ statusLabel(selected.status, spanOutcome(selected)) }} · {{ spanOutcome(selected) }}</dd>
            </dl>
            <small>{{ selected.attributes['aegis.decision.effect'] === 'require_approval' ? (selected.attributes['aegis.approval.phase'] === 'request' ? '审批请求阶段的记录；请在审批收件箱核对当前状态，本节点不执行工具。' : '通过审批绑定与单次领取检查后的执行记录。') : selected.attributes['aegis.decision.effect'] === 'deny' ? 'Runtime 在调用工具前拒绝，本次工具未执行。' : '允许调用；工具执行结果由结束原因表示。' }}</small>
            <a v-if="approvalLink" class="action-link" :href="approvalLink">{{ demo ? '查看演示审批结果' : '查看此动作的审批状态' }} ↗</a>
            <small>记录来自应用上报，不作为服务端认证身份或不可篡改审计证明。</small>
          </section>
          <section v-if="selected.operation === 'chat'" class="llm-usage" aria-label="模型用量">
            <p>模型调用</p>
            <dl class="properties">
              <dt>Provider</dt><dd>{{ selected.attributes['gen_ai.provider.name'] || '未知' }}</dd>
              <dt>请求模型</dt><dd>{{ selected.attributes['gen_ai.request.model'] }}</dd>
              <dt>返回模型</dt><dd>{{ selected.attributes['gen_ai.response.model'] || '未知' }}</dd>
              <dt>API</dt><dd>{{ selected.attributes['aegis.call.api'] }}</dd>
              <dt>输入 Token</dt><dd class="mono" data-testid="input-tokens">{{ tokenLabel(selected.attributes['gen_ai.usage.input_tokens']) }}</dd>
              <dt>输出 Token</dt><dd class="mono" data-testid="output-tokens">{{ tokenLabel(selected.attributes['gen_ai.usage.output_tokens']) }}</dd>
              <dt>结束原因</dt><dd>{{ statusLabel(selected.status, selected.attributes['aegis.call.outcome']) }} · {{ selected.attributes['aegis.call.outcome'] }}</dd>
              <dt>费用</dt><dd>未估算</dd>
            </dl>
          </section>
          <section v-if="selected.attributes['aegis.mapping.version'] === 'aegis.graph.v1'" class="llm-usage" aria-label="图流生命周期">
            <p>图流生命周期</p>
            <dl class="properties"><dt>接口</dt><dd>{{ selected.attributes['aegis.graph.mode'] }}</dd><dt>结束原因</dt><dd>{{ statusLabel(selected.status, spanOutcome(selected)) }} · {{ spanOutcome(selected) }}</dd></dl>
            <small v-if="spanOutcome(selected) === 'closed'">已提前停止消费，未确认完整执行。</small>
          </section>
          <div v-if="selected.attributes['error.type']" class="error-block"><p>异常类型</p><code>{{ selected.attributes['error.type'] }}</code><small>异常消息与堆栈未采集</small></div>
          <details class="metadata" open><summary>属性 <span>{{ attrs.length }}</span></summary><dl><template v-for="[key, value] in attrs" :key="key"><dt>{{ key === 'aegis.tool.permission' ? (governed ? '受控权限 · ' : '权限元数据 · ') + key : key }}</dt><dd>{{ value }}</dd></template></dl></details>
          <details class="metadata"><summary>原始时间与资源</summary><dl><dt>开始 · Unix ns</dt><dd class="mono" data-testid="exact-start">{{ selected.start_time_unix_nano.toString() }}</dd><dt>结束 · Unix ns</dt><dd class="mono">{{ selected.end_time_unix_nano.toString() }}</dd><template v-for="(value, key) in selected.resource" :key="key"><dt>{{ key }}</dt><dd>{{ value }}</dd></template><template v-for="(value, key) in selected.scope" :key="key"><dt>scope.{{ key }}</dt><dd>{{ value }}</dd></template></dl></details>
        </div>
      </section>
    </div>
  </div>
</template>
<style scoped>
.node-link-action{padding:7px 16px;border-bottom:1px solid var(--border)}
.trace-outcomes{display:grid;gap:6px;justify-items:end;font-size:11px;color:var(--muted)}
.trace-outcomes strong{color:#d4ba78;font-weight:500}
.action-link{display:block;margin:9px 0;color:#bdb4e7;text-decoration:underline;text-underline-offset:3px}
</style>
