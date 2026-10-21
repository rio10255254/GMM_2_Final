from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_r58_measurement_dataset.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_r58_measurement_dataset", SCRIPT_PATH)
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
        src = np.full((96, 96), 70 + idx, np.uint8)
        lbl = np.full((96, 96), 72, np.uint8)
        cv2.circle(lbl, (48, 48), 14 + idx, 170, -1, lineType=cv2.LINE_AA)
        rel = Path("base") / f"sample_{idx:03d}.bmp"
        _write_bmp(package / "src" / rel, src)
        _write_bmp(package / "lbl" / rel, lbl)
        _write_bmp(package / "geom" / "boundary" / rel, np.where(lbl > 100, 255, 0).astype(np.uint8))
        _write_bmp(package / "geom" / "centerline" / rel, np.where(lbl > 100, 255, 0).astype(np.uint8))
        dist_path = package / "geom" / "distance" / rel.with_suffix(".npy")
        dist_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(dist_path, np.zeros((96, 96), np.float32))
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


def _feature_radius_px(img: np.ndarray, feature: str) -> float:
    if feature == "pillar":
        mask = img > np.percentile(img, 70)
    else:
        mask = img < np.percentile(img, 30)
    ys, xs = np.nonzero(mask)
    assert len(xs) > 0
    cx = float(xs.mean())
    cy = float(ys.mean())
    return float(np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2).mean() * 1.5)


def test_r58_fractional_anchor_uses_weak_cd_correction(tmp_path: Path):
    module = load_module()
    base_package = tmp_path / "base_r55"
    _write_base_package(base_package)

    summary = module.prepare_package(
        base_package=base_package,
        output_root=tmp_path / "out",
        package_name="r58_frac050_train",
        base_limit=0,
        anchor_count=2,
        image_size=160,
        correction_fraction=0.5,
        seed=123,
        link_mode="copy",
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    records = {row["feature"]: row for row in manifest["pairs"]}

    pillar = records["pillar"]
    via = records["via"]
    assert manifest["r58_measurement_closed_loop"] is True
    assert manifest["correction_fraction"] == 0.5
    assert pillar["source_radius_nm"] > pillar["target_radius_nm"]
    assert via["source_radius_nm"] < via["target_radius_nm"]
    assert abs(pillar["target_radius_nm"] - pillar["sem_radius_nm"]) < abs(pillar["source_radius_nm"] - pillar["sem_radius_nm"])
    assert abs(via["target_radius_nm"] - via["sem_radius_nm"]) < abs(via["source_radius_nm"] - via["sem_radius_nm"])
    assert abs(pillar["applied_correction_fraction"] - 0.5) <= 1e-9
    assert abs(via["applied_correction_fraction"] - 0.5) <= 1e-9


def test_r58_source_and_label_keep_same_circle_centers():
    module = load_module()
    rng = np.random.default_rng(123)
    layout = module._sample_circle_layout(image_size=160, pitch_px=72.5, rng=rng)
    style = module._sample_circle_style(feature="pillar", rng=rng)
    source_label = module._draw_circle_layout(
        feature="pillar",
        image_size=160,
        radius_px=18.0,
        layout=layout,
        style=style,
    )
    target_label = module._draw_circle_layout(
        feature="pillar",
        image_size=160,
        radius_px=19.0,
        layout=layout,
        style=style,
    )

    src_cx, src_cy = module._feature_centroid(source_label, "pillar")
    lbl_cx, lbl_cy = module._feature_centroid(target_label, "pillar")
    assert ((src_cx - lbl_cx) ** 2 + (src_cy - lbl_cy) ** 2) ** 0.5 <= 0.5


def test_r58_real_style_source_is_less_sharp_than_clean_label():
    module = load_module()
    rng = np.random.default_rng(456)
    label = np.full((160, 160), 74, np.uint8)
    for y in (40, 80, 120):
        for x in (40, 80, 120):
            cv2.circle(label, (x, y), 18, 174, -1, lineType=cv2.LINE_AA)

    source = module._make_real_style_source(label, rng=rng, target_grad95=64.0)

    assert source.dtype == np.uint8
    assert source.shape == label.shape
    assert module._gradient_p95(source) < module._gradient_p95(label)
    assert 35.0 <= module._gradient_p95(source) <= 95.0


def test_prepare_package_writes_geometry_sidecars_for_all_pairs(tmp_path: Path):
    module = load_module()
    base_package = tmp_path / "base_r55"
    _write_base_package(base_package)

    summary = module.prepare_package(
        base_package=base_package,
        output_root=tmp_path / "out",
        package_name="r58_test_train",
        base_limit=2,
        anchor_count=4,
        image_size=128,
        correction_fraction=0.25,
        seed=789,
        link_mode="copy",
    )

    package = Path(summary["package_dir"])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert summary["total_pairs"] == 6
    assert manifest["geometry_sidecars"] is True
    assert manifest["geometry_count"] == 6
    assert len(manifest["pairs"]) == 6
    assert (package / "geom" / "boundary" / "stage_58_hs100mg_anchor").is_dir()
    assert (package / "geom" / "distance" / "stage_58_hs100mg_anchor").is_dir()
