<script setup lang="ts">
import TelemetryStatus from '@/components/app/TelemetryStatus.vue';
import LastUpdate from '@/components/app/LastUpdate.vue';
import apexchart from '@/components/plugins/Apexcharts.vue';
import { useSpacecraftView, useSparkline } from '@/composables/spacecraft-view';

const { loading, state, compact } = useSpacecraftView('view-EPS-state');

const chartBattery = useSparkline('Battery', 'eps_battery_dod');
const chartPower = useSparkline('Power', 'eps_net_power');
const chartTemperature = useSparkline('Temperature', 'eps_temperature');
</script>
<template>

	<h1 class="page-header">
		<span v-if="loading" class="spinner-border text-secondary app-fs-small" role="status"><span class="visually-hidden">Loading...</span></span>
		EPS <small class="d-none d-md-inline">Electrical Power System</small>
		<telemetry-status />
	</h1>
	<hr class="mb-4">

	<div class="row" v-if="!compact">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">EPS Chain</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_chain }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Solar Array 1</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_sol_array[0] }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Solar Array 2</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_sol_array[1] }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row" v-if="!compact">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Battery DOD</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state">
						<h3 class="mb-0 text-center">{{ state.eps_battery_dod.toFixed(2) }}%</h3>
						<div class="mt-1">
							<apexchart :height="chartBattery.height" :options="chartBattery.options" :series="chartBattery.series"></apexchart>
						</div>
					</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Net Power</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state">
						<h3 class="mb-0 text-center">{{ state.eps_net_power.toFixed(2) }}</h3>
						<div class="mt-1">
							<apexchart :height="chartPower.height" :options="chartPower.options" :series="chartPower.series"></apexchart>
						</div>
					</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Temperature</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state">
						<h3 class="mb-0 text-center">{{ state.eps_temperature.toFixed(2) }}°C</h3>
						<div class="mt-1">
							<apexchart :height="chartTemperature.height" :options="chartTemperature.options" :series="chartTemperature.series"></apexchart>
						</div>
					</div>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row" v-if="!compact">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Power Status</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-success': state.eps_power_status === 'power_positive', 'bg-warning': state.eps_power_status === 'power_negative', 'bg-danger': state.eps_power_status === 'power_critical' }">{{ state.eps_power_status }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">ACU Status</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-success': state.eps_acu === 'nominal', 'bg-danger': state.eps_acu !== 'nominal' }">{{ state.eps_acu }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">PDU Status</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-success': state.eps_pdu === 'nominal', 'bg-danger': state.eps_pdu !== 'nominal' }">{{ state.eps_pdu }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row" v-if="!compact">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Power Source</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_power_source === 'S' ? 'Solar Panels' : state.eps_power_source === 'R' ? 'RTG' : 'Unknown' }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row" v-if="compact">
		<div class="col-sm-4">
			<card class="mb-3">
				<card-body class="">
					<table class="table text-nowrap mb-0">
						<tbody>
							<tr>
								<td class="app-w-col">EPS Chain</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_chain }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Solar Array 1</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_sol_array[0] }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Solar Array 2</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_sol_array[1] }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Battery DOD</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_battery_dod.toFixed(2) }}%</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Net Power</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_net_power.toFixed(2) }}%</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Temperature</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_temperature.toFixed(2) }}%</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Power Status</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-success': state.eps_power_status === 'power_positive', 'bg-warning': state.eps_power_status === 'power_negative', 'bg-danger': state.eps_power_status === 'power_critical' }">{{ state.eps_power_status }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>ACU Status</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-success': state.eps_acu === 'nominal', 'bg-danger': state.eps_acu !== 'nominal' }">{{ state.eps_acu }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>PDU Status</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-success': state.eps_pdu === 'nominal', 'bg-danger': state.eps_pdu !== 'nominal' }">{{ state.eps_pdu }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Power Source</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_power_source === 'S' ? 'Solar Panels' : state.eps_power_source === 'R' ? 'RTG' : 'Unknown' }}</div></td>
								<td v-else>_</td>
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
