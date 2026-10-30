from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_r57_cd_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_r57_cd_gate", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_summary(path: Path, candidate_errors: dict[str, float]) -> None:
    rows = [
        {"image": "原圖", "feature": "圓孔", "n": 10, "abs_radius_error_vs_sem_nm": 66.0},
        {"image": "原圖", "feature": "圓柱", "n": 10, "abs_radius_error_vs_sem_nm": 11.0},
        {
            "image": "R57候選",
            "feature": "圓孔",
            "n": 10,
            "abs_radius_error_vs_sem_nm": candidate_errors["圓孔"],
        },
        {
            "image": "R57候選",
            "feature": "圓柱",
            "n": 10,
            "abs_radius_error_vs_sem_nm": candidate_errors["圓柱"],
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_cd_gate_passes_candidate_that_is_not_worse_than_original(tmp_path: Path):
    module = load_module()
    summary = tmp_path / "summary.csv"
    _write_summary(summary, {"圓孔": 60.0, "圓柱": 10.0})

    result = module.evaluate_cd_gate(
        summary_csv=summary,
        candidate_image="R57候選",
        reference_image="原圖",
        tolerance_nm=0.0,
    )

    assert result["passed"] is True
    assert result["feature_results"]["圓孔"]["passed"] is True
    assert result["feature_results"]["圓柱"]["passed"] is True


def test_cd_gate_fails_candidate_that_worsens_either_feature(tmp_path: Path):
    module = load_module()
    summary = tmp_path / "summary.csv"
    _write_summary(summary, {"圓孔": 80.0, "圓柱": 10.0})

    result = module.evaluate_cd_gate(
        summary_csv=summary,
        candidate_image="R57候選",
        reference_image="原圖",
        tolerance_nm=0.0,
    )

    assert result["passed"] is False
    assert result["feature_results"]["圓孔"]["passed"] is False
    assert result["feature_results"]["圓柱"]["passed"] is True

