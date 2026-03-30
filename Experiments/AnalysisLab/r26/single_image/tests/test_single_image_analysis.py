from __future__ import annotations

import importlib.util
from pathlib import Path

import cv2
import numpy as np
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_single_image_analysis.py"
SPEC = importlib.util.spec_from_file_location("single_image_analysis", MODULE_PATH)
analysis = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(analysis)


def make_ring_image(
    *,
    shape: tuple[int, int] = (256, 256),
    center: tuple[int, int] = (128, 150),
    inner_r: int = 56,
    outer_r: int = 76,
    blur_sigma: float = 3.2,
    noise_sigma: float = 3.0,
    gap_range: tuple[float, float] | None = None,
    seed: int = 0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    yy, xx = np.indices(shape)
    cx, cy = center
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    theta = np.arctan2(yy - cy, xx - cx)

    img = np.full(shape, 132.0, dtype=np.float32)
    img[rr < inner_r] = 136.0
    annulus = (rr >= inner_r) & (rr <= outer_r)
    img[annulus] = 225.0

    defect_mask = annulus & (theta > 0.55) & (theta < 0.82)
    img[defect_mask] = 176.0

    weak_zone = annulus & (theta < -2.2) & (theta > -2.7)
    img[weak_zone] = 206.0

    background_blob = ((xx - 40) ** 2 + (yy - 24) ** 2) < 14**2
    img[background_blob] = 88.0

    if gap_range is not None:
        gap_mask = annulus & (theta > gap_range[0]) & (theta < gap_range[1])
        img[gap_mask] = 140.0

    if blur_sigma > 0:
        img = cv2.GaussianBlur(img, (0, 0), blur_sigma)

    if noise_sigma > 0:
        img = img + rng.normal(0.0, noise_sigma, size=shape).astype(np.float32)

    return np.clip(img, 0, 255).astype(np.uint8)


@pytest.fixture()
def sharp_ring() -> np.ndarray:
    return make_ring_image(blur_sigma=1.2, noise_sigma=1.2, seed=2)


def test_detect_annulus_reference_recovers_offcenter_ring_geometry():
    img = make_ring_image(blur_sigma=2.0, noise_sigma=2.0, seed=1)

    ref = analysis.detect_annulus_reference(img.astype(np.float64))

    assert ref["status"] == "ok"
    assert abs(ref["cx"] - 128) <= 5
    assert abs(ref["cy"] - 150) <= 5
    assert abs(ref["r_inner"] - 56) <= 8
    assert abs(ref["r_outer"] - 76) <= 8


def test_sharp_ring_circle_fit_keeps_high_coverage_and_consistent_centers(sharp_ring):
    ref = analysis.detect_annulus_reference(sharp_ring.astype(np.float64))
    edge_data = analysis.extract_radial_edge_candidates(
        sharp_ring.astype(np.float64),
        ref["cx"],
        ref["cy"],
        ref["r_inner"],
        ref["r_outer"],
    )
    fit = analysis.summarize_circle_fits(edge_data, ref["cx"], ref["cy"])

    assert fit["status"] == "ok"
    assert fit["inner"]["coverage_ratio"] >= 0.9
    assert fit["outer"]["coverage_ratio"] >= 0.9
    assert fit["center_offset_px"] <= 2.0


def test_gapped_ring_is_reported_as_warning_instead_of_clean_fit():
    img = make_ring_image(
        blur_sigma=2.0,
        noise_sigma=2.0,
        gap_range=(-1.2, 0.1),
        seed=4,
    )

    ref = analysis.detect_annulus_reference(img.astype(np.float64))
    edge_data = analysis.extract_radial_edge_candidates(
        img.astype(np.float64),
        ref["cx"],
        ref["cy"],
        ref["r_inner"],
        ref["r_outer"],
    )
    fit = analysis.summarize_circle_fits(edge_data, ref["cx"], ref["cy"])

    assert fit["status"] == "warning"
    assert fit["inner"]["coverage_ratio"] < 0.9 or fit["outer"]["coverage_ratio"] < 0.9


def test_real_image_regression_finds_ring_near_true_output_geometry():
    out = analysis.load_image(analysis.RECON_PATH)

    ref = analysis.detect_annulus_reference(out)
    edge_data = analysis.extract_radial_edge_candidates(out, ref["cx"], ref["cy"], ref["r_inner"], ref["r_outer"])
    fit = analysis.summarize_circle_fits(edge_data, ref["cx"], ref["cy"])

    assert 760 <= ref["cx"] <= 785
    assert 1495 <= ref["cy"] <= 1525
    assert 470 <= ref["r_inner"] <= 500
    assert 585 <= ref["r_outer"] <= 610
    assert fit["inner"]["coverage_ratio"] >= 0.88
    assert fit["outer"]["coverage_ratio"] >= 0.88
    assert fit["center_offset_px"] < 5.0


def test_main_writes_expected_artifacts_and_quality_fields(tmp_path: Path):
    out_dir = tmp_path / "analysis_results"

    summary = analysis.main(out_dir=out_dir, verbose=False)

    expected_files = {
        "01_edge_profiles.png",
        "02_circle_fit.png",
        "03_angular_consistency.png",
        "04_frequency_spectrum.png",
        "05_overview_and_artifacts.png",
        "06_edge_width_angular.png",
        "07_residual_harmonics.png",
        "08_residual_hotspot.png",
        "analysis_summary.json",
    }
    assert expected_files == {path.name for path in out_dir.iterdir()}
    assert summary["annulus_geometry"]["status"] in {"ok", "warning", "failed"}
    assert "method" in summary["annulus_geometry"]
    assert "warnings" in summary["annulus_geometry"]
    assert "status" in summary["circle_fit"]["output"]["inner"]
    assert "coverage_ratio" in summary["circle_fit"]["output"]["outer"]
    assert "residual_harmonics" in summary
    assert summary["residual_harmonics"]["output_outer_dominant_k"] is not None
    assert "output_outer_energy" in summary["residual_harmonics"]
    assert "hotspot_clusters" in summary
    assert summary["hotspot_clusters"]["output_outer"]["n_clusters"] >= 0
