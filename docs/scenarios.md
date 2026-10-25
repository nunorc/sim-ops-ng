---
title: "Scenarios and breakpoints"
weight: 30
---

# Scenarios and breakpoints

A JSON file fixing the orbit and splitting the exercise into **breakpoints**, typically one per
pass. Loader: `load_scenario()` in
[`so/core.py`](../sim-ops-ng-lib/so/core.py); data classes in
[`so/data_model.py`](../sim-ops-ng-lib/so/data_model.py).

---

## 1. Shipped scenarios

| File | Breakpoints | Notes |
|---|---|---|
| [`data/demo.json`](../sim-ops-ng-lib/data/demo.json) | 4 | Default (`SIM_OPS_NG_SCENARIO`). |
| [`data/testing.json`](../sim-ops-ng-lib/data/testing.json) | 4 | `time_factor: 0.5` (twice real time). |

The admin panel can load any `*.json` in `data/` at runtime (`POST /api/scenario/load`); nothing
outside `data/` is accepted.

---

## 2. File format

```json
{
  "name": "example",
  "tle": "SAT\n1 …\n2 …",
  "time_factor": 1.0,
  "tm_packet_frequency": 30,
  "breakpoints": [
    {
      "name": "pass_1",
      "begin": "2030-01-01 10:00:00+00:00",
      "end":   "2030-01-01 10:15:00+00:00",
      "ground_station": {
        "name": "GS-1", "latitude": 0.0, "longitude": 0.0,
        "altitude": 0, "antenna_diameter_m": 4.0
      },
      "gs_initial_state": { "carrier_ul": "off" },
      "sc_initial_state": { }
    }
  ]
}
```

| Field | Default | Meaning |
|---|---|---|
| `name` | — | Scenario name; also names the MinIO buckets (`sim-<name>-tm`, `sim-<name>-tc`), so it must be 1–56 lowercase letters, digits, `-` or `.` (`.` not at either end, next to `-` or doubled; checked on load). |
| `tle` | — | Three-line element set (name + two lines), used by AOCS and the ground station. Checked on load: two 69-character element lines starting `1 ` / `2 `, same catalog number, valid checksums. |
| `time_factor` | `1.0` | Wall-clock seconds per simulated second; a positive number. |
| `tm_packet_frequency` | `30` | Seconds between stored TM packets; a positive integer. |
| `breakpoints[].name` | — | Unique within the scenario (breakpoints are looked up by name). |
| `breakpoints[].begin` / `end` | — | ISO timestamps of the window, with a timezone (`+00:00` by convention; other offsets give the same instant); `begin` must be before `end`. A timestamp without a timezone fails the load. |
| `breakpoints[].ground_station` | — | Station location and dish size (`antenna_diameter_m`, default 4.0). |
| `breakpoints[].gs_initial_state` | `{}` | `GroundStationState` fields applied when the breakpoint starts. |
| `breakpoints[].sc_initial_state` | `{}` | `SpacecraftState` fields applied when the breakpoint starts. |

Enum fields in initial states are given **by name** (`"carrier_ul": "off"`), lists element by
element. A field the state doesn't have, or an unknown enum name, fails the load (`ValueError`),
as does an invalid or missing scenario or breakpoint field above (a malformed `ground_station`
raises `TypeError`). The **types** of other initial-state values are not checked: a wrong one
(e.g. `"eps_battery_dod": "high"`) loads, then stops the simulation on that breakpoint's first
tick. Initial states are instructor-only: the API hides them from operators
([api.md](api.md#2-endpoints)), so keep planned faults there and out of these docs.

---

## 3. Breakpoints at runtime

When a breakpoint becomes active (`step_loop`, `move_to_next_breakpoint`,
`move_to_previous_breakpoint`), the engine:

1. re-seeds the spacecraft's time baseline to the breakpoint's `begin`
   (see [sim_loop.md](sim_loop.md#4-timestamps-and-deltas));
2. applies `sc_initial_state` and `gs_initial_state` over the **current** state (unlisted fields
   carry over);
3. enforces the fixed invariants (`apply_fixed_updates()`);
4. resets the flight-dynamics product flag and tracking samples for the new pass.

`next_breakpoint` with `restart=true` wraps around to the first breakpoint.
