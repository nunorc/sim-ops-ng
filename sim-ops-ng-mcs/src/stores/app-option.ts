import { defineStore } from "pinia";
import getEnv from '@/utils/env';

export const useAppOptionStore = defineStore("appOption", () => {
	return {
		appHeaderHide: false,
		appSidebarToggled: true,
		appSidebarCollapsed: false,
		appSidebarMobileToggled: false,
		appSidebarHide: false,
		appContentClass: '',
		soAPI: getEnv('SO_API', ''),		// empty = same origin (nginx); override with VITE_SO_API for local dev
	}
});
