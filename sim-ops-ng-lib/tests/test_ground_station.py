import json

import pytest



# ---- Flight dynamics ----

def test_flight_dynamics_reset_per_breakpoint(sim):
    sim.ground_station.state.flight_dynamics = [[1.0, 2.0, 3.0, 0.0, 0.0]]
    assert sim.move_to_next_breakpoint()
    assert sim.ground_station.state.flight_dynamics == []


def test_flight_dynamics_product_holds_only_its_pass(sim):
    """The MCS Flight Dynamics tab lists these products: each must hold its own pass only."""
    from types import SimpleNamespace
    from so.core import Products
    stored = {}
    store = SimpleNamespace(store=lambda bucket, name, data: stored.setdefault(name, data))
    sim.products = Products(store)
    sim._running = True
    env = SimpleNamespace(now=0.0)
    first, second = sim.scenario.breakpoints[0], sim.scenario.breakpoints[1]
    try:
        sim.ground_station.state.flight_dynamics = [[1.0, 2.0, 3.0, 500.0, 0.0]]
        sim._dispatch_cmd({"action": "next_breakpoint", "params": {}}, env)
        assert sim.breakpoint is second

        sim.ground_station.state.flight_dynamics.append([4.0, 5.0, 6.0, 0.0, 1.5])
        sim._dispatch_cmd({"action": "next_breakpoint", "params": {}}, env)
    finally:
        sim._running = False

    products = {name: json.loads(data) for name, data in stored.items()}
    by_bp = {p["id"].rsplit("-", 1)[0]: p for p in products.values()}
    assert by_bp[first.name]["data"] == [[1.0, 2.0, 3.0, 500.0, 0.0]]
    assert by_bp[first.name]["validity"] == 1
    assert by_bp[second.name]["data"] == [[4.0, 5.0, 6.0, 0.0, 1.5]]
    assert by_bp[second.name]["validity"] == 1


def test_flight_dynamics_not_broadcast(sim, monkeypatch):
    sent = []
    monkeypatch.setattr(sim._socket_server, "broadcast", sent.append)
    sim.ground_station.state.flight_dynamics = [[1.0, 2.0, 3.0, 0.0, 0.0]]
    sim._broadcast_state()
    assert "flight_dynamics" not in sent[-1]["ground_station"]


# ---- Spectrum ----

@pytest.mark.parametrize("coherent, expected", [("enabled", True), ("disabled", False)])
def test_downlink_spectrum_coherent_flag(sim, monkeypatch, coherent, expected):
    """Two-way Doppler on the downlink only with a coherent transponder (Status is always truthy)."""
    from so.data_model import Status, SpacecraftState
    gs = sim.ground_station
    calls = []
    real = gs.spectrum_gen.downlink_spectrum

    def spy(*args, **kwargs):
        calls.append(kwargs["coherent"])
        return real(*args, **kwargs)

    monkeypatch.setattr(gs.spectrum_gen, "downlink_spectrum", spy)
    gs._update_spectrums(gs.state, SpacecraftState(ttc_coherent=Status[coherent]))
    assert calls == [expected]


@pytest.mark.parametrize("mode_name", ["S_Sup_LBR", "X_Sup_HBR", "S_Sub_LBR", "X_Res_LBR"])
def test_spectra_centred_on_link_budget_frequencies(sim, mode_name):
    """The spectrum display uses the same carriers that freq_ul_mhz/freq_dl_mhz report."""
    from so.data_model import TTCModes
    from so.rf_link import CCSDS_FREQ_TABLE, ul_mode
    mode = TTCModes[mode_name]
    gen = sim.ground_station.spectrum_gen
    freqs, _ = gen.downlink_spectrum(mode)
    assert freqs[0] < CCSDS_FREQ_TABLE[mode]["dl_freq_mhz"] < freqs[-1]
    band = mode_name[0]
    freqs, _ = gen.uplink_spectrum(mode, band=band)
    assert freqs[0] < CCSDS_FREQ_TABLE[ul_mode(mode, band)]["ul_freq_mhz"] < freqs[-1]
