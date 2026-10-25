<script setup lang="ts">
import { computed } from 'vue';
import { useSocketStore } from '@/stores/app-websockets';
import AckStatus from '@/components/app/AckStatus.vue';

const socketStore = useSocketStore();

// the sim keeps the last TCs executed from the shared stack, newest first
const history = computed(() => socketStore.tc_history || []);

function ppDate(ts: string): string {
	const dt = new Date(ts);
	return Number.isNaN(dt.getTime()) ? ts : dt.toISOString().replace('T', ' ').replace(/\.\d+Z$/, '') + ' UTC';
}
</script>
<template>
	<h1 class="page-header">
		History <small>TC</small>
	</h1>
	<hr class="mb-4">

	<card class="mb-4">
		<card-header class="fw-bold small">Last executed TCs</card-header>
		<card-body>
			<p v-if="history.length === 0" class="text-muted mb-0">No TCs executed yet.</p>
			<table v-else class="table table-sm mb-0">
				<thead>
					<tr>
						<th>Executed</th>
						<th>TC</th>
						<th>Result</th>
					</tr>
				</thead>
				<tbody class="text-body">
					<tr v-for="(h, i) in history" :key="i">
						<td>{{ ppDate(h.ts) }}</td>
						<td>{{ h.command }}</td>
						<td><ack-status :status="h.status" /></td>
					</tr>
				</tbody>
			</table>
		</card-body>
	</card>
</template>
