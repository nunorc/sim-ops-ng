<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { MenuItem } from '@/stores/app-sidebar-menu';

defineProps<{
  menu: MenuItem;
}>();
</script>
<template>
	<router-link v-bind:to="menu.url ?? ''" custom v-slot="{ navigate, href, isActive }">
		<div class="menu-item" v-bind:class="{ 'active': isActive }">
			<a v-bind:href="href" @click="navigate" class="menu-link">
				<span class="menu-icon" v-if="menu.icon">
					<i v-bind:class="menu.icon"></i>
				</span>
				<span class="menu-text">{{ menu.text }}</span>
			</a>
		</div>
	</router-link>
</template>
