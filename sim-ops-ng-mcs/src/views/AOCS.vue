<script setup lang="ts">
import TelemetryStatus from '@/components/app/TelemetryStatus.vue';
import LastUpdate from '@/components/app/LastUpdate.vue';
import apexchart from '@/components/plugins/Apexcharts.vue';
import { useSpacecraftView, useSparkline } from '@/composables/spacecraft-view';

const { loading, state, compact } = useSpacecraftView('view-AOCS-state');

const chartRotX = useSparkline('rotation x', 'aocs_rot_x');
const chartRotY = useSparkline('rotation y', 'aocs_rot_y');
const chartRotZ = useSparkline('rotation z', 'aocs_rot_z');
const chartRateX = useSparkline('rate x', 'aocs_rate_x');
const chartRateY = useSparkline('rate y', 'aocs_rate_y');
const chartRateZ = useSparkline('rate z', 'aocs_rate_z');
const chartSunAngle = useSparkline('sun angle', 'aocs_sun_angle');
const chartNadirAngle = useSparkline('nadir angle', 'aocs_nadir_angle');
</script>
<template>

	<h1 class="page-header">
		<span v-if="loading" class="spinner-border text-secondary app-fs-small" role="status"><span class="visually-hidden">Loading...</span></span>
		AOCS <small class="d-none d-md-inline">Attitude and Orbit Control System</small>
		<telemetry-status />
	</h1>
	<hr class="mb-4">

	<div class="row" v-if="!compact">
		<div class="col-sm-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">AOCS Chain</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.aocs_chain }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-sm-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">AOCS Mode</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.aocs_mode }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-sm-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">AOCS Valid</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-danger': state.aocs_valid==='not_valid', 'text-bg-dark': state.aocs_valid==='unknown', 'text-bg-theme': state.aocs_valid==='valid' }">{{ state.aocs_valid }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row" v-if="!compact">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Rotation X</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state && state.aocs_rotation && state.aocs_rotation.length >= 3">
						<h3 class="mb-0 text-center">{{ state.aocs_rotation[0].toFixed(3) }}°</h3>
						<div class="mt-1">
							<apexchart :height="chartRotX.height" :options="chartRotX.options" :series="chartRotX.series"></apexchart>
						</div>
					</div>
					<div v-else class="text-center text-secondary">_</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Rotation Y</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state && state.aocs_rotation && state.aocs_rotation.length >= 3">
						<h3 class="mb-0 text-center">{{ state.aocs_rotation[1].toFixed(3) }}°</h3>
						<div class="mt-1">
							<apexchart :height="chartRotY.height" :options="chartRotY.options" :series="chartRotY.series"></apexchart>
						</div>
					</div>
					<div v-else class="text-center text-secondary">_</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Rotation Z</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state && state.aocs_rotation && state.aocs_rotation.length >= 3">
						<h3 class="mb-0 text-center">{{ state.aocs_rotation[2].toFixed(3) }}°</h3>
						<div class="mt-1">
							<apexchart :height="chartRotZ.height" :options="chartRotZ.options" :series="chartRotZ.series"></apexchart>
						</div>
					</div>
					<div v-else class="text-center text-secondary">_</div>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row" v-if="!compact">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Rate X</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state && state.aocs_rates && state.aocs_rates.length >= 3">
						<h3 class="mb-0 text-center">{{ state.aocs_rates[0].toFixed(3) }} <small class="text-secondary app-fs-small">°/s</small></h3>
						<div class="mt-1">
							<apexchart :height="chartRateX.height" :options="chartRateX.options" :series="chartRateX.series"></apexchart>
						</div>
					</div>
					<div v-else class="text-center text-secondary">_</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Rate Y</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state && state.aocs_rates && state.aocs_rates.length >= 3">
						<h3 class="mb-0 text-center">{{ state.aocs_rates[1].toFixed(3) }} <small class="text-secondary app-fs-small">°/s</small></h3>
						<div class="mt-1">
							<apexchart :height="chartRateY.height" :options="chartRateY.options" :series="chartRateY.series"></apexchart>
						</div>
					</div>
					<div v-else class="text-center text-secondary">_</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Rate Z</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state && state.aocs_rates && state.aocs_rates.length >= 3">
						<h3 class="mb-0 text-center">{{ state.aocs_rates[2].toFixed(3) }} <small class="text-secondary app-fs-small">°/s</small></h3>
						<div class="mt-1">
							<apexchart :height="chartRateZ.height" :options="chartRateZ.options" :series="chartRateZ.series"></apexchart>
						</div>
					</div>
					<div v-else class="text-center text-secondary">_</div>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row" v-if="!compact">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Sun Angle</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state && typeof state.aocs_sun_angle === 'number'">
						<h3 class="mb-0 text-center">{{ state.aocs_sun_angle.toFixed(3) }}°</h3>
						<div class="mt-1">
							<apexchart :height="chartSunAngle.height" :options="chartSunAngle.options" :series="chartSunAngle.series"></apexchart>
						</div>
					</div>
					<div v-else class="text-center text-secondary">_</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Nadir Angle</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state && typeof state.aocs_nadir_angle === 'number'">
						<h3 class="mb-0 text-center">{{ state.aocs_nadir_angle.toFixed(3) }}°</h3>
						<div class="mt-1">
							<apexchart :height="chartNadirAngle.height" :options="chartNadirAngle.options" :series="chartNadirAngle.series"></apexchart>
						</div>
					</div>
					<div v-else class="text-center text-secondary">_</div>
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
								<td class="app-w-col">AOCS Chain</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_chain }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>AOCS Mode</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_mode }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>AOCS Valid</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_valid }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Rotation X</td>
								<td v-if="state && state.aocs_rotation && state.aocs_rotation.length >= 3"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_rotation[0].toFixed(3) }}°</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Rotation Y</td>
								<td v-if="state && state.aocs_rotation && state.aocs_rotation.length >= 3"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_rotation[1].toFixed(3) }}°</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Rotation Z</td>
								<td v-if="state && state.aocs_rotation && state.aocs_rotation.length >= 3"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_rotation[2].toFixed(3) }}°</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Rate X</td>
								<td v-if="state && state.aocs_rates && state.aocs_rates.length >= 3"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_rates[0].toFixed(3) }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Rate Y</td>
								<td v-if="state && state.aocs_rates && state.aocs_rates.length >= 3"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_rates[1].toFixed(3) }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Rate Z</td>
								<td v-if="state && state.aocs_rates && state.aocs_rates.length >= 3"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_rates[2].toFixed(3) }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Sun Angle</td>
								<td v-if="state && typeof state.aocs_sun_angle === 'number'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_sun_angle.toFixed(3) }}°</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Nadir Angle</td>
								<td v-if="state && typeof state.aocs_nadir_angle === 'number'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_nadir_angle.toFixed(3) }}°</div></td>
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
