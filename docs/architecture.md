---
title: "Architecture"
weight: 10
---

# Architecture

The processes and what crosses between them. Per-tick engine internals: [sim_loop.md](sim_loop.md).

---

## 1. Processes

| Process | Entry point | Port | Role |
|---|---|---|---|
| **Sim engine** | [`bin/sim-ops.py`](../sim-ops-ng-lib/bin/sim-ops.py) → `SimOps` | `:5555` (TCP) | Runs the simulation loop and owns all state. |
| **API** | [`bin/sim-ops-api.py`](../sim-ops-ng-lib/bin/sim-ops-api.py) → `SimOpsAPI` | `:9111` (HTTP/WS) | Authenticates clients, forwards commands to the engine, relays state broadcasts to WebSockets. |
| **Admin** | [`bin/admin.py`](../sim-ops-ng-lib/bin/admin.py) → Flask under gunicorn | `:9131` (HTTP) | Instructor panel; a client of the API. |
| **MinIO** | built from source (`Dockerfile.minio`) | `:9000`, console `:9001` | Object store for TM/TC space packets and flight-dynamics products. |
| **nginx** | [`containers/nginx/nginx.conf`](../containers/nginx/nginx.conf) | `:8080` | Serves the MCS and proxies everything else. |

The engine holds **no passwords**: authentication lives entirely in the API layer.

---

## 2. Engine ↔ API: the socket link

JSON over TCP ([`so/communication.py`](../sim-ops-ng-lib/so/communication.py)): `SocketServer` in
the engine, `SocketClient` in the API (reconnects if the engine restarts):

```json
{"type": "command", "id": "…", "command": "control", "params": {"system": "spacecraft", "control": "aocs_mode", "value": "SUN"}}
{"type": "response", "id": "…", "command": "control", "success": true, "data": {"status": "g:REL g:ACC g:EXE"}}
```

After `{"type": "subscribe"}` a client gets a snapshot, then a `"type": "state"` broadcast every
tick. Handlers are registered in `SimOps._setup_socket_handlers()`; those that mutate state run in
the sim thread via a queue
([sim_loop.md](sim_loop.md#3-the-command-queue)).

---

## 3. The state broadcast

Each broadcast (`SimOps._broadcast_state()`) carries:

| Key | Content |
|---|---|
| `ts` | Simulated timestamp (epoch seconds). |
| `running`, `paused` | Loop status. |
| `data_proxy`, `sle_connected` | `SLE` or `EGSE`, and whether spacecraft TM is currently delivered. |
| `scenario`, `breakpoint` | The loaded scenario and active breakpoint. |
| `spacecraft` | The `SpacecraftState` as operators see it — `null` when there is no telemetry. |
| `spacecraft_admin` | The full, unfiltered `SpacecraftState`. |
| `ground_station` | The `GroundStationState`. |
| `tc_stack`, `tc_history` | The shared telecommand stack and the last ten executions. |

Enum fields are serialised **by name** (`custom_dict_factory` in
[`so/data_model.py`](../sim-ops-ng-lib/so/data_model.py)).

**Data proxy.** `SLE` (default): `spacecraft` is `null` unless the downlink is at `FRAME_LOCK`.
`EGSE`: always delivered, as on the bench. With the TTC MCU in `error`, `spacecraft` is scrubbed
(`SpacecraftState.scrub()`). Per-WebSocket relaying: [api.md](api.md#3-websockets).

---

## 4. Object store

When MinIO is reachable (`SIM_OPS_NG_MINIO_*`), the engine stores:

- **TM packets** — a CCSDS space packet of the spacecraft state every `tm_packet_frequency`
  simulated seconds, in `sim-<scenario>-tm` (in `SLE` mode only at `FRAME_LOCK`).
- **TC packets** — every command released to the spacecraft (`g:REL`), in `sim-<scenario>-tc`.
- **Flight-dynamics products** — the pass's tracking data at its end (`SLE` mode only), in
  `flight-dynamics`. See [ground_station.md](ground_station.md#3-flight-dynamics).

Packets are built by `SpacePacketHandler` ([`so/utils.py`](../sim-ops-ng-lib/so/utils.py)). Without
MinIO the engine logs a warning and carries on.

---

## 5. nginx routing

| Path | Upstream |
|---|---|
| `/` | The built MCS (static). |
| `/api/`, `/api/ws` | `sim-ops-ng-api:9111` |
| `/admin/` | `sim-ops-ng-admin:9131` |
| `/3dv/` | `sim-ops-ng-3dv:8080` |
