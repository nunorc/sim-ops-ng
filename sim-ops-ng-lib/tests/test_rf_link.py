import math
from datetime import datetime

import pytest



# ---- Link budget building blocks ----

def test_fspl_known_value_and_inverse_square():
    from so.rf_link import compute_fspl
    # 1000 km at 2245 MHz: 20log(1000) + 20log(2245) + 32.44
    assert compute_fspl(1000, 2245) == pytest.approx(159.46, abs=0.01)
    assert compute_fspl(2000, 2245) - compute_fspl(1000, 2245) == pytest.approx(6.02, abs=0.01)
    assert compute_fspl(1000, 8450) > compute_fspl(1000, 2245)
    assert compute_fspl(0, 2245) == math.inf
    assert compute_fspl(None, 2245) == math.inf


def test_atmospheric_loss():
    from so.rf_link import compute_atmospheric_loss, ATM_MIN_ELEVATION_DEG
    zenith = compute_atmospheric_loss(90, 2000)
    assert zenith == pytest.approx(0.3 + 0.1 * 2.0)
    assert compute_atmospheric_loss(30, 2000) == pytest.approx(2 * zenith)
    # falls with elevation
    losses = [compute_atmospheric_loss(el, 8400) for el in (5, 10, 30, 60, 90)]
    assert losses == sorted(losses, reverse=True)
    # clamped (and continuous across AOS) below the minimum elevation
    clamped = compute_atmospheric_loss(ATM_MIN_ELEVATION_DEG, 2000)
    for el in (4.9, 1.0, 0.0, -3.0, None):
        assert compute_atmospheric_loss(el, 2000) == pytest.approx(clamped)
    assert clamped < 10


def test_antenna_gain():
    from so.rf_link import compute_antenna_gain
    # 4 m dish at S-band, 55% efficiency: ~36.9 dBi
    assert compute_antenna_gain(4.0, 2245) == pytest.approx(36.9, abs=0.1)
    assert compute_antenna_gain(8.0, 2245) - compute_antenna_gain(4.0, 2245) == pytest.approx(6.02, abs=0.01)
    assert compute_antenna_gain(4.0, 8450) > compute_antenna_gain(4.0, 2245)
    assert compute_antenna_gain(0, 2245) == 0.0
    assert compute_antenna_gain(None, 2245) == 0.0


def test_pointing_and_polarization_loss():
    from so.data_model import TTCAntenna
    from so.rf_link import (
        compute_pointing_loss, compute_polarization_loss, POINTING_LOSS_MAX_DB, POINTING_LOSS_ELEVATION_DEG
    )
    assert compute_pointing_loss(None) == POINTING_LOSS_MAX_DB
    assert compute_pointing_loss(-1) == POINTING_LOSS_MAX_DB
    assert compute_pointing_loss(POINTING_LOSS_ELEVATION_DEG / 2) == pytest.approx(POINTING_LOSS_MAX_DB / 2)
    assert compute_pointing_loss(POINTING_LOSS_ELEVATION_DEG) == 0.0
    assert compute_pointing_loss(45) == 0.0

    assert compute_polarization_loss(TTCAntenna.LGA_RHC) == 0.0
    assert compute_polarization_loss(TTCAntenna.LGA_LHC) == 0.0
    assert 0 < compute_polarization_loss(TTCAntenna.MGA) < compute_polarization_loss(TTCAntenna.HGA)


def test_c_no_eb_no_margin_chain():
    from so.rf_link import compute_c_no, compute_eb_no, compute_link_margin, BOLTZMANN_DBW
    c_no = compute_c_no(eirp_dbw=10, fspl_db=160, atm_loss_db=1, pol_loss_db=0.5, pointing_loss_db=0.5,
                        g_over_t_db=15)
    assert c_no == pytest.approx(10 - 160 - 1 - 0.5 - 0.5 + 15 - BOLTZMANN_DBW)
    assert compute_eb_no(c_no, 1_000_000) == pytest.approx(c_no - 60)
    assert compute_eb_no(c_no, 1_000_000, mod_loss_db=3) == pytest.approx(c_no - 63)
    assert compute_eb_no(c_no, 0) == pytest.approx(c_no)
    assert compute_link_margin(eb_no_db=10, required_eb_no_db=9.6, coding_gain_db=5.1) == pytest.approx(5.5)


def test_ber_fer():
    from so.rf_link import compute_ber, compute_fer
    # coherent BPSK needs ~9.6 dB Eb/N0 for BER 1e-5
    assert compute_ber(9.6) == pytest.approx(1e-5, rel=0.3)
    assert compute_ber(-128) == pytest.approx(0.5, abs=1e-6)
    bers = [compute_ber(x) for x in range(-5, 15)]
    assert bers == sorted(bers, reverse=True)

    assert compute_fer(0.0) == 0.0
    assert compute_fer(0.5) == pytest.approx(1.0)
    assert compute_fer(1e-5) == pytest.approx(1 - (1 - 1e-5) ** 8192)
    assert compute_fer(-1) == 0.0 and compute_fer(2) == 1.0


def test_doppler_shift():
    from so.rf_link import compute_doppler_shift, C
    assert compute_doppler_shift(7.0, 2245) == pytest.approx(7000 / C * 2245)
    assert compute_doppler_shift(-7.0, 2245) == -compute_doppler_shift(7.0, 2245)
    assert compute_doppler_shift(None, 2245) == 0.0


def test_ccsds_tables_consistent():
    from so.data_model import TTCModes
    from so.rf_link import (
        CCSDS_FREQ_TABLE, TURNAROUND_RATIO, CODING_GAIN_TABLE, REQUIRED_EBNO_TABLE, CARRIER_MOD_LOSS_TABLE,
        SC_TX_POWER_DBW, ul_mode,
    )
    assert set(CCSDS_FREQ_TABLE) == set(TTCModes)
    for mode, row in CCSDS_FREQ_TABLE.items():
        band = mode.name[0]
        assert row["turnaround"] == TURNAROUND_RATIO[(band, band)]
        assert row["coding"] in CODING_GAIN_TABLE
        assert row["modulation"] in REQUIRED_EBNO_TABLE and row["modulation"] in CARRIER_MOD_LOSS_TABLE
        assert row["power_class"] in SC_TX_POWER_DBW
        # S-band around 2 GHz, X-band around 7-8.5 GHz
        assert (2000 < row["ul_freq_mhz"] < 2300) if band == "S" else (7000 < row["ul_freq_mhz"] < 8500)
        # a coherent turnaround of the uplink lands on the downlink frequency
        assert row["ul_freq_mhz"] * row["turnaround"] == pytest.approx(row["dl_freq_mhz"], rel=0.01)
        # the uplink band swap keeps the rest of the mode
        for ul_band in ("S", "X"):
            assert ul_mode(mode, ul_band).name == ul_band + mode.name[1:]


# ---- Downlink budget on the ground station ----

def _dl_budget(sim, elevation=30.0, distance=1000.0, overrides=None, **sc):
    from so.data_model import SpacecraftState
    gs = sim.ground_station
    state = gs.state
    sc_state = SpacecraftState(**sc)
    state.mode = sc_state.ttc_mode
    state.elevation = elevation
    state.distance = distance
    state.doppler_velocity = 0.0
    return gs._calc_link_budget_dl(state, sc_state, overrides or {})


def test_dl_budget_leo_pass_closes(sim):
    from so.data_model import TTCModes
    from so.rf_link import compute_ber
    state = _dl_budget(sim, ttc_mode=TTCModes.S_Sup_LBR)
    # a clear-sky LEO pass at 30 deg closes with some margin to spare, but not absurdly so
    assert 3 < state.link_margin_dl < 40
    assert 40 < state.c_no_dl < 100
    assert state.ber_dl == pytest.approx(compute_ber(state.eb_no_dl))
    assert state.dl_modulation == "BPSK"


def test_dl_budget_degrades_with_range_and_elevation(sim):
    from so.data_model import TTCModes
    near = _dl_budget(sim, ttc_mode=TTCModes.S_Sup_LBR, distance=800).link_margin_dl
    far = _dl_budget(sim, ttc_mode=TTCModes.S_Sup_LBR, distance=1600).link_margin_dl
    assert near - far == pytest.approx(6.02, abs=0.01)

    high = _dl_budget(sim, ttc_mode=TTCModes.S_Sup_LBR, elevation=60).link_margin_dl
    low = _dl_budget(sim, ttc_mode=TTCModes.S_Sup_LBR, elevation=1).link_margin_dl
    assert high > low


def test_dl_budget_bigger_dish_more_margin(sim):
    from so.data_model import TTCModes
    small = _dl_budget(sim, ttc_mode=TTCModes.S_Sup_LBR).link_margin_dl
    sim.ground_station.state.antenna_diameter_m *= 2
    big = _dl_budget(sim, ttc_mode=TTCModes.S_Sup_LBR).link_margin_dl
    assert big - small == pytest.approx(6.02, abs=0.01)


@pytest.mark.parametrize("case", ["tx_off", "below_horizon", "no_range", "band_mismatch", "x_hga"])
def test_dl_budget_no_link(sim, case):
    from so.data_model import Status, TTCAntenna, TTCModes
    from so.rf_link import NO_LINK_MARGIN, NO_LINK_BER, NO_LINK_FER
    kwargs = {"ttc_mode": TTCModes.S_Sup_LBR}
    geometry = {}
    if case == "tx_off":
        kwargs["ttc_s_tx_status"] = Status.off
    elif case == "below_horizon":
        geometry["elevation"] = -1.0
    elif case == "no_range":
        geometry["distance"] = None
    elif case == "x_hga":
        kwargs = {"ttc_mode": TTCModes.X_Sup_LBR, "ttc_x_tx_status": Status.on, "ttc_x_antenna": TTCAntenna.HGA}

    if case == "band_mismatch":
        from so.data_model import SpacecraftState
        state = sim.ground_station.state
        state.mode, state.elevation, state.distance = TTCModes.X_Sup_LBR, 30.0, 1000.0
        state = sim.ground_station._calc_link_budget_dl(state, SpacecraftState(**kwargs), {})
    else:
        state = _dl_budget(sim, **geometry, **kwargs)

    assert state.link_margin_dl == NO_LINK_MARGIN
    assert state.ber_dl == NO_LINK_BER and state.fer_dl == NO_LINK_FER


def test_dl_budget_ceiling_overrides(sim):
    from so.data_model import TTCModes
    base = _dl_budget(sim, ttc_mode=TTCModes.S_Sup_LBR)
    c_no, eb_no = base.c_no_dl, base.eb_no_dl

    capped = _dl_budget(sim, ttc_mode=TTCModes.S_Sup_LBR, overrides={"max_c_no_dl": c_no - 10})
    assert capped.c_no_dl == pytest.approx(c_no - 10)
    assert capped.eb_no_dl == pytest.approx(eb_no - 10)

    capped = _dl_budget(sim, ttc_mode=TTCModes.S_Sup_LBR, overrides={"max_eb_no_dl": eb_no - 4})
    assert capped.eb_no_dl == pytest.approx(eb_no - 4)
    assert capped.c_no_dl == pytest.approx(c_no - 4)

    # a ceiling above the real value changes nothing
    loose = _dl_budget(sim, ttc_mode=TTCModes.S_Sup_LBR, overrides={"max_c_no_dl": c_no + 10})
    assert loose.c_no_dl == pytest.approx(c_no)


# ---- Downlink lock state ----

@pytest.mark.parametrize("margin, expected", [
    (-128.0, "NO_RF"),
    (-5.0, "RF_DETECTED"),
    (-1.0, "RF_DETECTED"),
    (0.0, "PLL_LOCK"),
    (1.0, "PLL_LOCK"),
    (2.0, "BIT_LOCK"),
    (3.0, "BIT_LOCK"),
    (3.1, "FRAME_LOCK"),
    (20.0, "FRAME_LOCK"),
])
def test_status_dl_thresholds(sim, margin, expected):
    from so.data_model import Quality, SpacecraftState, TTCState
    state = sim.ground_station.state
    sc_state = SpacecraftState()
    state.mode = sc_state.ttc_mode
    state.link_margin_dl = margin
    state = sim.ground_station._update_status_dl(state, sc_state, {})
    assert state.status_dl == TTCState[expected]
    assert state.frame_quality == (Quality.good if expected == "FRAME_LOCK" else Quality.unknown)


def test_status_dl_mode_mismatch_is_no_rf(sim):
    from so.data_model import SpacecraftState, TTCModes, TTCState
    state = sim.ground_station.state
    state.mode = TTCModes.S_Sup_HBR
    state.link_margin_dl = 20.0
    state = sim.ground_station._update_status_dl(state, SpacecraftState(ttc_mode=TTCModes.S_Sup_LBR), {})
    assert state.status_dl == TTCState.NO_RF


@pytest.mark.parametrize("ceiling", ["RF_DETECTED", "PLL_LOCK", "BIT_LOCK"])
def test_status_dl_max_override(sim, ceiling):
    from so.data_model import SpacecraftState, TTCState
    state = sim.ground_station.state
    sc_state = SpacecraftState()
    state.mode = sc_state.ttc_mode
    state.link_margin_dl = 20.0
    state = sim.ground_station._update_status_dl(state, sc_state, {"max_status_dl": TTCState[ceiling]})
    assert state.status_dl == TTCState[ceiling]

    # a ceiling never raises a weaker lock
    state.link_margin_dl = -128.0
    state = sim.ground_station._update_status_dl(state, sc_state, {"max_status_dl": TTCState[ceiling]})
    assert state.status_dl == TTCState.NO_RF


def _run_pass(sim, bp, step=5):
    begin = datetime.fromisoformat(bp.begin).timestamp()
    end = datetime.fromisoformat(bp.end).timestamp()
    ts, samples = begin, []
    while ts <= end:
        gs = sim.ground_station.update(ts, sc_state=sim.spacecraft.state, overrides={})
        sim.spacecraft.update(ts, gs_state=gs, overrides={})
        samples.append((gs.elevation, gs.status_dl))
        ts += step
    return samples


@pytest.mark.parametrize("bp_index", range(4))
def test_status_dl_over_a_pass(sim, bp_index):
    """AOS climbs NO_RF -> ... -> FRAME_LOCK one state at a time, LOS walks back down."""
    from so.data_model import TTCState
    bp = sim.scenario.breakpoints[bp_index]
    sim.step_loop(bp=bp.name)
    samples = _run_pass(sim, bp)

    # collapse runs of the same state
    states = [samples[0][1]]
    for _el, status in samples[1:]:
        if status != states[-1]:
            states.append(status)

    peak = states.index(TTCState.FRAME_LOCK)
    rise, fall = states[:peak + 1], states[peak:]
    assert rise == sorted(rise) and fall == sorted(fall, reverse=True)
    assert rise[0] == TTCState.NO_RF and fall[-1] == TTCState.NO_RF
    # only one pass per breakpoint: a single rise and a single fall
    assert states.count(TTCState.FRAME_LOCK) == 1
    # no signal below the horizon, frame lock only above it
    for elevation, status in samples:
        if elevation is None or elevation < 0:
            assert status == TTCState.NO_RF
        if status == TTCState.FRAME_LOCK:
            assert elevation > 0


# ---- Uplink budget and lock state ----

def _ul(sim, margin=None, elevation=30.0, distance=1000.0, **gs_fields):
    """Run the TTC uplink with a given geometry; optionally force the uplink margin."""
    from so.data_model import GroundStationState, SpacecraftState, Status, TTCModes, TTCState
    fields = {"mode": TTCModes.S_Sup_LBR, "carrier_ul": Status.on, "sweep_done": True,
              "doppler_velocity": 0.0, "status_dl": TTCState.FRAME_LOCK, **gs_fields}
    gs = GroundStationState(elevation=elevation, distance=distance, **fields)
    ttc = sim.spacecraft.ttc
    if margin is not None:
        real = ttc._calculate_uplink_budget

        def forced(*args, **kwargs):
            return {**real(*args, **kwargs), "link_margin_ul": margin}
        ttc._calculate_uplink_budget = forced
    try:
        return ttc.update(SpacecraftState(ttc_coherent=Status.enabled), 0.0, gs)
    finally:
        ttc.__dict__.pop("_calculate_uplink_budget", None)


def test_ul_budget_leo_pass_closes(sim):
    state = _ul(sim)
    assert state.ttc_link_margin_ul > 3
    assert 2000 < state.ttc_freq_rx_mhz < 2100


def test_ul_budget_follows_power_and_range(sim):
    base = _ul(sim).ttc_link_margin_ul
    assert _ul(sim, power_ul=60.0).ttc_link_margin_ul - base == pytest.approx(10.0)
    assert base - _ul(sim, distance=2000.0).ttc_link_margin_ul == pytest.approx(6.02, abs=0.01)


@pytest.mark.parametrize("margin, expected", [
    (5.0, "BIT_LOCK"),
    (2.0, "PSK_LOCK"),
    (0.5, "PSK_LOCK"),
    (0.0, "PLL_LOCK"),
    (-0.5, "PLL_LOCK"),
    (-1.0, "NO_RF"),
    (-128.0, "NO_RF"),
])
def test_ul_state_thresholds(sim, margin, expected):
    from so.data_model import TTCState
    assert _ul(sim, margin=margin).ttc_state_ul == TTCState[expected]


@pytest.mark.parametrize("case", ["carrier_off", "no_sweep", "below_horizon", "rx_off"])
def test_ul_state_no_rf(sim, case):
    from so.data_model import Status, TTCState
    from so.rf_link import NO_LINK_MARGIN
    if case == "carrier_off":
        state = _ul(sim, carrier_ul=Status.off)
        assert state.ttc_link_margin_ul == NO_LINK_MARGIN
    elif case == "no_sweep":
        state = _ul(sim, sweep_done=False)
    elif case == "below_horizon":
        state = _ul(sim, elevation=-2.0)
        assert state.ttc_link_margin_ul == NO_LINK_MARGIN
    else:
        # the X-band receiver is off by default
        state = _ul(sim, band_ul="X")
    assert state.ttc_state_ul == TTCState.NO_RF
    # coherent mode needs two-way lock
    assert state.ttc_coherent == Status.disabled


def test_coherent_turnaround(sim):
    from so.rf_link import TURNAROUND_RATIO
    state = _ul(sim)
    assert state.ttc_freq_tx_mhz == pytest.approx(state.ttc_freq_rx_mhz * TURNAROUND_RATIO[("S", "S")])
