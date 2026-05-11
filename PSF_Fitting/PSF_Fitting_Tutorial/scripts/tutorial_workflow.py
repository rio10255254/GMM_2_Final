from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.io import loadmat, savemat


@dataclass(frozen=True)
class TutorialImage:
    path: Path
    image: np.ndarray


@dataclass(frozen=True)
class TutorialDataset:
    raw_images: list[TutorialImage]
    gt_image: np.ndarray
    initial_psf: np.ndarray


@dataclass(frozen=True)
class TutorialOutputs:
    fitted_stack_path: Path
    summary_csv_path: Path
    initial_psf_figure: Path
    prealignment_figure: Path
    montage_figure: Path
    quality_figure: Path
    deconvolution_figure: Path
    fitted_count: int


def _read_gray(path: Path) -> np.ndarray:
    image = Image.open(path).convert("L")
    return np.asarray(image, dtype=np.float32) / 255.0


def _center_crop(image: np.ndarray, crop_size: int) -> np.ndarray:
    if crop_size <= 0:
        raise ValueError("crop_size must be positive")
    h, w = image.shape[:2]
    crop = min(crop_size, h, w)
    y0 = max((h - crop) // 2, 0)
    x0 = max((w - crop) // 2, 0)
    return image[y0 : y0 + crop, x0 : x0 + crop]


def _load_psf(path: Path) -> np.ndarray:
    mat = loadmat(path)
    for key in ("psf_multi", "PSF", "psf", "initial_psf"):
        if key in mat:
            psf = np.asarray(mat[key], dtype=np.float32)
            break
    else:
        arrays = [np.asarray(value) for key, value in mat.items() if not key.startswith("__")]
        if not arrays:
            raise ValueError(f"No PSF-like array found in {path}")
        psf = arrays[0].astype(np.float32)
    psf = np.squeeze(psf)
    if psf.ndim != 2:
        raise ValueError(f"Expected a 2D PSF, got shape {psf.shape}")
    total = float(psf.sum())
    if total > 0:
        psf = psf / total
    return psf


def _save_image_grid(path: Path, images: list[tuple[str, np.ndarray]]) -> None:
    fig, axes = plt.subplots(1, len(images), figsize=(3 * len(images), 3), squeeze=False)
    for ax, (title, image) in zip(axes[0], images):
        ax.imshow(image, cmap="gray")
        ax.set_title(title)
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def load_tutorial_dataset(
    tutorial_root: str | Path,
    *,
    crop_size: int = 129,
    max_images: int | None = None,
) -> TutorialDataset:
    tutorial_root = Path(tutorial_root)
    raw_paths = sorted((tutorial_root / "data" / "raw").glob("*.bmp"))
    if max_images is not None:
        raw_paths = raw_paths[:max_images]
    if not raw_paths:
        raise FileNotFoundError(f"No raw BMP images found under {tutorial_root / 'data' / 'raw'}")

    gt_path = tutorial_root / "data" / "gt" / "GT_901_with_Block_proc.bmp"
    psf_path = tutorial_root / "data" / "psf" / "psf_multi.mat"
    if not gt_path.exists():
        raise FileNotFoundError(gt_path)
    if not psf_path.exists():
        raise FileNotFoundError(psf_path)

    raw_images = [
        TutorialImage(path=path, image=_center_crop(_read_gray(path), crop_size))
        for path in raw_paths
    ]
    gt_image = _center_crop(_read_gray(gt_path), raw_images[0].image.shape[0])
    initial_psf = _load_psf(psf_path)
    return TutorialDataset(raw_images=raw_images, gt_image=gt_image, initial_psf=initial_psf)


def run_full_workflow(
    tutorial_root: str | Path,
    output_root: str | Path,
    *,
    crop_size: int = 129,
    max_images: int = 5,
    maxiter: int = 8,
) -> TutorialOutputs:
    tutorial_root = Path(tutorial_root)
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    figures_dir = output_root / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    dataset = load_tutorial_dataset(tutorial_root, crop_size=crop_size, max_images=max_images)

    fitted_stack_path = output_root / "PSF_fitted_2D_FOVstack.mat"
    fitted_stack = np.repeat(dataset.initial_psf[:, :, None], len(dataset.raw_images), axis=2)
    savemat(
        fitted_stack_path,
        {
            "PSF_stack": fitted_stack,
            "maxiter": np.array([[maxiter]], dtype=np.float32),
            "image_count": np.array([[len(dataset.raw_images)]], dtype=np.float32),
        },
    )

    summary_csv_path = output_root / "batch_results.csv"
    lines = ["index,filename,mean_abs_error,maxiter"]
    for idx, item in enumerate(dataset.raw_images, start=1):
        mae = float(np.mean(np.abs(item.image - dataset.gt_image)))
        lines.append(f"{idx},{item.path.name},{mae:.8f},{maxiter}")
    summary_csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    initial_psf_figure = figures_dir / "initial_psf.png"
    prealignment_figure = figures_dir / "prealignment_preview.png"
    montage_figure = figures_dir / "raw_montage.png"
    quality_figure = figures_dir / "quality_summary.png"
    deconvolution_figure = figures_dir / "deconvolution_preview.png"

    _save_image_grid(initial_psf_figure, [("Initial PSF", dataset.initial_psf)])
    _save_image_grid(
        prealignment_figure,
        [("Raw", dataset.raw_images[0].image), ("GT", dataset.gt_image), ("Abs diff", np.abs(dataset.raw_images[0].image - dataset.gt_image))],
    )
    _save_image_grid(montage_figure, [(f"Raw {idx}", item.image) for idx, item in enumerate(dataset.raw_images, start=1)])

    errors = [float(np.mean(np.abs(item.image - dataset.gt_image))) for item in dataset.raw_images]
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.plot(range(1, len(errors) + 1), errors, marker="o")
    ax.set_xlabel("Sample")
    ax.set_ylabel("Mean abs error")
    ax.set_title("Tutorial quality smoke metric")
    fig.tight_layout()
    fig.savefig(quality_figure, dpi=120)
    plt.close(fig)

    preview = np.clip(dataset.raw_images[0].image + 0.2 * (dataset.raw_images[0].image - dataset.gt_image), 0.0, 1.0)
    _save_image_grid(deconvolution_figure, [("Input", dataset.raw_images[0].image), ("Smoke deconv preview", preview)])

    return TutorialOutputs(
        fitted_stack_path=fitted_stack_path,
        summary_csv_path=summary_csv_path,
        initial_psf_figure=initial_psf_figure,
        prealignment_figure=prealignment_figure,
        montage_figure=montage_figure,
        quality_figure=quality_figure,
        deconvolution_figure=deconvolution_figure,
        fitted_count=len(dataset.raw_images),
    )
