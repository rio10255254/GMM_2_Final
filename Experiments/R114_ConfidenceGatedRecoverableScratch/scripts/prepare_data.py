"""Prepare R114 data without modifying or copying the verified base package.

The default mode is a safe dry run.  It creates a full logical plan and batch
schedules, but materializes only a few supplemental examples.  The formal
supplemental arrays are generated only when --mode materialize is requested.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CONTRACT_PATH = DATA / "data_contract.json"
DYNAMIC_PATH = DATA / "dynamic_domains.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def atomic_json(path: Path, payload: Any) -> None:
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    atomic_bytes(path, encoded)


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    encoded = "".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows).encode("utf-8")
    atomic_bytes(path, encoded)


def save_npy_idempotent(path: Path, array: np.ndarray, replace_generated: bool = False) -> None:
    buffer = io.BytesIO()
    np.save(buffer, array, allow_pickle=False)
    payload = buffer.getvalue()
    if path.exists():
        existing = path.read_bytes()
        if hashlib.sha256(existing).digest() != hashlib.sha256(payload).digest():
            if replace_generated:
                resolved = path.resolve()
                allowed = (DATA / "supplemental_targets").resolve()
                if allowed not in resolved.parents:
                    raise RuntimeError(f"Refusing out-of-supplemental repair: {path}")
                atomic_bytes(path, payload)
                return
            raise RuntimeError(f"Refusing to overwrite a different existing array: {path}")
        return
    atomic_bytes(path, payload)


def save_image_idempotent(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise RuntimeError(f"Could not encode {path}")
    payload = encoded.tobytes()
    if path.exists() and path.read_bytes() != payload:
        raise RuntimeError(f"Refusing to overwrite a different existing image: {path}")
    if not path.exists():
        atomic_bytes(path, payload)


def normalize_scene_weights(weights: np.ndarray, epsilon: float = 1e-6) -> np.ndarray:
    """Normalize every scene independently; zero-weight scenes remain zero."""
    values = np.asarray(weights, dtype=np.float32)
    if values.ndim < 2:
        raise ValueError("Expected a scene axis followed by one or more spatial axes")
    spatial_axes = tuple(range(1, values.ndim))
    denominator = values.sum(axis=spatial_axes, keepdims=True)
    return values / np.maximum(denominator, float(epsilon))


def polygon_points(center: tuple[float, float], radii: np.ndarray, angles: np.ndarray) -> np.ndarray:
    return np.stack(
        [center[0] + radii * np.cos(angles), center[1] + radii * np.sin(angles)], axis=1
    ).round().astype(np.int32)


def rotated_rectangle(center: tuple[float, float], size: tuple[float, float], angle_deg: float) -> np.ndarray:
    return cv2.boxPoints((center, size, angle_deg)).round().astype(np.int32)


def draw_supplemental_mask(
    size: int, factor: int, family: str, rng: np.random.Generator, family_cfg: dict[str, Any]
) -> np.ndarray:
    high = int(size * factor)
    mask = np.zeros((high, high), dtype=np.uint8)
    cfg = family_cfg[family]
    cx = cy = high * 0.5

    if family == "close_pair":
        radius = float(rng.uniform(*cfg["component_radius"])) * factor
        gap = float(rng.uniform(*cfg["boundary_gap"])) * factor
        distance = 2.0 * radius + gap
        angle = float(rng.uniform(0.0, math.pi))
        dx, dy = math.cos(angle) * distance * 0.5, math.sin(angle) * distance * 0.5
        extent = radius + distance * 0.5
        if extent > high * 0.44:
            scale = high * 0.44 / extent
            radius *= scale
            distance = 2.0 * radius + gap
            dx, dy = math.cos(angle) * distance * 0.5, math.sin(angle) * distance * 0.5
        cv2.circle(mask, (round(cx - dx), round(cy - dy)), max(2, round(radius)), 255, -1, cv2.LINE_AA)
        cv2.circle(mask, (round(cx + dx), round(cy + dy)), max(2, round(radius)), 255, -1, cv2.LINE_AA)

    elif family == "narrow_gap":
        thickness = float(rng.uniform(*cfg["bar_thickness"])) * factor
        gap = float(rng.uniform(*cfg["gap"])) * factor
        length = float(rng.uniform(*cfg["length"])) * factor
        total_extent = math.hypot(length, 2.0 * thickness + gap)
        if total_extent > high * 0.88:
            scale = high * 0.88 / total_extent
            thickness *= scale
            length *= scale
        angle = float(rng.uniform(-75.0, 75.0))
        normal = math.radians(angle + 90.0)
        offset = 0.5 * (thickness + gap)
        dx, dy = math.cos(normal) * offset, math.sin(normal) * offset
        for sign in (-1.0, 1.0):
            center = (cx + sign * dx, cy + sign * dy)
            cv2.fillConvexPoly(mask, rotated_rectangle(center, (length, thickness), angle), 255, cv2.LINE_AA)

    elif family == "micro_notch":
        radius = float(rng.uniform(*cfg["base_radius"])) * factor
        angle = float(rng.uniform(0.0, 2.0 * math.pi))
        cv2.circle(mask, (round(cx), round(cy)), max(3, round(radius)), 255, -1, cv2.LINE_AA)
        depth = float(rng.uniform(*cfg["notch_depth"])) * factor
        width = float(rng.uniform(*cfg["notch_width"])) * factor
        tangent_deg = math.degrees(angle) + 90.0
        notch_center = (
            cx + math.cos(angle) * (radius - depth * 0.35),
            cy + math.sin(angle) * (radius - depth * 0.35),
        )
        notch_length = depth * 1.7 + 2.0 * factor
        cv2.fillConvexPoly(
            mask,
            rotated_rectangle(notch_center, (width, notch_length), tangent_deg),
            0,
            cv2.LINE_AA,
        )

    elif family == "rough_fourier":
        radius = float(rng.uniform(*cfg["base_radius"])) * factor
        samples = 1440
        angles = np.linspace(0.0, 2.0 * math.pi, samples, endpoint=False, dtype=np.float32)
        modes = int(rng.integers(int(cfg["modes"][0]), int(cfg["modes"][1]) + 1))
        selected = rng.choice(np.arange(2, int(cfg["modes"][1]) + 1), size=max(3, modes // 2), replace=False)
        rough = np.zeros_like(angles)
        for mode in selected:
            amplitude = float(rng.uniform(*cfg["relative_amplitude"])) / math.sqrt(len(selected))
            rough += amplitude * np.cos(float(mode) * angles + float(rng.uniform(-math.pi, math.pi)))
        rough = np.clip(rough, -0.26, 0.26)
        radii = radius * (1.0 + rough)
        center = (cx + float(rng.uniform(-0.04, 0.04) * high), cy + float(rng.uniform(-0.04, 0.04) * high))
        cv2.fillPoly(mask, [polygon_points(center, radii, angles)], 255, cv2.LINE_AA)

    elif family == "ultra_thin_ring":
        outer = float(rng.uniform(*cfg["outer_radius"])) * factor
        thickness = float(rng.uniform(*cfg["ring_thickness"])) * factor
        center = (
            cx + float(rng.uniform(-0.08, 0.08) * high),
            cy + float(rng.uniform(-0.08, 0.08) * high),
        )
        cv2.circle(mask, (round(center[0]), round(center[1])), max(4, round(outer)), 255, -1, cv2.LINE_AA)
        cv2.circle(
            mask,
            (round(center[0]), round(center[1])),
            max(1, round(outer - thickness)),
            0,
            -1,
            cv2.LINE_AA,
        )
    else:
        raise ValueError(f"Unknown supplemental family: {family}")

    if int((mask >= 128).sum()) == 0:
        raise RuntimeError(f"Generated an empty {family} mask")
    if np.any(mask[0] >= 128) or np.any(mask[-1] >= 128) or np.any(mask[:, 0] >= 128) or np.any(mask[:, -1] >= 128):
        raise RuntimeError(f"Generated a cropped {family} mask")
    return mask


def analytic_texture(size: int, rng: np.random.Generator) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    texture = np.zeros((size, size), dtype=np.float32)
    for _ in range(int(rng.integers(3, 7))):
        angle = float(rng.uniform(0.0, math.pi))
        period = float(np.exp(rng.uniform(np.log(2.8), np.log(28.0))))
        phase = float(rng.uniform(-math.pi, math.pi))
        coordinate = xx * math.cos(angle) + yy * math.sin(angle)
        texture += float(rng.uniform(0.25, 1.0)) * np.sin(2.0 * math.pi * coordinate / period + phase)
    texture -= float(texture.mean())
    scale = float(np.percentile(np.abs(texture), 99.0))
    return np.clip(texture / max(scale, 1e-6), -1.0, 1.0)


def shared_photometry(image: np.ndarray, rng: np.random.Generator, cfg: dict[str, Any]) -> np.ndarray:
    gamma = float(rng.uniform(*cfg["shared_gamma"]))
    contrast = float(rng.uniform(*cfg["shared_contrast"]))
    amplitude = float(rng.uniform(*cfg["shared_illumination_amplitude"]))
    result = np.power(np.clip(image, 0.0, 1.0), gamma).astype(np.float32)
    midpoint = float(np.median(result))
    result = midpoint + contrast * (result - midpoint)
    if amplitude > 0.0:
        yy, xx = np.mgrid[0:image.shape[0], 0:image.shape[1]].astype(np.float32)
        xx = (xx + 0.5) / image.shape[1] - 0.5
        yy = (yy + 0.5) / image.shape[0] - 0.5
        angle = float(rng.uniform(0.0, 2.0 * math.pi))
        result *= 1.0 + 2.0 * amplitude * (math.cos(angle) * xx + math.sin(angle) * yy)
    return np.clip(result, 0.0, 1.0).astype(np.float32)


def seed_for(contract: dict[str, Any], split: str, family_index: int, sample_index: int) -> int:
    split_offset = 0 if split == "train" else 1_000_000_007
    return int(contract["supplemental"]["seed"]) + split_offset + family_index * 1_000_003 + sample_index * 104_729


def supplemental_role(family: str, sample_index: int) -> str:
    return "textured_edge" if family == "rough_fourier" or sample_index % 4 == 0 else "edge"


def generate_supplemental(
    contract: dict[str, Any], split: str, family: str, family_index: int, sample_index: int
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    supplemental = contract["supplemental"]
    size = int(supplemental["canvas_size"])
    factor = int(supplemental["supersample_factor"])
    seed = seed_for(contract, split, family_index, sample_index)
    rng = np.random.default_rng(seed)
    high_mask = draw_supplemental_mask(
        size, factor, family, rng, supplemental["family_parameters_px_at_final_resolution"]
    )
    binary = (high_mask >= 128).astype(np.uint8)
    inside_distance = cv2.distanceTransform(binary, cv2.DIST_L2, cv2.DIST_MASK_5)
    outside_distance = cv2.distanceTransform(1 - binary, cv2.DIST_L2, cv2.DIST_MASK_5)
    sdf_high = inside_distance - outside_distance
    target_cfg = supplemental["target"]
    width = float(rng.uniform(*target_cfg["transition_width_px"]))
    polarity = 1.0 if rng.random() < 0.5 else -1.0
    outside = float(rng.uniform(0.10, 0.42))
    contrast = float(rng.uniform(*target_cfg["contrast"]))
    inside = float(np.clip(outside + polarity * contrast, 0.03, 0.97))
    probability = 1.0 / (1.0 + np.exp(-np.clip(sdf_high / (width * factor), -40.0, 40.0)))
    target_high = outside + (inside - outside) * probability
    role = supplemental_role(family, sample_index)
    if role == "textured_edge":
        texture = analytic_texture(size, rng)
        texture_high = cv2.resize(texture, (size * factor, size * factor), interpolation=cv2.INTER_CUBIC)
        modulation = 0.18 + 0.82 * (high_mask.astype(np.float32) / 255.0)
        amplitude = float(rng.uniform(*target_cfg["texture_amplitude"]))
        target_high += amplitude * texture_high * modulation
    target = cv2.resize(target_high.astype(np.float32), (size, size), interpolation=cv2.INTER_AREA)
    target = shared_photometry(target, rng, target_cfg)
    coverage = cv2.resize(high_mask.astype(np.float32) / 255.0, (size, size), interpolation=cv2.INTER_AREA)
    mask = np.round(np.clip(coverage, 0.0, 1.0) * 255.0).astype(np.uint8)
    # Recompute the final signed distance from the antialiased, downsampled
    # coverage.  Directly averaging a very thin high-resolution SDF can move
    # its zero crossing away from the 0.5 mask crossing for sub-pixel rings.
    # Keeping the high-resolution target/mask and rebuilding only the final
    # distance magnitude preserves antialiasing while making the sign exact.
    final_binary = (mask >= 128).astype(np.uint8)
    inside_distance = cv2.distanceTransform(final_binary, cv2.DIST_L2, 5)
    outside_distance = cv2.distanceTransform(1 - final_binary, cv2.DIST_L2, 5)
    sdf = (inside_distance - outside_distance).astype(np.float32)
    foreground = target[coverage >= 0.5]
    background = target[coverage < 0.5]
    midpoint = float(0.5 * (foreground.mean() + background.mean())) if foreground.size and background.size else float(np.median(target))
    record_id = f"r114_{split}_{family}_{sample_index:04d}"
    record = {
        "record_id": record_id,
        "scene_id": record_id,
        "split": split,
        "role": role,
        "family": family,
        "target_width_px": width,
        "midpoint": midpoint,
        "polarity": polarity,
        "seed": seed,
        "label_supersample_factor": factor,
    }
    arrays = {
        "target": np.round(np.clip(target, 0.0, 1.0) * 255.0).astype(np.uint8),
        "mask": mask,
        "sdf": sdf.astype(np.float16),
    }
    return record, arrays


def source_inventory(contract: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], Path]:
    source_cfg = contract["source"]
    canonical = Path(source_cfg["canonical_package"])
    equivalent = Path(source_cfg["equivalent_r109_package"])
    canonical_manifest_path = canonical / "manifest.json"
    equivalent_manifest_path = equivalent / "manifest.json"
    canonical_hash = sha256_file(canonical_manifest_path)
    equivalent_hash = sha256_file(equivalent_manifest_path)
    expected_hash = str(source_cfg["manifest_sha256"]).lower()
    if canonical_hash != expected_hash or equivalent_hash != expected_hash:
        raise RuntimeError("Verified source manifest hash changed; refusing to prepare R114 data")
    manifest = read_json(canonical_manifest_path)
    if len(manifest["records"]) != int(source_cfg["expected_records"]):
        raise RuntimeError("Unexpected source record count")
    missing: list[str] = []
    for record in manifest["records"]:
        for key in ("target", "mask", "sdf"):
            if not (canonical / record[key]).is_file():
                missing.append(f"{record['scene_id']}:{key}")
                if len(missing) >= 20:
                    break
        if len(missing) >= 20:
            break
    if missing:
        raise RuntimeError(f"Missing source arrays: {missing}")

    def describe(package: Path) -> dict[str, Any]:
        files = [path for path in package.rglob("*") if path.is_file()]
        return {
            "path": package.as_posix(),
            "files": len(files),
            "bytes": int(sum(path.stat().st_size for path in files)),
            "manifest_sha256": sha256_file(package / "manifest.json"),
        }

    generator = canonical.parent / "prepare_dataset.py"
    inventory = {
        "status": "verified_immutable_reference",
        "canonical": describe(canonical),
        "equivalent_r109_copy": describe(equivalent),
        "generator": {
            "path": generator.as_posix(),
            "sha256": sha256_file(generator),
            "label_supersample_factor": int(manifest["supersample_factor"]),
        },
        "counts": manifest["counts"],
        "records": len(manifest["records"]),
        "families": dict(sorted(collections.Counter(row["family"] for row in manifest["records"]).items())),
        "roles": dict(sorted(collections.Counter(row["role"] for row in manifest["records"]).items())),
        "array_references_checked": len(manifest["records"]) * 3,
        "missing_array_references": 0,
        "source_arrays_copied_into_r114": False,
    }
    return inventory, manifest, canonical


def choose_replacements(
    contract: dict[str, Any], base_records: list[dict[str, Any]]
) -> tuple[set[str], dict[str, Any]]:
    preserve = set(contract["replacement"]["preserve_roles"])
    removed: set[str] = set()
    breakdown: dict[str, Any] = {}
    for split in ("train", "validation"):
        split_breakdown: dict[str, int] = {}
        for family, count_value in contract["replacement"][split].items():
            count = int(count_value)
            candidates = [
                row
                for row in base_records
                if row["split"] == split
                and row["family"] == family
                and row["role"] not in preserve
                and row["scene_id"] not in removed
            ]
            if len(candidates) < count:
                raise RuntimeError(f"Not enough replaceable {split}/{family} records")
            salt = int(hashlib.sha256(f"{split}:{family}".encode()).hexdigest()[:8], 16)
            rng = np.random.default_rng(int(contract["supplemental"]["seed"]) + salt)
            order = rng.permutation(len(candidates))[:count]
            selected = [candidates[int(index)] for index in order]
            removed.update(row["scene_id"] for row in selected)
            split_breakdown[family] = len(selected)
        breakdown[split] = split_breakdown
    return removed, breakdown


def base_logical_record(row: dict[str, Any], source_root: Path, source_hash: str) -> dict[str, Any]:
    return {
        "record_id": row["scene_id"],
        "scene_id": row["scene_id"],
        "source_scene_index": int(row["scene_index"]),
        "split": row["split"],
        "role": row["role"],
        "family": row["family"],
        "artifact_root": source_root.as_posix(),
        "target": row["target"],
        "mask": row["mask"],
        "sdf": row["sdf"],
        "target_width_px": float(row["target_width_px"]),
        "midpoint": float(row["midpoint"]),
        "polarity": float(row["polarity"]),
        "seed": int(row["seed"]),
        "storage": "referenced_immutable",
        "source_manifest_sha256": source_hash,
        "scene_loss_scale": 1.0,
        "edge_weight_normalization": "per_scene_sum_one",
    }


def planned_supplemental_records(contract: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    families = contract["supplemental"]["families"]
    counts = contract["supplemental"]["formal_count_per_family"]
    factor = int(contract["supplemental"]["supersample_factor"])
    for split in ("train", "validation"):
        for family_index, family in enumerate(families):
            for sample_index in range(int(counts[split])):
                record_id = f"r114_{split}_{family}_{sample_index:04d}"
                rows.append(
                    {
                        "record_id": record_id,
                        "scene_id": record_id,
                        "split": split,
                        "role": supplemental_role(family, sample_index),
                        "family": family,
                        "artifact_root": root.as_posix(),
                        "target": f"targets/{record_id}.npy",
                        "mask": f"masks/{record_id}.npy",
                        "sdf": f"sdf/{record_id}.npy",
                        "seed": seed_for(contract, split, family_index, sample_index),
                        "label_supersample_factor": factor,
                        "storage": "planned_supplemental_not_materialized",
                        "metadata_state": "deterministic_pending_materialization",
                        "scene_loss_scale": 1.0,
                        "edge_weight_normalization": "per_scene_sum_one",
                    }
                )
    return rows


def classify_bucket(row: dict[str, Any], hard_families: set[str]) -> str:
    if row["family"] == "dense_array":
        return "dense_array"
    if row["role"] == "identity":
        return "identity"
    if row["role"] == "flat_negative":
        return "flat_negative"
    if row["family"] in hard_families:
        return "hard_geometry"
    if row["role"] == "textured_edge":
        return "textured"
    return "general_geometry"


def batch_stats(batch: list[dict[str, Any]], hard_families: set[str]) -> dict[str, Any]:
    bucket_counts = collections.Counter(classify_bucket(row, hard_families) for row in batch)
    return {
        "dense_count": sum(row["family"] == "dense_array" for row in batch),
        "identity_count": sum(row["role"] == "identity" for row in batch),
        "flat_negative_count": sum(row["role"] == "flat_negative" for row in batch),
        "bucket_counts": dict(sorted(bucket_counts.items())),
    }


def make_batch_schedule(
    records: list[dict[str, Any]], split: str, batch_size: int, contract: dict[str, Any], seed: int
) -> list[dict[str, Any]]:
    selected = [row for row in records if row["split"] == split]
    count = len(selected)
    number_of_batches = math.ceil(count / batch_size)
    capacities = [batch_size] * number_of_batches
    capacities[-1] = count - batch_size * (number_of_batches - 1)
    cfg = contract["batch_contract"]
    dense_max = int(cfg["dense_array_max_per_batch"])
    identity_min = int(cfg["identity_min_per_batch"])
    identity_max = int(cfg["identity_max_per_batch"])
    hard_families = set(cfg["hard_families"])
    rng = np.random.default_rng(seed)
    batches: list[list[dict[str, Any]]] = [[] for _ in range(number_of_batches)]
    assigned: set[str] = set()

    def place(batch_index: int, row: dict[str, Any]) -> None:
        if len(batches[batch_index]) >= capacities[batch_index]:
            raise RuntimeError("Batch capacity overflow")
        batches[batch_index].append(row)
        assigned.add(row["record_id"])

    dense = [row for row in selected if row["family"] == "dense_array"]
    if len(dense) > number_of_batches * dense_max:
        raise RuntimeError(
            f"{split} has {len(dense)} dense records but only {number_of_batches} batches; replacement quota is insufficient"
        )
    dense_order = [dense[int(index)] for index in rng.permutation(len(dense))]
    batch_order = [int(index) for index in rng.permutation(number_of_batches)]
    for row, batch_index in zip(dense_order, batch_order):
        place(batch_index, row)

    identity = [row for row in selected if row["role"] == "identity" and row["record_id"] not in assigned]
    identity = [identity[int(index)] for index in rng.permutation(len(identity))]
    identity_cursor = 0
    for batch_index in range(number_of_batches):
        current = sum(row["role"] == "identity" for row in batches[batch_index])
        while current < identity_min:
            if identity_cursor >= len(identity):
                raise RuntimeError(f"Not enough {split} identity records for one per batch")
            place(batch_index, identity[identity_cursor])
            identity_cursor += 1
            current += 1
    while identity_cursor < len(identity):
        candidates = [
            index
            for index, batch in enumerate(batches)
            if len(batch) < capacities[index]
            and sum(row["role"] == "identity" for row in batch) < identity_max
        ]
        if not candidates:
            raise RuntimeError(f"Too many {split} identity records for the configured maximum")
        minimum_length = min(len(batches[index]) for index in candidates)
        candidates = [index for index in candidates if len(batches[index]) == minimum_length]
        place(int(rng.choice(candidates)), identity[identity_cursor])
        identity_cursor += 1

    remaining = [row for row in selected if row["record_id"] not in assigned]
    pools: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in remaining:
        pools[classify_bucket(row, hard_families)].append(row)
    order = ["flat_negative", "hard_geometry", "textured", "general_geometry"]
    for category in order:
        pool = pools.pop(category, [])
        if pool:
            pool = [pool[int(index)] for index in rng.permutation(len(pool))]
        for row in pool:
            candidates = [index for index, batch in enumerate(batches) if len(batch) < capacities[index]]
            category_counts = {
                index: sum(classify_bucket(item, hard_families) == category for item in batches[index])
                for index in candidates
            }
            minimum_category = min(category_counts.values())
            candidates = [index for index in candidates if category_counts[index] == minimum_category]
            minimum_length = min(len(batches[index]) for index in candidates)
            candidates = [index for index in candidates if len(batches[index]) == minimum_length]
            place(int(rng.choice(candidates)), row)
    if pools:
        raise RuntimeError(f"Unhandled batch buckets: {sorted(pools)}")

    schedule: list[dict[str, Any]] = []
    for batch_index, batch in enumerate(batches):
        shuffled = [batch[int(index)] for index in rng.permutation(len(batch))]
        stats = batch_stats(shuffled, hard_families)
        schedule.append(
            {
                "batch_index": batch_index,
                "split": split,
                "configured_batch_size": batch_size,
                "actual_batch_size": len(shuffled),
                "record_ids": [row["record_id"] for row in shuffled],
                "families": [row["family"] for row in shuffled],
                "roles": [row["role"] for row in shuffled],
                **stats,
                "loss_reduction": "normalize_each_scene_then_mean_batch",
            }
        )
    validate_batch_schedule(schedule, selected, contract)
    return schedule


def validate_batch_schedule(
    schedule: list[dict[str, Any]], records: list[dict[str, Any]], contract: dict[str, Any]
) -> None:
    cfg = contract["batch_contract"]
    identifiers = [identifier for batch in schedule for identifier in batch["record_ids"]]
    expected = {row["record_id"] for row in records}
    if len(identifiers) != len(expected) or set(identifiers) != expected:
        raise RuntimeError("Batch schedule does not contain every scene exactly once")
    if len(identifiers) != len(set(identifiers)):
        raise RuntimeError("Batch schedule contains duplicate scenes")
    for batch in schedule:
        if int(batch["dense_count"]) > int(cfg["dense_array_max_per_batch"]):
            raise RuntimeError("Dense-array batch quota violated")
        if not int(cfg["identity_min_per_batch"]) <= int(batch["identity_count"]) <= int(cfg["identity_max_per_batch"]):
            raise RuntimeError("Identity batch quota violated")


def build_logical_plan(
    contract: dict[str, Any], source_manifest: dict[str, Any], source_root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    removed, removal_breakdown = choose_replacements(contract, source_manifest["records"])
    source_hash = str(contract["source"]["manifest_sha256"]).lower()
    base = [
        base_logical_record(row, source_root, source_hash)
        for row in source_manifest["records"]
        if row["scene_id"] not in removed
    ]
    supplemental_root = DATA / "supplemental_targets"
    supplemental = planned_supplemental_records(contract, supplemental_root)
    logical = base + supplemental
    logical.sort(key=lambda row: (0 if row["split"] == "train" else 1, row["record_id"]))
    for logical_index, row in enumerate(logical):
        row["logical_index"] = logical_index
    counts = collections.Counter(row["split"] for row in logical)
    if dict(counts) != contract["target_counts"]:
        raise RuntimeError(f"Logical counts changed: {dict(counts)}")
    replacement_total = {split: sum(values.values()) for split, values in removal_breakdown.items()}
    supplemental_total = {
        split: len([row for row in supplemental if row["split"] == split]) for split in ("train", "validation")
    }
    if replacement_total != supplemental_total:
        raise RuntimeError("Replacement and supplemental counts do not balance")
    summary = {
        "counts": dict(counts),
        "records": len(logical),
        "base_references": len(base),
        "planned_supplemental": len(supplemental),
        "removed_source_records": len(removed),
        "replacement_breakdown": removal_breakdown,
        "family_counts": {
            split: dict(sorted(collections.Counter(row["family"] for row in logical if row["split"] == split).items()))
            for split in ("train", "validation")
        },
        "role_counts": {
            split: dict(sorted(collections.Counter(row["role"] for row in logical if row["split"] == split).items()))
            for split in ("train", "validation")
        },
    }
    plan = {
        "schema_version": 1,
        "status": "planned_not_materialized",
        "source_manifest": (source_root / "manifest.json").as_posix(),
        "source_manifest_sha256": source_hash,
        "source_is_immutable": True,
        "base_arrays_are_referenced_not_copied": True,
        "loss_contract": contract["loss_contract"],
        "summary": summary,
        "removed_source_record_ids": sorted(removed),
        "records": logical,
    }
    return plan, summary


def write_batch_schedules(plan: dict[str, Any], contract: dict[str, Any], prefix: str = "planned") -> dict[str, Any]:
    output = DATA / "batches"
    output.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {}
    for split_index, split in enumerate(("train", "validation")):
        split_records = [row for row in plan["records"] if row["split"] == split]
        for batch_size in contract["batch_contract"]["candidate_batch_sizes"]:
            schedule = make_batch_schedule(
                plan["records"], split, int(batch_size), contract, int(contract["supplemental"]["seed"]) + split_index * 1000 + int(batch_size)
            )
            path = output / f"{prefix}_{split}_bs{batch_size}_epoch0.jsonl"
            atomic_jsonl(path, schedule)
            dense_values = [int(row["dense_count"]) for row in schedule]
            identity_values = [int(row["identity_count"]) for row in schedule]
            summary[f"{split}_bs{batch_size}"] = {
                "path": path.as_posix(),
                "batches": len(schedule),
                "scenes": len(split_records),
                "dense_max": max(dense_values),
                "identity_min": min(identity_values),
                "identity_max": max(identity_values),
                "unique_scenes": len({identifier for row in schedule for identifier in row["record_ids"]}),
            }
    return summary


def materialize_records(
    contract: dict[str, Any], counts_key: str, output_root: Path, dry_run: bool
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    families = contract["supplemental"]["families"]
    counts = contract["supplemental"][counts_key]
    records: list[dict[str, Any]] = []
    previews: list[np.ndarray] = []
    integrity: list[dict[str, Any]] = []
    for split in ("train", "validation"):
        for family_index, family in enumerate(families):
            for sample_index in range(int(counts[split])):
                record, arrays = generate_supplemental(contract, split, family, family_index, sample_index)
                record_id = record["record_id"]
                for key in ("target", "mask", "sdf"):
                    relative = f"{key}s/{record_id}.npy" if key != "sdf" else f"sdf/{record_id}.npy"
                    record[key] = relative
                    save_npy_idempotent(
                        output_root / relative,
                        arrays[key],
                        replace_generated=not dry_run,
                    )
                record["artifact_root"] = output_root.as_posix()
                record["storage"] = "dry_run_materialized" if dry_run else "materialized_supplemental"
                record["scene_loss_scale"] = 1.0
                record["edge_weight_normalization"] = "per_scene_sum_one"
                binary = arrays["mask"] >= 128
                sdf_sign = arrays["sdf"].astype(np.float32) >= 0.0
                union = int(np.logical_or(binary, sdf_sign).sum())
                sign_iou = 1.0 if union == 0 else float(np.logical_and(binary, sdf_sign).sum() / union)
                integrity.append(
                    {
                        "record_id": record_id,
                        "family": family,
                        "split": split,
                        "foreground_fraction": float(binary.mean()),
                        "soft_mask_fraction": float(((arrays["mask"] > 0) & (arrays["mask"] < 255)).mean()),
                        "sdf_sign_iou": sign_iou,
                        "target_min": float(arrays["target"].min() / 255.0),
                        "target_max": float(arrays["target"].max() / 255.0),
                        "sdf_finite": bool(np.isfinite(arrays["sdf"]).all()),
                    }
                )
                records.append(record)
                if len(previews) < 30:
                    previews.append(arrays["target"])
    if previews:
        tile = 128
        columns = 5
        rows = math.ceil(len(previews) / columns)
        canvas = np.zeros((rows * tile, columns * tile), dtype=np.uint8)
        for index, image in enumerate(previews):
            row, column = divmod(index, columns)
            canvas[row * tile : (row + 1) * tile, column * tile : (column + 1) * tile] = cv2.resize(
                image, (tile, tile), interpolation=cv2.INTER_AREA
            )
        save_image_idempotent(output_root.parent / "preview_supplemental.png", canvas)
    report = {
        "records": len(records),
        "counts": dict(collections.Counter(row["split"] for row in records)),
        "family_counts": dict(collections.Counter(row["family"] for row in records)),
        "minimum_sdf_sign_iou": min(row["sdf_sign_iou"] for row in integrity),
        "minimum_soft_mask_fraction": min(row["soft_mask_fraction"] for row in integrity),
        "all_sdf_finite": all(row["sdf_finite"] for row in integrity),
        "integrity": integrity,
    }
    return records, report


def replace_planned_with_materialized(plan: dict[str, Any], materialized: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {row["record_id"]: row for row in materialized}
    records: list[dict[str, Any]] = []
    for row in plan["records"]:
        records.append(by_id.get(row["record_id"], row))
    records.sort(key=lambda row: (0 if row["split"] == "train" else 1, row["record_id"]))
    for logical_index, row in enumerate(records):
        row["logical_index"] = logical_index
    formal = dict(plan)
    formal["status"] = "complete_referenced_base_plus_materialized_supplemental"
    formal["records"] = records
    formal["summary"] = dict(plan["summary"])
    formal["summary"]["materialized_supplemental"] = len(materialized)
    formal["summary"]["planned_supplemental"] = 0
    return formal


def loss_normalization_probe() -> dict[str, Any]:
    small = np.ones((1, 8, 8), dtype=np.float32)
    dense = np.ones((1, 256, 256), dtype=np.float32)
    zero = np.zeros((1, 32, 32), dtype=np.float32)
    sums = {
        "small_scene_sum": float(normalize_scene_weights(small).sum()),
        "dense_scene_sum": float(normalize_scene_weights(dense).sum()),
        "zero_scene_sum": float(normalize_scene_weights(zero).sum()),
    }
    sums["equal_nonzero_scene_influence"] = abs(sums["small_scene_sum"] - sums["dense_scene_sum"]) < 1e-6
    return sums


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("plan", "dry-run", "materialize"), default="dry-run")
    args = parser.parse_args()
    contract = read_json(CONTRACT_PATH)
    if not DYNAMIC_PATH.is_file():
        raise FileNotFoundError(DYNAMIC_PATH)
    source_hash_before = sha256_file(Path(contract["source"]["canonical_package"]) / "manifest.json")
    inventory, source_manifest, source_root = source_inventory(contract)
    atomic_json(DATA / "source_inventory.json", inventory)
    plan, plan_summary = build_logical_plan(contract, source_manifest, source_root)
    atomic_json(DATA / "planned_manifest.json", plan)
    schedule_summary = write_batch_schedules(plan, contract, prefix="planned")
    result: dict[str, Any] = {
        "status": "planned",
        "mode": args.mode,
        "source_manifest_sha256_before": source_hash_before,
        "plan_summary": plan_summary,
        "batch_schedules": schedule_summary,
        "loss_normalization_probe": loss_normalization_probe(),
    }
    if args.mode == "dry-run":
        dry_root = DATA / "dry_run" / "supplemental_targets"
        records, dry_report = materialize_records(
            contract, "dry_run_count_per_family", dry_root, dry_run=True
        )
        atomic_json(DATA / "dry_run" / "supplemental_manifest.json", {"status": "dry_run_only", "records": records})
        atomic_json(DATA / "dry_run" / "generator_statistics.json", dry_report)
        result["status"] = "dry_run_complete"
        result["dry_run"] = dry_report
    elif args.mode == "materialize":
        formal_root = DATA / "supplemental_targets"
        records, formal_report = materialize_records(
            contract, "formal_count_per_family", formal_root, dry_run=False
        )
        formal = replace_planned_with_materialized(plan, records)
        atomic_json(DATA / "manifest.json", formal)
        formal_schedules = write_batch_schedules(formal, contract, prefix="formal")
        atomic_json(DATA / "materialization_report.json", formal_report)
        result["status"] = "materialization_complete"
        result["formal"] = formal_report
        result["formal_batch_schedules"] = formal_schedules
    source_hash_after = sha256_file(Path(contract["source"]["canonical_package"]) / "manifest.json")
    if source_hash_before != source_hash_after:
        raise RuntimeError("Source manifest changed during preparation")
    result["source_manifest_sha256_after"] = source_hash_after
    result["source_unchanged"] = True
    atomic_json(DATA / ("dry_run" if args.mode == "dry-run" else "") / "preparation_result.json", result)
    print(json.dumps({"status": result["status"], "mode": args.mode, "records": plan_summary["records"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
