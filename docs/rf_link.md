---
title: "RF link budget"
weight: 60
---

# RF link budget

Both directions, from power and geometry to C/N0, Eb/N0, margin, BER, FER and lock state, enough
to reproduce the numbers by hand. Code:
[`so/rf_link.py`](../sim-ops-ng-lib/so/rf_link.py), called by
`GroundStationSim._calc_link_budget_dl` (**downlink**,
[`so/ground_station.py`](../sim-ops-ng-lib/so/ground_station.py)) and
`TTCMin._calculate_uplink_budget` (**uplink**, [`so/sys/ttc.py`](../sim-ops-ng-lib/so/sys/ttc.py)).

A Friis budget following CCSDS 401.0-B-32 (frequencies, bit rates, turnaround ratios) and CCSDS
131.0-B-5 (coding gains), with constants typical of a small LEO mission.

---

## 1. The equations

All quantities in dB unless noted; evaluated for each direction every tick:

```
C/N0   = EIRP − L_fs − L_atm − L_pol − L_point + G/T − k          [dBHz]
Eb/N0  = C/N0 − L_mod − 10·log10(R_b)                              [dB]
margin = Eb/N0 + G_coding − (Eb/N0)_req                            [dB]
BER    = ½ · erfc( √(10^(Eb/N0 / 10)) )
FER    = 1 − (1 − BER)^8192
```

| Symbol | Meaning | Where it comes from |
|---|---|---|
| EIRP | Effective isotropic radiated power, dBW | [§2](#2-terms-per-direction) |
| L_fs | Free-space path loss | [§3.1](#31-free-space-path-loss) |
| L_atm | Atmospheric loss | [§3.2](#32-atmospheric-loss) |
| L_pol | Polarisation mismatch loss | [§3.3](#33-polarisation-loss) |
| L_point | Ground antenna pointing loss | [§3.4](#34-pointing-loss) |
| G/T | Receiver figure of merit, dB/K | [§2](#2-terms-per-direction) |
| k | Boltzmann's constant, −228.6 dBW/K/Hz (10·log10(1.380649e−23)) | `BOLTZMANN_DBW` |
| L_mod | Carrier modulation loss | [§4.4](#44-modulation-coding-and-required-ebn0) |
| R_b | Bit rate, bit/s | [§4.1](#41-mode-table) |
| G_coding | Channel coding gain | [§4.4](#44-modulation-coding-and-required-ebn0) |
| (Eb/N0)_req | Eb/N0 required for BER 1e−5 | [§4.4](#44-modulation-coding-and-required-ebn0) |

Notes:

- k is negative, so `− k` **adds** 228.6 dB.
- BER uses the **uncoded** Eb/N0: the coding gain only enters the margin.
- FER assumes an 8192-bit frame; BER is clamped to [0, 1] first.

---

## 2. Terms, per direction

| Term | Downlink (spacecraft → ground) | Uplink (ground → spacecraft) |
|---|---|---|
| Mode | the spacecraft's `ttc_mode` | `ul_mode(gs.mode, gs.band_ul)`: the ground station's mode with its band letter replaced by `band_ul` (e.g. `X_Sup_LBR` with `band_ul = S` → `S_Sup_LBR`) |
| Frequency f | `dl_freq_mhz` of the mode | `ul_freq_mhz` of the uplink mode |
| Bit rate R_b | `dl_bit_rate_bps` | `ul_bit_rate_bps` |
| Spacecraft antenna | `ttc_s_antenna` if the band is S, `ttc_x_antenna` if X | same, for the uplink band |
| Transmit power | `P_sc` = `SC_TX_POWER_DBW[power_class]` (3 or 7 dBW) | `power_ul` (dBm, from the GS control, default 50) − 30 → dBW |
| Transmit antenna gain | `G_sc` = `SC_ANTENNA_GAIN_DB[antenna]` | `G_gs` = dish gain at f ([§3.5](#35-ground-dish-gain)) |
| EIRP | `P_sc + G_sc − L_tx` | `(power_ul − 30) + G_gs − L_tx` |
| Receive G/T | `G_gs − T_gs` = dish gain at f − 22 dBK | `G_sc − T_sc` = antenna gain − 27 dBK |
| Modulation, coding | of the spacecraft's mode | of the uplink mode |
| Elevation, range | from the ground station's tracking (`elevation`, `distance` in km) | same |

`L_tx` is the transmitter line loss, 1 dB on both sides (`TX_LOSS_DB`). G_gs is computed separately
at the uplink and downlink frequencies.

---

## 3. Loss and gain models

### 3.1 Free-space path loss

```
L_fs = 20·log10(d_km) + 20·log10(f_MHz) + 32.44
```

### 3.2 Atmospheric loss

A simplified ITU-R P.618 model: a zenith loss scaled by the cosecant of the elevation:

```
L_zenith = 0.3 + 0.1·f_GHz
L_atm    = L_zenith / sin(max(el, 5°))
```

Elevation is clamped at 5° (`ATM_MIN_ELEVATION_DEG`, also when missing or negative) so the loss is
continuous across AOS. Maximum ≈ 6.02 dB at 2245 MHz, ≈ 13.1 dB at 8450 MHz.

### 3.3 Polarisation loss

Keyed on the spacecraft antenna in use:

| Antenna | L_pol |
|---|---|
| `LGA_RHC`, `LGA_LHC` | 0.0 dB |
| `MGA` | 0.5 dB |
| `HGA` | 1.0 dB |

### 3.4 Pointing loss

Ground antenna loss while autotrack settles near AOS:

```
el ≤ 0°        → L_point = 5.0
0° < el < 2.6° → L_point = 5.0 · (1 − el / 2.6)
el ≥ 2.6°      → L_point = 0.0
```

(`POINTING_LOSS_MAX_DB = 5.0`, `POINTING_LOSS_ELEVATION_DEG = 2.6`.)

### 3.5 Ground dish gain

Parabolic dish of diameter D (m, the breakpoint's `antenna_diameter_m`), aperture efficiency
η = 0.55 (`GS_ANTENNA_EFFICIENCY`), c = 2.99792458e8 m/s:

```
G_gs = 10·log10(η) + 20·log10(π · D · f_Hz / c)          [dBi]
```

Example: D = 3.7 m → 36.20 dBi at 2245 MHz, 35.48 dBi at 2067 MHz.

### 3.6 Doppler shift

```
Δf_MHz = (v_km/s · 1000 / c) · f_MHz
```

`v` is the ground station's `doppler_velocity`, **positive when the spacecraft approaches**.

---

## 4. Constants and tables

### 4.1 Mode table

`CCSDS_FREQ_TABLE`. A mode name is `<band>_<carrier>_<rate>`; see [ttc.md](ttc.md#1-modes-and-antennas).

| Mode | UL MHz | DL MHz | UL bit/s | DL bit/s | Modulation | Coding | Power class |
|---|---|---|---|---|---|---|---|
| `S_Sup_LBR` | 2067.0 | 2245.0 | 256 000 | 2 900 000 | BPSK | CONV_7_HALF | LBR |
| `S_Sup_HBR` | 2067.0 | 2245.0 | 256 000 | 6 000 000 | BPSK | CONV_7_HALF | HBR |
| `X_Sup_LBR` | 7190.0 | 8450.0 | 256 000 | 100 000 000 | BPSK | CONV_7_HALF | LBR |
| `X_Sup_HBR` | 7190.0 | 8450.0 | 256 000 | 600 000 000 | BPSK | CONV_7_HALF | HBR |
| `S_Res_LBR` | 2040.0 | 2210.0 | 256 000 | 2 900 000 | QPSK | CONV_7_HALF | LBR |
| `X_Res_LBR` | 7145.0 | 8400.0 | 256 000 | 100 000 000 | QPSK | CONV_7_HALF | LBR |
| `S_Sub_LBR` | 2025.0 | 2200.0 | 256 000 | 2 900 000 | PM_SUBCARRIER | UNCODED | LBR |
| `X_Sub_LBR` | 7180.0 | 8420.0 | 256 000 | 100 000 000 | PM_SUBCARRIER | UNCODED | LBR |

### 4.2 Spacecraft

| Constant | Value |
|---|---|
| Transmit power, LBR (`SC_TX_POWER_DBW`) | 3.0 dBW (~2 W) |
| Transmit power, HBR | 7.0 dBW (~5 W) |
| Antenna gain, `LGA_RHC` / `LGA_LHC` (`SC_ANTENNA_GAIN_DB`) | 0.0 dBi |
| Antenna gain, `MGA` | 15.0 dBi |
| Antenna gain, `HGA` | 25.0 dBi |
| System noise temperature (`SC_NOISE_TEMP_DBK`) | 27.0 dBK (~500 K) |
| Transmit line loss, both sides (`TX_LOSS_DB`) | 1.0 dB |

The same antenna gain is used to transmit and to receive.

### 4.3 Ground station

| Constant | Value |
|---|---|
| Uplink power (`power_ul`, GS control) | dBm; default 50.0 (= 20 dBW) |
| Dish diameter (`antenna_diameter_m`, scenario) | default 4.0 m |
| Aperture efficiency (`GS_ANTENNA_EFFICIENCY`) | 0.55 |
| System noise temperature, S and X (`GS_BAND_PARAMS`) | 22.0 dBK (~160 K) |

### 4.4 Modulation, coding and required Eb/N0

| Modulation | L_mod (`CARRIER_MOD_LOSS_TABLE`) | (Eb/N0)_req for BER 1e−5 (`REQUIRED_EBNO_TABLE`) |
|---|---|---|
| BPSK (suppressed carrier, `Sup`) | 0.0 dB | 9.6 dB |
| QPSK (residual carrier, `Res`) | 1.0 dB | 9.6 dB |
| PM_SUBCARRIER (`Sub`) | 3.0 dB | 11.0 dB |

L_mod is the power put into a residual carrier tone (for ground tracking) instead of the data.

| Coding (`CODING_GAIN_TABLE`) | G_coding |
|---|---|
| UNCODED | 0.0 dB |
| CONV_7_HALF (convolutional, K=7, r=1/2) | 5.1 dB |
| RS_255_223 | 2.0 dB |
| CONCAT_CONV_RS | 7.5 dB |
| LDPC_7136 | 8.3 dB |

Only UNCODED and CONV_7_HALF are used by the current modes.

### 4.5 Turnaround ratios

`TURNAROUND_RATIO`, keyed (uplink band, downlink band), used for the coherent transponder
([§6](#6-frequencies)):

| Uplink ↓ / Downlink → | S | X |
|---|---|---|
| **S** | 240/221 | 880/221 |
| **X** | 240/749 | 880/749 |

---

## 5. No-link conditions

A direction with no link reports C/N0, Eb/N0 and margin of −128.0 (`NO_LINK_C_NO`,
`NO_LINK_MARGIN`), BER 0.5 (`NO_LINK_BER`), FER 1.0 (`NO_LINK_FER`) and no Doppler shift.

**Downlink** — no link if any of:

- the spacecraft transmitter for the mode's band (`ttc_s_tx_status` / `ttc_x_tx_status`) is not `on`;
- no elevation, or elevation < 0°; no range, or range < 0;
- the ground station's mode band differs from the spacecraft's;
- the band is X and the X antenna is `HGA`.

**Uplink** — no link if any of:

- no ground-station state;
- the uplink carrier (`carrier_ul`) is not `on`;
- no elevation, or elevation ≤ 0°; no range, or range ≤ 0.

Elevation and range only exist during a pass with program track on
([ground_station.md](ground_station.md#1-passes-and-tracking)).

---

## 6. Frequencies

On board (TTC):

```
freq_rx = f_ul + Δf_ul
freq_tx = freq_rx · TURNAROUND_RATIO[(band_ul, dl band)]   if ttc_coherent = enabled
        = f_dl (nominal, of the spacecraft mode)              otherwise
```

On the ground: `freq_ul_mhz` is the nominal uplink frequency of the uplink mode, and

```
freq_dl = freq_tx + Δf_dl   if coherent
        = f_dl    + Δf_dl   otherwise
```

where Δf_ul and Δf_dl are the Doppler shifts ([§3.6](#36-doppler-shift)) at f_ul and f_dl.

---

## 7. From margin to lock state

**Downlink** (`status_dl`), against the ground station mode's `status_dl_transitions` (defaults
`DEFAULT_STATUS_DL_TRANSITIONS` in [`so/data_model.py`](../sim-ops-ng-lib/so/data_model.py), the
same for all modes):

| Margin | State |
|---|---|
| > 3.0 dB | `FRAME_LOCK` |
| > 1.0 dB | `BIT_LOCK` |
| > −1.0 dB | `PLL_LOCK` |
| > −128 (any real signal) | `RF_DETECTED` |
| −128 (no link) | `NO_RF` |

A mode mismatch between ground station and spacecraft forces the margin to −128 → `NO_RF`.

**Uplink** (`ttc_state_ul`), only if the spacecraft receiver for the uplink band is on and the
ground station has swept:

| Margin | State |
|---|---|
| > 2.0 dB | `BIT_LOCK` |
| > 0.0 dB | `PSK_LOCK` |
| > −1.0 dB | `PLL_LOCK` |
| otherwise | `NO_RF` |

For carrier, sweep and Doppler housekeeping see [ground_station.md](ground_station.md#2-lock-states).

---

## 8. Instructor overrides

Applied to the downlink after the budget, in order ([admin.md](admin.md#2-overrides)):

1. **`max_c_no_dl`** caps C/N0; Eb/N0, margin, BER and FER are recomputed from it.
2. **`max_eb_no_dl`** caps Eb/N0; margin, BER and FER are recomputed, and C/N0 back-computed as
   `Eb/N0 + L_mod + 10·log10(R_b)`.
3. **`max_status_dl`** caps the lock state.

---

## 9. Worked example

Mode `S_Sup_LBR`, S-band antenna `LGA_RHC`, dish D = 3.7 m, elevation 10°, range 2000 km,
range-rate +5 km/s (approaching), uplink power 50 dBm, no overrides. Values from `so/rf_link.py`.

**Downlink** (f = 2245 MHz, R_b = 2.9 Mbit/s):

| Step | Value |
|---|---|
| EIRP = 3.0 + 0.0 − 1.0 | 2.00 dBW |
| G_gs(2245 MHz) | 36.20 dBi |
| G/T = 36.20 − 22.0 | 14.20 dB/K |
| L_fs = 20·log10(2000) + 20·log10(2245) + 32.44 | 165.48 dB |
| L_atm = (0.3 + 0.2245) / sin 10° | 3.02 dB |
| L_pol (LGA), L_point (el ≥ 2.6°) | 0.0 dB, 0.0 dB |
| C/N0 = 2.00 − 165.48 − 3.02 − 0 − 0 + 14.20 + 228.6 | 76.29 dBHz |
| Eb/N0 = 76.29 − 0.0 − 10·log10(2 900 000) | 11.67 dB |
| margin = 11.67 + 5.1 − 9.6 | 7.17 dB → `FRAME_LOCK` |
| BER, FER | 2.99e−08, 2.45e−04 |
| Δf_dl = 5000 / c · 2245 | +0.0374 MHz |

**Uplink** (f = 2067 MHz, R_b = 256 kbit/s):

| Step | Value |
|---|---|
| G_gs(2067 MHz) | 35.48 dBi |
| EIRP = (50 − 30) + 35.48 − 1.0 | 54.48 dBW |
| G/T = 0.0 − 27.0 | −27.00 dB/K |
| L_fs | 164.77 dB |
| L_atm = (0.3 + 0.2067) / sin 10° | 2.92 dB |
| C/N0 = 54.48 − 164.77 − 2.92 − 27.0 + 228.6 | 88.40 dBHz |
| Eb/N0 = 88.40 − 10·log10(256 000) | 34.31 dB |
| margin = 34.31 + 5.1 − 9.6 | 29.81 dB → `BIT_LOCK` (after sweep) |
| BER, FER | ≈ 0, ≈ 0 |
| Δf_ul, coherent freq_tx = (2067 + 0.0345) · 240/221 | +0.0345 MHz, 2244.743 MHz |
