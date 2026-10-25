<script setup lang="ts">
import { computed } from 'vue';
import { useAppOptionStore } from '@/stores/app-option';
import { useSocketStore } from '@/stores/app-websockets';
import { RouterLink } from 'vue-router';

const appOption = useAppOptionStore();
const socketStore = useSocketStore();
const appVersion = __APP_VERSION__;

const scTimestamp = computed(() => {
	const ts = socketStore.sim_ts;
	if (!ts) return '--';
	return new Date(ts * 1000).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
});
function toggleAppSidebarCollapsed() {
	if (!appOption.appSidebarHide) {
		if (appOption.appSidebarCollapsed) {
			appOption.appSidebarToggled = !appOption.appSidebarToggled;
		} else if (appOption.appSidebarToggled) {
			appOption.appSidebarToggled = !appOption.appSidebarToggled;
		}
		appOption.appSidebarCollapsed = !appOption.appSidebarCollapsed;
	}
}
function toggleAppSidebarMobileToggled() {
	appOption.appSidebarMobileToggled = !appOption.appSidebarMobileToggled;
}

</script>
<template>
	<div id="header" class="app-header">
		<div class="desktop-toggler">
			<button type="button" class="menu-toggler" v-on:click="toggleAppSidebarCollapsed">
				<span class="bar"></span>
				<span class="bar"></span>
				<span class="bar"></span>
			</button>
		</div>

		<div class="mobile-toggler">
			<button type="button" class="menu-toggler" v-on:click="toggleAppSidebarMobileToggled">
				<span class="bar"></span>
				<span class="bar"></span>
				<span class="bar"></span>
			</button>
		</div>

		<div class="brand">
			<RouterLink to="/" class="brand-logo">
				<span class="brand-text">MCS</span>
				<small class="ms-2 text-body-secondary fw-normal">v{{ appVersion }}</small>
			</RouterLink>
		</div>

		<div class="menu">
			<span class="badge rounded-0 ms-1">TM/TC</span>
			<span class="badge rounded-0 text-uppercase bg-light text-dark font-monospace">{{ socketStore.data_proxy }}</span>
			<span class="badge rounded-0 ms-1">TS</span>
			<span class="badge rounded-0 text-uppercase bg-light text-dark font-monospace" style="margin-right: 2rem;">{{ scTimestamp }}</span>
		</div>

	</div>
</template>
