
import os
import signal
import struct
import sys
import time
from typing import Callable

import requests
from minsp import SpacePacket
from minsp.core import PacketType

from .data_model import SpacecraftState, AOCSTarget, Status, TTCAntenna, TTCModes, TTCState

class SpacePacketHandler:
    def __init__(self):
        _fields = 'I3B8f' + 'I4Bf6BIB' + 'If2B2f3BI' + 'IB?f2I' + 'B3fBB'
        # CCSDS packet data is big-endian, with no alignment padding
        self.fmt = '>' + _fields
        # packets archived before the big-endian format used native order/alignment; their size tells them apart
        self._legacy_fmt = '@' + _fields
        self.payload_keys = [
            'ts',
            'aocs_chain',
            'aocs_mode',
            'aocs_valid',
            'aocs_rotation_x',
            'aocs_rotation_y',
            'aocs_rotation_z',
            'aocs_rate_x',
            'aocs_rate_y',
            'aocs_rate_z',
            'aocs_sun_angle',
            'aocs_nadir_angle',
            'ttc_chain',
            'ttc_mcu',
            'ttc_mode',
            'ttc_s_antenna',
            'ttc_x_antenna',
            'ttc_link_margin_ul',
            'ttc_state_ul',
            'ttc_coherent',
            'ttc_s_tx_status',
            'ttc_s_rx_status',
            'ttc_x_tx_status',
            'ttc_x_rx_status',
            'ttc_ping_ack',
            'ttc_ranging',
            'eps_chain',
            'eps_net_power',
            'eps_sol_array_1',
            'eps_sol_array_2',
            'eps_battery_dod',
            'eps_temperature',
            'eps_acu',
            'eps_pdu',
            'eps_power_status',
            'eps_power_source',
            'dhs_chain',
            'dhs_obsw_mode',
            'dhs_mem_dump_enabled',
            'dhs_memory',
            'dhs_tm_counter',
            'dhs_tc_counter',
            'pl_gnss_status',
            'pl_gnss_lat',
            'pl_gnss_lon',
            'pl_gnss_alt',
            'pl_camera_status',
            'pl_sdr_status'
        ]

    def as_byte_string(self, sc_state: SpacecraftState):
        return struct.pack(
            self.fmt,
            int(sc_state.ts),
            ord(sc_state.aocs_chain),
            sc_state.aocs_mode.value,
            sc_state.aocs_valid.value,
            sc_state.aocs_rotation[0], sc_state.aocs_rotation[1], sc_state.aocs_rotation[2],
            sc_state.aocs_rates[0], sc_state.aocs_rates[1], sc_state.aocs_rates[2],
            sc_state.aocs_sun_angle,
            sc_state.aocs_nadir_angle,
            ord(sc_state.ttc_chain),
            sc_state.ttc_mcu.value,
            sc_state.ttc_mode.value,
            sc_state.ttc_s_antenna.value,
            sc_state.ttc_x_antenna.value,
            sc_state.ttc_link_margin_ul,
            sc_state.ttc_state_ul.value,
            sc_state.ttc_coherent.value,
            sc_state.ttc_s_tx_status.value,
            sc_state.ttc_s_rx_status.value,
            sc_state.ttc_x_tx_status.value,
            sc_state.ttc_x_rx_status.value,
            sc_state.ttc_ping_ack,
            sc_state.ttc_ranging.value,
            ord(sc_state.eps_chain),
            sc_state.eps_net_power,
            sc_state.eps_sol_array[0].value,
            sc_state.eps_sol_array[1].value,
            sc_state.eps_battery_dod,
            sc_state.eps_temperature,
            sc_state.eps_acu,
            sc_state.eps_pdu,
            sc_state.eps_power_status,
            ord(sc_state.eps_power_source),
            ord(sc_state.dhs_chain),
            sc_state.dhs_obsw_mode.value,
            sc_state.dhs_mem_dump_enabled,
            sc_state.dhs_memory,
            sc_state.dhs_tm_counter,
            sc_state.dhs_tc_counter,
            sc_state.pl_gnss_status.value,
            sc_state.pl_gnss_pos[0],
            sc_state.pl_gnss_pos[1],
            sc_state.pl_gnss_pos[2],
            sc_state.pl_camera_status.value,
            sc_state.pl_sdr_status.value
        )

    def as_dict(self, packet: SpacePacket, post_proc: bool = True):
        primary_header = {
            'version': '0b' + format(int(packet.version), '03b'),
            'type': "TM" if packet.type == 0 else "TC",
            'sec_hdr_flag': '0b' + format(int(packet.secondary_header_flag), '01b'),
            'apid': packet.apid,
            'sequence_flags': '0b' + format(int(packet.sequence_flags), '02b'),
            'sequence_count': packet.sequence_count,
            'data_length': packet.data_length
        }

        if packet.type == PacketType.TC:
            command, _, value = packet.data_field.decode().partition(':')
            return {
                'primary_header': primary_header,
                'sec_hdr': None,
                'payload': {'command': command, 'value': value}
            }

        fmt = self.fmt
        if len(packet.data_field) == struct.calcsize(self._legacy_fmt) != struct.calcsize(self.fmt):
            fmt = self._legacy_fmt
        values = struct.unpack(fmt, packet.data_field)

        data = {
            'primary_header': primary_header,
            'sec_hdr': None,
            'payload': dict(zip(self.payload_keys, values))
        }

        if post_proc:
            data['payload']['aocs_chain'] = chr(data['payload']['aocs_chain'])
            data['payload']['aocs_mode'] = AOCSTarget(data['payload']['aocs_mode']).name.upper()
            data['payload']['aocs_valid'] = Status(data['payload']['aocs_valid']).name.upper()
            data['payload']['ttc_chain'] = chr(data['payload']['ttc_chain'])
            data['payload']['ttc_mcu'] = Status(data['payload']['ttc_mcu']).name.upper()
            data['payload']['ttc_mode'] = TTCModes(data['payload']['ttc_mode']).name.upper()
            data['payload']['ttc_s_antenna'] = TTCAntenna(data['payload']['ttc_s_antenna']).name.upper()
            data['payload']['ttc_x_antenna'] = TTCAntenna(data['payload']['ttc_x_antenna']).name.upper()
            data['payload']['ttc_state_ul'] = TTCState(data['payload']['ttc_state_ul']).name.upper()
            data['payload']['ttc_s_tx_status'] = Status(data['payload']['ttc_s_tx_status']).name.upper()
            data['payload']['ttc_s_rx_status'] = Status(data['payload']['ttc_s_rx_status']).name.upper()
            data['payload']['ttc_x_tx_status'] = Status(data['payload']['ttc_x_tx_status']).name.upper()
            data['payload']['ttc_x_rx_status'] = Status(data['payload']['ttc_x_rx_status']).name.upper()
            data['payload']['ttc_coherent'] = Status(data['payload']['ttc_coherent']).name.upper()
            data['payload']['ttc_ranging'] = Status(data['payload']['ttc_ranging']).name.upper()
            data['payload']['eps_chain'] = chr(data['payload']['eps_chain'])
            data['payload']['eps_sol_array_1'] = Status(data['payload']['eps_sol_array_1']).name.upper()
            data['payload']['eps_sol_array_2'] = Status(data['payload']['eps_sol_array_2']).name.upper()
            data['payload']['eps_acu'] = Status(data['payload']['eps_acu']).name.upper()
            data['payload']['eps_pdu'] = Status(data['payload']['eps_pdu']).name.upper()
            data['payload']['eps_power_status'] = Status(data['payload']['eps_power_status']).name.upper()
            data['payload']['eps_power_source'] = chr(data['payload']['eps_power_source'])
            data['payload']['dhs_chain'] = chr(data['payload']['dhs_chain'])
            data['payload']['dhs_obsw_mode'] = Status(data['payload']['dhs_obsw_mode']).name.upper()
            data['payload']['pl_gnss_status'] = Status(data['payload']['pl_gnss_status']).name.upper()
            data['payload']['pl_camera_status'] = Status(data['payload']['pl_camera_status']).name.upper()
            data['payload']['pl_sdr_status'] = Status(data['payload']['pl_sdr_status']).name.upper()
        else:
            data['payload']['dhs_mem_dump_enabled'] = int(data['payload']['dhs_mem_dump_enabled'])

        return data

    def space_packet(self, sc_state:SpacecraftState):
        payload = self.as_byte_string(sc_state)

        packet = SpacePacket(apid=10, data_field=payload)

        return packet

    def tc_packet(self, command: str, value: str = "", apid: int = 10) -> SpacePacket:
        data = f"{command}:{value}".encode()
        return SpacePacket(type=PacketType.TC, apid=apid, data_field=data)

    def from_bytestream(self, data: bytes):
        return SpacePacket.from_bytes(data)


def resolve_control_request(backend_url: str, data: dict) -> tuple[str, dict]:
    """Given a control step dict, return (url, payload); shared by the admin /api/trigger and data/trigger-*.py."""
    system = data.get("system")
    control = data.get("control")
    value = data.get("value")

    if system == "override" and control == "_unset":
        return f"{backend_url}/api/override/unset", {"attr": value}
    elif system == "override":
        return f"{backend_url}/api/override/set", {"attr": control, "value": value}
    elif data.get("admin"):
        return f"{backend_url}/api/admin/set-state", {"attr": control, "value": value}
    else:
        return f"{backend_url}/api/control", {"system": system, "control": control, "value": value}


def run_control_steps(steps: list[dict]) -> None:
    """Send each control step to the backend (env SIM_OPS_NG_API_URL), printing S:/R:; exit 1 if any step failed."""
    backend_url = os.getenv("SIM_OPS_NG_API_URL", "http://localhost:9111")
    headers = {"X-Admin-Password": os.getenv("SIM_OPS_NG_ADMIN_PASSWORD", "admin123")}

    failures = 0
    for data in steps:
        try:
            url, payload = resolve_control_request(backend_url, data)
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            if response.status_code == 200:
                result = response.json()
            else:
                failures += 1
                result = {'status': 'FAIL', 'error': f"{response.status_code}: {response.text}"}
        except requests.RequestException as e:
            failures += 1
            result = {'status': 'FAIL', 'error': str(e)}

        print("S:", data)
        print("R:", result)

    if failures:
        print(f"FAILED: {failures}/{len(steps)} steps")
        sys.exit(1)

    print(f"OK: {len(steps)} steps")


def run_until_signalled(shutdown: Callable[[], None], name: str) -> None:
    """Block until SIGINT/SIGTERM (or Ctrl-C), then call `shutdown` once; for the bin/ entry points."""
    running = True

    def on_signal(*_):
        nonlocal running
        if running:
            running = False
            print(f"\nShutting down {name}...")
            shutdown()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        on_signal()
