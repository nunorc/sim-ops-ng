
import random
from typing import Protocol

from ..data_model import SpacecraftState, Status, BusMessage, Scenario
from ._common import set_choice, set_enum, safe_chain_swap, finite_float

class EPS(Protocol):
    def init(self, scenario:Scenario | None = None) -> None: ...
    def update(self, _state: SpacecraftState, ts: float) -> SpacecraftState: ...
    def command(self, _state:SpacecraftState, message:BusMessage) -> bool | None: ...

class EPSMin:
    def __init__(self) -> None:
        self.name:str | None = None

    def init(self, _scenario:Scenario | None = None):
        self.name = "eps"

    def update(self, _state: SpacecraftState, ts: float) -> SpacecraftState:
        # the arrays report illumination, not health: SUN when sunlit, NO_SUN in eclipse
        _v = Status.sun if _state.is_sunlit else Status.no_sun
        _state.eps_sol_array = [_v, _v]

        _state.eps_net_power = self._calc_net_power(_state)

        # power chain summary: a degraded ACU is critical, otherwise net power decides (eps_pdu is not modelled)
        if _state.eps_acu != Status.nominal:
            _state.eps_power_status = Status.power_critical
        elif _state.eps_net_power > 0:
            _state.eps_power_status = Status.power_positive
        else:
            _state.eps_power_status = Status.power_negative

        # update battery dod
        if ts > 0:
            _state.eps_battery_dod = _state.eps_battery_dod - (_state.eps_net_power*(ts-_state.ts))

        # limit battery dod
        _state.eps_battery_dod = min(_state.eps_battery_dod, 100)
        _state.eps_battery_dod = max(_state.eps_battery_dod, 0)

        # update temperature
        equilibrium_temp = 10
        sunlit_temp = 20
        transmitter_on_temp = 10
        gnss_on_temp = 10
        cam_on_temp = 10
        tx_on = int(_state.ttc_s_tx_status==Status.on) + int(_state.ttc_x_tx_status==Status.on)
        target_temp = equilibrium_temp + tx_on*transmitter_on_temp + int(_state.is_sunlit)*sunlit_temp+\
            int(_state.pl_gnss_status==Status.on)*gnss_on_temp + int(_state.pl_camera_status==Status.on)*cam_on_temp

        _state.eps_temperature = (_state.eps_temperature - (_state.eps_temperature-target_temp)*0.005
                                   + random.random()-0.5)

        return _state

    def _calc_net_power(self, _state: SpacecraftState) -> float:
        _power = -2.0 # base consumption

        # an ACU fault shunts the array power, so the loads run off the battery alone and the DoD keeps rising
        _generating = (_state.eps_acu != Status.control_err
                       and _state.is_sunlit)

        if _generating:
            _power += 5  # array 1
            _power += 5  # array 2
        if _state.pl_gnss_status == Status.on:
            _power -= 0.5
        if _state.pl_camera_status == Status.on:
            _power -= 4
        for _tx in (_state.ttc_s_tx_status, _state.ttc_x_tx_status):
            if _tx == Status.on:
                _power -= 5
        for _rx in (_state.ttc_s_rx_status, _state.ttc_x_rx_status):
            if _rx == Status.on:
                _power -= 0.5

        return _power/100

    # TTC transmitters and receivers are powered from the EPS, one command per unit
    TTC_POWER_COMMANDS = {
        'eps_ttc_s_tx': 'ttc_s_tx_status',
        'eps_ttc_s_rx': 'ttc_s_rx_status',
        'eps_ttc_x_tx': 'ttc_x_tx_status',
        'eps_ttc_x_rx': 'ttc_x_rx_status',
    }

    def command(self, state:SpacecraftState, message:BusMessage) -> bool | None:
        command = message.payload.get("command")
        value = message.payload.get("value")
        result = None

        if command == 'eps_chain':
            if value in ['A', 'B']:
                # on chain swap -> OBSW to safe and ADCS to Sun pointing
                if state.eps_chain != value:
                    safe_chain_swap(state)
                result = set_choice(state, 'eps_chain', value, ['A', 'B'])
            else:
                result = False
        if command == 'eps_battery_dod':
            state.eps_battery_dod = max(0.0, min(100.0, finite_float(value)))
            result = True
        if command in ('eps_sol_array_1_reset', 'eps_sol_array_2_reset'):
            # no effect on spacecraft state — accepted/ack'd only
            result = True
        if command == 'eps_power_cycle_aocs':
            # power cycle recovers the configuration state
            state.aocs_valid = Status.unknown
            result = True
        if command == 'eps_power_cycle_ttc':
            # power cycle recovers the configuration state
            state.ttc_mcu = Status.nominal
            result = True
        if command == 'eps_power_cycle_acu':
            # power cycle recovers the configuration state
            state.eps_acu = Status.nominal
            result = True
        if command == 'eps_power_cycle_pdu':
            # power cycle recovers the configuration state; eps_pdu is telemetry only, so nothing else changes
            state.eps_pdu = Status.nominal
            result = True
        if command in self.TTC_POWER_COMMANDS:
            result = set_enum(state, self.TTC_POWER_COMMANDS[command], value, Status, ['on', 'off'])

        return result
