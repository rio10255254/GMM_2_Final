from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence")
SOURCE = ROOT / "Final_Data_Figures" / "20260710_v42_checkpoint_cd_validation" / "scripts" / "run_individual_cd_validation.py"
OUT = ROOT / "Final_Data_Figures" / "20260710_v42_full_validation"
IMAGE = "Image__2026-06-18__17-10-31.bmp"


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("v42_cd_full", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = load_module(SOURCE)
    module.OUT_ROOT = OUT
    module.TABLE_DIR = OUT / "tables" / "cd"
    module.FIG_DIR = OUT / "figures" / "cd"
    module.CASES["v42_e120"] = (
        "V42 epoch 120",
        OUT / "reconstructions" / "reconstruct_progress_epoch_120_in_20260618_100MG_20260709_202713" / "100mg_static" / IMAGE,
    )
    module.main()


if __name__ == "__main__":
    main()
