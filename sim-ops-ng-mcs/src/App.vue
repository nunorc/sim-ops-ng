<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { RouterView } from 'vue-router';
import { useAppOptionStore } from '@/stores/app-option';
import { type ProgressFinisher, useProgress } from '@marcoschulte/vue3-progress';
import AppSidebar from '@/components/app/Sidebar.vue';
import AppHeader from '@/components/app/Header.vue';
import ConnectionBanner from '@/components/app/ConnectionBanner.vue';
import router from './router';
import { useSocketStore } from '@/stores/app-websockets';
import { useAuthStore } from '@/stores/app-auth';
import axios, { type AxiosError } from 'axios';
import { storeToRefs } from 'pinia';

const appOption = useAppOptionStore();
const progresses = [] as ProgressFinisher[];
const socketStore = useSocketStore();
const authStore = useAuthStore();

// Use storeToRefs to ensure reactivity
const { isAuthenticated, authMessage } = storeToRefs(authStore);

const passwordInput = ref('');
const passwordError = ref('');
const passwordLoading = ref(false);

const handlePasswordSubmit = async () => {
	if (!passwordInput.value.trim()) {
		passwordError.value = 'Password is required';
		return;
	}

	passwordLoading.value = true;
	passwordError.value = '';

	try {
		// validate the password against the API (in a header, not the query string, to keep it out of access logs)
		await axios.get(`${appOption.soAPI}/api/auth`, { headers: { 'X-User-Password': passwordInput.value } });

		// axios throws for non-2xx, so the password is valid: authenticate now, hiding the password prompt
		authStore.setPassword(passwordInput.value);
		passwordInput.value = '';
		passwordError.value = '';
	} catch (error) {
		// Handle API errors
		const { response, request } = (error ?? {}) as AxiosError;
		if (response) {
			// Server responded with error status
			if (response.status === 401 || response.status === 403) {
				passwordError.value = 'Invalid password. Please try again.';
			} else {
				passwordError.value = `Authentication failed: ${response.statusText || 'Server error'}`;
			}
		} else if (request) {
			// Request was made but no response received
			passwordError.value = 'Unable to connect to server. Please check your connection.';
		} else {
			// Something else happened
			passwordError.value = 'An error occurred during authentication.';
		}
	} finally {
		passwordLoading.value = false;
	}
};

router.beforeEach(async () => {
	progresses.push(useProgress().start());
	appOption.appSidebarMobileToggled = false;
	appOption.appSidebarToggled = false;
	document.body.scrollTop = 0;
    document.documentElement.scrollTop = 0;
})
router.afterEach(async () => {
	progresses.pop()?.finish();
})

document.body?.classList.add('app-init');

onMounted(() => {
	// Watch for authentication changes and connect socket
	if (isAuthenticated.value) {
		socketStore.connect();
	}
})

// Connect the socket when authenticated; stop it (and any pending reconnect) when not
watch(isAuthenticated, (authenticated) => {
	if (authenticated) {
		socketStore.connect();
	} else {
		socketStore.disconnect();
	}
});
</script>

<template>
	<!-- Password Prompt -->
	<div v-if="!isAuthenticated" class="password-prompt-overlay">
		<div class="password-prompt-container">
			<div class="card">
				<div class="card-header">
					<h4 class="card-title">Authentication Required</h4>
				</div>
				<div class="card-body">
					<div v-if="authMessage" class="alert alert-warning py-2 mb-3">{{ authMessage }}</div>
						<p class="mb-3">Please enter your password to access the application.</p>
					<div class="mb-3">
						<label for="password-input" class="form-label">Password</label>
						<input
							id="password-input"
							v-model="passwordInput"
							type="password"
							class="form-control"
							:class="{ 'is-invalid': passwordError }"
							placeholder="Enter password"
							@keyup.enter="handlePasswordSubmit"
							:disabled="passwordLoading"
							autofocus
						/>
						<div v-if="passwordError" class="invalid-feedback">{{ passwordError }}</div>
					</div>
					<button
						@click="handlePasswordSubmit"
						class="btn btn-theme w-100"
						:disabled="passwordLoading"
					>
						<span v-if="passwordLoading" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
						{{ passwordLoading ? 'Validating...' : 'Submit' }}
					</button>
				</div>
			</div>
		</div>
	</div>

	<!-- Main App -->
	<div v-else class="app" v-bind:class="{
		'app-sidebar-toggled': appOption.appSidebarToggled && !appOption.appSidebarCollapsed,
		'app-sidebar-collapsed': appOption.appSidebarCollapsed,
		'app-sidebar-mobile-toggled': appOption.appSidebarMobileToggled,
		'app-content-full-width': appOption.appSidebarHide,
		'app-without-sidebar': appOption.appSidebarHide,
		'app-without-header': appOption.appHeaderHide,
	}">
		<vue3-progress-bar />
		<app-header v-if="!appOption.appHeaderHide" />
		<app-sidebar v-if="!appOption.appSidebarHide" />
		<div class="app-content" v-bind:class="appOption.appContentClass">
			<connection-banner />
			<router-view></router-view>
		</div>
	</div>
</template>

<style scoped>
.password-prompt-overlay {
	position: fixed;
	top: 0;
	left: 0;
	right: 0;
	bottom: 0;
	background-color: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 9999;
}

.password-prompt-container {
	width: 100%;
	max-width: 400px;
	padding: 20px;
}

.password-prompt-container .card {
	box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}
</style>
