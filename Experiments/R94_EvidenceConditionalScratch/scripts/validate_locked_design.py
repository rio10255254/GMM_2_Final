"""Fail-closed audit for the locked R94 architecture and training strategy."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_model_module():
    path = ROOT / "model" / "r94_model.py"
    spec = importlib.util.spec_from_file_location("r94_locked_design_model", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    design = read("config/experiment_design.json")
    prototype = read("reports/prototype_report.json")
    replay = read("reports/causal_replay_validation.json")
    decomposition = read("reports/optical_layer_decomposition_validation.json")
    capacity = read("reports/branch_expressivity_analysis.json")
    oracle = read("reports/oracle_target_validation.json")
    acm = read("reports/locked_acm_clean_ceiling.json")
    source_manifest = Path(design["data"]["source_package"]) / "manifest.json"
    source_audit = json.loads(
        (Path(design["data"]["source_package"]) / "audit.json").read_text(encoding="utf-8")
    )
    model_module = load_model_module()
    formal_model = model_module.build_model(base=int(design["architecture"]["model_width"]))
    formal_parameter_count = int(model_module.count_parameters(formal_model))

    checks = {
        "formal_training_authorization_is_explicit": isinstance(design["formal_training_authorized"], bool),
        "scratch_only": all(
            design["independence"][name] is True
            for name in (
                "random_initialization_required", "checkpoint_resume_forbidden",
                "teacher_or_pseudo_label_forbidden", "real_training_pixels_forbidden",
                "sem_or_hs100mg_geometry_forbidden", "optimizer_reuse_forbidden",
            )
        ),
        "one_formal_run": int(design["independence"]["formal_run_count"]) == 1,
        "source_manifest_exists": source_manifest.is_file(),
        "source_content_hash_locked": (
            source_audit["passed"] is True
            and source_audit["content_sha256"] == design["data"]["source_content_sha256"]
        ),
        "prototype_all_passed": prototype["passed"] is True and all(prototype["checks"].values()),
        "prototype_did_not_start_training": prototype["formal_training_started"] is False,
        "model_parameter_budget": (
            formal_parameter_count
            == int(design["architecture"]["parameter_count"])
            <= int(design["architecture"]["parameter_budget_max"])
        ),
        "private_towers_do_not_overlap": (
            prototype["architecture_contract"]["learned_parameter_group_overlap"] is False
        ),
        "causal_replay_pixel_exact": (
            replay["all_replayed_noise_free_views_are_pixel_exact"] is True
            and int(replay["maximum_abs_gray"]) == 0
        ),
        "layer_recomposition_exact": (
            decomposition["additive_decomposition_is_numerically_exact"] is True
            and float(decomposition["target_recomposition_max_abs_float"]) < 1e-5
        ),
        "patch_labels_exact": max(
            float(decomposition["patch_core_boundary_max_abs_float"]),
            float(decomposition["patch_core_texture_max_abs_float"]),
            float(decomposition["patch_core_local_contrast_max_abs_float"]),
        ) == 0.0,
        "branch_capacity_passed": not any(capacity["recommendation"].values()),
        "oracle_joint_improvement": oracle["oracle_semantics_support_joint_improvement"] is True,
        "locked_acm_clean_ceiling_positive": all(acm["conclusion"].values()),
        "exact_tiling": float(prototype["metrics"]["full_vs_tiled_max_abs_gray"]) == 0.0,
        "translation_equivariant": max(
            float(value)
            for value in prototype["metrics"]["translation_equivariance_max_abs_gray"].values()
        ) < 1e-4,
        "clear_initial_identity": (
            float(prototype["metrics"]["identity_max_abs_gray"]) == 0.0
            and max(prototype["metrics"]["real_initial_identity_max_abs_gray"].values()) == 0.0
        ),
        "training_is_short_and_staged": (
            int(design["training"]["planned_epochs"]) == 48
            and int(design["training"]["batches_per_epoch"]) >= 80
            and len(design["training"]["phases"]) == 5
        ),
        "gpu_headroom_preserved": (
            float(design["training"]["gpu_batch_calibration"]["minimum_memory_left_for_desktop_gib"])
            >= 9.0
        ),
        "gpu_calibration_passed_before_authorization": (
            (ROOT / "config" / "gpu_batch_calibration.json").is_file()
            and read("config/gpu_batch_calibration.json")["passed"] is True
        ),
        "formal_trainer_exists": (ROOT / "training" / "train_r94.py").is_file(),
        "external_data_cannot_select_checkpoint": (
            design["validation"]["selection"]["external_results_can_reject_but_not_reselect_checkpoint"] is True
        ),
    }
    report = {
        "audit_id": "R94_LOCKED_DESIGN_AUDIT_V1",
        "passed": all(checks.values()),
        "formal_training_authorized": design["formal_training_authorized"],
        "checks": checks,
    }
    output = ROOT / "reports" / "locked_design_audit.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
