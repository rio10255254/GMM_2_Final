"""Reusable validation core for R114 controller, renderer, and formal runs."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping
import csv
import hashlib
import json
import math
import time

import cv2
import numpy as np
import torch

import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "inference") not in sys.path:
    sys.path.insert(0, str(ROOT / "inference"))
from tiled_runtime import Prediction, TileConfig, predict, predict_tiled, save_internal_maps, seam_mask


DEFAULT_MAPS = (
    "normalized_sdf",
    "normal_x",
    "normal_y",
    "boundary_confidence",
    "correction_need",
    "recoverability",
    "geometry_gate",
    "detail_gate",
    "width_gain",
    "normal_shift",
)


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"Cannot read image: {path}")
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.dtype == np.uint8:
        return image.astype(np.float32) / 255.0
    if image.dtype == np.uint16:
        return image.astype(np.float32) / 65535.0
    image = image.astype(np.float32)
    maximum = float(np.nanmax(image))
    if maximum > 1.0:
        image /= maximum
    return image


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = np.rint(np.clip(image, 0.0, 1.0) * 255.0).astype(np.uint8)
    encoded = cv2.imencode(path.suffix or ".png", value)[1]
    encoded.tofile(path)


def gradient_magnitude(image: np.ndarray) -> np.ndarray:
    gx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3)
    return np.hypot(gx, gy)


def quantile(values: np.ndarray, fraction: float) -> float:
    return float(np.quantile(values.astype(np.float64), fraction)) if values.size else 0.0


def image_metrics(source: np.ndarray, output: np.ndarray, target: np.ndarray | None) -> dict[str, float]:
    change = output.astype(np.float64) - source.astype(np.float64)
    absolute = np.abs(change)
    source_gradient = gradient_magnitude(source)
    output_gradient = gradient_magnitude(output)
    support = source_gradient >= np.quantile(source_gradient, .75)
    metrics = {
        "mean_signed_change_gray": float(change.mean() * 255.0),
        "mean_abs_change_gray": float(absolute.mean() * 255.0),
        "p95_abs_change_gray": quantile(absolute, .95) * 255.0,
        "max_abs_change_gray": float(absolute.max() * 255.0),
        "output_minimum": float(output.min()),
        "output_maximum": float(output.max()),
        "low_clip_fraction": float((output <= 0.0).mean()),
        "high_clip_fraction": float((output >= 1.0).mean()),
        "edge_gain_on_raw_support": float(output_gradient[support].mean() / max(source_gradient[support].mean(), 1e-9)),
        "off_source_strong_edge_fraction": float(
            ((output_gradient >= np.quantile(output_gradient, .9)) & ~support).mean()
        ),
    }
    if target is not None:
        error = output.astype(np.float64) - target.astype(np.float64)
        mse = float(np.mean(error * error))
        metrics.update({
            "target_mae_gray": float(np.mean(np.abs(error)) * 255.0),
            "target_p95_gray": quantile(np.abs(error), .95) * 255.0,
            "target_psnr_db": float(99.0 if mse <= 1e-12 else 10.0 * math.log10(1.0 / mse)),
        })
    return metrics


def tensor_image(value: torch.Tensor) -> np.ndarray:
    return value.detach().float().cpu().numpy()[0, 0]


def difference_metrics(reference: torch.Tensor, candidate: torch.Tensor, seam: np.ndarray | None) -> dict[str, float]:
    difference = np.abs(tensor_image(reference) - tensor_image(candidate)) * 255.0
    result = {
        "mean_gray": float(difference.mean()),
        "p99_gray": quantile(difference, .99),
        "maximum_gray": float(difference.max()),
    }
    if seam is not None and seam.any():
        result["seam_mean_gray"] = float(difference[seam].mean())
        result["off_seam_mean_gray"] = float(difference[~seam].mean())
    else:
        result["seam_mean_gray"] = 0.0
        result["off_seam_mean_gray"] = float(difference.mean())
    return result


def map_statistics(sample_id: str, family: str, role: str, maps: Mapping[str, torch.Tensor]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, value in sorted(maps.items()):
        array = value.detach().float().cpu().numpy()
        finite = np.isfinite(array)
        rows.append({
            "sample_id": sample_id,
            "family": family,
            "role": role,
            "map": name,
            "finite_fraction": float(finite.mean()),
            "mean": float(np.nanmean(array)) if finite.any() else math.nan,
            "standard_deviation": float(np.nanstd(array)) if finite.any() else math.nan,
            "p05": float(np.nanquantile(array, .05)) if finite.any() else math.nan,
            "p95": float(np.nanquantile(array, .95)) if finite.any() else math.nan,
            "minimum": float(np.nanmin(array)) if finite.any() else math.nan,
            "maximum": float(np.nanmax(array)) if finite.any() else math.nan,
        })
    return rows


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def aggregate(rows: list[dict[str, Any]], keys: tuple[str, ...], numeric_fields: list[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    summaries: list[dict[str, Any]] = []
    for identity, members in sorted(groups.items(), key=lambda item: tuple(str(value) for value in item[0])):
        summary = {key: value for key, value in zip(keys, identity)}
        summary["samples"] = len(members)
        for field in numeric_fields:
            values = np.asarray([float(row[field]) for row in members if field in row and np.isfinite(float(row[field]))])
            if not values.size:
                continue
            summary[f"{field}_median"] = float(np.median(values))
            summary[f"{field}_p95"] = float(np.quantile(values, .95))
            summary[f"{field}_worst"] = float(np.max(values))
        summaries.append(summary)
    return summaries


def resolve_record_paths(records: list[dict[str, Any]], base: Path) -> list[dict[str, Any]]:
    result = []
    for item in records:
        row = dict(item)
        for key in ("source", "target"):
            if row.get(key):
                path = Path(row[key])
                row[key] = str(path if path.is_absolute() else (base / path).resolve())
        result.append(row)
    return result


@torch.inference_mode()
def run_validation(
    model: torch.nn.Module,
    records: list[dict[str, Any]],
    output_dir: Path,
    device: torch.device,
    tile_configs: list[TileConfig],
    required_maps: tuple[str, ...] = DEFAULT_MAPS,
    thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Execute the common finite/identity/family/tile/internal-map audit."""
    thresholds = dict(thresholds or {})
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    model = model.to(device).eval()
    per_sample: list[dict[str, Any]] = []
    parity_rows: list[dict[str, Any]] = []
    map_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    observed_maps: set[str] = set()

    for index, record in enumerate(records, 1):
        sample_id = str(record.get("id", f"sample_{index:04d}"))
        family = str(record.get("family", "unknown"))
        role = str(record.get("role", "degraded"))
        source_path = Path(record["source"])
        target_path = Path(record["target"]) if record.get("target") else None
        source = read_gray(source_path)
        target = read_gray(target_path) if target_path else None
        if target is not None and target.shape != source.shape:
            raise ValueError(f"Target shape mismatch for {sample_id}")
        tensor = torch.from_numpy(source)[None, None].to(device)
        if not tile_configs:
            raise ValueError("At least one deployment tile configuration is required")
        # The deployed tiled boundary policy is the canonical output.  A raw
        # whole-image forward applies reflect padding independently at every
        # layer, which is mathematically different only at the outer image
        # border from the one-time outer padding used by all tiled grids.
        # Comparing tile grids against the first deployment grid tests seams
        # and origin invariance without conflating those border conventions.
        tiled_predictions = {config.name: predict_tiled(model, tensor, config) for config in tile_configs}
        canonical_config = tile_configs[0]
        full = tiled_predictions[canonical_config.name]
        full_array = tensor_image(full.output)
        finite = bool(torch.isfinite(full.output).all()) and all(bool(torch.isfinite(value).all()) for value in full.maps.values())
        if not finite:
            failures.append(f"{sample_id}: non-finite canonical tiled prediction")
        observed_maps.update(full.maps)
        row: dict[str, Any] = {
            "sample_id": sample_id,
            "family": family,
            "role": role,
            "source": str(source_path),
            "source_sha256": sha256(source_path),
            "finite": finite,
            **image_metrics(source, full_array, target),
        }
        per_sample.append(row)
        write_gray(output_dir / "images" / f"{sample_id}_output.png", full_array)
        write_gray(output_dir / "images" / f"{sample_id}_abs_diff_x8.png", np.clip(np.abs(full_array - source) * 8.0, 0.0, 1.0))
        save_internal_maps(output_dir / "internal_maps" / sample_id, full.maps)
        map_rows.extend(map_statistics(sample_id, family, role, full.maps))

        tiled_results: dict[str, torch.Tensor] = {}
        for config in tile_configs:
            tiled = tiled_predictions[config.name]
            tiled_results[config.name] = tiled.output
            if not bool(torch.isfinite(tiled.output).all()):
                failures.append(f"{sample_id}/{config.name}: non-finite tiled prediction")
            difference = difference_metrics(full.output, tiled.output, seam_mask(source.shape[0], source.shape[1], config))
            parity_rows.append({
                "sample_id": sample_id,
                "family": family,
                "comparison": f"canonical_{canonical_config.name}_vs_{config.name}",
                "core": config.core,
                "halo": config.halo,
                "overlap": config.overlap,
                "origin_y": config.origin_y,
                "origin_x": config.origin_x,
                "tile_count": tiled.tile_count,
                "coverage_minimum": float(tiled.coverage.min()),
                "coverage_maximum": float(tiled.coverage.max()),
                **difference,
            })
        names = list(tiled_results)
        for first_index, first_name in enumerate(names):
            for second_name in names[first_index + 1 :]:
                parity_rows.append({
                    "sample_id": sample_id,
                    "family": family,
                    "comparison": f"{first_name}_vs_{second_name}",
                    **difference_metrics(tiled_results[first_name], tiled_results[second_name], None),
                })
        atomic_json(output_dir / "progress.json", {
            "status": "running",
            "completed": index,
            "total": len(records),
            "sample_id": sample_id,
            "elapsed_seconds": time.perf_counter() - started,
        })

    missing_maps = sorted(set(required_maps) - observed_maps)
    if missing_maps:
        failures.append(f"Missing required internal maps: {missing_maps}")
    for map_row in map_rows:
        if map_row["finite_fraction"] < 1.0:
            failures.append(f"{map_row['sample_id']}/{map_row['map']}: non-finite internal map")

    identity_rows = [row for row in per_sample if row["role"] in {"clear", "identity", "flat"}]
    family_fields = [
        "mean_abs_change_gray", "p95_abs_change_gray", "max_abs_change_gray",
        "target_mae_gray", "target_p95_gray", "off_source_strong_edge_fraction",
    ]
    family_summary = aggregate(per_sample, ("family", "role"), family_fields)
    parity_summary = aggregate(parity_rows, ("comparison",), ["mean_gray", "p99_gray", "maximum_gray", "seam_mean_gray"])
    write_csv(output_dir / "tables" / "per_sample_metrics.csv", per_sample)
    write_csv(output_dir / "tables" / "family_metrics.csv", family_summary)
    write_csv(output_dir / "tables" / "identity_metrics.csv", identity_rows)
    write_csv(output_dir / "tables" / "tile_parity.csv", parity_rows)
    write_csv(output_dir / "tables" / "tile_parity_summary.csv", parity_summary)
    write_csv(output_dir / "tables" / "internal_map_stats.csv", map_rows)

    maximum_identity = max((float(row["mean_abs_change_gray"]) for row in identity_rows), default=0.0)
    maximum_parity_mean = max((float(row["mean_gray"]) for row in parity_rows), default=math.inf)
    maximum_parity_p99 = max((float(row["p99_gray"]) for row in parity_rows), default=math.inf)
    maximum_parity_absolute = max((float(row["maximum_gray"]) for row in parity_rows), default=math.inf)
    checks = {
        "records_present": bool(records),
        "all_outputs_finite": all(bool(row["finite"]) for row in per_sample),
        "required_internal_maps_present": not missing_maps,
        "all_internal_maps_finite": all(float(row["finite_fraction"]) == 1.0 for row in map_rows),
        "identity_samples_present": bool(identity_rows),
        "family_breakdown_present": len(family_summary) >= len({row["family"] for row in per_sample}),
        "multiple_tile_grids_exercised": len(tile_configs) >= 3 and len({(item.core, item.halo) for item in tile_configs}) >= 2,
        "shifted_tile_origin_exercised": any(item.origin_x or item.origin_y for item in tile_configs),
        "overlap_exercised": any(item.overlap for item in tile_configs),
        "tile_coverage_complete": all(float(row.get("coverage_minimum", 1.0)) >= 1.0 for row in parity_rows),
    }
    if "max_identity_mae_gray" in thresholds:
        checks["identity_within_configured_limit"] = maximum_identity <= float(thresholds["max_identity_mae_gray"])
    if "max_tile_mean_gray" in thresholds:
        checks["tile_mean_within_configured_limit"] = maximum_parity_mean <= float(thresholds["max_tile_mean_gray"])
    if "max_tile_p99_gray" in thresholds:
        checks["tile_p99_within_configured_limit"] = maximum_parity_p99 <= float(thresholds["max_tile_p99_gray"])
    if "max_tile_absolute_gray" in thresholds:
        checks["tile_absolute_within_configured_limit"] = maximum_parity_absolute <= float(thresholds["max_tile_absolute_gray"])
    failures.extend(name for name, passed in checks.items() if not passed and name not in failures)
    summary = {
        "status": "complete" if not failures else "failed",
        "samples": len(per_sample),
        "families": sorted({row["family"] for row in per_sample}),
        "roles": sorted({row["role"] for row in per_sample}),
        "observed_internal_maps": sorted(observed_maps),
        "missing_internal_maps": missing_maps,
        "maximum_identity_mae_gray": maximum_identity,
        "maximum_tile_mean_gray": maximum_parity_mean,
        "maximum_tile_p99_gray": maximum_parity_p99,
        "maximum_tile_absolute_gray": maximum_parity_absolute,
        "tile_configs": [vars(item) for item in tile_configs],
        "checks": checks,
        "failures": failures,
        "elapsed_seconds": time.perf_counter() - started,
    }
    atomic_json(output_dir / "summary.json", summary)
    atomic_json(output_dir / "progress.json", {**summary, "status": summary["status"]})
    return summary
