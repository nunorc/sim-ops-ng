// Sparkline history: which telemetry values the socket store samples on every state message, and how.

// Samples kept per series; older ones are dropped
export const MAX_SAMPLES = 180

// A spacecraft or ground station state: a flat record of telemetry fields (see so/data_model.py)
export interface TelemetryState {
  ts?: number
  [field: string]: unknown
}

type State = TelemetryState | null

export function toFinite(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function finitePairs(points: unknown): [number, number][] {
  if (!Array.isArray(points)) return []

  return points.filter(
    (p): p is [number, number] => Array.isArray(p) && toFinite(p[0]) !== null && toFinite(p[1]) !== null
  )
}

// Ranging data needs ranging enabled on both the ground station and the spacecraft transponder.
export function rangingActive(gs: State, sc: State): boolean {
  return !!(gs && gs.auto_range && sc && sc.ttc_ranging === 'enabled')
}

// Doppler data needs doppler enabled on the ground station and a coherent spacecraft transponder.
export function dopplerActive(gs: State, sc: State): boolean {
  return !!(gs && gs.doppler_enabled && sc && sc.ttc_coherent === 'enabled')
}

export function gsElevation(gs: State): number | null {
  const v = toFinite(gs && gs.elevation)
  return v !== null && v > 0 ? v : null
}

// azimuth is only meaningful while the spacecraft is above the horizon
export function gsAzimuth(gs: State): number | null {
  return gsElevation(gs) !== null ? toFinite(gs && gs.azimuth) : null
}

export function gsDistance(gs: State, sc: State): number | null {
  if (!rangingActive(gs, sc)) return null

  const v = toFinite(gs && gs.distance)
  return v !== null && v > 0 ? v : null
}

export function gsVelocity(gs: State, sc: State): number | null {
  return dopplerActive(gs, sc) ? toFinite(gs && gs.doppler_velocity) : null
}

export function gsSnr(gs: State): number | null {
  const v = toFinite(gs && gs.eb_no_dl)
  return v !== null && v > -128 ? v : null
}

interface Sampler {
  // 'sc': sampled when a spacecraft state arrives; 'gs': when a ground station state arrives
  source: 'sc' | 'gs'
  // gs samplers get the last known spacecraft state, which survives SLE drop-outs
  get: (state: TelemetryState, sc: State) => unknown
  digits?: number
  // clear the series when the value is unavailable (otherwise the sample is just skipped)
  clearOnNull?: boolean
}

const sc = (field: string, digits?: number): Sampler => ({ source: 'sc', get: (s) => s[field], digits })
const scIndex = (field: string, i: number, digits?: number): Sampler => ({
  source: 'sc',
  get: (s) => {
    const v = s[field]
    return Array.isArray(v) && v.length >= 3 ? v[i] : null
  },
  digits
})
const gs = (get: (gs: State, sc: State) => number | null, digits?: number): Sampler => ({
  source: 'gs',
  get,
  digits,
  clearOnNull: true
})

export const SAMPLERS: Record<string, Sampler> = {
  aocs_rot_x: scIndex('aocs_rotation', 0, 1),
  aocs_rot_y: scIndex('aocs_rotation', 1, 1),
  aocs_rot_z: scIndex('aocs_rotation', 2, 1),
  aocs_rate_x: scIndex('aocs_rates', 0, 1),
  aocs_rate_y: scIndex('aocs_rates', 1, 1),
  aocs_rate_z: scIndex('aocs_rates', 2, 1),
  aocs_sun_angle: sc('aocs_sun_angle', 1),
  aocs_nadir_angle: sc('aocs_nadir_angle', 1),
  eps_battery_dod: sc('eps_battery_dod'),
  eps_net_power: sc('eps_net_power'),
  eps_temperature: sc('eps_temperature'),
  dhs_memory: sc('dhs_memory', 3),
  dhs_tm_counter: sc('dhs_tm_counter', 0),
  dhs_tc_counter: sc('dhs_tc_counter', 0),
  ttc_eb_no_ul: { source: 'sc', get: (s) => (s.ttc_state_ul !== 'NO_RF' ? s.ttc_eb_no_ul : null), digits: 1 },
  gs_elevation: gs(gsElevation),
  gs_azimuth: gs(gsAzimuth),
  gs_distance: gs(gsDistance, 0),
  gs_velocity: gs(gsVelocity),
  gs_snr: gs(gsSnr)
}

export type SeriesKey = keyof typeof SAMPLERS

// Append one sample per sampler of `source` to its bounded buffer in `history`
export function sampleInto(history: Map<string, number[]>, source: 'sc' | 'gs', state: TelemetryState, lastSc: State): void {
  for (const key in SAMPLERS) {
    const sampler = SAMPLERS[key]!
    if (sampler.source !== source) continue

    const raw = sampler.get(state, lastSc)
    const n = typeof raw === 'string' ? parseFloat(raw) : raw
    let buf = history.get(key)
    if (typeof n !== 'number' || !Number.isFinite(n)) {
      if (sampler.clearOnNull && buf) buf.length = 0
      continue
    }
    if (!buf) history.set(key, (buf = []))
    buf.push(Number(n.toFixed(sampler.digits ?? 2)))
    if (buf.length > MAX_SAMPLES) buf.splice(0, buf.length - MAX_SAMPLES)
  }
}
