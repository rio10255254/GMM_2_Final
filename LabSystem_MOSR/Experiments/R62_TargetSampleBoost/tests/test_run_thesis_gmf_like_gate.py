from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_thesis_gmf_like_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_thesis_gmf_like_gate", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_shifted_dark_spots(folder: Path, *, shift_px: float = 3.0, count: int = 4) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    centers = [(30, 30), (70, 30), (30, 70), (70, 70)]
    for idx in range(count):
        image = np.full((100, 100), 220, dtype=np.uint8)
        for cx, cy in centers:
            cv2.circle(image, (int(round(cx + idx * shift_px)), cy), 5, 40, -1)
        cv2.imwrite(str(folder / f"frame_{idx:04d}.bmp"), image)


def test_gmf_like_sequence_tracks_known_dark_spot_shift(tmp_path: Path):
    module = load_module()
    image_dir = tmp_path / "bmp"
    _write_shifted_dark_spots(image_dir, shift_px=3.0, count=5)

    summary, rows = module.analyze_case(
        image_dir,
        output_dir=tmp_path / "out",
        dataset="toy",
        group="x",
        case="raw",
        roi_label="toy_dark",
        crop=(0, 0, 100, 100),
        polarity="dark",
        nominal_um=1.0,
        object_um_per_px=1.0,
        local_radius=8.0,
        cluster_radius=1.0,
    )

    assert summary["status"] == "ok"
    assert summary["valid_step_count"] == 4
    assert abs(summary["mean_dx_px"] - 3.0) < 0.35
    assert summary["std_dx_px"] < 0.35
    assert rows[0]["status"] == "reference"
    assert rows[1]["tracked_feature_count"] == 4


def test_result_row_matches_candidate_scorer_columns(tmp_path: Path):
    module = load_module()
    image_dir = tmp_path / "bmp"
    _write_shifted_dark_spots(image_dir, shift_px=2.0, count=3)

    summary, _rows = module.analyze_case(
        image_dir,
        output_dir=tmp_path / "out",
        dataset="toy",
        group="x",
        case="candidate",
        roi_label="toy_dark",
        crop=(0, 0, 100, 100),
        polarity="dark",
        nominal_um=0.5,
        object_um_per_px=0.25,
        local_radius=8.0,
        cluster_radius=1.0,
    )
    result = module.result_row_from_summary(summary)

    required = {
        "dataset",
        "group",
        "case",
        "valid_step_count",
        "failed_step_count",
        "std_um",
        "step_um",
        "step_error_um",
        "input_dir",
        "steps_csv",
        "summary_json",
    }
    assert required <= set(result)
    assert result["case"] == "candidate"
    assert abs(float(result["step_um"]) - 0.5) < 0.1


def test_shape_aware_profile_uses_square_edge_roi_for_5x():
    module = load_module()

    datasets = module.datasets_for_profile("shape_aware_square")
    spec = next(item for item in datasets if item["dataset"] == "20260704_20x_5x")

    assert spec["crop_by_group"]["5x_1um"] == (985, 395, 185, 115)
    assert spec["crop_by_group"]["5x_0p5um"] == (985, 395, 185, 115)
    assert spec["signal_mode_by_group"]["5x_1um"] == "edge"
    assert spec["signal_mode_by_group"]["5x_0p5um"] == "edge"
    assert spec["min_area_by_group"]["5x_1um"] == 4
    assert spec["threshold_quantile_by_group"]["5x_1um"] == 0.55
    assert spec["roi_label_by_group"]["5x_1um"] == "shape_aware_square_block_5x"


def test_run_gate_uses_profile_specific_group_settings(monkeypatch, tmp_path: Path):
    module = load_module()
    calls: list[dict[str, object]] = []

    def fake_analyze_case(input_dir, **kwargs):
        calls.append(dict(kwargs))
        summary = {
            "algorithm": "fake",
            "input_dir": str(input_dir),
            "dataset": kwargs["dataset"],
            "group": kwargs["group"],
            "case": kwargs["case"],
            "roi_label": kwargs["roi_label"],
            "polarity": kwargs["polarity"],
            "mode": "multi",
            "signal_mode": kwargs["signal_mode"],
            "nominal_um": kwargs["nominal_um"],
            "object_um_per_px": kwargs["object_um_per_px"],
            "valid_step_count": 1,
            "failed_step_count": 0,
            "mean_dx_px": 1.0,
            "std_dx_px": 0.1,
            "std_um": 0.01,
            "step_um": kwargs["nominal_um"],
            "step_error_um": 0.0,
            "status": "ok",
            "steps_csv": str(tmp_path / "steps.csv"),
            "summary_json": str(tmp_path / "summary.json"),
        }
        return summary, []

    monkeypatch.setattr(module, "analyze_case", fake_analyze_case)
    spec = {
        "dataset": "toy",
        "root": tmp_path,
        "groups": ["5x_1um"],
        "nominal_um": {"5x_1um": 1.0},
        "object_um_per_px": {"5x_1um": 0.5},
        "roi_label": "default_roi",
        "roi_label_by_group": {"5x_1um": "square_roi"},
        "crop": (0, 0, 100, 100),
        "crop_by_group": {"5x_1um": (10, 20, 30, 40)},
        "polarity": "bright",
        "signal_mode_by_group": {"5x_1um": "edge"},
        "threshold_quantile_by_group": {"5x_1um": 0.55},
        "min_area_by_group": {"5x_1um": 4},
        "local_radius": 8.0,
        "cluster_radius": 1.0,
    }

    module.run_gate(
        output_dir=tmp_path / "out",
        cases={"raw": "raw_inputs/{group}/bmp"},
        candidate_case="raw",
        dataset_specs=[spec],
    )

    assert calls[0]["roi_label"] == "square_roi"
    assert calls[0]["crop"] == (10, 20, 30, 40)
    assert calls[0]["signal_mode"] == "edge"
    assert calls[0]["threshold_quantile"] == 0.55
    assert calls[0]["min_area"] == 4
