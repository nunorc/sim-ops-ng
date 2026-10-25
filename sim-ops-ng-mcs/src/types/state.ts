// Generated from sim-ops-ng-lib/so/data_model.py by sim-ops-ng-lib/bin/gen-ts-types.py: do not edit.
// The spacecraft and ground station state, as broadcast to the MCS.

export type AOCSTarget = 'SUN' | 'TARGET' | 'NADIR' | 'RATEDAMPING' | 'MONITORING'
export type Quality = 'good' | 'bad' | 'unknown'
export type Status = 'enabled' | 'disabled' | 'unknown' | 'nominal' | 'safe' | 'on' | 'off' | 'not_valid' | 'valid' | 'error' | 'control_err' | 'power_positive' | 'power_negative' | 'power_critical' | 'sun' | 'no_sun'
export type TTCAntenna = 'LGA_RHC' | 'LGA_LHC' | 'MGA' | 'HGA'
export type TTCModes = 'S_Sup_LBR' | 'S_Sup_HBR' | 'X_Sup_LBR' | 'X_Sup_HBR' | 'S_Res_LBR' | 'X_Res_LBR' | 'S_Sub_LBR' | 'X_Sub_LBR'
export type TTCState = 'NO_RF' | 'RF_DETECTED' | 'PLL_LOCK' | 'PSK_LOCK' | 'BIT_LOCK' | 'FRAME_LOCK'

export type SpacecraftState = {
  ts: number
  aocs_chain: string
  aocs_mode: AOCSTarget
  aocs_valid: Status
  aocs_prev_mode: AOCSTarget
  aocs_rotation: number[]
  aocs_rates: number[]
  aocs_sun_angle: number
  aocs_nadir_angle: number
  aocs_damp: number
  aocs_position: number[]
  ttc_chain: string
  ttc_mcu: Status
  ttc_mode: TTCModes
  ttc_s_antenna: TTCAntenna
  ttc_x_antenna: TTCAntenna
  ttc_state_ul: TTCState
  ttc_coherent: Status
  ttc_s_tx_status: Status
  ttc_s_rx_status: Status
  ttc_x_tx_status: Status
  ttc_x_rx_status: Status
  ttc_ping_ack: number
  ttc_ranging: Status
  ttc_c_no_ul: number
  ttc_eb_no_ul: number
  ttc_link_margin_ul: number
  ttc_ber_ul: number
  ttc_fer_ul: number
  ttc_doppler_shift_ul: number
  ttc_freq_rx_mhz: number
  ttc_freq_tx_mhz: number
  eps_chain: string
  eps_net_power: number
  eps_sol_array: Status[]
  eps_battery_dod: number
  eps_temperature: number
  eps_acu: Status
  eps_pdu: Status
  eps_power_status: Status
  eps_power_source: string
  dhs_chain: string
  dhs_obsw_mode: Status
  dhs_mem_dump_enabled: boolean
  dhs_memory: number
  dhs_tm_counter: number
  dhs_tc_counter: number
  dhs_tm_window: string[]
  dhs_tc_history: string[]
  dhs_uploaded: string[]
  pl_gnss_status: Status
  pl_gnss_pos: number[]
  pl_camera_status: Status
  pl_camera_config: string
  pl_sdr_status: Status
  pl_sdr_config: string
  ov_no_tm: boolean
  frame_quality: Quality
  frame_checks: Status
  is_sunlit: boolean | null
}

export type GroundStationState = {
  ts: number
  carrier_ul: Status
  spectrum_ul: [number, number][]
  spectrum_dl: [number, number][]
  frame_quality: Quality
  frame_checks: Status
  status_dl: TTCState
  status_dl_transitions: Record<string, unknown>
  c_no_dl: number
  eb_no_dl: number
  link_margin_dl: number
  ber_dl: number
  fer_dl: number
  doppler_shift_dl: number
  freq_ul_mhz: number
  freq_dl_mhz: number
  dl_modulation: string
  dl_coding: string
  elevation: number | null
  azimuth: number | null
  distance: number | null
  auto_track: boolean
  program_track: boolean
  doppler_enabled: boolean
  doppler_velocity: number | null
  sweep_done: boolean
  mode: TTCModes
  band_ul: string
  power_ul: number
  antenna_diameter_m: number
  position: number[]
  ov_no_tm: boolean
  ov_no_tc: boolean
  auto_range: boolean
  ul_state: TTCState
  ul_link_margin: number
  modes: string[]
  next_pass_start: number | null
  next_pass_end: number | null
  next_5_start: number | null
  next_5_end: number | null
  sweep_count: number
  name: string
  latitude: number
  longitude: number
  altitude: number
}
