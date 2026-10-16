from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "rebuild_source_style_training_data.py"
AUDIT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_training_data_style.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_source_style_label_removes_hard_binary_cad_fill() -> None:
    rebuild = _load_module("rebuild_source_style_training_data", SCRIPT_PATH)
    audit = _load_module("audit_training_data_style", AUDIT_PATH)

    x = np.linspace(82, 168, 64, dtype=np.float32)
    src = np.tile(x, (64, 1)).astype(np.uint8)
    src = cv2.GaussianBlur(src, (0, 0), 1.2)
    cad = np.zeros((64, 64), dtype=np.uint8)
    cad[:, 32:] = 255
    mask = np.full((64, 64), 255, dtype=np.uint8)

    repaired = rebuild.make_source_style_label(src, cad, mask)
    metrics = audit.measure_pair_style(src, repaired)
    verdict = audit.classify_pair_style(metrics)

    assert repaired.shape == src.shape
    assert metrics["lbl_saturation_frac"] == 0
    assert "hard_binary_label" not in verdict["flags"]
    assert metrics["ncc"] > 0.95

    edge_band = np.zeros_like(src, dtype=bool)
    edge_band[:, 26:39] = True
    far_from_edge = ~edge_band
    assert np.max(np.abs(repaired[far_from_edge].astype(np.int16) - src[far_from_edge].astype(np.int16))) <= 2


def test_rebuild_package_repairs_flagged_pair_and_preserves_counts(tmp_path: Path) -> None:
    rebuild = _load_module("rebuild_source_style_training_data_tmp", SCRIPT_PATH)
    audit = _load_module("audit_training_data_style_tmp", AUDIT_PATH)

    training_root = tmp_path / "Training_Data"
    src_dir = training_root / "bad_package" / "src" / "stage_a"
    lbl_dir = training_root / "bad_package" / "lbl" / "stage_a"
    src_dir.mkdir(parents=True)
    lbl_dir.mkdir(parents=True)

    src = np.tile(np.linspace(90, 165, 48, dtype=np.float32), (48, 1)).astype(np.uint8)
    hard = np.zeros((48, 48), dtype=np.uint8)
    hard[:, 24:] = 255
    safe = np.clip(src.astype(np.int16) + 1, 0, 255).astype(np.uint8)

    bad_src = src_dir / "bad.bmp"
    bad_lbl = lbl_dir / "bad.bmp"
    safe_src = src_dir / "safe.bmp"
    safe_lbl = lbl_dir / "safe.bmp"
    cv2.imwrite(str(bad_src), src)
    cv2.imwrite(str(bad_lbl), hard)
    cv2.imwrite(str(safe_src), src)
    cv2.imwrite(str(safe_lbl), safe)

    unsafe_csv = tmp_path / "unsafe.csv"
    with unsafe_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["package", "src", "lbl", "flags"])
        writer.writeheader()
        writer.writerow({"package": "bad_package", "src": str(bad_src), "lbl": str(bad_lbl), "flags": "hard_binary_label"})

    out_root = tmp_path / "rebuilt"
    summary = rebuild.rebuild_from_audit(
        training_root=training_root,
        unsafe_csv=unsafe_csv,
        output_root=out_root,
        force=True,
        packages=["bad_package"],
    )

    assert summary["total_pairs"] == 2
    assert summary["repaired_pairs"] == 1
    rebuilt_pkg = out_root / "bad_package"
    assert len(list((rebuilt_pkg / "src").rglob("*.bmp"))) == 2
    assert len(list((rebuilt_pkg / "lbl").rglob("*.bmp"))) == 2

    repaired = cv2.imread(str(rebuilt_pkg / "lbl" / "stage_a" / "bad.bmp"), cv2.IMREAD_GRAYSCALE)
    assert repaired is not None
    metrics = audit.measure_pair_style(src, repaired)
    verdict = audit.classify_pair_style(metrics)
    assert "hard_binary_label" not in verdict["flags"]
    assert verdict["risk"] in {"low", "medium"}


def test_rebuild_repairs_cad_anchor_path_even_without_audit_flag(tmp_path: Path) -> None:
    rebuild = _load_module("rebuild_source_style_training_data_cad_tmp", SCRIPT_PATH)

    training_root = tmp_path / "Training_Data"
    rel = Path("stage_40_boundary_mixed") / "stage_57_cad_anchor_real" / "val"
    src_dir = training_root / "cad_package" / "src" / rel
    lbl_dir = training_root / "cad_package" / "lbl" / rel
    src_dir.mkdir(parents=True)
    lbl_dir.mkdir(parents=True)

    src = np.tile(np.linspace(80, 170, 48, dtype=np.float32), (48, 1)).astype(np.uint8)
    hard = np.zeros((48, 48), dtype=np.uint8)
    hard[:, 24:] = 255
    src_path = src_dir / "cad.bmp"
    lbl_path = lbl_dir / "cad.bmp"
    cv2.imwrite(str(src_path), src)
    cv2.imwrite(str(lbl_path), hard)

    unsafe_csv = tmp_path / "unsafe.csv"
    with unsafe_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["package", "src", "lbl", "flags"])
        writer.writeheader()

    summary = rebuild.rebuild_from_audit(
        training_root=training_root,
        unsafe_csv=unsafe_csv,
        output_root=tmp_path / "rebuilt",
        force=True,
        packages=["cad_package"],
    )

    assert summary["total_pairs"] == 1
    assert summary["repaired_pairs"] == 1
