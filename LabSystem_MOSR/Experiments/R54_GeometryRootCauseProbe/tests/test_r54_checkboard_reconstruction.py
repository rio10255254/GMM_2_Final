from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


RECON_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_r54_checkboard_reconstruction.py"
VALIDATION_SCRIPT = (
    Path(__file__).resolve().parents[3]
    / "Reconstruct_Progress"
    / "20250605_checkboard_external_gmf_prepare"
    / "validate_checkboard_corner_geometry_r54.py"
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


def test_reconstruction_case_spec_selects_r54_edgeband_epoch20(tmp_path: Path):
    module = load_module(RECON_SCRIPT, "run_r54_checkboard_reconstruction")
    training_root = tmp_path / "Traing_Progress"
    valid_run = (
        training_root
        / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r54_masked_overfit_from_r40_edgeband_e020_20260616_224650"
    )
    invalid_old_run = (
        training_root
        / "training_progress_LAB_GESR_v1_v5_ST0p8_SWP_r54_masked_overfit_from_r40_overfit_e020_full_20260616_223421"
    )
    _write_weight(valid_run / "epoch_020.pth.tar")
    _write_weight(invalid_old_run / "epoch_020.pth.tar")

    specs = module.build_case_specs(training_root, ["r54_masked_overfit_from_r40_edgeband_e020"])

    assert len(specs) == 1
    spec = specs[0]
    assert spec.case_name == "lab_r54_edgeband_epoch020"
    assert spec.checkpoint_kind == "epoch020"
    assert "edgeband" in spec.run_dir.name
    assert "overfit_e020_full" not in spec.run_dir.name
    assert spec.weights == valid_run / "epoch_020.pth.tar"

    argv = module.build_infer_argv(spec, Path("input"), Path("recon"), "cuda:0")
    assert argv[0] == "--weights"
    assert "--psf-fitted-path" in argv
    assert "--no-psf-from-ckpt" in argv


def test_sync_case_to_gmf_copies_only_bmps_under_cases_root(tmp_path: Path):
    module = load_module(RECON_SCRIPT, "run_r54_checkboard_reconstruction_sync")
    module.GMF_CASES_ROOT = tmp_path / "gmf_cases"
    output_dir = tmp_path / "recon"
    output_dir.mkdir()
    (output_dir / "Image__0001.bmp").write_bytes(b"bmp1")
    (output_dir / "Image__0002.bmp").write_bytes(b"bmp2")
    (output_dir / "notes.txt").write_text("skip", encoding="utf-8")

    sync = module.sync_case_to_gmf(output_dir, "lab_r54_edgeband_epoch020")

    case_dir = module.GMF_CASES_ROOT / "lab_r54_edgeband_epoch020"
    assert sync["bmp_count"] == 2
    assert sorted(path.name for path in case_dir.glob("*")) == ["Image__0001.bmp", "Image__0002.bmp"]


def test_validation_cases_include_r54_edgeband_output():
    module = load_module(VALIDATION_SCRIPT, "validate_checkboard_corner_geometry_r54")

    cases = [case for case, _label in module.CASES]

    assert "raw_input" in cases
    assert "lab_r40_best_tradeoff" in cases
    assert "lab_r53_realistic_best_tradeoff" in cases
    assert "lab_r53_realistic_latest" in cases
    assert "lab_r54_edgeband_epoch020" in cases
    assert "R54_GeometryRootCauseProbe" in str(module.REPORT_PATH)
    assert "corner_geometry_validation_r54" in str(module.OUTPUT_DIR)
