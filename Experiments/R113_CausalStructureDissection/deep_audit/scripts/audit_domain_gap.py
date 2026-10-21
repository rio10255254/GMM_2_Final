"""Compare synthetic targets/degradations with held-out real microscopy textures."""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import entropy
from sklearn.neighbors import NearestNeighbors


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
R109 = Path(CONFIG["sources"]["r109_root"])
OUTPUT = ROOT / "results" / "domain_gap"
OUTPUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(R109 / "training"))
from r109_dataset import R109Dataset


REAL = {
    "real_5x": [Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\5x_dense_raw.bmp")],
    "real_20x": [Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\20x_mixed_raw.bmp")],
    "real_50x": [
        Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\50x_array_raw.bmp"),
        Path(r"D:\GMM_2_Final\Experiments\R100_CausalOperatorScratch\data\live_validation\pillar_center9_50x_raw.bmp"),
    ],
    "sem_optical": sorted(Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\inputs\sem_paired_50x_exposure_stack").glob("*.bmp")),
    "junhua_ring": [Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\External_GMF_Packages\Pitch1um_Y_100_Raw_Even_R109E48\pitch1um_y100_raw\bmp\frame_0050.bmp")],
}
METRICS = [
    "mean", "std", "gradient_rms", "highpass_rms", "edge_density", "local_contrast",
    "spectral_high_fraction", "spectral_centroid", "spectral_slope", "orientation_anisotropy", "entropy_bits",
]


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read {path}")
    return image.astype(np.float32) / 255.0


def patches(image: np.ndarray, size: int = 256, stride: int = 128, limit: int = 64) -> list[np.ndarray]:
    if min(image.shape) < size:
        return [cv2.resize(image, (size, size), interpolation=cv2.INTER_CUBIC)]
    rows = []
    for top in range(0, image.shape[0] - size + 1, stride):
        for left in range(0, image.shape[1] - size + 1, stride):
            patch = image[top : top + size, left : left + size]
            score = float(cv2.Laplacian(patch, cv2.CV_32F).var())
            rows.append((score, patch.copy()))
    rows.sort(key=lambda value: value[0], reverse=True)
    return [value[1] for value in rows[:limit]]


def patch_metrics(image: np.ndarray) -> dict[str, float]:
    image = image.astype(np.float32)
    gx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    magnitude = np.sqrt(gx * gx + gy * gy + 1e-12)
    high = image - cv2.GaussianBlur(image, (0, 0), 1.5)
    local_mean = cv2.GaussianBlur(image, (0, 0), 8.0)
    centered = image - float(image.mean())
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(centered))) ** 2
    yy, xx = np.indices(image.shape)
    cy, cx = (np.asarray(image.shape) - 1) / 2
    radius = np.sqrt(((yy - cy) / image.shape[0]) ** 2 + ((xx - cx) / image.shape[1]) ** 2)
    total_power = float(spectrum.sum())
    high_fraction = float(spectrum[radius > .25].sum() / max(total_power, 1e-12))
    centroid = float((spectrum * radius).sum() / max(total_power, 1e-12))
    radial_bins = np.linspace(.02, .48, 32)
    radial_power, radial_center = [], []
    for low, upper in zip(radial_bins[:-1], radial_bins[1:]):
        values = spectrum[(radius >= low) & (radius < upper)]
        if len(values) and float(values.mean()) > 0:
            radial_power.append(float(values.mean()))
            radial_center.append(.5 * (low + upper))
    slope = float(np.polyfit(np.log(radial_center), np.log(radial_power), 1)[0]) if len(radial_power) >= 3 else 0.0
    structure = np.asarray([[float((gx * gx).mean()), float((gx * gy).mean())], [float((gx * gy).mean()), float((gy * gy).mean())]])
    eigenvalues = np.linalg.eigvalsh(structure)
    anisotropy = float((eigenvalues[-1] - eigenvalues[0]) / max(float(eigenvalues.sum()), 1e-12))
    histogram, _ = np.histogram(image, bins=64, range=(0, 1), density=False)
    return {
        "mean": float(image.mean()),
        "std": float(image.std()),
        "gradient_rms": float(np.sqrt(np.mean(gx * gx + gy * gy))),
        "highpass_rms": float(np.sqrt(np.mean(high * high))),
        "edge_density": float(np.mean(magnitude > 5 / 255)),
        "local_contrast": float(np.sqrt(np.mean((image - local_mean) ** 2))),
        "spectral_high_fraction": high_fraction,
        "spectral_centroid": centroid,
        "spectral_slope": slope,
        "orientation_anisotropy": anisotropy,
        "entropy_bits": float(entropy(histogram + 1e-12, base=2)),
    }


def synthetic_rows() -> tuple[list[dict[str, object]], dict[str, list[np.ndarray]]]:
    rows = []
    images: dict[str, list[np.ndarray]] = {"synthetic_target": [], "synthetic_standard": [], "synthetic_mixed_hard": []}
    datasets = {epoch: R109Dataset("validation", epoch=epoch) for epoch in range(6)}
    indices = list(range(len(datasets[0])))
    for index in indices:
        base = datasets[0][index]
        target = base["target"][0, 0].numpy()
        images["synthetic_target"].append(target)
        rows.append({"domain": "synthetic_target", "source": f"scene_{int(base['scene_index'])}", **patch_metrics(target)})
        found = {}
        for epoch in range(6):
            item = datasets[epoch][index]
            challenge = str(item["challenge"])
            if challenge in {"standard", "mixed_hard"} and challenge not in found:
                found[challenge] = item["source"][0, 0].numpy()
        for challenge, domain in (("standard", "synthetic_standard"), ("mixed_hard", "synthetic_mixed_hard")):
            if challenge in found:
                image = found[challenge]
                images[domain].append(image)
                rows.append({"domain": domain, "source": f"scene_{int(base['scene_index'])}", **patch_metrics(image)})
    return rows, images


def real_rows() -> tuple[list[dict[str, object]], dict[str, list[np.ndarray]]]:
    rows, images = [], {}
    for domain, paths in REAL.items():
        images[domain] = []
        for path in paths:
            for index, patch in enumerate(patches(read_gray(path))):
                images[domain].append(patch)
                rows.append({"domain": domain, "source": f"{path.name}:{index}", **patch_metrics(patch)})
    return rows, images


def distance_analysis(frame: pd.DataFrame) -> dict[str, object]:
    synthetic = frame.loc[frame.domain.isin(["synthetic_standard", "synthetic_mixed_hard"]), METRICS].to_numpy(float)
    mean = synthetic.mean(0)
    std = synthetic.std(0) + 1e-9
    standardized = (synthetic - mean) / std
    model = NearestNeighbors(n_neighbors=2).fit(standardized)
    self_distances = model.kneighbors(standardized)[0][:, 1]
    baseline = float(np.median(self_distances))
    result = {}
    for domain in sorted(set(frame.domain) - {"synthetic_target", "synthetic_standard", "synthetic_mixed_hard"}):
        values = (frame.loc[frame.domain.eq(domain), METRICS].to_numpy(float) - mean) / std
        distances = model.kneighbors(values, n_neighbors=1)[0][:, 0]
        outside = {}
        for metric in METRICS:
            low, high = frame.loc[frame.domain.isin(["synthetic_standard", "synthetic_mixed_hard"]), metric].quantile([.01, .99])
            real = frame.loc[frame.domain.eq(domain), metric]
            outside[metric] = float(np.mean((real < low) | (real > high)))
        result[domain] = {
            "patches": len(values),
            "nearest_synthetic_distance_median": float(np.median(distances)),
            "distance_over_synthetic_self_median": float(np.median(distances) / max(baseline, 1e-9)),
            "outside_synthetic_1_to_99pct_fraction_by_metric": outside,
        }
    return {"synthetic_self_neighbor_median": baseline, "real_domains": result}


def save_panel(images: dict[str, list[np.ndarray]]) -> None:
    domains = ["synthetic_target", "synthetic_standard", "synthetic_mixed_hard", "real_5x", "real_20x", "real_50x", "sem_optical", "junhua_ring"]
    figure, axes = plt.subplots(len(domains), 6, figsize=(12, 2 * len(domains)))
    for row, domain in enumerate(domains):
        values = images.get(domain, [])
        if not values:
            continue
        indices = np.linspace(0, len(values) - 1, 6).round().astype(int)
        for column, index in enumerate(indices):
            axes[row, column].imshow(values[index], cmap="gray", vmin=0, vmax=1)
            axes[row, column].set_title(domain if column == 0 else "", fontsize=8)
            axes[row, column].axis("off")
    figure.tight_layout()
    figure.savefig(OUTPUT / "domain_patch_panel.png", dpi=150)
    plt.close(figure)


def main() -> int:
    synthetic, synthetic_images = synthetic_rows()
    real, real_images = real_rows()
    frame = pd.DataFrame([*synthetic, *real])
    frame.to_csv(OUTPUT / "per_patch_metrics.csv", index=False, encoding="utf-8-sig")
    summary = frame.groupby("domain", as_index=False)[METRICS].median()
    summary.to_csv(OUTPUT / "domain_metric_medians.csv", index=False, encoding="utf-8-sig")
    distances = distance_analysis(frame)
    save_panel({**synthetic_images, **real_images})
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "patch_counts": frame.domain.value_counts().to_dict(),
        "domain_medians": summary.to_dict(orient="records"),
        "distance_analysis": distances,
        "interpretation_boundary": "Real patches were selected from a small set of held-out captures and are a domain-gap diagnostic, not a population estimate of every microscope scene.",
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
