import threading
import time
from datetime import datetime

import pytest

from conftest import wait_for


SCENARIOS = ["data/demo.json", "data/testing.json"]


@pytest.fixture
def make_sim(no_minio):
    from so.core import SimOps
    sims = []

    def _make(scenario, **kwargs):
        sim = SimOps(scenario=scenario, **kwargs)
        sims.append(sim)
        return sim

    yield _make
    for sim in sims:
        sim.shutdown()


# ---- Scenarios ----

def test_load_scenario_missing_file_is_clear(tmp_path):
    from so.core import SimOps, load_scenario
    missing = str(tmp_path / "nope.json")
    with pytest.raises(FileNotFoundError, match="nope.json"):
        load_scenario(missing)
    with pytest.raises(FileNotFoundError, match="nope.json"):
        SimOps(scenario=missing)


def test_load_scenario_without_breakpoints(tmp_path):
    from so.core import load_scenario
    path = tmp_path / "empty.json"
    path.write_text('{"name": "empty", "tle": "x", "breakpoints": []}')
    with pytest.raises(ValueError, match="no breakpoints"):
        load_scenario(str(path))


@pytest.mark.parametrize("field, value", [
    ("tm_packet_frequency", 0), ("tm_packet_frequency", 2.5), ("tm_packet_frequency", True),
    ("time_factor", 0), ("time_factor", -1), ("time_factor", "fast"),
])
def test_load_scenario_rejects_bad_timing(tmp_path, field, value):
    import json
    from so.core import load_scenario
    with open("data/demo.json", encoding="utf-8") as fin:
        data = json.load(fin)
    data[field] = value
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=field):
        load_scenario(str(path))


@pytest.mark.parametrize("change, match", [
    (lambda bp: bp.pop("ground_station"), "no ground_station"),
    (lambda bp: bp.update(begin="not-a-date"), "begin"),
    (lambda bp: bp.update(end=None), "end"),
    (lambda bp: bp.pop("name"), "missing name"),
    (lambda bp: bp.pop("begin"), "missing begin"),
    (lambda bp: bp.update(end=bp["begin"]), "begin must be before end"),
    (lambda bp: bp.update(begin=bp["begin"].replace("+00:00", "")), "begin must have a timezone"),
    (lambda bp: bp.update(end=bp["end"].replace("+00:00", "")), "end must have a timezone"),
    (lambda bp: bp.update(sc_initial_state={"eps_acuu": "control_err"}), "unknown fields: eps_acuu"),
    (lambda bp: bp.update(gs_initial_state={"carrier": "off"}), "unknown fields: carrier"),
    (lambda bp: bp.update(sc_initial_state={"aocs_mode": "SUNN"}), "aocs_mode must be one of"),
])
def test_load_scenario_rejects_bad_breakpoint(tmp_path, change, match):
    import json
    from so.core import load_scenario
    with open("data/demo.json", encoding="utf-8") as fin:
        data = json.load(fin)
    change(data["breakpoints"][0])
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=match):
        load_scenario(str(path))


def test_breakpoint_with_utc_offset_finds_the_same_passes(tmp_path):
    """A non-UTC offset is the same instant: the pass window is built from its UTC day, not the local one."""
    import json
    from so.core import load_scenario
    from so.ground_station import GroundStationSim
    with open("data/demo.json", encoding="utf-8") as fin:
        data = json.load(fin)
    utc = load_scenario("data/demo.json")
    bp = data["breakpoints"][0]
    # 04:39:24+00:00 is 23:39:24-05:00 on the previous day
    bp["begin"], bp["end"] = "2023-08-26 23:39:24-05:00", "2023-08-26 23:54:24-05:00"
    path = tmp_path / "offset.json"
    path.write_text(json.dumps(data))
    shifted = load_scenario(str(path))
    gs_utc = GroundStationSim(scenario=utc, bp=utc.breakpoints[0])
    gs_shifted = GroundStationSim(scenario=shifted, bp=shifted.breakpoints[0])
    assert gs_shifted.passes == gs_utc.passes


def test_load_scenario_rejects_duplicate_breakpoint_names(tmp_path):
    """Breakpoints are looked up by name, so a duplicate would make next/previous loop."""
    import json
    from so.core import load_scenario
    with open("data/demo.json", encoding="utf-8") as fin:
        data = json.load(fin)
    data["breakpoints"][1]["name"] = data["breakpoints"][0]["name"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Duplicate breakpoint name"):
        load_scenario(str(path))


@pytest.mark.parametrize("key", ["name", "tle"])
def test_load_scenario_requires_name_and_tle(tmp_path, key):
    import json
    from so.core import load_scenario
    with open("data/demo.json", encoding="utf-8") as fin:
        data = json.load(fin)
    del data[key]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=f"missing {key}"):
        load_scenario(str(path))


def _demo_tle_lines():
    import json
    with open("data/demo.json", encoding="utf-8") as fin:
        return json.load(fin)["tle"].split("\n")


def _with_checksum(line):
    from so.core import _tle_checksum
    return line[:68] + str(_tle_checksum(line))


@pytest.mark.parametrize("tle, match", [
    (lambda name, l1, l2: f"{name}\n1 garbage\n2 garbage", "69 characters"),
    (lambda name, l1, l2: f"{l1}\n{l2}", "3 lines"),
    (lambda name, l1, l2: f"{name}\n{l2}\n{l1}", "starting with '1 '"),
    (lambda name, l1, l2: f"{name}\n{l1[:68]}{(int(l1[68]) + 1) % 10}\n{l2}", "checksum"),
    # a digit changed (and the checksum fixed to match): not a typo the checksum would catch
    (lambda name, l1, l2: f"{name}\n{l1}\n{_with_checksum(l2[:2] + '99999' + l2[7:])}", "different satellites"),
    (lambda name, l1, l2: None, "string"),
])
def test_load_scenario_rejects_bad_tle(tmp_path, tle, match):
    import json
    from so.core import load_scenario
    with open("data/demo.json", encoding="utf-8") as fin:
        data = json.load(fin)
    data["tle"] = tle(*_demo_tle_lines())
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=match):
        load_scenario(str(path))


@pytest.mark.parametrize("name", ["Demo", "my scenario", "my_scenario", ".demo", "a.-b", "a..b", "", "a" * 57, None])
def test_load_scenario_rejects_bad_name(tmp_path, name):
    """The name is used in the MinIO bucket names, which make_bucket would reject on every TM/TC write."""
    import json
    from so.core import load_scenario
    with open("data/demo.json", encoding="utf-8") as fin:
        data = json.load(fin)
    data["name"] = name
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="scenario name"):
        load_scenario(str(path))


def test_shipped_scenario_names_pass_the_check():
    import glob
    import json
    from so.core import _check_scenario_name
    for filename in glob.glob("data/*.json"):
        with open(filename, encoding="utf-8") as fin:
            _check_scenario_name(json.load(fin)["name"])
    # valid bucket names, which make_bucket accepts
    for name in ("a" * 56, "-demo", "demo-", "my.scenario", "pass-1.v2"):
        _check_scenario_name(name)


def test_shipped_tles_pass_the_check():
    import json
    from so.core import _check_tle
    from so.data_model import Scenario
    for scenario in SCENARIOS:
        with open(scenario, encoding="utf-8") as fin:
            _check_tle(json.load(fin)["tle"])
    _check_tle(Scenario().tle)


def test_failed_scenario_load_leaves_sim_untouched(sim, monkeypatch):
    import so.core
    good = so.core.load_scenario("data/demo.json")
    bad = so.core.load_scenario("data/demo.json")
    bad.name = "bad-tle"
    bad.tle = "NAME LINE ONLY"  # the element lines are missing: building the sims fails
    monkeypatch.setattr(so.core, "load_scenario", lambda _filename: bad)

    before = (sim.scenario, sim.spacecraft, sim.ground_station)
    sim.time_factor = 0.01
    sim.start_loop()
    try:
        result = sim._handle_load_scenario({"filename": "data/demo.json"})
        assert result["success"] is False and "Invalid scenario" in result["error"]
        # still running the old scenario, with its own spacecraft and ground station
        assert sim._running
        assert (sim.scenario, sim.spacecraft, sim.ground_station) == before
        assert sim.scenario.name == good.name
    finally:
        sim.stop_loop()


def test_scenario_serialises_enums_by_name():
    from so.core import load_scenario
    from so.communication import convert_to_serializable
    scenario = convert_to_serializable(load_scenario("data/demo.json").to_dict())
    initial = scenario["breakpoints"][0]["gs_initial_state"]
    assert initial["carrier_ul"] == "off" and initial["mode"] == "S_Sup_LBR"


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_breakpoint_runs_begin_to_end(make_sim, scenario):
    sim = make_sim(scenario)

    for bp in sim.scenario.breakpoints:
        sim.step_loop(bp=bp.name)
        begin = datetime.fromisoformat(bp.begin).timestamp()
        end = datetime.fromisoformat(bp.end).timestamp()

        elevations = []
        ts = begin
        while ts <= end:
            sim.ground_station.update(ts, sc_state=sim.spacecraft.state, overrides={})
            sim.spacecraft.update(ts, gs_state=sim.ground_station.state, overrides={})
            if sim.ground_station.state.elevation is not None:
                elevations.append(sim.ground_station.state.elevation)
            ts += 10

        # every shipped breakpoint is a pass, so the station must see the spacecraft
        assert elevations, f"{scenario} {bp.name}: no elevation during the breakpoint"


def test_passes_follow_breakpoint_day(make_sim):
    sim = make_sim("data/demo.json")
    bp = sim.scenario.breakpoints[-1]
    sim.step_loop(bp=bp.name)

    begin = datetime.fromisoformat(bp.begin).timestamp()
    end = datetime.fromisoformat(bp.end).timestamp()
    assert any(p[0] <= end and begin <= p[1] for p in sim.ground_station.passes)


def test_5deg_passes_matched_by_time(make_sim):
    sim = make_sim("data/demo.json")
    gs = sim.ground_station

    assert len(gs.passes_5) == len(gs.passes)
    for p, p5 in zip(gs.passes, gs.passes_5):
        if p5 is not None:
            assert p[0] <= p5[0] <= p5[1] <= p[1]


# ---- Breakpoint navigation ----

def _names(sim):
    return [bp.name for bp in sim.scenario.breakpoints]


def test_next_and_previous_walk_all_breakpoints(sim):
    names = _names(sim)
    assert sim.breakpoint.name == names[0]
    assert sim.move_to_previous_breakpoint() is False
    assert sim.breakpoint.name == names[0]

    for name in names[1:]:
        assert sim.move_to_next_breakpoint() is True
        assert sim.breakpoint.name == name
    assert sim.move_to_next_breakpoint() is False
    assert sim.breakpoint.name == names[-1]

    for name in reversed(names[:-1]):
        assert sim.move_to_previous_breakpoint() is True
        assert sim.breakpoint.name == name


def test_next_breakpoint_restart_wraps(sim):
    sim.step_loop(bp=len(sim.scenario.breakpoints) - 1)
    assert sim.move_to_next_breakpoint(restart=True) is True
    assert sim.breakpoint is sim.scenario.breakpoints[0]


def test_entering_breakpoint_seeds_state(sim):
    from so.data_model import TTCModes
    bp = sim.scenario.breakpoints[2]
    sim.spacecraft.state.ts = 0.0
    sim.ground_station.state.mode = TTCModes.X_Sup_HBR
    sim.step_loop(bp=bp.name)

    assert sim.spacecraft.state.ts == datetime.fromisoformat(bp.begin).timestamp()
    assert sim.ground_station.breakpoint is bp
    assert sim.ground_station.state.mode == bp.gs_initial_state["mode"]


def test_dispatch_breakpoint_commands_jump_ts(sim):
    from types import SimpleNamespace
    env = SimpleNamespace(now=123.0)
    names = _names(sim)
    sim._running = True
    try:
        def dispatch(action, **params):
            cmd = {"action": action, "params": params}
            sim._dispatch_cmd(cmd, env)
            return cmd["result"]

        def sim_ts():
            return env.now + sim._ts_offset

        result = dispatch("next_breakpoint")
        assert result["success"] is True and result["breakpoint"]["name"] == names[1]
        assert sim_ts() == datetime.fromisoformat(sim.breakpoint.begin).timestamp()

        result = dispatch("previous_breakpoint")
        assert result["success"] is True and result["breakpoint"]["name"] == names[0]
        assert dispatch("previous_breakpoint")["status"] == "no_previous_breakpoint"

        assert dispatch("step", breakpoint=names[-1])["success"] is True
        assert sim.breakpoint.name == names[-1]
        assert sim_ts() == datetime.fromisoformat(sim.breakpoint.begin).timestamp()
        assert dispatch("next_breakpoint")["status"] == "no_next_breakpoint"

        bad = dispatch("step", breakpoint="no_such_pass")
        assert bad["success"] is False and "no_such_pass" in bad["error"]
        assert sim.breakpoint.name == names[-1]

        assert dispatch("bogus")["success"] is False
    finally:
        sim._running = False


@pytest.mark.parametrize("bp", ["no_such_pass", 99, -1])
def test_step_loop_unknown_breakpoint(sim, bp):
    before = sim.breakpoint
    with pytest.raises(ValueError):
        sim.step_loop(bp=bp)
    assert sim.breakpoint is before


def test_step_loop_by_name_and_index(sim):
    last = sim.scenario.breakpoints[-1]
    sim.step_loop(bp=last.name)
    assert sim.breakpoint is last
    sim.step_loop(bp=0)
    assert sim.breakpoint is sim.scenario.breakpoints[0]


# ---- Loop lifecycle ----

def test_start_reports_failures(sim):
    assert sim._handle_start_command({"breakpoint": "no_such_pass"})["success"] is False
    assert not sim._running
    sim.time_factor = 0.01
    try:
        assert sim._handle_start_command({"breakpoint": 0})["success"] is True
        assert sim._handle_start_command({"breakpoint": 0})["status"] == "already_running"
    finally:
        sim.stop_loop()


def test_restart_during_long_tick_runs_one_thread(sim, monkeypatch):
    """A thread sleeping past stop_loop's join timeout must exit on waking after a restart, not run alongside."""
    import so.core
    ticks_by_thread = {}
    real_update = so.core.GroundStationSim.update

    def counting_update(self, *args, **kwargs):
        name = threading.current_thread().name
        ticks_by_thread[name] = ticks_by_thread.get(name, 0) + 1
        return real_update(self, *args, **kwargs)

    monkeypatch.setattr(so.core.GroundStationSim, "update", counting_update)
    sim.time_factor = 2.0  # 2 s of wall-clock sleep per tick
    sim.start_loop()
    old_thread = sim._thread
    assert wait_for(lambda: ticks_by_thread.get(old_thread.name) == 1)

    # stop_loop's join gives up while the thread is still asleep
    real_join = threading.Thread.join
    with monkeypatch.context() as m:
        m.setattr(threading.Thread, "join", lambda self, timeout=None: real_join(self, 0.05))
        sim.stop_loop()
    assert old_thread.is_alive()

    sim.time_factor = 0.01
    sim.start_loop()
    new_thread = sim._thread
    try:
        old_thread.join(timeout=5)
        assert not old_thread.is_alive()
        assert ticks_by_thread[old_thread.name] == 1
        assert wait_for(lambda: ticks_by_thread.get(new_thread.name, 0) > 2)
        assert sim._running and new_thread.is_alive()
    finally:
        sim.stop_loop()


def test_tick_exception_stops_sim(make_sim):
    sim = make_sim("data/demo.json", time_factor=0.01)

    def boom(*_args, **_kwargs):
        raise RuntimeError("tick failed")

    sim.ground_station.update = boom
    sim.start_loop()
    sim._thread.join(timeout=5)

    assert not sim._thread.is_alive()
    assert sim._running is False
    assert "tick failed" in sim._last_error

    # commands fail fast instead of timing out against a dead thread
    t0 = time.monotonic()
    result = sim._send_cmd("next_breakpoint")
    assert result["success"] is False
    assert time.monotonic() - t0 < 1


def test_sim_runs_without_minio(make_sim):
    sim = make_sim("data/demo.json", time_factor=0.01)
    bp = sim.scenario.breakpoints[0]
    sim.start_loop()
    try:
        # jump to just before the breakpoint end so the pass-end FD product is created
        end = datetime.fromisoformat(bp.end).timestamp()
        with sim._lock:
            sim._ts_offset += end - 5 - (datetime.fromisoformat(bp.begin).timestamp())

        time.sleep(0.5)
        assert sim._running
        assert sim.products._fd_created

        t0 = time.monotonic()
        result = sim._send_cmd("next_breakpoint")
        assert result["success"] is True, result
        assert time.monotonic() - t0 < 1
        assert sim._running
    finally:
        sim.stop_loop()


# ---- Command queue ----

def test_timed_out_command_never_runs(sim, monkeypatch):
    calls = []
    monkeypatch.setattr(sim, "_do_control", lambda params: calls.append(params) or {"success": True})
    sim._running = True  # no loop thread: nothing drains the queue
    try:
        result = sim._send_cmd("control", {"system": "ground_station"}, timeout=0.05)
        assert result == {"success": False, "error": "Command timed out"}

        # the sim thread gets to it after the caller gave up: it must not run
        cmd = sim._command_queue.get_nowait()
        sim._dispatch_cmd(cmd, env=None)
        assert not calls
        assert cmd["result"] is None
    finally:
        sim._running = False


def test_commands_run_within_a_long_tick(make_sim):
    # a tick lasts 20 s of wall time; commands must not wait for the next one
    sim = make_sim("data/demo.json", time_factor=20)
    sim.start_loop()
    try:
        time.sleep(0.3)
        t0 = time.monotonic()
        result = sim._send_cmd("control", {"system": "ground_station", "control": "power_ul", "value": 60})
        assert result["success"] is True, result
        assert time.monotonic() - t0 < 1
        assert sim.ground_station.state.power_ul == 60.0
    finally:
        sim.stop_loop()


def test_pause_freezes_ts_and_broadcasts_once_per_tick(make_sim, monkeypatch):
    # 0.3 s of wall time per tick, polled in 3 slices
    sim = make_sim("data/demo.json", time_factor=0.3)
    sent = []
    monkeypatch.setattr(sim._socket_server, "broadcast", lambda data: sent.append(data["ts"]))
    sim.start_loop()
    try:
        assert wait_for(lambda: len(sent) >= 2)
        sim.pause_loop()
        time.sleep(0.4)
        frozen = sim.spacecraft.state.ts
        count = len(sent)
        time.sleep(1.5)  # 5 ticks
        assert 3 <= len(sent) - count <= 7
        assert set(sent[count:]) == {frozen}

        sim.resume_loop()
        assert wait_for(lambda: len(set(sent)) >= len(set(sent[:count])) + 2)
    finally:
        sim.stop_loop()

    ticks = sorted(set(sent))
    # integer timestamps, one second apart: pausing did not skew or skip the clock
    assert all(ts == int(ts) for ts in ticks)
    assert all(b - a == 1 for a, b in zip(ticks, ticks[1:]))


def test_tle_whitespace_line_is_skipped_everywhere():
    """Validation and the TLE consumers (AOCS, ground station) split the TLE the same way."""
    from so.core import _check_tle
    from so.data_model import Scenario
    from so.sys.aocs import AOCSMin
    name, l1, l2 = Scenario().tle.split("\n")
    tle = f"{name}\n   \n{l1}\n\t\n{l2}\n"
    _check_tle(tle)
    aocs = AOCSMin()
    aocs.init(Scenario(tle=tle))
    assert aocs.satellite.name == name
    assert aocs.satellite.model.satnum == 44878
