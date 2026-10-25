<script setup lang="ts">
import { useSocketStore } from '@/stores/app-websockets';

// WebSocket connection and (optionally) downlink lock badges for a view's page header
withDefaults(defineProps<{ downlink?: boolean }>(), { downlink: true });

const socketStore = useSocketStore();
const LOCKING = ['PLL_LOCK', 'PSK_LOCK', 'BIT_LOCK', 'RF_DETECTED'];
</script>
<template>
	<small class="float-end">
		<span class="badge rounded-0 bg-secondary">WS</span>
		<span class="badge rounded-0" :class="socketStore.connected ? 'bg-success' : 'bg-danger'">{{ socketStore.status }}</span>
		<template v-if="downlink">
			<span class="badge rounded-0 bg-secondary ms-1">D/L</span>
			<span v-if="socketStore.data_proxy === 'EGSE'" class="badge rounded-0 bg-dark">--</span>
			<span v-else-if="socketStore.gs_state && socketStore.gs_state.status_dl" class="badge rounded-0 text-uppercase" :class="{ 'text-bg-danger': socketStore.gs_state.status_dl === 'NO_RF', 'text-bg-warning': LOCKING.includes(socketStore.gs_state.status_dl), 'text-bg-success': socketStore.gs_state.status_dl === 'FRAME_LOCK' }">{{ socketStore.gs_state.status_dl }}</span>
			<span v-else class="badge rounded-0 bg-dark">_</span>
		</template>
	</small>
</template>
