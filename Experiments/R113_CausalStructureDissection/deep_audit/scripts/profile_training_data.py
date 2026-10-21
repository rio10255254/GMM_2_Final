"""Full 5,512-record audit of R109 target, mask, and SDF training arrays."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
PACKAGE = Path(CONFIG["sources"]["data_package"])
OUTPUT = ROOT / "results" / "data_profile"
OUTPUT.mkdir(parents=True, exist_ok=True)


def sha_array(value: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(str(value.dtype).encode())
    digest.update(np.asarray(value.shape, np.int64).tobytes())
    digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def shape_hash(binary: np.ndarray) -> str:
    yy, xx = np.nonzero(binary)
    if len(xx) == 0:
        return "empty"
    crop = binary[yy.min() : yy.max() + 1, xx.min() : xx.max() + 1].astype(np.uint8) * 255
    side = max(crop.shape)
    square = np.zeros((side, side), np.uint8)
    top = (side - crop.shape[0]) // 2
    left = (side - crop.shape[1]) // 2
    square[top : top + crop.shape[0], left : left + crop.shape[1]] = crop
    normalized = cv2.resize(square, (64, 64), interpolation=cv2.INTER_AREA) > 127
    return hashlib.sha256(np.packbits(normalized).tobytes()).hexdigest()


def topology(binary: np.ndarray) -> tuple[int, int, float, float, int]:
    value = binary.astype(np.uint8)
    labels, _ = cv2.connectedComponents(value, connectivity=8)
    components = max(0, labels - 1)
    contours, hierarchy = cv2.findContours(value, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    perimeter = float(sum(cv2.arcLength(contour, True) for contour in contours))
    holes = 0
    if hierarchy is not None:
        holes = int(sum(1 for entry in hierarchy[0] if entry[3] >= 0))
    circularity = 0.0
    area = float(value.sum())
    if perimeter > 0:
        circularity = float(4 * math.pi * area / (perimeter * perimeter))
    border = int(value[0].sum() + value[-1].sum() + value[:, 0].sum() + value[:, -1].sum())
    return components, holes, perimeter, circularity, border


def gradient_rms(image: np.ndarray, weight: np.ndarray | None = None) -> float:
    gx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    energy = gx * gx + gy * gy
    if weight is None or not np.any(weight):
        return float(np.sqrt(np.mean(energy)))
    return float(np.sqrt(np.sum(energy * weight) / max(float(weight.sum()), 1e-8)))


def record_metrics(record: dict) -> dict[str, object]:
    target_u8 = np.load(PACKAGE / record["target"], mmap_mode="r")
    mask_u8 = np.load(PACKAGE / record["mask"], mmap_mode="r")
    sdf16 = np.load(PACKAGE / record["sdf"], mmap_mode="r")
    target = np.asarray(target_u8, np.float32) / 255.0
    mask = np.asarray(mask_u8, np.float32) / 255.0
    sdf = np.asarray(sdf16, np.float32)
    binary = mask >= 0.5
    area_fraction = float(binary.mean())
    soft_area_fraction = float(mask.mean())
    antialias_fraction = float(np.mean((mask > 0) & (mask < 1)))
    components, holes, perimeter, circularity, border_pixels = topology(binary)
    yy, xx = np.nonzero(binary)
    if len(xx):
        bbox_width = int(xx.max() - xx.min() + 1)
        bbox_height = int(yy.max() - yy.min() + 1)
        inside = target[binary]
        outside = target[~binary]
        inside_mean = float(inside.mean())
        outside_mean = float(outside.mean())
        contrast = inside_mean - outside_mean
        interior = cv2.erode(binary.astype(np.uint8), np.ones((7, 7), np.uint8), iterations=1).astype(bool)
        interior_texture = gradient_rms(target, interior.astype(np.float32)) if interior.any() else 0.0
    else:
        bbox_width = bbox_height = 0
        inside_mean = float("nan")
        outside_mean = float(target.mean())
        contrast = 0.0
        interior_texture = 0.0
    polarity = float(record["polarity"])
    polarity_consistent = True if not binary.any() else bool(np.sign(contrast or polarity) == np.sign(polarity))
    sdf_sign = sdf >= 0
    sdf_union = int(np.logical_or(sdf_sign, binary).sum())
    sdf_sign_iou = 1.0 if sdf_union == 0 else float(np.logical_and(sdf_sign, binary).sum() / sdf_union)
    boundary_soft = (mask > 0.05) & (mask < 0.95)
    edge_weight = np.exp(-np.abs(sdf) / 2.5).astype(np.float32) if binary.any() else np.zeros_like(sdf, np.float32)
    sdf_at_soft_boundary_abs_mean = float(np.mean(np.abs(sdf[boundary_soft]))) if boundary_soft.any() else 0.0
    midpoint = float(record["midpoint"])
    intensity_midpoint = 0.5 * (inside_mean + outside_mean) if binary.any() else float(target.mean())
    target_low = cv2.GaussianBlur(target, (0, 0), 2.0)
    target_high_rms = float(np.sqrt(np.mean((target - target_low) ** 2)))
    hu = cv2.HuMoments(cv2.moments(binary.astype(np.uint8))).flatten()
    hu_signed_log = [-math.copysign(math.log10(abs(float(value)) + 1e-30), float(value)) for value in hu]
    return {
        "scene_index": int(record["scene_index"]),
        "scene_id": record["scene_id"],
        "split": record["split"],
        "role": record["role"],
        "family": record["family"],
        "polarity": polarity,
        "target_width_px": float(record["target_width_px"]),
        "midpoint": midpoint,
        "target_hash": sha_array(np.asarray(target_u8)),
        "mask_hash": sha_array(np.asarray(mask_u8)),
        "sdf_hash": sha_array(np.asarray(sdf16)),
        "combined_hash": hashlib.sha256((sha_array(np.asarray(target_u8)) + sha_array(np.asarray(mask_u8)) + sha_array(np.asarray(sdf16))).encode()).hexdigest(),
        "normalized_shape_hash": shape_hash(binary),
        "target_dtype": str(target_u8.dtype),
        "mask_dtype": str(mask_u8.dtype),
        "sdf_dtype": str(sdf16.dtype),
        "target_min": float(target.min()),
        "target_max": float(target.max()),
        "target_mean": float(target.mean()),
        "target_std": float(target.std()),
        "target_high_frequency_rms": target_high_rms,
        "inside_mean": inside_mean,
        "outside_mean": outside_mean,
        "signed_contrast": contrast,
        "absolute_contrast": abs(contrast),
        "polarity_consistent": polarity_consistent,
        "area_fraction": area_fraction,
        "soft_area_fraction": soft_area_fraction,
        "antialias_fraction": antialias_fraction,
        "components": components,
        "holes": holes,
        "perimeter_px": perimeter,
        "circularity": circularity,
        "border_foreground_pixels": border_pixels,
        "bbox_width_px": bbox_width,
        "bbox_height_px": bbox_height,
        "interior_texture_gradient_rms": interior_texture,
        "sdf_min": float(sdf.min()),
        "sdf_max": float(sdf.max()),
        "sdf_finite": bool(np.isfinite(sdf).all()),
        "sdf_sign_iou": sdf_sign_iou,
        "sdf_at_soft_boundary_abs_mean": sdf_at_soft_boundary_abs_mean,
        "training_edge_weight_sum": float(edge_weight.sum()),
        "training_edge_weight_fraction": float(edge_weight.mean()),
        "manifest_midpoint_error": abs(midpoint - intensity_midpoint),
        **{f"hu_{index + 1}": value for index, value in enumerate(hu_signed_log)},
    }


def duplicate_summary(frame: pd.DataFrame, column: str) -> list[dict[str, object]]:
    rows = []
    for value, group in frame.groupby(column):
        if len(group) <= 1:
            continue
        rows.append({
            "key_type": column,
            "key": value,
            "records": len(group),
            "train_records": int(group.split.eq("train").sum()),
            "validation_records": int(group.split.eq("validation").sum()),
            "cross_split": bool(group.split.nunique() > 1),
            "scene_ids": "|".join(group.scene_id.astype(str).tolist()),
            "families": "|".join(sorted(group.family.astype(str).unique())),
        })
    return rows


def distribution_comparison(frame: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "target_width_px", "midpoint", "absolute_contrast", "area_fraction",
        "antialias_fraction", "perimeter_px", "circularity", "bbox_width_px",
        "bbox_height_px", "target_high_frequency_rms", "interior_texture_gradient_rms",
        "sdf_sign_iou", "manifest_midpoint_error",
    ]
    rows = []
    train = frame.loc[frame.split.eq("train")]
    validation = frame.loc[frame.split.eq("validation")]
    for metric in metrics:
        left = train[metric].dropna().to_numpy(float)
        right = validation[metric].dropna().to_numpy(float)
        result = ks_2samp(left, right)
        pooled = math.sqrt(0.5 * (left.var(ddof=1) + right.var(ddof=1)))
        rows.append({
            "metric": metric,
            "train_mean": float(left.mean()),
            "validation_mean": float(right.mean()),
            "train_median": float(np.median(left)),
            "validation_median": float(np.median(right)),
            "standardized_mean_difference": float((right.mean() - left.mean()) / max(pooled, 1e-12)),
            "ks_statistic": float(result.statistic),
            "ks_p_value": float(result.pvalue),
        })
    return pd.DataFrame(rows)


def save_representative_panel(frame: pd.DataFrame) -> None:
    selections = []
    for family in CONFIG["expected"]["families"]:
        group = frame.loc[(frame.family == family) & (frame.split == "train")].sort_values("scene_index")
        if len(group):
            selections.append(group.iloc[len(group) // 2])
    figure, axes = plt.subplots(len(selections), 3, figsize=(9, 2.4 * len(selections)))
    for row_index, row in enumerate(selections):
        record = manifest_by_index[int(row.scene_index)]
        target = np.load(PACKAGE / record["target"])
        mask = np.load(PACKAGE / record["mask"])
        sdf = np.load(PACKAGE / record["sdf"])
        for axis, image, title, cmap in (
            (axes[row_index, 0], target, f"{row.family}: target", "gray"),
            (axes[row_index, 1], mask, "soft mask", "gray"),
            (axes[row_index, 2], sdf, "SDF", "coolwarm"),
        ):
            axis.imshow(image, cmap=cmap)
            axis.set_title(title, fontsize=8)
            axis.axis("off")
    figure.tight_layout()
    figure.savefig(OUTPUT / "representative_family_panel.png", dpi=150)
    plt.close(figure)


def save_anomaly_panel(frame: pd.DataFrame) -> None:
    candidates = pd.concat([
        frame.nlargest(4, "manifest_midpoint_error"),
        frame.nsmallest(4, "sdf_sign_iou"),
        frame.nlargest(4, "antialias_fraction"),
        frame.loc[~frame.polarity_consistent].head(4),
    ]).drop_duplicates("scene_index").head(16)
    if candidates.empty:
        return
    figure, axes = plt.subplots(len(candidates), 3, figsize=(9, 2.4 * len(candidates)))
    if len(candidates) == 1:
        axes = np.asarray([axes])
    for row_index, row in enumerate(candidates.itertuples(index=False)):
        record = manifest_by_index[int(row.scene_index)]
        images = [np.load(PACKAGE / record[key]) for key in ("target", "mask", "sdf")]
        titles = [f"{row.scene_id}\n{row.family}/{row.role}", f"sign IoU={row.sdf_sign_iou:.3f}", f"mid err={row.manifest_midpoint_error:.3f}"]
        for column, (image, title) in enumerate(zip(images, titles)):
            axes[row_index, column].imshow(image, cmap="coolwarm" if column == 2 else "gray")
            axes[row_index, column].set_title(title, fontsize=8)
            axes[row_index, column].axis("off")
    figure.tight_layout()
    figure.savefig(OUTPUT / "data_anomaly_panel.png", dpi=150)
    plt.close(figure)


def main() -> int:
    global manifest_by_index
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    records = manifest["records"]
    manifest_by_index = {int(record["scene_index"]): record for record in records}
    rows = []
    for index, record in enumerate(records, 1):
        rows.append(record_metrics(record))
        if index % 250 == 0 or index == len(records):
            print(json.dumps({"done": index, "total": len(records)}), flush=True)
    frame = pd.DataFrame(rows).sort_values("scene_index")
    frame.to_csv(OUTPUT / "per_record_profile.csv", index=False, encoding="utf-8-sig")

    duplicates = []
    for column in ("combined_hash", "target_hash", "mask_hash", "sdf_hash", "normalized_shape_hash"):
        duplicates.extend(duplicate_summary(frame, column))
    duplicate_frame = pd.DataFrame(duplicates)
    duplicate_frame.to_csv(OUTPUT / "duplicate_groups.csv", index=False, encoding="utf-8-sig")

    counts = frame.groupby(["split", "family", "role", "polarity"], as_index=False).size().rename(columns={"size": "records"})
    counts.to_csv(OUTPUT / "population_counts.csv", index=False, encoding="utf-8-sig")
    distribution = distribution_comparison(frame)
    distribution.to_csv(OUTPUT / "train_validation_distribution.csv", index=False, encoding="utf-8-sig")
    family_summary = frame.groupby(["split", "family"], as_index=False).agg(
        records=("scene_id", "size"),
        area_fraction_median=("area_fraction", "median"),
        perimeter_median=("perimeter_px", "median"),
        contrast_median=("absolute_contrast", "median"),
        antialias_fraction_median=("antialias_fraction", "median"),
        target_width_median=("target_width_px", "median"),
        texture_median=("interior_texture_gradient_rms", "median"),
        sdf_sign_iou_min=("sdf_sign_iou", "min"),
    )
    family_summary.to_csv(OUTPUT / "family_summary.csv", index=False, encoding="utf-8-sig")

    save_representative_panel(frame)
    save_anomaly_panel(frame)
    cross_split_exact = int(duplicate_frame.loc[(duplicate_frame.key_type == "combined_hash") & duplicate_frame.cross_split].shape[0]) if len(duplicate_frame) else 0
    cross_split_mask = int(duplicate_frame.loc[(duplicate_frame.key_type == "mask_hash") & duplicate_frame.cross_split].shape[0]) if len(duplicate_frame) else 0
    cross_split_shape = int(duplicate_frame.loc[(duplicate_frame.key_type == "normalized_shape_hash") & duplicate_frame.cross_split].shape[0]) if len(duplicate_frame) else 0
    quality = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "records": len(frame),
        "split_counts": frame.split.value_counts().to_dict(),
        "family_counts": frame.family.value_counts().to_dict(),
        "role_counts": frame.role.value_counts().to_dict(),
        "polarity_counts": {str(key): int(value) for key, value in frame.polarity.value_counts().items()},
        "exact_combined_duplicate_groups_cross_split": cross_split_exact,
        "exact_mask_duplicate_groups_cross_split": cross_split_mask,
        "normalized_shape_duplicate_groups_cross_split": cross_split_shape,
        "polarity_inconsistent_records": int((~frame.polarity_consistent).sum()),
        "nonfinite_sdf_records": int((~frame.sdf_finite).sum()),
        "sdf_sign_iou_below_0p99": int((frame.sdf_sign_iou < 0.99).sum()),
        "multi_component_records": int((frame.components > 1).sum()),
        "hole_records": int((frame.holes > 0).sum()),
        "border_touch_records": int((frame.border_foreground_pixels > 0).sum()),
        "antialias_fraction": {
            "median": float(frame.antialias_fraction.median()),
            "p05": float(frame.antialias_fraction.quantile(.05)),
            "p95": float(frame.antialias_fraction.quantile(.95)),
            "zero_records": int((frame.antialias_fraction == 0).sum()),
        },
        "largest_train_validation_distribution_shifts": distribution.reindex(distribution.standardized_mean_difference.abs().sort_values(ascending=False).index).head(5).to_dict(orient="records"),
        "interpretation_boundary": "Normalized shape hashes are a collision screen, not proof of semantic duplication. Exact combined hashes control leakage claims.",
    }
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(quality, ensure_ascii=False, indent=2))
    return 0


manifest_by_index: dict[int, dict] = {}

if __name__ == "__main__":
    raise SystemExit(main())
