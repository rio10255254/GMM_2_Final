from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


RECON_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_r52_checkboard_reconstruction.py"


def load_module(path: Path, name: str):
    script_dir = path.parent
    sys.path.insert(0, str(script_dir))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_weight(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake")


def test_reconstruction_case_specs_select_best_and_latest(tmp_path: Path):
    module = load_module(RECON_SCRIPT, "run_r52_checkboard_reconstruction")
    training_root = tmp_path / "Traing_Progress"
    run_dir = (
        training_root
        / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r52_stability_from_r51_mixed_best_formal_e100_20260614_225415"
    )
    _write_weight(run_dir / "weights" / "best_tradeoff.pth.tar")
    _write_weight(run_dir / "weights" / "latest.pth.tar")

    specs = module.build_case_specs(training_root, ["r52_stability_from_r51_mixed_best"])

    assert [spec.case_name for spec in specs] == [
        "lab_r52_stability_best_tradeoff",
        "lab_r52_stability_latest",
    ]
    assert all(spec.weights.exists() for spec in specs)
    assert module.build_infer_argv(specs[0], Path("input"), Path("recon"), "cuda:0")[0] == "--weights"
