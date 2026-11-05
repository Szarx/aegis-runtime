<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ title: string; activeCount: number }>()
const expanded = ref(typeof window === 'undefined' || !window.matchMedia('(max-width: 760px)').matches)
function toggle(event: Event) { expanded.value = (event.target as HTMLDetailsElement).open }
</script>

<template>
  <details class="query-filters" :open="expanded" @toggle="toggle">
    <summary><span>{{ title }}</span><small>{{ activeCount ? `已应用 ${activeCount} 项筛选` : '未应用筛选' }}</small></summary>
    <slot />
  </details>
</template>

<style scoped>
.query-filters.panel{margin-bottom:16px}.query-filters>summary{display:flex;align-items:center;gap:10px;list-style:none;cursor:pointer;min-height:42px;padding:10px 16px;border-bottom:1px solid var(--border);font-size:11px;color:var(--text-primary)}.query-filters>summary::-webkit-details-marker{display:none}.query-filters>summary::before{content:'';width:5px;height:5px;border-right:1px solid var(--muted);border-bottom:1px solid var(--muted);transform:rotate(-45deg);margin-right:2px}.query-filters[open]>summary::before{transform:rotate(45deg);margin-top:-3px}.query-filters>summary:hover{background:var(--surface-hover)}.query-filters>summary small{margin-left:auto;color:var(--muted);font-size:10px}.query-filters>summary:focus-visible{outline:2px solid var(--accent);outline-offset:-3px}
</style>
