import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from 'axios'
import { useSocketStore, RECONNECT_MIN_MS } from '../app-websockets'
import { useAuthStore } from '../app-auth'
import { MAX_SAMPLES } from '@/utils/telemetry'

vi.mock('axios')

class FakeWebSocket {
  static OPEN = 1
  static instances: FakeWebSocket[] = []
  readyState = 0
  sent: string[] = []
  onopen: (() => void) | null = null
  onmessage: ((ev: { data: string }) => void) | null = null
  onclose: ((ev: { code: number }) => void | Promise<void>) | null = null
  onerror: ((ev: Event) => void) | null = null

  constructor(public url: string, public protocols: string[]) {
    FakeWebSocket.instances.push(this)
  }
  open() {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.()
  }
  message(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }
  async serverClose(code = 1006) {
    this.readyState = 3
    await this.onclose?.({ code })
  }
  send(data: string) {
    this.sent.push(data)
  }
  close() {
    this.readyState = 3
  }
}

const latest = () => FakeWebSocket.instances[FakeWebSocket.instances.length - 1]!

function signedIn() {
  const auth = useAuthStore()
  auth.setPassword('user-pw')
  return auth
}

describe('socket store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    vi.useFakeTimers()
    vi.mocked(axios.get).mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('reconnects after a drop, keeping the session', async () => {
    const auth = signedIn()
    const store = useSocketStore()
    store.connect()
    latest().open()
    expect(store.status).toBe('connected')

    await latest().serverClose(1006)
    expect(store.status).toBe('reconnecting')
    expect(auth.isAuthenticated).toBe(true)
    expect(axios.get).not.toHaveBeenCalled()

    vi.advanceTimersByTime(RECONNECT_MIN_MS)
    expect(FakeWebSocket.instances).toHaveLength(2)
    latest().open()
    expect(store.status).toBe('connected')
  })

  it('backs off between failed attempts', async () => {
    signedIn()
    vi.mocked(axios.get).mockRejectedValue(new Error('Network Error'))
    const store = useSocketStore()
    store.connect()

    await latest().serverClose()
    expect(store.retryDelayMs).toBe(RECONNECT_MIN_MS)
    vi.advanceTimersByTime(RECONNECT_MIN_MS)
    await latest().serverClose()
    expect(store.retryDelayMs).toBe(2 * RECONNECT_MIN_MS)
  })

  it('reports an unreachable server instead of expiring the session', async () => {
    const auth = signedIn()
    vi.mocked(axios.get).mockRejectedValue(new Error('Network Error'))
    const store = useSocketStore()
    store.connect()

    await latest().serverClose(1006)
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.authMessage).toBeNull()
    expect(store.status).toBe('reconnecting')
    expect(store.unreachable).toBe(true)
  })

  it('expires the session when the password is rejected', async () => {
    const auth = signedIn()
    vi.mocked(axios.get).mockRejectedValue({ response: { status: 401 } })
    const store = useSocketStore()
    store.connect()

    await latest().serverClose(1006)
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.authMessage).toMatch(/no longer valid/)
    expect(store.status).toBe('disconnected')
    vi.advanceTimersByTime(60_000)
    expect(FakeWebSocket.instances).toHaveLength(1)
  })

  it('expires the session on a password-change disconnect', async () => {
    const auth = signedIn()
    const store = useSocketStore()
    store.connect()
    latest().open()

    await latest().serverClose(1008)
    expect(auth.isAuthenticated).toBe(false)
    expect(store.status).toBe('disconnected')
  })

  it('stops reconnecting on disconnect', async () => {
    signedIn()
    const store = useSocketStore()
    store.connect()
    latest().open()
    await latest().serverClose(1006)

    store.disconnect()
    vi.advanceTimersByTime(60_000)
    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(store.status).toBe('disconnected')
  })

  it('keeps the last spacecraft state without SLE frame lock', () => {
    signedIn()
    const store = useSocketStore()
    store.connect()
    latest().open()

    latest().message({ ts: 10, spacecraft: { ts: 10 }, sle_connected: true, data_proxy: 'SLE' })
    expect(store.sc_ts).toBe(10)

    latest().message({ ts: 20, spacecraft: null, sle_connected: false, data_proxy: 'SLE' })
    expect(store.sc_ts).toBe(10) // last values kept
    expect(store.sim_ts).toBe(20)

    latest().message({ ts: 30, spacecraft: { ts: 30 }, sle_connected: true, data_proxy: 'EGSE' })
    expect(store.sc_ts).toBe(30)
  })

  describe('telemetry history', () => {
    function setHidden(hidden: boolean) {
      vi.spyOn(document, 'hidden', 'get').mockReturnValue(hidden)
      document.dispatchEvent(new Event('visibilitychange'))
    }

    afterEach(() => {
      vi.restoreAllMocks()
    })

    function connected() {
      signedIn()
      const store = useSocketStore()
      store.connect()
      latest().open()
      return store
    }

    it('keeps at most MAX_SAMPLES samples per series', () => {
      const store = connected()
      for (let i = 0; i < MAX_SAMPLES + 20; i++) {
        latest().message({ ts: i, spacecraft: { ts: i, eps_temperature: i } })
      }
      const series = store.series('eps_temperature')
      expect(series).toHaveLength(MAX_SAMPLES)
      expect(series[series.length - 1]).toBe(MAX_SAMPLES + 19)
    })

    it('samples while hidden and publishes the latest state when visible again', () => {
      const store = connected()
      latest().message({ ts: 1, spacecraft: { ts: 1, eps_temperature: 1 } })
      const version = store.historyVersion

      setHidden(true)
      latest().message({ ts: 2, spacecraft: { ts: 2, eps_temperature: 2 }, sle_connected: true })
      latest().message({ ts: 3, spacecraft: null, sle_connected: false })
      expect(store.sc_ts).toBe(1)
      expect(store.sim_ts).toBe(1)
      expect(store.historyVersion).toBe(version)
      expect(store.series('eps_temperature')).toEqual([1, 2])

      setHidden(false)
      expect(store.sc_ts).toBe(2) // a null spacecraft keeps the last one
      expect(store.sim_ts).toBe(3)
      expect(store.sle_connected).toBe(false)
      expect(store.historyVersion).toBe(version + 1)
    })

    it('samples a state re-sent unchanged only once', () => {
      const store = connected()
      // a paused sim keeps broadcasting the same tick
      for (let i = 0; i < 5; i++) {
        latest().message({ ts: 7, spacecraft: { ts: 7, eps_temperature: 30 }, ground_station: { ts: 7, elevation: 10 } })
      }
      latest().message({ ts: 8, spacecraft: { ts: 8, eps_temperature: 31 }, ground_station: { ts: 8, elevation: 11 } })
      expect(store.series('eps_temperature')).toEqual([30, 31])
      expect(store.series('gs_elevation')).toEqual([10, 11])
    })

    it('clears a ground station series when its value is unavailable', () => {
      const store = connected()
      latest().message({ ground_station: { elevation: 10 } })
      latest().message({ ground_station: { elevation: 12 } })
      expect(store.series('gs_elevation')).toEqual([10, 12])

      latest().message({ ground_station: { elevation: -5 } })
      expect(store.series('gs_elevation')).toEqual([])
    })
  })
})
