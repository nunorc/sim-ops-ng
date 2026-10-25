
import os
import json
import dataclasses
import math
import re
import types
import typing
import threading
import logging
import uuid
import simpy.rt
import urllib3

from enum import Enum
from queue import Queue, Empty, Full
from minio import Minio
from io import BytesIO
from datetime import datetime, timezone

from .data_model import (
    Scenario, GroundStation, GroundStationState, SpacecraftState, Status, TTCModes, AOCSTarget, Breakpoint,
    TTCAntenna, TTCState, DataProxy
)
from .spacecraft import SpacecraftSim
from .utils import SpacePacketHandler
from .ground_station import GroundStationSim
from .communication import SocketServer
from .sys._common import finite_float, tle_lines

logger = logging.getLogger(__name__)

def _enum_field_types(*state_classes: type) -> dict[str, tuple[type[Enum], bool]]:
    """Map state field name -> (Enum subclass, is_list) for every enum or list-of-enum field, from the type hints."""
    fields = {}
    for cls in state_classes:
        for name, hint in typing.get_type_hints(cls).items():
            is_list = typing.get_origin(hint) is list
            elem_hint = typing.get_args(hint)[0] if is_list and typing.get_args(hint) else hint
            if isinstance(elem_hint, type) and issubclass(elem_hint, Enum):
                fields[name] = (elem_hint, is_list)
    return fields

# field name -> (Enum type, is_list); built once from the dataclass definitions themselves
_STATE_ENUM_FIELDS = _enum_field_types(SpacecraftState, GroundStationState)
_SC_ENUM_FIELDS = _enum_field_types(SpacecraftState)
_GS_ENUM_FIELDS = _enum_field_types(GroundStationState)

def _enum_member(enum_type: type[Enum], name: str, key: str) -> Enum:
    try:
        return enum_type[name]
    except KeyError:
        raise ValueError(f"{key} must be one of {[m.name for m in enum_type]}, got {name!r}") from None

def _coerce_enum_fields(state: dict, enum_fields: dict) -> dict:
    """Convert enum-typed fields in a scenario state dict from name(s) to Enum members, in place."""
    for key, (enum_type, _is_list) in enum_fields.items():
        if key not in state:
            continue
        value = state[key]
        if isinstance(value, list):
            state[key] = [_enum_member(enum_type, v, key) if isinstance(v, str) else v for v in value]
        elif isinstance(value, str):
            state[key] = _enum_member(enum_type, value, key)
    return state

def _initial_state(curr: dict, key: str, state_class: type, enum_fields: dict) -> dict:
    """A breakpoint's sc/gs_initial_state with enums coerced; ValueError on a field the state doesn't have."""
    state = curr.get(key, {})
    if not isinstance(state, dict):
        raise ValueError(f"Breakpoint {curr['name']!r} {key} must be an object, got {state!r}")
    unknown = sorted(set(state) - {f.name for f in dataclasses.fields(state_class)})
    if unknown:
        # update_state() would setattr these silently, so a typo would never take effect
        raise ValueError(f"Breakpoint {curr['name']!r} {key} has unknown fields: {', '.join(unknown)}")
    return _coerce_enum_fields(state, enum_fields)

def _require_keys(obj: dict, keys: tuple, where: str) -> None:
    missing = [k for k in keys if k not in obj]
    if missing:
        raise ValueError(f"{where} is missing {', '.join(missing)}")

def _tle_checksum(line: str) -> int:
    """TLE line checksum: sum of the digits in the first 68 columns, each '-' counting 1, modulo 10."""
    return sum(int(c) if c.isdigit() else int(c == '-') for c in line[:68]) % 10

def _check_tle(tle) -> None:
    """Raise ValueError unless `tle` is a valid three-line element set (Skyfield accepts garbage silently)."""
    if not isinstance(tle, str):
        raise ValueError(f"tle must be a string, got {tle!r}")
    lines = tle_lines(tle)  # the same split AOCS/GroundStationSim use
    if len(lines) != 3:
        raise ValueError(f"tle must have 3 lines (name and two element lines), got {len(lines)}")
    for number, line in enumerate(lines[1:], start=1):
        if len(line) != 69 or not line.startswith(f"{number} "):
            raise ValueError(f"tle line {number} must be 69 characters starting with '{number} ', got {line!r}")
        if not line[68].isdigit() or int(line[68]) != _tle_checksum(line):
            raise ValueError(f"tle line {number} has a bad checksum: {line!r}")
    if lines[1][2:7] != lines[2][2:7]:
        raise ValueError(f"tle element lines name different satellites: {lines[1][2:7]!r}, {lines[2][2:7]!r}")

# the name is used in the MinIO buckets sim-<name>-tm/-tc: S3 names are 3-63 chars of a-z, 0-9, '.', '-',
# starting and ending with a letter or digit, with no '..', '.-' or '-.'
_BUCKET_NAME_RE = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")

def _check_scenario_name(name) -> None:
    """Raise ValueError unless `name` makes valid S3 bucket names (make_bucket would fail on every write)."""
    bucket = f"sim-{name}-tm"  # -tc is the same length
    if (not isinstance(name, str) or not name or not _BUCKET_NAME_RE.fullmatch(bucket)
            or any(s in bucket for s in ('..', '.-', '-.'))):
        raise ValueError(f"scenario name must be 1-56 lowercase letters, digits, '-' or '.' "
                         f"('.' not at either end, next to '-' or doubled), got {name!r}")

# load scenario from file
def load_scenario(filename:str) -> Scenario:
    """Load a scenario JSON file; FileNotFoundError if missing, ValueError if it is invalid (e.g. no breakpoints)."""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Scenario file not found: {filename}")

    with open(filename, 'r', encoding='utf-8') as fin:
        data = json.load(fin)

    if not isinstance(data, dict):
        raise ValueError(f"Scenario must be a JSON object: {filename}")
    _require_keys(data, ("name", "tle"), f"Scenario {filename}")

    breakpoints = []
    names = set()
    for curr in data.get("breakpoints") or []:
        if not isinstance(curr, dict):
            raise ValueError(f"Breakpoint must be an object, got {curr!r}: {filename}")
        _require_keys(curr, ("name", "begin", "end"), f"Breakpoint {curr.get('name')!r}")
        # breakpoints are looked up by name (step_loop, move_to_next/previous_breakpoint)
        if curr["name"] in names:
            raise ValueError(f"Duplicate breakpoint name {curr['name']!r}: {filename}")
        names.add(curr["name"])

        # checked now, not when the breakpoint is entered after the running sim was stopped to load this scenario
        if "ground_station" not in curr:
            raise ValueError(f"Breakpoint {curr['name']!r} has no ground_station: {filename}")
        gs = GroundStation(**curr["ground_station"])
        times = {}
        for key in ("begin", "end"):
            try:
                times[key] = datetime.fromisoformat(curr[key])
            except (TypeError, ValueError):
                raise ValueError(
                    f"Breakpoint {curr['name']!r} {key} must be an ISO timestamp, got {curr[key]!r}"
                ) from None
            # a naive timestamp would be read as the host's local time by .timestamp()
            if times[key].tzinfo is None:
                raise ValueError(
                    f"Breakpoint {curr['name']!r} {key} must have a timezone (e.g. '+00:00'), got {curr[key]!r}"
                )
        if not times["begin"] < times["end"]:
            raise ValueError(
                f"Breakpoint {curr['name']!r} begin must be before end, got {curr['begin']} >= {curr['end']}"
            )

        b = Breakpoint(
            name=curr["name"],
            begin=curr["begin"],
            end=curr["end"],
            ground_station=gs,
            gs_initial_state=_initial_state(curr, "gs_initial_state", GroundStationState, _GS_ENUM_FIELDS),
            sc_initial_state=_initial_state(curr, "sc_initial_state", SpacecraftState, _SC_ENUM_FIELDS)
        )
        breakpoints.append(b)

    if not breakpoints:
        raise ValueError(f"Scenario has no breakpoints: {filename}")

    # checked here: a bad value would otherwise only surface as a crash on the first tick
    tm_packet_frequency = data.get("tm_packet_frequency", 30)
    if isinstance(tm_packet_frequency, bool) or not isinstance(tm_packet_frequency, int) or tm_packet_frequency < 1:
        raise ValueError(f"tm_packet_frequency must be a positive integer (seconds), got {tm_packet_frequency!r}")
    time_factor = data.get("time_factor", 1.0)
    if (isinstance(time_factor, bool) or not isinstance(time_factor, (int, float))
            or not math.isfinite(time_factor) or time_factor <= 0):
        raise ValueError(f"time_factor must be a positive number, got {time_factor!r}")
    _check_scenario_name(data["name"])
    _check_tle(data["tle"])

    scenario = Scenario(
        name=data["name"],
        tle=data["tle"],
        breakpoints=breakpoints,
        tm_packet_frequency=tm_packet_frequency,
        time_factor=float(time_factor),
    )

    return scenario

# high priority commands -- only ones processed with TTC MCU in error
HPTC = ['TC_TTC_001', 'TC_TTC_002', 'TC_TTC_003', 'TC_TTC_004', 'TC_TTC_005', 'TC_TTC_006', 'TC_TTC_007', 'TC_TTC_008',
        'TC_TTC_011', 'TC_TTC_012', 'TC_TTC_021', 'TC_TTC_022', 'TC_TTC_023',
        'TC_TTC_041', 'TC_TTC_051', 'TC_TTC_052', 'TC_TTC_053', 'TC_TTC_054',
        'TC_TTC_061', 'TC_TTC_062',
        'TC_EPS_041', 'TC_EPS_042', 'TC_EPS_043', 'TC_EPS_044',
        # TTC transmitter/receiver power on/off, one pair per unit
        'TC_EPS_051', 'TC_EPS_052', 'TC_EPS_053', 'TC_EPS_054',
        'TC_EPS_055', 'TC_EPS_056', 'TC_EPS_057', 'TC_EPS_058']

# localhost for manual dev; docker-compose.yml sets the container hostname
SIM_OPS_NG_MINIO_ENDPOINT = os.getenv('SIM_OPS_NG_MINIO_ENDPOINT', 'localhost:9000')
if not SIM_OPS_NG_MINIO_ENDPOINT:
    SIM_OPS_NG_MINIO_ENDPOINT = 'localhost:9000'
SIM_OPS_NG_MINIO_ROOT_USER = os.getenv('SIM_OPS_NG_MINIO_ROOT_USER', 'myusername')
if not SIM_OPS_NG_MINIO_ROOT_USER:
    SIM_OPS_NG_MINIO_ROOT_USER = 'myusername'
SIM_OPS_NG_MINIO_ROOT_PASSWORD = os.getenv('SIM_OPS_NG_MINIO_ROOT_PASSWORD', 'mypassword')
if not SIM_OPS_NG_MINIO_ROOT_PASSWORD:
    SIM_OPS_NG_MINIO_ROOT_PASSWORD = 'mypassword'

# max wait for the sim thread; shorter than the API's 5 s SocketClient timeout, so the sim gives up first
SEND_CMD_TIMEOUT = 4.0
# wall-clock seconds between two checks of the command queue while the loop sleeps
CMD_POLL_S = 0.1

class ObjectStore:
    def __init__(self,
                 endpoint=SIM_OPS_NG_MINIO_ENDPOINT,
                 access_key=SIM_OPS_NG_MINIO_ROOT_USER,
                 secret_key=SIM_OPS_NG_MINIO_ROOT_PASSWORD):
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key

        # Minio() doesn't connect on construction and retries with backoff when down: fail fast instead
        http_client = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=2.0, read=5.0),
            retries=urllib3.Retry(total=0),
        )
        self.client = Minio(self.endpoint, access_key=self.access_key, secret_key=self.secret_key, secure=False,
                            http_client=http_client)
        self._buckets: set[str] = set()

    def probe(self) -> bool:
        """True if the object store is reachable (and the credentials work)."""
        try:
            self.client.list_buckets()
            return True
        except Exception as e:
            logger.warning("ObjectStore %s unreachable: %s", self.endpoint, e)
            return False

    # store space packet tm
    def store(self, bucket, packet_id, byte_stream):
        # create bucket if does not exist
        if bucket not in self._buckets:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
            self._buckets.add(bucket)

        data = BytesIO(byte_stream)

        self.client.put_object(bucket_name=bucket, object_name=packet_id, data=data, length=len(byte_stream))

    def get_objects_tm(self):
        buckets = [x.name for x in self.client.list_buckets()]

        data = []
        for bucket in buckets:
            if bucket.startswith('sim-') and (bucket.endswith('-tm') or bucket.endswith('-tc')):
                objects = self.client.list_objects(bucket)
                data.append({ 'bucket': bucket, 'data': [x.object_name for x in objects] })

        return data

    # retrieve objects with flight dynamics products
    def get_objects_fd(self):
        if not self.client.bucket_exists('flight-dynamics'):
            return []

        objects = self.client.list_objects('flight-dynamics')

        data = [self.get('flight-dynamics', obj.object_name, is_json=True) for obj in objects]
        data.reverse()

        return data

    def get(self, bucket, object_name, is_json=False):
        response = self.client.get_object(bucket, object_name)
        # an unreleased response keeps its pooled connection: the pool runs dry after a few requests
        try:
            return response.json() if is_json else response.read()
        finally:
            response.close()
            response.release_conn()

class BackgroundObjectStore:
    """Queues `store()` calls for a worker thread, so object-store latency and outages never reach the sim thread."""

    def __init__(self, object_store: ObjectStore, max_pending: int = 1000):
        self._object_store = object_store
        self._queue: Queue = Queue(maxsize=max_pending)
        self._failing = False
        self._thread = threading.Thread(target=self._run, name="object-store-writer", daemon=True)
        self._thread.start()

    def store(self, bucket, object_name, byte_stream):
        try:
            self._queue.put_nowait((bucket, object_name, byte_stream))
        except Full:
            logger.debug("ObjectStore write queue full, dropping %s/%s", bucket, object_name)

    def _run(self):
        while True:
            bucket, object_name, byte_stream = self._queue.get()
            try:
                self._object_store.store(bucket, object_name, byte_stream)
                if self._failing:
                    logger.info("ObjectStore writes succeeding again")
                    self._failing = False
            except Exception as e:
                if not self._failing:
                    logger.warning("ObjectStore write failed, dropping objects until it recovers: %s", e)
                    self._failing = True
                else:
                    logger.debug("ObjectStore write failed for %s/%s: %s", bucket, object_name, e)

class Products:
    """Creates and stores object-store products once at the end of a pass; :meth:`reset` on each new breakpoint."""

    def __init__(self, object_store: ObjectStore | BackgroundObjectStore):
        self._object_store = object_store
        self._fd_created = False

    def reset(self):
        """Call when the active breakpoint changes so products can be re-created."""
        self._fd_created = False

    def try_create_fd(self, now: float, bp, gs_state, force: bool = False) -> dict | None:
        """Write a flight-dynamics product once the pass end is reached (or now, with `force`); the data or None."""
        if self._fd_created:
            return None

        end_ts = datetime.fromisoformat(bp.end).timestamp()
        if not force and now < end_ts:
            return None

        self._fd_created = True

        fd = gs_state.flight_dynamics or []
        _ranging = any(row[3] for row in fd)   # index 3: distance (km), non-zero when ranging active
        _doppler = any(row[4] for row in fd)   # index 4: doppler velocity (km/s), non-zero when doppler active

        if _doppler and _ranging:
            validity = 2
        elif _doppler or _ranging:
            validity = 1
        else:
            validity = 0

        sim_uid = f"{bp.name}-{int(end_ts)}"
        data = {
            'id': sim_uid,
            'status': 2,
            'validity': validity,
            'data': fd,
        }
        self._object_store.store('flight-dynamics', sim_uid, json.dumps(data).encode())
        logger.info("Flight dynamics product stored: %s (validity=%d)", sim_uid, validity)

        return data


def _scalar_field_types(state_class: type) -> dict[str, type]:
    """Map field name -> bool/int/float/str for the plain scalar fields (Optional unwrapped)."""
    fields = {}
    for name, hint in typing.get_type_hints(state_class).items():
        args = [a for a in typing.get_args(hint) if a is not types.NoneType]
        if typing.get_origin(hint) in (typing.Union, types.UnionType) and len(args) == 1:
            hint = args[0]
        if hint in (bool, int, float, str):
            fields[name] = hint
    return fields

# spacecraft overrides are applied onto SpacecraftState fields by name
_SC_SCALAR_FIELDS = _scalar_field_types(SpacecraftState)

_TRUE_VALUES = ('1', 'true', 'on', 'yes', 'enabled')
_FALSE_VALUES = ('0', 'false', 'off', 'no', 'disabled', '')

def _parse_bool(value) -> bool:
    text = str(value).strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    raise ValueError(f"expected a boolean, got {value!r}")

def _parse_number(kind: type, value):
    number = kind(value)
    if not math.isfinite(number):
        raise ValueError(f"expected a finite number, got {value!r}")
    return number

# overrides applied by GroundStationSim.update(); every other override is a spacecraft one
GS_OVERRIDE_FIELDS = frozenset({
    'status_dl', 'max_status_dl', 'max_c_no_dl', 'max_eb_no_dl', 'no_tm', 'no_tc', 'frame_quality'
})

class Overrides:
    """Converts override values to their state field's type; ValueError for an unknown override or bad value."""
    # override parameter names that alias a differently-named state field
    _ALIASES = {'max_status_dl': 'status_dl'}

    def set(self, parameter, value):
        if parameter in ('max_c_no_dl', 'max_eb_no_dl'):
            return _parse_number(float, value)
        if parameter in ('no_tm', 'no_tc'):
            return _parse_bool(value)

        # convert to enum if the field is enum-typed; GS overrides map to GroundStationState, the rest SpacecraftState
        field = self._ALIASES.get(parameter, parameter)
        enum_fields = _GS_ENUM_FIELDS if parameter in GS_OVERRIDE_FIELDS else _SC_ENUM_FIELDS
        entry = enum_fields.get(field)
        if entry is not None:
            enum_type, is_list = entry
            try:
                converted = enum_type[value]
            except (KeyError, TypeError):
                valid = ', '.join(enum_type.__members__)
                raise ValueError(f"invalid value {value!r} for {parameter}, expected one of: {valid}") from None
            # a list-typed field (e.g. eps_sol_array) takes one value for all elements
            return [converted] * 2 if is_list else converted

        kind = _SC_SCALAR_FIELDS.get(field)
        if kind is None:
            raise ValueError(f"unknown override: {parameter}")
        if kind is bool:
            return _parse_bool(value)
        if kind in (int, float):
            try:
                return _parse_number(kind, value)
            except (TypeError, ValueError):
                raise ValueError(f"invalid value {value!r} for {parameter}, expected a number") from None
        return str(value)

def override_display(value):
    """Render an override value for the admin UI: enums by name, lists element-wise."""
    if isinstance(value, list):
        return ', '.join(override_display(x) for x in value)
    return value.name if hasattr(value, 'name') else str(value)

class SimOps:
    def __init__(self,
        scenario: Scenario | str,
        spacecraft: SpacecraftSim | None = None,
        ground_station: GroundStationSim | None = None,
        time_step=1.0,
        time_factor: float | None = None
    ) -> None:
        if isinstance(scenario, str):
            self.scenario = load_scenario(scenario)
        else:
            self.scenario = scenario
        self.breakpoint = self.scenario.breakpoints[0]

        # real-time scaling factor (1.0 = real time, >1 slower, <1 faster); the constructor arg overrides the scenario
        self.time_factor = time_factor if time_factor is not None else self.scenario.time_factor

        if spacecraft:
            self.spacecraft = spacecraft
        else:
            self.spacecraft = SpacecraftSim(scenario=self.scenario)

        if ground_station:
            self.ground_station = ground_station
        else:
            self.ground_station = GroundStationSim(scenario=self.scenario, bp=self.breakpoint)

        # sim loop
        self._running = False
        self._paused = False
        self._thread = None
        # bumped on every start; a sim thread only runs while its run id is current, so a stale one can't run alongside
        self._run_id = 0
        self._lock = threading.Lock()
        # socket handlers run concurrently; lifecycle/admin ones check _running then act, so they serialise on this lock
        self._admin_lock = threading.RLock()
        # set when the sim loop crashes on an unexpected exception; cleared on start
        self._last_error: str | None = None
        # offset applied to env.now for the simulated timestamp, to jump to a breakpoint without restarting the env
        self._ts_offset = 0.0

        # Socket server for communication with API
        socket_host = os.getenv("SIM_OPS_NG_SOCKET_HOST", "127.0.0.1")
        socket_port = int(os.getenv("SIM_OPS_NG_SOCKET_PORT", "5555"))
        self._socket_server = SocketServer(host=socket_host, port=socket_port)
        self._setup_socket_handlers()
        self._socket_server.start()

        # unified command queue: external commands execute in the SimPy thread, so state needs no locking
        self._command_queue: Queue = Queue()

        self.time_step = time_step
        self.sc_overrides = {}
        self.gs_overrides = {}
        self.data_proxy: DataProxy = DataProxy.SLE

        # TC stack shared across all clients; protected by _tc_lock
        self.tc_stack: list[dict] = []    # [{command, system, control, value}, ...]
        self.tc_history: list[dict] = []  # [{command, status, ts}, ...]
        self._tc_lock = threading.Lock()

        self._sp_handler = SpacePacketHandler()
        # writes go via a background thread so the sim never waits on MinIO, which may come up after the sim
        self._object_store: BackgroundObjectStore | None
        try:
            store = ObjectStore()
            if store.probe():
                logger.info("ObjectStore connected: %s", SIM_OPS_NG_MINIO_ENDPOINT)
            else:
                logger.warning("ObjectStore unavailable, TM/TC packets and products are not stored until it is up")
            self._object_store = BackgroundObjectStore(store)
        except Exception as e:
            self._object_store = None
            logger.warning("ObjectStore disabled, TM packets will not be stored: %s", e)

        self.products = Products(self._object_store) if self._object_store else None

        # push a snapshot to any client that (re)connects; registered last, once _broadcast_state()'s attributes are set
        self._socket_server.set_on_subscribe(self._broadcast_state)

    # ---- Socket handler registration ----

    def _serialized(self, handler):
        def run(params: dict) -> dict:
            with self._admin_lock:
                return handler(params)
        return run

    def _setup_socket_handlers(self):
        self._socket_server.register_handler('start', self._serialized(self._handle_start_command))
        self._socket_server.register_handler('stop', self._serialized(self._handle_stop_command))
        self._socket_server.register_handler('pause', self._serialized(self._handle_pause_command))
        self._socket_server.register_handler('resume', self._serialized(self._handle_resume_command))
        self._socket_server.register_handler('step', self._serialized(self._handle_step_command))
        self._socket_server.register_handler('next_breakpoint', self._serialized(self._handle_next_breakpoint_command))
        self._socket_server.register_handler(
            'previous_breakpoint', self._serialized(self._handle_previous_breakpoint_command))
        self._socket_server.register_handler('get_scenario', self._handle_get_scenario_command)
        self._socket_server.register_handler('control', self._handle_control_command)
        self._socket_server.register_handler('tc_stack_push', self._handle_tc_stack_push)
        self._socket_server.register_handler('tc_stack_delete', self._handle_tc_stack_delete)
        self._socket_server.register_handler('tc_stack_execute', self._handle_tc_stack_execute)
        self._socket_server.register_handler('tc_send', self._handle_tc_send)
        self._socket_server.register_handler('get_overrides', self._handle_get_overrides)
        self._socket_server.register_handler('set_override', self._serialized(self._handle_set_override))
        self._socket_server.register_handler('unset_override', self._serialized(self._handle_unset_override))
        self._socket_server.register_handler('admin_set_state', self._serialized(self._handle_admin_set_state))
        self._socket_server.register_handler('set_data_proxy', self._serialized(self._handle_set_data_proxy))
        self._socket_server.register_handler('load_scenario', self._serialized(self._handle_load_scenario))

    # ---- Socket handlers ----

    def _handle_start_command(self, params: dict) -> dict:
        bp = params.get('breakpoint', 0)
        if self._running:
            return {'success': False, 'status': 'already_running', 'error': 'Simulation is already running'}
        try:
            self.start_loop(bp=bp)
        except ValueError as e:
            return {'success': False, 'error': str(e)}
        return {'success': True, 'status': 'started'}

    def _handle_stop_command(self, _params: dict) -> dict:
        self.stop_loop()
        return {'status': 'stopped'}

    def _handle_pause_command(self, _params: dict) -> dict:
        self.pause_loop()
        return {'status': 'paused'}

    def _handle_resume_command(self, _params: dict) -> dict:
        self.resume_loop()
        return {'status': 'resumed'}

    def _handle_step_command(self, params: dict) -> dict:
        if self._running:
            # route through queue so it executes in the sim thread
            return self._send_cmd('step', params)
        # sim not running: safe to call directly
        bp = params.get('breakpoint')
        self.step_loop(bp=bp)
        return {'status': 'stepped'}

    def _handle_next_breakpoint_command(self, params: dict) -> dict:
        return self._send_cmd('next_breakpoint', params)

    def _handle_previous_breakpoint_command(self, params: dict) -> dict:
        return self._send_cmd('previous_breakpoint', params)

    def _handle_get_scenario_command(self, _params: dict) -> dict:
        return self.scenario.to_dict() if self.scenario else {}

    def _handle_load_scenario(self, params: dict) -> dict:
        """Load a new scenario JSON from the data directory, restarting the simulation loop if it was running."""
        filename = params.get('filename', '').strip()
        if not filename:
            return {'success': False, 'error': 'Filename is required'}

        data_dir = os.path.abspath('data')
        target = os.path.abspath(filename)
        if os.path.commonpath([data_dir, target]) != data_dir:
            return {'success': False, 'error': 'Invalid scenario path'}

        try:
            scenario = load_scenario(target)
            # built before stopping the current run, so a scenario failing here (e.g. bad TLE) leaves the sim untouched
            spacecraft = SpacecraftSim(scenario=scenario)
            ground_station = GroundStationSim(scenario=scenario, bp=scenario.breakpoints[0])
        except FileNotFoundError:
            return {'success': False, 'error': f'Scenario file not found: {filename}'}
        except Exception as e:
            return {'success': False, 'error': f'Invalid scenario {filename}: {e}'}

        was_running = self._running
        if was_running:
            self.stop_loop()

        self.scenario = scenario
        self.time_factor = scenario.time_factor
        self.breakpoint = self.scenario.breakpoints[0]
        self.spacecraft = spacecraft
        self.ground_station = ground_station
        self.sc_overrides = {}
        self.gs_overrides = {}
        self._ts_offset = 0.0
        with self._tc_lock:
            self.tc_stack = []
            self.tc_history = []

        self.step_loop()

        if was_running:
            self.start_loop()
        else:
            self._broadcast_state()

        logger.info(f"Loaded scenario: {filename}")
        return {'success': True, 'scenario': self.scenario.to_dict()}

    def _handle_admin_set_state(self, params: dict) -> dict:
        # Must run in the sim thread: Spacecraft.update deep-copies the state
        if not self._running:
            return self._do_admin_set_state(params)
        return self._send_cmd('admin_set_state', params)

    def _do_admin_set_state(self, params: dict) -> dict:
        """Directly set a SpacecraftState attribute, bypassing subsystem command handlers and RF checks."""
        attr = params.get('attr', '').strip()
        value = params.get('value')

        _coerce = {
            'aocs_mode':      lambda v: AOCSTarget[v],
            'aocs_valid':     lambda v: Status[v],
            'ttc_mode':       lambda v: TTCModes[v],
            'ttc_s_antenna':  lambda v: TTCAntenna[v],
            'ttc_x_antenna':  lambda v: TTCAntenna[v],
            'ttc_mcu':        lambda v: Status[v],
            'ttc_s_tx_status': lambda v: Status[v],
            'ttc_s_rx_status': lambda v: Status[v],
            'ttc_x_tx_status': lambda v: Status[v],
            'ttc_x_rx_status': lambda v: Status[v],
            'dhs_obsw_mode':  lambda v: Status[v],
            'dhs_memory':     lambda v: max(0.0, min(100.0, finite_float(v))),
            'eps_battery_dod': lambda v: max(0.0, min(100.0, finite_float(v))),
            'eps_acu':        lambda v: Status[v],
            'eps_pdu':        lambda v: Status[v],
        }

        if attr not in _coerce:
            return {'success': False, 'error': f'Unknown attribute: {attr}'}

        try:
            setattr(self.spacecraft.state, attr, _coerce[attr](value))
            logger.info(f"Admin set state: {attr} = {value}")
            return {'success': True}
        except (KeyError, ValueError) as e:
            return {'success': False, 'error': str(e)}

    def _handle_set_data_proxy(self, params: dict) -> dict:
        mode = params.get('mode', '').upper().strip()
        try:
            self.data_proxy = DataProxy[mode]
            logger.info(f"Data proxy mode set to: {self.data_proxy.name}")
            # push the new state now so the UI reflects it even while the sim loop is stopped
            self._broadcast_state()
            return {'success': True, 'mode': self.data_proxy.name}
        except KeyError:
            return {'success': False, 'error': f'Unknown mode: {mode}. Valid: EGSE, SLE'}

    def _handle_control_command(self, params: dict) -> dict:
        logger.info(f"Control command: system={params.get('system')}, "
                    f"control={params.get('control')}, value={params.get('value')}")
        result = self._send_cmd('control', params)
        logger.info(f"Control response: {result}")
        return result

    @staticmethod
    def _tc_entry(params: dict) -> dict:
        return {
            'command': params.get('command', ''),
            'system': params.get('system', 'spacecraft'),
            'control': params.get('control', ''),
            'value': params.get('value', '')
        }

    def _handle_tc_stack_push(self, params: dict) -> dict:
        with self._tc_lock:
            if len(self.tc_stack) >= 5:
                return {'success': False, 'error': 'Stack full (max 5)'}
            self.tc_stack.append(self._tc_entry(params))
        return {'success': True}

    def _handle_tc_stack_delete(self, params: dict) -> dict:
        index = params.get('index', 0)
        with self._tc_lock:
            if not isinstance(index, int) or not 0 <= index < len(self.tc_stack):
                return {'success': False, 'error': f'No TC at index {index} (stack has {len(self.tc_stack)})'}
            self.tc_stack.pop(index)
        return {'success': True}

    def _handle_tc_stack_execute(self, params: dict) -> dict:
        return self._send_cmd('tc_execute', params)

    def _handle_tc_send(self, params: dict) -> dict:
        # executes the given TC, not the stack head: the stack may hold other TCs loaded by anyone
        return self._send_cmd('tc_send', params)

    def _handle_get_overrides(self, _params: dict) -> dict:
        combined = {**self.sc_overrides, **self.gs_overrides}
        overrides = [[k, override_display(v)] for k, v in combined.items()]
        return {'overrides': overrides}

    # Onboard FDIR-triggered controls: not ground TCs, so they must execute regardless of link status
    _LINK_INDEPENDENT_CONTROLS = {'trigger_safe_mode'}

    def _handle_set_override(self, params: dict) -> dict:
        # must run in the sim thread: SpacecraftSim.update() iterates sc_overrides/gs_overrides unlocked on every tick
        if not self._running:
            return self._do_set_override(params)
        return self._send_cmd('set_override', params)

    def _do_set_override(self, params: dict) -> dict:
        attr = params.get('attr', '').strip()
        value = params.get('value', '')
        if not attr:
            raise ValueError('Attribute name required')
        # raises ValueError for an unknown attribute or bad value, rather than store one that breaks the next tick
        converted = Overrides().set(attr, value)
        if attr in GS_OVERRIDE_FIELDS:
            self.gs_overrides[attr] = converted
        else:
            self.sc_overrides[attr] = converted
        display = override_display(converted)
        return {'attr': attr, 'value': display}

    def _handle_unset_override(self, params: dict) -> dict:
        # Must run in the sim thread: see _handle_set_override.
        if not self._running:
            return self._do_unset_override(params)
        return self._send_cmd('unset_override', params)

    def _do_unset_override(self, params: dict) -> dict:
        attr = params.get('attr', '').strip()
        if not attr:
            raise ValueError('Attribute name required')
        self.sc_overrides.pop(attr, None)
        self.gs_overrides.pop(attr, None)
        return {'attr': attr}

    # ---- Command queue: bridge from socket-handler threads into the sim thread ----

    @staticmethod
    def _claim_cmd(cmd: dict, state: str) -> bool:
        """Claim a queued command as 'running' or 'cancelled'; False if it was already claimed."""
        lock = cmd.get('lock')
        if lock is None:
            return True
        with lock:
            if cmd['state'] != 'queued':
                return False
            cmd['state'] = state
            return True

    def _send_cmd(self, action: str, params: dict | None = None, timeout: float = SEND_CMD_TIMEOUT) -> dict:
        """Put a command on the queue and block until the sim thread executes it."""
        if not self._running:
            return {'success': False, 'error': 'Simulation is not running'}
        event = threading.Event()
        cmd = {'action': action, 'params': params or {}, 'event': event, 'result': None,
               'lock': threading.Lock(), 'state': 'queued'}
        self._command_queue.put(cmd)
        if event.wait(timeout=timeout):
            return cmd['result']
        if self._claim_cmd(cmd, 'cancelled'):
            return {'success': False, 'error': 'Command timed out'}
        # the sim thread started it just now: it runs to completion, so report its outcome
        event.wait()
        return cmd['result']

    def _dispatch_cmd(self, cmd: dict, env: simpy.rt.RealtimeEnvironment, now: float | None = None) -> None:
        """Execute one queued command in the sim thread; breakpoint jumps are relative to `now` (default env.now)."""
        if not self._claim_cmd(cmd, 'running'):
            return  # its caller timed out and was told so
        if now is None:
            now = env.now
        action = cmd['action']
        params = cmd['params']
        result = {'success': False, 'error': f'Unknown action: {action}'}

        try:
            if action == 'control':
                result = self._do_control(params)

            elif action == 'tc_execute':
                result = self._do_tc_execute()

            elif action == 'tc_send':
                result = self._do_tc_execute(self._tc_entry(params))

            elif action == 'admin_set_state':
                result = self._do_admin_set_state(params)

            elif action == 'set_override':
                result = self._do_set_override(params)

            elif action == 'unset_override':
                result = self._do_unset_override(params)

            elif action == 'next_breakpoint':
                restart = params.get('restart', False)
                if self.products is not None and self.data_proxy == DataProxy.SLE:
                    # a failed product must not block moving on
                    try:
                        ts = now + self._ts_offset
                        self.products.try_create_fd(ts, self.breakpoint, self.ground_station.state, force=True)
                    except Exception:
                        logger.exception("Failed to create flight dynamics product")
                if self.move_to_next_breakpoint(restart=restart):
                    # ts jumps to the new breakpoint's begin time on the next tick
                    self._ts_offset = datetime.fromisoformat(self.breakpoint.begin).timestamp() - now
                    result = {'success': True, 'status': 'moved_to_next_breakpoint',
                              'breakpoint': self.breakpoint.to_dict()}
                else:
                    result = {'success': False, 'status': 'no_next_breakpoint',
                              'breakpoint': self.breakpoint.to_dict()}

            elif action == 'previous_breakpoint':
                if self.move_to_previous_breakpoint():
                    # ts jumps to the new breakpoint's begin time on the next tick
                    self._ts_offset = datetime.fromisoformat(self.breakpoint.begin).timestamp() - now
                    result = {'success': True, 'status': 'moved_to_previous_breakpoint',
                              'breakpoint': self.breakpoint.to_dict()}
                else:
                    result = {'success': False, 'status': 'no_previous_breakpoint',
                              'breakpoint': self.breakpoint.to_dict()}

            elif action == 'step':
                bp = params.get('breakpoint')
                self.step_loop(bp=bp)
                # ts jumps to the selected breakpoint's begin time on the next tick
                self._ts_offset = datetime.fromisoformat(self.breakpoint.begin).timestamp() - now
                result = {'success': True}

        except Exception as e:
            result = {'success': False, 'error': str(e)}

        cmd['result'] = result
        event = cmd.get('event')
        if event is not None:
            event.set()

    def _flush_command_queue(self) -> None:
        """Drain the command queue, failing any waiting callers instead of leaving them to time out."""
        while True:
            try:
                cmd = self._command_queue.get_nowait()
                if not self._claim_cmd(cmd, 'cancelled'):
                    continue
                cmd['result'] = {'success': False, 'error': 'Simulation stopped or restarting'}
                event = cmd.get('event')
                if event is not None:
                    event.set()
            except Empty:
                break

    def _do_control(self, params: dict) -> dict:
        """Execute a ground-station or spacecraft control command (in the sim thread, so no lock needed)."""
        system = params.get('system')

        if not self._running:
            return {'success': False, 'status': 'r:REL r:ACC r:EXE', 'error': 'Simulation is not running'}

        if system == 'ground_station':
            result = self.ground_station.control(params)
            return {'success': True, **result}

        if system == 'spacecraft':
            result = self._control_spacecraft(params)
            # archive only what was actually uplinked: not TCs blocked on the ground, nor onboard FDIR controls
            released = str(result.get('status', '')).startswith('g:REL')
            if (self._object_store is not None and released
                    and params.get('control') not in self._LINK_INDEPENDENT_CONTROLS):
                self._store_tc_packet(params.get('control', ''), params.get('value', ''))
            return result

        return {'success': False, 'status': 'FAIL', 'error': f'Unknown system: {system}'}

    def _control_spacecraft(self, params: dict) -> dict:
        """Uplink a spacecraft TC through the link checks and return its acknowledgement."""
        if params.get('control') not in self._LINK_INDEPENDENT_CONTROLS:
            # manual TC block
            if self.gs_overrides.get('no_tc'):
                return {'success': False, 'status': 'r:REL r:ACC r:EXE'}

            carrier_on = self.ground_station.state.carrier_ul != Status.off
            sweep_ok = self.ground_station.state.sweep_done

            if self.data_proxy == DataProxy.SLE and (not carrier_on or not sweep_ok):
                return {'success': False, 'status': 'r:REL r:ACC r:EXE'}
            if self.ground_station.state.power_ul < 50:
                return {'success': False, 'status': 'g:REL r:ACC r:EXE'}

            # the command leaves the ground but the spacecraft receiver for the uplink band is off: ACC/EXE unknown
            if self.spacecraft.state.rx_status(self.ground_station.state.band_ul) != Status.on:
                return {'success': True, 'status': 'g:REL u:ACC u:EXE'}

            # link is up so the command is released, but a degraded MCU only processes HPTC commands: ACC/EXE unknown
            if self.spacecraft.state.ttc_mcu == Status.error and params.get('command') not in HPTC:
                return {'success': True, 'status': 'g:REL u:ACC u:EXE'}

        result = self.spacecraft.control(params, gs_sim=self.ground_station)
        return {'success': True, **result}

    def _do_tc_execute(self, entry: dict | None = None) -> dict:
        """Execute a TC and record the result in history: `entry` if given, else the head of the stack."""
        if entry is None:
            with self._tc_lock:
                if not self.tc_stack:
                    return {'success': False, 'error': 'Stack empty'}
                entry = self.tc_stack.pop(0)

        ctrl_result = self._do_control(entry)
        ts = datetime.now(tz=timezone.utc).isoformat()
        history_entry = {
            'command': entry.get('command', ''),
            'status': ctrl_result.get('status', 'r:REL r:ACC r:EXE'),
            'ts': ts
        }
        with self._tc_lock:
            self.tc_history.insert(0, history_entry)
            if len(self.tc_history) > 10:
                self.tc_history = self.tc_history[:10]

        # return the command actually executed: the stack is a FIFO shared across clients, so it may not be the caller's
        return {'success': True, 'status': ctrl_result.get('status'), 'command': entry.get('command', '')}

    # ---- SimPy simulation loop ----

    def _drain_commands(self, env: simpy.rt.RealtimeEnvironment, run_id: int, now: float) -> None:
        """Execute every queued command (see _dispatch_cmd for `now`)."""
        while self._is_current_run(run_id):
            try:
                cmd = self._command_queue.get_nowait()
            except Empty:
                return
            self._dispatch_cmd(cmd, env, now)

    def _sleep(self, env: simpy.rt.RealtimeEnvironment, run_id: int, frozen: bool):
        """SimPy generator: advance env time by one time_step, executing queued commands meanwhile.

        Commands are picked up about every CMD_POLL_S wall-clock seconds rather than once per
        tick, which is time_step * time_factor wall seconds and can outlast a caller's timeout.

        With `frozen` (paused) the effective timestamp env.now + _ts_offset stays where it was;
        otherwise the commands' breakpoint jumps are relative to the next tick.
        """
        start = env.now
        target = start + self.time_step
        slices = max(1, math.ceil(self.time_step * self.time_factor / CMD_POLL_S))
        for _ in range(slices - 1):
            yield env.timeout(self.time_step / slices)
            if not self._is_current_run(run_id):
                return
            self._drain_commands(env, run_id, start if frozen else target)
        # land exactly on target (start + time_step), so integer timestamps stay integer
        yield env.timeout(target - env.now)
        if frozen:
            # cancel the sim time just advanced so resuming doesn't jump ahead by the whole pause
            self._ts_offset -= self.time_step

    def _simpy_process(self, env: simpy.rt.RealtimeEnvironment, run_id: int):
        """SimPy generator: one iteration = one simulation tick."""
        while self._is_current_run(run_id):
            # drain the command queue before updating state; a command (e.g. next_breakpoint) may have stopped the sim
            self._drain_commands(env, run_id, env.now)
            if not self._is_current_run(run_id):
                break

            if self._paused:
                # once per tick, not per poll: clients sample every state message
                self._broadcast_state()
                yield from self._sleep(env, run_id, frozen=True)
                continue

            ts = env.now + self._ts_offset

            with self._lock:
                self.ground_station.update(ts, sc_state=self.spacecraft.state, overrides=self.gs_overrides)
                self.spacecraft.update(ts, gs_state=self.ground_station.state, overrides=self.sc_overrides)
                self._broadcast_state()

            if self._object_store is not None:
                freq = self.scenario.tm_packet_frequency
                if int(ts) % freq == 0:
                    self._store_tm_packet()

            if self.products is not None and self.data_proxy == DataProxy.SLE:
                try:
                    self.products.try_create_fd(ts, self.breakpoint, self.ground_station.state)
                except Exception:
                    logger.exception("Failed to create flight dynamics product")

            yield from self._sleep(env, run_id, frozen=False)

        # a stale thread must not fail the commands queued for the run that replaced it
        if self._run_id == run_id:
            self._flush_command_queue()

    def _store_tc_packet(self, command: str, value: str):
        try:
            packet = self._sp_handler.tc_packet(command=command, value=str(value))
            bucket = f"sim-{self.scenario.name}-tc"
            # several TCs can go up in one second, and breakpoint reruns repeat timestamps: a suffix avoids overwrites
            object_name = f"{int(self.spacecraft.state.ts)}-{uuid.uuid4().hex[:8]}"
            self._object_store.store(bucket, object_name, packet.as_bytes())
            logger.debug("Stored TC packet %s in bucket %s", object_name, bucket)
        except Exception as e:
            logger.warning("Failed to store TC packet: %s", e)

    def _store_tm_packet(self):
        # manual TM block: stops packet production outright, whatever the link is doing
        if self.gs_overrides.get('no_tm'):
            return
        if self.data_proxy == DataProxy.SLE and self.ground_station.state.status_dl != TTCState.FRAME_LOCK:
            return
        try:
            sc_state = self.spacecraft.state
            if sc_state.ttc_mcu == Status.error:
                sc_state = sc_state.scrub()
            packet = self._sp_handler.space_packet(sc_state)
            bucket = f"sim-{self.scenario.name}-tm"
            object_name = str(int(self.spacecraft.state.ts))
            self._object_store.store(bucket, object_name, packet.as_bytes())
            logger.debug("Stored TM packet %s in bucket %s", object_name, bucket)
        except Exception as e:
            logger.warning("Failed to store TM packet: %s", e)

    def _is_current_run(self, run_id: int) -> bool:
        return self._running and self._run_id == run_id

    def _run_simops_thread(self, run_id: int) -> None:
        """Thread target: runs the SimPy RealtimeEnvironment until stop_loop() clears _running."""
        begin_ts = datetime.fromisoformat(self.breakpoint.begin).timestamp()
        env = simpy.rt.RealtimeEnvironment(
            initial_time=begin_ts,
            factor=self.time_factor, # 1 sim-second == `time_factor` wall-clock seconds
            strict=False,            # don't raise if a tick overshoots the deadline
        )
        env.process(self._simpy_process(env, run_id))
        try:
            env.run()  # blocks until _simpy_process returns
        except Exception as e:
            if self._run_id != run_id:
                logger.exception("Stale simulation thread crashed after the loop was restarted")
                return
            # a failing tick stops the sim cleanly, so commands fail fast and clients see running=False
            logger.exception("Simulation loop crashed, stopping")
            self._last_error = f"{type(e).__name__}: {e}"
            self._running = False
            self._paused = False
            self._flush_command_queue()
            try:
                self._broadcast_state()
            except Exception:
                logger.exception("Failed to broadcast state after simulation crash")

    # ---- Lifecycle control ----

    def start_loop(self, bp: int | str | None = None):
        if self._running:
            return
        if bp is not None:
            self.step_loop(bp=bp)
        # apply the fixed rules to the starting state (e.g. safe mode -> transmitters off)
        self.spacecraft.apply_fixed_updates()
        self._last_error = None
        self._run_id += 1
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._run_simops_thread, args=(self._run_id,), daemon=True)
        self._thread.start()

    def pause_loop(self):
        if self._running and not self._paused:
            self._paused = True

    def resume_loop(self):
        if self._running and self._paused:
            self._paused = False

    def stop_loop(self):
        self._running = False
        if self._thread:
            # a tick may outlive this timeout with a large time_factor; the thread then exits on waking
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                logger.warning("Simulation thread still sleeping, it stops at the end of its tick")
            self._thread = None
        self._flush_command_queue()

        # reset everything back to the state it was in before the loop ever started
        self._paused = False
        self._ts_offset = 0.0
        self.breakpoint = self.scenario.breakpoints[0]
        self.spacecraft = SpacecraftSim(scenario=self.scenario)
        self.ground_station = GroundStationSim(scenario=self.scenario, bp=self.breakpoint)
        self.sc_overrides = {}
        self.gs_overrides = {}
        self.data_proxy = DataProxy.SLE

        with self._tc_lock:
            self.tc_stack = []
            self.tc_history = []

        if self.products:
            self.products.reset()

    def _enter_breakpoint(self) -> None:
        """Apply the (already selected) self.breakpoint to the spacecraft and ground station."""
        self.spacecraft.seed_ts(self.breakpoint.begin)
        # location and passes depend on the breakpoint's ground station and day
        self.ground_station.set_breakpoint(self.breakpoint)
        if self.breakpoint.sc_initial_state:
            self.spacecraft.update_state(self.breakpoint.sc_initial_state)
        if self.breakpoint.gs_initial_state:
            self.ground_station.update_state(self.breakpoint.gs_initial_state)
        self.spacecraft.apply_fixed_updates()

        if self.products:
            self.products.reset()

    def step_loop(self, bp: int | str | None = None):
        """Enter a breakpoint, by index or name (the first one if None). Raises ValueError if unknown."""
        self.breakpoint = self._find_breakpoint(bp)

        self._enter_breakpoint()

    def _find_breakpoint(self, bp: int | str | None) -> Breakpoint:
        breakpoints = self.scenario.breakpoints
        if bp is None:
            return breakpoints[0]
        if isinstance(bp, int):
            if 0 <= bp < len(breakpoints):
                return breakpoints[bp]
            raise ValueError(f"Breakpoint index out of range: {bp} (scenario has {len(breakpoints)})")
        for x in breakpoints:
            if x.name == bp:
                return x
        raise ValueError(f"Unknown breakpoint: {bp!r}")

    def move_to_next_breakpoint(self, restart: bool = False) -> bool:
        """Move to the next breakpoint. Returns False (no-op) if already at the last one."""
        current_index = None
        for i, bp in enumerate(self.scenario.breakpoints):
            if bp.name == self.breakpoint.name:
                current_index = i
                break
        if current_index is None:
            current_index = 0

        if not restart and current_index >= len(self.scenario.breakpoints) - 1:
            return False

        next_index = 0 if restart else current_index + 1
        self.breakpoint = self.scenario.breakpoints[next_index]

        self._enter_breakpoint()

        return True

    def move_to_previous_breakpoint(self) -> bool:
        """Move to the previous breakpoint. Returns False (no-op) if already at the first one."""
        current_index = None
        for i, bp in enumerate(self.scenario.breakpoints):
            if bp.name == self.breakpoint.name:
                current_index = i
                break
        if current_index is None:
            current_index = 0

        if current_index <= 0:
            return False

        previous_index = current_index - 1
        self.breakpoint = self.scenario.breakpoints[previous_index]

        self._enter_breakpoint()

        return True

    @property
    def socket_address(self) -> str:
        """host:port of the socket server the API connects to."""
        return f"{self._socket_server.host}:{self._socket_server.port}"

    def shutdown(self):
        self.stop_loop()
        if hasattr(self, '_socket_server'):
            self._socket_server.stop()

    # ---- State helpers ----

    def _broadcast_state(self):
        with self._tc_lock:
            tc_stack = list(self.tc_stack)
            tc_history = list(self.tc_history)

        gs_state = self.ground_station.state.to_dict()
        # tracking samples only feed the FD product; no client reads them from the state
        gs_state.pop('flight_dynamics', None)
        sc_state = self.spacecraft.state.to_dict()

        # SLE mode: users get spacecraft state only on FRAME_LOCK; spacecraft_admin always carries the full state
        status_dl = gs_state.get('status_dl', 'NO_RF')
        if self.data_proxy == DataProxy.SLE and status_dl != 'FRAME_LOCK':
            sc_state_user = None
            sle_connected = False
        else:
            sle_connected = True
            if self.spacecraft.state.ttc_mcu == Status.error:
                sc_state_user = self.spacecraft.state.scrub().to_dict()
            else:
                sc_state_user = sc_state

        state_data = {
            "type": "state",
            "ts": sc_state.get('ts'),
            "running": self._running,
            "paused": self._paused,
            "error": self._last_error,
            "data_proxy": self.data_proxy.name,
            "sle_connected": sle_connected,
            "scenario": self.scenario.to_dict(),
            "breakpoint": self.breakpoint.to_dict(),
            "spacecraft": sc_state_user,
            "spacecraft_admin": sc_state,
            "ground_station": gs_state,
            "tc_stack": tc_stack,
            "tc_history": tc_history
        }
        self._socket_server.broadcast(state_data)
