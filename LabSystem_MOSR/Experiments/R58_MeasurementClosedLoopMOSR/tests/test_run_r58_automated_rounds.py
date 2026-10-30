from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_r58_automated_rounds.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_r58_automated_rounds", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_summary(path: Path, label: str, via: float, pillar: float) -> None:
    rows = [
        {"image": label, "feature": "圓孔", "n": 10, "abs_radius_error_vs_sem_nm": via},
        {"image": label, "feature": "圓柱", "n": 10, "abs_radius_error_vs_sem_nm": pillar},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_candidate_plan_uses_expected_profiles(tmp_path: Path):
    module = load_module()

    plans = module.build_candidate_plans(
        candidates=["r58_frac025", "r58_frac050"],
        num_epoch=2,
        max_train_batches=3,
        batch_size=2,
        run_suffix="unit",
        data_root=tmp_path / "data",
        output_root=tmp_path / "out",
        device="cpu",
    )

    assert [plan.candidate for plan in plans] == ["r58_frac025", "r58_frac050"]
    assert plans[0].training_label == "r58_frac025_unit"
    assert "--candidate" in plans[0].train_command
    assert "r58_frac025" in plans[0].train_command
    assert "--max-train-batches" in plans[0].train_command
    assert str(tmp_path / "data") in plans[0].train_command


def test_rank_candidates_prefers_lowest_mean_cd_error(tmp_path: Path):
    module = load_module()
    first = tmp_path / "first" / "cd_measurement_summary.csv"
    second = tmp_path / "second" / "cd_measurement_summary.csv"
    _write_summary(first, "r58_frac025", via=60.0, pillar=20.0)
    _write_summary(second, "r58_frac050", via=50.0, pillar=12.0)

    ranked = module.rank_cd_results(
        [
            {"candidate": "r58_frac025", "summary_csv": str(first)},
            {"candidate": "r58_frac050", "summary_csv": str(second)},
        ],
        reference_mean_abs_radius_error_nm=38.59,
    )

    assert ranked[0]["candidate"] == "r58_frac050"
    assert ranked[0]["mean_abs_radius_error_nm"] == 31.0
    assert ranked[0]["beats_original_mean"] is True
    assert ranked[1]["candidate"] == "r58_frac025"


def test_write_results_report_contains_best_candidate(tmp_path: Path):
    module = load_module()
    report = tmp_path / "R58_AUTOMATED_ROUNDS_STATUS.md"
    payload = {
        "status": "dry_run",
        "ranked_results": [
            {
                "candidate": "r58_frac050",
                "mean_abs_radius_error_nm": 31.0,
                "beats_original_mean": True,
            }
        ],
    }

    module.write_status_report(report, payload)

    text = report.read_text(encoding="utf-8")
    assert "R58 Automated Rounds Status" in text
    assert "r58_frac050" in text
    assert "31.00" in text
    assert json.loads((report.with_suffix(".json")).read_text(encoding="utf-8"))["status"] == "dry_run"
