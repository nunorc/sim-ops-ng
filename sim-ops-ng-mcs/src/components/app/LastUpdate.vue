<script setup lang="ts">
import { computed } from 'vue';
import { useSocketStore } from '@/stores/app-websockets';

// Simulated time of the last spacecraft telemetry received
const socketStore = useSocketStore();

const lastUpdate = computed(() => {
	const ts = socketStore.sc_ts;
	if (typeof ts !== 'number' || !Number.isFinite(ts) || ts <= 0) return '_';
	return new Date(ts * 1000).toISOString().replace('T', ' ').replace(/\.\d+Z$/, '') + ' UTC';
});
</script>
<template>
	<div class="row mt-3">
		<div class="col">
			<span class="badge rounded-0 bg-secondary">Last Update</span>
			<span class="badge rounded-0 bg-dark">{{ lastUpdate }}</span>
		</div>
	</div>
</template>
