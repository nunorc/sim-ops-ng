---
title: "The simulation loop"
weight: 20
---

# The simulation loop

What `SimOps` does each tick, and how simulated time survives pauses and breakpoint jumps. Code:
[`so/core.py`](../sim-ops-ng-lib/so/core.py),
[`so/spacecraft.py`](../sim-ops-ng-lib/so/spacecraft.py).

---

## 1. Real-time environment

The loop is a SimPy process running in a `simpy.rt.RealtimeEnvironment` on its own thread
(`SimOps._run_simops_thread()`):

- `initial_time` is the active breakpoint's `begin`, so `env.now` is a UTC epoch timestamp.
- `factor` is the scenario's `time_factor`: `1.0` is real time, `0.5` runs twice as fast.
- One tick advances `time_step` simulated seconds (default `1.0`).

---

## 2. One tick

`SimOps._simpy_process()`:

1. **Drain the command queue** — execute every pending command in the sim thread (§3).
2. If **paused**, broadcast state and wait one tick without advancing simulated time.
3. Compute `ts = env.now + _ts_offset`.
4. `GroundStationSim.update(ts, sc_state, gs_overrides)` — geometry, downlink budget, lock state,
   spectra. See [ground_station.md](ground_station.md) and [rf_link.md](rf_link.md).
5. `SpacecraftSim.update(ts, gs_state, sc_overrides)` — the subsystem chain
   **AOCS → TTC → EPS → DHS → Payload**, then overrides.
6. Broadcast the state (see [architecture.md](architecture.md#3-the-state-broadcast)).
7. Store a TM packet if `int(ts) % tm_packet_frequency == 0`, and try to write the pass's
   flight-dynamics product.
8. Sleep `time_step` (`_sleep()`), executing queued commands about every `CMD_POLL_S` (0.1 s)
   of wall time.

---

## 3. The command queue

The socket server runs each request on its own thread. Commands that change state (controls, TC
execution, overrides, admin set-state, breakpoint moves) are queued instead (`_send_cmd()` →
`_command_queue`) and run in the sim thread by `_dispatch_cmd()` within ~0.1 s, also between ticks.

- The caller waits up to `SEND_CMD_TIMEOUT` (4 s, under the API's 5 s, so the sim gives up first).
  A command whose caller timed out is cancelled and never runs.
- Stopping the loop fails anything still queued.
- Lifecycle and admin handlers (start/stop, breakpoints, overrides, scenario load) run one at a
  time (`_admin_lock`).

---

## 4. Timestamps and deltas

`SpacecraftSim.update()` sets `_state.ts = ts` only **after** the subsystems run, so they can use
`ts - _state.ts` as the tick length (EPS battery, DHS memory). The baseline is seeded to the
breakpoint's `begin` (`SpacecraftSim.__init__`, and `seed_ts()` on each breakpoint change);
otherwise the first delta would be measured from `0.0`.

---

## 5. Jumping in time

The effective timestamp is `env.now + _ts_offset`, so the clock can move without restarting SimPy:

- **Breakpoint change** — the offset is set so the next tick lands on the new breakpoint's `begin`.
- **Pause** — each paused iteration advances `env.now` by `time_step` and subtracts it from the
  offset: time stays frozen and resuming doesn't skip ahead.

---

## 6. Lifecycle

| Action | Method | Effect |
|---|---|---|
| Start | `start_loop(bp)` | Optionally step to breakpoint `bp`, apply fixed invariants, start the thread. |
| Pause / resume | `pause_loop()` / `resume_loop()` | Freeze / unfreeze simulated time. |
| Stop | `stop_loop()` | Stop the thread and **reset everything**: first breakpoint, fresh spacecraft and ground station, no overrides, empty TC stack, data proxy back to `SLE`. |
| Step | `step_loop(bp)` | Select a breakpoint and apply its initial states. |

`SpacecraftSim.apply_fixed_updates()` runs at start and after each breakpoint change: currently,
in OBSW safe mode both transmitters are off. It is not re-applied on later ticks, so safe mode
entered mid-pass leaves the transmitters as they were.
