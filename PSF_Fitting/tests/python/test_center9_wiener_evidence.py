import csv
import json
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.io import loadmat
PROJECT_ROOT = Path(__file__).resolve().parents[3]


PACKAGE_ROOT = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/03_PSF_EXPERIMENT_RESULTS/01_global_bads_fit')
)
FIGURE_ROOT = PACKAGE_ROOT / "figures" / "center9_pillar_fit_20x_50x"
TABLE_ROOT = PACKAGE_ROOT / "tables" / "center9_pillar_fit_20x_50x"
SOURCE_ROOT = (
    PACKAGE_ROOT
    / "source_data"
    / "center9_pillar_fit_20x_50x"
    / "psf_deconvolution_cd"
)
SPECTRUM_ROOT = SOURCE_ROOT.parent / "spectra"
WIENER_ROOT = SOURCE_ROOT


def read_csv(name: str) -> list[dict[str, str]]:
    with (TABLE_ROOT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_center9_wiener_outputs_match_frozen_parameters_and_all_pillar_results() -> None:
    summaries = read_csv("cd_before_after_summary.csv")
    per_pillar = read_csv("cd_before_after_per_pillar.csv")
    sensitivity = read_csv("cd_threshold_sensitivity.csv")

    assert len(summaries) == 2
    assert {row["magnification"] for row in summaries} == {"20x", "50x"}
    assert len(per_pillar) == 18
    assert len(sensitivity) == 6

    recipe = (SOURCE_ROOT / "run_wiener_deconvolution.m").read_text(encoding="utf-8")
    fixed_nsr = float(re.search(r"calibrated_common_nsr\s*=\s*([0-9.]+)", recipe).group(1))
    assert fixed_nsr == 0.05
    for row in summaries:
        required = [
            "calibrated_common_nsr",
            "raw_mean_edge_width_px",
            "deconvolved_mean_edge_width_px",
            "edge_width_change_percent",
            "deconvolved_max_ringing_ratio",
            "deconvolved_inverted_centers",
            "mae_change_percent",
        ]
        values = [float(row[name]) for name in required]
        assert all(math.isfinite(value) for value in values)
        assert math.isclose(float(row["calibrated_common_nsr"]), fixed_nsr, abs_tol=1e-12)
        assert float(row["edge_width_change_percent"]) < 0
        # Integrity checks must retain an adverse result rather than require a
        # scientific win. This frozen 50x result is sharper but worse in CD.
        pillars = [p for p in per_pillar if p["magnification"] == row["magnification"]]
        assert len(pillars) == 9
        raw_errors = np.array([abs(float(p["raw_cd_nm"]) - float(p["sem_cd_nm"])) for p in pillars])
        restored_errors = np.array([abs(float(p["deconvolved_cd_nm"]) - float(p["sem_cd_nm"])) for p in pillars])
        np.testing.assert_allclose(raw_errors, [float(p["raw_abs_error_nm"]) for p in pillars], atol=1e-10, rtol=0)
        np.testing.assert_allclose(restored_errors, [float(p["deconvolved_abs_error_nm"]) for p in pillars], atol=1e-10, rtol=0)
        assert math.isclose(float(row["raw_mae_nm"]), float(raw_errors.mean()), abs_tol=1e-10)
        assert math.isclose(float(row["deconvolved_mae_nm"]), float(restored_errors.mean()), abs_tol=1e-10)
        assert int(float(row["pillars_improved"])) == int(np.count_nonzero(restored_errors < raw_errors))
        expected_change = 100 * (restored_errors.mean() / raw_errors.mean() - 1)
        assert math.isclose(float(row["mae_change_percent"]), float(expected_change), abs_tol=1e-10)
        assert int(float(row["deconvolved_inverted_centers"])) == 0

    expected_png = [
        "09_fitted_psf_wiener_deconvolution_pillar_3x3.png",
        "10_cd_measurement_overlay_captured.png",
        "11_cd_measurement_overlay_deconvolved.png",
        "12_cd_before_after_vs_sem.png",
        "13_cd_error_before_after.png",
        "14_edge_width_before_after.png",
    ]
    expected_bmp = ["09_fitted_psf_wiener_deconvolution_pillar_3x3.bmp"]
    for magnification in ("20x", "50x"):
        for name in expected_png + expected_bmp:
            path = FIGURE_ROOT / magnification / name
            assert path.is_file() and path.stat().st_size > 0
            with Image.open(path) as image:
                image.verify()


def test_captured_and_deconvolved_overlays_use_one_shared_grayscale() -> None:
    with (SOURCE_ROOT / "analysis_manifest.json").open(encoding="utf-8") as handle:
        manifest = json.load(handle)

    assert manifest["overlay_display_rule"] == (
        "captured and deconvolved overlays share the combined 0.5-99.5 percentile "
        "grayscale range within each magnification; display only"
    )


def test_spectra_use_absolute_dbfs_without_per_image_normalization() -> None:
    with (SPECTRUM_ROOT / "spectrum_manifest.json").open(encoding="utf-8") as handle:
        manifest = json.load(handle)

    assert manifest["quantity"] == (
        "absolute two-dimensional FFT amplitude for supplied image and "
        "floating-point sources"
    )
    assert manifest["normalization"] == (
        "20*log10(abs(fftshift(fft2(image/255)))/pixel_count); "
        "0 dBFS is a full-scale constant image"
    )
    assert manifest["wiener_source_normalization"] == (
        "20*log10(abs(fftshift(fft2(restored)))/pixel_count); "
        "0 dBFS is a constant floating-point image with value 1.0"
    )
    assert manifest["wiener_array"] == "restored"
    assert manifest["wiener_full_scale_reference"] == 1.0
    assert manifest["per_image_peak_normalization"] is False
    assert manifest["window"] == "none"
    assert manifest["mean_subtraction"] is False
    assert manifest["display_limits_dbfs"] == [-80.0, 0.0]
    assert manifest["shared_display_scale"] == "all six spectra"

    for magnification in ("20x", "50x"):
        figure_dir = FIGURE_ROOT / magnification
        wiener_path = WIENER_ROOT / f"{magnification}_wiener_deconvolution.mat"
        result = loadmat(wiener_path)
        restored = np.asarray(result["restored"], dtype=float)
        assert float(np.asarray(result["nsr"]).squeeze()) == 0.05
        assert "background" in result and "restored_contrast" in result
        assert restored.ndim == 2
        assert np.isfinite(restored).all()

        with np.load(SPECTRUM_ROOT / f"{magnification}_absolute_spectra.npz") as data:
            for source_name, prefix in (
                ("05_original_pillar_3x3.bmp", "captured"),
                ("06_v42_e120_reconstruction_pillar_3x3.bmp", "v42"),
            ):
                image = np.asarray(Image.open(figure_dir / source_name).convert("L"), dtype=float)
                amplitude = np.abs(np.fft.fftshift(np.fft.fft2(image / 255.0))) / image.size
                dbfs = 20.0 * np.log10(np.maximum(amplitude, np.finfo(float).tiny))
                np.testing.assert_allclose(
                    data[f"{prefix}_amplitude"], amplitude, rtol=0, atol=1e-12
                )
                np.testing.assert_allclose(
                    data[f"{prefix}_dbfs"], dbfs, rtol=0, atol=1e-12
                )

            deconvolved_amplitude = (
                np.abs(np.fft.fftshift(np.fft.fft2(restored))) / restored.size
            )
            deconvolved_dbfs = 20.0 * np.log10(
                np.maximum(deconvolved_amplitude, np.finfo(float).tiny)
            )
            np.testing.assert_allclose(
                data["deconvolved_amplitude"],
                deconvolved_amplitude,
                rtol=0,
                atol=1e-12,
            )
            np.testing.assert_allclose(
                data["deconvolved_dbfs"], deconvolved_dbfs, rtol=0, atol=1e-12
            )
            for key in (
                "captured_amplitude",
                "captured_dbfs",
                "v42_amplitude",
                "v42_dbfs",
                "deconvolved_amplitude",
                "deconvolved_dbfs",
            ):
                assert np.isfinite(data[key]).all()
                assert data[key].shape == restored.shape
            assert data["fx_cycles_per_pixel"].shape == (restored.shape[1],)
            assert data["fy_cycles_per_pixel"].shape == (restored.shape[0],)
            assert np.isfinite(data["fx_cycles_per_pixel"]).all()
            assert np.isfinite(data["fy_cycles_per_pixel"]).all()

        record = manifest["records"][magnification]
        assert str(PROJECT_ROOT / record["wiener_source"]) == str(wiener_path)
        assert record["wiener_array"] == "restored"
        assert record["wiener_nsr"] == 0.05

        for name in (
            "07_original_pillar_3x3_spectrum.png",
            "08_v42_e120_reconstruction_pillar_3x3_spectrum.png",
            "09_fitted_psf_wiener_deconvolution_pillar_3x3_spectrum.png",
        ):
            with Image.open(figure_dir / name) as image:
                assert image.mode == "RGB"
                assert image.width > 1000 and image.height > 1000
                image.verify()
