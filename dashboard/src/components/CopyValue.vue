<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import Icon from './Icon.vue'
const props = withDefaults(defineProps<{ value: string; label: string; showValue?: boolean; buttonText?: string }>(), {showValue:true,buttonText:''})
const feedback = ref(''), copying = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined, active = true, sequence = 0
watch(() => props.value, () => { sequence++; feedback.value = ''; copying.value = false; clearTimeout(timer) })
async function copy() {
  copying.value = true
  const current = ++sequence
  try { await navigator.clipboard.writeText(props.value); if (active && current === sequence) feedback.value = '已复制' }
  catch { if (active && current === sequence) feedback.value = '复制不可用，请手动选择文本' }
  finally {
    if (active && current === sequence) {
      copying.value = false; clearTimeout(timer)
      timer = setTimeout(() => { feedback.value = '' }, 2500)
    }
  }
}
onBeforeUnmount(() => { active = false; clearTimeout(timer) })
</script>
<template><span class="copy-value"><span v-if="showValue || feedback === '复制不可用，请手动选择文本'" class="mono">{{ value }}</span><button class="copy-button" type="button" :aria-label="`复制 ${label}`" :title="`复制 ${label}`" :disabled="copying" @click="copy"><Icon name="copy" :size="13" /><span v-if="buttonText">{{ buttonText }}</span></button><span v-if="feedback" class="copy-feedback" role="status">{{ feedback }}</span></span></template>
<style scoped>.copy-button{display:inline-flex;align-items:center;justify-content:center;gap:5px}.copy-button>span{font-size:10px}</style>
