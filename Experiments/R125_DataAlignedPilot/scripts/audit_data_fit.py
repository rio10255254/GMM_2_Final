"""Independent, read-only audit of R125's procedural acquisition package.

No kernel is fitted and no target is changed. The 4x generator observation is
compared with the frozen R124 2x operator on the actual supervised core. These
engineering checks do not qualify a simulated kernel as real calibration.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType

import numpy as np
from scipy.ndimage import shift as image_shift
from scipy.signal import convolve
import torch

ROOT = Path(__file__).resolve().parents[1]
R124 = ROOT.parent / "R124_RealFirstPrototype"
CORE = (256, 384, 256, 384)
LIMITS = {
    "target_area_max_abs": 2e-7,
    "operator_discrepancy_rms_over_declared_sigma": 0.25,
    "operator_discrepancy_p99_over_declared_sigma": 1.0,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def confined_path(base: Path, relative: str) -> Path:
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError(f"package path escapes its root: {relative}")
    return path


def area_mean(x: np.ndarray, factor: int) -> np.ndarray:
    """Independent explicit reshape of equally sized physical cell averages."""
    if x.shape[-2] % factor or x.shape[-1] % factor:
        raise ValueError("area integration would discard incomplete cells")
    shape = x.shape[:-2] + (x.shape[-2] // factor, factor, x.shape[-1] // factor, factor)
    return x.reshape(shape).mean(axis=(-3, -1), dtype=np.float64)


def discrepancy_stats(error: np.ndarray, sigma: float | None = None) -> dict:
    values = np.asarray(error, dtype=np.float64).ravel()
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("discrepancy statistics require finite nonempty values")
    absolute = np.abs(values)
    result = {
        "count": int(values.size), "mean_signed": float(values.mean()),
        "rms": float(np.sqrt(np.mean(values * values))),
        "max_abs": float(absolute.max()),
        **{f"p{p:g}_abs": float(np.percentile(absolute, p)) for p in (50, 90, 95, 99, 99.9)},
    }
    result.update({f"{name}_gray": value * 255 for name, value in list(result.items()) if name != "count"})
    if sigma is not None:
        if not np.isfinite(sigma) or sigma <= 0:
            raise ValueError("normalizing sigma must be positive and finite")
        result.update({f"{name}_over_declared_sigma": result[name] / sigma for name in ("rms", "max_abs", "p99_abs")})
    return result


def model_discrepancy_admissible(stats: dict) -> bool:
    return (
        stats["rms_over_declared_sigma"] <= LIMITS["operator_discrepancy_rms_over_declared_sigma"]
        and stats["p99_abs_over_declared_sigma"] <= LIMITS["operator_discrepancy_p99_over_declared_sigma"]
    )


def observation_from_profile(profile: dict):
    """Load the immutable R124 implementation without importing the generator."""
    package_name = "r124_frozen_model_for_r125_audit"
    if package_name not in sys.modules:
        module = ModuleType(package_name)
        module.__path__ = [str(R124 / "model")]
        sys.modules[package_name] = module
    name = package_name + ".calibration"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, R124 / "model" / "calibration.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return sys.modules[name].observation_from_profile(profile, device="cpu")


def operator_core_prediction(latent: np.ndarray, profile: dict, core=CORE) -> np.ndarray:
    observation = observation_from_profile(profile)
    factor = observation.sampling_factor
    if factor != 2:
        raise ValueError("R125 audit requires the declared 2x latent representation")
    r0, r1, c0, c1 = core
    margin = math.ceil(observation.kernel_radius_internal / factor) + 1
    if min(r0, c0, latent.shape[-2] // factor - r1, latent.shape[-1] // factor - c1) < margin:
        raise ValueError("insufficient physical context for the supervised core")
    patch = latent[:, (r0 - margin) * factor:(r1 + margin) * factor,
                   (c0 - margin) * factor:(c1 + margin) * factor]
    tensor = torch.from_numpy(np.ascontiguousarray(patch[:, None])).float()
    with torch.inference_mode():
        prediction = observation(tensor)[:, 0, margin:margin + r1 - r0, margin:margin + c1 - c0]
    return prediction.numpy()


def motion_diagnostic(target: np.ndarray, sdf: np.ndarray, delta_xy, core=CORE) -> dict:
    """Check direction on actual images; fractional interpolation is diagnostic.

    Bilinear translation of an already integrated image is not the physical
    renderer and therefore is never required to match exactly.
    """
    dx, dy = map(float, delta_xy)
    r0, r1, c0, c1 = core
    target_core = target[1, r0:r1, c0:c1]
    same = target[0, r0:r1, c0:c1]
    expected = image_shift(target[0], (dy, dx), order=1, mode="nearest", prefilter=False)[r0:r1, c0:c1]
    opposite = image_shift(target[0], (-dy, -dx), order=1, mode="nearest", prefilter=False)[r0:r1, c0:c1]
    transformed_sdf = image_shift(sdf[0], (dy, dx), order=1, mode="nearest", prefilter=False)[r0:r1, c0:c1]
    actual_sdf = sdf[1, r0:r1, c0:c1]
    edge = np.abs(actual_sdf) < 8
    result = {
        "delta_xy": [dx, dy],
        "target_unshifted_rms": float(np.sqrt(np.mean((same - target_core) ** 2))),
        "target_expected_shift_rms": float(np.sqrt(np.mean((expected - target_core) ** 2))),
        "target_opposite_shift_rms": float(np.sqrt(np.mean((opposite - target_core) ** 2))),
        "sdf_edge_comparison_pixels": int(edge.sum()),
        "limitation": "native bilinear resampling is approximate; generator physical order is reviewed separately",
    }
    if edge.any():
        result["sdf_expected_shift_error"] = discrepancy_stats((transformed_sdf - actual_sdf)[edge])
    return result


def independent_intensity(x, y, shape: dict, photo: dict, displacement):
    """Re-express the declared analytic shapes; never import generator helpers."""
    dx, dy = displacement
    px, py = x - float(shape["center_xy"][0]) - dx, y - float(shape["center_xy"][1]) - dy
    rotation = float(shape["rotation_rad"])
    u = np.cos(rotation) * px + np.sin(rotation) * py
    v = np.cos(rotation) * py - np.sin(rotation) * px
    category = shape["category"]
    if category == "irregular_curved":
        a = u / shape["ellipticity"]
        angle = np.arctan2(v, a)
        radial_limit = shape["radius"] * (1 + shape["harmonic3"] * np.cos(3 * angle + shape["phase"]) + shape["harmonic5"] * np.sin(5 * angle - shape["phase"]))
        foreground = np.sqrt(a * a + v * v) < radial_limit
    elif category == "corners_lines_junctions":
        w, length, offset = shape["bar_width"], shape["arm_length"], shape["branch_offset"]
        vertical = (np.abs(u + offset) < w / 2) & (np.abs(v) < length / 2)
        horizontal = (np.abs(u) < length / 2) & (np.abs(v - offset) < w / 2)
        diagonal = (np.abs(u - v) < w / np.sqrt(2)) & (np.abs(u + v) < length * 0.3 * np.sqrt(2))
        foreground = vertical | horizontal | diagonal
    elif category == "dense_close_structures":
        pitch = shape["pitch"]
        local_x, local_y = (u + pitch / 2) % pitch - pitch / 2, (v + pitch / 2) % pitch - pitch / 2
        radius = (pitch - shape["gap"]) / 2
        foreground = ((np.abs(local_x) < radius) & (np.abs(local_y) < radius)) if shape["motif"] == "squares" else (local_x**2 + local_y**2 < radius**2)
    elif category == "textured_edges":
        foreground = u > -shape["wave_amplitude"] * np.sin(2 * np.pi * v / shape["wave_period"])
    elif category == "clean_identity":
        foreground = (np.abs(u) < shape["box_half_width"]) & (np.abs(v) < shape["box_half_height"])
        notch = (np.abs(u) <= shape["notch_width"]) & (v >= 0) & (v <= shape["box_half_height"])
        foreground &= ~notch
    elif category == "flat_negative":
        foreground = np.full(np.broadcast_shapes(x.shape, y.shape), bool(shape["foreground"]))
    else:
        raise ValueError(f"unreviewed procedural category {category}")
    material = foreground if photo["polarity"] == 1 else ~foreground
    intensity = float(photo["low"]) + (float(photo["high"]) - float(photo["low"])) * material
    amplitude = float(photo["texture_amplitude"])
    if amplitude:
        angle = float(photo["texture_angle_rad"])
        tx = np.cos(angle) * (x - dx) + np.sin(angle) * (y - dy)
        ty = np.cos(angle) * (y - dy) - np.sin(angle) * (x - dx)
        texture = amplitude * (0.62 * np.sin(2 * np.pi * tx / photo["texture_period1"] + photo["texture_phase"]) + 0.38 * np.cos(2 * np.pi * ty / photo["texture_period2"] - photo["texture_phase"]))
        intensity += texture * np.where(foreground, 1, 0.55)
    return np.asarray(intensity, dtype=np.float64), foreground


def independent_physical_patch(arrays: dict, metadata: dict, width=16) -> dict:
    """Small 4x, float64 reconstruction from analytic parameters and covariance.

    Select one boundary location per view from stored geometry, or the center
    for a flat field. Reconstruct the surrounding physical object before optics.
    This tests the retained data, not a second invocation of the generator.
    """
    profile = metadata["rendering_profile"]
    radius = int(profile["radius_native"])
    sigma_x, sigma_y = profile["sigma_native_xy"]
    axis = np.arange(-4 * radius, 4 * radius + 1, dtype=np.float64) / 4
    kx, ky = np.meshgrid(axis, axis)
    theta = float(profile["rotation_rad"])
    if sigma_x == 0 and sigma_y == 0:
        kernel = np.ones((1, 1))
    else:
        ku, kv = np.cos(theta) * kx + np.sin(theta) * ky, -np.sin(theta) * kx + np.cos(theta) * ky
        kernel = np.exp(-0.5 * (ku**2 / sigma_x**2 + kv**2 / sigma_y**2))
        kernel /= kernel.sum()
    declared_kernel = np.asarray(profile["kernel"], dtype=np.float64)
    output = {"kernel_from_covariance_max_abs": float(np.max(np.abs(kernel - declared_kernel))), "views": []}
    for view in range(2):
        r0, r1, c0, c1 = CORE
        candidate_sdf = np.abs(arrays["sdf"][view, r0:r1, c0:c1])
        yy, xx = np.indices(candidate_sdf.shape)
        score = candidate_sdf + 0.0001 * ((yy - 64)**2 + (xx - 64)**2)
        selected_y, selected_x = np.unravel_index(np.argmin(score), score.shape)
        center_y, center_x = int(r0 + selected_y), int(c0 + selected_x)
        start_y, start_x = center_y - width // 2, center_x - width // 2
        x = (np.arange((width + 2 * radius) * 4, dtype=np.float64) + 0.5) / 4 + start_x - radius
        y = (np.arange((width + 2 * radius) * 4, dtype=np.float64) + 0.5) / 4 + start_y - radius
        intensity, foreground = independent_intensity(x[None, :], y[:, None], metadata["shape_params"], metadata["photometry"], metadata["view_shift_xy"][view])
        formed = convolve(intensity, kernel, mode="same", method="fft")
        native = area_mean(formed[radius * 4:(radius + width) * 4, radius * 4:(radius + width) * 4], 4)
        truth = area_mean(intensity[radius * 4:(radius + width) * 4, radius * 4:(radius + width) * 4], 4)
        stored = arrays["noiseless"][view, start_y:start_y + width, start_x:start_x + width]
        stored_target = arrays["target"][view, start_y:start_y + width, start_x:start_x + width]
        output["views"].append({"view": view, "patch_native": [start_y, start_y + width, start_x, start_x + width], "noiseless_error": discrepancy_stats(native - stored), "target_error": discrepancy_stats(truth - stored_target)})
    return output


def audit_arrays(arrays: dict, metadata: dict) -> tuple[dict, list[str]]:
    failures = []
    expected_shapes = {name: (2, 640, 640) for name in ("source", "target", "noiseless", "sdf", "boundary")}
    expected_shapes["latent_target"] = (2, 1280, 1280)
    for name, shape in expected_shapes.items():
        if name not in arrays or arrays[name].shape != shape:
            raise ValueError(f"{name}: expected array shape {shape}")
        expected_dtype = np.uint8 if name == "source" else np.float32
        if arrays[name].dtype != expected_dtype or not np.isfinite(arrays[name]).all():
            raise ValueError(f"{name}: invalid dtype or nonfinite data")
    for name in ("target", "noiseless", "latent_target", "boundary"):
        if arrays[name].min() < -2e-7 or arrays[name].max() > 1 + 2e-7:
            failures.append(f"{name}_outside_declared_range")
    if list(metadata.get("core_slice", [])) != list(CORE):
        failures.append("supervised_core_or_context_contract_mismatch")
    r0, r1, c0, c1 = CORE
    core = (slice(None), slice(r0, r1), slice(c0, c1))
    integrated = area_mean(arrays["latent_target"], 2)
    area_error = discrepancy_stats(integrated - arrays["target"])
    if area_error["max_abs"] > LIMITS["target_area_max_abs"]:
        failures.append("target_does_not_equal_area_integrated_latent")
    profile = metadata["profile"]
    if profile["sampling_factor"] != 2 or profile["qualification"] != "unqualified_diagnostic":
        failures.append("invalid_simulation_profile_or_qualification")
    if profile["kernel_convention"] != "physical_psf" or profile["gain"] != 1 or profile["bias"] != 0:
        failures.append("profile_differs_from_declared_pilot_contract")
    prediction = operator_core_prediction(arrays["latent_target"], profile)
    mismatch = prediction - arrays["noiseless"][core]
    sigma = math.sqrt(float(profile["noise_variance"]))
    fit = discrepancy_stats(mismatch, sigma)
    view_fits = [discrepancy_stats(mismatch[v], sigma) for v in range(2)]
    if not all(model_discrepancy_admissible(view_fit) for view_fit in view_fits):
        failures.append("2x_model_vs_4x_render_discrepancy_exceeds_prespecified_screen")
    source_error = arrays["source"][core].astype(np.float64) / 255 - arrays["noiseless"][core]
    noise = discrepancy_stats(source_error, sigma)
    identity = bool(metadata.get("identity"))
    flat = bool(metadata.get("flat"))
    actual_noise = float(metadata.get("noise_sigma_gray", -1))
    expected_variance = (max(actual_noise, 0.5)**2 + 1 / 12) / 255**2
    if actual_noise < 0 or not math.isclose(float(profile["noise_variance"]), expected_variance, abs_tol=1e-15, rel_tol=1e-12):
        failures.append("declared_noise_variance_formula_mismatch")
    if metadata.get("profile_variance_includes_quantization") is not True or not math.isclose(float(metadata.get("quantization_step", -1)), 1 / 255, abs_tol=1e-15):
        failures.append("quantization_contract_not_explicit")
    if identity:
        if not np.array_equal(arrays["source"].astype(np.float32) / np.float32(255), arrays["target"]) or not np.array_equal(arrays["target"], arrays["noiseless"]):
            failures.append("identity_source_target_not_exact")
        if actual_noise != 0 or list(metadata.get("exact_delta_xy", [])) != [0, 0] or profile["kernel"]["values"] != [[1.0]]:
            failures.append("identity_noise_motion_or_optics_not_identity")
    geometry = []
    for view in range(2):
        sdf = arrays["sdf"][view, r0:r1, c0:c1]
        target = arrays["target"][view, r0:r1, c0:c1]
        boundary = arrays["boundary"][view, r0:r1, c0:c1]
        inside, outside, near = sdf > 2, sdf < -2, np.abs(sdf) <= 2
        row = {
            "view": view, "foreground_fraction": float((sdf > 0).mean()),
            "near_boundary_fraction": float(near.mean()),
            "target_mean": float(target.mean()), "target_std": float(target.std()),
            "boundary_mean": float(boundary.mean()),
            "inside_pixels": int(inside.sum()), "outside_pixels": int(outside.sum()),
            "sdf_min": float(sdf.min()), "sdf_max": float(sdf.max()),
        }
        if inside.any() and outside.any():
            row["inside_minus_outside_median"] = float(np.median(target[inside]) - np.median(target[outside]))
            if row["inside_minus_outside_median"] * metadata["polarity"] <= 0:
                failures.append(f"view{view}_sdf_intensity_polarity_disagrees")
        if near.any():
            row["boundary_near_mean"] = float(boundary[near].mean())
        if (np.abs(sdf) > 8).any():
            row["boundary_far_mean"] = float(boundary[np.abs(sdf) > 8].mean())
        geometry.append(row)
        if not flat and (not 0.04 <= row["foreground_fraction"] <= 0.94 or int((np.abs(sdf) <= 1.5).sum()) < 32):
            failures.append(f"view{view}_missing_core_geometry")
        if flat and (row["target_std"] > 1e-6 or row["boundary_mean"] != 0 or row["near_boundary_fraction"] != 0):
            failures.append(f"view{view}_flat_label_disagrees_with_pixels")
        if not np.array_equal(boundary, (np.abs(sdf) <= 1).astype(np.float32)):
            failures.append(f"view{view}_boundary_does_not_match_declared_sdf_band")
        recorded = metadata["core_stats"][view]
        if not math.isclose(recorded["foreground_fraction"], row["foreground_fraction"], abs_tol=1e-12) or recorded["boundary_pixels"] != int((np.abs(sdf) <= 1.5).sum()):
            failures.append(f"view{view}_recorded_core_statistics_mismatch")
    delta = metadata.get("exact_delta_xy")
    positions = np.asarray(metadata.get("view_shift_xy"), dtype=np.float64)
    if delta is None or positions.shape != (2, 2) or not np.allclose(positions[1] - positions[0], delta, atol=1e-12, rtol=0):
        failures.append("motion_delta_does_not_match_physical_positions")
    motion = motion_diagnostic(arrays["target"], arrays["sdf"], delta or [0, 0])
    if not flat and not identity and motion["target_expected_shift_rms"] >= motion["target_opposite_shift_rms"]:
        failures.append("actual_pair_motion_direction_disagrees_with_label")
    expected_order = ["evaluate_continuous_shifted_object_at_4x_cell_centers", "fixed_pair_psf_convolution", "sensor_area_integration", "independent_additive_sensor_noise", "uint8_quantization"]
    if metadata.get("rendering_order") != expected_order:
        failures.append("physical_render_order_not_explicit")
    ancestors = metadata.get("source_ancestors", [])
    if ancestors != [metadata.get("parent_latent_id")] or not ancestors or not ancestors[0].startswith("r125_procedural_"):
        failures.append("new_procedural_ancestry_not_explicit")
    if metadata.get("external_training_inputs") != [] or metadata.get("existing_test_answer_access") is not False:
        failures.append("external_or_test_answer_ancestry_not_excluded")
    result = {
        "target_area_integration": area_error,
        "operator_fit_all_core": fit,
        "operator_fit_per_view": view_fits,
        "source_minus_noiseless": noise,
        "sensor_saturation_fraction": float(((arrays["source"][core] == 0) | (arrays["source"][core] == 255)).mean()),
        "uniform_quantization_variance_approximation": 1 / (12 * 255**2),
        "declared_noise_variance": float(profile["noise_variance"]),
        "actual_added_noise_sigma_gray": actual_noise,
        "identity_exact": identity and not any(f.startswith("identity_") for f in failures),
        "geometry_actual_core": geometry, "motion": motion,
    }
    return result, failures


def legacy_findings() -> dict:
    """Bounded inspection, not a claim to audit every historical sample."""
    r118 = ROOT.parent / "R118_PhysicalCoordinateRepairScratch"
    r120 = ROOT.parent / "R120_PhysicalSequenceRepair"
    package = r118 / "data" / "package"
    manifest_path = package / "manifest.json"
    manifest = read_json(manifest_path)
    first = manifest["records"][0]
    first_shapes = {}
    for name in ("source_a", "source_b", "target_a", "target_b"):
        array = np.load(package / first[name], mmap_mode="r", allow_pickle=False)
        first_shapes[name] = {"shape": list(array.shape), "dtype": str(array.dtype)}
    selection = read_json(r118 / "reports" / "next_design_selected_ids.json")
    bank_path = r120 / "data" / "sequences" / "train" / "manifest.json"
    bank = read_json(bank_path)
    r61_launcher = ROOT.parent.parent / "LabSystem_MOSR" / "Experiments" / "R61_BoundaryGeneralizationUniversal" / "scripts" / "launch_r61.py"
    launcher = r61_launcher.read_text(encoding="utf-8-sig")
    return {
        "scope": "R118 manifest and one actual four-array record; R120 bank manifest/loader; R61 launcher, not whole historical datasets",
        "R118": {
            "manifest_sha256": sha256(manifest_path), "records": len(manifest["records"]),
            "first_record_actual_arrays": first_shapes, "first_record_pair_psfs_identical": first["psf_a"] == first["psf_b"],
            "stored_latent_target_2x_declared": "latent_target" in first,
            "directly_usable": False,
            "reason": "256px stored crops lack 640px genuine context and 1280px latent intensity truth; first pair uses different optics",
        },
        "R120": {
            "bank_manifest_sha256": sha256(bank_path), "physical_bank_scenes": len(bank["records"]),
            "base_probe_scenes": len(selection["probe_scene_ids"]),
            "all_base_probe_scenes_have_same_optics_sequence_bank": len(bank["records"]) == len(selection["probe_scene_ids"]),
            "directly_usable": False,
            "reason": "physical sequence order is repaired on a subset, but payload remains 256px and loader falls back for other scenes",
        },
        "R61": {
            "launcher_sha256": sha256(r61_launcher),
            "includes_sem_truth_anchor_role": "stage_36_r61_sem_truth_anchor" in launcher,
            "v16_teacher_checkpoint_declared": '"region_kd_teacher_checkpoint": R39_A970_BASE_CHECKPOINT' in launcher,
            "default_crop_256": 'parser.add_argument("--crop-size", type=int, default=256)' in launcher,
            "directly_usable": False,
            "reason": "SEM-truth and teacher ancestry conflict with source-disjoint pilot; legacy intensity targets lack current 2x optical contract",
        },
    }


def generator_source_review(generator: Path) -> dict:
    source = generator.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    read_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if name.endswith((".load", ".imread", ".read_text", ".read_bytes", ".open")) or name == "open":
                read_calls.append({"line": node.lineno, "call": name})
    return {
        "path": str(generator), "sha256": sha256(generator), "file_read_call_sites": read_calls,
        "note": "Call-site inventory supplements manual source review; absence of image reads alone is not a complete information-flow proof.",
    }


def audit_package(manifest_path: Path, output: Path, limit: int = 0) -> dict:
    if output.exists():
        raise FileExistsError(f"Preserve prior audit: {output}")
    torch.set_num_threads(2)
    manifest = read_json(manifest_path)
    base = manifest_path.parent
    records = manifest["scenes"]
    all_failures = []
    if manifest.get("scene_count") != len(records):
        all_failures.append("manifest_count_mismatch")
    if len({r["scene_id"] for r in records}) != len(records):
        all_failures.append("duplicate_scene_id")
    chosen = records[:limit or None]
    report = {
        "schema_version": 1, "utc": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path.resolve()), "manifest_sha256": sha256(manifest_path),
        "scope": "independent stored-array and model-fit audit; no training and no real calibration qualification",
        "screen_limits_fixed_before_measurement": LIMITS,
        "screen_interpretation": "RMS<=0.25 sigma limits extra mean-square discrepancy to 6.25% declared variance; p99<=1 sigma protects localized failures. Engineering screen, not physics theorem.",
        "package_scene_count": len(records), "audited_scene_count": len(chosen),
        "legacy": legacy_findings(), "scenes": [],
        "generator_source": generator_source_review(ROOT / "data" / "generator.py"),
    }
    source_hashes = {str(R124 / "model" / f): sha256(R124 / "model" / f) for f in ("observation.py", "calibration.py")}
    ancestors = []
    for index, record in enumerate(chosen):
        row = {"scene_id": record["scene_id"], "category": record["category"], "failures": []}
        try:
            arrays_path = confined_path(base, record["arrays_path"])
            metadata_path = confined_path(base, record["metadata_path"])
            expected = record["sha256"]
            row["hashes_match_manifest"] = sha256(arrays_path) == expected["arrays"] and sha256(metadata_path) == expected["metadata"]
            if not row["hashes_match_manifest"]:
                row["failures"].append("hash_mismatch")
            metadata = read_json(metadata_path)
            row["metadata"] = {k: metadata.get(k) for k in ("source_ancestors", "polarity", "photometry", "noise_sigma_gray", "rendering_order", "motion_observable", "core_stats")}
            ancestors.extend(metadata.get("source_ancestors", []))
            with np.load(arrays_path, allow_pickle=False) as saved:
                arrays = {key: saved[key] for key in saved.files}
            findings, failures = audit_arrays(arrays, metadata)
            row.update(findings)
            row["failures"].extend(failures)
            if index < 8:
                row["independent_4x_physical_patch"] = independent_physical_patch(arrays, metadata)
                for view in row["independent_4x_physical_patch"]["views"]:
                    if view["noiseless_error"]["max_abs"] > 1e-4 or view["target_error"]["max_abs"] > 1e-4:
                        row["failures"].append(f"independent_float64_physical_patch_view{view['view']}_differs_materially")
        except Exception as exc:
            row["failures"].append(f"{type(exc).__name__}: {exc}")
        report["scenes"].append(row)
        print(json.dumps({"audited": index + 1, "total": len(chosen), "scene": row["scene_id"], "failures": row["failures"]}), flush=True)
    source_unchanged = all(sha256(Path(path)) == digest for path, digest in source_hashes.items())
    if not source_unchanged:
        all_failures.append("R124_source_changed_during_audit")
    report["R124_immutable_source_hashes"] = source_hashes
    report["R124_sources_unchanged"] = source_unchanged
    report["ancestor_declarations"] = ancestors
    if len(ancestors) != len(set(ancestors)):
        all_failures.append("procedural_scene_ancestry_overlap")
    if manifest.get("source_kind") != "new_procedural_only" or manifest.get("external_training_inputs") != []:
        all_failures.append("manifest_procedural_only_ancestry_not_explicit")
    if manifest.get("generator_sha256") != report["generator_source"]["sha256"]:
        all_failures.append("generator_source_does_not_match_package")
    admission_path = ROOT / "config" / "data_admission.json"
    report["admission_contract_sha256"] = sha256(admission_path)
    report["physical_order_source_review"] = {
        "reviewed_source_sha256": report["generator_source"]["sha256"],
        "findings": [
            "Each view evaluates analytic foreground and moving texture at coordinates shifted by its recorded physical displacement.",
            "Optics are specified once before the view loop and applied at 4x, followed by area integration, independent noise, and quantization.",
            "Physical context beyond the 640px sensor domain is generated to the PSF support; it is not padding of a 256px historical crop.",
            "The only file reads in the reviewed generator hash its own source or its newly written package files; there are no microscope, SEM, model-teacher, or old-dataset inputs.",
            "SDF is a raster EDT approximation, not exact continuous distance; polarity and geometry are independently checked from stored intensity.",
            "All validation conclusions refer to this reviewed source identity; no general guarantee for future modified generators is implied."
        ]
    }
    report["global_failures"] = all_failures
    report["scene_failure_counts"] = dict(Counter(failure for row in report["scenes"] for failure in row["failures"]))
    successful = [row for row in report["scenes"] if "operator_fit_all_core" in row]
    strata = defaultdict(list)
    for row in successful:
        polarity = row["metadata"].get("polarity")
        key = f"{row['category']}|polarity={polarity}"
        if "flat" in row["category"]:
            key += "|" + ("bright" if np.mean([v["target_mean"] for v in row["geometry_actual_core"]]) >= 0.5 else "dark")
        strata[key].append(row)
    report["strata"] = {
        key: {"scenes": len(rows), "worst_rms_gray": max(v["rms_gray"] for r in rows for v in r["operator_fit_per_view"]),
              "worst_rms_over_sigma": max(r["operator_fit_all_core"]["rms_over_declared_sigma"] for r in rows),
              "worst_p99_over_sigma": max(v["p99_abs_over_declared_sigma"] for r in rows for v in r["operator_fit_per_view"])}
        for key, rows in strata.items()
    }
    report["admissible_for_bounded_pipeline_pilot_by_numerical_screen"] = not all_failures and not report["scene_failure_counts"] and len(chosen) == len(records)
    report["pilot_admitted"] = report["admissible_for_bounded_pipeline_pilot_by_numerical_screen"]
    report["real_applicability"] = "unproven; simulated fixed optics is not independent real-instrument calibration, and pipeline admission is not a usefulness verdict"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "data_audit_v1.json")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    result = audit_package(args.manifest, args.output, args.limit)
    print(json.dumps({"output": str(args.output), "admissible_numerical_screen": result["admissible_for_bounded_pipeline_pilot_by_numerical_screen"], "failures": result["scene_failure_counts"]}))
    raise SystemExit(0 if result["admissible_for_bounded_pipeline_pilot_by_numerical_screen"] else 2)
