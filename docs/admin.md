---
title: "Admin panel"
weight: 40
---

# Admin panel

The instructor's panel: a Flask app ([`so/admin.py`](../sim-ops-ng-lib/so/admin.py), templates in
[`so/templates/`](../sim-ops-ng-lib/so/templates/)) under gunicorn on `:9131` (`/admin/` behind
nginx). It is an API client using the admin password.

---

## 1. Session control

Log in with `SIM_OPS_NG_ADMIN_PASSWORD`, then:

- **Start / stop / pause / resume** the simulation. Stopping resets everything
  ([sim_loop.md](sim_loop.md#6-lifecycle)).
- **Next / previous breakpoint** — move between passes.
- **Load a scenario** from `data/`.
- **Data proxy** — `SLE` (telemetry only at `FRAME_LOCK`) or `EGSE` (always).
- **Change the user password** — disconnects every operator.
- **Set spacecraft state** (`/api/admin/set-state`), bypassing the bus and link checks; only the
  fields in `SimOps._do_admin_set_state()` (modes, antennas, TX/RX status, MCU, OBSW mode, memory,
  battery DoD, ACU, PDU).
- **Trigger safe mode** — the on-board FDIR action, link-independent.

---

## 2. Overrides

Overrides force a value **after** each step, so they always win until unset.

| Kind | Attributes |
|---|---|
| Ground station | `status_dl`, `max_status_dl`, `max_c_no_dl`, `max_eb_no_dl`, `frame_quality`, `no_tm`, `no_tc` |
| Spacecraft | any scalar (number, boolean, text) or enum `SpacecraftState` field, e.g. `aocs_valid`, `eps_battery_dod`; `eps_sol_array` takes one value for both arrays. Other list fields (`aocs_rotation`, `pl_gnss_pos`, the DHS windows, …) can't be overridden. |

Enum values are given by name. `no_tm` stops telemetry outright; `no_tc` rejects every command.

---

## 3. Triggers

Triggers are scripted failures: `data/trigger-<n>.py`, run as a subprocess (60 s timeout) by the
admin app's `POST /api/trigger/<n>` (`/admin/api/trigger/<n>` behind nginx). Each is a list of
steps, routed by `run_control_steps()` in [`so/utils.py`](../sim-ops-ng-lib/so/utils.py):

| Step `system` | Goes to |
|---|---|
| `override` | `/api/override/set` (or `/unset` with `control: "_unset"`) |
| any, with `admin: true` | `/api/admin/set-state` |
| `spacecraft`, `ground_station` | `/api/control` |

What each trigger does is exercise content: read the script, don't document it here. To add one,
drop a script in `data/` and register it in `TRIGGER_SCRIPTS` in `so/admin.py`.
