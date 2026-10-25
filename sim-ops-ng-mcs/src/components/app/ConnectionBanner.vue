<script setup lang="ts">
import { computed } from 'vue';
import { useSocketStore } from '@/stores/app-websockets';

const socketStore = useSocketStore();

const message = computed(() => {
	if (socketStore.status !== 'reconnecting') return null;
	const seconds = Math.round(socketStore.retryDelayMs / 1000);
	const reason = socketStore.unreachable ? 'Server unreachable' : 'Connection to the server lost';
	return `${reason}: retrying every ${seconds}s. Values shown are from before the drop.`;
});
</script>
<template>
	<div v-if="message" class="alert alert-danger rounded-0 py-2 mb-3 small" role="status">
		<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>{{ message }}
	</div>
</template>
