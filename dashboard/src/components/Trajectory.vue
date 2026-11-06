<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { displayName, formatDuration, spanColor, spanOutcome, statusLabel, type TreeRow } from '../domain'
import { adjacentNode } from '../traceExplorer'
import { chronological, laneOf, position, trajectoryLanes } from '../trajectory'

const props = defineProps<{ rows: TreeRow[]; origin: bigint; duration: bigint; selected: string }>()
const emit = defineEmits<{ select: [id: string] }>()
const pageSize = 50
const page = ref(0)
const ledger = ref<HTMLElement>()
const ordered = computed(() => chronological(props.rows))
const lastPage = computed(() => Math.max(0, Math.ceil(ordered.value.length / pageSize) - 1))
const visible = computed(() => ordered.value.slice(page.value * pageSize, (page.value + 1) * pageSize))
const focusable = computed(() => visible.value.some(row => row.span.span_id === props.selected) ?
  props.selected : visible.value[0]?.span.span_id)
const markers = computed(() => visible.value.flatMap(({ span }) => {
  const interval = position(span, props.origin, props.duration)
  return interval ? [{ span, interval, lane: laneOf(span) }] : []
}))

function reveal(id: string) {
  const index = ordered.value.findIndex(row => row.span.span_id === id)
  page.value = index < 0 ? Math.min(page.value, lastPage.value) : Math.floor(index / pageSize)
}
watch([ordered, () => props.selected], () => reveal(props.selected), { immediate: true })

async function focusNode(id: string) {
  reveal(id)
  await nextTick()
  Array.from(ledger.value?.querySelectorAll<HTMLButtonElement>('[data-span-id]') ?? [])
    .find(button => button.dataset.spanId === id)?.focus()
}
defineExpose({ focusNode })

async function choose(id: string, focus = false) {
  emit('select', id)
  if (focus) await focusNode(id)
}
function onKey(event: KeyboardEvent, id: string) {
  const target = adjacentNode(ordered.value, id, event.key)
  if (!target) return
  event.preventDefault()
  void choose(target, true)
}
</script>

<template>
  <div class="trajectory">
    <section class="trajectory-overview" aria-label="轨迹时间总览">
      <div class="trajectory-caption"><strong>时间总览</strong><span>本页节点 · 全 Trace 尺度</span></div>
      <div class="trajectory-scale"><span>0 ns</span><span>{{ formatDuration(duration) }}</span></div>
      <div v-for="lane in trajectoryLanes" :key="lane" class="trajectory-lane">
        <span>{{ lane }}</span>
        <div class="trajectory-track">
          <button v-for="mark in markers.filter(item => item.lane === lane)" :key="mark.span.span_id" type="button"
            :style="{ left: mark.interval.left + '%', width: mark.interval.width + '%', background: spanColor(mark.span) }"
            tabindex="-1" :aria-pressed="selected === mark.span.span_id" :aria-label="'定位 ' + displayName(mark.span.name)"
            :title="displayName(mark.span.name)" @click="choose(mark.span.span_id, true)" />
        </div>
      </div>
    </section>
    <div ref="ledger" class="trajectory-ledger" role="group" aria-label="按时间排列的执行步骤">
      <button v-for="row in visible" :key="row.span.span_id" type="button" class="trajectory-step"
        :data-span-id="row.span.span_id" :aria-pressed="selected === row.span.span_id"
        :tabindex="focusable === row.span.span_id ? 0 : -1" @click="choose(row.span.span_id)"
        @keydown="onKey($event, row.span.span_id)">
        <span class="step-lane" :style="{ color: spanColor(row.span) }">{{ laneOf(row.span) }}</span>
        <span class="step-name"><strong>{{ displayName(row.span.name) }}</strong>
          <small>{{ statusLabel(row.span.status, spanOutcome(row.span)) }}<template v-if="row.relation !== 'normal'"> · 父子关系不完整</template></small>
        </span>
        <span class="mono step-time">{{ position(row.span, origin, duration) ? formatDuration(row.span.end_time_unix_nano - row.span.start_time_unix_nano) : '时间未知' }}</span>
      </button>
    </div>
    <div v-if="lastPage" class="table-footer">
      <span>步骤 {{ page * pageSize + 1 }}–{{ page * pageSize + visible.length }} / {{ ordered.length }}</span>
      <div><button class="page-button" :disabled="page === 0" aria-label="轨迹上一页" @click="page--">←</button>
        <button class="page-button" :disabled="page === lastPage" aria-label="轨迹下一页" @click="page++">→</button></div>
    </div>
  </div>
</template>

<style scoped>
.trajectory { padding: 12px; }
.trajectory-overview { padding: 12px; background: var(--surface-subtle); border: 1px solid var(--border); border-radius: 6px; }
.trajectory-caption, .trajectory-scale { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; }
.trajectory-caption span, .trajectory-scale, .trajectory-lane, .step-time, .step-name small { color: var(--muted); }
.trajectory-scale { margin: 10px 0 3px 48px; }
.trajectory-lane { display: grid; grid-template-columns: 40px minmax(0,1fr); gap: 8px; align-items: center; font-size: 11px; }
.trajectory-track { height: 22px; position: relative; border-bottom: 1px solid var(--border); }
.trajectory-track button { position: absolute; top: 5px; height: 12px; padding: 0; min-width: 3px; border: 0; border-radius: 2px; opacity: .75; }
.trajectory-track button[aria-pressed=true] { opacity: 1; box-shadow: 0 0 0 1px currentColor; z-index: 1; }
.trajectory-ledger { margin-top: 12px; }
.trajectory-step { width: 100%; display: grid; grid-template-columns: 46px minmax(0,1fr) auto; gap: 8px; align-items: center; text-align: left; min-height: 43px; padding: 6px 9px; border: 0; border-bottom: 1px solid var(--border); background: none; }
.trajectory-step:hover, .trajectory-step[aria-pressed=true] { background: var(--surface-subtle); }
.trajectory-step[aria-pressed=true] { box-shadow: inset 2px 0 var(--accent, #a39cc7); }
.step-lane, .step-time, .step-name small { font-size: 10px; }
.step-name strong { display: block; overflow-wrap: anywhere; font-size: 12px; }
.step-name small { display: block; margin-top: 2px; }
</style>
