from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "score_generalization_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("score_generalization_gate", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_metrics_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "case_id",
        "seed",
        "bias_px",
        "blur_sigma",
        "noise_sigma",
        "image",
        "region",
        "shape",
        "polarity",
        "chamfer_px",
        "area_error_px2",
        "abs_area_error_px2",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def metric_row(
    *,
    case_id: str,
    value: float,
    polarity: str,
    bias_px: float = 0.0,
    shape: str = "circle",
    image: str = "model_recon",
) -> dict:
    return {
        "case_id": case_id,
        "seed": 1,
        "bias_px": bias_px,
        "blur_sigma": 1.0,
        "noise_sigma": 1.0,
        "image": image,
        "region": f"{polarity}_{shape}_{case_id}",
        "shape": shape,
        "polarity": polarity,
        "chamfer_px": value,
        "area_error_px2": 0.0,
        "abs_area_error_px2": 0.0,
    }


def test_gate_fails_when_candidate_average_improves_but_dark_boundary_regresses(tmp_path: Path):
    module = load_module()
    baseline_csv = tmp_path / "baseline.csv"
    candidate_csv = tmp_path / "candidate.csv"
    baseline_rows = [
        metric_row(case_id="a", value=1.0, polarity="bright", bias_px=0.0, shape="circle"),
        metric_row(case_id="b", value=1.0, polarity="bright", bias_px=0.5, shape="ellipse"),
        metric_row(case_id="c", value=1.0, polarity="dark", bias_px=0.0, shape="circle"),
        metric_row(case_id="d", value=1.0, polarity="dark", bias_px=0.5, shape="ellipse"),
        metric_row(case_id="ignored", value=99.0, polarity="dark", image="input_biased_blurred"),
    ]
    candidate_rows = [
        metric_row(case_id="a", value=0.2, polarity="bright", bias_px=0.0, shape="circle"),
        metric_row(case_id="b", value=0.2, polarity="bright", bias_px=0.5, shape="ellipse"),
        metric_row(case_id="c", value=1.1, polarity="dark", bias_px=0.0, shape="circle"),
        metric_row(case_id="d", value=1.1, polarity="dark", bias_px=0.5, shape="ellipse"),
    ]
    write_metrics_csv(baseline_csv, baseline_rows)
    write_metrics_csv(candidate_csv, candidate_rows)

    report = module.evaluate_gate(
        module.load_metric_rows(baseline_csv),
        module.load_metric_rows(candidate_csv),
        tolerance_px=0.0,
    )

    assert report["pass"] is False
    assert any(
        failure["scope"] == "polarity" and failure["group"] == "dark" and failure["metric"] == "mean_chamfer_px"
        for failure in report["failures"]
    )
    assert report["summary"]["overall"]["candidate"]["mean_chamfer_px"] < report["summary"]["overall"]["baseline"]["mean_chamfer_px"]


def test_gate_passes_when_candidate_improves_all_required_groups(tmp_path: Path):
    module = load_module()
    baseline_csv = tmp_path / "baseline.csv"
    candidate_csv = tmp_path / "candidate.csv"
    baseline_rows = [
        metric_row(case_id="a", value=0.8, polarity="bright", bias_px=0.0, shape="circle"),
        metric_row(case_id="b", value=0.9, polarity="bright", bias_px=0.5, shape="ellipse"),
        metric_row(case_id="c", value=1.0, polarity="dark", bias_px=0.0, shape="circle"),
        metric_row(case_id="d", value=1.1, polarity="dark", bias_px=0.5, shape="ellipse"),
    ]
    candidate_rows = [
        metric_row(case_id="a", value=0.7, polarity="bright", bias_px=0.0, shape="circle"),
        metric_row(case_id="b", value=0.8, polarity="bright", bias_px=0.5, shape="ellipse"),
        metric_row(case_id="c", value=0.9, polarity="dark", bias_px=0.0, shape="circle"),
        metric_row(case_id="d", value=1.0, polarity="dark", bias_px=0.5, shape="ellipse"),
    ]
    write_metrics_csv(baseline_csv, baseline_rows)
    write_metrics_csv(candidate_csv, candidate_rows)

    report = module.evaluate_gate(module.load_metric_rows(baseline_csv), module.load_metric_rows(candidate_csv))

    assert report["pass"] is True
    assert report["failures"] == []


def test_cli_writes_report_json_without_failed_exit_when_requested(tmp_path: Path):
    module = load_module()
    baseline_csv = tmp_path / "baseline.csv"
    candidate_csv = tmp_path / "candidate.csv"
    output_json = tmp_path / "gate_report.json"
    write_metrics_csv(
        baseline_csv,
        [
            metric_row(case_id="a", value=1.0, polarity="bright"),
            metric_row(case_id="b", value=1.0, polarity="dark"),
        ],
    )
    write_metrics_csv(
        candidate_csv,
        [
            metric_row(case_id="a", value=0.1, polarity="bright"),
            metric_row(case_id="b", value=1.2, polarity="dark"),
        ],
    )

    rc = module.main(
        [
            "--baseline-csv",
            str(baseline_csv),
            "--candidate-csv",
            str(candidate_csv),
            "--candidate-name",
            "candidate",
            "--output-json",
            str(output_json),
            "--no-fail-exit",
        ]
    )

    assert rc == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["candidate_name"] == "candidate"
    assert payload["pass"] is False
