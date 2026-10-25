
from typing import Protocol, cast
import numpy as np
from datetime import datetime, timezone
from skyfield.api import load, EarthSatellite, wgs84
from skyfield.jpllib import SpiceKernel
from skyfield.positionlib import Barycentric, Geocentric
from skyfield.timelib import Timescale
from skyfield.vectorlib import VectorSum

from ..data_model import SpacecraftState, AOCSTarget, BusMessage, Status, Scenario
from ._common import set_choice, set_enum, tle_lines

class AOCS(Protocol):
    def init(self, scenario:Scenario | None = None) -> None: ...
    def update(self, _state:SpacecraftState, ts:float) -> SpacecraftState: ...
    def command(self, _state:SpacecraftState, message:BusMessage) -> bool | None: ...

class AOCSMin:
    def __init__(self) -> None:
        self.name:str | None = None
        self.time_scale:Timescale | None = None
        self.is_sunlit:bool | None = None
        self.ephemeris:SpiceKernel | None = None
        self.earth:VectorSum | None = None
        self.sun:VectorSum | None = None
        self.satellite:EarthSatellite | None = None

    def init(self, scenario:Scenario | None = None) -> None:
        self.name = "aocs"

        self.time_scale = load.timescale()
        self.is_sunlit = None

        self.ephemeris = cast(SpiceKernel, load("de421.bsp"))
        self.earth = cast(VectorSum, self.ephemeris["earth"])
        self.sun = cast(VectorSum, self.ephemeris["sun"])
        if scenario:
            lines = tle_lines(scenario.tle)
            self.satellite = EarthSatellite(lines[1], lines[2], lines[0])

    def update(self, _state:SpacecraftState, ts:float) -> SpacecraftState:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        time_scale = self.time_scale
        if time_scale is None:
            raise RuntimeError("AOCS time scale has not been initialized")
        t = time_scale.from_datetime(dt)

        position = self._update_position(ts)
        sat_pos = np.asarray(position.position.km, dtype=float)
        subpoint = wgs84.subpoint(position)
        _state.aocs_position = [
            cast(float, subpoint.latitude.degrees),
            cast(float, subpoint.longitude.degrees),
            cast(float, subpoint.elevation.km),
        ]
        earth, sun = self.earth, self.sun
        if earth is None or sun is None:
            raise RuntimeError("AOCS ephemeris bodies have not been initialized")
        ssb_at_t = cast(Barycentric, earth.at(t))
        earth_pos = np.asarray(ssb_at_t.observe(earth).position.km, dtype=float)
        sun_pos = np.asarray(ssb_at_t.observe(sun).position.km, dtype=float)
        _state.is_sunlit = self.is_sunlit

        nadir_dir = earth_pos - sat_pos
        sun_dir = sun_pos - sat_pos

        if _state.aocs_mode != _state.aocs_prev_mode:
            _state.aocs_damp = 0.0
            _state.aocs_prev_mode = _state.aocs_mode

        if _state.aocs_damp < 1.0:
            _state.aocs_damp += 0.05
        _state.aocs_damp = min(_state.aocs_damp, 1.0)

        new_rotation = list(_state.aocs_rotation)

        if _state.aocs_mode in (AOCSTarget.NADIR, AOCSTarget.TARGET):
            new_rotation = self._aocs_euler_angles(nadir_dir, np.array([0, 0, -1]))
            _state.aocs_nadir_angle = (self._aocs_calc_angle(nadir_dir, nadir_dir)
                                        + (1-_state.aocs_damp)*_state.aocs_nadir_angle)
            _state.aocs_sun_angle = self._aocs_calc_angle(sun_dir, nadir_dir) * _state.aocs_damp

        if _state.aocs_mode == AOCSTarget.SUN:
            new_rotation = self._aocs_euler_angles(sun_dir, np.array([0, 0, -1]))
            _state.aocs_nadir_angle = self._aocs_calc_angle(nadir_dir, sun_dir) * _state.aocs_damp
            _state.aocs_sun_angle = self._aocs_calc_angle(sun_dir, sun_dir) + (1-_state.aocs_damp)*_state.aocs_sun_angle

        _state.aocs_rates = list(
            np.absolute(np.array(new_rotation)*_state.aocs_damp) - np.absolute(np.array(_state.aocs_rotation))
        )
        _state.aocs_rotation = list(np.array(new_rotation)*_state.aocs_damp)

        return _state

    def _update_position(self, ts:float) -> Geocentric:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        time_scale = self.time_scale
        if time_scale is None:
            raise RuntimeError("AOCS time scale has not been initialized")
        t = time_scale.from_datetime(dt)

        if self.satellite is None:
            raise RuntimeError("AOCS satellite has not been initialized")
        if self.ephemeris is None:
            raise RuntimeError("AOCS ephemeris has not been initialized")
        position = cast(Geocentric, self.satellite.at(t))
        self.is_sunlit = bool(position.is_sunlit(self.ephemeris))
        return position

    def _aocs_calc_angle(self, v1, v2):
        v1 = v1 / np.linalg.norm(v1)
        v2 = v2 / np.linalg.norm(v2)

        # rounding can push the dot product of unit vectors just past +/-1
        angle_rad = np.arccos(np.clip(np.dot(v1, v2), -1.0, 1.0))
        angle_deg = np.degrees(angle_rad)

        # still NaN for a zero-length vector
        if np.isnan(angle_deg):
            angle_deg = 0.0

        return angle_deg

    def _aocs_euler_angles(self, v1, v2):
        v1 = v1 / np.linalg.norm(v1)
        v2 = v2 / np.linalg.norm(v2)

        # rounding can push the dot product of unit vectors just past +/-1 (NaN from arccos)
        dot_product = np.clip(np.dot(v1, v2), -1.0, 1.0)
        angle = np.arccos(dot_product)

        axis = np.cross(v1, v2)
        axis_norm = np.linalg.norm(axis)
        if not axis_norm > 1e-12:
            if dot_product > 0:
                return np.zeros(3)  # parallel: no rotation
            # antiparallel: any axis perpendicular to v1 gives the 180 deg rotation
            axis = np.cross(v1, [1.0, 0.0, 0.0] if abs(v1[0]) < 0.9 else [0.0, 1.0, 0.0])
            axis_norm = np.linalg.norm(axis)
        axis = axis / axis_norm

        w = np.cos(angle / 2)
        x, y, z = axis * np.sin(angle / 2)
        t0 = 2.0 * (w * x + y * z)
        t1 = 1.0 - 2.0 * (x**2 + y**2)
        roll = np.arctan2(t0, t1)

        t2 = 2.0 * (w * y - z * x)
        t2 = 1 if t2 > 1 else t2
        t2 = -1 if t2 < -1 else t2
        pitch = np.arcsin(t2)

        t3 = 2.0 * (w * z + x * y)
        t4 = 1.0 - 2.0 * (y**2 + z**2)
        yaw = np.arctan2(t3, t4)

        return np.degrees([roll, pitch, yaw])

    def command(self, state:SpacecraftState, message:BusMessage) -> bool | None:
        command = message.payload.get("command")
        value = message.payload.get("value")
        result = None

        if command == "aocs_mode":
            result = set_enum(state, "aocs_mode", value, AOCSTarget, ["SUN", "TARGET", "NADIR"])
        if command == "aocs_chain":
            result = set_choice(state, "aocs_chain", value, ["A", "B"])
        if command == "aocs_valid":
            result = set_enum(state, "aocs_valid", value, Status, ["valid", "not_valid", "unknown"])

        return result
