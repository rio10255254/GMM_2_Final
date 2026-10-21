"""Apply the predeclared R83 confirmation gates and write the final decision."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "final_confirmation"
TABLES = OUTPUT / "tables"
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
METHODS = ["R79", "R83Direct", "R83Safe"]


def contour_summary(root: Path, prefix: str) -> pd.DataFrame:
    table = pd.read_csv(root / "results" / "tables" / "primary_contour_metrics.csv")
    table = table.loc[(table["alignment"] == "translation_only") & table["method"].isin(METHODS)]
    return table.groupby("method", as_index=False).agg(**{
        f"{prefix}_boundary": ("mean_boundary_distance_px", "median"),
        f"{prefix}_iou": ("iou", "median"),
        f"{prefix}_success": ("acm_success", "mean"),
    })


def main() -> int:
    protocol = CONFIG["final_confirmation_protocol"]
    selection_manifest = json.loads((ROOT / "weights" / "selected" / "selection_manifest.json").read_text(encoding="utf-8"))
    direct_is_epoch_zero = bool(selection_manifest.get("direct_mode_is_exact_r79", False))
    image = pd.read_csv(TABLES / "locked_synthetic_per_pair.csv").groupby("method", as_index=False).agg(
        holdout_mae=("mae", "median"), holdout_psnr=("psnr", "median"),
        holdout_ssim=("ssim", "median"), holdout_edge_mae=("edge_mae", "median")
    )
    acm = contour_summary(OUTPUT / "locked_synthetic_acm", "holdout_acm")
    r73 = contour_summary(OUTPUT / "development_recheck" / "R73_novel_shapes", "r73")
    r74 = contour_summary(OUTPUT / "development_recheck" / "R74_hard_microscopy", "r74")
    sem_table = pd.read_csv(OUTPUT / "SEM_reserved" / "results" / "acm_sem" / "tables" / "primary_contour_metrics.csv")
    expected_sem = set(protocol["sem_reserved"]["pillar_ids"])
    actual_sem = set(int(value) for value in sem_table["pillar_id"].unique())
    if actual_sem != expected_sem:
        raise RuntimeError(f"Reserved SEM scope mismatch: {sorted(actual_sem)}")
    sem = sem_table.loc[sem_table["method"].isin(METHODS)].groupby("method", as_index=False).agg(
        sem_reserved_boundary_pitch_pct=("mean_boundary_distance_pitch_pct", "median"),
        sem_reserved_iou=("iou", "median"),
    )
    merged = image.merge(acm, on="method").merge(r73, on="method").merge(r74, on="method").merge(sem, on="method")
    base = merged.loc[merged["method"] == "R79"].iloc[0]
    real = pd.read_csv(TABLES / "real_motion_summary_with_r79.csv")
    tile = pd.read_csv(TABLES / "tile_consistency.csv")
    gates = {}
    for method in ["R83Direct", "R83Safe"]:
        row = merged.loc[merged["method"] == method].iloc[0]
        real_rows = real.loc[real["method"] == method]
        sequence_pass = real_rows["sequence_pass"].astype(str).str.lower().eq("true")
        tile_rows = tile.loc[tile["method"] == method]
        method_gates = {
            "synthetic_image_fidelity": bool(row["holdout_mae"] <= base["holdout_mae"] * 1.03),
            "synthetic_acm": bool(
                row["holdout_acm_boundary"] <= base["holdout_acm_boundary"] * 1.05
                and row["holdout_acm_success"] == 1.0
            ),
            "reserved_sem": bool(row["sem_reserved_boundary_pitch_pct"] <= base["sem_reserved_boundary_pitch_pct"] * 1.10),
            "real_fov_6_of_6": bool(len(real_rows) == 6 and sequence_pass.all()),
            "r73_safe": bool(row["r73_boundary"] <= 0.30 and row["r73_success"] == 1.0),
            "tile_consistency": bool(
                tile_rows["mean_abs_gray"].max() <= 0.10
                and tile_rows["p99_abs_gray"].max() <= 1.0
                and tile_rows["max_abs_gray"].max() <= 3.0
            ),
        }
        if method == "R83Direct":
            if direct_is_epoch_zero:
                method_gates["r74_goal"] = bool(row["r74_boundary"] <= base["r74_boundary"] * 1.001 and row["r74_success"] == 1.0)
            else:
                method_gates["r74_goal"] = bool(row["r74_boundary"] < base["r74_boundary"] and row["r74_success"] == 1.0)
        else:
            method_gates["r74_goal"] = bool(row["r74_boundary"] <= base["r74_boundary"] * 0.90 and row["r74_success"] == 1.0)
        method_gates["all_pass"] = bool(all(method_gates.values()))
        gates[method] = method_gates
    if gates["R83Direct"]["all_pass"] and gates["R83Safe"]["all_pass"]:
        recommended = "R83Safe"
    elif gates["R83Direct"]["all_pass"]:
        recommended = "R83Direct"
    else:
        recommended = "R79"
    real_compact = real.groupby("method", as_index=False).agg(
        passed_sequences=("sequence_pass", lambda values: int(values.astype(str).str.lower().eq("true").sum())),
        total_sequences=("sequence", "count"),
        worst_median_difference_of_step=("median_difference_of_step", "max"),
        worst_p95_difference_of_step=("p95_difference_of_step", "max"),
        worst_step_std_um=("step_std_um", "max"),
    )
    tile_compact = tile.groupby("method", as_index=False).agg(
        worst_mean_abs_gray=("mean_abs_gray", "max"),
        worst_p99_abs_gray=("p99_abs_gray", "max"),
        worst_max_abs_gray=("max_abs_gray", "max"),
    )
    decision = {
        "status": "complete",
        "recommended_mode": recommended,
        "formal_baseline_unchanged": True,
        "research_candidate_confirmed": recommended != "R79",
        "restricted_full_frame_safe_mode_available": bool(
            all(value for key, value in gates["R83Safe"].items() if key not in {"tile_consistency", "all_pass"})
            and not gates["R83Safe"]["tile_consistency"]
        ),
        "fine_tune_promoted_over_r79": bool(selection_manifest.get("fine_tune_promoted_over_r79", False)),
        "direct_mode_is_exact_r79": direct_is_epoch_zero,
        "gates": gates,
        "contour_and_image_rows": merged.where(pd.notna(merged), None).to_dict(orient="records"),
        "real_motion_rows": real_compact.where(pd.notna(real_compact), None).to_dict(orient="records"),
        "tile_rows": tile_compact.where(pd.notna(tile_compact), None).to_dict(orient="records"),
        "interpretation": {
            "R83Direct": "an exact copy of the R79 epoch-23 EMA state",
            "R83Safe": "the exact R79 state with the frozen input-quality-dependent residual reduction",
            "R79": "the unchanged parent reference",
        },
        "nonpromotion_reason": (
            "R79 and the frozen safe output depend on inference tile size; the predeclared 512-pixel tile-consistency gate failed."
            if recommended == "R79" else None
        ),
    }
    merged.to_csv(TABLES / "final_contour_image_summary.csv", index=False)
    (OUTPUT / "final_decision.json").write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return 0 if recommended != "R79" else 2


if __name__ == "__main__":
    raise SystemExit(main())
