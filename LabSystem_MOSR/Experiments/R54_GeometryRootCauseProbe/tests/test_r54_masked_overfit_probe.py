from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "r54_masked_overfit_probe.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r54_masked_overfit_probe", SCRIPT_PATH)
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


def _write_selected_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_make_masked_label_uses_cad_gt_only_inside_reliable_mask():
    module = load_module()
    src = np.full((8, 8), 30, dtype=np.uint8)
    gt = np.full((8, 8), 220, dtype=np.uint8)
    mask = np.zeros((8, 8), dtype=np.uint8)
    mask[2:6, 3:7] = 255

    label = module.make_masked_label(src, gt, mask)

    assert np.array_equal(label[mask == 0], src[mask == 0])
    assert np.array_equal(label[mask > 0], gt[mask > 0])


def test_materialize_overfit_package_writes_masks_geometry_and_manifest(tmp_path: Path):
    module = load_module()
    src = np.full((80, 80), 46, dtype=np.uint8)
    gt = src.copy()
    mask = np.zeros((80, 80), dtype=np.uint8)
    cv2.rectangle(mask, (20, 20), (59, 59), 255, -1)
    cv2.rectangle(gt, (20, 20), (59, 59), 212, -1)
    source = tmp_path / "source.bmp"
    cad_gt = tmp_path / "gt.bmp"
    reliable_mask = tmp_path / "mask.bmp"
    _write_gray(source, src)
    _write_gray(cad_gt, gt)
    _write_gray(reliable_mask, mask)
    selected_csv = tmp_path / "selected.csv"
    _write_selected_csv(
        selected_csv,
        [
            {
                "pair_id": "unit_pair",
                "source_image": str(source),
                "gt_image": str(cad_gt),
                "reliable_mask": str(reliable_mask),
                "edge_p95_px": "0.955",
                "edge_within_2px_ratio": "1.0",
                "coverage": "0.25",
                "component_count": "1",
            }
        ],
    )

    package_dir = tmp_path / "package"
    manifest = module.materialize_overfit_package(
        selected_csv,
        package_dir,
        patch_size=32,
        patches_per_pair=2,
        min_trusted_ratio=0.10,
        force=False,
    )

    assert manifest["profile"] == "r54_masked_small_overfit_train"
    assert manifest["total_pairs"] == 2
    assert manifest["label_policy"] == module.LABEL_POLICY
    assert manifest["geometry_sidecars"] is True
    assert manifest["geometry_count"] == 2
    assert (package_dir / "manifest.json").exists()
    assert (package_dir / "src").is_dir()
    assert (package_dir / "lbl").is_dir()
    assert (package_dir / "mask").is_dir()

    records = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))["pairs"]
    for record in records:
        src_patch = cv2.imread(str(package_dir / record["package_src"]), cv2.IMREAD_GRAYSCALE)
        lbl_patch = cv2.imread(str(package_dir / record["package_lbl"]), cv2.IMREAD_GRAYSCALE)
        mask_patch = cv2.imread(str(package_dir / record["package_mask"]), cv2.IMREAD_GRAYSCALE)
        assert src_patch is not None
        assert lbl_patch is not None
        assert mask_patch is not None
        assert np.array_equal(lbl_patch[mask_patch == 0], src_patch[mask_patch == 0])
        assert np.any(lbl_patch[mask_patch > 0] != src_patch[mask_patch > 0])
        assert (package_dir / record["geometry_boundary"]).exists()
        assert (package_dir / record["geometry_centerline"]).exists()
        assert (package_dir / record["geometry_distance"]).exists()

    validation = module.validate_package(package_dir)
    assert validation["total_pairs"] == 2
    assert validation["outside_mask_mismatch_pixels"] == 0
    assert validation["inside_mask_changed_pairs"] == 2


def test_patch_planner_prefers_cad_edge_regions_over_flat_trusted_area():
    module = load_module()
    mask = np.full((96, 96), 255, dtype=np.uint8)
    gt = np.full((96, 96), 240, dtype=np.uint8)
    gt[:, 8:14] = 20

    patches = module.plan_masked_patches(
        mask,
        guide=gt,
        patch_size=24,
        patches_per_pair=1,
        min_trusted_ratio=0.5,
        base_seed=123,
        pair_id="edge_unit",
    )

    patch = patches[0]
    crop = gt[int(patch["y0"]) : int(patch["y0"]) + 24, int(patch["x0"]) : int(patch["x0"]) + 24]
    assert np.any(crop < 100)
    assert patch["edge_ratio"] > 0.0


def test_supervision_mask_adds_cad_edge_band_when_reliable_mask_excludes_edges():
    module = load_module()
    reliable = np.zeros((64, 64), dtype=np.uint8)
    reliable[24:40, 24:40] = 255
    gt = np.full((64, 64), 255, dtype=np.uint8)
    gt[:, 8:12] = 0

    supervision = module.build_supervision_mask(reliable, gt, edge_band_radius=3)

    assert np.count_nonzero(supervision[:, 8:12]) > 0
    assert np.count_nonzero(supervision[24:40, 24:40]) == 16 * 16
