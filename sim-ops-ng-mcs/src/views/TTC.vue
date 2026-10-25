<script setup lang="ts">
import TelemetryStatus from '@/components/app/TelemetryStatus.vue';
import LastUpdate from '@/components/app/LastUpdate.vue';
import apexchart from '@/components/plugins/Apexcharts.vue';
import { useSpacecraftView, useSparkline } from '@/composables/spacecraft-view';
import type { SpacecraftState } from '@/types/state';

const { loading, state, compact } = useSpacecraftView('view-TTC-state');

const chartSnr = useSparkline('SNR', 'ttc_eb_no_ul');

const ttcUnits: { field: keyof SpacecraftState; label: string; title: string }[] = [
	{ field: 'ttc_s_tx_status', label: 'Sb TX', title: 'TTC Sb Transmitter' },
	{ field: 'ttc_s_rx_status', label: 'Sb RX', title: 'TTC Sb Receiver' },
	{ field: 'ttc_x_tx_status', label: 'Xb TX', title: 'TTC Xb Transmitter' },
	{ field: 'ttc_x_rx_status', label: 'Xb RX', title: 'TTC Xb Receiver' }
];
</script>
<template>

	<h1 class="page-header">
		<span v-if="loading" class="spinner-border text-secondary app-fs-small" role="status"><span class="visually-hidden">Loading...</span></span>
		TTC <small class="d-none d-md-inline">Telemetry, Tracking & Command</small>
		<telemetry-status />
	</h1>
	<hr class="mb-4">

	<div class="row" v-if="!compact">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">TTC Chain</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.ttc_chain }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">U/L Status</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-danger': state.ttc_state_ul==='NO_RF', 'text-bg-warning': state.ttc_state_ul==='PLL_LOCK', 'text-bg-success': state.ttc_state_ul==='BIT_LOCK' }">{{ state.ttc_state_ul }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">MCU Status</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-success': state.ttc_mcu === 'nominal', 'bg-danger': state.ttc_mcu !== 'nominal' }">{{ state.ttc_mcu }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">TTC Mode</card-header>
				<card-body class="p-2 mx-2">
					<h5 class="mb-0 text-center">
						<span v-if="state">{{ state.ttc_mode }}</span>
						<span v-else>_</span>
					</h5>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Ranging</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-danger': state.ttc_ranging === 'disabled', 'text-bg-success': state.ttc_ranging === 'enabled' }">{{ state.ttc_ranging }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Coherent</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-danger': state.ttc_coherent === 'disabled', 'text-bg-success': state.ttc_coherent === 'enabled' }">{{ state.ttc_coherent }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row" v-if="!compact">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">U/L SNR</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state">
						<h3 class="mb-0 text-center">{{ state.ttc_state_ul !== 'NO_RF' ? state.ttc_eb_no_ul.toFixed(1) : '_' }} <small v-if="state.ttc_state_ul !== 'NO_RF'" class="text-secondary app-fs-small"> dB</small></h3>
						<div class="mt-1">
							<apexchart :height="chartSnr.height" :options="chartSnr.options" :series="chartSnr.series"></apexchart>
						</div>
					</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">TX / RX Status</card-header>
				<card-body class="p-2 mx-2">
					<div v-if="state" class="row g-1">
						<div class="col-6" v-for="unit in ttcUnits" :key="unit.field">
							<span class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-theme': state[unit.field] === 'on', 'text-bg-danger': state[unit.field] !== 'on' }" :title="unit.title">{{ unit.label }}</span>
						</div>
					</div>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Ping Ack</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-dark': state.ttc_ping_ack===0, 'text-bg-success': state.ttc_ping_ack>0}">{{ state.ttc_ping_ack }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">TTC Sb Antenna</card-header>
				<card-body class="p-2 mx-2">
					<h5 class="mb-0 text-center">
						<span v-if="state">{{ state.ttc_s_antenna }}</span>
						<span v-else>_</span>
					</h5>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">TTC Xb Antenna</card-header>
				<card-body class="p-2 mx-2">
					<h5 class="mb-0 text-center">
						<span v-if="state">{{ state.ttc_x_antenna }}</span>
						<span v-else>_</span>
					</h5>
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
								<td class="app-w-col">TTC Chain</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.ttc_chain }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>TTC Mode</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.ttc_mode }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>U/L Status</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase" :class="{ 'text-bg-danger': state.ttc_state_ul==='NO_RF', 'text-bg-warning': state.ttc_state_ul==='PLL_LOCK', 'text-bg-success': state.ttc_state_ul==='BIT_LOCK' }">{{ state.ttc_state_ul }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>MCU Status</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase" :class="{ 'bg-success': state.ttc_mcu === 'nominal', 'bg-danger': state.ttc_mcu !== 'nominal' }">{{ state.ttc_mcu }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>U/L SNR</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.ttc_state_ul !== 'NO_RF' ? state.ttc_eb_no_ul.toFixed(1) : '_' }} <small style="text-transform: none;">dBm</small></div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Sb TX Status</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase" :class="{ 'text-bg-theme': state.ttc_s_tx_status === 'on', 'text-bg-danger': state.ttc_s_tx_status !== 'on' }">{{ state.ttc_s_tx_status }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Sb RX Status</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase" :class="{ 'text-bg-theme': state.ttc_s_rx_status === 'on', 'text-bg-danger': state.ttc_s_rx_status !== 'on' }">{{ state.ttc_s_rx_status }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Xb TX Status</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase" :class="{ 'text-bg-theme': state.ttc_x_tx_status === 'on', 'text-bg-danger': state.ttc_x_tx_status !== 'on' }">{{ state.ttc_x_tx_status }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Xb RX Status</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase" :class="{ 'text-bg-theme': state.ttc_x_rx_status === 'on', 'text-bg-danger': state.ttc_x_rx_status !== 'on' }">{{ state.ttc_x_rx_status }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Ranging</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase" :class="{ 'text-bg-danger': state.ttc_ranging === 'disabled', 'text-bg-success': state.ttc_ranging === 'enabled'}">{{ state.ttc_ranging }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Coherent</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase" :class="{ 'text-bg-danger': state.ttc_coherent === 'disabled', 'text-bg-success': state.ttc_coherent === 'enabled'}">{{ state.ttc_coherent }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Ping Ack</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase" :class="{ 'bg-dark': state.ttc_ping_ack===0, 'text-bg-success': state.ttc_ping_ack>0}">{{ state.ttc_ping_ack }}</div></td>
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
