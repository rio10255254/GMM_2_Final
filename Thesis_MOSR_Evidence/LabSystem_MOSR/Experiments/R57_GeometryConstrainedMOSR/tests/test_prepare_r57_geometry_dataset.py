from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_r57_geometry_dataset.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_r57_geometry_dataset", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_bmp(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", img)
    assert ok
    path.write_bytes(encoded.tobytes())


def _write_base_package(package: Path) -> None:
    pairs = []
    for idx in range(2):
        src = np.full((64, 64), 72 + idx, np.uint8)
        lbl = np.full((64, 64), 72, np.uint8)
        cv2.circle(lbl, (32, 32), 12 + idx, 180, -1)
        rel = Path("base") / f"sample_{idx:03d}.bmp"
        _write_bmp(package / "src" / rel, src)
        _write_bmp(package / "lbl" / rel, lbl)
        _write_bmp(package / "geom" / "boundary" / rel, np.where(lbl > 100, 255, 0).astype(np.uint8))
        _write_bmp(package / "geom" / "centerline" / rel, np.where(lbl > 100, 255, 0).astype(np.uint8))
        dist_path = package / "geom" / "distance" / rel.with_suffix(".npy")
        dist_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(dist_path, np.zeros((64, 64), np.float32))
        pairs.append(
            {
                "package_src": f"src/{rel.as_posix()}",
                "package_lbl": f"lbl/{rel.as_posix()}",
                "geometry_boundary": f"geom/boundary/{rel.as_posix()}",
                "geometry_centerline": f"geom/centerline/{rel.as_posix()}",
                "geometry_distance": f"geom/distance/{rel.with_suffix('.npy').as_posix()}",
            }
        )
    manifest = {
        "total_pairs": len(pairs),
        "pairs": pairs,
        "geometry_sidecars": True,
        "geometry_count": len(pairs),
        "geom_dir": str(package / "geom"),
    }
    (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_prepare_package_builds_mixed_r55_plus_hs100mg_anchor(tmp_path: Path):
    module = load_module()
    base_package = tmp_path / "base_r55"
    _write_base_package(base_package)

    summary = module.prepare_package(
        base_package=base_package,
        output_root=tmp_path / "out",
        package_name="r57_test_train",
        base_limit=2,
        anchor_count=4,
        image_size=128,
        link_mode="copy",
        seed=123,
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert summary["total_pairs"] == 6
    assert summary["base_pairs"] == 2
    assert summary["anchor_pairs"] == 4
    assert manifest["r57_geometry_constrained"] is True
    assert manifest["camera"] == "Basler ace acA2040-120um"
    assert manifest["nm_per_px"] == 69.0
    assert (package / "src" / "stage_34_hs100mg_anchor" / "pillar").is_dir()
    assert (package / "src" / "stage_34_hs100mg_anchor" / "via").is_dir()
    assert (package / "geom" / "distance" / "stage_34_hs100mg_anchor").is_dir()
    assert not (package / "src" / "anchor").exists()
    assert len(manifest["pairs"]) == 6


def test_anchor_records_encode_asymmetric_cd_source_bias(tmp_path: Path):
    module = load_module()
    base_package = tmp_path / "base_r55"
    _write_base_package(base_package)

    summary = module.prepare_package(
        base_package=base_package,
        output_root=tmp_path / "out",
        package_name="r57_test_train",
        base_limit=0,
        anchor_count=2,
        image_size=128,
        link_mode="copy",
        seed=123,
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    anchor_records = {record["feature"]: record for record in manifest["pairs"]}
    pillar = anchor_records["pillar"]
    via = anchor_records["via"]

    assert pillar["source_radius_nm"] > pillar["target_radius_nm"]
    assert via["source_radius_nm"] < via["target_radius_nm"]
    assert pillar["correction_direction"] == "shrink_pillar"
    assert via["correction_direction"] == "expand_via"


def test_shared_layout_draws_source_and_label_with_same_centers():
    module = load_module()
    rng = np.random.default_rng(123)
    layout = module._sample_circle_layout(image_size=128, pitch_px=72.5, rng=rng)
    style = {"bg": 50, "fg": 200}
    source = module._draw_circle_layout(
        feature="pillar",
        image_size=128,
        radius_px=18.0,
        layout=layout,
        style=style,
    )
    label = module._draw_circle_layout(
        feature="pillar",
        image_size=128,
        radius_px=20.0,
        layout=layout,
        style=style,
    )
    src_cx, src_cy = _feature_centroid(source, "pillar")
    lbl_cx, lbl_cy = _feature_centroid(label, "pillar")
    center_delta = ((src_cx - lbl_cx) ** 2 + (src_cy - lbl_cy) ** 2) ** 0.5
    assert center_delta <= 0.5


def _feature_centroid(img: np.ndarray, feature: str) -> tuple[float, float]:
    if feature == "pillar":
        mask = img > np.percentile(img, 70)
    else:
        mask = img < np.percentile(img, 30)
    ys, xs = np.nonzero(mask)
    assert len(xs) > 0
    return float(xs.mean()), float(ys.mean())
