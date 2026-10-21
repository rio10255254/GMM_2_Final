"""Run the unchanged locked R73/R74 ACM pipeline with the R114D adapter."""

from __future__ import annotations

from probes.r114d_action_selector import adapter
from validation import run_split_profile_locked_acm as locked


def main() -> int:
    # Reuse the sealed runner and change only its inference adapter.  All ACM
    # scripts, manifests, parameters, alignments, metrics, and audits remain
    # exactly those of ``run_split_profile_locked_acm``.
    locked.load_model = adapter.load_model
    locked.canonical_tile_config = adapter.canonical_tile_config
    locked.predict_canonical_tiled = adapter.predict_canonical_tiled
    return locked.main()


if __name__ == "__main__":
    raise SystemExit(main())
