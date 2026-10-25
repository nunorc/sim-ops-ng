
import threading
import copy
import logging
from datetime import datetime, timezone

from .data_model import SpacecraftState, Status, TTCState, BusMessage, GroundStationState, Scenario
from .sys.aocs import AOCS, AOCSMin
from .sys.ttc import TTC, TTCMin
from .sys.eps import EPS, EPSMin
from .sys.dhs import DHS, DHSMin
from .sys.payload import Payload, PayloadMin

logger = logging.getLogger(__name__)

class CommunicationBus:
    def __init__(self):
        self.systems = {}

    def register(self, system):
        self.systems[system.name] = system

    def send(self, state:SpacecraftState, message:BusMessage):
        logger.info(f"CommunicationBus send to [{message.destination}] message: {message}")

        # DHS logs every onboard TC, whichever subsystem it's destined for
        state.dhs_tc_counter = state.dhs_tc_counter + 1
        ts_str = datetime.fromtimestamp(state.ts, tz=timezone.utc).isoformat().replace('+00:00', '')
        newTC = (f"{state.dhs_tc_counter}\t{ts_str}\t"
                 f"{message.payload.get('command')}={message.payload.get('value')}")
        state.dhs_tc_history = [newTC] + state.dhs_tc_history[0:9]

        if message.destination in self.systems:
            return self.systems[message.destination].command(state, message)

        logger.info(f"CommunicationBus destination not found: {message.destination}")
        return None

class SpacecraftSim:
    def __init__(self,
        name:str = "",
        aocs:AOCS | None = None,
        ttc:TTC | None = None,
        eps:EPS | None = None,
        dhs:DHS | None = None,
        payload:Payload | None = None,
        state:SpacecraftState | None = None,
        scenario:Scenario|None = None
    ) -> None:
        self.name = name

        # set subsystems
        self.aocs = aocs if aocs is not None else AOCSMin()
        self.ttc = ttc if ttc is not None else TTCMin()
        self.eps = eps if eps is not None else EPSMin()
        self.dhs = dhs if dhs is not None else DHSMin()
        self.payload = payload if payload is not None else PayloadMin()

        # init subsystems
        self.aocs.init(scenario=scenario)
        self.ttc.init(scenario)
        self.eps.init(scenario)
        self.dhs.init(scenario)
        self.payload.init(scenario)

        # init spacecraft state
        self.state = state if state is not None else SpacecraftState()
        if scenario is not None and scenario.breakpoints:
            # seed ts to the first breakpoint's begin so the first update() computes a zero time delta
            self.state.ts = datetime.fromisoformat(scenario.breakpoints[0].begin).timestamp()
        self._lock = threading.Lock()

        # pre-override values, captured on first override so they can be restored once it's removed
        self._override_prev = {}

        # spacecraft bus
        self.bus = CommunicationBus()
        self.bus.register(self.aocs)
        self.bus.register(self.ttc)
        self.bus.register(self.eps)
        self.bus.register(self.dhs)
        self.bus.register(self.payload)

    def update(
        self, ts: float, gs_state: GroundStationState | None = None, overrides: dict | None = None
    ) -> SpacecraftState:
        if overrides is None:
            overrides = {}
        _state = copy.deepcopy(self.state)

        _state = self.aocs.update(_state, ts)
        _state = self.ttc.update(_state, ts, gs_state)
        _state = self.eps.update(_state, ts)
        _state = self.dhs.update(_state, ts)
        _state = self.payload.update(_state, ts)

        # frame quality/checks are ground station concepts, mirrored onto the spacecraft state for display
        if gs_state is not None:
            _state.frame_quality = gs_state.frame_quality
            _state.frame_checks = gs_state.frame_checks
            _state.ov_no_tm = gs_state.ov_no_tm

        # apply direct overrides after the subsystem chain so they always win (values already typed by Overrides.set)
        if isinstance(overrides, dict):
            # restore originals for overrides that have been removed
            for attr in list(self._override_prev.keys()):
                if attr not in overrides:
                    if hasattr(_state, attr):
                        setattr(_state, attr, self._override_prev[attr])
                    del self._override_prev[attr]

            # apply active overrides, capturing the pre-override value once
            for attr, value in overrides.items():
                if hasattr(_state, attr):
                    if attr not in self._override_prev:
                        self._override_prev[attr] = getattr(_state, attr)
                    setattr(_state, attr, value)

        _state.ts = ts

        with self._lock:
            self.state = _state

        return self.state

    def update_state(self, data:dict) -> SpacecraftState:
        with self._lock:
            for k, v in data.items():
                setattr(self.state, k, v)

        return self.state

    def seed_ts(self, begin_iso: str) -> None:
        """Reset the per-tick delta baseline to a breakpoint's begin; call on every breakpoint jump."""
        with self._lock:
            self.state.ts = datetime.fromisoformat(begin_iso).timestamp()

    def apply_fixed_updates(self) -> SpacecraftState:
        """Apply deterministic rules to the state a breakpoint starts from.

        Called before the simulation loop starts and after every breakpoint change, so the
        initial state is consistent regardless of which initial states or overrides were
        applied. Not re-applied on later ticks: safe mode entered during a pass (FDIR, a TC)
        leaves the transmitters as they were, and operators may switch them back on. Add
        fixed, rule-based corrections here.
        """
        with self._lock:
            # in safe mode both transmitters are off; the receivers stay on so the spacecraft can still be commanded
            if self.state.dhs_obsw_mode == Status.safe:
                self.state.ttc_s_tx_status = Status.off
                self.state.ttc_x_tx_status = Status.off

        return self.state

    def control(self, params:dict, gs_sim=None) -> dict:
        """Handle a spacecraft control command ('control', 'value') from the API; returns a dict with 'status'."""

        control_name = params.get('control')
        value = params.get('value')
        logger.info(f"Spacecraft.control: {control_name}={value}")

        # Default response
        response = { 'status': 'g:REL g:ACC g:EXE' }

        if not control_name:
            logger.error("Spacecraft control error: missing control name")
            return {'status': 'g:REL g:ACC r:EXE'}

        if control_name == 'trigger_safe_mode':
            system_name = 'dhs'
        else:
            system_name = control_name.split('_')[0]

        try:
            with self._lock:
                message = BusMessage(
                    source="spacecraft",
                    destination=system_name,
                    payload={ "command": control_name, "value": value }
                )
                result = self.bus.send(self.state, message)
                if result is True:
                    # command executes, but ACC/EXE can't be confirmed without GS frame lock (no TM to check)
                    if gs_sim is not None and gs_sim.state.status_dl != TTCState.FRAME_LOCK:
                        response = { 'status': 'g:REL u:ACC u:EXE' }
                    else:
                        response = { 'status': 'g:REL g:ACC g:EXE' }
                else:
                    response = { 'status': 'g:REL g:ACC r:EXE' }

        except Exception as e:
            logger.error(f"Spacecraft control error: {control_name} = {value}: {e}")
            response = {'status': 'g:REL g:ACC r:EXE'}

        logger.info(f"Spacecraft.control response: {response}")
        return response
