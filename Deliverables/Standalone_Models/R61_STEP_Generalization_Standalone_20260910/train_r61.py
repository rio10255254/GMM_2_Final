"""Portable R61 v16 training entry point.

The full R61 candidate configuration remains in scripts/launch_r61.py.
This file provides the package-root command used by the standalone README.
"""
from __future__ import annotations

import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = PACKAGE_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import launch_r61  # noqa: E402


DEFAULT_CANDIDATE = "r61_motion_texture_stepguard_v16_dualgate_boundary_focus"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--candidate" not in args and "--help" not in args and "-h" not in args:
        args = ["--candidate", DEFAULT_CANDIDATE, *args]
    return int(launch_r61.main(args))


if __name__ == "__main__":
    raise SystemExit(main())
