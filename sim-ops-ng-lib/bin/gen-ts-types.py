"""Write the MCS's TypeScript state types from the dataclasses (run from sim-ops-ng-lib after changing them)."""

from pathlib import Path

from so.ts_types import render_ts_types

TARGET = Path(__file__).resolve().parents[2] / "sim-ops-ng-mcs" / "src" / "types" / "state.ts"


def main():
    TARGET.parent.mkdir(exist_ok=True)
    TARGET.write_text(render_ts_types(), encoding="utf-8")
    print(f"Wrote {TARGET}")


if __name__ == "__main__":
    main()
