"""R100 design falsification experiments.

This script answers three questions before a trainable architecture is frozen:

1. Can a source-image threshold provide a trustworthy transport label?
2. Can synthetic latent texture be strengthened without moving its exact shape?
3. How slowly must spatially varying restoration strength change to avoid an
   apparent boundary displacement?

No model checkpoint, SEM pixel, or real sample structure is used here.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(str(PROJECT_ROOT / 'Experiments/R92_PhysicalTransitionBalancedScratch/data/r92_formal'))
OUTPUT = ROOT / "results" / "architecture_falsification.json"
CONTACT = ROOT / "results" / "target_adapter_contact.png"
SEED = 100041
PATCH = 256
SCENES_PER_ROLE = 12


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def summary(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    if not len(array):
        return {"count": 0, "mean": math.nan, "median": math.nan, "p95": math.nan, "maximum": math.nan}
    return {
        "count": int(len(array)),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95)),
        "maximum": float(array.max()),
    }


def signed_distance(mask: np.ndarray) -> np.ndarray:
    binary = (mask > 0).astype(np.uint8)
    inside = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    outside = cv2.distanceTransform(1 - binary, cv2.DIST_L2, 5)
    return inside - outside


def boundary(mask: np.ndarray) -> np.ndarray:
    return cv2.morphologyEx((mask > 0).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)


def centroid(mask: np.ndarray) -> np.ndarray:
    coordinates = np.argwhere(mask > 0)
    if not len(coordinates):
        return np.asarray([math.nan, math.nan], dtype=np.float64)
    return coordinates[:, ::-1].mean(axis=0)


def mask_metrics(candidate: np.ndarray, truth: np.ndarray) -> dict[str, float]:
    candidate = candidate.astype(bool)
    truth = truth.astype(bool)
    intersection = np.count_nonzero(candidate & truth)
    union = np.count_nonzero(candidate | truth)
    candidate_center = centroid(candidate)
    truth_center = centroid(truth)
    center_error = float(np.linalg.norm(candidate_center - truth_center)) if np.all(np.isfinite(candidate_center)) else 999.0
    truth_sdf = signed_distance(truth.astype(np.uint8))
    candidate_boundary = boundary(candidate)
    boundary_error = float(np.mean(np.abs(truth_sdf[candidate_boundary]))) if np.any(candidate_boundary) else 999.0
    return {
        "iou": float(intersection / max(union, 1)),
        "centroid_error_px": center_error,
        "boundary_distance_px": boundary_error,
    }


def gaussian(image: np.ndarray, sigma: float, radius: int) -> np.ndarray:
    return cv2.GaussianBlur(image.astype(np.float32), (2 * radius + 1, 2 * radius + 1), sigma, borderType=cv2.BORDER_REFLECT_101)


def band_stack(image: np.ndarray) -> np.ndarray:
    source = image.astype(np.float32)
    g07 = gaussian(source, 0.7, 3)
    g14 = gaussian(source, 1.4, 6)
    g28 = gaussian(source, 2.8, 12)
    return np.stack([source - g07, g07 - g14, g14 - g28], axis=-1)


def boost_coefficients(gain: float) -> np.ndarray:
    return np.asarray([gain, 0.70 * gain, 0.20 * gain], dtype=np.float32)


def fine_energy(image: np.ndarray, support: np.ndarray | None = None) -> float:
    band = image.astype(np.float32) - gaussian(image, 0.7, 3)
    if support is not None and np.any(support):
        band = band[support]
    return float(np.mean(np.abs(band)))


def stable_hash(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)


def select_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in manifest["records"]:
        if record["split"] == "validation":
            grouped[str(record["role"])].append(record)
    selected: list[dict[str, Any]] = []
    for role in sorted(grouped):
        rows = sorted(grouped[role], key=lambda row: stable_hash(str(row["scene_id"])))
        selected.extend(rows[:SCENES_PER_ROLE])
    return selected


def structure_crop(mask: np.ndarray, scene_id: str) -> tuple[int, int]:
    coordinates = np.argwhere(boundary(mask >= 128))
    if not len(coordinates):
        coordinates = np.argwhere(mask >= 128)
    selector = stable_hash(scene_id) % max(len(coordinates), 1)
    cy, cx = coordinates[int(selector)] if len(coordinates) else (mask.shape[0] // 2, mask.shape[1] // 2)
    y0 = int(np.clip(int(cy) - PATCH // 2, 0, mask.shape[0] - PATCH))
    x0 = int(np.clip(int(cx) - PATCH // 2, 0, mask.shape[1] - PATCH))
    return y0, x0


def warp(array: np.ndarray, dx: float, dy: float, interpolation: int) -> np.ndarray:
    if abs(dx) + abs(dy) <= 0:
        return array.copy()
    matrix = np.asarray([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    return cv2.warpAffine(array, matrix, (array.shape[1], array.shape[0]), flags=interpolation, borderMode=cv2.BORDER_REFLECT_101)


def threshold_mask(image: np.ndarray, bright_foreground: bool, method: str, recorded_level: float) -> np.ndarray:
    smooth = gaussian(image, 0.8, 3)
    if method == "recorded_level":
        threshold = float(recorded_level)
    elif method == "percentile_level":
        low, high = np.percentile(smooth, [8, 92])
        threshold = 0.5 * float(low + high)
    elif method == "otsu":
        u8 = np.clip(np.rint(smooth * 255.0), 0, 255).astype(np.uint8)
        threshold_u8, _ = cv2.threshold(u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        threshold = float(threshold_u8) / 255.0
    else:
        raise ValueError(method)
    candidate = smooth >= threshold if bright_foreground else smooth <= threshold
    candidate = cv2.morphologyEx(candidate.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return candidate


def source_transport_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows: defaultdict[str, list[dict[str, float]]] = defaultdict(list)
    exposure_consistency: defaultdict[str, list[float]] = defaultdict(list)
    methods = ("recorded_level", "percentile_level", "otsu")
    for record in records:
        target = np.load(PACKAGE / record["target"], mmap_mode="r", allow_pickle=False)
        mask = np.load(PACKAGE / record["mask"], mmap_mode="r", allow_pickle=False)
        y0, x0 = structure_crop(np.asarray(mask), str(record["scene_id"]))
        base_mask = (np.asarray(mask[y0:y0 + PATCH, x0:x0 + PATCH]) >= 128).astype(np.uint8)
        texture = record["texture"]
        bright = bool(texture["bright_foreground"])
        fg = float(texture["foreground_mean"])
        bg = float(texture["background_mean"])
        fraction = float(texture["physical_boundary_intensity_fraction"])
        recorded_level = (1.0 - fraction) * bg + fraction * fg
        scene_commands: defaultdict[str, list[float]] = defaultdict(list)
        for observation in record["observations"]:
            source_full = np.load(PACKAGE / observation["source"], mmap_mode="r", allow_pickle=False)
            source = np.asarray(source_full[y0:y0 + PATCH, x0:x0 + PATCH], dtype=np.float32) / 255.0
            dx = float(observation["motion_dx_px"])
            dy = float(observation["motion_dy_px"])
            truth = warp(base_mask, dx, dy, cv2.INTER_NEAREST)
            target_sdf = signed_distance(truth)
            for method in methods:
                estimated = threshold_mask(source, bright, method, recorded_level)
                source_sdf = signed_distance(estimated)
                support = np.abs(source_sdf) <= 3.5
                difference = np.clip(target_sdf - source_sdf, -1.5, 1.5)
                metrics = mask_metrics(estimated, truth)
                command_abs = float(np.mean(np.abs(difference[support]))) if np.any(support) else 1.5
                command_signed = float(np.mean(difference[support])) if np.any(support) else 0.0
                rows[method].append({
                    **metrics,
                    "command_abs_px": command_abs,
                    "command_signed_px": command_signed,
                    "identity_family": float(observation["degradation_family"] == "identity_and_near_identity"),
                })
                scene_commands[method].append(command_signed)
        for method, commands in scene_commands.items():
            if len(commands) > 1:
                exposure_consistency[method].append(float(np.ptp(np.asarray(commands, dtype=np.float64))))

    output: dict[str, Any] = {}
    for method, method_rows in rows.items():
        all_rows = method_rows
        identity_rows = [row for row in method_rows if row["identity_family"] > 0]
        output[method] = {
            "view_count": len(all_rows),
            "mask_iou": summary([row["iou"] for row in all_rows]),
            "command_abs_px": summary([row["command_abs_px"] for row in all_rows]),
            "command_signed_px": summary([row["command_signed_px"] for row in all_rows]),
            "identity_command_abs_px": summary([row["command_abs_px"] for row in identity_rows]),
            "four_view_signed_command_range_px": summary(exposure_consistency[method]),
        }
    return output


def target_adapter_audit(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[np.ndarray]]:
    configurations = [(gain, margin) for gain in (0.15, 0.30, 0.45, 0.60) for margin in (2.0, 3.0, 4.0)]
    rows: defaultdict[str, list[dict[str, float]]] = defaultdict(list)
    contact_images: list[np.ndarray] = []
    for record_index, record in enumerate(records):
        target = np.load(PACKAGE / record["target"], mmap_mode="r", allow_pickle=False)
        mask = np.load(PACKAGE / record["mask"], mmap_mode="r", allow_pickle=False)
        sdf_q4 = np.load(PACKAGE / record["sdf_q4"], mmap_mode="r", allow_pickle=False)
        y0, x0 = structure_crop(np.asarray(mask), str(record["scene_id"]))
        target_crop = np.asarray(target[y0:y0 + PATCH, x0:x0 + PATCH], dtype=np.float32) / 255.0
        mask_crop = (np.asarray(mask[y0:y0 + PATCH, x0:x0 + PATCH]) >= 128).astype(np.uint8)
        q4_y, q4_x = y0 // 4, x0 // 4
        sdf = cv2.resize(np.asarray(sdf_q4[q4_y:q4_y + PATCH // 4, q4_x:q4_x + PATCH // 4], dtype=np.float32) * 4.0, (PATCH, PATCH), interpolation=cv2.INTER_LINEAR)
        texture = record["texture"]
        fg = float(texture["foreground_mean"])
        bg = float(texture["background_mean"])
        fraction = float(texture["physical_boundary_intensity_fraction"])
        level = (1.0 - fraction) * bg + fraction * fg
        bright = bool(texture["bright_foreground"])
        baseline_mask = (target_crop >= level if bright else target_crop <= level).astype(np.uint8)
        baseline_metrics = mask_metrics(baseline_mask, mask_crop)
        bands = band_stack(target_crop)
        for gain, margin in configurations:
            support = np.clip((np.abs(sdf) - margin) / 3.0, 0.0, 1.0).astype(np.float32)
            addition = np.tensordot(bands, boost_coefficients(gain), axes=([-1], [0]))
            unbounded = target_crop + support * addition
            adapted = np.clip(unbounded, 0.0, 1.0)
            adapted_mask = (adapted >= level if bright else adapted <= level).astype(np.uint8)
            metrics = mask_metrics(adapted_mask, mask_crop)
            away = np.abs(sdf) >= max(margin + 1.0, 4.0)
            rows[f"gain_{gain:.2f}_margin_{margin:.0f}"].append({
                "gain": gain,
                "margin_px": margin,
                "fine_energy_ratio": fine_energy(adapted, away) / max(fine_energy(target_crop, away), 1e-8),
                "iou": metrics["iou"],
                "iou_change_from_target": metrics["iou"] - baseline_metrics["iou"],
                "centroid_change_from_target_px": float(np.linalg.norm(centroid(adapted_mask) - centroid(baseline_mask))),
                "boundary_change_from_target_px": metrics["boundary_distance_px"] - baseline_metrics["boundary_distance_px"],
                "mean_change_gray": float(np.mean(np.abs(adapted - target_crop)) * 255.0),
                "clip_fraction": float(np.mean((unbounded < 0.0) | (unbounded > 1.0))),
            })
            if record_index == 0 and margin == 3.0:
                contact_images.append((np.clip(adapted, 0, 1) * 255).astype(np.uint8))

    configurations_output: dict[str, Any] = {}
    pareto: list[dict[str, Any]] = []
    for name, config_rows in rows.items():
        aggregate = {
            "gain": config_rows[0]["gain"],
            "margin_px": config_rows[0]["margin_px"],
            "fine_energy_ratio": summary([row["fine_energy_ratio"] for row in config_rows]),
            "iou_change_from_target": summary([row["iou_change_from_target"] for row in config_rows]),
            "centroid_change_from_target_px": summary([row["centroid_change_from_target_px"] for row in config_rows]),
            "boundary_change_from_target_px": summary([row["boundary_change_from_target_px"] for row in config_rows]),
            "mean_change_gray": summary([row["mean_change_gray"] for row in config_rows]),
            "clip_fraction": summary([row["clip_fraction"] for row in config_rows]),
        }
        configurations_output[name] = aggregate
        pareto.append({
            "name": name,
            "gain": aggregate["gain"],
            "margin_px": aggregate["margin_px"],
            "fine_energy_ratio_mean": aggregate["fine_energy_ratio"]["mean"],
            "iou_change_mean": aggregate["iou_change_from_target"]["mean"],
            "centroid_change_p95_px": aggregate["centroid_change_from_target_px"]["p95"],
            "clip_fraction_mean": aggregate["clip_fraction"]["mean"],
        })
    # Keep the whole non-dominated set rather than hiding the design tradeoff
    # behind one arbitrary score.
    front: list[dict[str, Any]] = []
    for candidate in pareto:
        dominated = False
        for other in pareto:
            if other is candidate:
                continue
            better_or_equal = (
                other["fine_energy_ratio_mean"] >= candidate["fine_energy_ratio_mean"]
                and other["iou_change_mean"] >= candidate["iou_change_mean"]
                and other["centroid_change_p95_px"] <= candidate["centroid_change_p95_px"]
                and other["clip_fraction_mean"] <= candidate["clip_fraction_mean"]
            )
            strictly_better = any((
                other["fine_energy_ratio_mean"] > candidate["fine_energy_ratio_mean"],
                other["iou_change_mean"] > candidate["iou_change_mean"],
                other["centroid_change_p95_px"] < candidate["centroid_change_p95_px"],
                other["clip_fraction_mean"] < candidate["clip_fraction_mean"],
            ))
            if better_or_equal and strictly_better:
                dominated = True
                break
        if not dominated:
            front.append(candidate)
    front.sort(key=lambda row: (row["gain"], row["margin_px"]))
    return {"configurations": configurations_output, "pareto_front": front}, contact_images


def coefficient_smoothness_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    rng = np.random.default_rng(SEED)
    sigma_values = (0.0, 2.0, 4.0, 8.0, 12.0)
    rows: defaultdict[str, list[dict[str, float]]] = defaultdict(list)
    for record in records[: min(48, len(records))]:
        target = np.load(PACKAGE / record["target"], mmap_mode="r", allow_pickle=False)
        mask = np.load(PACKAGE / record["mask"], mmap_mode="r", allow_pickle=False)
        y0, x0 = structure_crop(np.asarray(mask), str(record["scene_id"]))
        image = np.asarray(target[y0:y0 + PATCH, x0:x0 + PATCH], dtype=np.float32) / 255.0
        truth = (np.asarray(mask[y0:y0 + PATCH, x0:x0 + PATCH]) >= 128).astype(np.uint8)
        texture = record["texture"]
        fg = float(texture["foreground_mean"])
        bg = float(texture["background_mean"])
        fraction = float(texture["physical_boundary_intensity_fraction"])
        level = (1.0 - fraction) * bg + fraction * fg
        bright = bool(texture["bright_foreground"])
        baseline = (image >= level if bright else image <= level).astype(np.uint8)
        coarse = rng.uniform(0.0, 0.60, size=(16, 16)).astype(np.float32)
        gain_map = cv2.resize(coarse, (PATCH, PATCH), interpolation=cv2.INTER_CUBIC)
        bands = band_stack(image)
        basis = bands[..., 0] + 0.70 * bands[..., 1] + 0.20 * bands[..., 2]
        for sigma in sigma_values:
            if sigma > 0:
                radius = int(math.ceil(3.0 * sigma))
                coefficient = gaussian(gain_map, sigma, radius)
            else:
                coefficient = gain_map
            output = np.clip(image + coefficient * basis, 0.0, 1.0)
            candidate = (output >= level if bright else output <= level).astype(np.uint8)
            rows[f"sigma_{sigma:.0f}"].append({
                "centroid_change_px": float(np.linalg.norm(centroid(candidate) - centroid(baseline))),
                "iou_change": mask_metrics(candidate, truth)["iou"] - mask_metrics(baseline, truth)["iou"],
                "fine_energy_ratio": fine_energy(output) / max(fine_energy(image), 1e-8),
                "coefficient_gradient": float(np.mean(cv2.magnitude(cv2.Sobel(coefficient, cv2.CV_32F, 1, 0), cv2.Sobel(coefficient, cv2.CV_32F, 0, 1)))),
            })
    return {
        name: {
            "centroid_change_px": summary([row["centroid_change_px"] for row in config]),
            "iou_change": summary([row["iou_change"] for row in config]),
            "fine_energy_ratio": summary([row["fine_energy_ratio"] for row in config]),
            "coefficient_gradient": summary([row["coefficient_gradient"] for row in config]),
        }
        for name, config in rows.items()
    }


def save_contact(images: list[np.ndarray]) -> None:
    if not images:
        return
    labels = ["gain 0.15", "gain 0.30", "gain 0.45", "gain 0.60"]
    panels = []
    for label, image in zip(labels, images):
        panel = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(panel, (0, 0), (120, 24), (0, 0, 0), -1)
        cv2.putText(panel, label, (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
        panels.append(panel)
    CONTACT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(CONTACT), np.hstack(panels))


def main() -> int:
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    records = select_records(manifest)
    roles = defaultdict(int)
    for record in records:
        roles[str(record["role"])] += 1
    print(f"selected {len(records)} validation scenes: {dict(roles)}", flush=True)
    print("source transport label audit", flush=True)
    transport = source_transport_audit(records)
    print("shape-safe target adapter audit", flush=True)
    adapter, contact = target_adapter_audit(records)
    print("coefficient smoothness audit", flush=True)
    smoothness = coefficient_smoothness_audit(records)
    save_contact(contact)
    payload = {
        "status": "complete",
        "purpose": "falsify R100 architecture assumptions before training",
        "training_started": False,
        "package": str(PACKAGE),
        "dataset_content_sha256": manifest["content_sha256"],
        "scene_count": len(records),
        "role_scene_counts": dict(roles),
        "source_transport_label": transport,
        "shape_safe_target_adapter": adapter,
        "coefficient_smoothness": smoothness,
        "contact_sheet": str(CONTACT),
    }
    json_dump(OUTPUT, payload)
    print(json.dumps({
        "output": str(OUTPUT),
        "transport_median_abs_px": {name: row["command_abs_px"]["median"] for name, row in transport.items()},
        "target_adapter_pareto": adapter["pareto_front"],
        "smoothness_centroid_p95": {name: row["centroid_change_px"]["p95"] for name, row in smoothness.items()},
    }, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
