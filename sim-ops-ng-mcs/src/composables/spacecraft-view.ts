import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useSocketStore } from '@/stores/app-websockets'
import { createViewCache } from '@/utils/view-cache'
import { sparklineOptions } from '@/utils/chart'
import type { SeriesKey } from '@/utils/telemetry'
import type { SpacecraftState } from '@/types/state'

/** A subsystem view's spacecraft state: the live one, or the cached last one until the first arrives. */
export function useSpacecraftView(cacheKey: string) {
  const socketStore = useSocketStore()
  const cache = createViewCache(cacheKey)

  const loading = ref(true)
  // shallow: replaced wholesale on every message, never mutated in place
  const state = shallowRef<SpacecraftState | null>(null)
  const compact = ref(false)

  function updateData(data: SpacecraftState) {
    loading.value = false
    state.value = data
    cache.save(data)
  }

  onMounted(() => {
    compact.value = JSON.parse(sessionStorage.getItem('compact') ?? 'false') || false

    // restore the last state from the cache, if any
    const cached = cache.load() as SpacecraftState | null
    if (cached) {
      state.value = cached
      loading.value = false
    }

    watch(
      () => socketStore.sc_state,
      (sc_data) => {
        if (sc_data) updateData(sc_data)
      },
      { immediate: true }
    )
  })

  onBeforeUnmount(() => cache.flush())

  return { loading, state, compact }
}

/** A sparkline chart's props for one series sampled by the socket store; historyVersion makes it reactive. */
export function useSparkline(name: string, key: SeriesKey) {
  const socketStore = useSocketStore()
  return computed(() => {
    void socketStore.historyVersion
    return { height: 30, options: sparklineOptions(), series: [{ name, data: socketStore.series(key) }] }
  })
}
