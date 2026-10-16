"""R74 upper-bound probe for a constrained boundary-profile action.

This is a frozen, non-deployable causal intervention.  It asks whether the
R114 action library is missing a local contrast/profile operation after width
and normal-shift actions have proved insufficient.  Synthetic truth may choose
the geometry and reliability of the action, but it can never be copied to the
output.  The renderer is restricted to a signed-distance tanh profile with
five bounded parameter fields and acts only in a narrow boundary band.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import cv2
import numpy as np
import pandas as pd


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SOURCE = Path(
    r"D:\GMM_2_Final\Experiments\R74_R61HardMicroscopyACMGeneralization"
    r"\data\r74_hard_acm_val"
)
TEMPLATE = Path(
    r"D:\GMM_2_Final\Experiments\R104_PhotometricInvariantCausalGateScratch"
    r"\results\posttraining_validation\external_acm\R74_hard_microscopy"
    r"\config\experiment.json"
)
FULL_ROOT = ROOT / "results" / "geometry_probe" / "E020" / "r74_interventions" / "inputs" / "Full"
CHECKPOINT = ROOT / "runs" / "r114_geometry_probe_scratch_20260830" / "weights" / "epoch_020.pth"
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
R82 = Path(r"D:\GMM_2_Final\Experiments\R82_R39R40CrossSceneGeneralizationBenchmark\scripts")

METHODS = ("Full", "FullPlusProfile")
FAILURE_FAMILIES = ("boundary_fade", "low_contrast", "mixed_hard")
PRESERVE_FAMILIES = ("asymmetric_blur_halo", "uneven_illumination")

# Frozen before the locked ACM run.  These are action-capacity limits, not
# values fitted from ACM results.
PROFILE_WIDTH_PX = 1.35
FULL_STRENGTH_RADIUS_PX = 10.0
OUTER_BAND_RADIUS_PX = 14.0
PLATEAU_SAMPLE_DISTANCES_PX = (8.0, 12.0, 16.0)
MAXIMUM_ACTION_GRAY = 48.0
CONTRAST_FLOOR_FRACTION = 0.85
CONTRAST_CEILING_FRACTION = 1.20
RELIABILITY_ERROR_SIGMA_PX = 3.0
RELIABILITY_FEATHER_SIGMA_PX = 1.5


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: str | Path) -> np.ndarray:
    path = Path(path)
    value = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(f"cannot read {path}")
    return value.astype(np.float32) / 255.0


def write_gray(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    byte = np.rint(np.clip(value, 0.0, 1.0) * 255.0).astype(np.uint8)
    ok, encoded = cv2.imencode(".bmp", byte)
    if not ok:
        raise RuntimeError(f"cannot encode {path}")
    encoded.tofile(path)


def signed_distance(mask: np.ndarray) -> np.ndarray:
    """Signed pixel-center distance, positive inside, zero between pixels."""
    inside = mask > 0.5
    inside_distance = cv2.distanceTransform(inside.astype(np.uint8), cv2.DIST_L2, 5)
    outside_distance = cv2.distanceTransform((~inside).astype(np.uint8), cv2.DIST_L2, 5)
    return np.where(inside, inside_distance - 0.5, -(outside_distance - 0.5)).astype(np.float32)


def sdf_normals(sdf: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    gx = cv2.Sobel(sdf, cv2.CV_32F, 1, 0, ksize=3, borderType=cv2.BORDER_REFLECT) / 8.0
    gy = cv2.Sobel(sdf, cv2.CV_32F, 0, 1, ksize=3, borderType=cv2.BORDER_REFLECT) / 8.0
    magnitude = np.sqrt(gx * gx + gy * gy + 1.0e-8)
    return (gx / magnitude).astype(np.float32), (gy / magnitude).astype(np.float32)


def remap(value: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return cv2.remap(
        value.astype(np.float32),
        x.astype(np.float32),
        y.astype(np.float32),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def local_plateaus(raw: np.ndarray, sdf: np.ndarray, nx: np.ndarray, ny: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sample two local plateaus from the nearest boundary along its normal."""
    height, width = raw.shape
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    boundary_x = xx - nx * sdf
    boundary_y = yy - ny * sdf
    inside_samples = []
    outside_samples = []
    for distance in PLATEAU_SAMPLE_DISTANCES_PX:
        inside_samples.append(remap(raw, boundary_x + nx * distance, boundary_y + ny * distance))
        outside_samples.append(remap(raw, boundary_x - nx * distance, boundary_y - ny * distance))
    return (
        np.median(np.stack(inside_samples, axis=0), axis=0).astype(np.float32),
        np.median(np.stack(outside_samples, axis=0), axis=0).astype(np.float32),
    )


def cosine_band(sdf: np.ndarray) -> np.ndarray:
    distance = np.abs(sdf)
    gate = np.ones_like(sdf, np.float32)
    transition = (distance > FULL_STRENGTH_RADIUS_PX) & (distance < OUTER_BAND_RADIUS_PX)
    phase = (distance[transition] - FULL_STRENGTH_RADIUS_PX) / (
        OUTER_BAND_RADIUS_PX - FULL_STRENGTH_RADIUS_PX
    )
    gate[transition] = 0.5 * (1.0 + np.cos(np.pi * phase))
    gate[distance >= OUTER_BAND_RADIUS_PX] = 0.0
    return gate


def robust_class_median(value: np.ndarray, region: np.ndarray) -> float:
    selected = value[region]
    if selected.size < 64:
        selected = value.reshape(-1)
    return float(np.median(selected))


def aligned_clean_reference(raw: np.ndarray, label: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Radiometrically align clean truth without moving its known edge."""
    inside = mask > 0.5
    kernel = np.ones((9, 9), np.uint8)
    deep_inside = cv2.erode(inside.astype(np.uint8), kernel) > 0
    deep_outside = cv2.erode((~inside).astype(np.uint8), kernel) > 0
    raw_fg = robust_class_median(raw, deep_inside)
    raw_bg = robust_class_median(raw, deep_outside)
    label_fg = robust_class_median(label, deep_inside)
    label_bg = robust_class_median(label, deep_outside)
    denominator = label_fg - label_bg
    if abs(denominator) < 2.0 / 255.0:
        return label.astype(np.float32)
    return np.clip(raw_bg + (label - label_bg) * ((raw_fg - raw_bg) / denominator), 0, 1).astype(np.float32)


def render_from_parameters(
    full: np.ndarray,
    sdf: np.ndarray,
    midpoint: np.ndarray,
    signed_contrast: np.ndarray,
    width: np.ndarray,
    visibility: np.ndarray,
) -> np.ndarray:
    """Pointwise analytic renderer.  It has no free pixel residual path."""
    profile = midpoint + 0.5 * signed_contrast * np.tanh(sdf / np.maximum(width, 0.5))
    bounded_delta = np.clip(profile - full, -MAXIMUM_ACTION_GRAY / 255.0, MAXIMUM_ACTION_GRAY / 255.0)
    return np.clip(full + visibility * bounded_delta, 0.0, 1.0).astype(np.float32)


def build_oracle_action(
    raw: np.ndarray,
    full: np.ndarray,
    label: np.ndarray,
    mask: np.ndarray,
    record: dict,
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, float]]:
    """Build the bounded profile proposal and a truth-only reliability map."""
    sdf = signed_distance(mask)
    nx, ny = sdf_normals(sdf)
    inside_plateau, outside_plateau = local_plateaus(raw, sdf, nx, ny)
    midpoint = 0.5 * (inside_plateau + outside_plateau)

    polarity = 1.0 if str(record["polarity"]) == "bright" else -1.0
    nominal_contrast = float(record["contrast_abs"]) / 255.0
    observed_contrast = np.abs(inside_plateau - outside_plateau)
    contrast = np.clip(
        observed_contrast,
        CONTRAST_FLOOR_FRACTION * nominal_contrast,
        CONTRAST_CEILING_FRACTION * nominal_contrast,
    ).astype(np.float32)
    signed_contrast = (polarity * contrast).astype(np.float32)
    width = np.full_like(raw, PROFILE_WIDTH_PX, np.float32)
    band = cosine_band(sdf)

    all_visible = band
    proposal = render_from_parameters(full, sdf, midpoint, signed_contrast, width, all_visible)
    reference = aligned_clean_reference(raw, label, mask)
    full_error = cv2.GaussianBlur(
        np.abs(full - reference), (0, 0), RELIABILITY_ERROR_SIGMA_PX, borderType=cv2.BORDER_REFLECT
    )
    proposal_error = cv2.GaussianBlur(
        np.abs(proposal - reference), (0, 0), RELIABILITY_ERROR_SIGMA_PX, borderType=cv2.BORDER_REFLECT
    )
    gain = full_error - proposal_error
    hard_reliable = ((gain > 0.0) & (band > 0.0)).astype(np.float32)
    reliability = cv2.GaussianBlur(
        hard_reliable,
        (0, 0),
        RELIABILITY_FEATHER_SIGMA_PX,
        borderType=cv2.BORDER_REFLECT,
    )
    visibility = np.clip(reliability * band, 0.0, 1.0).astype(np.float32)
    output = render_from_parameters(full, sdf, midpoint, signed_contrast, width, visibility)

    active = band > 0.0
    outside = ~active
    delta = output - full
    stats = {
        "band_fraction": float(active.mean()),
        "reliable_fraction_in_band": float(hard_reliable[active].mean()),
        "visibility_mean_in_band": float(visibility[active].mean()),
        "median_gain_gray_in_band": float(np.median(gain[active]) * 255.0),
        "mean_abs_change_gray": float(np.mean(np.abs(delta)) * 255.0),
        "p99_abs_change_gray": float(np.quantile(np.abs(delta), 0.99) * 255.0),
        "maximum_abs_change_gray": float(np.max(np.abs(delta)) * 255.0),
        "maximum_outside_band_change_gray": float(np.max(np.abs(delta[outside])) * 255.0 if outside.any() else 0.0),
        "midpoint_min_gray": float(midpoint.min() * 255.0),
        "midpoint_max_gray": float(midpoint.max() * 255.0),
        "contrast_median_gray": float(np.median(contrast[active]) * 255.0),
        "profile_width_px": PROFILE_WIDTH_PX,
    }
    maps = {
        "sdf": sdf,
        "normal_x": nx,
        "normal_y": ny,
        "midpoint": midpoint,
        "signed_contrast": signed_contrast,
        "profile_width": width,
        "boundary_band": band,
        "reliability": reliability,
        "visibility": visibility,
        "proposal": proposal,
        "output": output,
    }
    return output, maps, stats


def save_maps(stage: str, filename: str, maps: dict[str, np.ndarray]) -> None:
    base = OUT / "maps" / stage / Path(filename).stem
    base.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(base / "profile_parameters.npz", **maps)
    display = {
        "boundary_band": maps["boundary_band"],
        "visibility": maps["visibility"],
        "reliability": maps["reliability"],
        "signed_contrast": 0.5 + 0.5 * maps["signed_contrast"] / max(CONTRAST_CEILING_FRACTION * 60.0 / 255.0, 1e-6),
        "midpoint": maps["midpoint"],
    }
    for name, value in display.items():
        write_gray(base / f"{name}.bmp", np.clip(value, 0.0, 1.0))


def generate(records: list[dict]) -> tuple[pd.DataFrame, dict[str, Path], float]:
    roots = {name: OUT / "inputs" / name for name in METHODS}
    rows: list[dict] = []
    maximum_full_copy_error = 0.0
    for index, record in enumerate(records, 1):
        stage = str(record["stage"])
        filename = str(record["filename"])
        raw = read_gray(record["src"])
        label = read_gray(record["lbl"])
        mask = read_gray(record["mask"])
        source_full = FULL_ROOT / stage / filename
        full = read_gray(source_full)
        output, maps, stats = build_oracle_action(raw, full, label, mask, record)

        full_destination = roots["Full"] / stage / filename
        full_destination.parent.mkdir(parents=True, exist_ok=True)
        if not full_destination.exists():
            shutil.copy2(source_full, full_destination)
        copied = read_gray(full_destination)
        maximum_full_copy_error = max(maximum_full_copy_error, float(np.max(np.abs(copied - full)) * 255.0))
        write_gray(roots["FullPlusProfile"] / stage / filename, output)
        save_maps(stage, filename, maps)
        rows.append(
            {
                "image_id": record["image_id"],
                "family": record["family"],
                "shape_family": record["shape_family"],
                "polarity": record["polarity"],
                **stats,
            }
        )
        if index % 10 == 0:
            print(json.dumps({"stage": "profile_generation", "done": index, "total": len(records)}), flush=True)

    table = pd.DataFrame(rows)
    tables = OUT / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    table.to_csv(tables / "profile_action_per_image.csv", index=False, encoding="utf-8-sig")
    table.groupby("family", as_index=False).median(numeric_only=True).to_csv(
        tables / "profile_action_by_family.csv", index=False, encoding="utf-8-sig"
    )
    return table, roots, maximum_full_copy_error


def prepare_contract(roots: dict[str, Path]) -> tuple[Path, int, int]:
    contract = OUT / "locked_acm_contract"
    config = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    config["experiment_id"] = "R114_R74_E020_BoundedProfileActionUpperBound"
    config["dataset"]["root"] = str(SOURCE)
    config_path = contract / "config" / "experiment.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    methods = ["Raw", *METHODS]
    directories = {name: {} for name in methods}
    for family in config["dataset"]["families"]:
        name, stage = str(family["name"]), str(family["stage"])
        directories["Raw"][name] = str(SOURCE / "src" / stage)
        for method, root in roots.items():
            directories[method][name] = str(root / stage)
    manifest = contract / "results" / "inference_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps({"suite": "R74", "methods": methods, "output_dirs": directories}, indent=2),
        encoding="utf-8",
    )
    primary_count = int(config["dataset"]["total_images"]) * len(methods) * 2
    sensitivity_count = (
        len(config["dataset"]["families"])
        * len(config["acm"]["sensitivity_filenames"])
        * len(config["acm"]["sensitivity_presets"])
        * len(methods)
    )
    return contract, primary_count, sensitivity_count


def acm_complete(contract: Path, primary_count: int, sensitivity_count: int) -> bool:
    tables = contract / "results" / "tables"
    primary = tables / "primary_contour_metrics.csv"
    sensitivity = tables / "acm_sensitivity_metrics.csv"
    return (
        primary.is_file()
        and sensitivity.is_file()
        and len(pd.read_csv(primary)) == primary_count
        and len(pd.read_csv(sensitivity)) == sensitivity_count
    )


def run_locked_acm(contract: Path, primary_count: int, sensitivity_count: int) -> None:
    if acm_complete(contract, primary_count, sensitivity_count):
        return
    expression = f"addpath('{R82.as_posix()}'); run_acm_multimethod('{contract.as_posix()}')"
    result = subprocess.run(
        [str(MATLAB), "-batch", expression],
        cwd=contract,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log = contract / "logs" / "matlab_acm.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not acm_complete(contract, primary_count, sensitivity_count):
        raise RuntimeError(f"locked ACM failed; inspect {log}")


def summarize(contract: Path, action_table: pd.DataFrame, maximum_full_copy_error: float) -> dict:
    primary = pd.read_csv(contract / "results" / "tables" / "primary_contour_metrics.csv")
    translated = primary.loc[primary["alignment"].eq("translation_only")].copy()
    metrics = ["iou", "mean_boundary_distance_px", "hd95_px", "area_error_pct", "perimeter_error_pct"]
    overall = translated.groupby("method", as_index=False)[metrics].median()
    family = translated.groupby(["method", "family"], as_index=False)[metrics].median()
    overall.to_csv(OUT / "tables" / "locked_acm_overall.csv", index=False, encoding="utf-8-sig")
    family.to_csv(OUT / "tables" / "locked_acm_by_family.csv", index=False, encoding="utf-8-sig")

    overall_index = overall.set_index("method")
    family_index = family.set_index(["method", "family"])
    raw = overall_index.loc["Raw"]
    models: dict[str, dict] = {}
    for method in METHODS:
        current = overall_index.loc[method]
        families = []
        for name in sorted(translated["family"].unique()):
            before = family_index.loc[("Raw", name)]
            after = family_index.loc[(method, name)]
            families.append(
                {
                    "family": name,
                    "boundary_distance_px": float(after["mean_boundary_distance_px"]),
                    "boundary_change_vs_raw_pct": float((after["mean_boundary_distance_px"] / before["mean_boundary_distance_px"] - 1.0) * 100.0),
                    "hd95_change_vs_raw_pct": float((after["hd95_px"] / before["hd95_px"] - 1.0) * 100.0),
                    "iou": float(after["iou"]),
                    "iou_delta_vs_raw": float(after["iou"] - before["iou"]),
                }
            )
        models[method] = {
            "metrics": {key: float(current[key]) for key in metrics},
            "boundary_change_vs_raw_pct": float((current["mean_boundary_distance_px"] / raw["mean_boundary_distance_px"] - 1.0) * 100.0),
            "hd95_change_vs_raw_pct": float((current["hd95_px"] / raw["hd95_px"] - 1.0) * 100.0),
            "iou_delta_vs_raw": float(current["iou"] - raw["iou"]),
            "families": families,
        }

    full = {row["family"]: row for row in models["Full"]["families"]}
    profile = {row["family"]: row for row in models["FullPlusProfile"]["families"]}
    failure_improvement = {
        name: {
            "boundary_better_than_full": profile[name]["boundary_distance_px"] < full[name]["boundary_distance_px"],
            "iou_better_than_full": profile[name]["iou"] > full[name]["iou"],
            "beats_raw_on_both": profile[name]["boundary_change_vs_raw_pct"] < 0.0 and profile[name]["iou_delta_vs_raw"] >= 0.0,
        }
        for name in FAILURE_FAMILIES
    }
    preserve = {
        name: {
            "remains_better_than_raw_on_both": profile[name]["boundary_change_vs_raw_pct"] < 0.0 and profile[name]["iou_delta_vs_raw"] >= 0.0,
            "not_worse_than_full_boundary": profile[name]["boundary_distance_px"] <= full[name]["boundary_distance_px"] * 1.0025,
            "not_worse_than_full_iou": profile[name]["iou"] >= full[name]["iou"] - 0.0005,
        }
        for name in PRESERVE_FAMILIES
    }
    action_family = action_table.groupby("family", as_index=False).median(numeric_only=True).to_dict(orient="records")
    conclusion = {
        "new_action_repairs_all_three_failure_families_over_full": bool(
            all(value["boundary_better_than_full"] and value["iou_better_than_full"] for value in failure_improvement.values())
        ),
        "all_three_failure_families_beat_raw_on_both": bool(
            all(value["beats_raw_on_both"] for value in failure_improvement.values())
        ),
        "halo_and_uneven_preserved": bool(
            all(all(value.values()) for value in preserve.values())
        ),
        "action_library_capacity_supported": bool(
            all(value["boundary_better_than_full"] and value["iou_better_than_full"] for value in failure_improvement.values())
            and all(all(value.values()) for value in preserve.values())
        ),
        "oracle_upper_bound_only": True,
        "deployable_model_claim": False,
    }
    payload = {
        "status": "complete",
        "purpose": "test whether a bounded local boundary-profile action adds missing capacity beyond width and normal shift",
        "protocol": "frozen E20 Full plus fixed bounded profile action; locked R74 Chan-Vese ACM; translation-only primary",
        "truth_usage": (
            "R74 mask supplies oracle SDF geometry and clean label supplies only a smoothed binary reliability choice "
            "between Full and one fixed analytic proposal. No target pixels are rendered and no weights are updated."
        ),
        "renderer_contract": {
            "free_pixel_residual": False,
            "direct_target_output": False,
            "local_analytic_operation": True,
            "parameter_fields": ["signed_distance", "midpoint", "signed_plateau_contrast", "profile_width", "visibility"],
            "profile": "midpoint + 0.5 * signed_contrast * tanh(sdf / width)",
            "full_strength_radius_px": FULL_STRENGTH_RADIUS_PX,
            "outer_band_radius_px": OUTER_BAND_RADIUS_PX,
            "maximum_action_gray": MAXIMUM_ACTION_GRAY,
            "profile_width_px": PROFILE_WIDTH_PX,
            "plateau_sample_distances_px": list(PLATEAU_SAMPLE_DISTANCES_PX),
            "tile_safe_given_local_parameter_maps": True,
        },
        "checkpoint": str(CHECKPOINT),
        "checkpoint_sha256": sha256(CHECKPOINT),
        "source_manifest_sha256": sha256(SOURCE / "manifest.json"),
        "maximum_full_copy_error_gray": maximum_full_copy_error,
        "models": models,
        "action_statistics_by_family": action_family,
        "failure_family_tests": failure_improvement,
        "preservation_family_tests": preserve,
        "acm_failures": primary.groupby("method")["acm_success"].apply(lambda values: int((~values.astype(bool)).sum())).to_dict(),
        "conclusion": conclusion,
    }
    (OUT / "analysis_summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def write_training_design(payload: dict) -> None:
    lines = [
        "# R114 Boundary Profile Action: Trainable Design",
        "",
        "## Causal result",
        "",
        f"- Action-library capacity supported: **{payload['conclusion']['action_library_capacity_supported']}**",
        f"- Repairs all three failure families over frozen Full: **{payload['conclusion']['new_action_repairs_all_three_failure_families_over_full']}**",
        f"- Preserves halo and uneven families: **{payload['conclusion']['halo_and_uneven_preserved']}**",
        "- This probe is an oracle upper bound and is not deployable.",
        "",
        "## Allowed runtime action",
        "",
        "Keep the existing local SDF and normal controller. Add one profile head with four bounded maps: midpoint offset, signed plateau contrast, profile width, and visibility/reliability. The renderer remains analytic:",
        "",
        "`profile = midpoint + 0.5 * signed_contrast * tanh(sdf / width)`",
        "",
        "Blend this proposal only inside a predicted narrow boundary band. Do not add a free RGB/gray residual branch.",
        "",
        "## Synthetic targets",
        "",
        "1. SDF and normal: exact mask-derived geometry already used by the controller.",
        "2. Midpoint: robust median of clean inside/outside normal-profile plateaus, expressed as an offset from the same raw-derived local midpoint cue used at inference.",
        "3. Signed contrast: clean plateau difference, polarity preserving, clipped to the renderer range.",
        "4. Width: robust 10-to-90 percent transition width fitted along the clean SDF normal; clamp to the analytic renderer range.",
        "5. Visibility target: one only where the bounded analytic profile has lower locally smoothed truth error than identity/geometry Full; zero elsewhere. Store it as a soft, feathered map.",
        "6. Reliability target: down-weight ambiguous normal samples, crossed plateaus, low signed contrast, and places where several shapes are inside one sampling radius.",
        "",
        "## Heads and bounds",
        "",
        "- midpoint_offset_gray: tanh bound, recommended +/-24 gray levels.",
        "- signed_contrast_gray: polarity-preserving, recommended magnitude 4-72 gray levels.",
        "- profile_width_px: sigmoid bound, recommended 0.8-3.5 px.",
        "- profile_visibility: sigmoid 0-1, multiplied by boundary confidence, correction need, and recoverability.",
        "- analytic action delta: retain a hard maximum of 48 gray levels and the 14 px outer band until a second ablation justifies relaxing either bound.",
        "",
        "## Losses and schedule",
        "",
        "- Parameter losses: masked smooth-L1 for midpoint, signed contrast, and width; each normalized per image before the batch mean.",
        "- Visibility/reliability: focal BCE plus soft Dice in the boundary band; identity/clear samples explicitly target zero action.",
        "- Profile loss: contrast-normalized 1D normal-profile loss at fixed distances, including transition midpoint and 10/50/90 percent positions.",
        "- Physical guards: polarity consistency, monotonicity, no overshoot beyond predicted plateaus, zero action outside the band, and local-mean preservation outside the transition.",
        "- Train the controller first. Then train the profile heads with the controller frozen or at a much lower learning rate. Only after both pass should a short joint stage be attempted.",
        "- Alternate geometry and profile batches; do not simply add every objective into one permanent weighted sum.",
        "",
        "## Required gate before formal training",
        "",
        "A learned head must reproduce the oracle direction on a sealed synthetic split, preserve clear/flat identity, pass two-origin tile parity, and improve all three R74 failure families without losing the halo and uneven gains. The current oracle result only authorizes a learned profile-head probe, not a formal R114 model.",
    ]
    (OUT / "TRAINABLE_HEAD_TARGET_LOSS_DESIGN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readme(payload: dict) -> None:
    full = {row["family"]: row for row in payload["models"]["Full"]["families"]}
    profile = {row["family"]: row for row in payload["models"]["FullPlusProfile"]["families"]}
    lines = [
        "# R74 E20 Bounded Boundary-Profile Action Probe",
        "",
        "Frozen causal upper bound only. No model or training file was changed and no weight was updated.",
        "The intervention can only render a bounded tanh profile from five parameter maps inside a 14 px boundary band.",
        "",
        "| family | Full boundary vs Raw | Full+Profile boundary vs Raw | Full IoU delta | Full+Profile IoU delta |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in sorted(full):
        lines.append(
            f"| {name} | {full[name]['boundary_change_vs_raw_pct']:.3f}% | "
            f"{profile[name]['boundary_change_vs_raw_pct']:.3f}% | "
            f"{full[name]['iou_delta_vs_raw']:.6f} | {profile[name]['iou_delta_vs_raw']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Repairs all three failed families over Full: **{payload['conclusion']['new_action_repairs_all_three_failure_families_over_full']}**",
            f"- Preserves halo and uneven illumination: **{payload['conclusion']['halo_and_uneven_preserved']}**",
            f"- Supports adding the action library: **{payload['conclusion']['action_library_capacity_supported']}**",
            "",
            "See `analysis_summary.json`, `representative_montage.png`, `tables/`, and `TRAINABLE_HEAD_TARGET_LOSS_DESIGN.md`.",
        ]
    )
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    for required in (SOURCE / "manifest.json", TEMPLATE, CHECKPOINT, MATLAB):
        if not required.is_file():
            raise FileNotFoundError(required)
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    if len(manifest["records"]) != 100:
        raise RuntimeError("locked R74 contract must contain exactly 100 records")
    checkpoint_hash_before = sha256(CHECKPOINT)
    action_table, roots, maximum_full_copy_error = generate(manifest["records"])
    contract, primary_count, sensitivity_count = prepare_contract(roots)
    run_locked_acm(contract, primary_count, sensitivity_count)
    if sha256(CHECKPOINT) != checkpoint_hash_before:
        raise RuntimeError("frozen checkpoint changed during probe")
    payload = summarize(contract, action_table, maximum_full_copy_error)
    write_training_design(payload)
    write_readme(payload)
    print(json.dumps(payload["conclusion"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
