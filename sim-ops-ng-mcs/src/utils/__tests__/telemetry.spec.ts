import { describe, expect, it } from 'vitest'
import {
  MAX_SAMPLES,
  finitePairs,
  gsAzimuth,
  gsDistance,
  gsElevation,
  gsSnr,
  gsVelocity,
  sampleInto,
  type TelemetryState
} from '../telemetry'

const sc = (fields: Record<string, unknown> = {}): TelemetryState => ({
  ts: 1,
  aocs_rotation: [1.234, 2.345, 3.456],
  aocs_rates: [0.11, 0.22, 0.33],
  eps_battery_dod: 12.3456,
  dhs_tm_counter: 41.6,
  ttc_state_ul: 'BIT_LOCK',
  ttc_eb_no_ul: 9.87,
  ttc_ranging: 'enabled',
  ttc_coherent: 'enabled',
  ...fields
})

const gs = (fields: Record<string, unknown> = {}): TelemetryState => ({
  ts: 1,
  elevation: 20,
  azimuth: 180,
  distance: 1500,
  doppler_velocity: -3.2,
  eb_no_dl: 7.5,
  auto_range: true,
  doppler_enabled: true,
  ...fields
})

describe('ground station values', () => {
  it('only exist while the spacecraft is above the horizon', () => {
    expect(gsElevation(gs())).toBe(20)
    expect(gsAzimuth(gs())).toBe(180)
    expect(gsElevation(gs({ elevation: -1 }))).toBeNull()
    expect(gsAzimuth(gs({ elevation: 0 }))).toBeNull()
    expect(gsElevation(null)).toBeNull()
  })

  it('need ranging on both ends for the distance', () => {
    expect(gsDistance(gs(), sc())).toBe(1500)
    expect(gsDistance(gs({ auto_range: false }), sc())).toBeNull()
    expect(gsDistance(gs(), sc({ ttc_ranging: 'disabled' }))).toBeNull()
    expect(gsDistance(gs(), null)).toBeNull()
  })

  it('need doppler and a coherent transponder for the velocity', () => {
    expect(gsVelocity(gs(), sc())).toBe(-3.2)
    expect(gsVelocity(gs({ doppler_enabled: false }), sc())).toBeNull()
    expect(gsVelocity(gs(), sc({ ttc_coherent: 'disabled' }))).toBeNull()
  })

  it('treat the -128 dB floor and non-finite values as no SNR', () => {
    expect(gsSnr(gs())).toBe(7.5)
    expect(gsSnr(gs({ eb_no_dl: -128 }))).toBeNull()
    expect(gsSnr(gs({ eb_no_dl: Number.NaN }))).toBeNull()
    expect(gsSnr(gs({ eb_no_dl: '7.5' }))).toBeNull()
  })
})

describe('finitePairs', () => {
  it('keeps only finite [x, y] points', () => {
    expect(finitePairs([[1, 2], [3, Number.NaN], [4], 'x', [5, 6]])).toEqual([[1, 2], [5, 6]])
    expect(finitePairs(undefined)).toEqual([])
  })
})

describe('sampleInto', () => {
  it('samples each spacecraft series, rounded to its digits', () => {
    const history = new Map<string, number[]>()
    sampleInto(history, 'sc', sc(), null)

    expect(history.get('aocs_rot_x')).toEqual([1.2])
    expect(history.get('aocs_rate_z')).toEqual([0.3])
    expect(history.get('eps_battery_dod')).toEqual([12.35])
    expect(history.get('dhs_tm_counter')).toEqual([42])
    expect(history.get('ttc_eb_no_ul')).toEqual([9.9])
    // ground station series only sample ground station states
    expect(history.has('gs_elevation')).toBe(false)
  })

  it('parses numeric strings and skips missing or malformed values', () => {
    const history = new Map<string, number[]>()
    sampleInto(history, 'sc', sc({ eps_battery_dod: '50.5', aocs_rotation: [1, 2], ttc_state_ul: 'NO_RF' }), null)

    expect(history.get('eps_battery_dod')).toEqual([50.5])
    // a short vector, and the uplink SNR without an uplink
    expect(history.has('aocs_rot_x')).toBe(false)
    expect(history.has('ttc_eb_no_ul')).toBe(false)
  })

  it('clears a ground station series when its value goes away', () => {
    const history = new Map<string, number[]>()
    sampleInto(history, 'gs', gs(), sc())
    sampleInto(history, 'gs', gs({ elevation: 25 }), sc())
    expect(history.get('gs_elevation')).toEqual([20, 25])
    expect(history.get('gs_distance')).toEqual([1500, 1500])

    // below the horizon: elevation-derived series restart rather than bridge the gap
    sampleInto(history, 'gs', gs({ elevation: -5 }), sc())
    expect(history.get('gs_elevation')).toEqual([])
    expect(history.get('gs_azimuth')).toEqual([])
  })

  it('uses the last spacecraft state for ground station samplers', () => {
    const history = new Map<string, number[]>()
    sampleInto(history, 'gs', gs(), sc({ ttc_ranging: 'disabled' }))
    expect(history.has('gs_distance')).toBe(false)
  })

  it(`keeps at most ${MAX_SAMPLES} samples per series`, () => {
    const history = new Map<string, number[]>()
    for (let i = 0; i < MAX_SAMPLES + 10; i++) sampleInto(history, 'sc', sc({ eps_battery_dod: i }), null)

    const buf = history.get('eps_battery_dod')!
    expect(buf).toHaveLength(MAX_SAMPLES)
    expect(buf[0]).toBe(10)
    expect(buf[buf.length - 1]).toBe(MAX_SAMPLES + 9)
  })
})
