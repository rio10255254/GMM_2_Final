"""Run the unchanged locked R73/R74 ACM pipeline through the R114E adapter."""

from probes.r114e_decoupled_hybrid import adapter
from validation import run_split_profile_locked_acm as locked


def main() -> int:
    locked.load_model = adapter.load_model
    locked.canonical_tile_config = adapter.canonical_tile_config
    locked.predict_canonical_tiled = adapter.predict_canonical_tiled
    return locked.main()


if __name__ == "__main__":
    raise SystemExit(main())

