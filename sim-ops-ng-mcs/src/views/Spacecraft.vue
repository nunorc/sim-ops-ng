<script setup lang="ts">
import TelemetryStatus from '@/components/app/TelemetryStatus.vue';
import LastUpdate from '@/components/app/LastUpdate.vue';
import apexchart from '@/components/plugins/Apexcharts.vue';
import { useSpacecraftView, useSparkline } from '@/composables/spacecraft-view';

const { loading, state, compact } = useSpacecraftView('view-Spacecraft-state');

const chartBattery = useSparkline('Battery', 'eps_battery_dod');
const chartTemperature = useSparkline('Temperature', 'eps_temperature');
const chartMemory = useSparkline('Memory', 'dhs_memory');
</script>
<template>

	<h1 class="page-header">
		<span v-if="loading" class="spinner-border text-secondary app-fs-small" role="status"><span class="visually-hidden">Loading...</span></span>
		Spacecraft <small>Monitor</small>
		<telemetry-status />
	</h1>
	<hr class="mb-4">

	<div class="row" v-if="!compact">
		<div class="col">
			<h4>AOCS</h4>
			<div class="row">
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">AOCS Chain</card-header>
						<card-body class="p-2 mx-2">
							<span v-if="state && state.ttc_mcu === 'nominal'" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.aocs_chain }}</span>
							<span v-else>_</span>
						</card-body>
					</card>
				</div>
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">AOCS Mode</card-header>
						<card-body class="p-2 mx-2">
							<span v-if="state && state.ttc_mcu === 'nominal'" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.aocs_mode }}</span>
							<span v-else>_</span>
						</card-body>
					</card>
				</div>
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">AOCS valid</card-header>
						<card-body class="p-2 mx-2">
							<span v-if="state && state.ttc_mcu === 'nominal'" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.aocs_valid }}</span>
							<span v-else>_</span>
						</card-body>
					</card>
				</div>
			</div>
		</div>
		<div class="col">
			<h4>TTC</h4>
			<div class="row">
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">TTC Chain</card-header>
						<card-body class="p-2 mx-2">
							<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.ttc_chain }}</span>
							<span v-else>_</span>
						</card-body>
					</card>
				</div>
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">U/L Status</card-header>
						<card-body class="p-2 mx-2">
							<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-danger': state.ttc_state_ul==='NO_RF', 'text-bg-warning': state.ttc_state_ul==='PLL_LOCK', 'text-bg-success': state.ttc_state_ul==='BIT_LOCK' }">{{ state.ttc_state_ul }}</span>
						</card-body>
					</card>
				</div>
				<div class="col-xl-4 col-lg-4">
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
			</div>
		</div>
	</div>

	<div class="row" v-if="!compact">
		<div class="col">
			<h4>EPS</h4>
			<div class="row">
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">EPS Chain</card-header>
						<card-body class="p-2 mx-2">
							<span v-if="state && state.ttc_mcu === 'nominal'" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_chain }}</span>
							<span v-else>_</span>
						</card-body>
					</card>
				</div>
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">Battery DOD</card-header>
						<card-body>
							<div class="row align-items-center" v-if="state && state.ttc_mcu === 'nominal'">
								<h3 class="mb-0 text-center">{{ state.eps_battery_dod.toFixed(2) }}%</h3>
								<div class="mt-1">
									<apexchart :height="chartBattery.height" :options="chartBattery.options" :series="chartBattery.series"></apexchart>
								</div>
							</div>
						</card-body>
					</card>
				</div>
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">Temperature</card-header>
						<card-body>
							<div class="row align-items-center" v-if="state && state.ttc_mcu === 'nominal'">
								<h3 class="mb-0 text-center">{{ state.eps_temperature.toFixed(2) }}°C</h3>
								<div class="mt-1">
									<apexchart :height="chartTemperature.height" :options="chartTemperature.options" :series="chartTemperature.series"></apexchart>
								</div>
							</div>
						</card-body>
					</card>
				</div>
			</div>
		</div>
		<div class="col">
			<h4>DHS</h4>
			<div class="row">
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">DHS Chain</card-header>
						<card-body class="p-2 mx-2">
							<span v-if="state && state.ttc_mcu === 'nominal'" class="badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.dhs_chain }}</span>
							<span v-else>_</span>
						</card-body>
					</card>
				</div>
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">OBSW Mode</card-header>
							<card-body class="p-2 mx-2">
								<span v-if="state && state.ttc_mcu === 'nominal'" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.dhs_obsw_mode === 'nominal', 'bg-danger': state.dhs_obsw_mode !== 'nominal'}">{{ state.dhs_obsw_mode }}</span>
								<span v-else>_</span>
							</card-body>
					</card>
				</div>
				<div class="col-xl-4 col-lg-4">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">Memory Usage</card-header>
						<card-body>
							<div class="row align-items-center" v-if="state && state.ttc_mcu === 'nominal'">
								<h3 class="mb-0 text-center">{{ state.dhs_memory.toFixed(2) }}%</h3>
								<div class="mt-1">
									<apexchart :height="chartMemory.height" :options="chartMemory.options" :series="chartMemory.series"></apexchart>
								</div>
							</div>
						</card-body>
					</card>
				</div>
			</div>
		</div>
	</div>

	<div class="row" v-if="!compact">
		<div class="col">
			<h4>Payload</h4>
			<div class="row">
				<div class="col-xl-2 col-lg-2">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">GNSS Status</card-header>
						<card-body class="p-2 mx-2">
							<span v-if="state && state.ttc_mcu === 'nominal'" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.pl_gnss_status==='on', 'bg-danger': state.pl_gnss_status!=='on' }">{{ state.pl_gnss_status }}</span>
							<span v-else>_</span>
						</card-body>
					</card>
				</div>
				<div class="col-xl-2 col-lg-2">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">Camera Status</card-header>
						<card-body class="p-2 mx-2">
							<span v-if="state && state.ttc_mcu === 'nominal'" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.pl_camera_status==='on', 'bg-danger': state.pl_camera_status!=='on' }">{{ state.pl_camera_status }}</span>
							<span v-else>_</span>
						</card-body>
					</card>
				</div>
				<div class="col-xl-2 col-lg-2">
					<card class="mb-3">
						<card-header class="card-header fw-bold small text-center p-1">SDR Status</card-header>
						<card-body class="p-2 mx-2">
							<span v-if="state && state.ttc_mcu === 'nominal'" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.pl_sdr_status==='on', 'bg-danger': state.pl_sdr_status!=='on' }">{{ state.pl_sdr_status }}</span>
							<span v-else>_</span>
						</card-body>
					</card>
				</div>
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
								<td colspan="2"><h5>AOCS</h5></td>
							</tr>
							<tr>
								<td class="app-w-col">AOCS Chain</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_chain }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>AOCS Mode</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_mode }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>AOCS Valid</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_valid }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Rotation X</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_rotation[0].toFixed(3) }}°</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Rotation Y</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_rotation[1].toFixed(3) }}°</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Rotation Z</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_rotation[2].toFixed(3) }}°</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Rate X</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_rates[0].toFixed(3) }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Rate Y</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_rates[1].toFixed(3) }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Rate Z</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_rates[2].toFixed(3) }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Sun Angle</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_sun_angle.toFixed(3) }}°</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Nadir Angle</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 text-uppercase bg-dark">{{ state.aocs_nadir_angle.toFixed(3) }}°</div></td>
								<td v-else>_</td>
							</tr>
						</tbody>
					</table>
				</card-body>
			</card>
		</div>
		<div class="col-sm-4">
			<card class="mb-3">
				<card-body class="">
					<table class="table text-nowrap mb-0">
						<tbody>
							<tr>
								<td colspan="2"><h5>TTC</h5></td>
							</tr>
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
								<td>Coherent</td>
								<td v-if="state"><div class="app-badge rounded-0 text-uppercase" :class="{ 'text-bg-success': state.ttc_coherent, 'text-bg-danger': !state.ttc_coherent}">{{ state.ttc_coherent }}</div></td>
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
			<card class="mb-3">
				<card-body class="">
					<table class="table text-nowrap mb-0">
						<tbody>
							<tr>
								<td colspan="2"><h5>DHS</h5></td>
							</tr>
							<tr>
								<td class="app-w-col">DHS Chain</td>
								<td v-if="state  && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.dhs_chain }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>OBSW Mode</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.dhs_obsw_mode === 'nominal', 'bg-danger': state.dhs_obsw_mode !== 'nominal'}">{{ state.dhs_obsw_mode }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Memory Dump</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.dhs_mem_dump_enabled, 'bg-danger': !state.dhs_mem_dump_enabled }">{{ state.dhs_mem_dump_enabled ? 'Enabled' : 'Disabled' }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Memory Usage</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.dhs_memory.toFixed(2) }}%</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>TM Counter</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.dhs_tm_counter }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>TC Counter</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.dhs_tc_counter }}</div></td>
								<td v-else>_</td>
							</tr>
						</tbody>
					</table>
				</card-body>
			</card>
		</div>
		<div class="col-sm-4">
			<card class="mb-3">
				<card-body class="">
					<table class="table text-nowrap mb-0">
						<tbody>
							<tr>
								<td colspan="2"><h5>EPS</h5></td>
							</tr>
							<tr>
								<td class="app-w-col">EPS Chain</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_chain }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Solar Array 1</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_sol_array[0] }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Solar Array 2</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_sol_array[1] }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Battery DOD</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_battery_dod.toFixed(2) }}%</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Net Power</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_net_power.toFixed(2) }}%</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td>Temperature</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase bg-dark">{{ state.eps_temperature.toFixed(2) }}%</div></td>
								<td v-else>_</td>
							</tr>
						</tbody>
					</table>
				</card-body>
			</card>
			<card class="mb-3">
				<card-body class="">
					<table class="table text-nowrap mb-0">
						<tbody>
							<tr>
								<td colspan="2"><h5>Payload</h5></td>
							</tr>
							<tr>
								<td class="app-w-col">GNSS Receiver Status</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.pl_gnss_status==='on', 'bg-danger': state.pl_gnss_status!=='on' }">{{ state.pl_gnss_status }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td class="app-w-col">Camera Status</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.pl_camera_status==='on', 'bg-danger': state.pl_camera_status!=='on' }">{{ state.pl_camera_status }}</div></td>
								<td v-else>_</td>
							</tr>
							<tr>
								<td class="app-w-col">SDR Status</td>
								<td v-if="state && state.ttc_mcu === 'nominal'"><div class="app-badge rounded-0 app-w-100 text-uppercase" :class="{ 'bg-theme': state.pl_sdr_status==='on', 'bg-danger': state.pl_sdr_status!=='on' }">{{ state.pl_sdr_status }}</div></td>
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
