"""Validate the authorized R91 design before any generated payload is used."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
GATES_PATH = ROOT / "config" / "acceptance_gates.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_design(design: dict[str, Any], gates: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    experiment_id = "R91_DetailDecoupledScratch"
    if design.get("experiment_id") != experiment_id or gates.get("experiment_id") != experiment_id:
        errors.append("Experiment identifiers do not match R91.")
    if design.get("status") != "authorized_for_one_clean_formal_run" or int(design["training"].get("formal_runs_authorized", 0)) != 1:
        errors.append("Exactly one clean formal run must be authorized.")

    isolation = design["source_isolation"]
    forbidden_true = (
        "checkpoint_loading_allowed", "resume_allowed", "teacher_models_allowed", "pseudo_labels_allowed",
        "sem_pixels_allowed", "sem_structure_allowed", "hs100mg_structure_allowed",
        "real_sample_pixels_stored_as_training_pairs", "real_sample_contours_allowed",
    )
    for key in forbidden_true:
        if isolation.get(key):
            errors.append(f"Forbidden training source is enabled: {key}")
    if not isolation.get("procedural_latent_truth_required") or not isolation.get("allowed_real_optical_statistics"):
        errors.append("Procedural truth and aggregate-only optical statistics must remain explicit.")

    architecture = design["architecture"]
    output = architecture["output"]
    if any(architecture.get(key) for key in ("spatial_reduction_normalization", "global_pooling", "global_fft_or_wiener")):
        errors.append("A tile-unsafe global or spatial-normalization operation is enabled.")
    if not architecture["tile_contract"].get("same_code_path_for_full_and_tiled"):
        errors.append("Full and tiled inference must share one path.")
    if output.get("binary_confidence_gate") or not output.get("direct_residual") or output.get("adversarial_or_generative_prior"):
        errors.append("R91 must remain a direct, non-generative residual reconstruction model.")
    if not output.get("low_frequency_branch_is_quarter_resolution_lowpass"):
        errors.append("The low-frequency branch must be physically low-pass constrained.")
    if not output.get("detail_branch_is_multiscale_zero_dc") or len(output.get("detail_bands", [])) < 2:
        errors.append("R91 detail recovery must use multiple zero-DC bands.")

    dataset = design["dataset"]
    roles = dataset["roles"]
    for split_key, expected_key in (("train", "train_scenes"), ("validation", "validation_scenes"), ("internal_test", "internal_test_scenes")):
        observed = sum(int(role[split_key]) for role in roles.values())
        expected = int(dataset["split_counts"][expected_key])
        if observed != expected:
            errors.append(f"Role split mismatch for {split_key}: {observed} != {expected}")
    if sum(int(role["total"]) for role in roles.values()) != int(dataset["scene_count"]):
        errors.append("Role scene totals do not match the declared scene count.")
    for name, role in roles.items():
        if sum(int(role[key]) for key in ("train", "validation", "internal_test")) != int(role["total"]):
            errors.append(f"Role split total is invalid: {name}")
    expected_observations = int(dataset["scene_count"]) * int(dataset["observations_per_scene"])
    if expected_observations != int(dataset["total_observations"]):
        errors.append("Scene and observation totals disagree.")
    if sum(int(value) for value in dataset["degradation_observation_quotas"].values()) != expected_observations:
        errors.append("Degradation quotas do not cover every observation.")
    if int(dataset.get("label_supersample_factor", 0)) < 8 or dataset.get("geometry_downsample") != "area_average":
        errors.append("Labels must be drawn at 8x or more and antialiased by area reduction.")
    exposure_path = dataset.get("continuous_exposure_path", {})
    if len(exposure_path.get("labels", [])) != 4 or len(set(exposure_path.get("labels", []))) != 4:
        errors.append("Exactly four distinct continuous exposure path labels are required.")
    if float(exposure_path.get("minimum_exposure_span", 0.0)) < 0.35 or not exposure_path.get("mid_transition_required"):
        errors.append("The continuous exposure path does not cover the transition region.")
    pairing = dataset.get("pairing", {})
    if not pairing.get("cross_observation_same_crop_required") or float(pairing.get("exposure_bundle_four_view_fraction", 0)) != 1.0:
        errors.append("Exposure bundles must always use all four views at the same crop origin.")
    recoverability = dataset["recoverability_contract"]
    if float(recoverability["maximum_source_target_gap"]) > float(recoverability["model_combined_bound"]):
        errors.append("Synthetic corruption exceeds the model correction range.")
    if float(recoverability.get("minimum_global_degradation_scale", 0.0)) < 0.30:
        errors.append("A degradation may be weakened too far during recoverability repair.")

    training = design["training"]
    covered: list[int] = []
    for stage in training["stages"]:
        covered.extend(range(int(stage["epoch_start"]), int(stage["epoch_end"]) + 1))
        if int(stage["scene_batch_size"]) * int(stage["gradient_accumulation"]) != int(stage["effective_scene_batch"]):
            errors.append(f"Effective batch mismatch in stage beginning {stage['epoch_start']}")
        for patch_key, core_key in (("patch_size", "core_size"), ("alternate_patch_size", "alternate_core_size")):
            if patch_key not in stage:
                continue
            patch, core = int(stage[patch_key]), int(stage[core_key])
            if patch < core or (patch - core) % 2 or patch % 8 or core % 8:
                errors.append(f"Invalid patch/core pair in stage beginning {stage['epoch_start']}")
    if covered != list(range(1, int(training["epochs"]) + 1)):
        errors.append(f"Training stages must cover epochs 1 through {training['epochs']} exactly once.")
    anchors = training.get("curriculum_anchors", [])
    anchor_epochs = [int(row["epoch"]) for row in anchors]
    if not anchors or anchor_epochs[0] != 1 or anchor_epochs[-1] != int(training["epochs"]) or anchor_epochs != sorted(set(anchor_epochs)):
        errors.append(f"Smooth curriculum anchors must begin at epoch 1 and end at epoch {training['epochs']}.")
    for row in anchors:
        for key, value in row.items():
            upper = 1.25 if key == "detail_factor" else 1.0
            if key != "epoch" and not 0.0 <= float(value) <= upper:
                errors.append(f"Curriculum factor out of range: {key}")
    required_losses = {"cross_observation_consistency", "bundle_soft_tail", "low_branch_edge_leakage", "low_branch_target", "detail_branch_target", "detail_halo", "region_relationship", "overlap_tile_consistency", "signed_displacement"}
    if not required_losses.issubset(training["loss_weights"]):
        errors.append("One or more R91 supervision terms are missing.")
    selection = training["checkpoint_selection"]
    if selection.get("hard_metric_rejection") or not selection.get("diagnostics_are_reported_not_used_as_binary_gates"):
        errors.append("Checkpoint selection must remain continuous rather than gate-driven.")
    if gates.get("checkpoint_selection_uses_hard_rejection"):
        errors.append("Diagnostic references must not become hard checkpoint gates.")

    holdout = dataset["holdout"]
    if not holdout.get("manifest_hash_before_training") or not holdout.get("unread_until_checkpoint_frozen"):
        errors.append("The independent holdout must be sealed before training.")
    required_files = (
        ROOT / "model" / "r91_model.py", ROOT / "training" / "train_r91.py",
        ROOT / "inference" / "reconstruct.py", ROOT / "scripts" / "generate_dataset.py",
        ROOT / "scripts" / "benchmark_r91.py", ROOT / "scripts" / "launch_r91.py",
        ROOT / "config" / "optical_statistics.json",
    )
    for path in required_files:
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"Missing required file: {path.name}")
    if len(list((ROOT / "data" / "live_validation").glob("*.bmp"))) != 4:
        errors.append("Exactly four fixed live-validation images are required.")
    return errors


def main() -> int:
    design = load_json(DESIGN_PATH)
    gates = load_json(GATES_PATH)
    errors = validate_design(design, gates)
    payload = {
        "experiment_id": design.get("experiment_id"),
        "passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "scene_count": design["dataset"]["scene_count"],
        "total_observations": design["dataset"]["total_observations"],
        "formal_runs_authorized": design["training"]["formal_runs_authorized"],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
