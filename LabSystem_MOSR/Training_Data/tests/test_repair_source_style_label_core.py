from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "repair_source_style_label_core.py"
AUDIT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_training_data_style.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_bmp(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", img)
    assert ok
    path.write_bytes(encoded.tobytes())


def _edge_grad_p95(img: np.ndarray, band: np.ndarray | None = None) -> float:
    f = img.astype(np.float32)
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(gx, gy)
    if band is not None:
        grad = grad[band]
    return float(np.percentile(grad, 95))


def test_core_repair_sharpens_soft_source_style_boundary_without_hard_fill() -> None:
    repair = _load_module("repair_source_style_label_core", SCRIPT_PATH)
    audit = _load_module("audit_training_data_style_for_core", AUDIT_PATH)

    src = np.full((96, 96), 82, dtype=np.uint8)
    src[:, 48:] = 168
    src = cv2.GaussianBlur(src, (0, 0), 2.2)
    old_lbl = np.zeros((96, 96), dtype=np.uint8)
    old_lbl[:, 48:] = 255
    soft_lbl = repair.make_soft_source_style_label_for_test(src, old_lbl)

    fixed, info = repair.repair_label_core(src, soft_lbl, old_lbl)
    edge_band = np.zeros_like(src, dtype=bool)
    edge_band[:, 42:55] = True
    soft_ratio = _edge_grad_p95(soft_lbl, edge_band) / max(_edge_grad_p95(src, edge_band), 1e-6)
    fixed_ratio = _edge_grad_p95(fixed, edge_band) / max(_edge_grad_p95(src, edge_band), 1e-6)
    metrics = audit.measure_pair_style(src, fixed)
    verdict = audit.classify_pair_style(metrics)

    assert info["method"] in {"region_core", "unsharp_core"}
    assert soft_ratio < 1.35
    assert fixed_ratio >= 2.0
    assert metrics["lbl_saturation_frac"] < 0.05
    assert "hard_binary_label" not in verdict["flags"]
    assert np.max(np.abs(fixed[:, :35].astype(np.int16) - soft_lbl[:, :35].astype(np.int16))) <= 3
    assert np.max(np.abs(fixed[:, 61:].astype(np.int16) - soft_lbl[:, 61:].astype(np.int16))) <= 3


def test_core_repair_does_not_weaken_dense_grid_labels() -> None:
    repair = _load_module("repair_source_style_label_core_grid", SCRIPT_PATH)

    src = np.full((96, 96), 116, dtype=np.uint8)
    for x in range(8, 96, 8):
        src[:, x : x + 1] = 154
    src = cv2.GaussianBlur(src, (0, 0), 1.0)
    anchor = np.full((96, 96), 80, dtype=np.uint8)
    for x in range(8, 96, 8):
        anchor[:, x : x + 1] = 220
    current = repair.make_soft_source_style_label_for_test(src, anchor)

    fixed, info = repair.repair_label_core(src, current, anchor)
    band = anchor > 180
    before = _edge_grad_p95(current, band) / max(_edge_grad_p95(src, band), 1e-6)
    after = _edge_grad_p95(fixed, band) / max(_edge_grad_p95(src, band), 1e-6)

    assert info["method"] in {"unsharp_core", "region_core"}
    assert after >= before


def test_package_repair_fixes_marked_and_metric_soft_pairs_without_touching_good_pair(tmp_path: Path) -> None:
    repair = _load_module("repair_source_style_label_core_pkg", SCRIPT_PATH)

    package = tmp_path / "r53_realistic_calibrated_train_6000"
    src = np.full((80, 80), 76, dtype=np.uint8)
    src[:, 40:] = 166
    src = cv2.GaussianBlur(src, (0, 0), 1.9)
    old_lbl = np.zeros((80, 80), dtype=np.uint8)
    old_lbl[:, 40:] = 255
    soft_lbl = repair.make_soft_source_style_label_for_test(src, old_lbl)
    good_lbl = np.full((80, 80), 76, dtype=np.uint8)
    good_lbl[:, 40:] = 166

    _write_bmp(package / "src" / "stage" / "bad_marked.bmp", src)
    _write_bmp(package / "lbl" / "stage" / "bad_marked.bmp", soft_lbl)
    _write_bmp(package / "old" / "stage" / "bad_marked.bmp", old_lbl)
    _write_bmp(package / "src" / "stage" / "bad_metric.bmp", src)
    _write_bmp(package / "lbl" / "stage" / "bad_metric.bmp", soft_lbl)
    _write_bmp(package / "old" / "stage" / "bad_metric.bmp", old_lbl)
    _write_bmp(package / "src" / "stage" / "good.bmp", src)
    _write_bmp(package / "lbl" / "stage" / "good.bmp", good_lbl)

    manifest = {
        "generator": "test",
        "total_pairs": 3,
        "pairs": [
            {
                "package_src": "src/stage/bad_marked.bmp",
                "package_lbl": "lbl/stage/bad_marked.bmp",
                "src": str(package / "src" / "stage" / "bad_marked.bmp"),
                "lbl": str(package / "old" / "stage" / "bad_marked.bmp"),
                "repaired": True,
                "repair_reason": "cad_anchor_source_style_rebuild",
            },
            {
                "package_src": "src/stage/bad_metric.bmp",
                "package_lbl": "lbl/stage/bad_metric.bmp",
                "src": str(package / "src" / "stage" / "bad_metric.bmp"),
                "lbl": str(package / "old" / "stage" / "bad_metric.bmp"),
                "repaired": False,
                "repair_reason": "",
            },
            {
                "package_src": "src/stage/good.bmp",
                "package_lbl": "lbl/stage/good.bmp",
                "src": str(package / "src" / "stage" / "good.bmp"),
                "lbl": str(package / "lbl" / "stage" / "good.bmp"),
                "repaired": False,
                "repair_reason": "",
            },
        ],
    }
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    output_root = tmp_path / "out"
    summary = repair.repair_packages(
        package_dirs=[package],
        output_root=output_root,
        force=True,
        grad_ratio_threshold=1.5,
        emit_preview=False,
    )

    out_pkg = output_root / package.name
    out_manifest = json.loads((out_pkg / "manifest.json").read_text(encoding="utf-8"))
    out_pairs = {Path(item["package_src"]).name: item for item in out_manifest["pairs"]}
    fixed_marked = cv2.imread(str(out_pkg / out_pairs["bad_marked.bmp"]["package_lbl"]), cv2.IMREAD_GRAYSCALE)
    fixed_metric = cv2.imread(str(out_pkg / out_pairs["bad_metric.bmp"]["package_lbl"]), cv2.IMREAD_GRAYSCALE)
    fixed_good = cv2.imread(str(out_pkg / out_pairs["good.bmp"]["package_lbl"]), cv2.IMREAD_GRAYSCALE)

    assert summary["total_pairs"] == 3
    assert summary["core_repaired_pairs"] == 2
    assert out_pairs["bad_marked.bmp"]["core_repaired"] is True
    assert out_pairs["bad_metric.bmp"]["core_repaired"] is True
    assert out_pairs["good.bmp"]["core_repaired"] is False
    edge_band = np.zeros_like(src, dtype=bool)
    edge_band[:, 35:46] = True
    assert _edge_grad_p95(fixed_marked, edge_band) / max(_edge_grad_p95(src, edge_band), 1e-6) >= 2.0
    assert _edge_grad_p95(fixed_metric, edge_band) / max(_edge_grad_p95(src, edge_band), 1e-6) >= 2.0
    assert np.array_equal(fixed_good, good_lbl)
