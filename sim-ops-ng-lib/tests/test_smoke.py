DEMO_SCENARIO = "data/demo.json"

def test_import_package():
    # pylint: disable=unused-import  # importing is the test
    import so
    from so.core import SimOps, load_scenario
    from so.spacecraft import SpacecraftSim
    from so.ground_station import GroundStationSim
    from so.data_model import Scenario, SpacecraftState, GroundStationState


def test_version_matches_root_version_file():
    from pathlib import Path
    import so
    root_version = (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip()
    assert so.__version__ == root_version


def test_load_scenario():
    from so.core import load_scenario

    scenario = load_scenario(DEMO_SCENARIO)

    assert scenario is not None
    assert len(scenario.breakpoints) > 0


def test_spacecraft_sim_construction():
    from so.core import load_scenario
    from so.data_model import SpacecraftState
    from so.spacecraft import SpacecraftSim

    scenario = load_scenario(DEMO_SCENARIO)
    spacecraft = SpacecraftSim(scenario=scenario)

    assert isinstance(spacecraft.state, SpacecraftState)


def test_ground_station_sim_construction():
    from so.core import load_scenario
    from so.data_model import GroundStationState
    from so.ground_station import GroundStationSim

    scenario = load_scenario(DEMO_SCENARIO)
    ground_station = GroundStationSim(scenario=scenario, bp=scenario.breakpoints[0])

    assert isinstance(ground_station.state, GroundStationState)


def test_sim_ops_construction():
    from so.core import SimOps

    sim = SimOps(scenario=DEMO_SCENARIO)
    try:
        assert sim.spacecraft is not None
        assert sim.ground_station is not None
        assert sim.breakpoint is not None
    finally:
        sim.shutdown()
