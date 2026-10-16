from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "r54_masked_overfit_eval.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r54_masked_overfit_eval", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    assert ok
    path.write_bytes(encoded.tobytes())


def test_masked_metrics_separates_inside_gt_error_from_outside_source_drift():
    module = load_module()
    src = np.full((6, 6), 10, dtype=np.uint8)
    lbl = src.copy()
    mask = np.zeros((6, 6), dtype=np.uint8)
    mask[2:4, 2:4] = 255
    lbl[mask > 0] = 110
    pred = src.copy()
    pred[mask > 0] = 90
    pred[0, 0] = 60

    metrics = module.masked_metrics(src, lbl, mask, pred)

    assert metrics["inside_mae_to_label"] == 20.0
    assert metrics["outside_mae_to_source"] > 0.0
    assert metrics["inside_mae_input_to_label"] == 100.0
    assert metrics["inside_improvement_vs_input_pct"] == 80.0


def test_evaluate_case_reads_manifest_records_and_recon_outputs(tmp_path: Path):
    module = load_module()
    package = tmp_path / "package"
    name = "sample_000.bmp"
    src = np.full((8, 8), 20, dtype=np.uint8)
    lbl = src.copy()
    mask = np.zeros((8, 8), dtype=np.uint8)
    mask[2:6, 2:6] = 255
    lbl[mask > 0] = 120
    pred = src.copy()
    pred[mask > 0] = 100
    for leaf, image in (("src", src), ("lbl", lbl), ("mask", mask)):
        _write_gray(package / leaf / "stage" / name, image)
    manifest = {
        "profile": "unit",
        "total_pairs": 1,
        "pairs": [
            {
                "package_src": f"src/stage/{name}",
                "package_lbl": f"lbl/stage/{name}",
                "package_mask": f"mask/stage/{name}",
            }
        ],
    }
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    recon = tmp_path / "recon"
    _write_gray(recon / name, pred)

    summary = module.evaluate_case(package, "unit_case", recon)

    assert summary["case"] == "unit_case"
    assert summary["image_count"] == 1
    assert summary["inside_mae_to_label_mean"] == 20.0
    assert summary["inside_improvement_vs_input_pct_mean"] == 80.0
