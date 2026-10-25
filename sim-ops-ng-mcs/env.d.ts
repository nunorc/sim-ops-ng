/// <reference types="vite/client" />

declare const __APP_VERSION__: string

// apexcharts' global chart defaults (set in components/plugins/Apexcharts.vue)
interface Window {
  Apex: object
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
