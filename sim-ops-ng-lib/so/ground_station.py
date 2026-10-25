
import copy
import threading
import logging
from skyfield.api import load, wgs84, EarthSatellite
from datetime import datetime, timezone
import numpy as np
from numpy import cos, pi, log10, sinc

from .data_model import (
    Scenario, Breakpoint, Status, TTCModes, TTCAntenna, TTCState, Quality, GroundStationState, SpacecraftState
)
from .sys._common import finite_float, tle_lines
from .rf_link import (
    CCSDS_FREQ_TABLE, ul_mode, CODING_GAIN_TABLE, REQUIRED_EBNO_TABLE, CARRIER_MOD_LOSS_TABLE,
    SC_ANTENNA_GAIN_DB, SC_TX_POWER_DBW, TX_LOSS_DB, GS_BAND_PARAMS,
    compute_fspl, compute_atmospheric_loss, compute_polarization_loss, compute_pointing_loss, compute_antenna_gain,
    compute_c_no, compute_eb_no, compute_link_margin, compute_ber, compute_fer,
    compute_doppler_shift, NO_LINK_C_NO, NO_LINK_MARGIN, NO_LINK_BER, NO_LINK_FER,
)

logger = logging.getLogger(__name__)

# accepted range of the power_ul control, in dBm
POWER_UL_MIN_DBM = 0.0
POWER_UL_MAX_DBM = 70.0

# ground station simulator
class GroundStationSim:
    def __init__(self,
        scenario:Scenario,
        bp:Breakpoint
    ) -> None:
        self.scenario = scenario
        self.breakpoint = bp

        # Initialize lock early before any code that uses it
        self._lock = threading.Lock()

        # ticks left before ul_link_margin can invalidate a sweep again; see the reset in _update_wrap_up
        self._sweep_grace = 0

        lines = tle_lines(self.scenario.tle)
        self.satellite = EarthSatellite(lines[1], lines[2], lines[0])
        self.time_scale = load.timescale()

        self.spectrum_gen = SpectrumGenerator()

        self.state = GroundStationState(ts=datetime.fromisoformat(bp.begin).timestamp())

        # (re)computes location and passes for this breakpoint
        self.set_breakpoint(bp)

        if bp.gs_initial_state:
            with self._lock:
                for k, v in bp.gs_initial_state.items():
                    setattr(self.state, k, v)

    def set_breakpoint(self, bp: Breakpoint) -> None:
        """Point the ground station at a breakpoint (location and passes); call on every breakpoint change."""
        self.breakpoint = bp
        # in UTC: the pass window below is built from these dates' UTC days
        self.dt_i = datetime.fromisoformat(bp.begin).astimezone(timezone.utc)
        self.dt_f = datetime.fromisoformat(bp.end).astimezone(timezone.utc)

        self.location = wgs84.latlon(
            bp.ground_station.latitude,
            bp.ground_station.longitude,
            elevation_m=bp.ground_station.altitude
        )

        # calculate passes for the breakpoint's day(s)
        self.t_i = self.time_scale.utc(self.dt_i.year, self.dt_i.month, self.dt_i.day, 0, 0, 0)
        self.t_f = self.time_scale.utc(self.dt_f.year, self.dt_f.month, self.dt_f.day, 23, 59, 59)
        self.passes = self._find_passes(0.0)
        passes_5 = self._find_passes(5.0)

        # 5 deg window of each 0 deg pass, matched by time since a low pass may never reach 5 deg
        self.passes_5 = [
            next((p5 for p5 in passes_5 if p[0] <= p5[0] and p5[1] <= p[1]), None)
            for p in self.passes
        ]

        with self._lock:
            # FD products are per breakpoint, so readings from the previous one are dropped
            self.state.flight_dynamics = []
            self.state.antenna_diameter_m = bp.ground_station.antenna_diameter_m
            self.state.latitude = bp.ground_station.latitude
            self.state.longitude = bp.ground_station.longitude
            self.state.altitude = bp.ground_station.altitude

    def _find_passes(self, altitude_degrees: float) -> list[list[float]]:
        """[[aos_ts, los_ts], ...] between t_i and t_f; a pass in progress at either end is clipped to it."""
        t, events = self.satellite.find_events(self.location, self.t_i, self.t_f, altitude_degrees=altitude_degrees)

        passes, start = [], None
        for ti, event in zip(t, events):
            ts = ti.utc_datetime().timestamp()
            if event == 0:
                start = ts
            elif event == 2:
                passes.append([start if start is not None else self.t_i.utc_datetime().timestamp(), ts])
                start = None
            elif event == 1 and start is None and not passes:
                # culmination with no preceding rise: pass already in progress at t_i
                start = self.t_i.utc_datetime().timestamp()
        if start is not None:
            passes.append([start, self.t_f.utc_datetime().timestamp()])

        return passes

    def update_state(self, data: dict) -> GroundStationState:
        """Update ground station state from dictionary"""
        with self._lock:
            for k, v in data.items():
                setattr(self.state, k, v)

        return self.state

    def _updates_from_sc_state(self, _state:GroundStationState, sc_state:SpacecraftState) -> GroundStationState:

        if sc_state: # SNR and state updates on spacecraft side based on GS
            _state.ul_state = sc_state.ttc_state_ul
            _state.ul_link_margin = sc_state.ttc_link_margin_ul
        else:
            _state.ul_state = TTCState.NO_RF
            _state.ul_link_margin = -128.0

        return _state

    def _update_tracking(self, _state:GroundStationState, ts:float, sc_state:SpacecraftState) -> GroundStationState:
        _state.elevation, _state.azimuth, _state.distance, _state.doppler_velocity = None, None, None, None

        if self.state.program_track is True:
            for i in self.passes:
                if i[0] <= ts <= i[1]:
                    difference = self.satellite - self.location
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    t = self.time_scale.from_datetime(dt)
                    topocentric = difference.at(t)
                    _state.position = topocentric.position.km
                    alt, az, dist = topocentric.altaz()
                    _, _, _, _, _, velocity = topocentric.frame_latlon_and_rates(self.location)

                    _state.elevation = alt.degrees
                    _state.azimuth = az.degrees
                    _state.distance = dist.km
                    _state.doppler_velocity = velocity.km_per_s * -1.0

                    # update flight dynamics data every 10s
                    if len(_state.position) > 0 and int(ts) % 10 == 0:
                        _reading = _state.position.tolist()
                        if _state.auto_range is True and sc_state.ttc_ranging == Status.enabled:
                            _reading.append(_state.distance)
                        else:
                            _reading.append(0.0)
                        if _state.doppler_enabled is True and sc_state.ttc_coherent == Status.enabled:
                            _reading.append(_state.doppler_velocity)
                        else:
                            _reading.append(0.0)
                        _state.flight_dynamics.append(_reading)

        return _state

    def _next_pass_window(self, _state:GroundStationState, ts:float) -> GroundStationState:
        _state.next_pass_start, _state.next_pass_end = None, None
        _state.next_5_start, _state.next_5_end = None, None

        for i, pass_data in enumerate(self.passes):
            if ts <= pass_data[1]:
                _state.next_pass_start = pass_data[0]
                _state.next_pass_end = pass_data[1]
                if self.passes_5[i] is not None:
                    _state.next_5_start, _state.next_5_end = self.passes_5[i]
                break

        return _state

    # link margin/BER/FER from Eb/N0 for a CCSDS mode table; shared by the D/L budget and its ceiling overrides
    def _dl_margin_ber_fer(self, table, eb_no_dl):
        link_margin_dl = compute_link_margin(
            eb_no_dl, REQUIRED_EBNO_TABLE[table['modulation']], CODING_GAIN_TABLE[table['coding']]
        )
        ber_dl = compute_ber(eb_no_dl)
        fer_dl = compute_fer(ber_dl)
        return link_margin_dl, ber_dl, fer_dl

    # calculate D/L link budget (C/N0 -> Eb/N0 -> margin -> BER/FER)
    def _calc_link_budget_dl(
        self, _state: GroundStationState, sc_state: SpacecraftState, ov_state: dict
    ) -> GroundStationState:
        mode = sc_state.ttc_mode
        band = mode.name[0]
        table = CCSDS_FREQ_TABLE[mode]
        ul_table = CCSDS_FREQ_TABLE[ul_mode(_state.mode, _state.band_ul)]
        sc_antenna = sc_state.ttc_s_antenna if band == 'S' else sc_state.ttc_x_antenna
        mod_loss = CARRIER_MOD_LOSS_TABLE[table['modulation']]

        no_link = (
            # if the spacecraft transmitter for this band is off
            sc_state.tx_status(band) != Status.on
            # if spacecraft is below horizon
            or _state.elevation is None or _state.elevation < 0.0
            or _state.distance is None or _state.distance < 0.0
            # no spectrum if bands in s/c and g/s are different
            or _state.mode.name[0] != band
            # LBSC25 if in X-band + HGA antenna -> no TM + no TC + no spectrum
            or (band == 'X' and sc_state.ttc_x_antenna == TTCAntenna.HGA)
        )

        if no_link:
            c_no_dl = NO_LINK_C_NO
            eb_no_dl = NO_LINK_C_NO
            link_margin_dl = NO_LINK_MARGIN
            ber_dl = NO_LINK_BER
            fer_dl = NO_LINK_FER
            doppler_shift_dl = 0.0
        else:
            eirp_dl = SC_TX_POWER_DBW[table['power_class']] + SC_ANTENNA_GAIN_DB[sc_antenna] - TX_LOSS_DB
            gs_gain_dbi = compute_antenna_gain(_state.antenna_diameter_m, table['dl_freq_mhz'])
            g_over_t = gs_gain_dbi - GS_BAND_PARAMS[band]['noise_temp_dbk']
            fspl = compute_fspl(_state.distance, table['dl_freq_mhz'])
            atm_loss = compute_atmospheric_loss(_state.elevation, table['dl_freq_mhz'])
            pol_loss = compute_polarization_loss(sc_antenna)
            pointing_loss = compute_pointing_loss(_state.elevation)

            c_no_dl = compute_c_no(eirp_dl, fspl, atm_loss, pol_loss, pointing_loss, g_over_t)
            eb_no_dl = compute_eb_no(c_no_dl, table['dl_bit_rate_bps'], mod_loss)
            link_margin_dl, ber_dl, fer_dl = self._dl_margin_ber_fer(table, eb_no_dl)
            doppler_shift_dl = compute_doppler_shift(_state.doppler_velocity, table['dl_freq_mhz'])

        # handle max_c_no_dl override (ceiling on C/N0 in dBHz)
        max_c_no_dl = ov_state.get('max_c_no_dl')
        if max_c_no_dl is not None and c_no_dl > max_c_no_dl:
            c_no_dl = max_c_no_dl
            eb_no_dl = compute_eb_no(c_no_dl, table['dl_bit_rate_bps'], mod_loss)
            link_margin_dl, ber_dl, fer_dl = self._dl_margin_ber_fer(table, eb_no_dl)

        # handle max_eb_no_dl override (ceiling on Eb/N0 in dB)
        max_eb_no_dl = ov_state.get('max_eb_no_dl')
        if max_eb_no_dl is not None and eb_no_dl > max_eb_no_dl:
            eb_no_dl = max_eb_no_dl
            bit_rate = table['dl_bit_rate_bps']
            c_no_dl = eb_no_dl + mod_loss + (10 * log10(bit_rate) if bit_rate and bit_rate > 0 else 0.0)
            link_margin_dl, ber_dl, fer_dl = self._dl_margin_ber_fer(table, eb_no_dl)

        _state.c_no_dl = c_no_dl
        _state.eb_no_dl = eb_no_dl
        _state.link_margin_dl = link_margin_dl
        _state.ber_dl = ber_dl
        _state.fer_dl = fer_dl
        _state.doppler_shift_dl = doppler_shift_dl
        _state.dl_modulation = table['modulation'].name
        _state.dl_coding = table['coding'].name

        # downlink frequency: coherent turnaround of the (Doppler-shifted) uplink, or nominal + one-way doppler
        if sc_state.ttc_coherent == Status.enabled:
            _state.freq_dl_mhz = sc_state.ttc_freq_tx_mhz + doppler_shift_dl
        else:
            _state.freq_dl_mhz = table['dl_freq_mhz'] + doppler_shift_dl
        _state.freq_ul_mhz = ul_table['ul_freq_mhz']

        return _state

    # update D/L status
    def _update_status_dl(
        self, _state: GroundStationState, sc_state: SpacecraftState, ov_state: dict
    ) -> GroundStationState:

        # if mode is wrong, status is affected but spectrum isnt
        if _state.mode != sc_state.ttc_mode:
            _state.link_margin_dl = NO_LINK_MARGIN

        _status_dl = TTCState.NO_RF

        if _state.link_margin_dl > _state.status_dl_transitions[_state.mode.name]['FRAME_LOCK']:
            _status_dl = TTCState.FRAME_LOCK
        elif _state.link_margin_dl > _state.status_dl_transitions[_state.mode.name]['BIT_LOCK']:
            _status_dl = TTCState.BIT_LOCK
        elif _state.link_margin_dl > _state.status_dl_transitions[_state.mode.name]['PLL_LOCK']:
            _status_dl = TTCState.PLL_LOCK
        elif _state.link_margin_dl > NO_LINK_MARGIN:
            # a carrier too weak to phase-lock is still detected; NO_LINK_MARGIN means no signal at all and stays NO_RF
            _status_dl = TTCState.RF_DETECTED

        # handle max_status_dl override
        max_status_dl = ov_state.get('max_status_dl')
        if max_status_dl is not None and _status_dl.value > max_status_dl.value:
            _status_dl = max_status_dl

        # set frame quality to good by default if no override
        frame_quality_ov = ov_state.get('frame_quality')
        if frame_quality_ov is None:
            if _status_dl == TTCState.FRAME_LOCK:
                _state.frame_quality = Quality.good
            else:
                _state.frame_quality = Quality.unknown
        else:
            _state.frame_quality = frame_quality_ov

        _state.status_dl = _status_dl

        return _state

    def _update_spectrums(self, _state:GroundStationState, sc_state:SpacecraftState) -> GroundStationState:

        if _state.carrier_ul == Status.on:
            _freqs, _totals = self.spectrum_gen.uplink_spectrum(_state.mode, band=_state.band_ul, power=_state.power_ul)
        else:
            _freqs, _totals = self.spectrum_gen.uplink_spectrum(_state.mode, band=_state.band_ul, power=0)
        _ul_f = list(_freqs[np.isfinite(_totals)])
        _ul_p = list(_totals[np.isfinite(_totals)])
        _ul = list(zip(_ul_f, _ul_p))

        _freqs, _totals = self.spectrum_gen.downlink_spectrum(
            sc_state.ttc_mode, SNR=_state.eb_no_dl, v_doppler=_state.doppler_velocity,
            coherent=sc_state.ttc_coherent == Status.enabled
        )
        _dl_f = list(_freqs[np.isfinite(_totals)])
        _dl_p = list(_totals[np.isfinite(_totals)])
        _dl = list(zip(_dl_f, _dl_p))

        _state.spectrum_ul = _ul
        _state.spectrum_dl = _dl

        return _state

    def _update_wrap_up(self, _state : GroundStationState) -> GroundStationState:

        # auto disconnect u/l carrier below 5 elevation
        if _state.carrier_ul == Status.on and _state.elevation is not None and _state.elevation <= 5.0:
            _state.carrier_ul = Status.off

        # reset U/L status
        if _state.elevation is None or _state.elevation <= 0.0:
            _state.ul_state = TTCState.NO_RF
            _state.sweep_done = False
            _state.sweep_count = 0
            _state.frame_quality = Quality.unknown

        # reset doppler requires two way PLL
        if int(_state.ul_state) < int(TTCState.PLL_LOCK) or int(_state.status_dl) < int(TTCState.PLL_LOCK):
            _state.doppler_enabled = False

        # reset sweep done: reset on carrier off
        if _state.carrier_ul != Status.on:
            _state.sweep_done = False
            self._sweep_grace = 0
        elif self._sweep_grace > 0:
            self._sweep_grace -= 1
        elif _state.ul_link_margin != NO_LINK_MARGIN and _state.ul_link_margin <= -1:
            _state.sweep_done = False

        return _state

    def update(
        self, ts:float, sc_state:SpacecraftState | None = None, overrides:dict | None = None
    ) -> GroundStationState:
        overrides = overrides or {}

        # start the next state from the current state
        _state = copy.deepcopy(self.state)
        _state.ts = ts

        # updates from spacecraft state
        _state = self._updates_from_sc_state(_state, sc_state)

        # update tracking: calculate elevation, azimuth, range (distance) and doppler velocity
        _state = self._update_tracking(_state, ts, sc_state)

        # update next pass window
        _state = self._next_pass_window(_state, ts)

        # calculate D/L link budget
        _state = self._calc_link_budget_dl(_state, sc_state, overrides)

        # build spectrums
        _state = self._update_spectrums(_state, sc_state)

        # update D/L state
        _state = self._update_status_dl(_state, sc_state, overrides)

        # apply direct gs overrides (after computation so they always win)
        if isinstance(overrides, dict):
            if 'status_dl' in overrides:
                _state.status_dl = overrides['status_dl']
            # manual TM/TC master switches
            _state.ov_no_tm = bool(overrides.get('no_tm'))
            _state.ov_no_tc = bool(overrides.get('no_tc'))
            if _state.ov_no_tm:
                _state.status_dl = TTCState.NO_RF

        # updates wrap up
        _state = self._update_wrap_up(_state)

        # update current state
        with self._lock:
            self.state = _state

        # pong
        return self.state

    def _set_state(self, settings):
        with self._lock:
            for attr, value in settings:
                setattr(self.state, attr, value)

    def control(self, data):
        _ok = { 'status': 'OK' }
        _fail = { 'status': 'FAIL' }

        if data['control'] == 'carrier_ul':
            if data['value'] == 'off':
                self._set_state([('carrier_ul', Status.off)])
                return _ok
            if data['value'] == 'on' and self.state.elevation and self.state.elevation >= 5.0:
                self._set_state([('carrier_ul', Status.on)])
                return _ok
            return _fail

        if data['control'] == 'sweep':
            if data['value'] is True:
                if self.state.carrier_ul == Status.on:
                    self._set_state([('sweep_done', True), ('sweep_count', self.state.sweep_count+1 )])
                    self._sweep_grace = 2
                    return _ok
                else:
                    return _fail
            else:
                self._set_state([('sweep_done', False)])
                return _ok

        if data['control'] == 'power_ul':
            power_ul = finite_float(data['value'])
            # a few thousand dB below zero overflows the uplink spectrum and crashes the tick
            if not POWER_UL_MIN_DBM <= power_ul <= POWER_UL_MAX_DBM:
                return _fail
            self._set_state([('power_ul', power_ul)])
            return _ok

        if data['control'] == 'mode':
            if data['value'] in [
                'S_Sup_LBR', 'S_Sup_HBR', 'X_Sup_LBR', 'X_Sup_HBR', 'S_Res_LBR', 'X_Res_LBR', 'S_Sub_LBR', 'X_Sub_LBR'
            ]:
                self._set_state([('mode', TTCModes[data['value']])])
                return _ok
            else:
                return _fail

        if data['control'] == 'band_ul':
            # the carrier cannot be retuned while it is radiating
            if data['value'] not in ['S', 'X'] or self.state.carrier_ul == Status.on:
                return _fail
            sets = [('band_ul', data['value'])]
            # a new carrier needs a new sweep
            if self.state.band_ul != data['value']:
                sets.append(('sweep_done', False))
            self._set_state(sets)
            return _ok

        if data['control'] == 'auto_track':
            if isinstance(data['value'], bool):
                self._set_state([('auto_track', data['value'])])
                return _ok
            else:
                return _fail

        if data['control'] == 'program_track':
            if isinstance(data['value'], bool):
                self._set_state([('program_track', data['value'])])
                return _ok
            else:
                return _fail

        if data['control'] == 'auto_range':
            if isinstance(data['value'], bool):
                self._set_state([('auto_range', data['value'])])
                return _ok
            else:
                return _fail

        if data['control'] == 'doppler_enabled':
            if isinstance(data['value'], bool):
                self._set_state([('doppler_enabled', data['value'])])
                return _ok
            else:
                return _fail

        if data['control'] == 'frame_checks':
            if data['value'] == 'enabled':
                self._set_state([('frame_checks', Status[data['value']])])
                return _ok
            elif data['value'] == 'disabled':
                self._set_state([('frame_checks', Status[data['value']])])
                return _ok
            else:
                return _fail

        return _fail

# spectrums generator
class SpectrumGenerator:
    def __init__(self, SPECTRUMSIZE : int = 200, BW : int = 20) -> None:
        self.SPECTRUMSIZE = SPECTRUMSIZE
        self.BW = BW

        # the uplink bandwidth/modulation index are the same in every mode; the carrier
        # frequencies come from CCSDS_FREQ_TABLE, as in the link budget
        self.ul_bw = 256e3
        self.ul_mod_idx = 0.5

        self.modeParameters = {
            TTCModes.S_Sup_LBR:{
                "dl_bw" : 1e6
            },
            TTCModes.S_Sup_HBR:{
                "dl_bw" : 2e6
            },
            TTCModes.X_Sup_LBR:{
                "dl_bw" : 3e6
            },
            TTCModes.X_Sup_HBR:{
                "dl_bw" : 4e6
            },
            TTCModes.S_Res_LBR:{
                "dl_bw" : 1e6
            },
            TTCModes.X_Res_LBR:{
                "dl_bw" : 3e6
            },
            TTCModes.S_Sub_LBR:{
                "dl_bw" : 1e6
            },
            TTCModes.X_Sub_LBR:{
                "dl_bw" : 3e6
            }
        }

    def _RC_filter(self, f, roll_off, bw):
        return 0.5*(1+cos(pi/bw/roll_off*(abs(f)-(1-roll_off)*bw/2)))

    def _lin2db(self, x):
        return 10*log10(x)

    def _db2lin(self, x):
        return 10**(x/10)

    def _NRZ_PM(self, mode: str, bw, frequencies, cf, mod_idx = 0.7):
        if mode == 'Sub': #NRZ/PSK/PM, subcarrier
            bw = bw/16
            P = lambda x: sinc(x/bw)/bw
            S = lambda x: bw/4*(P(x+4*bw)**2+P(x-4*bw)**2)
        elif mode == 'Res': #SP-L/PM
            bw = bw/4
            P = lambda x: sinc(x/bw)/bw
            S = lambda x: bw/4*(P(x+bw)**2+P(x-bw)**2)
        else: #NRZ-L/PM
            bw = bw/2
            P = lambda x: sinc(x/bw)/bw
            S = lambda x: bw/4*(P(x)**2)

        carrier_idx = min(range(len(frequencies)), key=lambda i: abs(frequencies[i]-cf))
        carrier = 1e-12*np.ones(self.SPECTRUMSIZE)
        carrier[carrier_idx] = 10*np.cos(mod_idx)**2 # 10 is just a factor, should be ref_bw/freq_step

        signal = np.array([S(f-cf) for f in frequencies])
        signal = np.sin(mod_idx)**2*signal + carrier
        return signal


    def _PSK(self, bw, frequencies, cf, roll_off = 0.4):
        spectrum_low = cf - self.BW/2
        spectrum_high = cf + self.BW/2
        #maybe make this constant until mode changes
        freq = [
            spectrum_low, -bw/2*(1+roll_off)+cf, -bw/2*(1-roll_off)+cf,
            bw/2*(1-roll_off)+cf, bw/2*(1+roll_off)+cf, spectrum_high
        ]
        signal = np.piecewise(
            frequencies,
            [
                frequencies < freq[1],
                (frequencies >= freq[1]) & (frequencies < freq[2]),
                (frequencies >= freq[2]) & (frequencies < freq[3]),
                (frequencies >= freq[3]) & (frequencies < freq[4]),
                frequencies >= freq[4]
            ],
            [0, lambda x: self._RC_filter(x-cf, roll_off, bw), 1, lambda x: self._RC_filter(x-cf, roll_off, bw), 0]
        )
        return signal

    def downlink_spectrum(self, mode : TTCModes, v_doppler = 0, SNR = 5, coherent = False):
        #Frequency span of Spectrum
        zoom = 4
        spectrum_center = CCSDS_FREQ_TABLE[mode]['dl_freq_mhz']
        spectrum_low = spectrum_center - self.BW/2/zoom
        spectrum_high = spectrum_center + self.BW/2/zoom
        frequencies = np.linspace(spectrum_low, spectrum_high, self.SPECTRUMSIZE)

        # doppler_velocity is None until the first tracking update (e.g. before AOS)
        if v_doppler is None:
            v_doppler = 0

        #values that go to deep to explain
        noise_level = -110
        #fixed by mode
        c = 3e8

        doppler = 1+v_doppler*1000/c
        bw = self.modeParameters[mode]["dl_bw"]/1e6
        cf = spectrum_center * doppler
        if coherent:
            cf = cf *doppler
        modename = mode.name[2:5]
        if modename == 'Sup':
            signal = self._db2lin(SNR)*self._PSK(bw, frequencies, cf)
        else:
            signal = self._db2lin(SNR)*self._NRZ_PM(modename, bw, frequencies, cf)

        noise = abs(np.random.normal(1, 0.2, self.SPECTRUMSIZE))

        total = self._lin2db(signal+noise) + noise_level

        return [frequencies, total]

    def uplink_spectrum(self, mode : TTCModes = TTCModes.S_Sup_LBR, band = 'S', power = 53, SNR = 20, noisefloor = 10):
        #Frequency span of Spectrum
        zoom = 16
        bw = self.ul_bw/1e6
        # the ground station's uplink carrier, as freq_ul_mhz reports it
        up_freq = CCSDS_FREQ_TABLE[ul_mode(mode, band)]['ul_freq_mhz']
        spectrum_center = up_freq # center frequency of the spectrum analyzer
        spectrum_low = spectrum_center - self.BW/2/zoom
        spectrum_high = spectrum_center + self.BW/2/zoom
        frequencies = np.linspace(spectrum_low, spectrum_high, self.SPECTRUMSIZE)


        mod_idx = self.ul_mod_idx
        cf = up_freq # center frequency of the signal
        noise = (self._db2lin(-SNR)*abs(np.random.normal(0, 0.5, self.SPECTRUMSIZE))
                 + self._db2lin(noisefloor-power)*abs(np.random.normal(0, 0.2, self.SPECTRUMSIZE)))
        signal = self._NRZ_PM('Res', bw, frequencies, cf, mod_idx)
        total = power + self._lin2db( noise + signal)

        return [frequencies, total]
