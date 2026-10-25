<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import axios from 'axios';
import { Modal } from 'bootstrap';
import { useAppOptionStore } from '@/stores/app-option';
import { useSocketStore } from '@/stores/app-websockets';
import { useAuthStore } from '@/stores/app-auth';
import TelemetryStatus from '@/components/app/TelemetryStatus.vue';
import AckStatus from '@/components/app/AckStatus.vue';
import type { FDProduct } from '@/types/obj-store';

type UploadType = 'command-seq' | 'orbit-control' | 'science-seq';

const appOption = useAppOptionStore(),
      socketStore = useSocketStore(),
      authStore = useAuthStore();

// one selection per modal, so a file picked in one is never sent from another
const file_uploads = ref<Record<UploadType, string | null>>({ 'command-seq': null, 'orbit-control': null, 'science-seq': null });
const fd_ttq_selected = ref<string | null>(null);
const is_armed = ref(false);
const flight_dynamics = ref<FDProduct[]>([]);
const pending_index = ref(-1);
const history_pending = ref(false);
const history_pending_ts = ref<string | null>(null);
// my-modal-1..3: the file uploads, in UploadType order; my-modal-4: the FD TTQ upload
const modals: Modal[] = [];

const manual_stack = computed(() => {
	const padded = [...socketStore.tc_stack];
	while (padded.length < 5) padded.push({ command: 'none' });
	return padded;
});

const tc_history = computed(() => {
	const result: [string, string | null][] = socketStore.tc_history.slice(0, 20).map(h => [h.command, h.status || null]);
	if (history_pending.value) {
		result.unshift(['__pending__', '__pending__']);
		if (result.length > 20) result.pop();
	}
	while (result.length < 20) result.push(['none', null]);
	return result;
});

function stackSize(): number {
	return socketStore.tc_stack.length;
}

function addStack(command: string, control: string, value: string | boolean) {
	pending_index.value = stackSize();
	const body = { system: 'spacecraft', control, value, command };
	axios.post(`${appOption.soAPI}/api/tc-stack`, body, authStore.authConfig())
		.catch((error) => {
			console.error('TC stack push error:', error);
			pending_index.value = -1;
		});
}

function toggleArm() {
	const c = (document.getElementById("manual-stack") as HTMLTableElement | null)?.rows[0]?.cells[0];
	if (!c) return;

	c.classList.toggle("text-warning");
	c.classList.toggle("text-success");
	c.classList.toggle("app-tc-loaded");
	c.classList.toggle("app-tc-armed");
}

function armButton() {
	is_armed.value = true;
	toggleArm();
}

function goButton() {
	toggleArm();
	history_pending_ts.value = socketStore.tc_history[0]?.ts ?? null;
	history_pending.value = true;
	axios.post(`${appOption.soAPI}/api/tc-stack/execute`, null, authStore.authConfig())
		.then(() => { is_armed.value = false; })
		.catch((error) => {
			console.error('TC execute error:', error);
			is_armed.value = false;
			history_pending.value = false;
		});
}

function delCommand(i: number) {
	axios.delete(`${appOption.soAPI}/api/tc-stack/${i}`, authStore.authConfig())
		.catch((error) => console.error('TC stack delete error:', error));
}

function fileUpload(type: UploadType | 'fd-ttq') {
	const filename = type == 'fd-ttq' ? fd_ttq_selected.value : file_uploads.value[type];
	if (!filename)
		return;  // the Uplink buttons are disabled until there is a selection

	modals.forEach((modal) => modal.hide());

	const short_name = filename.slice(0, 14);
	const body = { 'system': 'spacecraft', 'control': 'dhs_uploaded', 'value': `${type} > ${short_name}`, 'command': `UP: ${type} > ${short_name}` };
	// sent directly, not via the stack, whose execute would run its head (maybe another TC)
	axios.post(`${appOption.soAPI}/api/tc-stack/send`, body, authStore.authConfig())
		.catch((error) => console.error('File upload TC error:', error));
}

function onFileChange(type: UploadType, event: Event) {
	const files = (event.target as HTMLInputElement).files;

	// an empty list when the file picker is cancelled
	file_uploads.value[type] = files?.[0]?.name ?? null;
}

const openModal1 = () => modals[0]?.show();
const openModal2 = () => modals[1]?.show();
const openModal3 = () => modals[2]?.show();
const closeModal1 = () => modals[0]?.hide();
const closeModal2 = () => modals[1]?.hide();
const closeModal3 = () => modals[2]?.hide();
const closeModal4 = () => modals[3]?.hide();

function openModal4() {
	axios.get<FDProduct[]>(`${appOption.soAPI}/api/obj-store/fd`, authStore.authConfig())
		.then(response => {
			flight_dynamics.value = response.data.filter(e => e.status === 2);
			const ids = flight_dynamics.value.map(e => e.id);
			if (!fd_ttq_selected.value || !ids.includes(fd_ttq_selected.value))
				fd_ttq_selected.value = ids[0] ?? null;
		})
		.catch(error => {
			console.error('Flight dynamics fetch error:', error);
		})
		.finally(() => {
			modals[3]?.show();
		});
}

onMounted(() => {
	for (let n = 1; n <= 4; n++) modals.push(new Modal(`#my-modal-${n}`));

	// Clear the pending spinner once the queued command actually lands in the stack
	watch(
		() => socketStore.tc_stack.length,
		(len) => {
			if (pending_index.value != -1 && len > pending_index.value) {
				pending_index.value = -1;
			}
		}
	);

	// Clear the history spinner once the executed command's result lands at the top of history
	watch(
		() => socketStore.tc_history[0]?.ts,
		(newTs) => {
			if (history_pending.value && newTs !== history_pending_ts.value) {
				history_pending.value = false;
			}
		}
	);
});
</script>
<template>
	<h1 class="page-header">
		SpaCon <small>Spacecraft Controller</small>
		<telemetry-status :downlink="false" />
	</h1>
	<hr class="mb-4">

	<div id="my-modal-1" class="modal">
		<div class="modal-dialog">
			<div class="modal-content">
			<div class="modal-header">
				<h5 class="modal-title">CFDP Command Sequence Uplink</h5>
				<button type="button" class="btn-close" @click="closeModal1()"></button>
			</div>
			<div class="modal-body">
				<div class="mb-3">
  					<label class="form-label" for="defaultFile">Choose file</label>
  					<input @change="onFileChange('command-seq', $event)" type="file" class="form-control">
				</div>
			</div>
			<div class="modal-footer">
				<button type="button" class="btn btn-outline-secondary" @click="closeModal1()">Cancel</button>
				<button @click="fileUpload('command-seq')" type="button" class="btn btn-outline-theme" :disabled="!file_uploads['command-seq']">Uplink</button>
			</div>
			</div>
		</div>
	</div>

	<div id="my-modal-2" class="modal">
		<div class="modal-dialog">
			<div class="modal-content">
			<div class="modal-header">
				<h5 class="modal-title">CFDP Orbit Control Uplink</h5>
				<button type="button" class="btn-close" @click="closeModal2()"></button>
			</div>
			<div class="modal-body">
				<div class="mb-3">
  					<label class="form-label" for="defaultFile">Choose file</label>
  					<input @change="onFileChange('orbit-control', $event)" type="file" class="form-control">
				</div>
			</div>
			<div class="modal-footer">
				<button type="button" class="btn btn-outline-secondary" @click="closeModal2()">Cancel</button>
				<button @click="fileUpload('orbit-control')" type="button" class="btn btn-outline-theme" :disabled="!file_uploads['orbit-control']">Uplink</button>
			</div>
			</div>
		</div>
	</div>

	<div id="my-modal-3" class="modal">
		<div class="modal-dialog">
			<div class="modal-content">
			<div class="modal-header">
				<h5 class="modal-title">CFDP Science Sequence Uplink</h5>
				<button type="button" class="btn-close" @click="closeModal3()"></button>
			</div>
			<div class="modal-body">
				<div class="mb-3">
  					<label class="form-label" for="defaultFile">Choose file</label>
  					<input @change="onFileChange('science-seq', $event)" type="file" class="form-control">
				</div>
			</div>
			<div class="modal-footer">
				<button type="button" class="btn btn-outline-secondary" @click="closeModal3()">Cancel</button>
				<button @click="fileUpload('science-seq')" type="button" class="btn btn-outline-theme" :disabled="!file_uploads['science-seq']">Uplink</button>
			</div>
			</div>
		</div>
	</div>

	<div id="my-modal-4" class="modal">
		<div class="modal-dialog">
			<div class="modal-content">
			<div class="modal-header">
				<h5 class="modal-title">CFDP Flight Dynamics TTQ Uplink</h5>
				<button type="button" class="btn-close" @click="closeModal4()"></button>
			</div>
			<div class="modal-body">
				<form>
					<div class="form-check" v-for="(d, index) in flight_dynamics" :key="index">
						<input class="form-check-input" type="radio" name="fd_ttq_select" :id="d.id" :value="d.id" v-model="fd_ttq_selected">
						<label class="form-check-label" :for="d.id">TTQ from product:{{ d.id }}</label>
					</div>
				</form>
			</div>
			<div class="modal-footer">
				<button type="button" class="btn btn-outline-secondary" @click="closeModal4()">Cancel</button>
				<button @click="fileUpload('fd-ttq')" type="button" class="btn btn-outline-theme" :disabled="!fd_ttq_selected">Uplink</button>
			</div>
			</div>
		</div>
	</div>

	<div class="row">
		<div class="col-xl-4 col-lg-4">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">TC Manual Stack</card-header>
				<card-body>
					<div class="row">
						<div class="col-xl-8 col-lg-8">
							<table id="manual-stack" class="table table-sm mb-2px small text-nowrap">
								<tbody>
									<tr v-for="(item, i) in manual_stack" :key="i">
										<td :class="{ 'text-success': manual_stack[i].command != 'none', 'app-tc-loaded': manual_stack[i].command != 'none' }">
											<span v-if="i === pending_index" class="spinner-border spinner-border-sm text-secondary" role="status"><span class="visually-hidden">Loading...</span></span>
											<template v-else>{{ item.command }}</template>
										</td>
										<td class="text-end">
											<a href="#" @click.prevent="delCommand(i)" v-if="item.command != 'none'">
											<i class="fas fa-times text-danger"></i></a>
										</td>
									</tr>
								</tbody>
							</table>
						</div>
						<div class="col-xl-4 col-lg-4 text-center">
							<button @click="armButton" id="arm-button" type="button" class="btn btn-outline-warning ms-2 mt-2" :disabled="stackSize() == 0" style="width: 94px;">ARM</button>
							<button @click="goButton" id="go-button" type="button" class="btn btn-outline-success ms-2 mt-2" :disabled="!is_armed" style="width: 94px;">GO</button>
						</div>
					</div>
				</card-body>
			</card>
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">TC History</card-header>
				<card-body>
					<table class="table table-sm mb-2px small text-nowrap">
						<tbody>
							<tr v-for="(item, i) in tc_history" :key="i">
								<td v-if="item[0] === '__pending__'">
									<span class="spinner-border spinner-border-sm text-secondary" role="status"><span class="visually-hidden">Loading...</span></span>
								</td>
								<td v-else>{{ item[0] }}</td>
								<td v-if="item[0] === '__pending__'" class="text-end fw-bold">&nbsp;</td>
								<td v-else class="text-end"><ack-status v-if="item[1]" :status="item[1]" /></td>
							</tr>
						</tbody>
					</table>
				</card-body>
			</card>
		</div>
		<div class="col-xl-8 col-lg-8">
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">TC Database</card-header>
				<card-body>
					<div>
						<div class="app-tc-group">
							<span class="app-tc-label">AOCS</span>
							<div class="d-flex flex-wrap gap-1">
								<button @click="addStack('TC_AOCS_001', 'aocs_mode', 'SUN')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set AOCS Mode SUN">TC_AOCS_001</button>
								<button @click="addStack('TC_AOCS_002', 'aocs_mode', 'TARGET')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set AOCS Mode TARGET">TC_AOCS_002</button>
								<button @click="addStack('TC_AOCS_003', 'aocs_mode', 'NADIR')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set AOCS Mode NADIR">TC_AOCS_003</button>
								<button @click="addStack('TC_AOCS_011', 'aocs_chain', 'A')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set AOCS Chain A">TC_AOCS_011</button>
								<button @click="addStack('TC_AOCS_012', 'aocs_chain', 'B')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set AOCS Chain B">TC_AOCS_012</button>
								<button @click="addStack('TC_AOCS_021', 'aocs_valid', 'valid')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Calibrate AOCS sensors">TC_AOCS_021</button>
							</div>
						</div>
						<div class="app-tc-group">
							<span class="app-tc-label">TTC</span>
							<div class="d-flex flex-wrap gap-1">
								<button @click="addStack('TC_TTC_001', 'ttc_mode', 'S_Sup_LBR')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Mode S_Sup_LBR">TC_TTC_001</button>
								<button @click="addStack('TC_TTC_002', 'ttc_mode', 'S_Sup_HBR')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Mode S_Sup_HBR">TC_TTC_002</button>
								<button @click="addStack('TC_TTC_003', 'ttc_mode', 'X_Sup_LBR')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Mode X_Sup_LBR">TC_TTC_003</button>
								<button @click="addStack('TC_TTC_004', 'ttc_mode', 'X_Sup_HBR')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Mode X_Sup_HBR">TC_TTC_004</button>
								<button @click="addStack('TC_TTC_005', 'ttc_mode', 'S_Res_LBR')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Mode S_Res_LBR">TC_TTC_005</button>
								<button @click="addStack('TC_TTC_006', 'ttc_mode', 'X_Res_LBR')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Mode X_Res_LBR">TC_TTC_006</button>
								<button @click="addStack('TC_TTC_007', 'ttc_mode', 'S_Sub_LBR')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Mode S_Sub_LBR">TC_TTC_007</button>
								<button @click="addStack('TC_TTC_008', 'ttc_mode', 'X_Sub_LBR')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Mode X_Sub_LBR">TC_TTC_008</button>
								<button @click="addStack('TC_TTC_011', 'ttc_chain', 'A')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Chain A">TC_TTC_011</button>
								<button @click="addStack('TC_TTC_012', 'ttc_chain', 'B')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Chain B">TC_TTC_012</button>
								<button @click="addStack('TC_TTC_021', 'ttc_ping', '')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Ping Spacecraft">TC_TTC_021</button>
								<button @click="addStack('TC_TTC_022', 'ttc_coherent', 'enabled')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Enable Coherent Transmitter">TC_TTC_022</button>
								<button @click="addStack('TC_TTC_023', 'ttc_coherent', 'disabled')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Disable Coherent Transmitter">TC_TTC_023</button>
								<button @click="addStack('TC_TTC_041', 'ttc_mcu_reboot', '')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Software Reboot MCU">TC_TTC_041</button>
								<button @click="addStack('TC_TTC_051', 'ttc_s_antenna', 'LGA_RHC')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Sb Antenna LGA RHC">TC_TTC_051</button>
								<button @click="addStack('TC_TTC_052', 'ttc_s_antenna', 'LGA_LHC')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Sb Antenna LGA LHC">TC_TTC_052</button>
								<button @click="addStack('TC_TTC_053', 'ttc_x_antenna', 'MGA')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Xb Antenna MGA">TC_TTC_053</button>
								<button @click="addStack('TC_TTC_054', 'ttc_x_antenna', 'HGA')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set TTC Xb Antenna HGA">TC_TTC_054</button>
								<button @click="addStack('TC_TTC_061', 'ttc_ranging', 'enabled')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Enable Ranging">TC_TTC_061</button>
								<button @click="addStack('TC_TTC_062', 'ttc_ranging', 'disabled')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Disable Ranging">TC_TTC_062</button>
							</div>
						</div>
						<div class="app-tc-group">
							<span class="app-tc-label">EPS</span>
							<div class="d-flex flex-wrap gap-1">
								<button @click="addStack('TC_EPS_001', 'eps_chain', 'A')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set EPS Chain A">TC_EPS_001</button>
								<button @click="addStack('TC_EPS_002', 'eps_chain', 'B')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set EPS Chain B">TC_EPS_002</button>
								<button @click="addStack('TC_EPS_021', 'eps_sol_array_1_reset', '')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Reset Solar Array 1 Electrical Channel">TC_EPS_021</button>
								<button @click="addStack('TC_EPS_022', 'eps_sol_array_2_reset', '')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Reset Solar Array 2 Electrical Channel">TC_EPS_022</button>
								<button @click="addStack('TC_EPS_041', 'eps_power_cycle_aocs', '')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power Cycle AOCS">TC_EPS_041</button>
								<button @click="addStack('TC_EPS_042', 'eps_power_cycle_ttc', '')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power Cycle TTC">TC_EPS_042</button>
								<button @click="addStack('TC_EPS_043', 'eps_power_cycle_acu', '')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power Cycle ACU">TC_EPS_043</button>
								<button @click="addStack('TC_EPS_044', 'eps_power_cycle_pdu', '')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power Cycle PDU">TC_EPS_044</button>
								<button @click="addStack('TC_EPS_051', 'eps_ttc_s_tx', 'on')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power On TTC Sb Transmitter">TC_EPS_051</button>
								<button @click="addStack('TC_EPS_052', 'eps_ttc_s_tx', 'off')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power Off TTC Sb Transmitter">TC_EPS_052</button>
								<button @click="addStack('TC_EPS_053', 'eps_ttc_s_rx', 'on')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power On TTC Sb Receiver">TC_EPS_053</button>
								<button @click="addStack('TC_EPS_054', 'eps_ttc_s_rx', 'off')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power Off TTC Sb Receiver">TC_EPS_054</button>
								<button @click="addStack('TC_EPS_055', 'eps_ttc_x_tx', 'on')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power On TTC Xb Transmitter">TC_EPS_055</button>
								<button @click="addStack('TC_EPS_056', 'eps_ttc_x_tx', 'off')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power Off TTC Xb Transmitter">TC_EPS_056</button>
								<button @click="addStack('TC_EPS_057', 'eps_ttc_x_rx', 'on')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power On TTC Xb Receiver">TC_EPS_057</button>
								<button @click="addStack('TC_EPS_058', 'eps_ttc_x_rx', 'off')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power Off TTC Xb Receiver">TC_EPS_058</button>
							</div>
						</div>
						<div class="app-tc-group">
							<span class="app-tc-label">DHS</span>
							<div class="d-flex flex-wrap gap-1">
								<button @click="addStack('TC_DHS_001', 'dhs_chain', 'A')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set DHS Chain A">TC_DHS_001</button>
								<button @click="addStack('TC_DHS_002', 'dhs_chain', 'B')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set DHS Chain B">TC_DHS_002</button>
								<button @click="addStack('TC_DHS_011', 'dhs_obsw_mode', 'safe')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set OBSW to Safe Mode">TC_DHS_011</button>
								<button @click="addStack('TC_DHS_012', 'dhs_obsw_mode', 'nominal')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Set OBSW to Nominal Mode">TC_DHS_012</button>
								<button @click="addStack('TC_DHS_021', 'dhs_mem_dump_enabled', true)" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Enable Memory Dump">TC_DHS_021</button>
								<button @click="addStack('TC_DHS_022', 'dhs_mem_dump_enabled', false)" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Disable Memory Dump">TC_DHS_022</button>
							</div>
						</div>
						<div class="app-tc-group">
							<span class="app-tc-label">Payload</span>
							<div class="d-flex flex-wrap gap-1">
								<button @click="addStack('TC_PL_001', 'pl_gnss_status', 'on')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power On GNSS Receiver">TC_PL_001</button>
								<button @click="addStack('TC_PL_002', 'pl_gnss_status', 'off')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power Off GNSS Receiver">TC_PL_002</button>
								<button @click="addStack('TC_PL_011', 'pl_camera_status', 'on')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power On Camera">TC_PL_011</button>
								<button @click="addStack('TC_PL_012', 'pl_camera_status', 'off')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power Off Camera">TC_PL_012</button>
								<button @click="addStack('TC_PL_021', 'pl_sdr_status', 'on')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power On SDR">TC_PL_021</button>
								<button @click="addStack('TC_PL_022', 'pl_sdr_status', 'off')" type="button" class="btn btn-sm btn-outline-theme app-tc-btn" title="Power Off SDR">TC_PL_022</button>
							</div>
						</div>
					</div>
				</card-body>
			</card>
			<card class="mb-3">
				<card-header class="card-header fw-bold small text-center p-1">CFDP Files Uplink Service</card-header>
				<card-body class="text-center">
					<div class="row">
						<div class="col">
							<button type="button" class="btn btn-sm btn-outline-theme m-1 app-my-width" @click="openModal1()">Command<br/>Sequence</button>
						</div>
						<div class="col">
							<button type="button" class="btn btn-sm btn-outline-theme m-1 app-my-width" @click="openModal2()">Orbit<br/>Control</button>
						</div>
						<div class="col">
							<button type="button" class="btn btn-sm btn-outline-theme m-1 app-my-width" @click="openModal3()">Science<br/>Sequence</button>
						</div>
						<div class="col">
							<button type="button" class="btn btn-sm btn-outline-theme m-1 app-my-width" @click="openModal4()">Flight<br/>Dynamics</button>
						</div>
					</div>
				</card-body>
			</card>
		</div>
	</div>

</template>

<style>
.app-fs-small { font-size: small; }
.app-my-width { width: 120px; }
.app-tc-btn { font-size: 0.8rem; line-height: 1.5; padding: 0.2rem 0.5rem; }
.app-tc-group { display: block; padding: 0.35rem 0; border-bottom: 1px solid rgba(128,128,128,0.15); }
.app-tc-group:last-child { border-bottom: none; }
.app-tc-label { display: block; font-size: 0.75rem; font-weight: bold; margin-bottom: 0.3rem; }
tr:has(.app-tc-loaded) { border-bottom: 1px solid #3cd2a5; }
tr:has(.app-tc-armed) { border-bottom: 1px solid #ff9f0c; }
</style>
