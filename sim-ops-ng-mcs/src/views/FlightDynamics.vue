<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import axios from 'axios';
import { useAppOptionStore } from '@/stores/app-option';
import { useAuthStore } from '@/stores/app-auth';
import type { FDProduct } from '@/types/obj-store';

const appOption = useAppOptionStore(),
      authStore = useAuthStore();

const data = ref<FDProduct[]>([]);
const loading = ref(true);
const error = ref<Error | null>(null);
let pollInterval: ReturnType<typeof setInterval> | undefined;

function fetchData() {
	axios.get<FDProduct[]>(`${appOption.soAPI}/api/obj-store/fd`, authStore.authConfig())
		.then(response => {
			data.value = response.data;
			error.value = null;
		})
		.catch(e => {
			error.value = e as Error;
		})
		.finally(() => {
			loading.value = false;
		});
}

function ppStatus(status: number): string {
	if (status === 0) return 'Not Processed';
	if (status === 1) return 'Processing';
	if (status === 2) return 'Ready';
	if (status === -1) return 'Failed';
	return 'Unknown';
}

function ppValidity(validity: number): string {
	if (validity === 0) return 'Bad';
	if (validity === 1) return 'Average';
	if (validity === 2) return 'Good';
	return 'Unknown';
}

function statusClass(status: number): string {
	if (status === 2) return 'text-bg-theme';
	if (status === 1) return 'text-bg-warning';
	if (status === -1) return 'text-bg-danger';
	return 'text-bg-secondary';
}

function validityClass(validity: number): string {
	if (validity === 2) return 'text-bg-theme';
	if (validity === 1) return 'text-bg-warning';
	return 'text-bg-danger';
}

onMounted(() => {
	fetchData();
	pollInterval = setInterval(fetchData, 5000);
});

onBeforeUnmount(() => clearInterval(pollInterval));
</script>

<template>
	<h1 class="page-header">Flight Dynamics <small>Products</small></h1>
	<hr class="mb-4">

	<div v-if="loading && data.length === 0" class="text-muted">Loading...</div>

	<div v-if="error" class="alert alert-danger">Failed to load products.</div>

	<template v-if="!loading || data.length > 0">
		<p v-if="data.length === 0" class="text-muted">No products found.</p>

		<card class="mb-3" v-for="d in data" :key="d.id">
			<card-header class="fw-bold">PASS {{ d.id }}</card-header>
			<card-body class="mb-1">
				<div class="row">
					<div class="col-xl-2 col-lg-3">
						<p class="mb-2">
							Status<br/>
							<span class="badge rounded-0 text-uppercase small" :class="statusClass(d.status)">
								{{ ppStatus(d.status) }}
							</span>
						</p>
						<p class="mb-2">
							Validity<br/>
							<span class="badge rounded-0 text-uppercase small" :class="validityClass(d.validity)">
								{{ ppValidity(d.validity) }}
							</span>
						</p>
					</div>
					<div class="col-xl-10 col-lg-9">
						<div class="form-group table-responsive" style="max-height: 200px;">
							<label class="form-label small text-muted">{{ d.data ? d.data.length : 0 }} readings</label>
							<table class="table table-sm small">
								<thead>
									<tr>
										<th>P<sub>x</sub></th>
										<th>P<sub>y</sub></th>
										<th>P<sub>z</sub></th>
										<th>Range (km)</th>
										<th>Doppler (km/s)</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="(row, i) in d.data" :key="i">
										<td v-for="(col, j) in row.slice(0, 5)" :key="j">{{ typeof col === 'number' ? col.toFixed(3) : col }}</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
				</div>
			</card-body>
		</card>
	</template>
</template>
