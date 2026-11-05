<script setup lang="ts">
import { statusLabel } from '../domain'
defineProps<{ status: string; outcome?: string | bigint | null }>()
</script>
<template><span class="status-badge" :class="status === 'ERROR' ? 'error' : outcome === 'closed' || outcome === 'incomplete' || outcome === 'awaiting_approval' ? 'warning' : 'success'" :title="status + (outcome ? ' / ' + outcome : '')"><i />{{ statusLabel(status, outcome) }}</span></template>
