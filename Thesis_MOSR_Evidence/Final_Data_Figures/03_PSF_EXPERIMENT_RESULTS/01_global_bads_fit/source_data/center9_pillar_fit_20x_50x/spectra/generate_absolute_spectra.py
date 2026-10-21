from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.io import loadmat


PACKAGE_ROOT = Path(
    r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures"
    r"\03_PSF_EXPERIMENT_RESULTS\01_global_bads_fit"
)
FIGURE_ROOT = PACKAGE_ROOT / "figures" / "center9_pillar_fit_20x_50x"
SOURCE_ROOT = Path(__file__).resolve().parent
WIENER_ROOT = SOURCE_ROOT.parent / "psf_deconvolution_cd"
DISPLAY_LIMITS_DBFS = (-80.0, 0.0)
IMAGE_SUBTITLE = (
    "Absolute FFT amplitude; shared -80 to 0 dBFS scale; "
    "no window, mean subtraction, or peak normalization"
)
WIENER_SUBTITLE = (
    "Absolute FFT amplitude from unclipped background-normalized Wiener result; "
    "NSR=0.05; shared -80 to 0 dBFS scale"
)


def absolute_fft_amplitude_array(
    image: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    image = np.asarray(image, dtype=float)
    if image.ndim != 2 or not np.isfinite(image).all():
        raise ValueError("Spectrum source must be a finite two-dimensional array")
    amplitude = np.abs(np.fft.fftshift(np.fft.fft2(image))) / image.size
    dbfs = 20.0 * np.log10(np.maximum(amplitude, np.finfo(float).tiny))
    return amplitude, dbfs


def absolute_fft_amplitude(image_path: Path) -> tuple[np.ndarray, np.ndarray]:
    image = np.asarray(Image.open(image_path).convert("L"), dtype=float) / 255.0
    return absolute_fft_amplitude_array(image)


def frequency_extent(shape: tuple[int, int]) -> tuple[float, float, float, float]:
    height, width = shape
    fx = np.fft.fftshift(np.fft.fftfreq(width))
    fy = np.fft.fftshift(np.fft.fftfreq(height))
    dx = 1.0 / width
    dy = 1.0 / height
    return (
        float(fx[0] - dx / 2.0),
        float(fx[-1] + dx / 2.0),
        float(fy[0] - dy / 2.0),
        float(fy[-1] + dy / 2.0),
    )


def save_spectrum(
    dbfs: np.ndarray,
    path: Path,
    title: str,
    subtitle: str,
) -> None:
    fig, ax = plt.subplots(figsize=(7.4, 6.6), dpi=240, facecolor="white")
    image = ax.imshow(
        dbfs,
        origin="lower",
        extent=frequency_extent(dbfs.shape),
        cmap="viridis",
        vmin=DISPLAY_LIMITS_DBFS[0],
        vmax=DISPLAY_LIMITS_DBFS[1],
        interpolation="nearest",
        aspect="equal",
    )
    ax.set_title(title, loc="left", fontsize=12, pad=23)
    ax.text(
        0.0,
        1.01,
        subtitle,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.5,
        color="#4B5563",
    )
    ax.set_xlabel("spatial frequency x (cycles/pixel)")
    ax.set_ylabel("spatial frequency y (cycles/pixel)")
    colorbar = fig.colorbar(image, ax=ax, fraction=0.047, pad=0.035)
    colorbar.set_label("FFT amplitude (dBFS)")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    with Image.open(path) as saved:
        rgb = saved.convert("RGB")
    rgb.save(path)


def main() -> None:
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    records: dict[str, dict[str, object]] = {}

    for magnification in ("20x", "50x"):
        figure_dir = FIGURE_ROOT / magnification
        captured_path = figure_dir / "05_original_pillar_3x3.bmp"
        v42_path = figure_dir / "06_v42_e120_reconstruction_pillar_3x3.bmp"
        wiener_path = WIENER_ROOT / f"{magnification}_wiener_deconvolution.mat"
        captured_amplitude, captured_dbfs = absolute_fft_amplitude(captured_path)
        v42_amplitude, v42_dbfs = absolute_fft_amplitude(v42_path)
        wiener_result = loadmat(wiener_path)
        if "restored" not in wiener_result or "nsr" not in wiener_result:
            raise RuntimeError(f"{wiener_path} is missing restored or nsr")
        wiener_nsr = float(np.asarray(wiener_result["nsr"]).squeeze())
        if not np.isclose(wiener_nsr, 0.05):
            raise RuntimeError(
                f"{magnification} Wiener source used NSR {wiener_nsr}, not 0.05"
            )
        restored = np.asarray(wiener_result["restored"], dtype=float)
        deconvolved_amplitude, deconvolved_dbfs = absolute_fft_amplitude_array(
            restored
        )

        height, width = captured_dbfs.shape
        if not (
            v42_dbfs.shape == captured_dbfs.shape == deconvolved_dbfs.shape
        ):
            raise RuntimeError(
                f"{magnification} captured, V42, and Wiener sources have different shapes"
            )
        fx = np.fft.fftshift(np.fft.fftfreq(width))
        fy = np.fft.fftshift(np.fft.fftfreq(height))
        np.savez_compressed(
            SOURCE_ROOT / f"{magnification}_absolute_spectra.npz",
            captured_amplitude=captured_amplitude,
            captured_dbfs=captured_dbfs,
            v42_amplitude=v42_amplitude,
            v42_dbfs=v42_dbfs,
            deconvolved_amplitude=deconvolved_amplitude,
            deconvolved_dbfs=deconvolved_dbfs,
            fx_cycles_per_pixel=fx,
            fy_cycles_per_pixel=fy,
        )

        save_spectrum(
            captured_dbfs,
            figure_dir / "07_original_pillar_3x3_spectrum.png",
            f"{magnification} captured pillar crop: spatial-frequency spectrum",
            IMAGE_SUBTITLE,
        )
        save_spectrum(
            v42_dbfs,
            figure_dir / "08_v42_e120_reconstruction_pillar_3x3_spectrum.png",
            f"{magnification} V42 reconstruction: spatial-frequency spectrum",
            IMAGE_SUBTITLE,
        )
        save_spectrum(
            deconvolved_dbfs,
            figure_dir
            / "09_fitted_psf_wiener_deconvolution_pillar_3x3_spectrum.png",
            f"{magnification} fitted-PSF Wiener deconvolution: spatial-frequency spectrum",
            WIENER_SUBTITLE,
        )

        records[magnification] = {
            "shape_yx": [height, width],
            "captured_source": str(captured_path),
            "v42_source": str(v42_path),
            "captured_dbfs_min": float(np.min(captured_dbfs)),
            "captured_dbfs_max": float(np.max(captured_dbfs)),
            "v42_dbfs_min": float(np.min(v42_dbfs)),
            "v42_dbfs_max": float(np.max(v42_dbfs)),
            "wiener_source": str(wiener_path),
            "wiener_array": "restored",
            "wiener_nsr": wiener_nsr,
            "wiener_full_scale_reference": 1.0,
            "deconvolved_dbfs_min": float(np.min(deconvolved_dbfs)),
            "deconvolved_dbfs_max": float(np.max(deconvolved_dbfs)),
            "numeric_output": str(SOURCE_ROOT / f"{magnification}_absolute_spectra.npz"),
        }

    manifest = {
        "quantity": (
            "absolute two-dimensional FFT amplitude for supplied image and "
            "floating-point sources"
        ),
        "normalization": (
            "20*log10(abs(fftshift(fft2(image/255)))/pixel_count); "
            "0 dBFS is a full-scale constant image"
        ),
        "wiener_source_normalization": (
            "20*log10(abs(fftshift(fft2(restored)))/pixel_count); "
            "0 dBFS is a constant floating-point image with value 1.0"
        ),
        "wiener_array": "restored",
        "wiener_full_scale_reference": 1.0,
        "per_image_peak_normalization": False,
        "window": "none",
        "mean_subtraction": False,
        "smoothing": "none",
        "display_limits_dbfs": list(DISPLAY_LIMITS_DBFS),
        "shared_display_scale": "all six spectra",
        "display_floor_note": (
            "values below -80 dBFS use the darkest display color; exact unclipped values are stored in NPZ"
        ),
        "records": records,
    }
    with (SOURCE_ROOT / "spectrum_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
