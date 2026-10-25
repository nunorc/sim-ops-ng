
import copy
from dataclasses import dataclass, asdict, field
from enum import Enum
from numpy import ndarray

# return enum types names instead of values (numbers)
def custom_dict_factory(kv_pairs):
    def convert_value(obj):
        if isinstance(obj, Enum):
            return obj.name
        elif isinstance(obj, list):
            return [convert_value(x) for x in obj]
        elif isinstance(obj, dict):
            # e.g. a breakpoint's initial states, whose enum values load as members
            return {k: convert_value(v) for k, v in obj.items()}
        elif isinstance(obj, ndarray):
            return list(obj)
        else:
            return obj

    return dict((k, convert_value(v)) for k, v in kv_pairs)

# thresholds are on the downlink link margin (Eb/N0 - required Eb/N0), in dB
DEFAULT_STATUS_DL_TRANSITIONS = {
    'S_Sup_LBR': { 'PLL_LOCK': -1.0, 'BIT_LOCK': 1.0, 'FRAME_LOCK': 3.0 },
    'S_Sup_HBR': { 'PLL_LOCK': -1.0, 'BIT_LOCK': 1.0, 'FRAME_LOCK': 3.0 },
    'X_Sup_LBR': { 'PLL_LOCK': -1.0, 'BIT_LOCK': 1.0, 'FRAME_LOCK': 3.0 },
    'X_Sup_HBR': { 'PLL_LOCK': -1.0, 'BIT_LOCK': 1.0, 'FRAME_LOCK': 3.0 },
    'S_Res_LBR': { 'PLL_LOCK': -1.0, 'BIT_LOCK': 1.0, 'FRAME_LOCK': 3.0 },
    'X_Res_LBR': { 'PLL_LOCK': -1.0, 'BIT_LOCK': 1.0, 'FRAME_LOCK': 3.0 },
    'S_Sub_LBR': { 'PLL_LOCK': -1.0, 'BIT_LOCK': 1.0, 'FRAME_LOCK': 3.0 },
    'X_Sub_LBR': { 'PLL_LOCK': -1.0, 'BIT_LOCK': 1.0, 'FRAME_LOCK': 3.0 }
}

class Status(int, Enum):
    enabled = 1
    disabled = 2
    unknown = 3
    nominal = 4
    safe = 5
    on = 6
    off = 7
    not_valid = 8
    valid = 9
    error = 10
    control_err = 13
    power_positive = 14
    power_negative = 15
    power_critical = 16
    sun = 18
    no_sun = 19

class Quality(int, Enum):
    good = 1
    bad = 2
    unknown = 3

class TTCModes(int, Enum):
    S_Sup_LBR = 1
    S_Sup_HBR = 2
    X_Sup_LBR = 3
    X_Sup_HBR = 4
    S_Res_LBR = 5
    X_Res_LBR = 6
    S_Sub_LBR = 7
    X_Sub_LBR = 8

class TTCAntenna(int, Enum):
    LGA_RHC = 1
    LGA_LHC = 2
    MGA = 3
    HGA = 4

class AOCSTarget(Enum):
    SUN = 1
    TARGET = 2
    NADIR = 3
    RATEDAMPING = 4
    MONITORING = 5

class TTCState(int, Enum):
    NO_RF = 1
    RF_DETECTED = 2
    PLL_LOCK = 3
    PSK_LOCK = 4
    BIT_LOCK = 5
    FRAME_LOCK = 6

class DataProxy(int, Enum):
    EGSE = 1
    SLE  = 2

class Modulation(str, Enum):
    BPSK = 'BPSK'
    QPSK = 'QPSK'
    PM_SUBCARRIER = 'PM_SUBCARRIER'

class CodingScheme(str, Enum):
    UNCODED = 'UNCODED'
    CONV_7_HALF = 'CONV_7_HALF'
    RS_255_223 = 'RS_255_223'
    CONCAT_CONV_RS = 'CONCAT_CONV_RS'
    LDPC_7136 = 'LDPC_7136'

@dataclass
class SpacecraftState:
    ts: float = 0.0

    aocs_chain: str = 'A'
    aocs_mode: AOCSTarget = AOCSTarget.NADIR
    aocs_valid: Status = Status.unknown
    aocs_prev_mode: AOCSTarget = AOCSTarget.NADIR
    aocs_rotation: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    aocs_rates: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    aocs_sun_angle: float = 0.0
    aocs_nadir_angle: float = 0.0
    aocs_damp: float = 1.0
    aocs_position: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])

    ttc_chain: str = 'A'
    ttc_mcu: Status = Status.nominal
    ttc_mode: TTCModes = TTCModes.S_Sup_LBR
    ttc_s_antenna: TTCAntenna = TTCAntenna.LGA_RHC
    ttc_x_antenna: TTCAntenna = TTCAntenna.MGA
    ttc_state_ul: TTCState = TTCState.NO_RF
    ttc_coherent: Status = Status.disabled
    ttc_s_tx_status: Status = Status.on
    ttc_s_rx_status: Status = Status.on
    ttc_x_tx_status: Status = Status.off
    ttc_x_rx_status: Status = Status.off
    ttc_ping_ack: int = 0
    ttc_ranging: Status = Status.disabled

    # uplink RF link budget (CCSDS)
    ttc_c_no_ul: float = -128.0
    ttc_eb_no_ul: float = -128.0
    ttc_link_margin_ul: float = -128.0
    ttc_ber_ul: float = 0.5
    ttc_fer_ul: float = 1.0
    ttc_doppler_shift_ul: float = 0.0
    ttc_freq_rx_mhz: float = 0.0
    ttc_freq_tx_mhz: float = 0.0

    eps_chain: str = 'A'
    eps_net_power: float = 0.0
    eps_sol_array: list[Status] = field(default_factory=lambda: [Status.no_sun, Status.no_sun])
    eps_battery_dod: float = 50.0
    eps_temperature: float = 40.0
    eps_acu: Status = Status.nominal
    eps_pdu: Status = Status.nominal
    eps_power_status: Status = Status.power_negative  # derived in EPSMin.update
    eps_power_source: str = 'S'  # S == Solar Panels, R == RTG

    dhs_chain: str = 'A'
    dhs_obsw_mode: Status = Status.nominal
    dhs_mem_dump_enabled: bool = False
    dhs_memory: float = 50
    dhs_tm_counter: int = 0
    dhs_tc_counter: int = 0
    dhs_tm_window: list[str] = field(default_factory=list)
    dhs_tc_history: list[str] = field(default_factory=list)
    dhs_uploaded: list[str] = field(default_factory=list)

    pl_gnss_status: Status = Status.off
    pl_gnss_pos: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    pl_camera_status: Status = Status.off
    pl_camera_config: str = 'LE'
    pl_sdr_status: Status = Status.off
    pl_sdr_config: str = 'BCN'

    # book-keeping
    ov_no_tm: bool = False
    frame_quality: Quality = Quality.unknown
    frame_checks: Status = Status.enabled
    is_sunlit: bool | None = None

    def to_dict(self):
        return asdict(self, dict_factory=custom_dict_factory)

    def tx_status(self, band:str | None = None) -> Status:
        """Transmitter status for the given band, defaulting to the band of the active TTC mode."""
        band = band or self.ttc_mode.name[0]
        return self.ttc_s_tx_status if band == 'S' else self.ttc_x_tx_status

    def rx_status(self, band:str | None = None) -> Status:
        """Receiver status for the given band, defaulting to the band of the active TTC mode."""
        band = band or self.ttc_mode.name[0]
        return self.ttc_s_rx_status if band == 'S' else self.ttc_x_rx_status

    def scrub(self):
        _state = copy.deepcopy(self)

        _state.aocs_chain = '0'
        _state.aocs_mode = AOCSTarget.NADIR
        _state.aocs_valid = Status.unknown
        _state.aocs_prev_mode = AOCSTarget.NADIR
        _state.aocs_rotation = [0.0, 0.0, 0.0]
        _state.aocs_rates = [0.0, 0.0, 0.0]
        _state.aocs_sun_angle = 0.0
        _state.aocs_nadir_angle = 0.0

        _state.eps_chain = '0'
        _state.eps_net_power = 0
        _state.eps_sol_array = [Status.no_sun, Status.no_sun]
        _state.eps_battery_dod = 0.0
        _state.eps_temperature = 0.0
        _state.eps_acu = Status.control_err
        _state.eps_pdu = Status.error
        _state.eps_power_status = Status.power_critical
        _state.eps_power_source = '0'

        _state.dhs_chain = '0'
        _state.dhs_obsw_mode = Status.nominal
        _state.dhs_mem_dump_enabled = False
        _state.dhs_memory = 0.0
        _state.dhs_tm_counter = 0
        _state.dhs_tc_counter = 0
        _state.dhs_tm_window = []
        _state.dhs_tc_history = []
        _state.dhs_uploaded = []

        _state.pl_gnss_status = Status.off
        _state.pl_gnss_pos = [0.0, 0.0, 0.0]
        _state.pl_camera_status = Status.off
        _state.pl_camera_config = ''
        _state.pl_sdr_status = Status.off
        _state.pl_sdr_config = ''

        return _state

@dataclass
class BusMessage:
    source: str
    destination: str
    payload: dict

@dataclass
class GroundStationState:
    ts: float = 0.0
    carrier_ul: Status = Status.off
    # (frequency, power) points
    spectrum_ul: list[tuple[float, float]] = field(default_factory=list)
    spectrum_dl: list[tuple[float, float]] = field(default_factory=list)
    frame_quality: Quality = Quality.unknown
    frame_checks: Status = Status.enabled
    status_dl: TTCState = TTCState.NO_RF
    status_dl_transitions: dict = field(default_factory=lambda: DEFAULT_STATUS_DL_TRANSITIONS)
    # downlink RF link budget (CCSDS)
    c_no_dl: float = -128.0
    eb_no_dl: float = -128.0
    link_margin_dl: float = -128.0
    ber_dl: float = 0.5
    fer_dl: float = 1.0
    doppler_shift_dl: float = 0.0
    freq_ul_mhz: float = 0.0
    freq_dl_mhz: float = 0.0
    dl_modulation: str = ''
    dl_coding: str = ''

    elevation: float | None = None
    azimuth: float | None = None
    distance: float | None = None
    auto_track: bool = False
    program_track: bool = False
    doppler_enabled: bool = False
    doppler_velocity: float | None = None
    sweep_done: bool = False
    mode: TTCModes = TTCModes.S_Sub_LBR
    # uplink band ('S' or 'X'), independent of the downlink mode
    band_ul: str = 'S'
    power_ul: float = 50.0
    antenna_diameter_m: float = 4.0
    position: list[float] = field(default_factory=list)

    # book-keeping
    ov_no_tm: bool = False
    ov_no_tc: bool = False
    auto_range: bool = False
    ul_state: TTCState = TTCState.NO_RF
    ul_link_margin: float = -128.0
    modes: list[str] = field(default_factory=lambda: [m.name for m in TTCModes])
    # timestamps of the next pass (and its part above 5 degrees elevation); None when there is none
    next_pass_start: float | None = None
    next_pass_end: float | None = None
    next_5_start: float | None = None
    next_5_end: float | None = None
    sweep_count: int = 0
    flight_dynamics: list[list[float]] = field(default_factory=list)
    name: str = 'ESOC-1'
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0

    def to_dict(self):
        return asdict(self, dict_factory=custom_dict_factory)

@dataclass
class GroundStation:
    name: str
    latitude: float
    longitude: float
    altitude: float
    antenna_diameter_m: float = 4.0

@dataclass
class Breakpoint:
    name: str = ""
    begin: str = "2023-08-27 04:40:00+00:00"
    end: str = "2023-08-27 04:55:00+00:00"
    ground_station: GroundStation | None = None
    gs_initial_state: dict = field(default_factory=dict)
    sc_initial_state: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self, dict_factory=custom_dict_factory)

@dataclass
class Scenario:
    name: str = ""
    tle: str = (
        "OPS-SAT\n"
        "1 44878U 19092F   23237.49766723  .00030600  00000-0  81781-3 0  9990\n"
        "2 44878  97.4743  67.3096 0007340 241.3055 118.7452 15.38003807204438"
    )
    breakpoints: list[Breakpoint] = field(default_factory=list)
    tm_packet_frequency: int = 30
    time_factor: float = 1.0

    def to_dict(self):
        return asdict(self, dict_factory=custom_dict_factory)
