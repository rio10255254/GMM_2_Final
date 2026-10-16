"""Validate the locked R88 design without generating data or starting training."""
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

    if design.get("status") != "design_locked_no_training_authorization":
        errors.append("Design status must remain locked without training authorization.")
    if design["training"].get("formal_runs_authorized") != 0:
        errors.append("No formal run may be authorized by the design file.")

    isolation = design["source_isolation"]
    forbidden_true = [
        "checkpoint_loading_allowed",
        "resume_allowed",
        "teacher_models_allowed",
        "pseudo_labels_allowed",
        "sem_pixels_allowed",
        "sem_structure_allowed",
        "hs100mg_structure_allowed",
        "real_sample_pixels_stored_as_training_pairs",
        "real_sample_contours_allowed",
    ]
    for key in forbidden_true:
        if isolation.get(key):
            errors.append(f"Forbidden source switch is enabled: {key}")

    architecture = design["architecture"]
    for key in ("spatial_reduction_normalization", "global_pooling", "global_fft_or_wiener"):
        if architecture.get(key):
            errors.append(f"Tile-unsafe architecture switch is enabled: {key}")
    if not architecture["tile_contract"].get("same_code_path_for_full_and_tiled"):
        errors.append("Full and tiled inference must use the same code path.")
    if architecture["output"].get("adversarial_or_generative_prior"):
        errors.append("A generative prior is forbidden for measurement reconstruction.")

    minimum_halo = int(architecture["tile_contract"]["minimum_halo_px"])
    for tile_size, core_size in gates["gates"]["tile_consistency"]["tile_schemes"]:
        context = int(tile_size) - int(core_size)
        if context < 0 or context % 2 != 0:
            errors.append(f"Invalid tile/core scheme: {tile_size}/{core_size}")
            continue
        if context // 2 < minimum_halo:
            errors.append(
                f"Tile/core scheme {tile_size}/{core_size} provides only {context // 2}px halo; "
                f"minimum is {minimum_halo}px."
            )

    dataset = design["dataset"]
    roles = dataset["roles"]
    for split_key, expected_key in (
        ("train", "train_scenes"),
        ("validation", "validation_scenes"),
        ("internal_test", "internal_test_scenes"),
    ):
        observed = sum(int(role[split_key]) for role in roles.values())
        expected = int(dataset["split_counts"][expected_key])
        if observed != expected:
            errors.append(f"Role split mismatch for {split_key}: {observed} != {expected}")
    role_total = sum(int(role["total"]) for role in roles.values())
    if role_total != int(dataset["scene_count"]):
        errors.append(f"Scene total mismatch: {role_total} != {dataset['scene_count']}")
    for role_name, role in roles.items():
        split_total = int(role["train"]) + int(role["validation"]) + int(role["internal_test"])
        if split_total != int(role["total"]):
            errors.append(f"Role total mismatch for {role_name}: {split_total} != {role['total']}")
    expected_observations = int(dataset["scene_count"]) * int(dataset["observations_per_scene"])
    if expected_observations != int(dataset["total_observations"]):
        errors.append("Scene and observation totals do not agree.")
    quota_total = sum(int(value) for value in dataset["degradation_observation_quotas"].values())
    if quota_total != int(dataset["total_observations"]):
        errors.append(f"Degradation quota mismatch: {quota_total} != {dataset['total_observations']}")

    stages = design["training"]["stages"]
    covered_epochs: list[int] = []
    effective_batches = set()
    for stage in stages:
        covered_epochs.extend(range(int(stage["epoch_start"]), int(stage["epoch_end"]) + 1))
        effective = int(stage["scene_batch_size"]) * int(stage["gradient_accumulation"])
        effective_batches.add(effective)
        if effective != int(stage["effective_scene_batch"]):
            errors.append(f"Effective batch mismatch in stage {stage['epoch_start']}-{stage['epoch_end']}")
    if covered_epochs != list(range(1, int(design["training"]["epochs"]) + 1)):
        errors.append("Training stages do not cover epochs 1-100 exactly once.")
    if effective_batches != {12}:
        errors.append(f"Effective scene batch must stay 12, got {sorted(effective_batches)}")

    required_gate_groups = {
        "tile_consistency",
        "new_locked_synthetic",
        "R73_development",
        "R74_development",
        "SEM_36_pillars",
        "synthetic_motion",
        "real_motion_301_frames",
        "reference_circle_measurement",
        "synthetic_texture",
        "identity_and_real_texture_safety",
        "external_GMF",
    }
    missing_gates = sorted(required_gate_groups - set(gates.get("gates", {})))
    if missing_gates:
        errors.append(f"Missing gate groups: {missing_gates}")
    if not gates.get("all_domains_must_pass") or not gates.get("no_posthoc_average_override"):
        errors.append("All-domain and no-posthoc rules must remain enabled.")
    external_gmf = gates["gates"]["external_GMF"]
    if not external_gmf.get("required_for_promotion") or external_gmf.get("can_be_waived_for_promotion"):
        errors.append("External GMF must remain mandatory and non-waivable for promotion.")
    if not external_gmf.get("may_be_deferred_at_training_completion"):
        errors.append("A missing valid GMF license may defer promotion, but must not invalidate training completion.")

    holdout = dataset["holdout"]
    if not holdout.get("manifest_hash_before_training") or not holdout.get("unread_until_checkpoint_frozen"):
        errors.append("The new holdout must be hashed before training and sealed until checkpoint freeze.")
    if design["training"].get("external_live_validation_before_selection"):
        errors.append("External live validation must not be visible during checkpoint selection.")

    required_files = [
        ROOT / "README.md",
        ROOT / "MANIFEST.md",
        ROOT / "reports" / "R88_PROBLEM_LEDGER.md",
        ROOT / "reports" / "R88_LITERATURE_SYNTHESIS.md",
        ROOT / "reports" / "R88_EXPERIMENT_DESIGN.md",
        ROOT / "reports" / "R88_ACCEPTANCE_GATES.md",
        ROOT / "reports" / "r88_evidence_snapshot.json",
        ROOT / "reports" / "R88_DESIGN_REPORT.artifact.json",
    ]
    for path in required_files:
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"Missing required design document: {path.name}")
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
