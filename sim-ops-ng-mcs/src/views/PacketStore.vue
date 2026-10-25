<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import axios from 'axios';
import { Modal } from 'bootstrap';
import { useAppOptionStore } from '@/stores/app-option';
import { useAuthStore } from '@/stores/app-auth';
import type { Bucket, SpacePacket } from '@/types/obj-store';

const appOption = useAppOptionStore(),
      authStore = useAuthStore();

const data = ref<Bucket[]>([]);
const loading = ref(true);
const error = ref<Error | null>(null);
const packet = ref<SpacePacket | null>(null);
let modal: Modal | null = null;
let pollInterval: ReturnType<typeof setInterval> | undefined;

const rows = computed(() => {
	const result = [];
	for (const bucket of data.value) {
		const type = bucket.bucket.endsWith('-tc') ? 'TC' : 'TM';
		for (const ts of bucket.data) {
			result.push({ bucket: bucket.bucket, type, apid: 10, ts });
		}
	}
	// TC object names are "<ts>-<suffix>", TM ones a bare "<ts>": order by the timestamp
	return result.sort((a, b) => parseInt(b.ts) - parseInt(a.ts) || b.ts.localeCompare(a.ts));
});
const tmRows = computed(() => rows.value.filter(row => row.type === 'TM'));
const tcRows = computed(() => rows.value.filter(row => row.type === 'TC'));

function fetchData() {
	axios.get<Bucket[]>(`${appOption.soAPI}/api/obj-store/tm`, authStore.authConfig())
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

function toUTC(ts: string): string {
	return new Date(parseInt(ts) * 1000).toISOString().replace('T', ' ').replace('.000Z', ' UTC');
}

// a TM float field; anything else (e.g. a packet from an older format) as is
function fixed(value: unknown): unknown {
	return typeof value === 'number' ? value.toFixed(6) : value;
}

function packetDetails(bucket: string, ts: string) {
	packet.value = null;
	axios.get<SpacePacket>(`${appOption.soAPI}/api/obj-store/sp/${bucket}/${ts}`, authStore.authConfig())
		.then(response => { packet.value = response.data; })
		.catch(e => { error.value = e as Error; });
	modal?.show();
}

function closeModal1() {
	modal?.hide();
}

onMounted(() => {
	modal = new Modal('#my-modal-1');
	fetchData();
	pollInterval = setInterval(fetchData, 5000);
});

onBeforeUnmount(() => clearInterval(pollInterval));
</script>

<template>
	<div id="my-modal-1" class="modal">
		<div class="modal-dialog modal-lg">
			<div class="modal-content">
				<div class="modal-header">
					<h5 class="modal-title">Space Packet</h5>
					<button type="button" class="btn-close" @click="closeModal1()"></button>
				</div>
				<div class="modal-body" v-if="packet">
					<h5 class="text-muted border-bottom">Primary Header</h5>
					<div class="row small text-secondary mb-3">
						<div class="col-3">Version<br/><code>{{ packet.primary_header.version }}</code></div>
						<div class="col-3">Type<br/><code>{{ packet.primary_header.type }}</code></div>
						<div class="col-3">Sec. Hdr.<br/><code>{{ packet.primary_header.sec_hdr_flag }}</code></div>
						<div class="col-3">APID<br/><code>{{ packet.primary_header.apid }}</code></div>
						<div class="col-3">Seq. Flags<br/><code>{{ packet.primary_header.sequence_flags }}</code></div>
						<div class="col-3">Seq. Count<br/><code>{{ packet.primary_header.sequence_count }}</code></div>
						<div class="col-3">Data Length<br/><code>{{ packet.primary_header.data_length }}</code></div>
					</div>
					<h5 class="text-muted border-bottom">Payload</h5>
					<div class="row small text-secondary" v-if="packet.primary_header.type === 'TC'">
						<div class="col-3">Command<br/><code>{{ packet.payload.command }}</code></div>
						<div class="col-3">Value<br/><code>{{ packet.payload.value }}</code></div>
					</div>
					<div class="row small text-secondary" v-else>
						<div class="col-2">Time Step<br/><code>{{ packet.payload.ts }}</code></div>
						<div class="col-2">AOCS Chain<br/><code>{{ packet.payload.aocs_chain }}</code></div>
						<div class="col-2">AOCS Mode<br/><code>{{ packet.payload.aocs_mode }}</code></div>
						<div class="col-2">AOCS Valid<br/><code>{{ packet.payload.aocs_valid }}</code></div>
						<div class="col-2">AOCS Rotation X<br/><code>{{ fixed(packet.payload.aocs_rotation_x) }}</code></div>
						<div class="col-2">AOCS Rotation Y<br/><code>{{ fixed(packet.payload.aocs_rotation_y) }}</code></div>
						<div class="col-2">AOCS Rotation Z<br/><code>{{ fixed(packet.payload.aocs_rotation_z) }}</code></div>
						<div class="col-2">AOCS Rate X<br/><code>{{ fixed(packet.payload.aocs_rate_x) }}</code></div>
						<div class="col-2">AOCS Rate Y<br/><code>{{ fixed(packet.payload.aocs_rate_y) }}</code></div>
						<div class="col-2">AOCS Rate Z<br/><code>{{ fixed(packet.payload.aocs_rate_z) }}</code></div>
						<div class="col-2">AOCS Sun Ang.<br/><code>{{ fixed(packet.payload.aocs_sun_angle) }}</code></div>
						<div class="col-2">AOCS Nadir Ang.<br/><code>{{ fixed(packet.payload.aocs_nadir_angle) }}</code></div>
						<div class="col-2">TTC Chain<br/><code>{{ packet.payload.ttc_chain }}</code></div>
						<div class="col-2">TTC MCU<br/><code>{{ packet.payload.ttc_mcu }}</code></div>
						<div class="col-2">TTC Mode<br/><code>{{ packet.payload.ttc_mode }}</code></div>
						<div class="col-2">TTC Sb Antenna<br/><code>{{ packet.payload.ttc_s_antenna }}</code></div>
						<div class="col-2">TTC Xb Antenna<br/><code>{{ packet.payload.ttc_x_antenna }}</code></div>
						<div class="col-2">TTC Link Margin UL<br/><code>{{ fixed(packet.payload.ttc_link_margin_ul) }}</code></div>
						<div class="col-2">TTC State UL<br/><code>{{ packet.payload.ttc_state_ul }}</code></div>
						<div class="col-2">TTC Coherent<br/><code>{{ packet.payload.ttc_coherent }}</code></div>
						<div class="col-2">TTC Sb TX Status<br/><code>{{ packet.payload.ttc_s_tx_status }}</code></div>
						<div class="col-2">TTC Sb RX Status<br/><code>{{ packet.payload.ttc_s_rx_status }}</code></div>
						<div class="col-2">TTC Xb TX Status<br/><code>{{ packet.payload.ttc_x_tx_status }}</code></div>
						<div class="col-2">TTC Xb RX Status<br/><code>{{ packet.payload.ttc_x_rx_status }}</code></div>
						<div class="col-2">TTC Ping Ack.<br/><code>{{ packet.payload.ttc_ping_ack }}</code></div>
						<div class="col-2">TTC Ranging<br/><code>{{ packet.payload.ttc_ranging }}</code></div>
						<div class="col-2">EPS Chain<br/><code>{{ packet.payload.eps_chain }}</code></div>
						<div class="col-2">EPS Net Power<br/><code>{{ fixed(packet.payload.eps_net_power) }}</code></div>
						<div class="col-2">EPS Sol. Arr. 1<br/><code>{{ packet.payload.eps_sol_array_1 }}</code></div>
						<div class="col-2">EPS Sol. Arr. 2<br/><code>{{ packet.payload.eps_sol_array_2 }}</code></div>
						<div class="col-2">EPS Batt. DOD<br/><code>{{ fixed(packet.payload.eps_battery_dod) }}</code></div>
						<div class="col-2">EPS Temperature<br/><code>{{ fixed(packet.payload.eps_temperature) }}</code></div>
						<div class="col-2">EPS ACU<br/><code>{{ packet.payload.eps_acu }}</code></div>
						<div class="col-2">EPS PDU<br/><code>{{ packet.payload.eps_pdu }}</code></div>
						<div class="col-2">EPS Power Src.<br/><code>{{ packet.payload.eps_power_source }}</code></div>
					<div class="col-2">EPS Power Status<br/><code>{{ packet.payload.eps_power_status }}</code></div>
						<div class="col-2">DHS Chain<br/><code>{{ packet.payload.dhs_chain }}</code></div>
						<div class="col-2">DHS OBSW Mode<br/><code>{{ packet.payload.dhs_obsw_mode }}</code></div>
						<div class="col-2">DHS Mem. Dump<br/><code>{{ packet.payload.dhs_mem_dump_enabled }}</code></div>
						<div class="col-2">DHS Memory<br/><code>{{ fixed(packet.payload.dhs_memory) }}</code></div>
						<div class="col-2">DHS TM Count<br/><code>{{ packet.payload.dhs_tm_counter }}</code></div>
						<div class="col-2">DHS TC Count<br/><code>{{ packet.payload.dhs_tc_counter }}</code></div>
						<div class="col-2">PL GNSS<br/><code>{{ packet.payload.pl_gnss_status }}</code></div>
						<div class="col-2">PL GNSS Lat<br/><code>{{ packet.payload.pl_gnss_lat }}</code></div>
						<div class="col-2">PL GNSS Lon<br/><code>{{ packet.payload.pl_gnss_lon }}</code></div>
						<div class="col-2">PL GNSS Alt<br/><code>{{ packet.payload.pl_gnss_alt }}</code></div>
						<div class="col-2">PL Camera<br/><code>{{ packet.payload.pl_camera_status }}</code></div>
						<div class="col-2">PL SDR<br/><code>{{ packet.payload.pl_sdr_status }}</code></div>
					</div>
				</div>
				<div class="modal-body text-muted" v-else>
					Loading packet…
				</div>
				<div class="modal-footer">
					<button type="button" class="btn btn-outline-secondary" @click="closeModal1()">Close</button>
				</div>
			</div>
		</div>
	</div>

	<h1 class="page-header">Packet Store <small>Space Packets</small></h1>
	<hr class="mb-4">

	<div v-if="loading">Loading …</div>

	<div v-else-if="error" class="alert alert-danger">
		Could not reach object store: {{ error.message }}
	</div>

	<div v-else class="row">
		<div class="col-md-6">
			<h5 class="text-muted border-bottom">TM Packets</h5>
			<table class="table table-sm table-hover small" v-if="tmRows.length">
				<thead>
					<tr>
						<th>Packet</th>
						<th>Type</th>
						<th>APID</th>
						<th>Timestamp (UTC)</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="row in tmRows" :key="row.bucket + row.ts" class="pointer" @click="packetDetails(row.bucket, row.ts)">
						<td><code>SpacePacket</code></td>
						<td><code>{{ row.type }}</code></td>
						<td><code>{{ row.apid }}</code></td>
						<td><code>{{ toUTC(row.ts) }}</code></td>
					</tr>
				</tbody>
			</table>
			<p v-else>No TM packets found.</p>
		</div>
		<div class="col-md-6">
			<h5 class="text-muted border-bottom">TC Packets</h5>
			<table class="table table-sm table-hover small" v-if="tcRows.length">
				<thead>
					<tr>
						<th>Packet</th>
						<th>Type</th>
						<th>APID</th>
						<th>Timestamp (UTC)</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="row in tcRows" :key="row.bucket + row.ts" class="pointer" @click="packetDetails(row.bucket, row.ts)">
						<td><code>SpacePacket</code></td>
						<td><code>{{ row.type }}</code></td>
						<td><code>{{ row.apid }}</code></td>
						<td><code>{{ toUTC(row.ts) }}</code></td>
					</tr>
				</tbody>
			</table>
			<p v-else>No TC packets found.</p>
		</div>
	</div>
</template>

<style>
.pointer:hover { cursor: pointer; }
</style>
