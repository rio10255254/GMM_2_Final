from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


RECON_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_r51_checkboard_reconstruction.py"
VALIDATION_SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "Reconstruct_Progress"
    / "20250605_checkboard_external_gmf_prepare"
    / "validate_checkboard_corner_geometry_r51.py"
)


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
    module = load_module(RECON_SCRIPT, "run_r51_checkboard_reconstruction")
    training_root = tmp_path / "Traing_Progress"
    run_dir = (
        training_root
        / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r51_gaussian_corner_probe_short_e012_b080_20260614_215954"
    )
    _write_weight(run_dir / "weights" / "best_tradeoff.pth.tar")
    _write_weight(run_dir / "weights" / "latest.pth.tar")

    specs = module.build_case_specs(training_root, ["r51_gaussian_corner_probe"])

    assert [spec.case_name for spec in specs] == [
        "lab_r51_gaussian_best_tradeoff",
        "lab_r51_gaussian_latest",
    ]
    assert all(spec.weights.exists() for spec in specs)
    assert module.build_infer_argv(specs[0], Path("input"), Path("recon"), "cuda:0")[0] == "--weights"


def test_validation_cases_include_r51_outputs():
    module = load_module(VALIDATION_SCRIPT, "validate_checkboard_corner_geometry_r51")

    cases = [case for case, _label in module.CASES]

    assert "lab_r40_best_tradeoff" in cases
    assert "lab_r51_gaussian_best_tradeoff" in cases
    assert "lab_r51_weak_bads_best_tradeoff" in cases
    assert "lab_r51_mixed_psf_best_tradeoff" in cases
    assert "lab_r51_mixed_psf_latest" in cases
