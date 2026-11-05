<script setup lang="ts">
withDefaults(defineProps<{ name: string; size?: number }>(), { size: 18 })
const paths: Record<string, string> = {
  copy: 'M8 8h12v13H8Z M16 8V3H3v13h5',
  activity: 'M3 12h4l3-8 4 16 3-8h4',
  shield: 'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6Z M9 12l2 2 4-4',
  check: 'M5 12l4 4L19 6',
  clock: 'M12 8v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',
  refresh: 'M20 7v5h-5 M4 17v-5h5 M6 7a7 7 0 0 1 12-1l2 3 M4 15l2 3a7 7 0 0 0 12-1',
  plug: 'M8 3v5 M16 3v5 M6 8h12v3a6 6 0 0 1-12 0Z M12 17v4',
  arrow: 'M5 12h14 M13 6l6 6-6 6',
  layers: 'M12 3 3 8l9 5 9-5Z M3 12l9 5 9-5 M3 16l9 5 9-5',
}
</script>

<template><svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path :d="paths[name] || paths.activity" /></svg></template>
