"""TypeScript types for the broadcast state, rendered from the dataclasses so the MCS can't drift from them.

`bin/gen-ts-types.py` writes them to sim-ops-ng-mcs/src/types/state.ts; a test checks that file is current.
"""
import types
import typing
from enum import Enum

from .data_model import SpacecraftState, GroundStationState

# fields SimOps._broadcast_state() drops before sending
OMITTED_FIELDS = {GroundStationState: {'flight_dynamics'}}

_PRIMITIVES = {float: 'number', int: 'number', str: 'string', bool: 'boolean', dict: 'Record<string, unknown>'}


def _ts_type(hint, enums: dict[str, type[Enum]]) -> str:
    if hint in _PRIMITIVES:
        return _PRIMITIVES[hint]
    if isinstance(hint, type) and issubclass(hint, Enum):
        enums[hint.__name__] = hint
        return hint.__name__
    origin, args = typing.get_origin(hint), typing.get_args(hint)
    if origin is list:
        inner = _ts_type(args[0], enums)
        return f"({inner})[]" if ' | ' in inner else f"{inner}[]"
    if origin is tuple:
        return "[" + ", ".join(_ts_type(a, enums) for a in args) + "]"
    if origin in (typing.Union, types.UnionType):
        return ' | '.join('null' if a is types.NoneType else _ts_type(a, enums) for a in args)
    raise TypeError(f"No TypeScript type for {hint!r}")


def render_ts_types() -> str:
    enums: dict[str, type[Enum]] = {}
    blocks = []
    for cls in (SpacecraftState, GroundStationState):
        omitted = OMITTED_FIELDS.get(cls, set())
        fields = [f"  {name}: {_ts_type(hint, enums)}"
                  for name, hint in typing.get_type_hints(cls).items() if name not in omitted]
        # a type alias, not an interface: assignable to the index-signature TelemetryState
        blocks.append(f"export type {cls.__name__} = {{\n" + "\n".join(fields) + "\n}")

    # enums are serialised by name (data_model.custom_dict_factory)
    enum_lines = [f"export type {name} = " + " | ".join(f"'{m.name}'" for m in enum)
                  for name, enum in sorted(enums.items())]

    header = ("// Generated from sim-ops-ng-lib/so/data_model.py by sim-ops-ng-lib/bin/gen-ts-types.py: do not edit.\n"
              "// The spacecraft and ground station state, as broadcast to the MCS.\n")
    return header + "\n" + "\n".join(enum_lines) + "\n\n" + "\n\n".join(blocks) + "\n"
