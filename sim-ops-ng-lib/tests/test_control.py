import time

import pytest



@pytest.fixture
def link_up(sim):
    """Sim marked running with the uplink released and the downlink in frame lock."""
    from so.data_model import Status, TTCState
    gs = sim.ground_station.state
    gs.carrier_ul = Status.on
    gs.sweep_done = True
    gs.power_ul = 50.0
    gs.band_ul = "S"
    gs.status_dl = TTCState.FRAME_LOCK
    sc = sim.spacecraft.state
    sc.ttc_s_rx_status = Status.on
    sc.ttc_mcu = Status.nominal
    sc.dhs_obsw_mode = Status.nominal
    sim._object_store = None
    sim._running = True
    yield sim
    sim._running = False


def _tc(control, value, command="TC_XXX_001"):
    return {"system": "spacecraft", "command": command, "control": control, "value": value}


# ---- Command acks: SimOps._do_control ----

def test_ack_sim_not_running(sim):
    result = sim._do_control(_tc("dhs_memory", "10"))
    assert result["status"] == "r:REL r:ACC r:EXE"
    assert result["success"] is False


def test_ack_unknown_system(link_up):
    result = link_up._do_control({"system": "moon", "control": "x", "value": "y"})
    assert result["success"] is False
    assert "moon" in result["error"]


def test_ack_nominal(link_up):
    assert link_up._do_control(_tc("aocs_mode", "SUN"))["status"] == "g:REL g:ACC g:EXE"


@pytest.mark.parametrize("block", ["no_tc_override", "carrier_off", "no_sweep"])
def test_ack_not_released(link_up, block):
    from so.data_model import Status
    if block == "no_tc_override":
        link_up.gs_overrides["no_tc"] = True
    elif block == "carrier_off":
        link_up.ground_station.state.carrier_ul = Status.off
    else:
        link_up.ground_station.state.sweep_done = False
    assert link_up._do_control(_tc("aocs_mode", "SUN"))["status"] == "r:REL r:ACC r:EXE"


def test_ack_egse_skips_carrier_and_sweep(link_up):
    from so.data_model import DataProxy, Status
    link_up.data_proxy = DataProxy.EGSE
    link_up.ground_station.state.carrier_ul = Status.off
    link_up.ground_station.state.sweep_done = False
    assert link_up._do_control(_tc("aocs_mode", "SUN"))["status"] == "g:REL g:ACC g:EXE"


def test_ack_low_uplink_power(link_up):
    link_up.ground_station.state.power_ul = 49.0
    assert link_up._do_control(_tc("aocs_mode", "SUN"))["status"] == "g:REL r:ACC r:EXE"


def test_ack_receiver_off_is_unknown(link_up):
    from so.data_model import AOCSTarget, Status
    sc = link_up.spacecraft.state
    sc.ttc_s_rx_status = Status.off
    sc.aocs_mode = AOCSTarget.NADIR
    assert link_up._do_control(_tc("aocs_mode", "SUN"))["status"] == "g:REL u:ACC u:EXE"
    # never reached the spacecraft
    assert sc.aocs_mode == AOCSTarget.NADIR


def test_ack_receiver_for_uplink_band(link_up):
    """The receiver that matters is the one for the ground station's uplink band."""
    from so.data_model import Status
    sc = link_up.spacecraft.state
    link_up.ground_station.state.band_ul = "X"
    sc.ttc_s_rx_status = Status.on
    sc.ttc_x_rx_status = Status.off
    assert link_up._do_control(_tc("aocs_mode", "SUN"))["status"] == "g:REL u:ACC u:EXE"
    sc.ttc_x_rx_status = Status.on
    assert link_up._do_control(_tc("aocs_mode", "SUN"))["status"] == "g:REL g:ACC g:EXE"


def test_ack_mcu_error_only_hptc(link_up):
    from so.core import HPTC
    from so.data_model import Status
    link_up.spacecraft.state.ttc_mcu = Status.error

    assert link_up._do_control(_tc("aocs_mode", "SUN"))["status"] == "g:REL u:ACC u:EXE"
    result = link_up._do_control(_tc("ttc_ping", None, command=HPTC[0]))
    assert result["status"] == "g:REL g:ACC g:EXE"


def test_ack_trigger_safe_mode_ignores_link(link_up):
    from so.data_model import Status
    link_up.gs_overrides["no_tc"] = True
    link_up.ground_station.state.carrier_ul = Status.off
    result = link_up._do_control(_tc("trigger_safe_mode", None))
    assert result["status"].startswith("g:REL")
    assert link_up.spacecraft.state.dhs_obsw_mode == Status.safe


# ---- Command acks: SpacecraftSim.control ----

def test_spacecraft_control_invalid_value_is_red(link_up):
    assert link_up._do_control(_tc("aocs_mode", "SIDEWAYS"))["status"] == "g:REL g:ACC r:EXE"


def test_spacecraft_control_unknown_subsystem_is_red(link_up):
    assert link_up._do_control(_tc("warp_drive", "on"))["status"] == "g:REL g:ACC r:EXE"


def test_spacecraft_control_missing_name_is_red(sim):
    assert sim.spacecraft.control({"value": "x"})["status"] == "g:REL g:ACC r:EXE"


def test_spacecraft_control_exception_is_red(sim, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("bus failure")
    monkeypatch.setattr(sim.spacecraft.aocs, "command", boom)
    assert sim.spacecraft.control({"control": "aocs_mode", "value": "SUN"})["status"] == "g:REL g:ACC r:EXE"


def test_spacecraft_control_without_frame_lock_is_unknown(link_up):
    from so.data_model import AOCSTarget, TTCState
    link_up.ground_station.state.status_dl = TTCState.BIT_LOCK
    assert link_up._do_control(_tc("aocs_mode", "SUN"))["status"] == "g:REL u:ACC u:EXE"
    # it did execute; only the confirmation is missing
    assert link_up.spacecraft.state.aocs_mode == AOCSTarget.SUN


def test_spacecraft_control_without_gs_is_green(sim):
    assert sim.spacecraft.control({"control": "aocs_mode", "value": "SUN"})["status"] == "g:REL g:ACC g:EXE"


# ---- TC stack and archive ----

def test_tc_execute_records_ack(link_up):
    link_up.tc_stack = [_tc("aocs_mode", "SIDEWAYS", command="TC_AOCS_001")]
    result = link_up._do_tc_execute()
    assert result == {"success": True, "status": "g:REL g:ACC r:EXE", "command": "TC_AOCS_001"}
    assert link_up.tc_history[0]["status"] == "g:REL g:ACC r:EXE"
    assert link_up._do_tc_execute() == {"success": False, "error": "Stack empty"}


def test_rejected_tc_not_archived(sim):
    from so.data_model import Status
    stored = []
    sim._object_store = object()
    sim._store_tc_packet = lambda command, value: stored.append(command)
    sim._running = True
    try:
        # no uplink carrier: rejected on the ground
        sim.ground_station.state.carrier_ul = Status.off
        result = sim._do_control({"system": "spacecraft", "command": "TC_DHS_001",
                                  "control": "dhs_memory", "value": "10"})
        assert result["status"].startswith("r:REL")
        assert not stored

        # link up: released and archived
        sim.ground_station.state.carrier_ul = Status.on
        sim.ground_station.state.sweep_done = True
        result = sim._do_control({"system": "spacecraft", "command": "TC_DHS_001",
                                  "control": "dhs_memory", "value": "10"})
        assert result["status"].startswith("g:REL")
        assert stored == ["dhs_memory"]
    finally:
        sim._running = False


# ---- Overrides ----

@pytest.mark.parametrize("attr, value, expected", [
    ("ttc_mode", "X_Sup_LBR", "X_Sup_LBR"),
    ("aocs_mode", "SUN", "SUN"),
    ("eps_sol_array", "on", "on, on"),
    ("dhs_memory", "42", "42.0"),
    ("max_status_dl", "BIT_LOCK", "BIT_LOCK"),
    ("max_c_no_dl", "55", "55.0"),
    ("no_tm", "yes", "True"),
])
def test_override_valid_values(sim, attr, value, expected):
    assert sim._do_set_override({"attr": attr, "value": value}) == {"attr": attr, "value": expected}
    assert [attr, expected] in sim._handle_get_overrides({})["overrides"]


def test_valid_overrides_converted(sim):
    from so.data_model import TTCModes, TTCState
    assert sim._do_set_override({"attr": "ttc_mode", "value": "X_Sup_LBR"})["value"] == "X_Sup_LBR"
    assert sim.sc_overrides["ttc_mode"] == TTCModes.X_Sup_LBR
    sim._do_set_override({"attr": "max_status_dl", "value": "PLL_LOCK"})
    assert sim.gs_overrides["max_status_dl"] == TTCState.PLL_LOCK
    sim._do_set_override({"attr": "eps_battery_dod", "value": "72.5"})
    assert sim.sc_overrides["eps_battery_dod"] == 72.5
    sim._do_set_override({"attr": "no_tc", "value": "true"})
    assert sim.gs_overrides["no_tc"] is True


@pytest.mark.parametrize("attr, value", [
    ("", "x"),
    ("no_such_field", "1"),
    ("dhs_memory", "lots"),
    ("dhs_memory", "nan"),
    ("max_eb_no_dl", "inf"),
    ("no_tc", "maybe"),
    ("eps_sol_array", "sideways"),
])
def test_override_invalid_values(sim, attr, value):
    with pytest.raises(ValueError):
        sim._do_set_override({"attr": attr, "value": value})
    assert not sim.sc_overrides and not sim.gs_overrides


@pytest.mark.parametrize("attr, value", [
    ("ttc_mode", "foo"),
    ("aocs_mode", "SIDEWAYS"),
    ("status_dl", "LOCKED"),
    ("max_c_no_dl", "high"),
    ("max_eb_no_dl", "nan"),
    ("no_tm", "maybe"),
    ("eps_battery_dod", "lots"),
    ("not_a_field", "1"),
    # enum fields only the ground station has: no override applies them
    ("carrier_ul", "on"),
    ("mode", "S_Sup_LBR"),
    ("ul_state", "BIT_LOCK"),
])
def test_invalid_override_rejected(sim, attr, value):
    with pytest.raises(ValueError):
        sim._do_set_override({"attr": attr, "value": value})
    assert attr not in sim.sc_overrides and attr not in sim.gs_overrides


def test_invalid_override_rejected_while_running(sim):
    sim.time_factor = 0.01
    sim.start_loop()
    try:
        result = sim._handle_set_override({"attr": "ttc_mode", "value": "foo"})
        assert result["success"] is False
        assert "ttc_mode" not in sim.sc_overrides
        time.sleep(0.2)
        assert sim._running  # the next ticks still run
    finally:
        sim.stop_loop()


def test_admin_panel_override_options_all_accepted(sim):
    """Every attribute/value offered by the admin panel's override form converts."""
    import re
    with open("so/templates/control.html", encoding="utf-8") as fin:
        html = fin.read()
    block = html[html.index("const OVERRIDE_OPTIONS"):]
    block = block[:block.index("};")]
    entries = re.findall(r"^\s*(\w+):\s*(null|\[[^\]]*\])", block, re.M)
    assert entries
    for attr, options in entries:
        values = ["1.5"] if options == "null" else re.findall(r"'([^']*)'", options)
        for value in values:
            sim._do_set_override({"attr": attr, "value": value})


def test_override_routing(sim):
    sim._do_set_override({"attr": "no_tc", "value": "true"})
    sim._do_set_override({"attr": "ttc_mode", "value": "X_Sup_LBR"})
    assert set(sim.gs_overrides) == {"no_tc"}
    assert set(sim.sc_overrides) == {"ttc_mode"}


def test_override_applied_and_restored(sim):
    from so.data_model import TTCModes
    sc = sim.spacecraft
    original = sc.state.ttc_mode
    ts = sc.state.ts

    sim._do_set_override({"attr": "ttc_mode", "value": "X_Sup_HBR"})
    sc.update(ts + 1, overrides=sim.sc_overrides)
    assert sc.state.ttc_mode == TTCModes.X_Sup_HBR

    sim._do_unset_override({"attr": "ttc_mode"})
    sc.update(ts + 2, overrides=sim.sc_overrides)
    assert sc.state.ttc_mode == original


def test_override_wins_over_command(link_up):
    from so.data_model import AOCSTarget
    sc = link_up.spacecraft
    link_up._do_set_override({"attr": "aocs_mode", "value": "SUN"})
    link_up._do_control(_tc("aocs_mode", "NADIR"))
    sc.update(sc.state.ts + 1, gs_state=link_up.ground_station.state, overrides=link_up.sc_overrides)
    assert sc.state.aocs_mode == AOCSTarget.SUN


def test_unset_override(sim):
    sim._do_set_override({"attr": "no_tm", "value": "true"})
    assert sim._do_unset_override({"attr": "no_tm"}) == {"attr": "no_tm"}
    assert "no_tm" not in sim.gs_overrides
    # unsetting something that isn't set is fine
    sim._do_unset_override({"attr": "no_tm"})
    with pytest.raises(ValueError):
        sim._do_unset_override({"attr": " "})


def test_no_tm_override_drops_downlink(sim):
    from so.data_model import TTCState
    gs = sim.ground_station
    gs.update(gs.state.ts, sc_state=sim.spacecraft.state, overrides={"no_tm": True})
    assert gs.state.status_dl == TTCState.NO_RF
    assert gs.state.ov_no_tm is True


def test_tc_stack_delete_out_of_range(link_up):
    link_up._handle_tc_stack_push(_tc("aocs_mode", "SUN", command="TC_AOCS_001"))
    for index in (1, -1, "0"):
        result = link_up._handle_tc_stack_delete({"index": index})
        assert result["success"] is False and "No TC at index" in result["error"]
    assert len(link_up.tc_stack) == 1
    assert link_up._handle_tc_stack_delete({"index": 0}) == {"success": True}
    assert link_up.tc_stack == []


def test_tc_send_runs_given_tc_not_stack_head(link_up):
    link_up._handle_tc_stack_push(_tc("aocs_mode", "SUN", command="TC_AOCS_001"))
    upload = _tc("dhs_uploaded", "fd > x", command="UP: fd > x")
    cmd = {"action": "tc_send", "params": upload}
    link_up._dispatch_cmd(cmd, env=None, now=0.0)

    assert cmd["result"]["command"] == "UP: fd > x"
    assert link_up.spacecraft.state.dhs_uploaded == ["fd > x"]
    assert [e["command"] for e in link_up.tc_stack] == ["TC_AOCS_001"]
    assert link_up.tc_history[0]["command"] == "UP: fd > x"


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_non_finite_values_rejected(link_up, value):
    import math
    for control in ("eps_battery_dod", "dhs_memory"):
        assert link_up._do_control(_tc(control, value))["status"] == "g:REL g:ACC r:EXE"
        result = link_up._do_admin_set_state({"attr": control, "value": value})
        assert result["success"] is False
    assert math.isfinite(link_up.spacecraft.state.eps_battery_dod)
    assert math.isfinite(link_up.spacecraft.state.dhs_memory)
    with pytest.raises(ValueError):
        link_up.ground_station.control({"control": "power_ul", "value": value})


@pytest.mark.parametrize("value", [-1e6, -0.1, 70.1, 1e308])
def test_power_ul_out_of_range_rejected(link_up, value):
    gs = link_up.ground_station
    assert gs.control({"control": "power_ul", "value": value}) == {"status": "FAIL"}
    assert gs.state.power_ul == 50.0
    assert gs.control({"control": "power_ul", "value": 70})["status"] == "OK"


def test_tc_archive_names_are_unique(link_up):
    stored = []
    link_up._object_store = type("Store", (), {"store": lambda self, b, name, data: stored.append(name)})()
    for _ in range(3):  # same second
        link_up._store_tc_packet("aocs_mode", "SUN")
    assert len(set(stored)) == 3
    assert all(int(name.split("-")[0]) == int(link_up.spacecraft.state.ts) for name in stored)


def test_dhs_uploaded_is_capped(link_up):
    for i in range(15):
        link_up._do_control(_tc("dhs_uploaded", f"fd > {i}"))
    assert link_up.spacecraft.state.dhs_uploaded == [f"fd > {i}" for i in range(5, 15)]
