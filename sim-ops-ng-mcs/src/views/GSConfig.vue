<script lang="ts">
import { filterTableRows } from '@/utils/table-filter';

export default {
	components: {

	},
	data() {
		return {
			procedures: [
				{ 'desc': 'Enable U/L Carrier', 'res': 'Ground Station > U/L Carrier' },
				{ 'desc': 'Disable U/L Carrier', 'res': 'Ground Station > U/L Carrier' },
				{ 'desc': 'Enable Program Track', 'res': 'Ground Station > Program Track' },
				{ 'desc': 'Disable Program Track', 'res': 'Ground Station > Program Track' },
				{ 'desc': 'Enable Ranging', 'res': 'Ground Station > Ranging' },
				{ 'desc': 'Disable Ranging', 'res': 'Ground Station > Ranging' },
				{ 'desc': 'Enable Doppler', 'res': 'Ground Station > Doppler' },
				{ 'desc': 'Disable Doppler', 'res': 'Ground Station > Doppler' },
				{ 'desc': 'Sweep', 'res': 'Ground Station > Sweep Done' },
				{ 'desc': 'Enable Fr. Checks', 'res': 'Ground Station > Frame Checks' },
				{ 'desc': 'Disable Fr. Checks', 'res': 'Ground Station > Frame Checks' },
				{ 'desc': 'Set U/L Power level: 30, 40, 50', 'res': 'Ground Station > U/L Power' },
				{ 'desc': 'Set configuration mode: S/X, Sup/Res/Sub, LBR/HBR', 'res': 'Ground Station > mode' },
			]
		}
	},
	methods: {
		searchTable() {
			filterTableRows('myInput', 'myTable');
		}
	},
	mounted() {
		//this.updateProcedures();
	}
}
</script>
<template>
	<h1 class="page-header">Ground Station <small>Actions & Configuration Modes</small></h1>
	<hr class="mb-4">

	<h4 class="pt-3">Actions</h4>
	<div>
		<table id="myTable" class="table table-bordered mb-3 table-striped">
			<thead>
				<tr class="text-center">
					<th class="">Action</th>
					<th class="text-center">Monitor</th>
				</tr>
			</thead>
			<tbody class="text-body">
				<tr v-for="p in procedures" :key="p.desc">
					<td class="">{{ p.desc }}</td>
					<td class="text-center text-capitalize">{{ p.res }}</td>
				</tr>
			</tbody>
		</table>
	</div>

	<h4 class="pt-3">Configuration Modes</h4>
	<div>
		<table id="myTable" class="table table-bordered mb-3 table-striped">
			<thead>
				<tr class="text-center">
					<th class="">Mode</th>
					<th class="text-center">Description</th>
				</tr>
			</thead>
			<tbody class="text-body">
				<tr><td>S_Sup_LBR</td><td>S band, suppressed carrier, low bitrate</td></tr>
				<tr><td>S_Sup_HBR</td><td>S band, suppressed carrier, high bitrate</td></tr>
				<tr><td>X_Sup_LBR</td><td>X band, suppressed carrier, low bitrate</td></tr>
				<tr><td>X_Sup_HBR</td><td>X band, suppressed carrier, high bitrate</td></tr>
				<tr><td>S_Res_LBR</td><td>S band, residual carrier, low bitrate</td></tr>
				<tr><td>X_Res_LBR</td><td>S band, residual carrier, low bitrate</td></tr>
				<tr><td>S_Sub_LBR</td><td>S band, subcarrier carrier, low bitrate</td></tr>
				<tr><td>X_Sub_LBR</td><td>S band, subcarrier carrier, low bitrate</td></tr>
			</tbody>
		</table>
	</div>

</template>
