<script setup lang="ts">
import TelemetryStatus from '@/components/app/TelemetryStatus.vue';
import LastUpdate from '@/components/app/LastUpdate.vue';
import { useSpacecraftView } from '@/composables/spacecraft-view';

const { loading, state, compact } = useSpacecraftView('view-Payload-state');
</script>
<template>
	<h1 class="page-header">
		<span v-if="loading" class="spinner-border text-secondary app-fs-small" role="status"><span class="visually-hidden">Loading...</span></span>
		Payload
		<telemetry-status />
	</h1>
	<hr class="mb-4">

	<div class="row" v-if="!compact">
		<h5>GNSS Receiver</h5>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">GNSS Status</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.pl_gnss_status==='on', 'bg-danger': state.pl_gnss_status!=='on' }">{{ state.pl_gnss_status }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Latitude</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state">
						<h3 class="mb-0 text-center">{{ state.pl_gnss_pos[0].toFixed(3) }}°</h3>
					</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Longitude</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state">
						<h3 class="mb-0 text-center">{{ state.pl_gnss_pos[1].toFixed(3) }}°</h3>
					</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Altitude</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state">
						<h3 class="mb-0 text-center">{{ state.pl_gnss_pos[2].toFixed(0) }}<small class="text-secondary app-fs-small"> km</small></h3>
					</div>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row" v-if="!compact">
		<div class="col-xl-4 col-lg-4">
			<h5>Camera</h5>
		</div>
		<div class="col-xl-4 col-lg-4">
			<h5>SDR</h5>
		</div>
	</div>

	<div class="row" v-if="!compact">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Camera Status</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.pl_camera_status==='on', 'bg-danger': state.pl_camera_status!=='on' }">{{ state.pl_camera_status }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Camera Config</card-header>
				<card-body class="p-2 mx-2">
					<h3 v-if="state" class="mb-0 text-center">{{ state.pl_camera_config }}</h3>
					<h3 v-else>_</h3>
				</card-body>
			</card>
		</div>

		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">SDR Status</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.pl_sdr_status==='on', 'bg-danger': state.pl_sdr_status!=='on' }">{{ state.pl_sdr_status }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">SDR Config</card-header>
				<card-body class="p-2 mx-2">
					<h3 v-if="state" class="mb-0 text-center">{{ state.pl_sdr_config }}</h3>
					<h3 v-else>_</h3>
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
								<td colspan="2"><h5>GNSS Receiver</h5></td>
							</tr>
							<tr>
								<td class="app-w-col">GNSS Status</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.pl_gnss_status==='on', 'bg-danger': state.pl_gnss_status!=='on' }">{{ state.pl_gnss_status }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Latitude</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.pl_gnss_pos[0].toFixed(3) }}°</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Longitude</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.pl_gnss_pos[1].toFixed(3) }}°</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Altitude</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.pl_gnss_pos[2].toFixed(0) }} km</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td colspan="2"><h5>Camera</h5></td>
							</tr>
							<tr>
								<td>Camera Status</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.pl_camera_status==='on', 'bg-danger': state.pl_camera_status!=='on' }">{{ state.pl_camera_status }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Camera Config</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.pl_camera_config }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td colspan="2"><h5>SDR</h5></td>
							</tr>
							<tr>
								<td>SDR Status</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.pl_sdr_status==='on', 'bg-danger': state.pl_sdr_status!=='on' }">{{ state.pl_sdr_status }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>SDR Config</td>
								<td v-if="state"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.pl_sdr_config }}</div></td>
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
