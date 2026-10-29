"""Audit dynamic degradation visibility, recoverability, and source ambiguity."""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
R109 = Path(PROJECT_ROOT / CONFIG["sources"]["r109_root"])
OUTPUT = ROOT / "results" / "degradation_recoverability"
OUTPUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(R109 / "training"))
from r109_dataset import R109Dataset


def gradient_magnitude(image: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    return np.sqrt(gx * gx + gy * gy + 1e-12)


def highpass(image: np.ndarray, sigma: float = 1.5) -> np.ndarray:
    return image - cv2.GaussianBlur(image, (0, 0), sigma)


def source_feature(image: np.ndarray) -> np.ndarray:
    small = cv2.resize(image, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    small = (small - small.mean()) / max(float(small.std()), 1e-4)
    grad = gradient_magnitude(small)
    return np.concatenate([small.ravel(), grad.ravel()]).astype(np.float32)


def row_metrics(item: dict, epoch: int) -> tuple[dict[str, object], np.ndarray, np.ndarray]:
    source = item["source"][0, 0].numpy().astype(np.float32)
    target = item["target"][0, 0].numpy().astype(np.float32)
    mask = item["mask"][0, 0].numpy().astype(np.float32)
    edge = item["edge"][0, 0].numpy().astype(np.float32)
    truth = mask >= 0.5
    polarity = float(item["polarity"][0])
    midpoint = float(item["midpoint"][0])
    predicted = polarity * (source - midpoint) >= 0
    intersection = np.logical_and(predicted, truth).sum()
    union = np.logical_or(predicted, truth).sum()
    iou = float(intersection / max(union, 1))
    dice = float((2 * intersection + 1) / (predicted.sum() + truth.sum() + 1))
    source_grad = gradient_magnitude(source)
    target_grad = gradient_magnitude(target)
    boundary = edge > 0.5
    flat = edge < 0.05
    boundary_grad = float(np.median(source_grad[boundary])) if boundary.any() else 0.0
    flat_grad_p95 = float(np.quantile(source_grad[flat], .95)) if flat.any() else float(np.quantile(source_grad, .95))
    visibility = boundary_grad / max(flat_grad_p95, 1e-6)
    boundary_visible_fraction = float(np.mean(source_grad[boundary] > flat_grad_p95)) if boundary.any() else 0.0
    if truth.any() and (~truth).any():
        source_contrast = float(source[truth].mean() - source[~truth].mean())
        target_contrast = float(target[truth].mean() - target[~truth].mean())
    else:
        source_contrast = target_contrast = 0.0
    source_high = highpass(source)
    target_high = highpass(target)
    boundary_weight = edge.astype(np.float64)
    weighted_source_high = source_high.astype(np.float64) * np.sqrt(boundary_weight)
    weighted_target_high = target_high.astype(np.float64) * np.sqrt(boundary_weight)
    high_denominator = float(np.linalg.norm(weighted_source_high) * np.linalg.norm(weighted_target_high))
    boundary_highpass_cosine = 0.0 if high_denominator <= 1e-12 else float(np.sum(weighted_source_high * weighted_target_high) / high_denominator)
    target_energy = float(np.sum(weighted_target_high * weighted_target_high))
    aligned_gain = 0.0 if target_energy <= 1e-12 else float(np.sum(weighted_source_high * weighted_target_high) / target_energy)
    unexplained = weighted_source_high - aligned_gain * weighted_target_high
    low_error = cv2.GaussianBlur(source - target, (0, 0), 8.0)
    noise_mad = float(np.median(np.abs(source_high[flat] - np.median(source_high[flat])))) if flat.any() else 0.0
    contrast_snr = abs(source_contrast) / max(1.4826 * noise_mad, 1e-6)
    area_error = float(abs(predicted.mean() - truth.mean()))
    return ({
        "scene_index": int(item["scene_index"]),
        "epoch": int(epoch),
        "role": str(item["role"]),
        "family": str(item["family"]),
        "challenge": str(item["challenge"]),
        "polarity": polarity,
        "source_target_mae_gray": float(np.mean(np.abs(source - target)) * 255),
        "boundary_mae_gray": float(np.sum(np.abs(source - target) * edge) / max(float(edge.sum()), 1e-8) * 255),
        "low_frequency_error_gray": float(np.mean(np.abs(low_error)) * 255),
        "source_high_frequency_rms_gray": float(np.sqrt(np.mean(source_high * source_high)) * 255),
        "target_high_frequency_rms_gray": float(np.sqrt(np.mean(target_high * target_high)) * 255),
        "high_frequency_retention_ratio": float(np.sqrt(np.mean(source_high * source_high)) / max(float(np.sqrt(np.mean(target_high * target_high))), 1e-8)),
        "boundary_highpass_cosine": boundary_highpass_cosine,
        "target_aligned_highfrequency_gain": aligned_gain,
        "unexplained_boundary_highfrequency_rms_gray": float(np.sqrt(np.sum(unexplained * unexplained) / max(float(boundary_weight.sum()), 1e-8)) * 255),
        "source_threshold_iou": iou,
        "source_threshold_dice": dice,
        "source_threshold_area_error": area_error,
        "source_boundary_gradient_median": boundary_grad,
        "target_boundary_gradient_median": float(np.median(target_grad[boundary])) if boundary.any() else 0.0,
        "boundary_visibility_ratio": visibility,
        "boundary_visible_fraction": boundary_visible_fraction,
        "source_signed_contrast": source_contrast,
        "target_signed_contrast": target_contrast,
        "contrast_retention_ratio": abs(source_contrast) / max(abs(target_contrast), 1e-6),
        "contrast_snr": contrast_snr,
        "identity_record": bool(str(item["challenge"]) == "identity"),
    }, source_feature(source), cv2.resize(truth.astype(np.uint8), (64, 64), interpolation=cv2.INTER_NEAREST).astype(bool))


def collision_analysis(features: dict[str, list[np.ndarray]], masks: dict[str, list[np.ndarray]], metadata: dict[str, list[dict]]) -> tuple[pd.DataFrame, dict[str, object]]:
    rows = []
    summaries = {}
    for challenge in sorted(features):
        matrix = np.stack(features[challenge])
        count = len(matrix)
        components = min(48, count - 1, matrix.shape[1])
        reduced = PCA(n_components=components, random_state=113, svd_solver="randomized").fit_transform(matrix)
        neighbor = NearestNeighbors(n_neighbors=2, metric="euclidean").fit(reduced)
        distances, indices = neighbor.kneighbors(reduced)
        normalized_distance = distances[:, 1] / max(float(np.median(distances[:, 1])), 1e-8)
        pair_ious = []
        for index, other_index in enumerate(indices[:, 1]):
            first, second = masks[challenge][index], masks[challenge][other_index]
            union = np.logical_or(first, second).sum()
            iou = float(np.logical_and(first, second).sum() / max(union, 1))
            pair_ious.append(iou)
            rows.append({
                "challenge": challenge,
                "scene_index": metadata[challenge][index]["scene_index"],
                "neighbor_scene_index": metadata[challenge][other_index]["scene_index"],
                "family": metadata[challenge][index]["family"],
                "neighbor_family": metadata[challenge][other_index]["family"],
                "pca_neighbor_distance": float(distances[index, 1]),
                "normalized_neighbor_distance": float(normalized_distance[index]),
                "mask_iou": iou,
                "different_family": metadata[challenge][index]["family"] != metadata[challenge][other_index]["family"],
            })
        pair_ious = np.asarray(pair_ious)
        near = normalized_distance <= np.quantile(normalized_distance, .05)
        ambiguous = near & (pair_ious < .5)
        summaries[challenge] = {
            "records": count,
            "nearest_mask_iou_median": float(np.median(pair_ious)),
            "nearest_mask_iou_p05": float(np.quantile(pair_ious, .05)),
            "near_source_pairs": int(near.sum()),
            "near_source_low_mask_iou_pairs": int(ambiguous.sum()),
            "ambiguity_fraction_within_nearest_5pct": float(ambiguous.sum() / max(int(near.sum()), 1)),
        }
    return pd.DataFrame(rows), summaries


def save_worst_panel(frame: pd.DataFrame) -> None:
    worst = frame.loc[~frame.role.eq("flat_negative")].nsmallest(16, "source_threshold_iou")
    figure, axes = plt.subplots(len(worst), 3, figsize=(9, 2.2 * len(worst)))
    for row_index, row in enumerate(worst.itertuples(index=False)):
        dataset = R109Dataset("train" if row.scene_index < 5000 else "validation", epoch=int(row.epoch))
        local_index = row.scene_index if row.scene_index < 5000 else row.scene_index - 5000
        item = dataset[local_index]
        source = item["source"][0, 0].numpy()
        target = item["target"][0, 0].numpy()
        mask = item["mask"][0, 0].numpy()
        for column, (image, title) in enumerate(((source, f"{row.family}/{row.challenge}\nIoU={row.source_threshold_iou:.3f}"), (target, "target"), (mask, "mask"))):
            axes[row_index, column].imshow(image, cmap="gray", vmin=0, vmax=1)
            axes[row_index, column].set_title(title, fontsize=8)
            axes[row_index, column].axis("off")
    figure.tight_layout()
    figure.savefig(OUTPUT / "worst_recoverability_panel.png", dpi=150)
    plt.close(figure)


def main() -> int:
    rows = []
    collision_features: dict[str, list[np.ndarray]] = defaultdict(list)
    collision_masks: dict[str, list[np.ndarray]] = defaultdict(list)
    collision_metadata: dict[str, list[dict]] = defaultdict(list)
    epochs = [int(value) for value in CONFIG["degradation_epochs"]]
    for split in ("train", "validation"):
        for epoch in epochs:
            dataset = R109Dataset(split, epoch=epoch)
            for local_index in range(len(dataset)):
                item = dataset[local_index]
                row, feature, mask = row_metrics(item, epoch)
                row["split"] = split
                rows.append(row)
                if row["role"] not in {"flat_negative", "identity"}:
                    challenge = str(row["challenge"])
                    collision_features[challenge].append(feature)
                    collision_masks[challenge].append(mask)
                    collision_metadata[challenge].append({"scene_index": row["scene_index"], "family": row["family"]})
            print(json.dumps({"split": split, "epoch": epoch, "rows": len(rows)}), flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUTPUT / "per_observation_metrics.csv", index=False, encoding="utf-8-sig")
    shape_frame = frame.loc[~frame.role.eq("flat_negative")].copy()
    challenge_summary = shape_frame.groupby(["challenge"], as_index=False).agg(
        records=("scene_index", "size"),
        source_threshold_iou_median=("source_threshold_iou", "median"),
        source_threshold_iou_p05=("source_threshold_iou", lambda value: value.quantile(.05)),
        boundary_visibility_median=("boundary_visibility_ratio", "median"),
        boundary_visible_fraction_median=("boundary_visible_fraction", "median"),
        contrast_retention_median=("contrast_retention_ratio", "median"),
        contrast_snr_median=("contrast_snr", "median"),
        high_frequency_retention_median=("high_frequency_retention_ratio", "median"),
        boundary_highpass_cosine_median=("boundary_highpass_cosine", "median"),
        target_aligned_highfrequency_gain_median=("target_aligned_highfrequency_gain", "median"),
        unexplained_boundary_highfrequency_rms_median_gray=("unexplained_boundary_highfrequency_rms_gray", "median"),
        boundary_mae_median_gray=("boundary_mae_gray", "median"),
    )
    challenge_summary.to_csv(OUTPUT / "challenge_summary.csv", index=False, encoding="utf-8-sig")
    family_challenge = shape_frame.groupby(["family", "challenge"], as_index=False).agg(
        records=("scene_index", "size"),
        source_threshold_iou_median=("source_threshold_iou", "median"),
        source_threshold_iou_p05=("source_threshold_iou", lambda value: value.quantile(.05)),
        visibility_median=("boundary_visibility_ratio", "median"),
        contrast_snr_median=("contrast_snr", "median"),
        high_frequency_retention_median=("high_frequency_retention_ratio", "median"),
        boundary_highpass_cosine_median=("boundary_highpass_cosine", "median"),
        aligned_highfrequency_gain_median=("target_aligned_highfrequency_gain", "median"),
    )
    family_challenge.to_csv(OUTPUT / "family_challenge_summary.csv", index=False, encoding="utf-8-sig")
    collisions, collision_summary = collision_analysis(collision_features, collision_masks, collision_metadata)
    collisions.to_csv(OUTPUT / "nearest_source_ambiguity.csv", index=False, encoding="utf-8-sig")
    save_worst_panel(frame)

    manifest = json.loads((Path(PROJECT_ROOT / CONFIG["sources"]["data_package"]) / "manifest.json").read_text(encoding="utf-8"))
    roles = pd.Series([record["role"] for record in manifest["records"]])
    record_identity_fraction = float(roles.eq("identity").mean())
    effective_first_identity = record_identity_fraction
    effective_identity_fraction = 0.5 + 0.5 * effective_first_identity
    summary = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "observation_rows": len(frame),
        "records": len(manifest["records"]),
        "epochs": epochs,
        "challenge_summary": challenge_summary.to_dict(orient="records"),
        "source_ambiguity": collision_summary,
        "effective_training_composition": {
            "record_identity_role_fraction": record_identity_fraction,
            "paired_clear_observation_per_record": 1,
            "effective_clear_identity_fraction_after_flatten": effective_identity_fraction,
            "explanation": "Every dataset record is flattened into one degraded observation plus one clear target observation; identity-role records make both observations clear.",
        },
        "hard_visibility": {
            "threshold_iou_below_0p5": int((shape_frame.source_threshold_iou < .5).sum()),
            "boundary_visibility_below_1": int((shape_frame.boundary_visibility_ratio < 1).sum()),
            "contrast_snr_below_1": int((shape_frame.contrast_snr < 1).sum()),
        },
        "interpretation_boundary": "Threshold recoverability uses target midpoint and polarity, so it is a favorable diagnostic, not a deployable baseline. PCA nearest-neighbor collisions are evidence of ambiguity, not proof of identical physical images.",
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
