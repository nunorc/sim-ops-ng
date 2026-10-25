
"""RF link budget engine.

Implements a Friis-equation link budget for the TTC RF link, per CCSDS 401.0-B-32
(frequencies/bit rates/turnaround ratios) and CCSDS 131.0-B-5 (channel coding gains):

    C/N0 = EIRP - L_fs - L_atm - L_pol + G/T - k

Constants below (antenna gains, system noise temperatures, TX power) are representative
values for a small LEO mission and are tunable - they are not meant to match any specific
spacecraft.
"""

import numpy as np
from numpy import log10, sin, deg2rad, pi
from scipy.special import erfc

from .data_model import TTCModes, TTCAntenna, Modulation, CodingScheme

# Boltzmann constant in dBW/K/Hz: 10*log10(1.380649e-23)
BOLTZMANN_DBW = -228.6

# speed of light, m/s
C = 2.99792458e8

# spacecraft receive/transmit antenna gain, dBi (LGA is near-omni, MGA/HGA are directional)
SC_ANTENNA_GAIN_DB = {
    TTCAntenna.LGA_RHC: 0.0,
    TTCAntenna.LGA_LHC: 0.0,
    TTCAntenna.MGA: 15.0,
    TTCAntenna.HGA: 25.0,
}

# spacecraft receiver/transmitter system noise temperature, dBK (~500 K)
SC_NOISE_TEMP_DBK = 27.0

# GS system noise temperature per band, dBK; antenna gain comes from antenna_diameter_m (compute_antenna_gain())
GS_BAND_PARAMS = {
    'S': {'noise_temp_dbk': 22.0},
    'X': {'noise_temp_dbk': 22.0},
}

# typical aperture efficiency for a parabolic ground station dish
GS_ANTENNA_EFFICIENCY = 0.55

# transmitter line/connector losses between TX output and antenna feed, dB (applied to both SC and GS)
TX_LOSS_DB = 1.0

# spacecraft transmitter output power, dBW, by bit-rate class (LBR vs HBR)
SC_TX_POWER_DBW = {
    'LBR': 3.0,   # ~2 W
    'HBR': 7.0,   # ~5 W
}

# CCSDS 401.0-B-32 frequency / bit rate / turnaround / coding table per TTC mode
CCSDS_FREQ_TABLE = {
    TTCModes.S_Sup_LBR: {
        'ul_freq_mhz': 2067.0, 'dl_freq_mhz': 2245.0, 'turnaround': 240/221,
        'ul_bit_rate_bps': 256_000, 'dl_bit_rate_bps': 2_900_000,
        'coding': CodingScheme.CONV_7_HALF, 'modulation': Modulation.BPSK, 'power_class': 'LBR',
    },
    TTCModes.S_Sup_HBR: {
        'ul_freq_mhz': 2067.0, 'dl_freq_mhz': 2245.0, 'turnaround': 240/221,
        'ul_bit_rate_bps': 256_000, 'dl_bit_rate_bps': 6_000_000,
        'coding': CodingScheme.CONV_7_HALF, 'modulation': Modulation.BPSK, 'power_class': 'HBR',
    },
    TTCModes.X_Sup_LBR: {
        'ul_freq_mhz': 7190.0, 'dl_freq_mhz': 8450.0, 'turnaround': 880/749,
        'ul_bit_rate_bps': 256_000, 'dl_bit_rate_bps': 100_000_000,
        'coding': CodingScheme.CONV_7_HALF, 'modulation': Modulation.BPSK, 'power_class': 'LBR',
    },
    TTCModes.X_Sup_HBR: {
        'ul_freq_mhz': 7190.0, 'dl_freq_mhz': 8450.0, 'turnaround': 880/749,
        'ul_bit_rate_bps': 256_000, 'dl_bit_rate_bps': 600_000_000,
        'coding': CodingScheme.CONV_7_HALF, 'modulation': Modulation.BPSK, 'power_class': 'HBR',
    },
    TTCModes.S_Res_LBR: {
        'ul_freq_mhz': 2040.0, 'dl_freq_mhz': 2210.0, 'turnaround': 240/221,
        'ul_bit_rate_bps': 256_000, 'dl_bit_rate_bps': 2_900_000,
        'coding': CodingScheme.CONV_7_HALF, 'modulation': Modulation.QPSK, 'power_class': 'LBR',
    },
    TTCModes.X_Res_LBR: {
        'ul_freq_mhz': 7145.0, 'dl_freq_mhz': 8400.0, 'turnaround': 880/749,
        'ul_bit_rate_bps': 256_000, 'dl_bit_rate_bps': 100_000_000,
        'coding': CodingScheme.CONV_7_HALF, 'modulation': Modulation.QPSK, 'power_class': 'LBR',
    },
    TTCModes.S_Sub_LBR: {
        'ul_freq_mhz': 2025.0, 'dl_freq_mhz': 2200.0, 'turnaround': 240/221,
        'ul_bit_rate_bps': 256_000, 'dl_bit_rate_bps': 2_900_000,
        'coding': CodingScheme.UNCODED, 'modulation': Modulation.PM_SUBCARRIER, 'power_class': 'LBR',
    },
    TTCModes.X_Sub_LBR: {
        'ul_freq_mhz': 7180.0, 'dl_freq_mhz': 8420.0, 'turnaround': 880/749,
        'ul_bit_rate_bps': 256_000, 'dl_bit_rate_bps': 100_000_000,
        'coding': CodingScheme.UNCODED, 'modulation': Modulation.PM_SUBCARRIER, 'power_class': 'LBR',
    },
}

# CCSDS 401 transponder turnaround ratios, keyed (uplink band, downlink band)
TURNAROUND_RATIO = {
    ('S', 'S'): 240/221,
    ('S', 'X'): 880/221,
    ('X', 'S'): 240/749,
    ('X', 'X'): 880/749,
}

def ul_mode(mode:TTCModes, band:str) -> TTCModes:
    """The mode whose uplink parameters apply when the uplink runs in `band`."""
    return TTCModes[band + mode.name[1:]]

# CCSDS 131.0-B-5 channel coding gain, dB
CODING_GAIN_TABLE = {
    CodingScheme.UNCODED: 0.0,
    CodingScheme.CONV_7_HALF: 5.1,
    CodingScheme.RS_255_223: 2.0,
    CodingScheme.CONCAT_CONV_RS: 7.5,
    CodingScheme.LDPC_7136: 8.3,
}

# required Eb/N0 for a target BER of 1e-5, dB
REQUIRED_EBNO_TABLE = {
    Modulation.BPSK: 9.6,
    Modulation.QPSK: 9.6,
    Modulation.PM_SUBCARRIER: 11.0,
}

# carrier modulation loss, dB: power diverted to the residual carrier tone (~0 dB for suppressed-carrier modes)
CARRIER_MOD_LOSS_TABLE = {
    Modulation.BPSK: 0.0,
    Modulation.QPSK: 1.0,
    Modulation.PM_SUBCARRIER: 3.0,
}

# floor values used when there is effectively no signal
NO_LINK_C_NO = -128.0
NO_LINK_MARGIN = -128.0
NO_LINK_BER = 0.5
NO_LINK_FER = 1.0

# GS pointing loss at acquisition, dB: linear from POINTING_LOSS_MAX_DB at 0 deg to 0 at POINTING_LOSS_ELEVATION_DEG
POINTING_LOSS_MAX_DB = 5.0
POINTING_LOSS_ELEVATION_DEG = 2.6

# lowest elevation the cosecant atmospheric-loss law is evaluated at (deg)
ATM_MIN_ELEVATION_DEG = 5.0


def compute_fspl(distance_km, freq_mhz):
    """Free-space path loss, dB."""
    if distance_km is None or distance_km <= 0:
        return np.inf
    return 20 * log10(distance_km) + 20 * log10(freq_mhz) + 32.44


def compute_atmospheric_loss(elevation_deg, freq_mhz):
    """Simplified ITU-R P.618 atmospheric loss, dB: scales with 1/sin(elevation), clamped (also below the horizon)."""
    freq_ghz = freq_mhz / 1000.0
    zenith_loss = 0.3 + 0.1 * freq_ghz

    if elevation_deg is None:
        elevation_deg = 0.0
    elevation_deg = max(elevation_deg, ATM_MIN_ELEVATION_DEG)
    return zenith_loss / sin(deg2rad(elevation_deg))


def compute_antenna_gain(diameter_m, freq_mhz, efficiency=GS_ANTENNA_EFFICIENCY):
    """Parabolic dish antenna gain, dBi, for a given diameter (m) and frequency (MHz)."""
    if diameter_m is None or diameter_m <= 0:
        return 0.0
    freq_hz = freq_mhz * 1e6
    return 10 * log10(efficiency) + 20 * log10(pi * diameter_m * freq_hz / C)


def compute_polarization_loss(antenna: TTCAntenna):
    """Polarization mismatch loss, dB."""
    if antenna in (TTCAntenna.LGA_RHC, TTCAntenna.LGA_LHC):
        return 0.0
    if antenna == TTCAntenna.MGA:
        return 0.5
    return 1.0


def compute_pointing_loss(elevation_deg):
    """Ground station pointing loss during track acquisition near AOS, dB."""
    if elevation_deg is None or elevation_deg <= 0:
        return POINTING_LOSS_MAX_DB
    if elevation_deg >= POINTING_LOSS_ELEVATION_DEG:
        return 0.0
    return POINTING_LOSS_MAX_DB * (1 - elevation_deg / POINTING_LOSS_ELEVATION_DEG)


def compute_c_no(eirp_dbw, fspl_db, atm_loss_db, pol_loss_db, pointing_loss_db, g_over_t_db):
    """Carrier-to-noise density, dBHz."""
    return eirp_dbw - fspl_db - atm_loss_db - pol_loss_db - pointing_loss_db + g_over_t_db - BOLTZMANN_DBW


def compute_eb_no(c_no_dbhz, bit_rate_bps, mod_loss_db=0.0):
    """Energy-per-bit to noise density, dB, less `mod_loss_db` diverted to the carrier (CARRIER_MOD_LOSS_TABLE)."""
    if bit_rate_bps is None or bit_rate_bps <= 0:
        return c_no_dbhz - mod_loss_db
    return c_no_dbhz - mod_loss_db - 10 * log10(bit_rate_bps)


def compute_link_margin(eb_no_db, required_eb_no_db, coding_gain_db):
    """Link margin against the required Eb/N0, including FEC coding gain, dB."""
    return eb_no_db + coding_gain_db - required_eb_no_db


def compute_ber(eb_no_db):
    """Bit error rate from Eb/N0 (dB), for coherent BPSK/QPSK detection."""
    eb_no_lin = 10 ** (eb_no_db / 10)
    return 0.5 * erfc(np.sqrt(eb_no_lin))


def compute_fer(ber, frame_bits=8 * 1024):
    """Frame error rate from BER for a frame of `frame_bits` bits."""
    ber = min(max(ber, 0.0), 1.0)
    return 1 - (1 - ber) ** frame_bits


def compute_doppler_shift(velocity_km_s, freq_mhz):
    """Doppler shift, MHz, for a radial velocity in km/s (positive = approaching)."""
    if velocity_km_s is None:
        return 0.0
    return (velocity_km_s * 1000.0 / C) * freq_mhz
