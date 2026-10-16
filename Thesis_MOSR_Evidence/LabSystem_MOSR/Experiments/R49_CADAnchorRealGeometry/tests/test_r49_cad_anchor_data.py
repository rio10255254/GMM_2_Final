from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "r49_cad_anchor_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r49_cad_anchor_data", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    assert ok
    path.write_bytes(encoded.tobytes())


def _write_pair(root: Path, stage: str, name: str, value: int = 128) -> None:
    src = root / "Training_Data" / "generated_convolved" / stage / name
    lbl = root / "Training_Data" / "generated" / stage / name
    _write_image(src, np.full((96, 96), max(0, value - 12), dtype=np.uint8))
    _write_image(lbl, np.full((96, 96), value, dtype=np.uint8))


def _write_ring_pair(root: Path, name: str) -> None:
    src = root / "Training_Data" / "tra_src_ring" / name
    lbl = root / "Training_Data" / "tra_lbl_ring" / name
    _write_image(src, np.full((96, 96), 72, dtype=np.uint8))
    _write_image(lbl, np.full((96, 96), 196, dtype=np.uint8))


def _fake_repo(tmp_path: Path) -> Path:
    module = load_module()
    for idx in range(900):
        _write_ring_pair(tmp_path, f"{idx:04d}.bmp")
    for stage, quota in module.TRAIN_SHAPE_QUOTAS.items():
        for idx in range(quota):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", 120)
    for stage, quota in module.TRAIN_MICRO_QUOTAS.items():
        for idx in range(quota):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", 140)
    for stage, quota in module.TRAIN_R48_BOUNDARY_QUOTAS.items():
        for idx in range(quota):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", 210)
    for stage, quota in module.TRAIN_R48_REAL_BG_QUOTAS.items():
        for idx in range(quota):
            _write_pair(tmp_path, stage, f"{idx:04d}.bmp", 172)
    return tmp_path


def _cad_fixture(tmp_path: Path) -> Path:
    cad_root = tmp_path / "cad"
    rows = []
    for idx in range(12):
        pair_id = f"CB_FIX_{idx:04d}"
        source = np.full((256, 256), 34 + idx, dtype=np.uint8)
        gt = np.zeros((256, 256), dtype=np.uint8)
        mask = np.zeros((256, 256), dtype=np.uint8)
        x0 = 32 + (idx % 3) * 34
        y0 = 38 + (idx % 4) * 22
        cv2.rectangle(source, (x0, y0), (x0 + 96, y0 + 88), 184, -1)
        cv2.rectangle(gt, (x0 + 2, y0 + 2), (x0 + 94, y0 + 86), 255, -1)
        cv2.rectangle(mask, (x0 - 10, y0 - 10), (x0 + 106, y0 + 98), 255, -1)
        src_path = cad_root / "source" / f"{pair_id}.bmp"
        gt_path = cad_root / "gt" / f"{pair_id}_cad_gt.bmp"
        mask_path = cad_root / "mask" / f"{pair_id}_mask.bmp"
        overlay_path = cad_root / "overlay" / f"{pair_id}.png"
        _write_image(src_path, source)
        _write_image(gt_path, gt)
        _write_image(mask_path, mask)
        _write_image(overlay_path, source)
        rows.append(
            {
                "pair_id": pair_id,
                "valid_for_training": "yes",
                "exclusion_reason": "",
                "source_image": str(src_path),
                "gt_image": str(gt_path),
                "reliable_mask": str(mask_path),
                "overlay_check": str(overlay_path),
                "component_count": "1",
                "edge_p95_px": "1.0",
                "edge_within_2px_ratio": "1.0",
            }
        )
    csv_path = cad_root / "data_pairs_valid.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return csv_path


def test_generate_cad_anchor_dataset_blends_untrusted_pixels_and_splits_by_pair(tmp_path: Path):
    module = load_module()
    csv_path = _cad_fixture(tmp_path)
    out = tmp_path / "anchors"

    manifest = module.generate_cad_anchor_dataset(
        csv_path,
        out,
        patch_size=128,
        train_patches_per_pair=3,
        val_patches_per_pair=2,
        test_patches_per_pair=1,
        force=False,
    )

    assert manifest["valid_pair_count"] == 12
    assert manifest["split_pair_counts"] == {"train": 8, "val": 2, "test": 2}
    assert manifest["split_patch_counts"] == {"train": 24, "val": 4, "test": 2}
    train_pair_ids = {row["pair_id"] for row in manifest["records"] if row["split"] == "train"}
    val_pair_ids = {row["pair_id"] for row in manifest["records"] if row["split"] == "val"}
    test_pair_ids = {row["pair_id"] for row in manifest["records"] if row["split"] == "test"}
    assert train_pair_ids.isdisjoint(val_pair_ids)
    assert train_pair_ids.isdisjoint(test_pair_ids)
    assert val_pair_ids.isdisjoint(test_pair_ids)

    first = manifest["records"][0]
    src = cv2.imread(str(out / first["src"]), cv2.IMREAD_GRAYSCALE)
    lbl = cv2.imread(str(out / first["lbl"]), cv2.IMREAD_GRAYSCALE)
    trusted = cv2.imread(str(out / first["mask"]), cv2.IMREAD_GRAYSCALE)
    assert src.shape == (128, 128)
    assert lbl.shape == (128, 128)
    assert trusted.shape == (128, 128)
    assert np.array_equal(lbl[trusted == 0], src[trusted == 0])
    assert np.any(lbl[trusted > 0] != src[trusted > 0])


def test_train_profile_uses_small_real_cad_anchor_ratio_and_geometry_sidecars(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path / "repo")
    csv_path = _cad_fixture(tmp_path)
    anchor_root = repo / "Training_Data" / "r49_cad_anchor_source"
    module.generate_cad_anchor_dataset(csv_path, anchor_root, train_patches_per_pair=50, force=False)

    plan = module.build_plan(repo, module.PROFILES["r49_cad_anchor_train_4000"], anchor_root=anchor_root)
    assert len(plan.pairs) == 4000
    assert plan.count_by_role == {
        "ring": 700,
        "shape": 700,
        "micro": 700,
        "boundary": 1000,
        "real_bg": 500,
        "cad_anchor": 400,
    }

    out = tmp_path / "pkg"
    manifest = module.materialize_plan(plan, out, force=False, link_mode="copy")
    assert manifest["profile"] == "r49_cad_anchor_train_4000"
    assert manifest["total_pairs"] == 4000
    assert manifest["geometry_sidecars"] is True
    assert manifest["geometry_count"] == 4000
    cad_rows = [row for row in manifest["pairs"] if row["role"] == "cad_anchor"]
    assert len(cad_rows) == 400
    assert "source_cad_pair_id" in cad_rows[0]
    role_prefixes = ("ring", "stage_01", "stage_02", "stage_03", "stage_04", "stage_05", "stage_06", "stage_07",
                     "stage_29", "stage_30", "stage_31", "stage_32", "stage_33",
                     "stage_34", "stage_35", "stage_36", "stage_37", "stage_38", "stage_39", "stage_40")
    for row in cad_rows[:10]:
        rel_parts = [part.lower() for part in Path(row["package_src"]).parts]
        assert any(part == "ring" or part.startswith(role_prefixes[1:]) for part in rel_parts)
    first = cad_rows[0]
    rel = Path(first["package_src"]).relative_to("src")
    assert (out / "geom" / "boundary" / rel).exists()
    assert (out / "geom" / "centerline" / rel).exists()
    assert (out / "geom" / "distance" / rel.with_suffix(".npy")).exists()
