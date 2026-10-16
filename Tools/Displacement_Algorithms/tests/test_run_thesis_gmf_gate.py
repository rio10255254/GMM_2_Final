from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPTS_DIR = Path(r"D:\GMM_2_Final\Tools\Displacement_Algorithms\scripts")
sys.path.insert(0, str(SCRIPTS_DIR))


def make_blob_frame(
    center_x: float,
    center_y: float,
    *,
    shape: tuple[int, int] = (96, 128),
    sigma: float = 4.0,
) -> np.ndarray:
    yy, xx = np.indices(shape, dtype=np.float32)
    blob = np.exp(-(((xx - center_x) ** 2) + ((yy - center_y) ** 2)) / (2.0 * sigma * sigma))
    image = 40.0 + 180.0 * blob
    return np.clip(image, 0, 255).astype(np.uint8)


def write_sequence(folder: Path, *, dx: float, dy: float, jitter: list[float]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    x = 38.0
    y = 47.0
    for index, extra in enumerate(jitter):
        image = make_blob_frame(x + index * dx + extra, y + index * dy)
        ok, encoded = cv2.imencode(".bmp", image)
        assert ok
        (folder / f"frame_{index:03d}.bmp").write_bytes(encoded.tobytes())


def test_default_specs_cover_current_thesis_groups() -> None:
    from run_thesis_gmf_gate import default_case_specs

    specs = default_case_specs()
    groups = {(spec.dataset, spec.group) for spec in specs}

    assert groups == {
        ("20260702_100MG", "x_1um"),
        ("20260702_100MG", "x_0p5um"),
        ("20260704_20x_5x", "20x_1um"),
        ("20260704_20x_5x", "20x_0p5um"),
        ("20260704_20x_5x", "5x_1um"),
        ("20260704_20x_5x", "5x_0p5um"),
    }
    scale_by_group = {spec.group: spec.object_um_per_px for spec in specs}
    assert abs(scale_by_group["x_1um"] - 0.069) < 1e-9
    assert abs(scale_by_group["20x_1um"] - 0.1725) < 1e-9
    assert abs(scale_by_group["5x_1um"] - 0.69) < 1e-9


def test_summarize_measurement_converts_pixel_stability_to_um() -> None:
    from run_thesis_gmf_gate import GateSpec, summarize_measurement

    spec = GateSpec(
        dataset="toy",
        group="g",
        root=Path("."),
        cases={"raw": "raw"},
        nominal_um=1.0,
        object_um_per_px=0.25,
        roi=None,
        roi_label="whole",
        polarity="bright",
    )
    summary = {"valid_step_count": 5, "std_dx_px": 0.2, "mean_dx_px": -4.0, "failed_step_count": 0}

    row = summarize_measurement(spec, "raw", summary)

    assert row["std_um"] == 0.05
    assert row["step_um"] == 1.0
    assert row["step_error_um"] == 0.0
    assert row["status"] == "ok"


def test_build_comparison_reports_best_case_and_improvement_direction() -> None:
    from run_thesis_gmf_gate import build_comparison

    rows = [
        {"dataset": "toy", "group": "g", "case": "raw", "std_um": 0.10, "status": "ok"},
        {"dataset": "toy", "group": "g", "case": "r61", "std_um": 0.08, "status": "ok"},
        {"dataset": "toy", "group": "g", "case": "v7", "std_um": 0.06, "status": "ok"},
    ]

    comparison = build_comparison(rows, baseline_case="raw", candidate_case="v7")

    assert comparison == [
        {
            "dataset": "toy",
            "group": "g",
            "baseline_case": "raw",
            "candidate_case": "v7",
            "best_case": "v7",
            "baseline_std_um": 0.10,
            "candidate_std_um": 0.06,
            "candidate_vs_baseline_improvement_pct": 40.0,
        }
    ]


def test_build_selection_summary_prioritizes_primary_cases_and_counts_guardrails() -> None:
    from run_thesis_gmf_gate import build_selection_summary

    rows = [
        {"dataset": "main", "group": "a", "case": "raw", "std_um": 0.10},
        {"dataset": "main", "group": "a", "case": "v9", "std_um": 0.08},
        {"dataset": "main", "group": "b", "case": "raw", "std_um": 0.20},
        {"dataset": "main", "group": "b", "case": "v9", "std_um": 0.18},
        {"dataset": "guard", "group": "c", "case": "raw", "std_um": 0.10},
        {"dataset": "guard", "group": "c", "case": "v9", "std_um": 0.11},
    ]

    summary = build_selection_summary(
        rows,
        candidate_case="v9",
        primary_keys={("main", "a"), ("main", "b")},
        baseline_case="raw",
    )

    assert summary["candidate_case"] == "v9"
    assert summary["primary_case_count"] == 2
    assert summary["guardrail_case_count"] == 1
    assert round(float(summary["primary_mean_improvement_pct"]), 6) == 15.0
    assert summary["guardrail_worse_count"] == 1
    assert float(summary["guardrail_worst_regression_pct"]) == -10.0


def test_apply_extra_case_templates_adds_new_candidate_to_all_specs() -> None:
    from run_thesis_gmf_gate import apply_extra_case_templates, default_case_specs

    specs = apply_extra_case_templates(
        default_case_specs(),
        ["v8=r62_v8_gmfgate_psfoff_{group}\\bmp"],
    )

    assert specs
    assert all(spec.cases["v8"] == r"r62_v8_gmfgate_psfoff_{group}\bmp" for spec in specs)
    assert all("raw" in spec.cases and "r61" in spec.cases and "v7" in spec.cases for spec in specs)


def test_apply_extra_case_templates_rejects_malformed_case_definition() -> None:
    from run_thesis_gmf_gate import apply_extra_case_templates, default_case_specs

    try:
        apply_extra_case_templates(default_case_specs(), ["v8_without_equals"])
    except ValueError as exc:
        assert "case=relative_template" in str(exc)
    else:
        raise AssertionError("malformed extra case definition should raise ValueError")


def test_apply_mode_override_changes_all_specs_without_touching_cases() -> None:
    from run_thesis_gmf_gate import apply_mode_override, default_case_specs

    specs = default_case_specs()
    updated = apply_mode_override(specs, "pairwise")

    assert all(spec.mode == "pairwise" for spec in updated)
    assert all(before.cases == after.cases for before, after in zip(specs, updated))


def test_apply_signal_mode_override_changes_all_specs() -> None:
    from run_thesis_gmf_gate import apply_signal_mode_override, default_case_specs

    updated = apply_signal_mode_override(default_case_specs(), "edge")

    assert all(spec.signal_mode == "edge" for spec in updated)


def test_evaluate_spec_runs_open_gmf_like_measurement(tmp_path: Path) -> None:
    from run_thesis_gmf_gate import GateSpec, evaluate_spec

    write_sequence(tmp_path / "raw", dx=1.0, dy=0.0, jitter=[0.0, 0.00, 0.00, 0.00, 0.00])
    write_sequence(tmp_path / "v7", dx=1.0, dy=0.0, jitter=[0.0, 0.02, -0.01, 0.01, 0.00])
    spec = GateSpec(
        dataset="toy",
        group="g",
        root=tmp_path,
        cases={"raw": "raw", "v7": "v7"},
        nominal_um=1.0,
        object_um_per_px=1.0,
        roi=None,
        roi_label="whole",
        polarity="bright",
        mode="single",
        signal_mode="edge",
    )

    rows = evaluate_spec(spec, tmp_path / "out")

    assert {row["case"] for row in rows} == {"raw", "v7"}
    assert all(row["status"] == "ok" for row in rows)
    assert {row["signal_mode"] for row in rows} == {"edge"}
    assert (tmp_path / "out" / "toy_g_raw_steps.csv").exists()
    assert (tmp_path / "out" / "toy_g_v7_summary.json").exists()
