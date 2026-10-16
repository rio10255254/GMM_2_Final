"""Summarize the locked SEM ACM stage ablation and identify the harmful stage."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results" / "sem_acm_stage_g0p25"
OUTPUT = ROOT / "results" / "sem_stage_analysis_g0p25"
STAGES = ("denoise", "edge", "texture")
KEYS = ("exposure", "pillar_id")
METRICS = (
    "iou",
    "mean_boundary_distance_pitch_pct",
    "hd95_pitch_pct",
    "area_error_pct",
    "perimeter_error_pct",
    "circularity_abs_error",
)


def load_stage(stage: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = SOURCE / stage / "results" / "tables" / "primary_contour_metrics.csv"
    sensitivity = SOURCE / stage / "results" / "tables" / "acm_sensitivity_metrics.csv"
    primary = pd.read_csv(table)
    audit = pd.read_csv(sensitivity)
    if len(primary) != 864 or len(audit) != 648:
        raise RuntimeError(f"Incomplete ACM outputs for {stage}: {len(primary)}, {len(audit)}")
    model_rows = primary[primary.method != "Raw"].copy()
    raw_rows = primary[primary.method == "Raw"].copy()
    if len(model_rows) != 432 or len(raw_rows) != 432:
        raise RuntimeError(f"Unexpected primary split for {stage}")
    return primary, audit


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    overall_rows: list[dict[str, object]] = []
    exposure_rows: list[dict[str, object]] = []
    pillar_rows: list[dict[str, object]] = []
    transition_rows: list[dict[str, object]] = []
    sensitivity_rows: list[dict[str, object]] = []
    stage_models: dict[str, pd.DataFrame] = {}
    raw_reference: pd.DataFrame | None = None

    for stage in STAGES:
        primary, audit = load_stage(stage)
        raw = primary[primary.method == "Raw"].sort_values(list(KEYS)).reset_index(drop=True)
        model = primary[primary.method != "Raw"].sort_values(list(KEYS)).reset_index(drop=True)
        stage_models[stage] = model
        if raw_reference is None:
            raw_reference = raw
        elif not np.allclose(raw[list(METRICS)].to_numpy(), raw_reference[list(METRICS)].to_numpy()):
            raise RuntimeError("Raw ACM reference changed between stages")
        row: dict[str, object] = {"stage": stage, "observations": len(model)}
        for metric in METRICS:
            row[f"raw_{metric}_median"] = float(raw[metric].median())
            row[f"model_{metric}_median"] = float(model[metric].median())
        row["boundary_wins_of_432"] = int(
            (model["mean_boundary_distance_pitch_pct"] < raw["mean_boundary_distance_pitch_pct"]).sum()
        )
        row["iou_wins_of_432"] = int((model["iou"] > raw["iou"]).sum())
        row["joint_wins_of_432"] = int(
            (
                (model["mean_boundary_distance_pitch_pct"] < raw["mean_boundary_distance_pitch_pct"])
                & (model["iou"] > raw["iou"])
            ).sum()
        )
        overall_rows.append(row)

        for exposure in sorted(model.exposure.unique()):
            raw_group = raw[raw.exposure == exposure]
            model_group = model[model.exposure == exposure]
            exposure_rows.append(
                {
                    "stage": stage,
                    "exposure": int(exposure),
                    "raw_iou_median": float(raw_group.iou.median()),
                    "model_iou_median": float(model_group.iou.median()),
                    "raw_boundary_median": float(raw_group.mean_boundary_distance_pitch_pct.median()),
                    "model_boundary_median": float(model_group.mean_boundary_distance_pitch_pct.median()),
                    "boundary_wins_of_36": int(
                        (
                            model_group.mean_boundary_distance_pitch_pct.to_numpy()
                            < raw_group.mean_boundary_distance_pitch_pct.to_numpy()
                        ).sum()
                    ),
                }
            )

        for pillar in sorted(model.pillar_id.unique()):
            raw_group = raw[raw.pillar_id == pillar]
            model_group = model[model.pillar_id == pillar]
            pillar_rows.append(
                {
                    "stage": stage,
                    "pillar_id": int(pillar),
                    "raw_iou_median": float(raw_group.iou.median()),
                    "model_iou_median": float(model_group.iou.median()),
                    "raw_boundary_median": float(raw_group.mean_boundary_distance_pitch_pct.median()),
                    "model_boundary_median": float(model_group.mean_boundary_distance_pitch_pct.median()),
                    "boundary_improved": bool(
                        model_group.mean_boundary_distance_pitch_pct.median()
                        < raw_group.mean_boundary_distance_pitch_pct.median()
                    ),
                }
            )

        audit_model = audit[audit.method != "Raw"]
        audit_raw = audit[audit.method == "Raw"]
        sensitivity_rows.append(
            {
                "stage": stage,
                "records": len(audit_model),
                "raw_iou_median": float(audit_raw.iou.median()),
                "model_iou_median": float(audit_model.iou.median()),
                "raw_boundary_median": float(audit_raw.mean_boundary_distance_pitch_pct.median()),
                "model_boundary_median": float(audit_model.mean_boundary_distance_pitch_pct.median()),
            }
        )

    assert raw_reference is not None
    for previous, current in zip(STAGES, STAGES[1:]):
        before = stage_models[previous]
        after = stage_models[current]
        for metric in METRICS:
            lower_is_better = metric != "iou"
            difference = after[metric].to_numpy() - before[metric].to_numpy()
            improvement = difference < 0 if lower_is_better else difference > 0
            transition_rows.append(
                {
                    "transition": f"{previous}_to_{current}",
                    "metric": metric,
                    "median_before": float(before[metric].median()),
                    "median_after": float(after[metric].median()),
                    "median_change": float(np.median(difference)),
                    "improved_observations_of_432": int(improvement.sum()),
                }
            )

    overall = pd.DataFrame(overall_rows)
    exposure = pd.DataFrame(exposure_rows)
    pillar = pd.DataFrame(pillar_rows)
    transitions = pd.DataFrame(transition_rows)
    sensitivity = pd.DataFrame(sensitivity_rows)
    overall.to_csv(OUTPUT / "overall.csv", index=False)
    exposure.to_csv(OUTPUT / "by_exposure.csv", index=False)
    pillar.to_csv(OUTPUT / "by_pillar.csv", index=False)
    transitions.to_csv(OUTPUT / "stage_transitions.csv", index=False)
    sensitivity.to_csv(OUTPUT / "sensitivity_summary.csv", index=False)

    conclusion = {
        "status": "complete",
        "records_verified": {"primary_per_stage": 864, "sensitivity_per_stage": 648},
        "best_stage_by_boundary": str(overall.loc[overall.model_mean_boundary_distance_pitch_pct_median.idxmin(), "stage"]),
        "best_stage_by_iou": str(overall.loc[overall.model_iou_median.idxmax(), "stage"]),
        "pillar_boundary_wins": {
            stage: int(pillar[(pillar.stage == stage) & pillar.boundary_improved].shape[0]) for stage in STAGES
        },
        "exposure_18": exposure[exposure.exposure == 18].to_dict(orient="records"),
    }
    (OUTPUT / "summary.json").write_text(json.dumps(conclusion, indent=2), encoding="utf-8")
    print(json.dumps(conclusion), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
