<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from 'vue';
import axios, { type AxiosError } from 'axios';
import { useAppVariableStore } from '@/stores/app-variable';
import { useAppOptionStore } from '@/stores/app-option';
import { useSocketStore } from '@/stores/app-websockets';
import { useAuthStore } from '@/stores/app-auth';
import apexchart from '@/components/plugins/Apexcharts.vue';
import TelemetryStatus from '@/components/app/TelemetryStatus.vue';
import { useSparkline } from '@/composables/spacecraft-view';
import { toFinite, finitePairs, gsElevation, gsAzimuth, gsDistance, gsVelocity, gsSnr } from '@/utils/telemetry';
import type { GroundStationState, SpacecraftState } from '@/types/state';

// Ground station monitor, shared by the Ground Station view and OM (which adds the controls)
withDefaults(defineProps<{
	title: string;
	subtitle?: string;
	modeLabel?: string;
	// ground station controls (U/L carrier, tracking, ranging, power, band, mode)
	controls?: boolean;
}>(), { subtitle: '', modeLabel: 'Mode', controls: false });

const appVariable = useAppVariableStore(),
      appOption = useAppOptionStore(),
      socketStore = useSocketStore(),
      authStore = useAuthStore();

// spectrum charts: fixed y ranges with the U/L power limit and the D/L threshold marked
const chartTXOptions = { chart: { type: 'line', sparkline: { enabled: true } }, colors: [appVariable.color.theme], stroke: { curve: 'straight', width: 2 }, tooltip: { enabled: false }, yaxis: { min: -20, max: 60 },
	annotations: { yaxis: [{ y: 45, borderColor: '#ff0000' }] } };
const chartRXOptions = { chart: { type: 'line', sparkline: { enabled: true } }, colors: [appVariable.color.theme], stroke: { curve: 'straight', width: 2 }, tooltip: { enabled: false }, yaxis: { min: -120, max: -75 },
	annotations: { yaxis: [{ y: -109, borderColor: '#ff0000' }] } };

const loading = ref(true);
// deep, as the controls' selects v-model into it
const state = ref<GroundStationState | null>(null);
// the ranging/doppler values need the spacecraft transponder status
const sc_state = shallowRef<SpacecraftState | null>(null);
const control_send = ref('');
const control_recv = ref('');
const control_recv_loading = ref(false);

// Plotted/displayed values: a finite number when available, null otherwise.
const elevation_value = computed(() => gsElevation(state.value));
const azimuth_value = computed(() => gsAzimuth(state.value));
const distance_value = computed(() => gsDistance(state.value, sc_state.value));
const velocity_value = computed(() => gsVelocity(state.value, sc_state.value));
const snr_value = computed(() => gsSnr(state.value));

// sparkline history is sampled by the socket store (see utils/telemetry)
const chartElevation = useSparkline('Elevation', 'gs_elevation');
const chartAzimuth = useSparkline('Azimuth', 'gs_azimuth');
const chartDistance = useSparkline('Distance', 'gs_distance');
const chartVelocity = useSparkline('Velocity', 'gs_velocity');
const chartSnr = useSparkline('SNR', 'gs_snr');
const chartTX = computed(() => ({
	height: 100, options: chartTXOptions, series: [{ name: 'Power', data: finitePairs(state.value?.spectrum_ul) }]
}));
const chartRX = computed(() => ({
	height: 100, options: chartRXOptions, series: [{ name: 'Power', data: finitePairs(state.value?.spectrum_dl) }]
}));

function updateData(data: GroundStationState) {
	loading.value = false;

	// trigger sweep
	if (data.sweep_count > 0 && state.value && data.sweep_count > state.value.sweep_count) {
		const s1 = document.getElementById('sweep-1');

		if (s1) {
			s1.classList.add('sweep-bar-anim');
			setTimeout(() => { s1.classList.remove('sweep-bar-anim')}, 10000)
		}
	}

	state.value = data;
}

function sendCommand(command: string, value: unknown, event: Event) {
	const button = event.target as HTMLButtonElement;

	button.disabled = true;
	control_send.value = `${command} ${value}`;
	control_recv.value = '';
	control_recv_loading.value = true;

	const body = { 'system': 'ground_station',  'control': command, 'value': value };
	axios.post(`${appOption.soAPI}/api/control`, body, authStore.authConfig())
		.then((resp) => {
			control_recv.value = resp.data.status;
			button.disabled = false;
			control_recv_loading.value = false;
		})
		.catch((error: AxiosError<{ detail?: string }>) => {
			control_recv.value = error.response?.data?.detail || 'ERROR';
			button.disabled = false;
			control_recv_loading.value = false;
		})
}

function diffDatesStr(later: number | null): string {
	const now = toFinite(state.value?.ts),
	      end = toFinite(later);

	if (now === null || end === null || end < now)
		return '_';

	let delta = Math.abs(end - now);

	const days = Math.floor(delta/86400);
	delta -= days * 86400;

	const hours = Math.floor(delta/3600) % 24;
	delta -= hours * 3600;

	const minutes = Math.floor(delta/60) % 60;
	delta -= minutes * 60;

	const seconds = Math.floor(delta % 60);

	let res = 'in ';
	if (days > 0)
		res += days+'d '
	if (hours > 0)
		res += hours+'h '
	if (minutes > 0)
		res += minutes+'m '
	if (seconds >= 0)
		res += seconds+'s '

	return res;
}

onMounted(() => {
	// Watch for WebSocket ground station state changes
	watch(() => socketStore.gs_state, (gs_data) => { if (gs_data) updateData(gs_data); }, { immediate: true });

	// Watch for WebSocket spacecraft state changes (ranging transponder status)
	watch(() => socketStore.sc_state, (sc_data) => { if (sc_data) sc_state.value = sc_data; }, { immediate: true });
});
</script>
<template>
	<h1 class="page-header">
		{{ title }} <small>{{ subtitle }}</small>
		<telemetry-status :downlink="false" />
	</h1>
	<hr class="mb-4">

	<div class="row">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">D/L Status</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-danger': state.status_dl==='NO_RF', 'text-bg-warning': state.status_dl==='PLL_LOCK' || state.status_dl==='PSK_LOCK' || state.status_dl==='BIT_LOCK' || state.status_dl==='RF_DETECTED', 'text-bg-success': state.status_dl==='FRAME_LOCK' }">{{ state.status_dl }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Frame Quality</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-theme': state.frame_quality==='good', 'text-bg-danger': state.frame_quality==='bad', 'text-bg-warning': state.frame_quality==='unknown' }">{{ state.frame_quality }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Frame Checks</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-theme': state.frame_checks==='enabled', 'text-bg-danger': state.frame_checks!=='enabled' }">{{ state.frame_checks }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Program Track</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-danger': !state.program_track, 'text-bg-theme': state.program_track }">{{ state.program_track ? 'Enabled' : 'Disabled' }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Ground Station</card-header>
				<card-body class="p-2 mx-2">
					<h5 class="mb-0 text-center">
						<span v-if="state">{{ state.name }}</span>
						<span v-else>_</span>
					</h5>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Next AOS</card-header>
				<card-body class="p-2 mx-2">
					<p class="mb-0 text-center">
						<span v-if="state">{{ diffDatesStr(state.next_pass_start) }}</span>
						<span v-else>_</span>
					</p>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">U/L Carrier</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-danger': state.carrier_ul !== 'on', 'text-bg-success': state.carrier_ul === 'on' }">{{ state.carrier_ul === 'on' ? 'enabled' : 'disabled' }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Sweep Done</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-danger': !state.sweep_done, 'text-bg-success': state.sweep_done }">{{ state.sweep_done }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">U/L Power</card-header>
				<card-body class="p-2 mx-2">
					<h5 class="mb-0 text-center">
						<span v-if="state">{{ state.power_ul }} <small class="text-secondary app-fs-small"> dBm</small></span>
						<span v-else>_</span>
					</h5>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">U/L &#183; D/L Bands</card-header>
				<card-body class="p-2 mx-2">
					<h5 class="mb-0 text-center">
						<span v-if="state && state.mode">{{ state.band_ul }} &#183; {{ state.mode.charAt(0) }}</span>
						<span v-else>_</span>
					</h5>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">{{ modeLabel }}</card-header>
				<card-body class="p-2 mx-2">
					<h5 class="mb-0 text-center">
						<span v-if="state">{{ state.mode }}</span>
						<span v-else>_</span>
					</h5>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Next 5° AOS</card-header>
				<card-body class="p-2 mx-2">
					<p class="mb-0 text-center">
						<span v-if="state">{{ diffDatesStr(state.next_5_start) }}</span>
						<span v-else>_</span>
					</p>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">D/L Modulation</card-header>
				<card-body class="p-2 mx-2">
					<h5 class="mb-0 text-center">
						<span v-if="state && state.dl_modulation">{{ state.dl_modulation }}</span>
						<span v-else>_</span>
					</h5>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">D/L Coding</card-header>
				<card-body class="p-2 mx-2">
					<h5 class="mb-0 text-center">
						<span v-if="state && state.dl_coding">{{ state.dl_coding }}</span>
						<span v-else>_</span>
					</h5>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Ranging</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-danger': !state.auto_range, 'text-bg-theme': state.auto_range }">{{ state.auto_range ? 'Enabled' : 'Disabled' }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Doppler</card-header>
				<card-body class="p-2 mx-2">
					<span v-if="state" class="badge rounded-0 app-w-100 text-uppercase" :class="{ 'text-bg-danger': !state.doppler_enabled, 'text-bg-theme': state.doppler_enabled }">{{ state.doppler_enabled ? 'Enabled' : 'Disabled' }}</span>
					<span v-else>_</span>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2 offset-xl-2 offset-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Next 5° LOS</card-header>
				<card-body class="p-2 mx-2">
					<p class="mb-0 text-center">
						<span v-if="state">{{ diffDatesStr(state.next_5_end) }}</span>
						<span v-else>_</span>
					</p>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row">
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Elevation</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state">
						<h3 class="mb-0 text-center">{{ elevation_value !== null ? elevation_value.toFixed(2)+'°' : '_' }}</h3>
						<div class="mt-1">
							<apexchart :height="chartElevation.height" :options="chartElevation.options" :series="chartElevation.series"></apexchart>
						</div>
					</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Azimuth</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state">
						<h3 class="mb-0 text-center">{{ azimuth_value !== null ? azimuth_value.toFixed(2)+'°' : '_' }}</h3>
						<div class="mt-1">
							<apexchart :height="chartAzimuth.height" :options="chartAzimuth.options" :series="chartAzimuth.series"></apexchart>
						</div>
					</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Range</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state">
						<h3 class="mb-0 text-center">{{ distance_value !== null ? distance_value.toFixed(0) : '_' }} <small v-if="distance_value !== null" class="text-secondary app-fs-small"> km</small></h3>
						<div class="mt-1">
							<apexchart :height="chartDistance.height" :options="chartDistance.options" :series="chartDistance.series"></apexchart>
						</div>
					</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Velocity</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state">
						<h3 class="mb-0 text-center">{{ velocity_value !== null ? velocity_value.toFixed(2) : '_' }} <small v-if="velocity_value !== null" class="text-secondary app-fs-small"> km/s</small></h3>
						<div class="mt-1">
							<apexchart :height="chartVelocity.height" :options="chartVelocity.options" :series="chartVelocity.series"></apexchart>
						</div>
					</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">D/L SNR</card-header>
				<card-body>
					<div class="row align-items-center" v-if="state">
						<h3 class="mb-0 text-center">{{ snr_value !== null ? snr_value.toFixed(3) : '_' }} <small v-if="snr_value !== null" class="text-secondary app-fs-small"> dB</small></h3>
						<div class="mt-1">
							<apexchart :height="chartSnr.height" :options="chartSnr.options" :series="chartSnr.series"></apexchart>
						</div>
					</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Next LOS</card-header>
				<card-body class="p-2 mx-2">
					<p class="mb-0 text-center">
						<span v-if="state">{{ diffDatesStr(state.next_pass_end) }}</span>
						<span v-else>_</span>
					</p>
				</card-body>
			</card>
		</div>
	</div>

	<div class="row">
		<div class="col-xl-6 col-lg-6">
			<card class="">
				<card-header class="card-header fw-bold small text-center p-1">U/L Spectrum</card-header>
				<card-body class="px-0 p-2 mx-3">
					<div id="sweep-1" class="sweep-bar"></div>
					<apexchart :height="chartTX.height" :options="chartTX.options" :series="chartTX.series"></apexchart>
				</card-body>
			</card>
		</div>
		<div class="col-xl-6 col-lg-6">
			<card class="">
				<card-header class="card-header fw-bold small text-center p-1">D/L Spectrum</card-header>
				<card-body class="px-0 p-2 mx-3">
					<apexchart :height="chartRX.height" :options="chartRX.options" :series="chartRX.series"></apexchart>
				</card-body>
			</card>
		</div>
	</div>

	<template v-if="controls">
	<hr/>

	<div class="row">
		<div class="col-xl-4 col-lg-4">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">Control</card-header>
				<card-body class="text-center" v-if="state">
					<div>
						<button v-if="state.carrier_ul === 'off'" @click="sendCommand('carrier_ul', 'on', $event)" type="button" class="btn btn-sm btn-outline-theme app-w-80">Enable U/L Carrier</button>
						<button v-if="state.carrier_ul === 'on'" @click="sendCommand('carrier_ul', 'off', $event)" type="button" class="btn btn-sm btn-outline-danger app-w-80">Disable U/L Carrier</button>
						<span>&nbsp;</span>
						<button v-if="!state.program_track" @click="sendCommand('program_track', true, $event)" type="button" class="btn btn-sm btn-outline-theme app-w-80">Enable Prog. Track</button>
						<button v-if="state.program_track" @click="sendCommand('program_track', false, $event)" type="button" class="btn btn-sm btn-outline-danger app-w-80">Disable Prog. Track</button>
						<span>&nbsp;</span>
						<button @click="sendCommand('sweep', true, $event)" type="button" class="btn btn-sm btn-outline-theme app-w-80">Sweep</button>
					</div>
					<div class="mt-2">
						<button v-if="!state.auto_range" @click="sendCommand('auto_range', true, $event)" type="button" class="btn btn-sm btn-outline-theme app-w-80">Enable Ranging</button>
						<button v-if="state.auto_range" @click="sendCommand('auto_range', false, $event)" type="button" class="btn btn-sm btn-outline-danger app-w-80">Disable Ranging</button>
						<span>&nbsp;</span>
						<button v-if="!state.doppler_enabled" @click="sendCommand('doppler_enabled', true, $event)" type="button" class="btn btn-sm btn-outline-theme app-w-80">Enable Doppler</button>
						<button v-if="state.doppler_enabled" @click="sendCommand('doppler_enabled', false, $event)" type="button" class="btn btn-sm btn-outline-danger app-w-80">Disable Doppler</button>
						<span>&nbsp;</span>
						<button v-if="state.frame_checks === 'disabled'" @click="sendCommand('frame_checks', 'enabled', $event)" type="button" class="btn btn-sm btn-outline-theme app-w-80">Enable Fr. Checks</button>
						<button v-if="state.frame_checks === 'enabled'" @click="sendCommand('frame_checks', 'disabled', $event)" type="button" class="btn btn-sm btn-outline-danger app-w-80">Disable Fr. Checks</button>
					</div>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">U/L Power</card-header>
				<card-body class="my-2">
					<select v-if="state" class="form-select form-select-lg" @change="sendCommand('power_ul', state.power_ul, $event)" v-model="state.power_ul">
						<option value="50">50</option>
						<option value="40">40</option>
						<option value="30">30</option>
					</select>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">U/L Band</card-header>
				<card-body class="my-2">
					<select v-if="state" class="form-select form-select-lg" @change="sendCommand('band_ul', state.band_ul, $event)" v-model="state.band_ul">
						<option value="S">S</option>
						<option value="X">X</option>
					</select>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">D/L Mode</card-header>
				<card-body class="my-2">
					<select v-if="state" class="form-select form-select-lg" @change="sendCommand('mode', state.mode, $event)" v-model="state.mode">
						<option v-for="m in state.modes" :key="m">{{ m }}</option>
					</select>
				</card-body>
			</card>
		</div>
		<div class="col-xl-2 col-lg-2">
			<card class="pb-3">
				<card-header class="card-header fw-bold small text-center p-1">Control Console</card-header>
				<card-body class="p-2 mb-1">
					<table class="table table-sm table-striped table-borderless mb-2px small text-nowrap">
						<tbody>
							<tr><td><span>[S]&nbsp;</span><span style="font-size: smaller;">{{ control_send }}</span></td></tr>
							<tr><td><span>[R]&nbsp;</span>
								<span v-if="control_recv_loading" class="spinner-border spinner-border-sm text-secondary" role="status"><span class="visually-hidden">Loading...</span></span>
								<span class="fw-bold" :class="{ 'text-theme': control_recv==='OK', 'text-danger': control_recv!=='OK'}">{{ control_recv }}</span></td></tr>
						</tbody>
					</table>
				</card-body>
			</card>
		</div>
	</div>

	</template>
</template>

<style>
.app-fs-small { font-size: small; }
.sweep-bar {
	position: absolute;
    top: 0;
    left: 0;
    margin: 0;
    padding: 0;
    width: 17%;
    height: 100%;
    z-index: 10;
    opacity: 0;
    border-right: 2px solid rgb(60 210 165);
    background-image: linear-gradient(to right, rgba(60, 210, 165, 0), rgba(60, 210, 165,1));
}
.sweep-bar-anim {
	animation-name: fadeInAnimation;
	animation-duration: 5s;
	animation-timing-function: linear;
    animation-iteration-count: 1;
}
@keyframes fadeInAnimation {
    0% { opacity: 1; }
	10% { opacity: 1; }
	90% { opacity: 1; }
    100% { opacity: 1; left: 86%; }
}
</style>
