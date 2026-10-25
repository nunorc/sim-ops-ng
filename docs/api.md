---
title: "REST and WebSocket API"
weight: 10
---

# REST and WebSocket API

`SimOpsAPI` in [`so/api.py`](../sim-ops-ng-lib/so/api.py): FastAPI on `:9111`, at `/api` behind
nginx. Commands go to the engine over the socket link
([architecture.md](architecture.md#2-engine--api-the-socket-link)); state reads come from the last
broadcast.

---

## 1. Authentication

Two shared passwords, from the environment:

| Role | Variable | Passed as |
|---|---|---|
| User (operators) | `SIM_OPS_NG_USER_PASSWORD` | header `X-User-Password` |
| Admin (instructor) | `SIM_OPS_NG_ADMIN_PASSWORD` | header `X-Admin-Password` |

Never in query strings (they would end up in access logs). Browsers can't set WebSocket headers,
so WebSocket clients offer two subprotocols, `sim-ops` and `sim-ops.password.<unpadded base64url>`;
the server selects `sim-ops`:

```js
const b64 = btoa(String.fromCharCode(...new TextEncoder().encode(password)))
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
new WebSocket(url, ['sim-ops', `sim-ops.password.${b64}`]);
```

Changing the user password closes open user WebSockets (code 1008).

---

## 2. Endpoints

**Open**

| Method | Path | Returns |
|---|---|---|
| GET | `/api/version` | `{version}` |
| GET | `/api/sim` | Version, running flag, scenario, breakpoint, data proxy, `sle_connected`. |
| GET | `/api/scenario` | The loaded scenario. |

Without the admin password (and on the user WebSocket), breakpoints come without
`sc_initial_state` / `gs_initial_state`: they may set up a planned fault.

**User** (`X-User-Password`; the admin password is accepted too, except on `/api/auth`)

| Method | Path | Does |
|---|---|---|
| GET | `/api/auth` | 200 if the password is right, else 401. |
| GET | `/api/state` | Last `spacecraft` (operator view) and `ground_station` state. |
| POST | `/api/control` | `{system, control, value}` → `{status}`; 400 if the command never ran (sim stopped, timed out, bad value). Operators may only control the `ground_station`; `spacecraft` controls need the admin password. See [commanding.md](commanding.md). |
| GET | `/api/obj-store/tm` | TM/TC buckets and their objects. |
| GET | `/api/obj-store/fd` | Flight-dynamics products. |
| GET | `/api/obj-store/sp/{bucket}/{object}` | One decoded space packet. |
| POST | `/api/tc-stack` | Push `{command, system, control, value}` (max 5). Only spacecraft TCs from the operator catalogue (`OPERATOR_TC_CONTROLS` in `so/api.py`), else 403. |
| DELETE | `/api/tc-stack/{index}` | Remove an entry; 400 if there is none at that index. |
| POST | `/api/tc-stack/execute` | Execute the head of the stack → `{status, command}`. |
| POST | `/api/tc-stack/send` | Execute the given TC right away, bypassing the stack (file uploads) → `{status, command}`. |

**Admin** (`X-Admin-Password`)

| Method | Path | Does |
|---|---|---|
| POST | `/api/start` | Start the loop at the first breakpoint (409 if already running). |
| POST | `/api/stop`, `/api/pause`, `/api/resume` | Loop lifecycle ([sim_loop.md](sim_loop.md#6-lifecycle)). |
| POST | `/api/next-breakpoint[?restart=true]`, `/api/previous-breakpoint` | Move between breakpoints; returns the new breakpoint, 400 if there is none. |
| GET | `/api/scenarios` | `*.json` files in `data/`. |
| POST | `/api/scenario/load` | `{filename}` — load a scenario from `data/`. |
| GET | `/api/overrides` | Active overrides. |
| POST | `/api/override/set`, `/api/override/unset` | `{attr, value}` — see [admin.md](admin.md#2-overrides). |
| POST | `/api/admin/set-state` | `{attr, value}` — set a spacecraft field directly, bypassing commanding. |
| POST | `/api/data-proxy` | `{mode: "SLE" \| "EGSE"}`. |
| GET / POST | `/api/admin/user-password` | Read / change the user password. |

---

## 3. WebSockets

| Path | Auth | Receives |
|---|---|---|
| `/api/ws` | user password (subprotocol) | The state broadcast, with `spacecraft` filtered by the data proxy. |
| `/api/ws/admin` | admin password (subprotocol) | The full broadcast, with the unfiltered spacecraft state as `spacecraft`, whatever the link state. |
| `/api/ws/viewer` | none | Read-only subset for the 3D view: spacecraft position/attitude (unfiltered), ground-station link and pass state, and the current breakpoint. |

A wrong password closes the socket with code 1008. Each socket gets the latest state on connect,
then every broadcast ([contents](architecture.md#3-the-state-broadcast)).
[`bin/ws-client.py`](../sim-ops-ng-lib/bin/ws-client.py) is a small debug listener.
