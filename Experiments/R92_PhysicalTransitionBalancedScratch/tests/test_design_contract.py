from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_design.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("r92_validate_design", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_locked_design_contract_passes() -> None:
    module = load_validator()
    design = module.load_json(module.DESIGN_PATH)
    gates = module.load_json(module.GATES_PATH)
    assert module.validate_design(design, gates) == []


def test_all_config_identities_and_gpu_stages_match() -> None:
    module = load_validator()
    design = module.load_json(module.DESIGN_PATH)
    experiment_id = design["experiment_id"]
    for path in (module.GATES_PATH, module.OPTICAL_PATH, module.GPU_PROFILE_PATH):
        assert module.load_json(path)["experiment_id"] == experiment_id
    gpu = module.load_json(module.GPU_PROFILE_PATH)
    for stage, profile in zip(design["training"]["stages"], gpu["planned_profiles"], strict=True):
        assert profile["epochs"] == f"{stage['epoch_start']}-{stage['epoch_end']}"
        assert profile["patch_size"] == stage["patch_size"]
        assert profile["pair_scene_batch"] == stage["scene_batch_size"]
        assert profile["four_view_bundle_batch"] == max(1, stage["scene_batch_size"] // 2)
        assert profile["gradient_accumulation"] == stage["gradient_accumulation"]


def test_single_formal_run_is_explicit_and_remains_scratch_only() -> None:
    module = load_validator()
    design = module.load_json(module.DESIGN_PATH)
    assert design["status"] == "formal_80epoch_run_authorized"
    assert design["training"]["formal_runs_authorized"] == 1
    assert design["training"]["planned_formal_runs"] == 1
    assert design["training"]["epochs"] == 80
    assert design["source_isolation"]["checkpoint_loading_allowed"] is False
    assert design["source_isolation"]["teacher_models_allowed"] is False
    assert design["source_isolation"]["sem_pixels_allowed"] is False


def test_learning_rate_tail_is_predeclared_for_eighty_epochs() -> None:
    module = load_validator()
    training = module.load_json(module.DESIGN_PATH)["training"]
    anchors = training["learning_rate_anchors"]
    assert anchors[0] == {"epoch": 1, "learning_rate": 0.00005}
    assert anchors[-1] == {"epoch": 80, "learning_rate": 0.000012}
    assert max(row["learning_rate"] for row in anchors) == training["learning_rate"]
    assert all(left["epoch"] < right["epoch"] for left, right in zip(anchors, anchors[1:]))


def test_dataset_totals_are_exact() -> None:
    module = load_validator()
    dataset = module.load_json(module.DESIGN_PATH)["dataset"]
    assert dataset["scene_count"] == 1250
    assert dataset["observations_per_scene"] == 4
    assert dataset["total_observations"] == 5000
    assert sum(item["train"] for item in dataset["roles"].values()) == 1000
    assert sum(item["validation"] for item in dataset["roles"].values()) == 125
    assert sum(item["internal_test"] for item in dataset["roles"].values()) == 125
    assert sum(dataset["degradation_observation_quotas"].values()) == 5000


def test_architecture_changes_are_small_and_measurement_safe() -> None:
    module = load_validator()
    architecture = module.load_json(module.DESIGN_PATH)["architecture"]
    assert architecture["local_optical_bank"]["same_as_r90"] is True
    assert architecture["spatial_reduction_normalization"] is False
    assert architecture["global_pooling"] is False
    assert architecture["global_fft_or_wiener"] is False
    assert architecture["output"]["binary_confidence_gate"] is False
    assert architecture["output"]["direct_residual"] is True
    assert architecture["output"]["low_frequency_branch_is_quarter_resolution_lowpass"] is True
    assert architecture["output"]["detail_branch_is_multiscale_zero_dc"] is True
    assert architecture["tile_contract"]["same_code_path_for_full_and_tiled"] is True


def test_every_training_patch_honors_the_deployment_halo() -> None:
    module = load_validator()
    design = module.load_json(module.DESIGN_PATH)
    minimum_halo = design["architecture"]["tile_contract"]["minimum_halo_px"]
    for stage in design["training"]["stages"]:
        assert (stage["patch_size"] - stage["core_size"]) // 2 >= minimum_halo // 2
        if "alternate_patch_size" in stage:
            assert (stage["alternate_patch_size"] - stage["alternate_core_size"]) // 2 >= minimum_halo


def test_selection_is_continuous_and_external_results_cannot_select() -> None:
    module = load_validator()
    design = module.load_json(module.DESIGN_PATH)
    assert design["training"]["external_live_validation_before_selection"] is False
    assert design["training"]["checkpoint_selection"]["external_suites_used_for_selection"] is False
    assert design["training"]["checkpoint_selection"]["hard_metric_rejection"] is False
    assert design["training"]["checkpoint_selection"]["maintain_pareto_archive"] is True
    assert design["training"]["adaptive_detail_controller"]["binary_stop_or_gate"] is False
    assert design["training"]["adaptive_detail_controller"]["enabled"] is False
    assert design["dataset"]["recoverability_contract"]["target_mix_repair_allowed"] is False
    recoverability = design["dataset"]["recoverability_contract"]
    assert recoverability["projection_method"] == "global_affine_source_only_no_target_pixel_mix"
    assert recoverability["projection_requires_original_backup_and_full_rehash"] is True
    assert recoverability["maximum_observation_fraction_requiring_strength_projection"] <= 0.10
    assert recoverability["same_family_rerender_method"] == "deterministic_same_family_full_forward_rerender"
    assert recoverability["maximum_observation_fraction_requiring_same_family_rerender"] <= 0.02
    assert recoverability["same_family_rerender_requires_original_backup_and_full_rehash"] is True
    assert 0.12 <= design["dataset"]["sampling"]["exposure_bundle_update_share"] <= 0.20
    assert design["dataset"]["holdout"]["unread_until_checkpoint_frozen"] is True
    exposure = design["dataset"]["continuous_exposure_path"]
    assert exposure["span_repair_target"] >= exposure["minimum_exposure_span"]
    assert exposure["maximum_bundle_fraction_requiring_span_rerender"] <= 0.05
    assert exposure["span_rerender_requires_original_backup_and_full_rehash"] is True
    preservation = design["training"]["geometry_preservation"]
    assert preservation["binary_threshold"] is False
    assert preservation["confidence_source"] == "continuous_raw_soft_boundary_error"
    assert preservation["low_branch_neutrality_mode"] == "boundary_noninferiority_not_zero_correction"
    assert design["training"]["validation_precision"] == "float32"
    inference = design["evaluation"]["inference_contract"]
    assert inference["primary_precision"] == "float32"
    assert inference["primary_tile_batch"] == 1
    assert inference["bfloat16_opt_in_diagnostic_only"] is True
