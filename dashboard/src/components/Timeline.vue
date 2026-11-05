<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { init, use } from 'echarts/core'
import type { ECharts, EChartsCoreOption } from 'echarts/core'
import { CustomChart } from 'echarts/charts'
import { GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { TreeRow } from '../domain'
import { relativeMillis, spanColor } from '../domain'

use([CustomChart, GridComponent, CanvasRenderer])
const props = withDefaults(defineProps<{ rows: TreeRow[]; origin: bigint; duration: bigint; selected: string; rowHeight?: number }>(), { rowHeight: 46 })
const emit = defineEmits<{ select: [id: string] }>()
const container = ref<HTMLDivElement>()
let chart: ECharts | undefined, observer: ResizeObserver | undefined
function render() {
  if (!chart) return
  const maximum = Math.max(relativeMillis(props.origin + props.duration, props.origin), 0.000001)
  const options: EChartsCoreOption = {
    animation: false,
    grid: { top: 26, bottom: 12, left: 12, right: 22 },
    xAxis: { min: 0, max: maximum, position: 'top', type: 'value', axisLabel: { color: '#8d969e', fontSize: 10, formatter: (value: number) => `${Number(value.toPrecision(3))} ms` }, splitNumber: 3, splitLine: { lineStyle: { color: '#2b3035', type: 'dashed' } } },
    yAxis: { type: 'category', data: props.rows.map(row => row.span.span_id), inverse: true, show: false },
    series: [{
      type: 'custom', silent: false,
      data: props.rows.map((row, index) => ({ value: [index, relativeMillis(row.span.start_time_unix_nano, props.origin), relativeMillis(row.span.end_time_unix_nano, props.origin)], itemStyle: { color: spanColor(row.span) } })),
      renderItem: (_params: unknown, api: { value: (n: number) => number; coord: (values: number[]) => number[] }) => {
        const start = api.coord([api.value(1), api.value(0)]), end = api.coord([api.value(2), api.value(0)])
        const row = props.rows[api.value(0)]!, selected = row.span.span_id === props.selected
        const fill = spanColor(row.span)
        return { type: 'rect', shape: { x: start[0], y: start[1] - 7, width: Math.max(3, end[0] - start[0]), height: 14, r: 3 }, style: { fill, opacity: selected ? 1 : 0.7, stroke: selected ? '#e8e8e8' : 'transparent', lineWidth: 1 } }
      },
    }],
  }
  chart.setOption(options, true)
}
onMounted(() => {
  chart = init(container.value!)
  chart.on('click', (event: { dataIndex: number }) => { const row = props.rows[event.dataIndex]; if (row) emit('select', row.span.span_id) })
  observer = new ResizeObserver(() => chart?.resize()); observer.observe(container.value!)
  render()
})
watch(() => [props.rows, props.origin, props.duration, props.selected, props.rowHeight], render)
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>

<template><div ref="container" class="timeline-chart" role="img" aria-label="Span 相对执行时间线；可使用左侧节点按钮选择" :style="{ height: `${rows.length * rowHeight + 38}px` }" /></template>
