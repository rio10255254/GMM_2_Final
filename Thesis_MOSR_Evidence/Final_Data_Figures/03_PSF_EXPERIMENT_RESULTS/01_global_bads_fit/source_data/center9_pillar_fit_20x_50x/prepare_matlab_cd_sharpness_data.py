from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import loadmat, savemat
from scipy.ndimage import gaussian_filter1d, map_coordinates


ROOT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit"
)
SOURCE_ROOT = ROOT / "source_data" / "center9_pillar_fit_20x_50x"
DECONV_ROOT = SOURCE_ROOT / "psf_deconvolution_cd"
FIT_ROOT = Path(r"D:\GMM_2_Final\PSF_Fitting\output\deconvolution_baseline_psf_20260715")
OUT_DIR = SOURCE_ROOT / "sharpness_validation"

sys.path.insert(0, str(DECONV_ROOT))
from analyze_cd import CONFIGS, crossing_radius, measure_cd  # noqa: E402


def sample_profiles(
    image: np.ndarray,
    centers: np.ndarray,
    pitch_px: float,
    pixel_um: float,
) -> dict[str, np.ndarray]:
    radial_step = 0.05
    radii = np.arange(0.0, 0.38 * pitch_px + radial_step, radial_step)
    angles = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False)
    # Every trace contains this signed-distance range; keeping only the common
    # support avoids artificial gaps at the ends of the plotted median.
    common_distance_um = np.arange(-1.0, 0.5501, 0.005)

    aligned_profiles: list[np.ndarray] = []
    edge_widths: list[float] = []
    r10_all: list[np.ndarray] = []
    r50_all: list[np.ndarray] = []
    r90_all: list[np.ndarray] = []
    median_profiles: list[np.ndarray] = []

    cos_a = np.cos(angles)[:, None]
    sin_a = np.sin(angles)[:, None]
    for center in centers:
        x = center[0] + cos_a * radii[None, :]
        y = center[1] + sin_a * radii[None, :]
        samples = map_coordinates(image, [y, x], order=3, mode="reflect")

        core_mask = radii <= 0.07 * pitch_px
        background_mask = (radii >= 0.30 * pitch_px) & (radii <= 0.36 * pitch_px)
        core_level = float(np.median(samples[:, core_mask]))
        background_level = float(np.median(samples[:, background_mask]))
        contrast = max(background_level - core_level, np.finfo(float).eps)
        smoothed = gaussian_filter1d(samples, sigma=6.0, axis=1, mode="nearest")
        normalized = (smoothed - core_level) / contrast

        r10 = np.asarray(
            [crossing_radius(profile, radii, core_level + 0.10 * contrast) for profile in samples]
        )
        measurement = measure_cd(image, center, pitch_px, contrast_fraction=0.5)
        r50 = measurement.radii_px.copy()
        r90 = np.asarray(
            [crossing_radius(profile, radii, core_level + 0.90 * contrast) for profile in samples]
        )

        for profile, boundary in zip(normalized, r50):
            signed_distance_um = (radii - boundary) * pixel_um
            aligned_profiles.append(
                np.interp(
                    common_distance_um,
                    signed_distance_um,
                    profile,
                    left=np.nan,
                    right=np.nan,
                )
            )

        edge_widths.append(measurement.edge_width_px)
        r10_all.append(r10)
        r50_all.append(r50)
        r90_all.append(r90)
        median_profiles.append(np.median(normalized, axis=0))

    return {
        "distance_um": common_distance_um,
        "aligned_median": np.nanmedian(np.vstack(aligned_profiles), axis=0),
        "edge_width_px": np.asarray(edge_widths),
        "radii_px": radii,
        "angles_rad": angles,
        "r10_px": np.vstack(r10_all),
        "r50_px": np.vstack(r50_all),
        "r90_px": np.vstack(r90_all),
        "median_profile": np.vstack(median_profiles),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload: dict[str, np.ndarray | float] = {}

    for label, cfg in CONFIGS.items():
        result = loadmat(DECONV_ROOT / f"{label}_wiener_deconvolution.mat")
        with (FIT_ROOT / label / "selected_frame.json").open(encoding="utf-8") as handle:
            meta = json.load(handle)

        centers = np.asarray(result["centers_xy"], dtype=float)
        pitch_px = float(meta["pitch_px"])
        pixel_um = float(meta["object_pixel_um"])
        raw = np.asarray(result["I"], dtype=float)
        deconvolved = np.asarray(result["restored"], dtype=float)

        raw_profiles = sample_profiles(raw, centers, pitch_px, pixel_um)
        deconvolved_profiles = sample_profiles(deconvolved, centers, pitch_px, pixel_um)
        prefix = f"m{label}_"

        payload[prefix + "raw_image"] = raw
        payload[prefix + "centers_xy"] = centers
        payload[prefix + "pitch_px"] = pitch_px
        payload[prefix + "pixel_um"] = pixel_um
        for name, value in raw_profiles.items():
            payload[prefix + "raw_" + name] = value
        for name, value in deconvolved_profiles.items():
            payload[prefix + "deconvolved_" + name] = value

    output_path = OUT_DIR / "matlab_cd_sharpness_plot_data.mat"
    savemat(output_path, payload, do_compression=True)
    print(f"Wrote exact CD/sharpness plot data: {output_path}")


if __name__ == "__main__":
    main()
