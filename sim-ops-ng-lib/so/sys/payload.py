
from typing import Protocol

from ..data_model import SpacecraftState, BusMessage, Status, Scenario
from ._common import set_enum

class Payload(Protocol):
    def init(self, scenario:Scenario | None = None) -> None: ...
    def update(self, _state:SpacecraftState, ts:float) -> SpacecraftState: ...
    def command(self, _state:SpacecraftState, message:BusMessage) -> bool | None: ...

class PayloadMin:
    def __init__(self) -> None:
        self.name:str | None = None

    def init(self, _scenario:Scenario | None = None) -> None:
        self.name = "pl"

    def update(self, _state:SpacecraftState, _ts:float) -> SpacecraftState:
        # the GNSS receiver only outputs a fix while on; when off the last (stale) position is kept
        if _state.pl_gnss_status == Status.on:
            _state.pl_gnss_pos = list(_state.aocs_position)

        return _state

    def command(self, state:SpacecraftState, message:BusMessage) -> bool | None:
        command = message.payload.get("command")
        value = message.payload.get("value")
        result = None

        if command == 'pl_gnss_status':
            if state.dhs_obsw_mode == Status.nominal:
                result = set_enum(state, 'pl_gnss_status', value, Status, ['on', 'off'])
            else:
                result = False
        if command == 'pl_camera_status':
            if state.dhs_obsw_mode == Status.nominal:
                result = set_enum(state, 'pl_camera_status', value, Status, ['on', 'off'])
            else:
                result = False
        if command == 'pl_sdr_status':
            if state.dhs_obsw_mode == Status.nominal:
                result = set_enum(state, 'pl_sdr_status', value, Status, ['on', 'off'])
            else:
                result = False

        return result
