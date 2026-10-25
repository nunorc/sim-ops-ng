
from typing import Protocol

from ..data_model import (
    SpacecraftState, BusMessage, TTCState, GroundStationState, Status, TTCModes, TTCAntenna, Scenario
)
from ._common import set_choice, set_enum
from ..rf_link import (
    CCSDS_FREQ_TABLE, TURNAROUND_RATIO, ul_mode, CODING_GAIN_TABLE, REQUIRED_EBNO_TABLE, CARRIER_MOD_LOSS_TABLE,
    SC_ANTENNA_GAIN_DB, SC_NOISE_TEMP_DBK, TX_LOSS_DB,
    compute_fspl, compute_atmospheric_loss, compute_polarization_loss, compute_pointing_loss, compute_antenna_gain,
    compute_c_no, compute_eb_no, compute_link_margin, compute_ber, compute_fer,
    compute_doppler_shift, NO_LINK_C_NO, NO_LINK_MARGIN, NO_LINK_BER, NO_LINK_FER,
)

class TTC(Protocol):
    def init(self, scenario:Scenario | None = None) -> None: ...
    def update(
        self, _state: SpacecraftState, ts: float, gs_state: GroundStationState | None = None
    ) -> SpacecraftState: ...
    def command(self, _state:SpacecraftState, message:BusMessage) -> bool | None: ...

class TTCMin:
    def __init__(self) -> None:
        self.name:str | None = None

    def init(self, _scenario:Scenario | None = None) -> None:
        self.name = "ttc"

    def update(self, _state:SpacecraftState, _ts:float, gs_state:GroundStationState | None = None) -> SpacecraftState:
        # update U/L link budget (CCSDS C/N0 -> Eb/N0 -> margin -> BER/FER)
        budget = self._calculate_uplink_budget(_state, gs_state)
        _state.ttc_c_no_ul = budget['c_no_ul']
        _state.ttc_eb_no_ul = budget['eb_no_ul']
        _state.ttc_link_margin_ul = budget['link_margin_ul']
        _state.ttc_ber_ul = budget['ber_ul']
        _state.ttc_fer_ul = budget['fer_ul']
        _state.ttc_doppler_shift_ul = budget['doppler_shift_ul']
        _state.ttc_freq_rx_mhz = budget['freq_rx_mhz']
        _state.ttc_freq_tx_mhz = budget['freq_tx_mhz']
        # update u/l state from link margin; the receiver for the uplink band decides if the uplink can be acquired
        _state.ttc_state_ul = TTCState.NO_RF
        if _state.rx_status(budget['band']) == Status.on:
            if _state.ttc_link_margin_ul > 2:
                _state.ttc_state_ul = TTCState.BIT_LOCK
            elif _state.ttc_link_margin_ul > 0:
                _state.ttc_state_ul = TTCState.PSK_LOCK
            elif _state.ttc_link_margin_ul > -1:
                _state.ttc_state_ul = TTCState.PLL_LOCK

        sweep_done = gs_state.sweep_done if gs_state is not None else False
        if not sweep_done:
            _state.ttc_state_ul = TTCState.NO_RF

        status_dl = gs_state.status_dl if gs_state is not None else TTCState.NO_RF
        if int(_state.ttc_state_ul) < int(TTCState.PLL_LOCK) or int(status_dl) < int(TTCState.PLL_LOCK):
            _state.ttc_coherent = Status.disabled

        return _state

    def _calculate_uplink_budget(self, _state:SpacecraftState, gs_state:GroundStationState | None = None) -> dict:
        # the uplink band is set on the ground station and need not match the downlink band (e.g. S up, X down)
        gs_mode = gs_state.mode if gs_state else _state.ttc_mode
        band = gs_state.band_ul if gs_state else _state.ttc_mode.name[0]
        table = CCSDS_FREQ_TABLE[ul_mode(gs_mode, band)]
        distance = gs_state.distance if gs_state else None

        no_link = (
            gs_state is None
            or gs_state.carrier_ul != Status.on
            or gs_state.elevation is None
            or gs_state.elevation <= 0
            or distance is None
            or distance <= 0
        )

        ul_freq_mhz = table['ul_freq_mhz']
        dl_freq_mhz = CCSDS_FREQ_TABLE[_state.ttc_mode]['dl_freq_mhz']
        sc_antenna = _state.ttc_s_antenna if band == 'S' else _state.ttc_x_antenna

        if no_link:
            c_no_ul = NO_LINK_C_NO
            eb_no_ul = NO_LINK_C_NO
            link_margin_ul = NO_LINK_MARGIN
            ber_ul = NO_LINK_BER
            fer_ul = NO_LINK_FER
            doppler_shift_ul = 0.0
        else:
            # gs_state.power_ul is in dBm (per MCS UI), convert to dBW for the link budget
            gs_gain_dbi = compute_antenna_gain(gs_state.antenna_diameter_m, ul_freq_mhz)
            eirp_ul = (gs_state.power_ul - 30.0) + gs_gain_dbi - TX_LOSS_DB
            fspl = compute_fspl(distance, ul_freq_mhz)
            atm_loss = compute_atmospheric_loss(gs_state.elevation, ul_freq_mhz)
            pol_loss = compute_polarization_loss(sc_antenna)
            pointing_loss = compute_pointing_loss(gs_state.elevation)
            g_over_t = SC_ANTENNA_GAIN_DB[sc_antenna] - SC_NOISE_TEMP_DBK

            c_no_ul = compute_c_no(eirp_ul, fspl, atm_loss, pol_loss, pointing_loss, g_over_t)
            mod_loss = CARRIER_MOD_LOSS_TABLE[table['modulation']]
            eb_no_ul = compute_eb_no(c_no_ul, table['ul_bit_rate_bps'], mod_loss)
            link_margin_ul = compute_link_margin(
                eb_no_ul, REQUIRED_EBNO_TABLE[table['modulation']], CODING_GAIN_TABLE[table['coding']]
            )
            ber_ul = compute_ber(eb_no_ul)
            fer_ul = compute_fer(ber_ul)
            doppler_shift_ul = compute_doppler_shift(gs_state.doppler_velocity, ul_freq_mhz)

        # coherent downlink frequency via CCSDS turnaround ratio
        freq_rx_mhz = ul_freq_mhz + doppler_shift_ul
        if _state.ttc_coherent == Status.enabled:
            freq_tx_mhz = freq_rx_mhz * TURNAROUND_RATIO[(band, _state.ttc_mode.name[0])]
        else:
            freq_tx_mhz = dl_freq_mhz

        return {
            'band': band,
            'c_no_ul': c_no_ul,
            'eb_no_ul': eb_no_ul,
            'link_margin_ul': link_margin_ul,
            'ber_ul': ber_ul,
            'fer_ul': fer_ul,
            'doppler_shift_ul': doppler_shift_ul,
            'freq_rx_mhz': freq_rx_mhz,
            'freq_tx_mhz': freq_tx_mhz,
        }

    def command(self, state:SpacecraftState, message:BusMessage) -> bool | None:
        command = message.payload.get("command")
        value = message.payload.get("value")
        result = None

        if command == 'ttc_mode':
            result = set_enum(
                state, 'ttc_mode', value, TTCModes,
                ['S_Sup_LBR', 'S_Sup_HBR', 'X_Sup_LBR', 'X_Sup_HBR', 'S_Res_LBR', 'X_Res_LBR', 'S_Sub_LBR', 'X_Sub_LBR']
            )
        if command == 'ttc_s_antenna':
            result = set_enum(state, 'ttc_s_antenna', value, TTCAntenna, ['LGA_RHC', 'LGA_LHC'])
        if command == 'ttc_x_antenna':
            result = set_enum(state, 'ttc_x_antenna', value, TTCAntenna, ['MGA', 'HGA'])
        if command == 'ttc_chain':
            result = set_choice(state, 'ttc_chain', value, ['A', 'B'])
        if command == 'ttc_mcu':
            result = set_enum(state, 'ttc_mcu', value, Status, ['nominal', 'safe', 'error'])
        if command == 'ttc_mcu_reboot':
            # software reboot: acknowledged nominally but has no effect on the state
            result = True
        if command == 'ttc_ping':
            state.ttc_ping_ack = state.ttc_ping_ack + 1
            result = True
        if command == 'ttc_coherent':
            result = set_enum(state, 'ttc_coherent', value, Status, ['enabled', 'disabled'])
        if command == 'ttc_ranging':
            result = set_enum(state, 'ttc_ranging', value, Status, ['enabled', 'disabled'])

        return result
