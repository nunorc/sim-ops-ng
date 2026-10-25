import struct
from datetime import datetime

import pytest



# ---- Subsystems ----

def test_aocs_angle_parallel_and_antiparallel_vectors():
    import warnings
    import numpy as np
    from so.sys.aocs import AOCSMin
    aocs = AOCSMin()
    # these unit vectors' dot product rounds to just past +/-1
    v = np.array([0.1, 1.0, 0.7])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert aocs._aocs_calc_angle(v, v * 3) == pytest.approx(0.0, abs=1e-6)
        assert aocs._aocs_calc_angle(v, -3 * v) == pytest.approx(180.0)


def test_aocs_euler_angles_parallel_and_antiparallel_vectors():
    """No NaN: json.dumps would emit it and the MCS/3dv would drop the whole state message."""
    import warnings
    import numpy as np
    from so.sys.aocs import AOCSMin
    aocs = AOCSMin()
    v = np.array([0.1, 1.0, 0.7])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert aocs._aocs_euler_angles(v, v * 3) == pytest.approx([0.0, 0.0, 0.0], abs=1e-6)
        x = np.array([1.0, 0.0, 0.0])
        for v1, v2 in ((v, -3 * v), (x, -x)):
            angles = aocs._aocs_euler_angles(v1, v2)
            assert np.all(np.isfinite(angles))
            # a 180 deg rotation, whichever perpendicular axis was picked
            assert np.max(np.abs(angles)) > 90


def test_tm_tc_history_timestamps_are_utc(sim):
    from so.data_model import BusMessage
    ts = datetime.fromisoformat("2023-08-27 04:40:00+00:00").timestamp()
    state = sim.spacecraft.state
    state.ts = ts
    sim.spacecraft.bus.send(state, BusMessage("gs", "dhs", {"command": "dhs_memory", "value": "10"}))
    assert "2023-08-27T04:40:00\t" in state.dhs_tc_history[0]

    state = sim.spacecraft.dhs.update(state, ts)
    assert "2023-08-27T04:40:00 TM Packet" in state.dhs_tm_window[0]


@pytest.mark.parametrize("command", ["pl_gnss_status", "pl_camera_status", "pl_sdr_status"])
def test_payload_rejects_invalid_values(sim, command):
    from so.data_model import BusMessage, Status
    state = sim.spacecraft.state
    state.dhs_obsw_mode = Status.nominal
    before = getattr(state, command)
    message = BusMessage("gs", "pl", {"command": command, "value": "bogus"})
    assert sim.spacecraft.payload.command(state, message) is False
    assert getattr(state, command) == before
    assert sim.spacecraft.payload.command(state, BusMessage("gs", "pl", {"command": command, "value": "on"})) is True
    assert getattr(state, command) == Status.on


def test_memory_packet_count_follows_dump_rate(sim):
    from so.data_model import TTCModes
    from so.sys.dhs import DHSMin

    def packets(mode):
        state = sim.spacecraft.state
        state.dhs_mem_dump_enabled = True
        state.dhs_memory = 50.0
        state.dhs_tm_window = []
        state.ttc_mode = mode
        state = sim.spacecraft.dhs.update(state, state.ts + 1)
        return sum("Memory Packet" in line for line in state.dhs_tm_window)

    counts = {mode: packets(mode) for mode in TTCModes}
    assert all(n >= 1 for n in counts.values())
    # a faster dump never shows fewer packets than a slower one
    for a in TTCModes:
        for b in TTCModes:
            if DHSMin._dump_rate(a) > DHSMin._dump_rate(b):
                assert counts[a] >= counts[b], (a, b, counts)
    assert counts[TTCModes.S_Sup_HBR] == 2 * counts[TTCModes.S_Sup_LBR]


# ---- Data model ----

def test_data_model_field_types():
    from so.core import _STATE_ENUM_FIELDS
    from so.data_model import GroundStationState

    assert "pl_gnss_pos" not in _STATE_ENUM_FIELDS
    assert isinstance(GroundStationState().flight_dynamics, list)


# ---- Space packets ----

def test_space_packet_is_big_endian_and_round_trips():
    from so.data_model import SpacecraftState
    from so.utils import SpacePacketHandler
    handler = SpacePacketHandler()
    state = SpacecraftState(ts=1693111200.0, dhs_tm_counter=258)

    data = handler.as_byte_string(state)
    assert len(data) == struct.calcsize(handler.fmt)
    assert data[:4] == int(state.ts).to_bytes(4, "big")

    decoded = handler.as_dict(handler.from_bytestream(handler.space_packet(state).as_bytes()))
    assert decoded["payload"]["ts"] == int(state.ts)
    assert decoded["payload"]["dhs_tm_counter"] == 258
    assert decoded["payload"]["ttc_mode"] == state.ttc_mode.name.upper()


def test_legacy_native_space_packet_still_decodes():
    from minsp import SpacePacket
    from so.data_model import SpacecraftState
    from so.utils import SpacePacketHandler
    handler = SpacePacketHandler()
    state = SpacecraftState(ts=1693111200.0, dhs_tm_counter=258)
    legacy = struct.pack(handler._legacy_fmt, *struct.unpack(handler.fmt, handler.as_byte_string(state)))

    decoded = handler.as_dict(SpacePacket(apid=10, data_field=legacy))
    assert decoded["payload"]["ts"] == int(state.ts)
    assert decoded["payload"]["dhs_tm_counter"] == 258
