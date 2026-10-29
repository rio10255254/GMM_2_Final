"""Diagnose independent width/shift reliability targets without changing R114.

This is a read-only analysis of the frozen R74 source/target/mask pairs and the
R114 E020 internal maps.  It intentionally does not import or mutate the model
or training package.  The proposed targets are profile-based oracle labels that
can be generated only for synthetic pairs with known masks/SDFs.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage, stats
from sklearn.metrics import roc_auc_score
PROJECT_ROOT = Path(__file__).resolve().parents[6]


ROOT = Path(str(PROJECT_ROOT / 'Experiments/R114_ConfidenceGatedRecoverableScratch'))
R74_ROOT = Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization'))
R74_MANIFEST = R74_ROOT / "data" / "r74_hard_acm_val" / "manifest.json"
INTERNAL_ROOT = ROOT / "results" / "geometry_probe" / "E020" / "R74_contract" / "internal_maps"
OUTPUT = ROOT / "results" / "geometry_probe" / "E020" / "gate_design_diagnosis"

OFFSETS = np.arange(-12.0, 12.01, 1.0, dtype=np.float32)
MID_OFFSETS = 0.5 * (OFFSETS[:-1] + OFFSETS[1:])
MAX_POINTS_PER_SAMPLE = 1200
FAMILIES = (
    "asymmetric_blur_halo",
    "boundary_fade",
    "low_contrast",
    "mixed_hard",
    "uneven_illumination",
)


def read_gray(path: str | Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image.astype(np.float32) / 255.0


def sigmoid(value: np.ndarray | float) -> np.ndarray:
    value = np.asarray(value, dtype=np.float64)
    return 1.0 / (1.0 + np.exp(-np.clip(value, -40.0, 40.0)))


def signed_distance_and_normals(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    foreground = (mask > 0.5).astype(np.uint8)
    inside = cv2.distanceTransform(foreground, cv2.DIST_L2, 5)
    outside = cv2.distanceTransform(1 - foreground, cv2.DIST_L2, 5)
    sdf = inside - outside
    gx = cv2.Sobel(sdf, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(sdf, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    length = np.sqrt(gx * gx + gy * gy + 1.0e-8)
    return sdf, gx / length, gy / length


def deterministic_boundary_points(sdf: np.ndarray, maximum: int) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.nonzero(np.abs(sdf) <= 1.05)
    if len(xs) <= maximum:
        return ys.astype(np.int32), xs.astype(np.int32)
    indices = np.linspace(0, len(xs) - 1, maximum, dtype=np.int64)
    return ys[indices].astype(np.int32), xs[indices].astype(np.int32)


def sample_profiles(image: np.ndarray, xs: np.ndarray, ys: np.ndarray,
                    nx: np.ndarray, ny: np.ndarray) -> np.ndarray:
    profiles = []
    base_x = xs.astype(np.float32)
    base_y = ys.astype(np.float32)
    for offset in OFFSETS:
        map_x = (base_x + offset * nx).reshape(-1, 1)
        map_y = (base_y + offset * ny).reshape(-1, 1)
        values = cv2.remap(
            image,
            map_x,
            map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        profiles.append(values[:, 0])
    return np.stack(profiles, axis=1).astype(np.float64)


def profile_noise(profile: np.ndarray) -> np.ndarray:
    plateaus = np.concatenate([profile[:, :4], profile[:, -4:]], axis=1)
    left = profile[:, :4] - np.median(profile[:, :4], axis=1, keepdims=True)
    right = profile[:, -4:] - np.median(profile[:, -4:], axis=1, keepdims=True)
    residual = np.concatenate([left, right], axis=1)
    mad = 1.4826 * np.median(np.abs(residual), axis=1)
    # The quantization floor prevents a perfectly flat synthetic plateau from
    # claiming infinite localization precision.
    return np.maximum(mad, 1.5 / 255.0) + 0.05 * np.std(plateaus, axis=1)


def normalize_profiles(source: np.ndarray, target: np.ndarray) -> dict[str, np.ndarray]:
    source_left = np.median(source[:, :4], axis=1)
    source_right = np.median(source[:, -4:], axis=1)
    target_left = np.median(target[:, :4], axis=1)
    target_right = np.median(target[:, -4:], axis=1)
    source_delta = source_right - source_left
    target_delta = target_right - target_left
    target_sign = np.where(target_delta >= 0.0, 1.0, -1.0)
    polarity = (source_delta * target_delta > 0.0).astype(np.float64)

    target_norm = (target - target_left[:, None]) / (target_delta[:, None] + target_sign[:, None] * 1.0e-6)
    source_sign = np.where(source_delta >= 0.0, 1.0, -1.0)
    source_norm = (source - source_left[:, None]) / (source_delta[:, None] + source_sign[:, None] * 1.0e-6)
    # Division by each signed plateau difference already maps both bright and
    # dark edges from 0 on the first side to 1 on the second side.  Do not
    # reverse dark profiles a second time.
    source_norm = np.clip(source_norm, -1.0, 2.0)
    target_norm = np.clip(target_norm, -1.0, 2.0)

    source_noise = profile_noise(source)
    target_noise = profile_noise(target)
    source_snr = np.abs(source_delta) / (2.0 * source_noise + 1.0 / 255.0)
    target_snr = np.abs(target_delta) / (2.0 * target_noise + 1.0 / 255.0)
    return {
        "source": source_norm,
        "target": target_norm,
        "source_contrast": np.abs(source_delta),
        "target_contrast": np.abs(target_delta),
        "source_snr": source_snr,
        "target_snr": target_snr,
        "polarity": polarity,
    }


def edge_moments(profile: np.ndarray, sigma: float) -> dict[str, np.ndarray]:
    smooth = ndimage.gaussian_filter1d(profile, sigma=sigma, axis=1, mode="nearest")
    derivative = np.diff(smooth, axis=1)
    positive = np.maximum(derivative, 0.0)
    negative = np.maximum(-derivative, 0.0)
    positive_mass = positive.sum(axis=1)
    total_variation = (positive + negative).sum(axis=1)
    mass = np.maximum(positive_mass, 1.0e-8)
    location = (positive * MID_OFFSETS[None, :]).sum(axis=1) / mass
    variance = (positive * (MID_OFFSETS[None, :] - location[:, None]) ** 2).sum(axis=1) / mass
    width_10_90 = 2.563103 * np.sqrt(np.maximum(variance, 1.0e-4))
    monotonicity = positive_mass / np.maximum(total_variation, 1.0e-8)
    radius = np.maximum(2.0, 0.75 * width_10_90)
    central = np.abs(MID_OFFSETS[None, :] - location[:, None]) <= radius[:, None]
    concentration = (positive * central).sum(axis=1) / mass
    return {
        "location": location,
        "width": width_10_90,
        "monotonicity": np.clip(monotonicity, 0.0, 1.0),
        "concentration": np.clip(concentration, 0.0, 1.0),
        "positive_mass": positive_mass,
    }


def derive_reliability_targets(source_profile: np.ndarray, target_profile: np.ndarray) -> dict[str, np.ndarray]:
    normalized = normalize_profiles(source_profile, target_profile)
    src_a = edge_moments(normalized["source"], 0.85)
    src_b = edge_moments(normalized["source"], 1.45)
    tgt_a = edge_moments(normalized["target"], 0.85)
    tgt_b = edge_moments(normalized["target"], 1.45)

    polarity = normalized["polarity"]
    source_snr = normalized["source_snr"]
    target_snr = normalized["target_snr"]
    snr_score = sigmoid((source_snr - 2.6) / 1.15)
    target_score = sigmoid((target_snr - 4.0) / 1.5)
    monotonicity_score = np.clip((src_a["monotonicity"] - 0.50) / 0.42, 0.0, 1.0)
    target_monotonicity = np.clip((tgt_a["monotonicity"] - 0.55) / 0.38, 0.0, 1.0)
    width_stability = np.exp(-np.abs(np.log((src_a["width"] + 0.25) / (src_b["width"] + 0.25))) / 0.42)
    width_ratio_stability = np.exp(
        -np.abs(
            np.log(
                ((src_a["width"] / np.maximum(tgt_a["width"], 0.25)) + 0.1)
                / ((src_b["width"] / np.maximum(tgt_b["width"], 0.25)) + 0.1)
            )
        ) / 0.55
    )
    contrast_visibility = np.sqrt(
        np.clip(normalized["source_contrast"] / np.maximum(normalized["target_contrast"], 2.0 / 255.0), 0.0, 1.0)
    )

    width_reliability = polarity * np.sqrt(snr_score * target_score)
    width_reliability *= np.sqrt(monotonicity_score * target_monotonicity)
    width_reliability *= np.sqrt(width_stability * width_ratio_stability)
    width_reliability *= 0.35 + 0.65 * contrast_visibility
    width_reliability = np.clip(width_reliability, 0.0, 1.0)

    width_gain = np.clip(src_a["width"] / np.maximum(tgt_a["width"], 0.45), 1.0, 3.5)
    width_gain = 1.0 + width_reliability * (width_gain - 1.0)

    shift_a = src_a["location"] - tgt_a["location"]
    shift_b = src_b["location"] - tgt_b["location"]
    shift_stability = np.exp(-np.abs(shift_a - shift_b) / 0.40)
    representable = np.exp(-np.maximum(np.abs(shift_a) - 1.20, 0.0) / 0.22)
    localization_sigma = src_a["width"] / np.maximum(source_snr, 0.25)
    localization_score = 1.0 / (1.0 + (localization_sigma / 2.3) ** 2)
    unique_edge = np.sqrt(src_a["concentration"] * src_b["concentration"])
    shift_reliability = polarity * snr_score * monotonicity_score
    shift_reliability *= np.sqrt(target_score * target_monotonicity)
    shift_reliability *= shift_stability * representable * localization_score * unique_edge
    # The factors above describe two effective failure axes: visibility and
    # localization.  A square root is their geometric-mean calibration.  It
    # preserves ranking while avoiding a near-all-zero training target from a
    # long product of correlated confidence terms.
    shift_reliability = np.sqrt(np.clip(shift_reliability, 0.0, 1.0))
    shift_target = np.clip(shift_a, -1.5, 1.5)
    # An unidentifiable offset is not silently converted into a strong zero
    # label: reliability carries supervision/action strength separately.

    return {
        "width_reliability": width_reliability,
        "shift_reliability": shift_reliability,
        "width_gain_target": width_gain,
        "normal_shift_target": shift_target,
        "normal_shift_unclipped": shift_a,
        "source_snr": source_snr,
        "source_monotonicity": src_a["monotonicity"],
        "source_edge_width": src_a["width"],
        "shift_stability": shift_stability,
        "representable": representable,
        "localization_score": localization_score,
    }


def squeeze_map(path: Path) -> np.ndarray:
    value = np.load(path)
    return np.asarray(value).squeeze().astype(np.float64)


def quantile(value: np.ndarray, probability: float) -> float:
    return float(np.quantile(value, probability)) if value.size else float("nan")


def sample_row(record: dict, values: dict[str, np.ndarray], current: dict[str, np.ndarray]) -> dict:
    wr = values["width_reliability"]
    sr = values["shift_reliability"]
    shift = values["normal_shift_target"]
    gate = current["geometry_gate"]
    predicted_shift = current["normal_shift"]
    low_shift = sr < 0.15
    high_shift = sr >= 0.35
    return {
        "sample_id": record["image_id"].replace("/", "_"),
        "family": record["family"],
        "shape_family": record["shape_family"],
        "polarity": record["polarity"],
        "points": int(wr.size),
        "width_reliability_median": quantile(wr, 0.50),
        "width_reliability_p25": quantile(wr, 0.25),
        "width_safe_fraction": float(np.mean(wr >= 0.45)),
        "shift_reliability_median": quantile(sr, 0.50),
        "shift_reliability_p25": quantile(sr, 0.25),
        "shift_safe_fraction": float(np.mean(sr >= 0.35)),
        "shift_suppressed_fraction": float(np.mean(sr < 0.15)),
        "width_high_shift_low_fraction": float(np.mean((wr >= 0.45) & (sr < 0.15))),
        "absolute_shift_target_median_px": quantile(np.abs(shift), 0.50),
        "reliability_weighted_shift_px": float(np.mean(np.abs(shift) * sr)),
        "signed_shift_target_mean_px": float(np.mean(shift)),
        "source_snr_median": quantile(values["source_snr"], 0.50),
        "source_edge_width_median_px": quantile(values["source_edge_width"], 0.50),
        "current_geometry_gate_median": quantile(gate, 0.50),
        "current_geometry_gate_on_shift_unreliable": float(np.mean(gate[low_shift])) if np.any(low_shift) else float("nan"),
        "current_geometry_gate_on_shift_reliable": float(np.mean(gate[high_shift])) if np.any(high_shift) else float("nan"),
        "current_abs_shift_on_shift_unreliable_px": float(np.mean(np.abs(predicted_shift[low_shift]))) if np.any(low_shift) else float("nan"),
        "current_abs_shift_on_shift_reliable_px": float(np.mean(np.abs(predicted_shift[high_shift]))) if np.any(high_shift) else float("nan"),
        "blur_sigma_px": float(record["blur_sigma_px"]),
        "noise_sigma_gray": float(record["noise_sigma"]),
        "contrast_gray": float(record["contrast_abs"]),
        "illumination_amplitude_gray": float(record["illumination_amplitude"]),
        "fade_strength": float(record["fade_strength"]),
        "halo_strength": float(record["halo_strength"]),
        "motion_length_px": int(record["motion_length_px"]),
    }


def aggregate_family(rows: list[dict], family: str) -> dict:
    chosen = [row for row in rows if row["family"] == family]
    result: dict[str, object] = {"family": family, "samples": len(chosen)}
    metrics = [
        "width_reliability_median",
        "width_reliability_p25",
        "width_safe_fraction",
        "shift_reliability_median",
        "shift_reliability_p25",
        "shift_safe_fraction",
        "shift_suppressed_fraction",
        "width_high_shift_low_fraction",
        "absolute_shift_target_median_px",
        "reliability_weighted_shift_px",
        "signed_shift_target_mean_px",
        "source_snr_median",
        "source_edge_width_median_px",
        "current_geometry_gate_median",
        "current_geometry_gate_on_shift_unreliable",
        "current_geometry_gate_on_shift_reliable",
        "current_abs_shift_on_shift_unreliable_px",
        "current_abs_shift_on_shift_reliable_px",
    ]
    for metric in metrics:
        values = np.asarray([row[metric] for row in chosen], dtype=np.float64)
        values = values[np.isfinite(values)]
        result[f"{metric}_median"] = quantile(values, 0.50)
        result[f"{metric}_p10"] = quantile(values, 0.10)
        result[f"{metric}_p90"] = quantile(values, 0.90)
    return result


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError("no rows")
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def rank_separation(rows: list[dict]) -> dict:
    family_groups = {
        family: np.asarray(
            [row["shift_reliability_p25"] for row in rows if row["family"] == family],
            dtype=np.float64,
        )
        for family in FAMILIES
    }
    kw = stats.kruskal(*[family_groups[family] for family in FAMILIES])
    all_values = np.concatenate(list(family_groups.values()))
    n = len(all_values)
    epsilon_squared = max((float(kw.statistic) - len(FAMILIES) + 1) / (n - len(FAMILIES)), 0.0)

    safe = {"asymmetric_blur_halo", "uneven_illumination"}
    unsafe = {"low_contrast", "boundary_fade"}
    subset = [row for row in rows if row["family"] in safe | unsafe]
    labels = np.asarray([1 if row["family"] in safe else 0 for row in subset], dtype=np.int32)
    p25_score = np.asarray([row["shift_reliability_p25"] for row in subset], dtype=np.float64)
    safe_fraction_score = np.asarray([row["shift_safe_fraction"] for row in subset], dtype=np.float64)
    suppressed_score = -np.asarray([row["shift_suppressed_fraction"] for row in subset], dtype=np.float64)
    return {
        "kruskal_shift_reliability_p25": {
            "statistic": float(kw.statistic),
            "p_value": float(kw.pvalue),
            "epsilon_squared": float(epsilon_squared),
        },
        "safe_halo_uneven_vs_unsafe_lowcontrast_fade_auc": {
            "shift_reliability_p25": float(roc_auc_score(labels, p25_score)),
            "shift_safe_fraction": float(roc_auc_score(labels, safe_fraction_score)),
            "negative_shift_suppressed_fraction": float(roc_auc_score(labels, suppressed_score)),
        },
    }


def plot_representatives(representatives: dict[str, dict]) -> None:
    fig, axes = plt.subplots(len(FAMILIES), 6, figsize=(19, 14), constrained_layout=True)
    columns = ["Source", "Target", "Known mask", "Width reliability", "Shift reliability", "Shift target (px)"]
    for col, title in enumerate(columns):
        axes[0, col].set_title(title, fontsize=11)
    for row_index, family in enumerate(FAMILIES):
        item = representatives[family]
        source, target, mask = item["source"], item["target"], item["mask"]
        ys, xs, values = item["ys"], item["xs"], item["values"]
        axes[row_index, 0].imshow(source, cmap="gray", vmin=0, vmax=1)
        axes[row_index, 1].imshow(target, cmap="gray", vmin=0, vmax=1)
        axes[row_index, 2].imshow(mask, cmap="gray", vmin=0, vmax=1)
        for col, key, cmap, vmin, vmax in (
            (3, "width_reliability", "viridis", 0.0, 1.0),
            (4, "shift_reliability", "viridis", 0.0, 1.0),
            (5, "normal_shift_target", "coolwarm", -1.5, 1.5),
        ):
            axes[row_index, col].imshow(source, cmap="gray", vmin=0, vmax=1, alpha=0.32)
            plot = axes[row_index, col].scatter(xs, ys, c=values[key], s=3.0, cmap=cmap, vmin=vmin, vmax=vmax)
            if row_index == len(FAMILIES) - 1:
                fig.colorbar(plot, ax=axes[row_index, col], fraction=0.046, pad=0.02)
        axes[row_index, 0].set_ylabel(family.replace("_", "\n"), fontsize=9)
        for col in range(6):
            axes[row_index, col].set_xticks([])
            axes[row_index, col].set_yticks([])
    fig.suptitle("Oracle width/shift reliability targets from frozen R74 pairs", fontsize=15)
    fig.savefig(OUTPUT / "representative_target_maps.png", dpi=170)
    plt.close(fig)


def spearman_summary(point_vectors: dict[str, list[np.ndarray]]) -> dict:
    concatenated = {key: np.concatenate(value) for key, value in point_vectors.items()}
    pairs = (
        ("current_geometry_gate", "width_reliability"),
        ("current_geometry_gate", "shift_reliability"),
        ("width_reliability", "shift_reliability"),
        ("current_normal_shift", "normal_shift_target"),
    )
    result = {}
    for left, right in pairs:
        rho, p_value = stats.spearmanr(concatenated[left], concatenated[right])
        result[f"{left}_vs_{right}"] = {"rho": float(rho), "p_value": float(p_value)}
    wr = concatenated["width_reliability"]
    sr = concatenated["shift_reliability"]
    result["all_boundary_points"] = int(wr.size)
    result["width_high_shift_low_fraction"] = float(np.mean((wr >= 0.45) & (sr < 0.15)))
    return result


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(R74_MANIFEST.read_text(encoding="utf-8"))
    records = [record for record in manifest["records"] if record["family"] in FAMILIES]
    if len(records) != 100:
        raise RuntimeError(f"expected 100 frozen R74 records, found {len(records)}")

    sample_rows: list[dict] = []
    representatives: dict[str, dict] = {}
    point_vectors: dict[str, list[np.ndarray]] = {
        "current_geometry_gate": [],
        "current_normal_shift": [],
        "width_reliability": [],
        "shift_reliability": [],
        "normal_shift_target": [],
    }
    for index, record in enumerate(records):
        source = read_gray(record["src"])
        target = read_gray(record["lbl"])
        mask = read_gray(record["mask"])
        sdf, normal_x, normal_y = signed_distance_and_normals(mask)
        ys, xs = deterministic_boundary_points(sdf, MAX_POINTS_PER_SAMPLE)
        nx, ny = normal_x[ys, xs], normal_y[ys, xs]
        source_profile = sample_profiles(source, xs, ys, nx, ny)
        target_profile = sample_profiles(target, xs, ys, nx, ny)
        values = derive_reliability_targets(source_profile, target_profile)

        internal_name = f"R74_{record['family']}_{Path(record['filename']).stem}"
        internal_dir = INTERNAL_ROOT / internal_name
        current_maps = {
            key: squeeze_map(internal_dir / f"{key}.npy")
            for key in ("geometry_gate", "normal_shift", "width_gain")
        }
        current = {key: value[ys, xs] for key, value in current_maps.items()}
        sample_rows.append(sample_row(record, values, current))
        point_vectors["current_geometry_gate"].append(current["geometry_gate"])
        point_vectors["current_normal_shift"].append(current["normal_shift"])
        point_vectors["width_reliability"].append(values["width_reliability"])
        point_vectors["shift_reliability"].append(values["shift_reliability"])
        point_vectors["normal_shift_target"].append(values["normal_shift_target"])

        if record["family"] not in representatives:
            representatives[record["family"]] = {
                "source": source,
                "target": target,
                "mask": mask,
                "ys": ys,
                "xs": xs,
                "values": values,
            }
        if (index + 1) % 20 == 0:
            print(f"processed {index + 1}/{len(records)}")

    family_rows = [aggregate_family(sample_rows, family) for family in FAMILIES]
    separation = rank_separation(sample_rows)
    correlations = spearman_summary(point_vectors)
    write_csv(OUTPUT / "sample_statistics.csv", sample_rows)
    write_csv(OUTPUT / "family_statistics.csv", family_rows)
    plot_representatives(representatives)

    summary = {
        "status": "complete",
        "scope": "read_only_target_diagnosis_no_training_no_model_changes",
        "records": len(records),
        "families": list(FAMILIES),
        "points_per_sample_max": MAX_POINTS_PER_SAMPLE,
        "profile_offsets_px": [float(OFFSETS[0]), float(OFFSETS[-1]), 1.0],
        "target_semantics": {
            "width_reliability": "confidence that a local normal profile has enough visible, monotone evidence to estimate edge width independently of position",
            "shift_reliability": "stricter confidence that the local edge center is unique, stable, precise, and within the renderer shift range",
            "width_gain_target": "source-to-target 10-90 profile width ratio, attenuated toward identity only by width reliability",
            "normal_shift_target": "source edge center minus target edge center, clamped to renderer range; reliability is separate",
        },
        "separation": separation,
        "correlations": correlations,
        "family_statistics": family_rows,
        "inputs": {
            "r74_manifest": str(R74_MANIFEST),
            "r114_internal_maps": str(INTERNAL_ROOT),
        },
    }
    (OUTPUT / "diagnosis_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"status": "complete", "output": str(OUTPUT), "separation": separation}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
