"""Audit every stored R91 validation checkpoint with corrected, separable axes."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "config" / "capability_validation_20260811.json"
DESIGN = ROOT / "config" / "experiment_design.json"
RUN = ROOT / "runs" / "training_R91_scratch_seed910041_20260811_180203"
RESULTS = ROOT / "results" / "capability_diagnosis_20260811"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"

EXPECTED_ROLES = {
    "textured_general_geometry",
    "identity_and_detail_guard",
    "exposure_coherent_bundle",
    "difficult_contour",
    "cross_tile_and_dense",
    "signed_subpixel_motion",
    "clean_contour_anchor",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exposure_update_share(design: dict[str, Any], stage: dict[str, Any]) -> dict[str, float | int]:
    counts = design["dataset"]["roles"]
    exposure = int(counts["exposure_coherent_bundle"]["train"])
    regular = sum(int(value["train"]) for name, value in counts.items() if name != "exposure_coherent_bundle")
    batch = int(stage["scene_batch_size"])
    bundle_batch = max(1, batch // 2)
    regular_batches = math.ceil(regular / batch)
    exposure_batches = math.ceil(exposure / bundle_batch)
    total = regular_batches + exposure_batches
    return {
        "scene_batch_size": batch,
        "regular_batches": regular_batches,
        "exposure_batches": exposure_batches,
        "total_batches": total,
        "exposure_update_share": exposure_batches / total,
    }


def checkpoint_rows(checkpoint_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    paths = sorted(checkpoint_root.glob("epoch_*.pth.tar"))
    if not paths:
        raise RuntimeError("No R91 checkpoints were found")
    rows: list[dict[str, Any]] = []
    raw_references: dict[tuple[str, str], list[float]] = {}
    data_shapes: set[tuple[int, int, int]] = set()
    design_hashes: set[str] = set()
    architecture_hashes: set[str] = set()
    checkpoint_hashes: set[str] = set()
    for path in paths:
        payload = torch.load(path, map_location="cpu", weights_only=False)
        epoch = int(payload["epoch"])
        if path.name != f"epoch_{epoch:03d}.pth.tar":
            raise RuntimeError(f"Checkpoint epoch/name mismatch: {path}")
        if payload.get("experiment_id") != "R91_DetailDecoupledScratch":
            raise RuntimeError(f"Foreign checkpoint: {path}")
        metrics = payload.get("metrics", {})
        validation = metrics.get("validation")
        if not isinstance(validation, dict):
            raise RuntimeError(f"Checkpoint has no validation payload: {path}")
        roles = validation["roles"]
        if set(roles) != EXPECTED_ROLES:
            raise RuntimeError(f"Validation role drift at epoch {epoch}: {sorted(roles)}")
        data_shapes.add((int(validation["evaluated_scenes"]), int(validation["evaluated_cases"]), int(validation["evaluated_views"])))
        metadata = payload.get("metadata", {})
        design_hashes.add(str(metadata.get("locked_design_sha256")))
        architecture_hashes.add(str(metadata.get("architecture_sha256")))
        checkpoint_hash = sha256_file(path)
        if checkpoint_hash in checkpoint_hashes:
            raise RuntimeError(f"Duplicate checkpoint content: {path}")
        checkpoint_hashes.add(checkpoint_hash)
        for role, values in roles.items():
            for metric in ("raw_pixel", "raw_boundary", "raw_texture", "raw_cross_boundary"):
                if metric in values:
                    raw_references.setdefault((role, metric), []).append(float(values[metric]))

        safety = validation["safety"]
        normalized = validation["normalized_domain_ratios"]
        degraded_roles = [name for name in EXPECTED_ROLES if name != "identity_and_detail_guard"]
        textured = roles["textured_general_geometry"]
        degraded_texture_max = max(float(roles[name]["texture_ratio"]) for name in degraded_roles)
        degraded_texture_mean = float(np.mean([float(roles[name]["texture_ratio"]) for name in degraded_roles]))
        degraded_pixel_max = max(float(roles[name]["pixel_ratio"]) for name in degraded_roles)
        degraded_boundary_max = max(float(roles[name]["boundary_ratio"]) for name in degraded_roles)
        identity = roles["identity_and_detail_guard"]
        rows.append({
            "epoch": epoch,
            "checkpoint": str(path),
            "checkpoint_sha256": checkpoint_hash,
            "lr": float(metrics.get("lr", np.nan)),
            "detail_multiplier": float(metrics.get("adaptive_detail_multiplier", np.nan)),
            "stored_contaminated_detail_axis": float(normalized["texture"]),
            "degraded_textured_general_texture_ratio": float(textured["texture_ratio"]),
            "degraded_texture_max_role_ratio": degraded_texture_max,
            "degraded_texture_mean_role_ratio": degraded_texture_mean,
            "degraded_pixel_max_role_ratio": degraded_pixel_max,
            "degraded_boundary_max_role_ratio": degraded_boundary_max,
            "contour_axis": float(normalized["boundary"]),
            "identity_mean_abs_gray": float(safety["identity_mean_abs_gray"]),
            "identity_pixel_ratio": float(identity["pixel_ratio"]),
            "identity_boundary_ratio": float(identity["boundary_ratio"]),
            "identity_texture_ratio": float(identity["texture_ratio"]),
            "motion_mae_px": float(safety["motion_mae_px"]),
            "motion_p95_px": float(safety["motion_p95_px"]),
            "raw_motion_mae_px": float(safety["raw_motion_mae_px"]),
            "motion_bias_x_px": float(safety["signed_motion_bias_x_px"]),
            "motion_bias_y_px": float(safety["signed_motion_bias_y_px"]),
            "exposure_pixel_ratio": float(normalized["photometry"]),
            "exposure_stability_ratio": float(normalized["exposure_stability"]),
            "cross_observation_contour_gray": float(safety["cross_observation_contour_gray"]),
            "low_branch_edge_leakage_gray": float(safety["low_branch_edge_leakage_gray"]),
            "topology_mismatch_count": int(safety["topology_mismatch_count"]),
            "raw_topology_mismatch_count": int(safety["raw_topology_mismatch_count"]),
            "added_clear_topology_failures": int(safety["raw_clear_added_topology_failures"]),
            "tile_mean_abs_gray": float(safety["tile_mean_abs_gray"]),
        })
        del payload

    raw_spread = {
        f"{role}.{metric}": float(np.ptp(values))
        for (role, metric), values in sorted(raw_references.items())
    }
    audit = {
        "checkpoint_count": len(paths),
        "epochs": [int(value) for value in sorted(pd.DataFrame(rows)["epoch"].tolist())],
        "validation_population_shapes": [list(value) for value in sorted(data_shapes)],
        "validation_population_constant": len(data_shapes) == 1,
        "locked_design_hashes": sorted(design_hashes),
        "architecture_hashes": sorted(architecture_hashes),
        "unique_checkpoint_hashes": len(checkpoint_hashes),
        "maximum_raw_reference_spread": max(raw_spread.values(), default=0.0),
        "raw_reference_spread": raw_spread,
    }
    if not audit["validation_population_constant"] or len(design_hashes) != 1 or len(architecture_hashes) != 1:
        raise RuntimeError(f"Checkpoint comparability audit failed: {audit}")
    if float(audit["maximum_raw_reference_spread"]) > 1e-12:
        raise RuntimeError(f"Raw validation reference changed across epochs: {audit['maximum_raw_reference_spread']}")
    return pd.DataFrame(rows).sort_values("epoch"), audit


def phase_labels(table: pd.DataFrame) -> pd.Series:
    epoch = table["epoch"]
    return pd.Series(
        np.select(
            [epoch <= 6, epoch <= 26, epoch <= 36, epoch <= 46],
            ["conservative", "aggressive_drift", "recovery", "late_reconstruction"],
            default="final_plateau",
        ),
        index=table.index,
    )


def summarize_phases(table: pd.DataFrame) -> pd.DataFrame:
    table = table.copy()
    table["phase"] = phase_labels(table)
    fields = [
        "degraded_textured_general_texture_ratio",
        "contour_axis",
        "identity_mean_abs_gray",
        "motion_mae_px",
        "exposure_pixel_ratio",
        "added_clear_topology_failures",
        "low_branch_edge_leakage_gray",
    ]
    rows: list[dict[str, Any]] = []
    for phase, group in table.groupby("phase", sort=False):
        row: dict[str, Any] = {
            "phase": phase,
            "epoch_start": int(group["epoch"].min()),
            "epoch_end": int(group["epoch"].max()),
            "checkpoints": int(len(group)),
        }
        for field in fields:
            row[f"start_{field}"] = float(group.iloc[0][field])
            row[f"end_{field}"] = float(group.iloc[-1][field])
            row[f"best_{field}"] = float(group[field].min())
        rows.append(row)
    return pd.DataFrame(rows)


def pareto_flags(table: pd.DataFrame) -> pd.DataFrame:
    fields = [
        "degraded_textured_general_texture_ratio",
        "contour_axis",
        "identity_mean_abs_gray",
        "motion_mae_px",
        "exposure_pixel_ratio",
        "tile_mean_abs_gray",
    ]
    values = table[fields].to_numpy(float)
    dominated: list[bool] = []
    for index in range(len(table)):
        by_other = np.all(values <= values[index] + 1e-12, axis=1) & np.any(values < values[index] - 1e-12, axis=1)
        by_other[index] = False
        dominated.append(bool(np.any(by_other)))
    output = table.copy()
    output["corrected_pareto_non_dominated"] = ~np.asarray(dominated)
    return output


def save_figure(table: pd.DataFrame) -> Path:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5), constrained_layout=True)
    plots = [
        ("degraded_textured_general_texture_ratio", "Degraded texture error / Raw", 1.0),
        ("contour_axis", "Worst degraded contour error / Raw", 1.0),
        ("identity_mean_abs_gray", "Clear-input mean change (gray)", 0.0),
        ("motion_mae_px", "Stored motion MAE (px)", float(table["raw_motion_mae_px"].iloc[0])),
    ]
    selected = {6, 34, 40, 52, 60}
    for axis, (field, title, reference) in zip(axes.flat, plots):
        axis.plot(table["epoch"], table[field], color="#24557a", linewidth=2)
        axis.axhline(reference, color="#555555", linestyle="--", linewidth=1.2, label="Raw/reference")
        chosen = table.loc[table["epoch"].isin(selected)]
        axis.scatter(chosen["epoch"], chosen[field], color="#e07a1f", s=48, zorder=3)
        for row in chosen.itertuples(index=False):
            axis.annotate(f"E{row.epoch}", (row.epoch, getattr(row, field)), xytext=(4, 5), textcoords="offset points", fontsize=8)
        axis.set_title(title)
        axis.set_xlabel("Epoch")
        axis.grid(alpha=0.22)
        axis.legend(frameon=False, fontsize=8)
    path = FIGURES / "r91_corrected_training_trajectory.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return path


def main() -> int:
    protocol = read_json(PROTOCOL)
    design = read_json(DESIGN)
    summary = read_json(RUN / "run_summary.json")
    initialization = read_json(RUN / "scratch_initialization_audit.json")
    if summary.get("status") != "complete" or int(summary.get("completed_epoch", 0)) != 60:
        raise RuntimeError("R91 formal training is not complete")
    if initialization.get("checkpoint_loaded") or initialization.get("teacher_used") or initialization.get("real_training_pixels"):
        raise RuntimeError("R91 scratch/source-isolation audit failed")
    checkpoint_root = Path(PROJECT_ROOT / protocol["checkpoint_root"])
    table, checkpoint_audit = checkpoint_rows(checkpoint_root)
    table = pareto_flags(table)
    TABLES.mkdir(parents=True, exist_ok=True)
    table.to_csv(TABLES / "r91_checkpoint_trajectory_corrected.csv", index=False, encoding="utf-8-sig")
    phases = summarize_phases(table)
    phases.to_csv(TABLES / "r91_phase_summary.csv", index=False, encoding="utf-8-sig")
    figure = save_figure(table)

    schedule = [exposure_update_share(design, stage) for stage in design["training"]["stages"]]
    selected = table.loc[table["epoch"].isin(protocol["representative_stages"]["appearance_and_branch"])]
    payload = {
        "status": "complete",
        "protocol_id": protocol["protocol_id"],
        "run_complete": True,
        "scratch_training_verified": True,
        "source_isolation_verified": True,
        "checkpoint_audit": checkpoint_audit,
        "exposure_sampling_by_stage": schedule,
        "exposure_updates_are_overrepresented": bool(min(float(row["exposure_update_share"]) for row in schedule) > 0.35),
        "stored_detail_axis_is_contaminated": bool((table["stored_contaminated_detail_axis"] > table["degraded_textured_general_texture_ratio"] * 2.0).any()),
        "adaptive_detail_multiplier_reached_floor_epoch": int(table.loc[table["detail_multiplier"] <= 0.8500001, "epoch"].min()),
        "corrected_pareto_epochs": [int(value) for value in table.loc[table["corrected_pareto_non_dominated"], "epoch"]],
        "representative_stage_metrics": selected.replace({np.nan: None}).to_dict(orient="records"),
        "outputs": {
            "trajectory_table": str(TABLES / "r91_checkpoint_trajectory_corrected.csv"),
            "phase_table": str(TABLES / "r91_phase_summary.csv"),
            "trajectory_figure": str(figure),
        },
    }
    (RESULTS / "trajectory_diagnosis.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
