from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "r54_geometry_root_cause_probe.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r54_geometry_root_cause_probe", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_corner_damage_diagnosis_flags_reconstruction_damage():
    module = load_module()
    summary_rows = [
        {
            "case": "raw_input",
            "median_corner_peak_shift_px": "1.414",
            "pct_peak_shift_gt_5px": "1.676",
        },
        {
            "case": "lab_r40_best_tradeoff",
            "median_corner_peak_shift_px": "4.243",
            "pct_peak_shift_gt_5px": "24.581",
        },
        {
            "case": "lab_r53_realistic_latest",
            "median_corner_peak_shift_px": "9.220",
            "pct_peak_shift_gt_5px": "58.939",
        },
    ]

    diagnosis = module.diagnose_corner_damage(summary_rows)

    assert diagnosis["reconstruction_damage_detected"] is True
    assert diagnosis["raw_is_best_geometry_reference"] is True
    assert diagnosis["worst_case"] == "lab_r53_realistic_latest"
    assert diagnosis["r53_latest_over5_delta_vs_r40_pct"] > 30.0
    assert diagnosis["recommended_next_gate"] == "block_long_training_until_small_probe_passes"


def test_cad_reference_summary_marks_partial_gt_and_probe_ready(tmp_path):
    module = load_module()
    valid_csv = tmp_path / "valid.csv"
    quality_csv = tmp_path / "quality.csv"
    rows = [
        {
            "pair_id": "a",
            "valid_for_training": "yes",
            "source_image": "src_a.bmp",
            "gt_image": "gt_a.bmp",
            "reliable_mask": "mask_a.bmp",
            "component_count": "2",
            "edge_p95_px": "0.955",
            "edge_within_2px_ratio": "1.0",
        },
        {
            "pair_id": "b",
            "valid_for_training": "yes",
            "source_image": "src_b.bmp",
            "gt_image": "gt_b.bmp",
            "reliable_mask": "mask_b.bmp",
            "component_count": "1",
            "edge_p95_px": "1.5",
            "edge_within_2px_ratio": "0.98",
        },
    ]
    with valid_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with quality_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source_name", "status", "component_count", "coverage", "reliable_area_px", "edge_p95_px"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source_name": "src_a.bmp",
                "status": "ok",
                "component_count": "2",
                "coverage": "0.20",
                "reliable_area_px": "40000",
                "edge_p95_px": "0.955",
            }
        )
        writer.writerow(
            {
                "source_name": "src_b.bmp",
                "status": "ok",
                "component_count": "1",
                "coverage": "0.10",
                "reliable_area_px": "20000",
                "edge_p95_px": "1.5",
            }
        )

    summary = module.summarize_cad_reference(valid_csv, quality_csv)

    assert summary["valid_pair_count"] == 2
    assert summary["partial_gt_only"] is True
    assert summary["probe_ready"] is True
    assert summary["max_edge_p95_px"] == 1.5


def test_select_overfit_probe_pairs_keeps_best_reliable_rows():
    module = load_module()
    rows = [
        {"pair_id": "bad", "valid_for_training": "no", "edge_p95_px": "0.5", "edge_within_2px_ratio": "1.0"},
        {"pair_id": "mid", "valid_for_training": "yes", "edge_p95_px": "1.4", "edge_within_2px_ratio": "0.99"},
        {"pair_id": "best", "valid_for_training": "yes", "edge_p95_px": "0.7", "edge_within_2px_ratio": "1.0"},
    ]

    selected = module.select_overfit_probe_pairs(rows, limit=1)

    assert [row["pair_id"] for row in selected] == ["best"]
