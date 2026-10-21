"""Select the safer R83 pilot using developmental contour evidence only."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / "results" / "pilot_acm_screen"
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
METHODS = ["R79", "AdapterOnlyE4", "AdapterTailE4"]


def external(suite: str, prefix: str) -> pd.DataFrame:
    table = pd.read_csv(SCREEN / suite / "results" / "tables" / "primary_contour_metrics.csv")
    table = table.loc[(table["alignment"] == "translation_only") & table["method"].isin(METHODS)]
    return table.groupby("method", as_index=False).agg(**{
        f"{prefix}_boundary_px": ("mean_boundary_distance_px", "median"),
        f"{prefix}_iou": ("iou", "median"),
        f"{prefix}_acm_success": ("acm_success", "mean"),
    })


def sem_development() -> pd.DataFrame:
    table = pd.read_csv(SCREEN / "SEM" / "results" / "acm_sem" / "tables" / "primary_contour_metrics.csv")
    ids = set(CONFIG["locked_confirmation"]["sem_acm"]["development_pillar_ids"])
    table = table.loc[table["method"].isin(METHODS) & table["pillar_id"].isin(ids)]
    return table.groupby("method", as_index=False).agg(
        sem_dev_boundary_pitch_pct=("mean_boundary_distance_pitch_pct", "median"),
        sem_dev_iou=("iou", "median"),
    )


def main() -> int:
    merged = external("R73_novel_shapes", "r73").merge(external("R74_hard_microscopy", "r74"), on="method").merge(sem_development(), on="method")
    baseline = merged.loc[merged["method"] == "R79"].iloc[0]
    merged["beats_r79_r74"] = merged["r74_boundary_px"] < float(baseline["r74_boundary_px"])
    merged["r73_safe"] = merged["r73_boundary_px"] <= max(0.30, float(baseline["r73_boundary_px"]) * 1.05)
    merged["sem_dev_safe"] = merged["sem_dev_boundary_pitch_pct"] <= float(baseline["sem_dev_boundary_pitch_pct"]) * 1.10
    merged["eligible"] = merged["beats_r79_r74"] & merged["r73_safe"] & merged["sem_dev_safe"] & (merged["r73_acm_success"] == 1.0) & (merged["r74_acm_success"] == 1.0)
    candidates = merged.loc[merged["method"] != "R79"].sort_values(["eligible", "r74_boundary_px", "sem_dev_boundary_pitch_pct"], ascending=[False, True, True])
    selected = str(candidates.iloc[0]["method"])
    selected_eligible = bool(candidates.iloc[0]["eligible"])
    formal_candidate = "adapter_only" if selected == "AdapterOnlyE4" else "adapter_tail"
    decision = {
        "status": "complete",
        "selected_pilot": selected,
        "formal_candidate": formal_candidate,
        "selected_pilot_passed_all_development_gates": selected_eligible,
        "formal_training_authorized_by_screen": selected_eligible,
        "fallback_if_none_pass": "do not start formal training; revise data or loss design",
        "rows": merged.where(pd.notna(merged), None).to_dict(orient="records"),
        "reserved_sem_confirmation_was_not_read": True,
    }
    merged.to_csv(SCREEN / "pilot_screen_summary.csv", index=False)
    (SCREEN / "decision.json").write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    return 0 if selected_eligible else 2


if __name__ == "__main__":
    raise SystemExit(main())
