<script setup lang="ts">
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue'
import { ApprovalChannel, ApprovalError, executionLabels, isReviewed, reviewText } from '../api/approvals'
import type { Approval, ApprovalList } from '../api/approvals'
import { approvalDecisionLabel, filterReviewPage, sortReviewPage, reviewPageCounts, type QueueStatus, type QueueOrder } from '../reviewQueue'
import { emptySecurityFilters } from '../api/security'
import { queryHash } from '../queryLocation'
import CopyValue from '../components/CopyValue.vue'
const props = defineProps<{ reviewed?: boolean; actionId?: string; returnTo?: string }>()
const acknowledged = ref<Record<string, boolean>>({})
const queueQuery = ref(''), queueStatus = ref<QueueStatus>(''), expanded = ref('')
const queueOrder = ref<QueueOrder>('received'), updatedAt = ref('')
const token = ref(''), draft = ref(''), connected = ref(false), busy = ref(false), error = ref(''), offset = ref(0)
const list = shallowRef<ApprovalList>(), channel = new ApprovalChannel(undefined, 5000, props.reviewed ?? false)
const visible = computed(() => sortReviewPage(filterReviewPage(list.value?.items ?? [], queueStatus.value, queueQuery.value),queueOrder.value))
const pageCounts = computed(() => reviewPageCounts(list.value?.items ?? []))
function toggleReview(id: string) { acknowledged.value = {}; expanded.value = expanded.value === id ? '' : id }
function clearQueue() { queueQuery.value = ''; queueStatus.value = ''; queueOrder.value = 'received' }
watch([queueQuery, queueStatus, queueOrder], () => { acknowledged.value = {}; expanded.value = '' })
let sequence = 0
function disconnect() {
  sequence++; channel.cancel(); expanded.value = ''; clearQueue(); acknowledged.value = {}; token.value = ''; draft.value = ''; list.value = undefined
  connected.value = false; busy.value = false; error.value = ''; offset.value = 0; updatedAt.value = ''
}
async function refresh() {
  const seq = ++sequence; expanded.value = ''
  busy.value = true; error.value = ''; list.value = undefined; acknowledged.value = {}; updatedAt.value = ''
  try { await channel.run(token.value, offset.value, value => { list.value = value; connected.value = true; draft.value = ''; updatedAt.value = new Date().toLocaleTimeString('zh-CN',{hour12:false}) }, undefined, props.actionId) }
  catch { if (seq === sequence) error.value = new ApprovalError().message }
  finally { if (seq === sequence) busy.value = false }
}
async function connect() { const candidate = draft.value.trim(); disconnect(); token.value = candidate; draft.value = candidate; await refresh() }
async function decide(item: Approval, value: 'approved' | 'rejected') {
  const seq = ++sequence; expanded.value = ''
  busy.value = true; error.value = ''; list.value = undefined; acknowledged.value = {}; updatedAt.value = ''
  try {
    const committed = await channel.run(token.value, offset.value, () => {}, { action: item.action_id, value, ...(isReviewed(item) ? { reviewDigest: item.review_digest } : {}) }, props.actionId)
    if (committed && seq === sequence) await refresh()
  } catch { if (seq === sequence) error.value = '决定结果尚未确认。请先刷新状态，再继续审核。' }
  finally { if (seq === sequence) busy.value = false }
}
function page(delta: number) { offset.value += delta * 20; void refresh() }
onBeforeUnmount(disconnect)
</script>

<template>
  <a v-if="returnTo" :href="returnTo" class="back-link">← 返回原轨迹节点</a>
  <div class="page-heading"><div><p class="eyebrow">{{ props.reviewed ? 'REVIEWED EXECUTION' : 'APPROVAL PREPARATION' }}</p><h1>{{ props.reviewed ? '执行审批' : '审批准备' }}</h1><p class="subtitle">审核动作绑定，记录人工决定。</p></div><button v-if="connected" class="secondary-button" :disabled="busy" @click="refresh">刷新状态</button></div>
  <p class="notice approval-boundary">{{ props.reviewed ? '核对完整参数后批准，宿主可在策略允许时显式领取并执行一次。页面不执行工具；已领取可能表示结果未知，不可重试。' : '此处仅持久化审批决定，不执行工具。批准不会覆盖 Runtime 策略；此类准备记录不能恢复执行，需要执行时请另建执行审批。' }}</p>
  <section v-if="!connected" class="connect-card panel"><p class="eyebrow">INDEPENDENT REVIEWER ACCESS</p><h2>连接审批收件箱</h2><p>使用独立 reviewer 凭证。身份由 Collector 配置，凭证仅保存在当前页面。</p><form class="connect-form" @submit.prevent="connect"><label for="review-token">Reviewer token</label><div><input id="review-token" v-model="draft" type="password" autocomplete="off" required :disabled="busy" /><button class="primary-button" :disabled="busy">{{ busy ? '正在连接…' : '连接审批' }}</button></div></form></section>
  <div v-else class="approval-session"><span class="muted small">{{ list?.total ?? '—' }} 条请求 · 审批凭证独立</span><button class="text-button" @click="disconnect">断开审批</button></div>
  <p v-if="actionId" class="notice approval-boundary">精确查询 Action <span class="mono">{{ actionId }}</span> · <a href="#/reviewed-actions">查看全部执行审批</a><template v-if="updatedAt"> · 查询于 {{ updatedAt }}</template></p>
  <section v-if="connected && !actionId" class="queue-toolbar" aria-label="本页审批筛选">
    <div class="queue-stats"><span>本页 {{ list ? pageCounts.total : '—' }} 条</span><span>待审核 <strong>{{ list ? pageCounts.pending : '—' }}</strong></span><span>已批准 {{ list ? pageCounts.approved : '—' }}</span><span>已拒绝 {{ list ? pageCounts.rejected : '—' }}</span><span>已过期 {{ list ? pageCounts.expired : '—' }}</span></div>
    <div class="queue-controls"><label>搜索本页审批<input v-model="queueQuery" maxlength="128" placeholder="摘要、工具、身份或 Action ID" :disabled="busy" /></label><label>本页审批状态<select v-model="queueStatus" :disabled="busy"><option value="">全部状态</option><option value="pending">待审核</option><option value="approved">已批准</option><option value="rejected">已拒绝</option><option value="expired">已过期</option></select></label><label>本页排序<select v-model="queueOrder" :disabled="busy"><option value="received">原始顺序</option><option value="pending">待审核优先</option><option value="expires">到期时间升序</option></select></label><button class="text-button" :disabled="busy" @click="clearQueue">重置本页视图</button></div>
    <p class="muted small">仅筛选和排序已载入的当前页；全部 {{ list?.total ?? '—' }} 条请求请通过分页查看。</p><p class="queue-snapshot">{{ updatedAt ? `查询完成 ${updatedAt} · 这是上次查询的快照，请手动刷新确认状态。` : '尚未获得本次查询结果。' }}</p>
  </section>
  <p v-if="error" class="notice error-notice" role="alert">{{ error }}</p>
  <div v-if="connected" class="approval-list" :aria-busy="busy">
    <article v-for="item in visible" :key="item.action_id" class="panel approval-card">
      <div class="panel-heading queue-heading"><h2><button class="queue-title" type="button" :aria-expanded="expanded === item.action_id" :aria-controls="'review-' + item.action_id" :disabled="busy" @click="toggleReview(item.action_id)">{{ item.summary }}<span>{{ expanded === item.action_id ? '收起' : '展开审核' }}</span></button></h2><span class="approval-state" :class="item.status">{{ approvalDecisionLabel(item) }}</span></div>
      <div class="queue-meta"><strong v-if="isReviewed(item)">{{ executionLabels[item.execution_state] }}</strong><span>{{ item.tool }} <span class="muted">/ {{ item.permission }}</span></span><span>{{ item.subject }}</span><span class="mono">{{ item.action_id.slice(0, 12) }}…</span><span>到期 <time :datetime="item.expires_at" :title="item.expires_at">{{ new Date(item.expires_at).toLocaleString() }}</time></span></div>
      <div v-if="expanded === item.action_id" :id="'review-' + item.action_id" class="review-expanded">
      <section v-if="isReviewed(item)" class="review-context" aria-label="完整执行参数"><div class="review-meta"><strong>{{ executionLabels[item.execution_state] }}</strong><span>工具版本 {{ item.tool_revision }}</span></div><h3>将传给工具的完整参数（含默认值）</h3><pre>{{ reviewText(item.review_arguments) }}</pre><p class="muted small mono">参数审阅摘要 {{ item.review_digest }}</p><p v-if="item.executor" class="muted small">执行身份 {{ item.executor }} · 领取 {{ new Date(item.claimed_at!).toLocaleString() }}<span v-if="item.finished_at"> · 结果确认 {{ new Date(item.finished_at).toLocaleString() }}</span></p><label v-if="item.status === 'pending'" class="review-ack"><input v-model="acknowledged[item.action_id]" type="checkbox" :disabled="busy" />我已核对完整参数与工具版本</label></section>
      <dl class="approval-properties">
        <div><dt>主体</dt><dd>{{ item.subject }}</dd></div>
        <div><dt>工具 / 权限</dt><dd>{{ item.tool }} / {{ item.permission }}</dd></div>
        <div><dt>策略版本</dt><dd>{{ item.policy_revision }}</dd></div>
        <div><dt>有效期 · 本地时间</dt><dd>{{ new Date(item.created_at).toLocaleString() }} → {{ new Date(item.expires_at).toLocaleString() }}</dd></div>
        <div><dt>Action ID</dt><dd><CopyValue :value="item.action_id" label="Action ID" /></dd></div>
        <div v-if="item.reviewer"><dt>决定记录</dt><dd>{{ item.reviewer }} · {{ new Date(item.decided_at!).toLocaleString() }}</dd></div>
        <div><dt>关联治理事件</dt><dd><a :href="queryHash('security-events',{...emptySecurityFilters(),action_id:item.action_id},0)">按 Action 查询事件 ↗</a></dd></div>
        <div v-if="item.trace_id"><dt>关联追踪</dt><dd><a :href="'#/traces/' + item.trace_id">查看 Trace ↗</a></dd></div>
      </dl>
      <details class="review-binding"><summary>参数与策略绑定</summary><dl><dt>参数 HMAC</dt><dd class="mono">{{ item.arguments_hmac }}</dd><dt>策略摘要</dt><dd class="mono">{{ item.policy_digest }}</dd></dl></details>
      <div v-if="item.status === 'pending'" class="approval-actions"><button class="secondary-button" :disabled="busy || (isReviewed(item) && !acknowledged[item.action_id])" @click="decide(item, 'rejected')">{{ props.reviewed ? '拒绝本次动作' : '记录拒绝' }}</button><button class="primary-button" :disabled="busy || (isReviewed(item) && !acknowledged[item.action_id])" @click="decide(item, 'approved')">{{ props.reviewed ? '批准本次动作' : '记录批准' }}</button></div>
      </div>
    </article>
    <div v-if="!visible.length && !error" class="panel empty-state"><h3>{{ busy ? '正在读取审批记录…' : actionId ? '未找到这个执行审批动作' : queueQuery || queueStatus ? '本页没有匹配的审批' : '暂无审批请求' }}</h3></div>
    <footer v-if="!actionId" class="table-footer"><span>第 {{ offset / 20 + 1 }} 页</span><div><button class="page-button" :disabled="busy || !offset" aria-label="审批上一页" @click="page(-1)">←</button><button class="page-button" :disabled="busy || !list || offset + 20 >= list.total || offset >= 10000" aria-label="审批下一页" @click="page(1)">→</button></div></footer>
  </div>
</template>

<style scoped>
.approval-boundary { border: 1px solid var(--border); background: var(--surface-subtle); color: var(--muted); line-height: 1.7; margin-bottom: 24px }
.approval-boundary .mono { overflow-wrap: anywhere }
.approval-boundary a { text-decoration: underline }
.approval-session { display: flex; justify-content: space-between; align-items: center; margin: 22px 0 }
.approval-list { display: grid; gap: 10px }
.approval-card { overflow: hidden }
.approval-card h2 { overflow-wrap: anywhere; line-height: 1.5 }
.queue-snapshot{font-size:10px;color:var(--muted);margin-top:5px}
.review-binding{margin:16px 24px;border-top:1px solid var(--border);padding-top:12px;font-size:11px;color:var(--muted)}.review-binding summary{cursor:pointer;min-height:26px}.review-binding dl{display:grid;grid-template-columns:110px minmax(0,1fr);gap:10px;margin-top:10px}.review-binding dd{margin:0;color:var(--text-primary);overflow-wrap:anywhere;font-size:10px}
.approval-properties { padding: 0 24px; display: grid; gap: 14px }
.approval-properties div { display: grid; grid-template-columns: 140px 1fr; gap: 16px }
.approval-properties dt { color: var(--muted); font-size: 12px }
.approval-properties dd { margin: 0; font-size: 13px; overflow-wrap: anywhere }
.review-context { padding: 18px 24px; border-bottom: 1px solid var(--border) }
.review-meta { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 12px; font-size: 13px }
.review-context h3 { font-size: 13px; margin-top: 20px }
.review-context pre { white-space: pre-wrap; overflow-wrap: anywhere; padding: 16px; background: var(--surface-subtle); border-radius: 6px; line-height: 1.6; font-size: 13px }
.review-context p { overflow-wrap: anywhere }
.review-ack { display: flex; align-items: center; gap: 8px; font-size: 13px; margin-top: 18px }
.review-ack input { width: auto }
.approval-actions { padding: 18px 24px; display: flex; gap: 12px; justify-content: flex-end; border-top: 1px solid var(--border) }
@media (max-width: 760px) { .approval-properties div { grid-template-columns: 1fr; gap: 5px }.queue-controls>.text-button{grid-column:span 2;justify-self:end}.review-binding dl{grid-template-columns:1fr;gap:5px}.review-binding dd{margin-bottom:7px} }
</style>
