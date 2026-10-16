from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_design.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("r90_validate_design", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_locked_design_contract_passes() -> None:
    module = load_validator()
    design = module.load_json(module.DESIGN_PATH)
    gates = module.load_json(module.GATES_PATH)
    assert module.validate_design(design, gates) == []


def test_exactly_one_scratch_training_is_authorized() -> None:
    module = load_validator()
    design = module.load_json(module.DESIGN_PATH)
    assert design["training"]["formal_runs_authorized"] == 1
    assert design["source_isolation"]["checkpoint_loading_allowed"] is False
    assert design["source_isolation"]["teacher_models_allowed"] is False
    assert design["source_isolation"]["sem_pixels_allowed"] is False


def test_dataset_totals_are_exact() -> None:
    module = load_validator()
    dataset = module.load_json(module.DESIGN_PATH)["dataset"]
    assert dataset["scene_count"] == 1280
    assert dataset["observations_per_scene"] == 4
    assert dataset["total_observations"] == 5120
    assert sum(item["train"] for item in dataset["roles"].values()) == 1024
    assert sum(item["validation"] for item in dataset["roles"].values()) == 128
    assert sum(item["internal_test"] for item in dataset["roles"].values()) == 128
    assert sum(dataset["degradation_observation_quotas"].values()) == 5120


def test_architecture_changes_are_small_and_measurement_safe() -> None:
    module = load_validator()
    architecture = module.load_json(module.DESIGN_PATH)["architecture"]
    assert architecture["local_optical_bank"]["same_as_r89"] is True
    assert architecture["spatial_reduction_normalization"] is False
    assert architecture["global_pooling"] is False
    assert architecture["global_fft_or_wiener"] is False
    assert architecture["output"]["confidence_gate"] is False
    assert architecture["output"]["direct_residual"] is True
    assert architecture["output"]["low_frequency_branch_is_explicitly_lowpass"] is True
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
    assert design["dataset"]["holdout"]["unread_until_checkpoint_frozen"] is True
