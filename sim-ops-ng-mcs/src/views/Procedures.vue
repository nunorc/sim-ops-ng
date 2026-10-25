<script lang="ts">
export default {
	components: {

	},
	data() {
		const establishUplink = [
			{ 'num' : '1', 'con': '', 'action': 'Check G/S program track is enabled', 'tc': 'OM > Program Track'},
			{ 'num' : '2', 'con': 'U/L Power needs to be >= 50 dBm', 'action': 'Check G/S uplink power is set', 'tc': 'OM > U/L Power'},
			{ 'num' : '3', 'con': 'U/L carrier off; on-board receiver for the band must be on', 'action': 'Check uplink band is selected (S / X)', 'tc': 'OM > U/L Band'},
			{ 'num' : '4', 'con': 'Requires elevation above 5°', 'action': 'Enable uplink carrier', 'tc': 'OM > U/L Carrier'},
			{ 'num' : '5', 'con': 'Requires uplink carrier on', 'action': 'Perform sweep', 'tc': 'OM > Sweep'}
		];
		const establishDownlink = [
			{ 'num' : '1', 'con': '', 'action': 'Check G/S program track is enabled', 'tc': 'OM > Program Track'},
			{ 'num' : '2', 'con': 'Uplink not yet established', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '3', 'con': 'On-board transmitter off for the current band', 'action': 'Check on-board transmitter is powered on (Sb / Xb)', 'tc': 'TC_EPS_051 / TC_EPS_055'},
			{ 'num' : '4', 'con': '', 'action': 'Check TTC mode matches expected value, SNR and spectrum', 'tc': 'OM > D/L Spectrum'},
			{ 'num' : '5', 'con': '', 'action': 'Check onboard TTC mode is selected on G/S', 'tc': 'OM > Mode'}
		];
		const enableRanging = [
			{ 'num' : '1', 'con': 'No U/L Bit Lock', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '2', 'con': 'No D/L Frame Lock', 'action': 'Check downlink is established', 'tc': '<a href="#EstablishDownlink">Establish Downlink</a>'},
			{ 'num' : '3', 'con': '', 'action': 'Enable ranging in S/C', 'tc': 'TC_TTC_061'},
			{ 'num' : '4', 'con': '', 'action': 'Enable ranging in G/S', 'tc': 'OM > Enable Ranging'},
		];
		const enableDoppler = [
			{ 'num' : '1', 'con': 'No U/L Bit Lock', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '2', 'con': 'No D/L Frame Lock', 'action': 'Check downlink is established', 'tc': '<a href="#EstablishDownlink">Establish Downlink</a>'},
			{ 'num' : '3', 'con': '', 'action': 'Enable coherent transmitter in S/C', 'tc': 'TC_TTC_022'},
			{ 'num' : '4', 'con': '', 'action': 'Enable doppler in G/S', 'tc': 'OM > Enable Doppler'}
		];
		const changeTtcMode =[
			{ 'num' : '1', 'con': 'No U/L Bit Lock', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '2', 'con': 'No D/L Frame Lock', 'action': 'Check downlink is established', 'tc': '<a href="#EstablishDownlink">Establish Downlink</a>'},
			{ 'num' : '3', 'con': '', 'action': 'Set desired TTC Mode in S/C', 'tc': 'TC_TTC_00X'},
			{ 'num' : '4', 'con': '', 'action': 'Set desired TTC Mode in G/S', 'tc': 'OM > Mode'}
		];
		const downloadData = [
			{ 'num' : '1', 'con': 'Uplink not yet established', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '2', 'con': 'Downlink not yet established', 'action': 'Check downlink is established', 'tc': '<a href="#EstablishDownlink">Establish Downlink</a>'},
			{ 'num' : '3', 'con': '', 'action': 'Enable memory dump', 'tc': 'TC_DHS_021'}
		];
		const switchOnGNSS = [
			{ 'num' : '1', 'con': 'Uplink not yet established', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '2', 'con': 'Downlink not yet established', 'action': 'Check downlink is established', 'tc': '<a href="#EstablishDownlink">Establish Downlink</a>'},
			{ 'num' : '3', 'con': 'Requires OBSW Mode nominal', 'action': 'Power on GNSS receiver', 'tc': 'TC_PL_001'}
		];
		const switchOffGNSS = [
			{ 'num' : '1', 'con': 'Uplink not yet established', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '2', 'con': 'Downlink not yet established', 'action': 'Check downlink is established', 'tc': '<a href="#EstablishDownlink">Establish Downlink</a>'},
			{ 'num' : '3', 'con': 'Requires OBSW Mode nominal', 'action': 'Power off GNSS receiver', 'tc': 'TC_PL_002'}
		];
		const switchOnCamera = [
			{ 'num' : '1', 'con': 'Uplink not yet established', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '2', 'con': 'Downlink not yet established', 'action': 'Check downlink is established', 'tc': '<a href="#EstablishDownlink">Establish Downlink</a>'},
			{ 'num' : '3', 'con': 'Requires OBSW Mode nominal', 'action': 'Power on camera', 'tc': 'TC_PL_011'}
		];
		const switchOffCamera = [
			{ 'num' : '1', 'con': 'Uplink not yet established', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '2', 'con': 'Downlink not yet established', 'action': 'Check downlink is established', 'tc': '<a href="#EstablishDownlink">Establish Downlink</a>'},
			{ 'num' : '3', 'con': 'Requires OBSW Mode nominal', 'action': 'Power off camera', 'tc': 'TC_PL_012'}
		];
		const switchOnSDR = [
			{ 'num' : '1', 'con': 'Uplink not yet established', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '2', 'con': 'Downlink not yet established', 'action': 'Check downlink is established', 'tc': '<a href="#EstablishDownlink">Establish Downlink</a>'},
			{ 'num' : '3', 'con': 'Requires OBSW Mode nominal', 'action': 'Power on SDR', 'tc': 'TC_PL_021'}
		];
		const switchOffSDR = [
			{ 'num' : '1', 'con': 'Uplink not yet established', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '2', 'con': 'Downlink not yet established', 'action': 'Check downlink is established', 'tc': '<a href="#EstablishDownlink">Establish Downlink</a>'},
			{ 'num' : '3', 'con': 'Requires OBSW Mode nominal', 'action': 'Power off SDR', 'tc': 'TC_PL_022'}
		];
		const changeAocsMode = [
			{ 'num' : '1', 'con': 'Uplink not yet established', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '2', 'con': 'Downlink not yet established', 'action': 'Check downlink is established', 'tc': '<a href="#EstablishDownlink">Establish Downlink</a>'},
			{ 'num' : '3', 'con': '', 'action': 'Set desired AOCS mode (Sun / Target / Nadir)', 'tc': 'TC_AOCS_001 / TC_AOCS_002 / TC_AOCS_003'}
		];
		const pingSpacecraft = [
			{ 'num' : '1', 'con': 'Uplink not yet established', 'action': 'Check uplink is established', 'tc': '<a href="#EstablishUplink">Establish Uplink</a>'},
			{ 'num' : '2', 'con': 'High-priority command; processed even with TTC MCU in error', 'action': 'Ping spacecraft', 'tc': 'TC_TTC_021'}
		];
		return {
			procedures: [establishUplink, establishDownlink, enableRanging, enableDoppler, changeTtcMode, downloadData, switchOnGNSS, switchOffGNSS, switchOnCamera, switchOffCamera, switchOnSDR, switchOffSDR, changeAocsMode, pingSpacecraft],
			procedurenames: ["Establish Uplink", "Establish Downlink", "Enable Ranging", "Enable Doppler", "Change TTC Mode", "Dump Onboard Memory", "Power on GNSS Receiver", "Power off GNSS Receiver", "Power on Camera", "Power off Camera", "Power on SDR", "Power off SDR", "Change AOCS Mode", "Ping Spacecraft"]
		}
	},
	methods: {
		searchTable() {
			const input = document.getElementById("myInput") as HTMLInputElement | null;
			const filter = (input?.value ?? '').toUpperCase();

			document.querySelectorAll<HTMLElement>(".for-loop").forEach((div) => {
				const txt = (div.getElementsByTagName("h4")[0]?.textContent ?? '').toUpperCase();
				div.style.display = txt.includes(filter) ? "" : "none";
			});
		}
	}
}
</script>
<template>
	<h1 class="page-header">Procedures <small>Operations Procedures</small></h1>
	<hr class="mb-4">

	<div class="row">
		<div class="col-xl-2 col-lg-2 mb-4">
			<input id="myInput" @input="searchTable()" class="form-control" type="search" placeholder="Search">
		</div>
	</div>

	<div id="myTable">
		<div class="for-loop" v-for="(procedure, index) in procedures" :key="index" :id="procedurenames[index].replace(/ /g, '')">
			<h4 class="">{{ procedurenames[index] }}</h4>

			<table class="table table-bordered mb-3 table-striped">
				<thead>
					<tr class="text-center">
						<th class="text-center" style="width: 4%">#</th>
						<th class="text-start" style="width: 48%">Step</th>
						<th class="" style="">Details</th>
						<th class="text-center" style="width: 20%;">TC/OM</th>
					</tr>
				</thead>
				<tbody class="text-body">
					<tr v-for="p in procedure" :key="p.num">
						<td class="text-center">{{ p.num }}</td>
						<td class="">{{ p.action }}</td>
						<td class="text-center">{{ p.con }}</td>
						<td class="text-center text-capitalize" v-html="p.tc"></td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>

</template>

<style>
html { scroll-padding-top: 64px; }
</style>
