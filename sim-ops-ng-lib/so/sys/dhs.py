
from typing import Protocol
from datetime import datetime, timezone

from ..data_model import SpacecraftState, Status, BusMessage, AOCSTarget, TTCModes, Scenario
from ._common import set_choice, set_enum, safe_chain_swap, finite_float

# memory dump rate in S-band low bit rate, in percent of memory per second
LBR_DUMP_RATE = 0.2778

class DHS(Protocol):
    def init(self, scenario:Scenario | None = None) -> None: ...
    def update(self, _state: SpacecraftState, ts: float) -> SpacecraftState: ...
    def command(self, _state:SpacecraftState, message:BusMessage) -> bool | None: ...

class DHSMin:
    def __init__(self) -> None:
        self.name:str | None = None
        self.triggered_safe_mode = False

    def init(self, _scenario:Scenario | None = None) -> None:
        self.name = "dhs"
        self.triggered_safe_mode = False

    def update(self, _state: SpacecraftState, ts:float) -> SpacecraftState:
        # update onboard memory
        _state.dhs_tm_counter = _state.dhs_tm_counter + 1

        new_tm = []
        ts_str = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace('+00:00', '')
        new_tm.append(f"{str(_state.dhs_tm_counter)}\t{ts_str} TM Packet")
        if _state.dhs_mem_dump_enabled:
            # one memory packet per tick at the slowest dump rate, scaled with the mode's rate
            for _ in range(max(1, round(self._dump_rate(_state.ttc_mode) / LBR_DUMP_RATE))):
                new_tm.append(f"\t{ts_str} Memory Packet")
        _state.dhs_tm_window = new_tm + _state.dhs_tm_window[0:12-len(new_tm)]

        _state = self._update_memory(_state, ts)

        _state = self.fdir(_state)

        return _state

    def fdir(self, _state: SpacecraftState) -> SpacecraftState:
        # battery depletion check — trigger safe mode once when DOD reaches 95 %
        if _state.eps_battery_dod >= 95:
            if not self.triggered_safe_mode:
                _state = self._trigger_safe_mode(_state)
                self.triggered_safe_mode = True
        else:
            self.triggered_safe_mode = False

        # over-temperature check — trigger safe mode whenever temperature exceeds limit
        if _state.eps_temperature >= 60:
            _state = self._trigger_safe_mode(_state)

        return _state

    def _trigger_safe_mode(self, _state: SpacecraftState) -> SpacecraftState:
        _state.aocs_valid = Status.unknown
        _state.aocs_chain = 'B'
        _state.aocs_mode = AOCSTarget.SUN
        _state.ttc_chain = 'B'
        _state.ttc_mode = TTCModes.S_Sup_LBR
        _state.eps_chain = 'B'
        _state.dhs_chain = 'B'
        _state.dhs_obsw_mode = Status.safe
        _state.pl_gnss_status = Status.off
        _state.pl_camera_status = Status.off
        _state.pl_sdr_status = Status.off
        return _state

    @staticmethod
    def _dump_rate(mode:TTCModes) -> float:
        """Memory dump rate in %/s for a TTC mode; a full memory empties in ~3 min at S-band high bit rate."""
        band, carrier, bit_rate = mode.name.split('_')

        # modifier based on bit rate
        _mod = LBR_DUMP_RATE if bit_rate == 'LBR' else 2 * LBR_DUMP_RATE

        # modifier based on S/X-band
        if band == 'X':
            _mod = _mod * 3

        # modifier based on carrier: suppressed (full rate), residual or subcarrier
        if carrier == 'Res':
            _mod = _mod * 1/4
        if carrier == 'Sub':
            _mod = _mod * 1/8

        return _mod

    def _update_memory(self, _state:SpacecraftState, ts:float):

        # reset memory dump when memory empty
        if _state.dhs_memory <= 0.0:
            _state.dhs_mem_dump_enabled = False

        # memory usage updates
        _use = 0.0001 # memory fills with basic TM
        if _state.pl_camera_status == Status.on:
            _use += 0.5 # memory fills with Camera data
        if _state.pl_gnss_status == Status.on:
            _use += 0.0005 # memory fills with GNSS data
        _state.dhs_memory += _use * (ts-_state.ts)

        # if memory dump enabled
        if _state.dhs_mem_dump_enabled:

            _state.dhs_memory -= self._dump_rate(_state.ttc_mode) * (ts-_state.ts)

        # bound value to percentage
        _state.dhs_memory = max(_state.dhs_memory, 0)
        _state.dhs_memory = min(_state.dhs_memory, 100)

        return _state

    def command(self, state:SpacecraftState, message:BusMessage) -> bool | None:
        command = message.payload.get("command")
        value = message.payload.get("value")
        result = None

        if command == 'dhs_chain':
            if value in ['A', 'B']:
                # on chain swap -> OBSW to safe and ADCS to Sun pointing
                if state.dhs_chain != value:
                    safe_chain_swap(state)
                result = set_choice(state, 'dhs_chain', value, ['A', 'B'])
            else:
                result = False
        if command == 'dhs_obsw_mode':
            result = set_enum(state, 'dhs_obsw_mode', value, Status, ['safe', 'nominal'])
        if command == 'dhs_memory':
            state.dhs_memory = max(0.0, min(100.0, finite_float(value)))
            result = True
        if command == 'dhs_mem_dump_enabled':
            result = set_choice(state, 'dhs_mem_dump_enabled', value, [True, False])
        if command == 'trigger_safe_mode':
            state = self._trigger_safe_mode(state)
            self.triggered_safe_mode = True
            result = True
        if command == 'dhs_uploaded':
            # broadcast every tick: keep the last 10, as dhs_tc_history does
            state.dhs_uploaded = (state.dhs_uploaded + [value])[-10:]
            result = True

        return result
