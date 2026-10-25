import { markRaw } from 'vue'
import { useAppVariableStore } from '@/stores/app-variable'

let sparkline: object | null = null

/** Shared sparkline options: one object, since the chart wrapper watches `options` by reference only. */
export function sparklineOptions(): object {
  if (!sparkline) {
    const appVariable = useAppVariableStore()
    sparkline = markRaw({
      chart: { type: 'line', sparkline: { enabled: true } },
      colors: [appVariable.color.theme],
      stroke: { curve: 'straight', width: 2 },
      tooltip: { enabled: false }
    })
  }
  return sparkline
}
