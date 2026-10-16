"""Validate the authorized R92 design before any generated payload is used."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
GATES_PATH = ROOT / "config" / "acceptance_gates.json"
OPTICAL_PATH = ROOT / "config" / "optical_statistics.json"
GPU_PROFILE_PATH = ROOT / "config" / "gpu_safety_profile.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_design(design: dict[str, Any], gates: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    experiment_id = "R92_PhysicalTransitionBalancedScratch"
    optical = load_json(OPTICAL_PATH)
    gpu_profile = load_json(GPU_PROFILE_PATH)
    if any(payload.get("experiment_id") != experiment_id for payload in (design, gates, optical, gpu_profile)):
        errors.append("Experiment identifiers do not match R92.")
    status = design.get("status")
    formal_runs_authorized = int(design["training"].get("formal_runs_authorized", -1))
    if status not in {"setup_and_smoke_authorized_formal_run_not_authorized", "formal_80epoch_run_authorized"}:
        errors.append("R92 design authorization status is invalid.")
    if (status == "formal_80epoch_run_authorized") != (formal_runs_authorized == 1):
        errors.append("The design status and formal-run authorization count disagree.")
    if formal_runs_authorized not in {0, 1} or int(design["training"].get("planned_formal_runs", -1)) != 1:
        errors.append("R92 must allow at most one independent formal run.")

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
        errors.append("R92 must remain a direct, non-generative residual reconstruction model.")
    if not output.get("low_frequency_branch_is_quarter_resolution_lowpass"):
        errors.append("The low-frequency branch must be physically low-pass constrained.")
    if not output.get("detail_branch_is_multiscale_zero_dc") or len(output.get("detail_bands", [])) < 2:
        errors.append("R92 detail recovery must use multiple zero-DC bands.")

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
    if float(exposure_path.get("minimum_exposure_span", 0.0)) < 0.28 or not exposure_path.get("mid_transition_required"):
        errors.append("The continuous exposure path does not cover the transition region.")
    if (
        not exposure_path.get("post_generation_span_rerender_allowed")
        or float(exposure_path.get("span_repair_target", 0.0)) < float(exposure_path.get("minimum_exposure_span", 1.0))
        or float(exposure_path.get("maximum_bundle_fraction_requiring_span_rerender", 1.0)) > 0.05
        or not exposure_path.get("span_rerender_requires_original_backup_and_full_rehash")
    ):
        errors.append("Exposure-span repair must rerender only a small backed-up subset and preserve the declared minimum span.")
    if exposure_path.get("target_mix_repair_allowed") or len(exposure_path.get("source_contrast_gray_bands", [])) != 4:
        errors.append("Exposure synthesis must cover four contrast bands without target mixing.")
    path_bins = exposure_path.get("validation_path_bins", [])
    if [row.get("name") for row in path_bins] != ["dark_endpoint", "inner_dark", "inner_bright", "bright_endpoint"]:
        errors.append("Exposure validation must preserve the four predeclared path regions.")
    elif float(path_bins[0].get("minimum_inclusive", -1.0)) != 0.0 or float(path_bins[-1].get("maximum_exclusive", 0.0)) < 1.0:
        errors.append("Exposure validation path bins do not cover the complete path.")
    transition = dataset.get("physical_transition_profile", {})
    if transition.get("method") != "shifted_logit_on_supersampled_coverage" or not transition.get("record_per_scene"):
        errors.append("The physical transition profile is not explicit and traceable.")
    pairing = dataset.get("pairing", {})
    if not pairing.get("cross_observation_same_crop_required") or float(pairing.get("exposure_bundle_four_view_fraction", 0)) != 1.0 or not pairing.get("exposure_path_position_returned_per_view"):
        errors.append("Exposure bundles must always use all four views at the same crop origin.")
    recoverability = dataset["recoverability_contract"]
    if float(recoverability["maximum_source_target_gap"]) > float(recoverability["model_combined_bound"]):
        errors.append("Synthetic corruption exceeds the model correction range.")
    if float(recoverability.get("minimum_global_degradation_scale", 0.0)) < 0.30:
        errors.append("A degradation may be weakened too far during recoverability repair.")
    if recoverability.get("target_mix_repair_allowed") or float(recoverability.get("maximum_final_pixelwise_clip_fraction", 1.0)) != 0.0:
        errors.append("Rendered sources may not be repaired or clipped toward the target.")
    if (
        not recoverability.get("post_generation_global_photometric_projection_allowed")
        or recoverability.get("projection_method") != "global_affine_source_only_no_target_pixel_mix"
        or not recoverability.get("projection_requires_original_backup_and_full_rehash")
    ):
        errors.append("Recoverability projection must remain global, source-only, backed up and fully re-audited.")
    if float(recoverability.get("maximum_observation_fraction_requiring_strength_projection", 1.0)) > 0.10:
        errors.append("Too much of the formal dataset may require recoverability projection.")
    if (
        not recoverability.get("post_generation_same_family_parameter_rerender_allowed")
        or recoverability.get("same_family_rerender_method") != "deterministic_same_family_full_forward_rerender"
        or float(recoverability.get("maximum_observation_fraction_requiring_same_family_rerender", 1.0)) > 0.02
        or not recoverability.get("same_family_rerender_requires_original_backup_and_full_rehash")
    ):
        errors.append("Unprojectable observations may only use a small, backed-up same-family full rerender.")
    sampling = dataset.get("sampling", {})
    if not 0.12 <= float(sampling.get("exposure_bundle_update_share", 0.0)) <= 0.20:
        errors.append("Exposure bundle update share must remain controlled.")

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
    planned_profiles = gpu_profile.get("planned_profiles", [])
    if len(planned_profiles) != len(training["stages"]):
        errors.append("GPU safety profiles do not match the training stage count.")
    else:
        for stage, profile in zip(training["stages"], planned_profiles):
            expected = {
                "epochs": f"{int(stage['epoch_start'])}-{int(stage['epoch_end'])}",
                "patch_size": int(stage["patch_size"]),
                "pair_scene_batch": int(stage["scene_batch_size"]),
                "four_view_bundle_batch": max(1, int(stage["scene_batch_size"]) // 2),
                "gradient_accumulation": int(stage["gradient_accumulation"]),
            }
            if any(profile.get(key) != value for key, value in expected.items()):
                errors.append(f"GPU safety profile mismatch for epochs {expected['epochs']}.")
    anchors = training.get("curriculum_anchors", [])
    anchor_epochs = [int(row["epoch"]) for row in anchors]
    if not anchors or anchor_epochs[0] != 1 or anchor_epochs[-1] != int(training["epochs"]) or anchor_epochs != sorted(set(anchor_epochs)):
        errors.append(f"Smooth curriculum anchors must begin at epoch 1 and end at epoch {training['epochs']}.")
    for row in anchors:
        for key, value in row.items():
            upper = 1.25 if key == "detail_factor" else 1.0
            if key != "epoch" and not 0.0 <= float(value) <= upper:
                errors.append(f"Curriculum factor out of range: {key}")
    lr_anchors = training.get("learning_rate_anchors", [])
    lr_epochs = [int(row["epoch"]) for row in lr_anchors]
    lr_values = [float(row["learning_rate"]) for row in lr_anchors]
    if not lr_anchors or lr_epochs[0] != 1 or lr_epochs[-1] != int(training["epochs"]) or lr_epochs != sorted(set(lr_epochs)):
        errors.append("Learning-rate anchors must begin at epoch 1 and end at the final epoch.")
    elif max(lr_values) != float(training["learning_rate"]) or lr_values[-1] != float(training["minimum_learning_rate"]):
        errors.append("Learning-rate anchors do not match the declared maximum and minimum.")
    elif any(left < right for left, right in zip(lr_values[1:], lr_values[2:])):
        errors.append("Learning rate must not rise again after warmup.")
    required_losses = {"cross_observation_consistency", "bundle_soft_tail", "low_branch_edge_leakage", "low_branch_target", "detail_branch_target", "detail_halo", "region_relationship", "raw_geometry_preservation", "low_branch_geometry_neutrality", "overlap_tile_consistency", "signed_displacement", "physical_transition_profile", "signed_boundary_bias"}
    if not required_losses.issubset(training["loss_weights"]):
        errors.append("One or more R92 supervision terms are missing.")
    selection = training["checkpoint_selection"]
    if selection.get("hard_metric_rejection") or not selection.get("diagnostics_are_reported_not_used_as_binary_gates"):
        errors.append("Checkpoint selection must remain continuous rather than gate-driven.")
    if gates.get("checkpoint_selection_uses_hard_rejection"):
        errors.append("Diagnostic references must not become hard checkpoint gates.")
    controller = training.get("adaptive_detail_controller", {})
    if controller.get("enabled") or float(controller.get("minimum_multiplier", 0.0)) != 1.0 or float(controller.get("maximum_multiplier", 0.0)) != 1.0:
        errors.append("The unstable adaptive detail controller must remain disabled in R92.")
    geometry_preservation = training.get("geometry_preservation", {})
    if geometry_preservation.get("binary_threshold") or geometry_preservation.get("confidence_source") != "continuous_raw_soft_boundary_error":
        errors.append("Raw-geometry preservation must use a continuous confidence rather than a binary gate.")
    if geometry_preservation.get("low_branch_neutrality_mode") != "boundary_noninferiority_not_zero_correction":
        errors.append("Low-frequency geometry protection must allow neutral photometric correction.")
    if training.get("validation_precision") != "float32":
        errors.append("Primary procedural validation must use float32.")

    inference_contract = design.get("evaluation", {}).get("inference_contract", {})
    if inference_contract.get("primary_precision") != "float32" or int(inference_contract.get("primary_tile_batch", 0)) != 1:
        errors.append("Primary inference must use float32 with tile batch one.")
    if not inference_contract.get("bfloat16_opt_in_diagnostic_only") or not inference_contract.get("manifest_records_precision_and_tile_batch"):
        errors.append("Inference precision provenance is incomplete.")

    holdout = dataset["holdout"]
    if not holdout.get("manifest_hash_before_training") or not holdout.get("unread_until_checkpoint_frozen"):
        errors.append("The independent holdout must be sealed before training.")
    required_files = (
        ROOT / "model" / "r92_model.py", ROOT / "training" / "train_r92.py",
        ROOT / "inference" / "reconstruct.py", ROOT / "scripts" / "generate_dataset.py",
        ROOT / "scripts" / "benchmark_r92.py", ROOT / "scripts" / "repair_unprojectable_observations.py", ROOT / "scripts" / "repair_recoverability.py", ROOT / "scripts" / "repair_exposure_span.py", ROOT / "scripts" / "launch_r92.py",
        OPTICAL_PATH, GPU_PROFILE_PATH,
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
