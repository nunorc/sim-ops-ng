<script setup lang="ts">
import TelemetryStatus from '@/components/app/TelemetryStatus.vue';
import LastUpdate from '@/components/app/LastUpdate.vue';
import apexchart from '@/components/plugins/Apexcharts.vue';
import { useSpacecraftView, useSparkline } from '@/composables/spacecraft-view';

const { loading, state, compact } = useSpacecraftView('view-DHS-state');

const chartMemory = useSparkline('Memory', 'dhs_memory');
const chartTMcount = useSparkline('TM counter', 'dhs_tm_counter');
const chartTCcount = useSparkline('TC counter', 'dhs_tc_counter');
</script>
<template>

	<h1 class="page-header">
		<span v-if="loading" class="spinner-border text-secondary app-fs-small" role="status"><span class="visually-hidden">Loading...</span></span>
		DHS <small class="d-none d-md-inline">Data Handling Subsystem</small>
		<telemetry-status />
	</h1>
	<hr class="mb-4">

	<div class="row" v-if="!compact">
		<div class="col-xl-6 col-lg-6">
			<div class="row">
					<div class="col-xl-4 col-lg-4">
						<card class="mb-3">
							<card-header class="card-header fw-bold small text-center p-1">DHS Chain</card-header>
							<card-body class="p-2 mx-2">
								<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.dhs_chain }}</span>
								<span v-else>_</span>
							</card-body>
						</card>
					</div>
					<div class="col-xl-4 col-lg-4">
						<card class="mb-3">
							<card-header class="card-header fw-bold small text-center p-1">OBSW Mode</card-header>
							<card-body class="p-2 mx-2">
								<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.dhs_obsw_mode === 'nominal', 'bg-danger': state.dhs_obsw_mode !== 'nominal'}">{{ state.dhs_obsw_mode }}</span>
								<span v-else>_</span>
							</card-body>
						</card>
					</div>
					<div class="col-xl-4 col-lg-4">
						<card class="mb-3">
							<card-header class="card-header fw-bold small text-center p-1">Memory Dump</card-header>
							<card-body class="p-2 mx-2">
								<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.dhs_mem_dump_enabled, 'bg-danger': !state.dhs_mem_dump_enabled }">{{ state.dhs_mem_dump_enabled ? 'Enabled' : 'Disabled' }}</span>
								<span v-else>_</span>
							</card-body>
						</card>
					</div>
			</div>
			<div class="row">
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">TM Counter</card-header>
						<card-body>
							<div class="row align-items-center" v-if="state">
								<h3 class="mb-0 text-center">{{ state.dhs_tm_counter }}</h3>
								<div class="mt-1">
									<apexchart :height="chartTMcount.height" :options="chartTMcount.options" :series="chartTMcount.series"></apexchart>
								</div>
							</div>
						</card-body>
					</card>
				</div>
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">TC Counter</card-header>
						<card-body>
							<div class="row align-items-center" v-if="state">
								<h3 class="mb-0 text-center">{{ state.dhs_tc_counter }}</h3>
								<div class="mt-1">
									<apexchart :height="chartTCcount.height" :options="chartTCcount.options" :series="chartTCcount.series"></apexchart>
								</div>
							</div>
						</card-body>
					</card>
				</div>
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">Memory Usage</card-header>
						<card-body>
							<div class="row align-items-center" v-if="state">
								<h3 class="mb-0 text-center">{{ state.dhs_memory.toFixed(3) }}%</h3>
								<div class="mt-1">
									<apexchart :height="chartMemory.height" :options="chartMemory.options" :series="chartMemory.series"></apexchart>
								</div>
							</div>
						</card-body>
					</card>
				</div>
			</div>
		</div>
		<div class="col-xl-6 col-lg-6">
			<div class="col-xl-12 col-lg-12s">
			<card class="mb-3" style="min-height: 203px;">
				<card-header>Scheduled Time Tagged Files</card-header>
				<card-body class="mb-1">
					<table class="table table-sm table-striped table-borderless mb-2px small text-nowrap">
						<tbody v-if="state">
							<tr v-for="(row, i) in state.dhs_uploaded" :key="i">
								<td>{{ row }}</td>
							</tr>
							<tr v-if="state.dhs_uploaded.length === 0">
								<td>None</td>
							</tr>
						</tbody>
					</table>
				</card-body>
			</card>
		</div>
		</div>
	</div>

	<div class="row" v-if="compact">
		<div class="col-sm-4">
			<card class="mb-3">
				<card-body class="">
					<table class="table text-nowrap mb-0">
						<tbody>
							<tr>
								<td class="app-w-col">DHS Chain</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.dhs_chain }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>OBSW Mode</td>
								<td v-if="state"><div class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.dhs_obsw_mode === 'nominal', 'bg-danger': state.dhs_obsw_mode !== 'nominal'}">{{ state.dhs_obsw_mode }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Memory Dump</td>
								<td v-if="state"><div class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.dhs_mem_dump_enabled, 'bg-danger': !state.dhs_mem_dump_enabled }">{{ state.dhs_mem_dump_enabled ? 'Enabled' : 'Disabled' }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Memory Usage</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.dhs_memory.toFixed(3) }}%</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>TM Counter</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.dhs_tm_counter }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>TC Counter</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.dhs_tc_counter }}</div></td>
								<td v-else>_</td>
							</tr>
						</tbody>
					</table>
				</card-body>
			</card>
		</div>

		<div class="col-sm-4">
			<card class="mb-3">
				<card-header>Scheduled Time Tagged Files</card-header>
				<card-body class="mb-1">
					<table class="table table-sm table-striped table-borderless mb-2px small text-nowrap">
						<tbody v-if="state">
							<tr v-for="(row, i) in state.dhs_uploaded" :key="i">
								<td>{{ row }}</td>
							</tr>
							<tr v-if="state.dhs_uploaded.length === 0">
								<td>None</td>
							</tr>
						</tbody>
					</table>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row">
		<div class="col-xl-6 col-lg-6">
			<card class="mb-3">
				<card-header>TM History</card-header>
				<card-body class="mb-1">
					<table class="table table-sm table-striped table-borderless mb-2px small text-nowrap">
						<tbody v-if="state">
							<tr v-for="(row, i) in state.dhs_tm_window" :key="i">
								<td>{{ row }}</td>
							</tr>
						</tbody>
					</table>
				</card-body>
			</card>
		</div>
		<div class="col-xl-6 col-lg-6">
			<card class="mb-3">
				<card-header>TC History</card-header>
				<card-body class="mb-1">
					<table class="table table-sm table-striped table-borderless mb-2px small text-nowrap">
						<tbody v-if="state">
							<tr v-if="state && state.dhs_tc_history.length === 0">
								<td>None</td>
							</tr>
							<tr v-for="(row, i) in state.dhs_tc_history" :key="i">
								<td>{{ row }}</td>
							</tr>
						</tbody>
					</table>
				</card-body>
			</card>
		</div>
	</div>

	<last-update />

</template>

<style>
.app-w-col { width: 70%; }
.app-badge { font-size: 0.7rem; font-weight: 600; text-align: center; padding: 2px; }
.app-fs-small { font-size: small; }
</style>
