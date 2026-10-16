"""Summarize the R83 developmental blend ACM screen and decide on quality-gate eligibility."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / "results" / "preflight_blend_screen"
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
METHODS = ["Raw", "R79", "Blend25", "Blend50", "Blend75", "QualityConservative", "QualityModerate"]


def external_summary(suite: str) -> pd.DataFrame:
    table = pd.read_csv(SCREEN / suite / "results" / "tables" / "primary_contour_metrics.csv")
    table = table.loc[(table["alignment"] == "translation_only") & table["method"].isin(METHODS)].copy()
    return table.groupby("method", as_index=False).agg(
        boundary_distance=("mean_boundary_distance_px", "median"),
        iou=("iou", "median"),
        acm_success=("acm_success", "mean"),
    )


def sem_summary() -> pd.DataFrame:
    table = pd.read_csv(SCREEN / "SEM" / "results" / "acm_sem" / "tables" / "primary_contour_metrics.csv")
    development_ids = set(CONFIG["locked_confirmation"]["sem_acm"]["development_pillar_ids"])
    table = table.loc[table["method"].isin(METHODS) & table["pillar_id"].isin(development_ids)].copy()
    return table.groupby("method", as_index=False).agg(
        sem_boundary_pitch_pct=("mean_boundary_distance_pitch_pct", "median"),
        sem_iou=("iou", "median"),
    )


def main() -> int:
    r73 = external_summary("R73_novel_shapes").rename(columns={
        "boundary_distance": "r73_boundary_px", "iou": "r73_iou", "acm_success": "r73_acm_success"
    })
    r74 = external_summary("R74_hard_microscopy").rename(columns={
        "boundary_distance": "r74_boundary_px", "iou": "r74_iou", "acm_success": "r74_acm_success"
    })
    sem = sem_summary()
    merged = r73.merge(r74, on="method", how="outer").merge(sem, on="method", how="outer")
    merged = merged.set_index("method").reindex(METHODS).reset_index()
    merged["passes_screen"] = (
        (merged["r74_boundary_px"] < 11.2185)
        & (merged["r73_boundary_px"] <= 0.30)
        & (merged["sem_boundary_pitch_pct"] <= 0.2646)
        & (merged["r73_acm_success"] == 1.0)
        & (merged["r74_acm_success"] == 1.0)
    )
    quality_rows = merged.loc[merged["method"].str.startswith("Quality")]
    quality_gate_retained = bool(quality_rows["passes_screen"].any())
    merged.to_csv(SCREEN / "blend_screen_summary.csv", index=False)
    result = {
        "status": "complete",
        "quality_gate_retained": quality_gate_retained,
        "decision": (
            "retain the best passing quality mapping for the pilot"
            if quality_gate_retained
            else "reject the global quality gate and use data-only conservative fine-tuning"
        ),
        "screen_gates": {
            "r74_boundary_px_lt": 11.2185,
            "r73_boundary_px_max": 0.30,
            "sem_boundary_pitch_pct_max": 0.2646,
            "acm_success_required": 1.0,
        },
        "rows": merged.where(pd.notna(merged), None).to_dict(orient="records"),
    }
    (SCREEN / "decision.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# R83 Blend Screen",
        "",
        f"Global quality gate retained: **{quality_gate_retained}**",
        "",
        "| Method | R73 boundary px | R74 boundary px | SEM boundary % pitch | Pass |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in result["rows"]:
        lines.append(
            f"| {row['method']} | {row['r73_boundary_px']:.4f} | {row['r74_boundary_px']:.4f} | "
            f"{row['sem_boundary_pitch_pct']:.4f} | {'yes' if row['passes_screen'] else 'no'} |"
        )
    (SCREEN / "BLEND_SCREEN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
