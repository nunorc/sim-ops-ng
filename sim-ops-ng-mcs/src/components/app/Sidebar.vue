<script setup lang="ts">
import { useAppSidebarMenuStore } from '@/stores/app-sidebar-menu';
import { useAppOptionStore } from '@/stores/app-option';
import SidebarNav from '@/components/app/SidebarNav.vue';

const appSidebarMenu = useAppSidebarMenuStore();
const appOption = useAppOptionStore();
const compact = getCompact();

function appSidebarMobileToggled() {
	appOption.appSidebarMobileToggled = !appOption.appSidebarMobileToggled;
}

function getCompact() {
	let compact = false;

	const value = sessionStorage.getItem('compact');
	if (value !== null) {
		compact = JSON.parse(value);
	}

	return compact;
}

function toggleCompact() {
	const compact = getCompact();

	sessionStorage.setItem('compact', JSON.stringify(!compact));
	window.location.reload();
}

</script>
<template>
	<div id="sidebar" class="app-sidebar">
		<perfect-scrollbar class="app-sidebar-content">
			<div class="menu">
				<template v-for="menu in appSidebarMenu" :key="menu.text">
					<div class="menu-header" v-if="menu.is_header">{{ menu.text }}</div>
					<sidebar-nav v-else v-bind:menu="menu"></sidebar-nav>
				</template>

				<div class="menu-header">Options</div>
				<div class="menu-divider"></div>
				<div class="form-check form-switch mb-5 d-flex" style="margin-left: 20px;">
					<input @click="toggleCompact" class="form-check-input" type="checkbox" role="switch" id="flexSwitchCheckDefault" :checked="compact" style="cursor: pointer;">
					<label class="form-check-label ps-2 menu-link" for="flexSwitchCheckDefault" style="color: #ffffff80; cursor: pointer;"> Compact Mode</label>
				</div>

			</div>
		</perfect-scrollbar>
	</div>
	<button class="app-sidebar-mobile-backdrop" v-on:click="appSidebarMobileToggled"></button>
</template>