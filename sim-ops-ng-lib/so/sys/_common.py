
import math

from ..data_model import Status, AOCSTarget


def finite_float(value) -> float:
    """float(value), rejecting NaN/inf: they survive min/max clamps and serialise to invalid JSON."""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"expected a finite number, got {value!r}")
    return number


def tle_lines(tle: str) -> list[str]:
    """The non-blank lines of a TLE, stripped: [name, line 1, line 2] for a valid one."""
    return [x.strip() for x in tle.split("\n") if x.strip()]


def set_choice(state, attr: str, value, choices: list) -> bool:
    """Assign a plain (non-enum) command value if it's one of the allowed choices."""
    if value in choices:
        setattr(state, attr, value)
        return True
    return False


def set_enum(state, attr: str, value, enum_cls, choices: list | None = None) -> bool:
    """Assign an Enum-valued command, converting the incoming string via enum_cls[value]."""
    if value in (choices if choices is not None else enum_cls.__members__):
        setattr(state, attr, enum_cls[value])
        return True
    return False


def safe_chain_swap(state) -> None:
    """Force OBSW to safe and AOCS to Sun-pointing on a redundancy chain swap."""
    state.dhs_obsw_mode = Status.safe
    state.aocs_mode = AOCSTarget.SUN
