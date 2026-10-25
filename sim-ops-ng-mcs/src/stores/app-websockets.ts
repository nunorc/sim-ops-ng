import { defineStore } from 'pinia'
import { ref, shallowRef, computed } from 'vue'
import axios, { type AxiosError } from 'axios'
import { useAuthStore, wsAuthProtocols } from './app-auth'
import { useAppOptionStore } from './app-option'
import { sampleInto, type SeriesKey, type TelemetryState } from '@/utils/telemetry'
import type { GroundStationState, SpacecraftState } from '@/types/state'

// Reconnect backoff after a drop or a failed attempt
export const RECONNECT_MIN_MS = 1000
const RECONNECT_MAX_MS = 15000

// 'connecting': first attempt; 'reconnecting': waiting to retry after a drop or a failed attempt
type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'reconnecting'

// A TC waiting in the shared stack, and one already executed (newest first)
export interface TcStackEntry {
  command: string
  system?: string
  control?: string
  value?: unknown
}

export interface TcHistoryEntry {
  command: string
  status: string | null
  ts: string
}

// A state message pushed by the API (only the fields that changed may be present)
interface StateMessage {
  ts?: number
  spacecraft?: SpacecraftState | null
  ground_station?: GroundStationState | null
  tc_stack?: TcStackEntry[]
  tc_history?: TcHistoryEntry[]
  data_proxy?: string
  sle_connected?: boolean
}

export const useSocketStore = defineStore('socket', () => {
  const _wsUrl = import.meta.env.VITE_WS_URL
  const WS_URL = _wsUrl || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/ws`
  const authStore = useAuthStore()
  const appOption = useAppOptionStore()

  // shallow: the socket is compared by identity, which a reactive proxy would break
  const socket = shallowRef<WebSocket | null>(null)
  const status = ref<ConnectionStatus>('disconnected')
  // set while reconnecting when the server could not be reached at all (vs. a dropped socket)
  const unreachable = ref(false)
  // delay of the retry currently scheduled, for display
  const retryDelayMs = ref(0)
  // shallow: replaced wholesale on every message, never mutated in place
  const sc_state = shallowRef<SpacecraftState | null>(null)
  const gs_state = shallowRef<GroundStationState | null>(null)
  const tc_stack = shallowRef<TcStackEntry[]>([])
  const tc_history = shallowRef<TcHistoryEntry[]>([])
  const sim_ts = ref<number | null>(null)
  const data_proxy = ref<string>('SLE')
  const sle_connected = ref<boolean>(true)

  const connected = computed(() => status.value === 'connected')
  // simulated time of the last spacecraft state received
  const sc_ts = computed<number | null>(() => sc_state.value?.ts ?? null)

  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectDelayMs = RECONNECT_MIN_MS

  function clearReconnect() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  function scheduleReconnect() {
    clearReconnect()
    status.value = 'reconnecting'
    retryDelayMs.value = reconnectDelayMs
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, reconnectDelayMs)
    reconnectDelayMs = Math.min(reconnectDelayMs * 2, RECONNECT_MAX_MS)
  }

  // closing before opening means a bad password or a down server (both code 1006): ask the HTTP API which
  async function passwordRejected(): Promise<boolean> {
    try {
      await axios.get(`${appOption.soAPI}/api/auth`, authStore.authConfig())
      unreachable.value = false
      return false
    } catch (error) {
      const code = (error as AxiosError | undefined)?.response?.status
      unreachable.value = code === undefined || code >= 500
      return code === 401 || code === 403
    }
  }

  // sparkline history, sampled on every message; not reactive, views watch historyVersion instead
  const history = new Map<string, number[]>()
  const historyVersion = shallowRef(0)
  // last spacecraft state received, for ground station samplers (survives SLE drop-outs)
  let lastSc: TelemetryState | null = null

  function series(key: SeriesKey): number[] {
    return history.get(key)?.slice() ?? []
  }

  // fields received while the tab is hidden, applied in one go when it's visible again
  let pending: Record<string, unknown> | null = null

  // ts of the last state sampled per source, so an unchanged re-sent state doesn't add duplicate samples
  const lastSampledTs: Record<'sc' | 'gs', number | undefined> = { sc: undefined, gs: undefined }

  function isNewSample(source: 'sc' | 'gs', state: TelemetryState): boolean {
    if (state.ts !== undefined && state.ts === lastSampledTs[source]) return false
    lastSampledTs[source] = state.ts
    return true
  }

  function sample(data: StateMessage) {
    if (data.spacecraft) {
      lastSc = data.spacecraft
      if (isNewSample('sc', data.spacecraft)) sampleInto(history, 'sc', data.spacecraft, lastSc)
    }
    if (data.ground_station && isNewSample('gs', data.ground_station)) {
      sampleInto(history, 'gs', data.ground_station, lastSc)
    }
  }

  function publish(data: StateMessage) {
    if (data.ts !== undefined) sim_ts.value = data.ts
    if (data.spacecraft) sc_state.value = data.spacecraft
    if (data.ground_station) gs_state.value = data.ground_station
    if (data.tc_stack !== undefined) tc_stack.value = data.tc_stack
    if (data.tc_history !== undefined) tc_history.value = data.tc_history
    if (data.data_proxy) data_proxy.value = data.data_proxy
    if (data.sle_connected !== undefined) sle_connected.value = data.sle_connected
    historyVersion.value++
  }

  function applyMessage(data: StateMessage) {
    sample(data)
    if (document.hidden) {
      // keep the latest value of each field (a null spacecraft keeps the last one, as publish does)
      pending ??= {}
      for (const [k, v] of Object.entries(data)) {
        if (v !== undefined && v !== null) pending[k] = v
      }
      return
    }
    publish(data)
  }

  function flushPending() {
    if (document.hidden || !pending) return
    const data = pending
    pending = null
    publish(data as StateMessage)
  }

  document.addEventListener('visibilitychange', flushPending)

  function connect() {
    if (socket.value) return
    if (!authStore.isAuthenticated || !authStore.password) {
      console.warn('Cannot connect: user not authenticated')
      return
    }
    clearReconnect()
    if (status.value !== 'reconnecting') status.value = 'connecting'

    // whether this socket ever opened: closing before opening means a rejected password
    let opened = false
    const ws = new WebSocket(WS_URL, wsAuthProtocols(authStore.password))
    socket.value = ws

    ws.onopen = () => {
      opened = true
      status.value = 'connected'
      unreachable.value = false
      reconnectDelayMs = RECONNECT_MIN_MS
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        applyMessage(JSON.parse(event.data))
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err)
      }
    }

    ws.onclose = async (event: CloseEvent) => {
      if (socket.value === ws) socket.value = null
      if (!authStore.isAuthenticated) {
        status.value = 'disconnected'
        return
      }
      // 1008 (policy violation) after opening is the runtime password-change force-disconnect
      if (event.code === 1008 || (!opened && await passwordRejected())) {
        status.value = 'disconnected'
        authStore.expireSession('Your session is no longer valid. Please sign in again.')
        return
      }
      // a drop, or the server is not reachable (yet): keep the session and retry
      scheduleReconnect()
    }

    ws.onerror = (err: Event) => {
      console.error('WebSocket error', err)
    }
  }

  function disconnect() {
    clearReconnect()
    const ws = socket.value
    socket.value = null
    status.value = 'disconnected'
    ws?.close()
  }

  function send(payload: unknown) {
    if (socket.value?.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify(payload))
    }
  }

  return {
    status,
    connected,
    unreachable,
    retryDelayMs,
    sc_ts,
    sc_state,
    gs_state,
    historyVersion,
    series,
    tc_stack,
    tc_history,
    sim_ts,
    data_proxy,
    sle_connected,
    connect,
    disconnect,
    send
  }
})
