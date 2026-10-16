"""Apply every predeclared R84 gate without exclusions or threshold changes."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "final_confirmation"
TABLES = OUTPUT / "tables"


def contour_summary(root: Path, prefix: str) -> pd.DataFrame:
    table = pd.read_csv(root / "results" / "tables" / "primary_contour_metrics.csv")
    table = table.loc[(table["alignment"] == "translation_only") & table["method"].isin(["Raw", "R79", "R84"])]
    return table.groupby("method", as_index=False).agg(**{
        f"{prefix}_boundary": ("mean_boundary_distance_px", "median"),
        f"{prefix}_iou": ("iou", "median"),
        f"{prefix}_success": ("acm_success", "mean"),
    })


def main() -> int:
    image = pd.read_csv(TABLES / "locked_synthetic_per_pair.csv").groupby("method", as_index=False).agg(
        holdout_mae=("mae", "median"),
        holdout_edge_mae=("edge_mae", "median"),
        holdout_psnr=("psnr", "median"),
        holdout_ssim=("ssim", "median"),
    )
    holdout_acm = contour_summary(OUTPUT / "locked_synthetic_acm", "holdout_acm")
    r73 = contour_summary(OUTPUT / "development_recheck" / "R73_novel_shapes", "r73")
    r74 = contour_summary(OUTPUT / "development_recheck" / "R74_hard_microscopy", "r74")
    sem_table = pd.read_csv(OUTPUT / "SEM_reserved" / "results" / "acm_sem" / "tables" / "primary_contour_metrics.csv")
    if set(int(value) for value in sem_table["pillar_id"].unique()) != set(range(1, 37)):
        raise RuntimeError("SEM all-36 scope changed.")
    sem = sem_table.loc[sem_table["method"].isin(["Raw", "R79", "R84"])].groupby("method", as_index=False).agg(
        sem_boundary_pitch_pct=("mean_boundary_distance_pitch_pct", "median"),
        sem_iou=("iou", "median"),
        sem_rows=("pillar_id", "count"),
    )
    merged = image.merge(holdout_acm, on="method").merge(r73, on="method").merge(r74, on="method").merge(sem, on="method")
    base = merged.loc[merged["method"] == "R79"].iloc[0]
    candidate = merged.loc[merged["method"] == "R84"].iloc[0]
    tile = pd.read_csv(TABLES / "tile_consistency.csv")
    real = pd.read_csv(TABLES / "real_motion_summary_with_r79.csv")
    real_r84 = real.loc[real["method"] == "R84"]
    sequence_pass = real_r84["sequence_pass"].astype(str).str.lower().eq("true")

    rows = [
        {"gate": "tile_mean", "value": float(tile["mean_abs_gray"].max()), "limit": 0.10, "pass": bool(tile["mean_abs_gray"].max() <= 0.10)},
        {"gate": "tile_p99", "value": float(tile["p99_abs_gray"].max()), "limit": 1.0, "pass": bool(tile["p99_abs_gray"].max() <= 1.0)},
        {"gate": "tile_max", "value": float(tile["max_abs_gray"].max()), "limit": 3.0, "pass": bool(tile["max_abs_gray"].max() <= 3.0)},
        {"gate": "locked_synthetic_mae_ratio", "value": float(candidate["holdout_mae"] / base["holdout_mae"]), "limit": 1.05, "pass": bool(candidate["holdout_mae"] <= base["holdout_mae"] * 1.05)},
        {"gate": "locked_synthetic_edge_ratio", "value": float(candidate["holdout_edge_mae"] / base["holdout_edge_mae"]), "limit": 1.08, "pass": bool(candidate["holdout_edge_mae"] <= base["holdout_edge_mae"] * 1.08)},
        {"gate": "locked_synthetic_acm_ratio", "value": float(candidate["holdout_acm_boundary"] / base["holdout_acm_boundary"]), "limit": 1.08, "pass": bool(candidate["holdout_acm_boundary"] <= base["holdout_acm_boundary"] * 1.08 and candidate["holdout_acm_success"] == 1.0)},
        {"gate": "R73_boundary_px", "value": float(candidate["r73_boundary"]), "limit": 0.30, "pass": bool(candidate["r73_boundary"] <= 0.30 and candidate["r73_success"] == 1.0)},
        {"gate": "R74_boundary_ratio", "value": float(candidate["r74_boundary"] / base["r74_boundary"]), "limit": 1.05, "pass": bool(candidate["r74_boundary"] <= base["r74_boundary"] * 1.05 and candidate["r74_success"] == 1.0)},
        {"gate": "SEM_all36_boundary_ratio", "value": float(candidate["sem_boundary_pitch_pct"] / base["sem_boundary_pitch_pct"]), "limit": 1.10, "pass": bool(candidate["sem_boundary_pitch_pct"] <= base["sem_boundary_pitch_pct"] * 1.10)},
        {"gate": "real_motion_sequences", "value": int(sequence_pass.sum()), "limit": 6, "pass": bool(len(real_r84) == 6 and sequence_pass.all())},
    ]
    gates = pd.DataFrame(rows)
    gates.to_csv(TABLES / "final_gate_table.csv", index=False)
    merged.to_csv(TABLES / "final_metric_summary.csv", index=False)
    decision = {
        "status": "complete",
        "decision": "R84_not_promoted_R79_retained",
        "formal_baseline_unchanged": True,
        "tile_root_cause_fixed": bool(gates.loc[gates["gate"].str.startswith("tile_"), "pass"].all()),
        "all_predeclared_gates_pass": bool(gates["pass"].all()),
        "passed_gate_count": int(gates["pass"].sum()),
        "total_gate_count": int(len(gates)),
        "failed_gates": gates.loc[~gates["pass"], "gate"].tolist(),
        "recommended_model": "R79",
        "candidate_role": "diagnostic tile-stable branch only",
        "root_diagnosis": "Replacing spatially global normalization fixed extent dependence, but bypassing the global optical preconditioner removed most of R79's clean-boundary and SEM advantage.",
        "next_precise_repair": "Compute the original optical preconditioner once on the canonical full canvas, then feed the same preconditioned canvas to both full and tiled local-normalization inference.",
        "metrics": merged.where(pd.notna(merged), None).to_dict(orient="records"),
        "gates": gates.to_dict(orient="records"),
    }
    (OUTPUT / "final_decision.json").write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
    report = [
        "# R84 最終判決",
        "",
        "R84 已根治完整影像與分塊影像不一致，也保住 6 組真實位移；但沒有通過全部品質門檻，因此不能取代 R79。",
        "",
        f"- 通過：{decision['passed_gate_count']}/{decision['total_gate_count']} 個門檻",
        f"- 未通過：{', '.join(decision['failed_gates'])}",
        f"- 新合成整體誤差：R84/R79 = {candidate['holdout_mae'] / base['holdout_mae']:.3f}",
        f"- 新合成邊界誤差：R84/R79 = {candidate['holdout_edge_mae'] / base['holdout_edge_mae']:.3f}",
        f"- 新合成 ACM 輪廓：R84/R79 = {candidate['holdout_acm_boundary'] / base['holdout_acm_boundary']:.3f}",
        f"- R74 困難顯微：R84/R79 = {candidate['r74_boundary'] / base['r74_boundary']:.3f}",
        f"- SEM 36 顆：R84/R79 = {candidate['sem_boundary_pitch_pct'] / base['sem_boundary_pitch_pct']:.3f}",
        f"- 位移：{int(sequence_pass.sum())}/6 組通過",
        "",
        "下一步不是繼續放大訓練，而是把 R79 的光學前處理保留下來，在整張畫布只算一次，再讓完整與分塊推論共用它。",
    ]
    report_path = ROOT / "reports" / "R84_FINAL_VERDICT.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(decision, indent=2, ensure_ascii=False), flush=True)
    return 0 if decision["all_predeclared_gates_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
