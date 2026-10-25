import os
import base64
import binascii
import secrets
import uvicorn
import asyncio
import threading
import logging
from contextlib import asynccontextmanager
from typing import Optional, Any
from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .communication import SocketClient
from .core import ObjectStore
from .utils import SpacePacketHandler
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# WS auth: clients offer WS_SUBPROTOCOL and WS_PASSWORD_PREFIX + unpadded base64url(password); server selects the 1st
WS_SUBPROTOCOL = "sim-ops"
WS_PASSWORD_PREFIX = "sim-ops.password."


def ws_password(ws: WebSocket) -> Optional[str]:
    """The password a WebSocket client offered in Sec-WebSocket-Protocol, if any."""
    for proto in ws.headers.get("sec-websocket-protocol", "").split(","):
        proto = proto.strip()
        if proto.startswith(WS_PASSWORD_PREFIX):
            token = proto[len(WS_PASSWORD_PREFIX):]
            try:
                return base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
            except (binascii.Error, ValueError):
                return None
    return None


# breakpoint fields that set up the exercise (e.g. a planned ACU fault): instructor-only
BREAKPOINT_SETUP_FIELDS = ('sc_initial_state', 'gs_initial_state')


def public_breakpoint(bp: Optional[dict]) -> Optional[dict]:
    if not bp:
        return bp
    return {k: v for k, v in bp.items() if k not in BREAKPOINT_SETUP_FIELDS}


def public_scenario(scenario: Optional[dict]) -> Optional[dict]:
    """A scenario without its breakpoints' initial states, which would give the exercise away."""
    if not scenario:
        return scenario
    return {**scenario, 'breakpoints': [public_breakpoint(bp) for bp in scenario.get('breakpoints') or []]}


def user_view(data: dict) -> dict:
    """State for operators: the sim broadcast (already SLE-filtered), minus admin-only fields and initial states."""
    view = {k: v for k, v in data.items() if k != 'spacecraft_admin'}
    if 'scenario' in view:
        view['scenario'] = public_scenario(view['scenario'])
    if 'breakpoint' in view:
        view['breakpoint'] = public_breakpoint(view['breakpoint'])
    return view


def admin_view(data: dict) -> dict:
    """State for the instructor: the full, unfiltered spacecraft state and scenario."""
    view = {k: v for k, v in data.items() if k != 'spacecraft_admin'}
    view['spacecraft'] = data.get('spacecraft_admin')
    return view


# what the 3D view draws; anything else stays off the unauthenticated viewer feed
VIEWER_SC_FIELDS = ('aocs_position', 'aocs_rotation', 'aocs_mode')
VIEWER_GS_FIELDS = ('elevation', 'distance', 'ul_state', 'status_dl',
                    'next_pass_start', 'next_pass_end', 'next_5_start', 'next_5_end')


def viewer_view(data: dict) -> dict:
    """Read-only subset for the 3D view: spacecraft position/attitude (not SLE-filtered), GS link/pass, breakpoint."""
    sc = data.get('spacecraft_admin') or {}
    gs = data.get('ground_station') or {}
    bp = data.get('breakpoint') or {}
    return {
        'type': data.get('type', 'state'),
        'ts': data.get('ts'),
        'running': data.get('running'),
        'paused': data.get('paused'),
        'breakpoint': {'name': bp.get('name'), 'ground_station': bp.get('ground_station')},
        'spacecraft': {k: sc.get(k) for k in VIEWER_SC_FIELDS},
        'ground_station': {k: gs.get(k) for k in VIEWER_GS_FIELDS},
    }


# controls operators may send via the TC stack; the rest (e.g. eps_battery_dod) set internal state and are admin-only
OPERATOR_TC_CONTROLS = frozenset({
    'aocs_mode', 'aocs_chain', 'aocs_valid',
    'ttc_mode', 'ttc_chain', 'ttc_ping', 'ttc_coherent', 'ttc_mcu_reboot',
    'ttc_s_antenna', 'ttc_x_antenna', 'ttc_ranging',
    'eps_chain', 'eps_sol_array_1_reset', 'eps_sol_array_2_reset',
    'eps_power_cycle_aocs', 'eps_power_cycle_ttc', 'eps_power_cycle_acu', 'eps_power_cycle_pdu',
    'eps_ttc_s_tx', 'eps_ttc_s_rx', 'eps_ttc_x_tx', 'eps_ttc_x_rx',
    'dhs_chain', 'dhs_obsw_mode', 'dhs_mem_dump_enabled', 'dhs_uploaded',
    'pl_gnss_status', 'pl_camera_status', 'pl_sdr_status',
})


class ControlRequest(BaseModel):
    """Request model for control commands"""
    system: str
    control: str
    value: Any
    # TC identifier (e.g. TC_TTC_021), lets an HPTC through a TTC MCU in error
    command: Optional[str] = None

class TCStackPushRequest(BaseModel):
    command: str
    system: str
    control: str
    value: Any

class OverrideRequest(BaseModel):
    attr: str
    value: Any = None

class DataProxyRequest(BaseModel):
    mode: str  # 'EGSE' or 'SLE'

class LoadScenarioRequest(BaseModel):
    filename: str

class UserPasswordRequest(BaseModel):
    password: str

class SimOpsAPI:
    """FastAPI service for SimOps control and monitoring (decoupled via socket communication)"""

    def __init__(self, host="0.0.0.0", port=9111, simops_host="127.0.0.1", simops_port=5555):
        self.host = host
        self.port = port
        self._api_thread = None
        self._event_loop: asyncio.AbstractEventLoop | None = None

        self._user_password = os.getenv("SIM_OPS_NG_USER_PASSWORD", "user123")
        self._admin_password = os.getenv("SIM_OPS_NG_ADMIN_PASSWORD", "admin123")

        # Socket client to communicate with SimOps
        self._socket_client = SocketClient(host=simops_host, port=simops_port)

        # WebSocket management — user connections (SLE-filtered) and admin connections (always full state)
        self._connections: set[WebSocket] = set()
        self._connections_lock = threading.Lock()
        self._admin_connections: set[WebSocket] = set()
        self._admin_connections_lock = threading.Lock()
        # viewer connections (3D view): no password, a read-only subset of the state
        self._viewer_connections: set[WebSocket] = set()
        self._viewer_connections_lock = threading.Lock()

        # Current state cache
        self._current_state = {}

        self._sp_handler = SpacePacketHandler()
        try:
            self._object_store = ObjectStore()
        except Exception as e:
            self._object_store = None
            logger.warning("ObjectStore unavailable: %s", e)

        # Create FastAPI app with lifespan
        @asynccontextmanager
        async def lifespan(_app: FastAPI):
            # Startup: capture the event loop
            self._event_loop = asyncio.get_running_loop()
            yield
            # Shutdown: nothing to clean up

        self.api = FastAPI(lifespan=lifespan)
        self.api.add_middleware(
            CORSMiddleware,
            allow_origins=['*'],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"]
        )

        self._setup_routes()

    def _verify_user_password(self, password: Optional[str]) -> bool:
        return bool(password) and secrets.compare_digest(password, self._user_password)

    def _verify_admin_password(self, password: Optional[str]) -> bool:
        return bool(password) and secrets.compare_digest(password, self._admin_password)

    def _require_user(self, x_user_password: Optional[str], x_admin_password: Optional[str]) -> None:
        """Operator endpoints: the user password, or the admin password (admin panel, triggers)."""
        if not (self._verify_user_password(x_user_password) or self._verify_admin_password(x_admin_password)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User password required")

    @staticmethod
    def _sim_result(result: dict, error: str) -> dict:
        """The sim handler's own result from a socket response; 400 if the command never ran."""
        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('error', error))
        return result.get('data') or {}

    @staticmethod
    def _raise_on_sim_failure(data: dict, error: str) -> None:
        """400 when the sim ran the command but reported it failed (e.g. no next breakpoint)."""
        if data.get('success') is False:
            raise HTTPException(status_code=400, detail=data.get('error') or data.get('status') or error)

    def _setup_routes(self):
        """Setup all API routes"""
        router = APIRouter(prefix="/api")

        @router.get("/auth")
        def auth(x_user_password: Optional[str] = Header(None)):
            if self._verify_user_password(x_user_password):
                return {"status": "ok"}  # 200 OK
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth failed")

        @router.get("/version")
        def get_version():
            return {"version": __version__}

        @router.get("/sim")
        def get_sim(x_admin_password: Optional[str] = Header(None)):
            # open, but the breakpoints' initial states are for the instructor only
            admin = self._verify_admin_password(x_admin_password)
            scenario = self._current_state.get("scenario")
            bp = self._current_state.get("breakpoint")
            return {
                "version": __version__,
                "running": self._current_state.get("running", False),
                "scenario": scenario if admin else public_scenario(scenario),
                "breakpoint": bp if admin else public_breakpoint(bp),
                "data_proxy": self._current_state.get("data_proxy", "SLE"),
                "sle_connected": self._current_state.get("sle_connected", False)
            }

        @router.get("/scenario")
        def get_scenario(x_admin_password: Optional[str] = Header(None)):
            scenario = self._current_state.get("scenario")
            if not scenario:
                result = self._socket_client.send_command('get_scenario', {})
                if result.get('success'):
                    scenario = result.get('data', {})
            if not self._verify_admin_password(x_admin_password):
                scenario = public_scenario(scenario)
            return scenario or {}

        @router.get("/scenarios")
        def list_scenarios(x_admin_password: Optional[str] = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin password required")
            data_dir = os.path.join(os.getcwd(), "data")
            if not os.path.isdir(data_dir):
                return {"scenarios": []}
            files = sorted(f for f in os.listdir(data_dir) if f.endswith(".json"))
            return {"scenarios": files}

        @router.post("/scenario/load")
        def load_scenario_route(req: LoadScenarioRequest, x_admin_password: str = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin password required")
            result = self._socket_client.send_command('load_scenario', {'filename': req.filename})
            if result.get('success'):
                data = result.get('data', {})
                if data.get('success'):
                    return data
                raise HTTPException(status_code=400, detail=data.get('error', 'Failed to load scenario'))
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to load scenario'))

        @router.get("/state")
        def get_state(x_user_password: Optional[str] = Header(None),
                      x_admin_password: Optional[str] = Header(None)):
            self._require_user(x_user_password, x_admin_password)
            return {
                "spacecraft": self._current_state.get("spacecraft", {}),
                "ground_station": self._current_state.get("ground_station", {})
            }

        @router.post("/start")
        def start_default(x_admin_password: str = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Admin password required"
                )
            # Send command via socket
            result = self._socket_client.send_command('start', {'breakpoint': 0})
            data = self._sim_result(result, "Failed to start simulation")
            if data.get('status') == 'already_running':
                raise HTTPException(status_code=409, detail=data.get('error', 'Simulation is already running'))
            self._raise_on_sim_failure(data, "Failed to start simulation")
            return {"running": True}

        @router.post("/stop")
        def stop(x_admin_password: str = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Admin password required"
                )
            # Send command via socket
            result = self._socket_client.send_command('stop')
            if result.get('success'):
                return {"running": False}
            raise HTTPException(status_code=400, detail="Failed to stop simulation")

        @router.post("/pause")
        def pause(x_admin_password: str = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Admin password required"
                )
            # Send command via socket
            result = self._socket_client.send_command('pause')
            if result.get('success'):
                return {"status": "paused"}
            raise HTTPException(status_code=400, detail="Failed to pause simulation")

        @router.post("/resume")
        def resume(x_admin_password: str = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Admin password required"
                )
            # Send command via socket
            result = self._socket_client.send_command('resume')
            if result.get('success'):
                return {"status": "resumed"}
            raise HTTPException(status_code=400, detail="Failed to resume simulation")

        @router.post("/next-breakpoint")
        def next_breakpoint(x_admin_password: str = Header(None), restart: bool = Query(False)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Admin password required"
                )
            # Send command via socket
            result = self._socket_client.send_command('next_breakpoint', {'restart': restart})
            data = self._sim_result(result, "Failed to move to next breakpoint")
            self._raise_on_sim_failure(data, "Failed to move to next breakpoint")
            # the moved-to breakpoint; the cached state may not have been broadcast since the move
            return {"status": "moved_to_next_breakpoint", "breakpoint": data.get("breakpoint")}

        @router.post("/previous-breakpoint")
        def previous_breakpoint(x_admin_password: str = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Admin password required"
                )
            # Send command via socket
            result = self._socket_client.send_command('previous_breakpoint')
            data = self._sim_result(result, "Failed to move to previous breakpoint")
            self._raise_on_sim_failure(data, "Failed to move to previous breakpoint")
            return {"status": "moved_to_previous_breakpoint", "breakpoint": data.get("breakpoint")}

        @router.post("/control")
        def control(request: ControlRequest, x_user_password: Optional[str] = Header(None),
                    x_admin_password: Optional[str] = Header(None)):
            """Ground station controls (operators), and direct spacecraft controls (admin only)"""
            self._require_user(x_user_password, x_admin_password)
            # operators use the TC stack; direct spacecraft controls reach internal state and are admin/trigger-only
            if request.system != 'ground_station' and not self._verify_admin_password(x_admin_password):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="Admin password required for spacecraft controls")
            # Prepare control data for socket command
            control_data = {
                'system': request.system,
                'control': request.control,
                'value': request.value,
                'command': request.command,
            }
            logger.info(f"API /control: sending command {request.control} to {request.system}")

            # Send command via socket
            result = self._socket_client.send_command('control', control_data)
            logger.info(f"API /control: socket response = {result}")

            if result.get('success'):
                # extract the status from the control response: {'success': True, 'data': {...}}
                data = result.get('data') or {}
                # a link-blocked TC still has a status; no status means it never ran (sim stopped, timeout, bad value)
                if data.get('success') is False and 'status' not in data:
                    raise HTTPException(status_code=400, detail=data.get('error', 'Failed to execute control command'))
                status_val = data.get('status', 'OK')
                logger.info(f"API /control: returning status = {status_val}")
                return {"status": status_val}
            logger.warning(f"API /control: command failed - {result}")
            raise HTTPException(status_code=400, detail="Failed to execute control command")

        @router.post("/tc-stack/execute")
        def tc_stack_execute(x_user_password: Optional[str] = Header(None),
                             x_admin_password: Optional[str] = Header(None)):
            self._require_user(x_user_password, x_admin_password)
            result = self._socket_client.send_command('tc_stack_execute', {})
            if result.get('success'):
                data = result.get('data', {})
                if data.get('success'):
                    return {'status': data.get('status', 'ok'), 'command': data.get('command')}
                raise HTTPException(status_code=400, detail=data.get('error', 'Failed to execute'))
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to execute'))

        def operator_tc(request: TCStackPushRequest, x_user_password: Optional[str],
                        x_admin_password: Optional[str]) -> dict:
            """The socket params of an operator TC; 401/403 unless it's a spacecraft TC operators can send."""
            self._require_user(x_user_password, x_admin_password)
            if request.system != 'spacecraft' or request.control not in OPERATOR_TC_CONTROLS:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail=f"Not an operator TC: {request.system}/{request.control}")
            return {
                'command': request.command,
                'system': request.system,
                'control': request.control,
                'value': request.value
            }

        @router.post("/tc-stack/send")
        def tc_send(request: TCStackPushRequest, x_user_password: Optional[str] = Header(None),
                    x_admin_password: Optional[str] = Header(None)):
            """Execute this TC right away, bypassing the stack (e.g. a file upload)."""
            params = operator_tc(request, x_user_password, x_admin_password)
            result = self._socket_client.send_command('tc_send', params)
            data = self._sim_result(result, "Failed to execute")
            self._raise_on_sim_failure(data, "Failed to execute")
            return {'status': data.get('status', 'ok'), 'command': data.get('command')}

        @router.post("/tc-stack")
        def tc_stack_push(request: TCStackPushRequest, x_user_password: Optional[str] = Header(None),
                          x_admin_password: Optional[str] = Header(None)):
            params = operator_tc(request, x_user_password, x_admin_password)
            result = self._socket_client.send_command('tc_stack_push', params)
            if result.get('success'):
                data = result.get('data', {})
                if data.get('success'):
                    return {'status': 'ok'}
                raise HTTPException(status_code=400, detail=data.get('error', 'Failed to add to stack'))
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to add to stack'))

        @router.delete("/tc-stack/{index}")
        def tc_stack_delete(index: int, x_user_password: Optional[str] = Header(None),
                            x_admin_password: Optional[str] = Header(None)):
            self._require_user(x_user_password, x_admin_password)
            result = self._socket_client.send_command('tc_stack_delete', {'index': index})
            data = self._sim_result(result, "Failed to delete from stack")
            self._raise_on_sim_failure(data, "Failed to delete from stack")
            return {'status': 'ok'}

        @router.get("/overrides")
        def get_overrides(x_admin_password: str = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin password required")
            result = self._socket_client.send_command('get_overrides', {})
            if result.get('success'):
                return result.get('data', {'overrides': []})
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to get overrides'))

        @router.post("/override/set")
        def set_override(req: OverrideRequest, x_admin_password: str = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin password required")
            result = self._socket_client.send_command('set_override', {'attr': req.attr, 'value': req.value})
            if result.get('success'):
                data = result.get('data') or {}
                # routed through the sim thread, a rejected value comes back as data.success False
                if data.get('success') is False:
                    raise HTTPException(status_code=400, detail=data.get('error', 'Failed to set override'))
                return data or {'status': 'ok'}
            raise HTTPException(status_code=400, detail=result.get('error', 'Failed to set override'))

        @router.post("/override/unset")
        def unset_override(req: OverrideRequest, x_admin_password: str = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin password required")
            result = self._socket_client.send_command('unset_override', {'attr': req.attr})
            data = self._sim_result(result, "Failed to unset override")
            self._raise_on_sim_failure(data, "Failed to unset override")
            return data or {'status': 'ok'}

        @router.post("/data-proxy")
        def set_data_proxy(req: DataProxyRequest, x_admin_password: str = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin password required")
            result = self._socket_client.send_command('set_data_proxy', {'mode': req.mode})
            data = self._sim_result(result, "Failed to set data proxy mode")
            self._raise_on_sim_failure(data, "Failed to set data proxy mode")
            return data or {'status': 'ok'}

        @router.post("/admin/set-state")
        def admin_set_state(req: OverrideRequest, x_admin_password: str = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin password required")
            result = self._socket_client.send_command('admin_set_state', {'attr': req.attr, 'value': req.value})
            data = self._sim_result(result, "Failed to set state")
            self._raise_on_sim_failure(data, "Failed to set state")
            return {'status': 'ok'}

        @router.get("/admin/user-password")
        def get_user_password(x_admin_password: str = Header(None)):
            # lets the admin panel show the real current password instead of a stale copy cached in its session
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin password required")
            return {'password': self._user_password}

        @router.post("/admin/user-password")
        def set_user_password(req: UserPasswordRequest, x_admin_password: str = Header(None)):
            if not self._verify_admin_password(x_admin_password):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin password required")
            new_password = req.password.strip()
            if not new_password:
                raise HTTPException(status_code=400, detail="Password cannot be empty")
            self._user_password = new_password
            # Drop active user sockets so they re-authenticate with the new password
            self._close_user_connections()
            logger.info("User password updated; active user connections closed")
            return {'status': 'ok'}

        @router.get("/obj-store/tm")
        def get_tm_packets(x_user_password: Optional[str] = Header(None),
                           x_admin_password: Optional[str] = Header(None)):
            self._require_user(x_user_password, x_admin_password)
            if self._object_store is None:
                raise HTTPException(status_code=503, detail="Object store unavailable")
            try:
                return self._object_store.get_objects_tm()
            except Exception as e:
                raise HTTPException(status_code=503, detail=str(e)) from e

        @router.get("/obj-store/fd")
        def get_fd_products(x_user_password: Optional[str] = Header(None),
                            x_admin_password: Optional[str] = Header(None)):
            self._require_user(x_user_password, x_admin_password)
            if self._object_store is None:
                raise HTTPException(status_code=503, detail="Object store unavailable")
            try:
                return self._object_store.get_objects_fd()
            except Exception as e:
                raise HTTPException(status_code=503, detail=str(e)) from e

        @router.get("/obj-store/sp/{bucket}/{object_name}")
        def get_space_packet(bucket: str, object_name: str, x_user_password: Optional[str] = Header(None),
                             x_admin_password: Optional[str] = Header(None)):
            self._require_user(x_user_password, x_admin_password)
            if self._object_store is None:
                raise HTTPException(status_code=503, detail="Object store unavailable")
            try:
                raw = self._object_store.get(bucket, object_name)
                packet = self._sp_handler.from_bytestream(raw)
                return self._sp_handler.as_dict(packet)
            except Exception as e:
                raise HTTPException(status_code=404, detail=str(e)) from e

        async def serve(ws: WebSocket, connections: set, lock: threading.Lock, view) -> None:
            # a browser drops the connection unless the server selects a subprotocol it offered
            offered = [p.strip() for p in ws.headers.get("sec-websocket-protocol", "").split(",")]
            await ws.accept(subprotocol=WS_SUBPROTOCOL if WS_SUBPROTOCOL in offered else None)
            with lock:
                connections.add(ws)
            try:
                # send the latest state now instead of waiting for the next tick (none come while the sim is stopped)
                if self._current_state:
                    await ws.send_json(view(self._current_state))
                while True:
                    await ws.receive_text()  # keep connection alive
            except WebSocketDisconnect:
                pass
            finally:
                with lock:
                    connections.discard(ws)

        @router.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket):
            if not self._verify_user_password(ws_password(ws)):
                await ws.close(code=1008)
                return
            await serve(ws, self._connections, self._connections_lock, user_view)

        @router.websocket("/ws/admin")
        async def websocket_admin_endpoint(ws: WebSocket):
            # Admin WebSocket: always receives full state regardless of data_proxy mode
            if not self._verify_admin_password(ws_password(ws)):
                await ws.close(code=1008)
                return
            await serve(ws, self._admin_connections, self._admin_connections_lock, admin_view)

        @router.websocket("/ws/viewer")
        async def websocket_viewer_endpoint(ws: WebSocket):
            # Viewer WebSocket (3D view): open, read-only, only what the visualization draws
            await serve(ws, self._viewer_connections, self._viewer_connections_lock, viewer_view)

        self.api.include_router(router)

    def start(self):
        """Start the API server in a background thread and connect to SimOps"""
        # register the broadcast handler before connecting: the sim answers a subscribe with a snapshot right away
        self._socket_client.register_broadcast_handler('state', self._on_state_update)

        # connect to the SimOps socket server, reconnecting in the background if the sim is down or restarted
        self._socket_client.start()

        if self._api_thread:
            return

        def run():
            uvicorn.run(
                self.api,
                host=self.host,
                port=self.port,
                log_level="info",
            )

        self._api_thread = threading.Thread(target=run, daemon=True)
        self._api_thread.start()

    def _on_state_update(self, data: dict):
        """Handle state update from socket server"""
        self._current_state = data
        # Broadcast to WebSocket clients
        self._broadcast_to_websockets(data)

    def _broadcast_to_websockets(self, data: dict):
        """Broadcast state to WebSocket clients: users minus spacecraft_admin, admins with it, viewers a subset."""
        if not self._event_loop:
            return

        feeds = [
            (self._connections, self._connections_lock, user_view(data)),
            (self._admin_connections, self._admin_connections_lock, admin_view(data)),
            (self._viewer_connections, self._viewer_connections_lock, viewer_view(data)),
        ]

        async def _send():
            for connections, lock, payload in feeds:
                with lock:
                    snapshot = list(connections)
                dead = []
                for ws in snapshot:
                    try:
                        await ws.send_json(payload)
                    except Exception:
                        dead.append(ws)
                if dead:
                    with lock:
                        for ws in dead:
                            connections.discard(ws)

        asyncio.run_coroutine_threadsafe(_send(), self._event_loop)

    def _close_user_connections(self, code: int = 1008):
        """Force-close all user WebSocket connections (e.g. after a password change) so they re-authenticate."""
        if not self._event_loop:
            return

        async def _close():
            with self._connections_lock:
                snapshot = list(self._connections)
                self._connections.clear()
            for ws in snapshot:
                try:
                    await ws.close(code=code)
                except Exception:
                    pass

        asyncio.run_coroutine_threadsafe(_close(), self._event_loop)

    def stop(self):
        """Stop the API server and disconnect socket"""
        self._socket_client.disconnect()

        if self._api_thread:
            self._api_thread.join(timeout=5)
            self._api_thread = None
