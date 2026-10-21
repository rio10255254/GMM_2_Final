"""New procedural paired scenes, independently rendered on a 4x physical grid.

No microscope frame, SEM image, teacher, prior model, or historical dataset is
read here. Moving object coordinates precedes fixed-pair optical convolution,
area integration, additive sensor noise and quantization, in that order.
The 2x profile is a separate sample of the same specified optical covariance;
it is not fitted to force the independently rendered 4x data to match a model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage, signal


MAIN_CATEGORIES = (
    "irregular_curved", "corners_lines_junctions", "dense_close_structures", "textured_edges"
)
CATEGORIES = tuple(
    category
    for round_index in range(13)
    for category in MAIN_CATEGORIES + (("clean_identity", "flat_negative") if round_index < 6 else ())
)
RENDER_FACTOR = 4
MODEL_FACTOR = 2
BASE_SEED = 1251000
MAX_SDF = 16.0


def _json_write(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False, ensure_ascii=False)
        stream.write("\n")


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _array_hash(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def area_average(image: np.ndarray, factor: int) -> np.ndarray:
    if image.ndim != 2 or any(size % factor for size in image.shape):
        raise ValueError("Area integration needs a 2D array divisible by the sampling factor")
    height, width = image.shape
    return image.reshape(height // factor, factor, width // factor, factor).mean((1, 3), dtype=np.float32)


def gaussian_kernel(sigma_xy: tuple[float, float], angle: float, factor: int, radius_native: int) -> np.ndarray:
    """Centered physical impulse response sampled independently at the given density."""
    if sigma_xy == (0.0, 0.0):
        return np.ones((1, 1), dtype=np.float32)
    radius = radius_native * factor
    axis = np.arange(-radius, radius + 1, dtype=np.float64) / factor
    xx, yy = np.meshgrid(axis, axis)
    cosine, sine = math.cos(angle), math.sin(angle)
    u, v = cosine * xx + sine * yy, -sine * xx + cosine * yy
    kernel = np.exp(-0.5 * ((u / sigma_xy[0]) ** 2 + (v / sigma_xy[1]) ** 2))
    kernel /= kernel.sum()
    return kernel.astype(np.float32)


def _parameters(index: int, category: str, rng: np.random.Generator, size: int, core: int) -> dict:
    scale = core / 128
    center = [size / 2 + float(rng.uniform(-8, 8)) * scale,
              size / 2 + float(rng.uniform(-8, 8)) * scale]
    shape = {
        "category": category, "center_xy": center,
        "rotation_rad": float(rng.uniform(-math.pi, math.pi)), "scale": scale,
    }
    if category == "irregular_curved":
        shape.update(radius=float(rng.uniform(37, 48)) * scale,
                     ellipticity=float(rng.uniform(0.8, 1.2)),
                     harmonic3=float(rng.uniform(0.07, 0.14)),
                     harmonic5=float(rng.uniform(0.025, 0.07)),
                     phase=float(rng.uniform(-math.pi, math.pi)))
    elif category == "corners_lines_junctions":
        shape.update(bar_width=float(rng.uniform(10, 15)) * scale,
                     arm_length=float(rng.uniform(78, 94)) * scale,
                     branch_offset=float(rng.uniform(14, 20)) * scale)
    elif category == "dense_close_structures":
        shape.update(pitch=float(rng.uniform(14, 21)) * scale,
                     gap=float(rng.uniform(2.5, 4.5)) * scale,
                     motif="squares" if rng.random() < 0.5 else "disks")
    elif category == "textured_edges":
        shape.update(wave_amplitude=float(rng.uniform(4, 9)) * scale,
                     wave_period=float(rng.uniform(36, 56)) * scale)
    elif category == "clean_identity":
        # All coordinates lie on native-pixel boundaries; the identity control
        # is precisely representable on native, 2x and 4x grids.
        shape.update(center_xy=[size // 2, size // 2], rotation_rad=0.0,
                     box_half_width=max(3, round(27 * scale)),
                     box_half_height=max(3, round(36 * scale)),
                     notch_width=max(2, round(9 * scale)))
    elif category == "flat_negative":
        shape.update(foreground=False)
    else:
        raise ValueError(category)
    return shape


def object_score(x: np.ndarray, y: np.ndarray, shape: dict, shift_xy: tuple[float, float]) -> np.ndarray:
    """Continuous foreground-positive occupancy function, not a claimed exact SDF."""
    dx = x - shape["center_xy"][0] - shift_xy[0]
    dy = y - shape["center_xy"][1] - shift_xy[1]
    cosine, sine = math.cos(shape["rotation_rad"]), math.sin(shape["rotation_rad"])
    u, v = cosine * dx + sine * dy, -sine * dx + cosine * dy
    category = shape["category"]
    if category == "irregular_curved":
        ue = u / shape["ellipticity"]
        theta = np.arctan2(v, ue)
        boundary_radius = shape["radius"] * (
            1 + shape["harmonic3"] * np.cos(3 * theta + shape["phase"])
            + shape["harmonic5"] * np.sin(5 * theta - shape["phase"])
        )
        return boundary_radius - np.hypot(ue, v)
    if category == "corners_lines_junctions":
        width, length, offset = shape["bar_width"], shape["arm_length"], shape["branch_offset"]
        vertical = np.minimum(width / 2 - np.abs(u + offset), length / 2 - np.abs(v))
        horizontal = np.minimum(length / 2 - np.abs(u), width / 2 - np.abs(v - offset))
        branch = np.minimum(width / 2 - np.abs((u - v) / math.sqrt(2)), length * 0.3 - np.abs((u + v) / math.sqrt(2)))
        return np.maximum(np.maximum(vertical, horizontal), branch)
    if category == "dense_close_structures":
        pitch, gap = shape["pitch"], shape["gap"]
        tx = (u + pitch / 2) % pitch - pitch / 2
        ty = (v + pitch / 2) % pitch - pitch / 2
        half = (pitch - gap) / 2
        return half - (np.maximum(np.abs(tx), np.abs(ty)) if shape["motif"] == "squares" else np.hypot(tx, ty))
    if category == "textured_edges":
        return u + shape["wave_amplitude"] * np.sin(2 * math.pi * v / shape["wave_period"])
    if category == "clean_identity":
        box = np.minimum(shape["box_half_width"] - np.abs(u), shape["box_half_height"] - np.abs(v))
        notch = np.minimum(shape["notch_width"] - np.abs(u), shape["box_half_height"] - v)
        # Subtract a narrow slot entering from the upper end, making two corners.
        notch = np.minimum(notch, v)
        return np.minimum(box, -notch)
    return np.full(np.broadcast_shapes(x.shape, y.shape), 1.0 if shape["foreground"] else -1.0, dtype=np.float32)


def intensity_at(x: np.ndarray, y: np.ndarray, shape: dict, photometry: dict,
                 shift_xy: tuple[float, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    score = object_score(x, y, shape, shift_xy)
    foreground = score > 0
    low, high = photometry["low"], photometry["high"]
    amplitude = photometry["texture_amplitude"]
    material = foreground.astype(np.float32)
    if photometry["polarity"] == -1:
        material = 1 - material
    image = low + (high - low) * material
    if amplitude:
        # Texture moves with the object. Its frequencies, phase, direction and
        # amplitude are sampled independently of geometry and PSF parameters.
        tx, ty = x - shift_xy[0], y - shift_xy[1]
        a = photometry["texture_angle_rad"]
        u, v = math.cos(a) * tx + math.sin(a) * ty, -math.sin(a) * tx + math.cos(a) * ty
        phase = photometry["texture_phase"]
        texture = amplitude * (0.62 * np.sin(2 * math.pi * u / photometry["texture_period1"] + phase)
                               + 0.38 * np.cos(2 * math.pi * v / photometry["texture_period2"] - phase))
        texture = texture * np.where(foreground, 1.0, 0.55)
        image = image + texture
    else:
        texture = np.zeros_like(image)
    return image.astype(np.float32), foreground, texture.astype(np.float32)


def _sdf_from_foreground(foreground: np.ndarray) -> np.ndarray:
    if foreground.all():
        return np.full((foreground.shape[0] // 4, foreground.shape[1] // 4), MAX_SDF, dtype=np.float32)
    if not foreground.any():
        return np.full((foreground.shape[0] // 4, foreground.shape[1] // 4), -MAX_SDF, dtype=np.float32)
    inside = ndimage.distance_transform_edt(foreground).astype(np.float32)
    outside = ndimage.distance_transform_edt(~foreground).astype(np.float32)
    signed = np.where(foreground, inside - 0.5, -(outside - 0.5)) / RENDER_FACTOR
    return np.clip(area_average(signed, RENDER_FACTOR), -MAX_SDF, MAX_SDF).astype(np.float32)


def _core_statistics(arrays: dict, textures: list[np.ndarray], core_slice: list[int]) -> list[dict]:
    y0, y1, x0, x1 = core_slice
    stats = []
    for view in range(2):
        target = arrays["target"][view, y0:y1, x0:x1]
        source = arrays["source"][view, y0:y1, x0:x1]
        sdf = arrays["sdf"][view, y0:y1, x0:x1]
        binary = sdf > 0
        # An actual corner response computed from the core geometry, rather
        # than trusting the category label to imply the presence of corners.
        gx = ndimage.sobel(binary.astype(np.float32), axis=1) / 8
        gy = ndimage.sobel(binary.astype(np.float32), axis=0) / 8
        a = ndimage.gaussian_filter(gx * gx, 1)
        b = ndimage.gaussian_filter(gx * gy, 1)
        c = ndimage.gaussian_filter(gy * gy, 1)
        response = a * c - b * b - 0.04 * (a + c) ** 2
        peaks = (response == ndimage.maximum_filter(response, 5)) & (response > max(1e-5, float(response.max()) * 0.05))
        stats.append({
            "view": view, "foreground_fraction": float(binary.mean()),
            "boundary_pixels": int((np.abs(sdf) <= 1.5).sum()),
            "corner_response_peaks": int(peaks.sum()),
            "narrow_background_fraction": float(((~binary) & (np.abs(sdf) < 3)).mean()),
            "target_mean": float(target.mean()), "target_std": float(target.std()),
            "target_min": float(target.min()), "target_max": float(target.max()),
            "intrinsic_texture_std": float(textures[view][y0:y1, x0:x1].std()),
            "noiseless_min": float(arrays["noiseless"][view, y0:y1, x0:x1].min()),
            "noiseless_max": float(arrays["noiseless"][view, y0:y1, x0:x1].max()),
            "source_saturated_pixels": int(((source == 0) | (source == 255)).sum()),
        })
    return stats


def _admission(category: str, statistics: list[dict]) -> tuple[bool, list[str]]:
    failures = []
    for stats in statistics:
        view = stats["view"]
        if stats["source_saturated_pixels"]:
            failures.append(f"view{view}:saturated_core")
        if category == "flat_negative":
            if stats["target_std"] > 1e-6 or stats["boundary_pixels"]:
                failures.append(f"view{view}:not_flat")
            continue
        if not 0.04 <= stats["foreground_fraction"] <= 0.94 or stats["boundary_pixels"] < 32:
            failures.append(f"view{view}:missing_material_edge_in_core")
        if category == "corners_lines_junctions" and stats["corner_response_peaks"] < 1:
            failures.append(f"view{view}:missing_corner")
        if category == "dense_close_structures" and stats["narrow_background_fraction"] < 0.01:
            failures.append(f"view{view}:missing_close_gap")
        if category == "textured_edges" and stats["intrinsic_texture_std"] < 0.005:
            failures.append(f"view{view}:missing_intrinsic_texture")
    return not failures, failures


def generate_scene(index: int, *, native_size: int = 640, supervised_size: int = 128) -> tuple[dict, dict]:
    if type(index) is not int or not 0 <= index < len(CATEGORIES):
        raise ValueError("Scene index must select one of the 64 preregistered category slots")
    if native_size < supervised_size or (native_size - supervised_size) % 2 or supervised_size < 32:
        raise ValueError("Invalid native/core dimensions")
    category = CATEGORIES[index]
    seed = BASE_SEED + index
    lower = (native_size - supervised_size) // 2
    core_slice = [lower, lower + supervised_size, lower, lower + supervised_size]
    rejected_attempts = []
    for attempt in range(20):
        effective_seed = seed + 100000 * attempt
        # Disjoint deterministic random streams: geometry, radiometry, optics,
        # motion, and the two sensor-noise draws cannot accidentally share state.
        streams = [np.random.default_rng(child) for child in np.random.SeedSequence(effective_seed).spawn(6)]
        geom_rng, photo_rng, optical_rng, motion_rng, noise0, noise1 = streams
        shape = _parameters(index, category, geom_rng, native_size, supervised_size)
        low, high = float(photo_rng.uniform(0.17, 0.34)), float(photo_rng.uniform(0.65, 0.83))
        clean = category == "clean_identity"
        flat = category == "flat_negative"
        if clean:
            low, high = round(low * 255) / 255, round(high * 255) / 255
        texture_amplitude = float(photo_rng.uniform(0.025, 0.06)) if category == "textured_edges" else (float(photo_rng.uniform(0, 0.012)) if not (clean or flat) else 0.0)
        photometry = {
            "low": low, "high": high,
            "polarity": 1 if photo_rng.random() < 0.5 else -1,
            "texture_amplitude": texture_amplitude,
            "texture_angle_rad": float(photo_rng.uniform(-math.pi, math.pi)),
            "texture_phase": float(photo_rng.uniform(-math.pi, math.pi)),
            "texture_period1": float(photo_rng.uniform(4.5, 9)),
            "texture_period2": float(photo_rng.uniform(9, 17)),
        }
        sigma = float(optical_rng.choice([0.6, 1.0, 1.6, 2.2]))
        sigma_xy = (sigma, sigma * float(optical_rng.choice([0.8, 1.0, 1.25])))
        angle = float(optical_rng.choice([0, math.pi / 6, math.pi / 3, math.pi / 2]))
        radius_native = int(math.ceil(4.5 * max(sigma_xy)))
        noise_sigma = float(optical_rng.choice([0.5, 1.5, 3.0]))
        if clean:
            sigma_xy, angle, radius_native, noise_sigma = (0.0, 0.0), 0.0, 0, 0.0
        kernel4 = gaussian_kernel(sigma_xy, angle, 4, radius_native)
        kernel2 = gaussian_kernel(sigma_xy, angle, 2, radius_native)
        delta = (float(motion_rng.uniform(-0.85, 0.85)), float(motion_rng.uniform(-0.85, 0.85)))
        if math.hypot(*delta) < 0.15:
            delta = (delta[0] + 0.35, delta[1])
        if clean:
            delta = (0.0, 0.0)
        shifts = [(0.0, 0.0), delta]
        margin = radius_native
        axis = (np.arange((native_size + 2 * margin) * 4, dtype=np.float32) + 0.5) / 4 - margin
        x, y = axis[None, :], axis[:, None]
        region = slice(margin * 4, (margin + native_size) * 4)
        arrays = {name: [] for name in ("source", "target", "latent_target", "sdf", "boundary", "noiseless")}
        textures = []
        for view, shift in enumerate(shifts):
            optical, foreground, texture = intensity_at(x, y, shape, photometry, shift)
            inside = optical[region, region]
            truth_native = area_average(inside, 4)
            if clean:
                # Canonical conversion matches source.uint8 / 255 exactly, and
                # does not alter the representable pixel-aligned physical scene.
                truth_native = (np.rint(truth_native * 255).astype(np.uint8).astype(np.float32) / np.float32(255))
            latent_target = area_average(inside, 2)
            if clean:
                latent_target = truth_native.repeat(2, 0).repeat(2, 1)
            blurred = optical if clean else signal.fftconvolve(optical, kernel4, mode="same")
            noiseless = area_average(blurred[region, region], 4)
            if clean:
                noiseless = truth_native.copy()
            sdf = _sdf_from_foreground(foreground[region, region])
            noise_rng = noise0 if view == 0 else noise1
            noise = noise_rng.normal(0, noise_sigma / 255, noiseless.shape).astype(np.float32)
            source = np.rint(np.clip(noiseless + noise, 0, 1) * 255).astype(np.uint8)
            for key, value in (
                ("source", source), ("target", truth_native), ("latent_target", latent_target),
                ("sdf", sdf), ("boundary", (np.abs(sdf) <= 1.0).astype(np.float32)),
                ("noiseless", noiseless.astype(np.float32)),
            ):
                arrays[key].append(value)
            textures.append(area_average(texture[region, region], 4))
        arrays = {key: np.stack(values) for key, values in arrays.items()}
        statistics = _core_statistics(arrays, textures, core_slice)
        admitted, failures = _admission(category, statistics)
        if not admitted:
            rejected_attempts.append({"attempt": attempt, "effective_seed": effective_seed, "failures": failures})
            continue
        scene_id = f"scene_{index:03d}"
        parent_id = f"r125_procedural_{index:03d}_seed{effective_seed}"
        profile = {
            "calibration_id": parent_id + "_specified_simulation_optics",
            "qualification": "unqualified_diagnostic", "simulation_known_operator": True,
            "kernel_convention": "physical_psf", "sampling_factor": 2,
            "kernel": {"type": "explicit", "values": kernel2.tolist()},
            "gain": 1.0, "bias": 0.0,
            "noise_variance": (max(noise_sigma, 0.5) ** 2 + 1 / 12) / 255 ** 2,
        }
        metadata = {
            "schema_version": 1, "scene_id": scene_id, "index": index, "category": category,
            "parent_latent_id": parent_id, "source_ancestors": [parent_id],
            "seed": seed, "effective_seed": effective_seed, "attempt": attempt,
            "rejected_attempts": rejected_attempts,
            "random_streams": ["geometry", "radiometry", "optics", "motion", "noise_view0", "noise_view1"],
            "native_size": native_size, "supervised_size": supervised_size, "core_slice": core_slice,
            "shape_params": shape, "photometry": photometry, "polarity": photometry["polarity"],
            "shift_xy": list(delta), "view_shift_xy": [list(shift) for shift in shifts], "exact_delta_xy": list(delta),
            "identity": clean, "flat": flat, "motion_observable": not flat, "zero_motion_control": clean,
            "profile": profile,
            "rendering_profile": {"sampling_factor": 4, "kernel_convention": "physical_psf",
                                  "kernel": kernel4.tolist(), "sigma_native_xy": list(sigma_xy),
                                  "rotation_rad": angle, "radius_native": radius_native,
                                  "boundary": "continuous object extended by PSF support before convolution and sensor crop"},
            "noise_sigma_gray": noise_sigma, "noise_variance_floor_gray": 0.5,
            "profile_variance_includes_quantization": True,
            "profile_variance_formula": "(max(actual_noise_sigma_gray,0.5)^2 + 1/12)/255^2; floor/quantization term is numerical weighting, identity observations themselves have no noise",
            "quantization_step": 1 / 255, "uniform_quantization_variance_approximation": 1 / (12 * 255 ** 2),
            "rendering_order": ["evaluate_continuous_shifted_object_at_4x_cell_centers", "fixed_pair_psf_convolution", "sensor_area_integration", "independent_additive_sensor_noise", "uint8_quantization"],
            "latent_target_convention": "2x area means of unblurred 4x optical intensity, no post-acquisition target blur",
            "sdf_convention": "foreground-positive 4x raster EDT, half-grid boundary correction, native area mean, clipped to +/-16 native pixels; not exact continuous geometry",
            "boundary_convention": "abs(native signed distance) <= 1 native pixel",
            "core_stats": statistics,
            "admission": {"passed": True, "checked_both_views": True, "no_saturation_in_supervised_core": True},
            "source_original_sha256": [_array_hash(arrays["source"][view]) for view in range(2)],
            "array_sha256": {key: _array_hash(value) for key, value in arrays.items()},
            "external_training_inputs": [], "existing_test_answer_access": False,
        }
        return arrays, metadata
    raise RuntimeError(f"Scene {index} rejected after 20 deterministic attempts: {rejected_attempts}")


def prepare_package(output: str | Path, count: int = 64) -> dict:
    if type(count) is not int or not 1 <= count <= 64:
        raise ValueError("count must be between 1 and 64")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    scene_dir = output / "scenes"
    scene_dir.mkdir()
    _json_write(output / "generation_started.json", {
        "status": "generation_started_not_completion", "scene_count_requested": count,
        "generator_sha256": _file_hash(Path(__file__)), "source_kind": "new_procedural_only",
    })
    entries = []
    for index in range(count):
        arrays, metadata = generate_scene(index)
        array_path = scene_dir / f"{metadata['scene_id']}.npz"
        metadata_path = scene_dir / f"{metadata['scene_id']}.metadata.json"
        with array_path.open("xb") as stream:
            np.savez_compressed(stream, **arrays)
        _json_write(metadata_path, metadata)
        entries.append({
            "scene_id": metadata["scene_id"], "index": index, "category": metadata["category"],
            "parent_latent_id": metadata["parent_latent_id"],
            "arrays_path": array_path.relative_to(output).as_posix(),
            "metadata_path": metadata_path.relative_to(output).as_posix(),
            "sha256": {"arrays": _file_hash(array_path), "metadata": _file_hash(metadata_path)},
        })
        print(json.dumps({"scene": index + 1, "count": count, "category": metadata["category"],
                          "attempt": metadata["attempt"], "bytes": array_path.stat().st_size}), flush=True)
    manifest = {
        "schema_version": 1, "status": "generated_not_model_or_real_world_validation",
        "scene_count": count, "views_per_scene": 2, "native_size": 640,
        "supervised_size": 128, "context_native_px": 256,
        "category_counts": dict(Counter(entry["category"] for entry in entries)),
        "scene_order": "deterministically_interleaved_categories",
        "source_kind": "new_procedural_only", "external_training_inputs": [],
        "generator_path": str(Path(__file__).resolve()), "generator_sha256": _file_hash(Path(__file__)),
        "scenes": entries,
    }
    _json_write(output / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--count", type=int, default=64)
    arguments = parser.parse_args()
    prepare_package(arguments.output, arguments.count)
