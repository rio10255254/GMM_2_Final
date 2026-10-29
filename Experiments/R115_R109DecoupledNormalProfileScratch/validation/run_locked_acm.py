"""Reuse the unchanged locked R73/R74 ACM pipeline with the R115 adapter."""
from __future__ import annotations

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
R114 = Path(str(PROJECT_ROOT / 'Experiments/R114_ConfidenceGatedRecoverableScratch'))
for path in (R114, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from validation import adapter
from validation import run_split_profile_locked_acm as locked


def main() -> int:
    locked.load_model = adapter.load_model
    locked.canonical_tile_config = adapter.canonical_tile_config
    locked.predict_canonical_tiled = adapter.predict_canonical_tiled
    return locked.main()


if __name__ == "__main__":
    raise SystemExit(main())
