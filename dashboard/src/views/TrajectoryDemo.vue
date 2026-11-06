<script setup lang="ts">
import { computed } from 'vue'
import type { Span, TraceDetail as Detail } from '../api/types'
import TraceDetail from './TraceDetail.vue'

const props = defineProps<{ hash: string }>()
const requestId = '1'.repeat(32), executionId = '2'.repeat(32), actionId = 'a'.repeat(32)
const base = 1793577600000000000n
const at = (ms: number) => base + BigInt(ms) * 1_000_000n

function step(traceId: string, index: number, name: string, operation: Span['operation'],
  start: number, end: number, attributes: Span['attributes'] = {}): Span {
  return {
    trace_id: traceId, span_id: index.toString(16).padStart(16, '0'),
    parent_span_id: index === 1 ? null : '1'.padStart(16, '0'),
    name, operation, kind: operation === 'chat' ? 'CLIENT' : 'INTERNAL', status: 'UNSET',
    service_name: 'synthetic-demo', agent_name: '退款助手 · 合成演示',
    start_time_unix_nano: at(start), end_time_unix_nano: at(end),
    attributes, resource: {}, scope: {}, events: [],
  }
}

function reviewed(phase: 'request' | 'execute'): Span['attributes'] {
  return {
    'aegis.mapping.version': 'aegis.governance.v2',
    'aegis.approval.phase': phase,
    'aegis.action.id': actionId,
    'aegis.action.outcome': phase === 'request' ? 'awaiting_approval' : 'completed',
    'aegis.decision.effect': 'require_approval',
    'aegis.decision.reason': 'explicit_require_approval',
    'aegis.decision.rule_id': 'refund-write-review',
    'aegis.policy.revision': 'demo-policy-v2',
    'aegis.subject.id': 'demo-agent',
    'aegis.tool.permission': 'orders.refund',
  }
}

function detail(spans: Span[], signal: Detail['trace']['governance_signal']): Detail {
  const root = spans[0]!
  return { spans, missing_parent_ids: [], trace: {
    trace_id: root.trace_id, start_time_unix_nano: root.start_time_unix_nano,
    end_time_unix_nano: root.end_time_unix_nano,
    duration_ns: root.end_time_unix_nano - root.start_time_unix_nano,
    span_count: spans.length, status: 'UNSET', agent_names: [root.agent_name!], governance_signal: signal,
  } }
}

const request = detail([
  step(requestId, 1, '退款请求', 'invoke_agent', 0, 1440),
  step(requestId, 2, '判断退款流程', 'chat', 10, 1210, {
    'aegis.mapping.version': 'aegis.genai.v2', 'aegis.call.outcome': 'completed',
    'gen_ai.provider.name': 'synthetic', 'gen_ai.request.model': 'demo-model',
    'gen_ai.response.model': 'demo-model', 'aegis.call.api': 'demo',
    'gen_ai.usage.input_tokens': 120n, 'gen_ai.usage.output_tokens': 18n,
  }),
  step(requestId, 3, '查询订单', 'execute_tool', 1220, 1360),
  step(requestId, 4, '申请执行退款', 'execute_tool', 1370, 1420, reviewed('request')),
], 'approval_requested')
const execution = detail([
  step(executionId, 1, '宿主恢复退款', 'invoke_agent', 22000, 22250),
  step(executionId, 2, '执行合成退款', 'execute_tool', 22030, 22230, reviewed('execute')),
], 'review_tool_returned')
const selected = computed(() => props.hash === '#/demo/execution' ? execution : request)
</script>

<template>
  <section class="demo-banner panel">
    <div><p class="eyebrow">只读合成演示</p><strong>退款助手的请求、批准和恢复</strong></div>
    <a href="#/traces" class="back-link">← 返回工作区</a>
    <p>在请求轨迹找出最慢调用，点开治理步骤查看审批规则，再核对工具执行结果。</p>
    <nav aria-label="演示阶段">
      <a v-for="[href, label] in [['#/demo', '请求轨迹'], ['#/demo/approval', '审批结果'], ['#/demo/execution', '恢复轨迹']]" :key="href"
        :href="href" :aria-current="hash === href ? 'page' : undefined">{{ label }}</a>
    </nav>
  </section>
  <section v-if="hash === '#/demo/approval'" class="panel demo-approval">
    <h1>演示审批结果</h1>
    <p class="mono">Action {{ actionId }}</p>
    <ol>
      <li><strong>请求审核</strong><span>规则 refund-write-review 要求人工审批。</span></li>
      <li><strong>人工已批准</strong><span>审批决定记录于演示起点后 20 秒。</span></li>
      <li><strong>已确认完成</strong><span>宿主在第 22 秒领取并恢复，工具返回后确认完成。</span></li>
    </ol>
    <a href="#/demo/execution">查看恢复轨迹 ↗</a>
  </section>
  <TraceDetail v-else :key="selected.trace.trace_id" :detail="selected" demo />
</template>

<style scoped>
.demo-banner { display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;padding:16px;margin-bottom:18px }
.demo-banner p,.demo-approval p,.demo-approval li span{color:var(--muted);font-size:12px}
.demo-banner > p,.demo-banner nav{grid-column:1 / -1}
.demo-banner nav{display:flex;flex-wrap:wrap;gap:8px}
.demo-banner nav a{border:1px solid var(--border);border-radius:4px;padding:6px 9px}
.demo-banner nav a[aria-current=page]{background:var(--surface-subtle);border-color:#8c80aa}
.demo-approval{padding:20px}
.demo-approval p{overflow-wrap:anywhere;margin-top:8px}
.demo-approval ol{display:grid;gap:16px;margin:18px 0;padding-left:22px}
.demo-approval li span{display:block;margin-top:4px}
.demo-approval a{text-decoration:underline}
</style>
