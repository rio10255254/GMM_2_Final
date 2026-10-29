"""Run the locked 36-pillar SEM ACM protocol on R109 causal interventions."""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results" / "structure_probe" / "sem_interventions"
CONTRACT = ROOT / "results" / "physical_validation" / "sem_acm_contract"
R82_SCRIPTS = Path(str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark/scripts'))
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
RAW = Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack'))
SEM = Path(r"H:\From_2TB_D_disk\13_thesis\SEM_data")
VARIANTS = ("full", "no_shift", "no_width", "learned_support_only", "smoothed_controls")
EXPOSURES = tuple(range(13, 25))


def prepare() -> None:
    expected = [f"{exposure}.bmp" for exposure in EXPOSURES]
    for variant in VARIANTS:
        source = SOURCE / variant
        names = sorted(path.name for path in source.glob("*.bmp"))
        if names != expected:
            raise RuntimeError(f"{variant}: expected {expected}, found {names}")
        destination = CONTRACT / "results" / "reconstructions" / "sem_acm" / variant
        destination.mkdir(parents=True, exist_ok=True)
        for name in expected:
            shutil.copy2(source / name, destination / name)
    config = {
        "experiment_id": "R113_R109SEMInterventionACM",
        "models": {variant: {"role": "frozen_intervention"} for variant in VARIANTS},
        "sem_acm": {
            "raw_input_dir": str(RAW),
            "sem_dir": str(SEM),
            "optical_exposures": list(EXPOSURES),
            "physical_pillars": 36,
            "alignment": "translation_only",
            "scale_fitting": False,
            "rotation_fitting": False,
        },
    }
    path = CONTRACT / "config" / "experiment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def ready() -> bool:
    table = CONTRACT / "results" / "acm_sem" / "tables" / "primary_contour_metrics.csv"
    sensitivity = CONTRACT / "results" / "acm_sem" / "tables" / "acm_sensitivity_metrics.csv"
    if not (table.is_file() and sensitivity.is_file()):
        return False
    return len(pd.read_csv(table)) == 12 * 36 * (1 + len(VARIANTS)) and len(pd.read_csv(sensitivity)) == 3 * 3 * 36 * (1 + len(VARIANTS))


def run_matlab() -> None:
    if ready():
        return
    expression = f"addpath('{R82_SCRIPTS.as_posix()}'); run_sem_acm_multimethod('{CONTRACT.as_posix()}')"
    completed = subprocess.run(
        [str(MATLAB), "-batch", expression],
        cwd=CONTRACT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log = CONTRACT / "logs" / "matlab_acm.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(completed.stdout, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise RuntimeError(f"MATLAB ACM failed with exit code {completed.returncode}; see {log}")
    if not ready():
        raise RuntimeError("MATLAB exited successfully but ACM output is incomplete")


def analyze() -> None:
    tables = CONTRACT / "results" / "acm_sem" / "tables"
    primary = pd.read_csv(tables / "primary_contour_metrics.csv")
    sensitivity = pd.read_csv(tables / "acm_sensitivity_metrics.csv")
    metric_columns = [
        "iou",
        "mean_boundary_distance_pitch_pct",
        "hd95_pitch_pct",
        "area_error_pct",
        "perimeter_error_pct",
        "circularity_abs_error",
    ]
    per_pillar = primary.groupby(["method", "pillar_id"], as_index=False)[metric_columns].median()
    per_pillar.to_csv(tables / "intervention_per_pillar_median.csv", index=False, encoding="utf-8-sig")
    aggregate = per_pillar.groupby("method", as_index=False)[metric_columns].median()
    aggregate.to_csv(tables / "intervention_method_summary.csv", index=False, encoding="utf-8-sig")
    per_exposure = primary.groupby(["method", "exposure"], as_index=False)[metric_columns].median()
    per_exposure.to_csv(tables / "intervention_per_exposure_median.csv", index=False, encoding="utf-8-sig")

    full = aggregate.set_index("method").loc["full"]
    effects: list[dict[str, object]] = []
    for _, row in aggregate.iterrows():
        effects.append(
            {
                "method": row["method"],
                "boundary_vs_full_pct": float((row["mean_boundary_distance_pitch_pct"] / full["mean_boundary_distance_pitch_pct"] - 1.0) * 100.0),
                "hd95_vs_full_pct": float((row["hd95_pitch_pct"] / full["hd95_pitch_pct"] - 1.0) * 100.0),
                "perimeter_vs_full_pct": float((row["perimeter_error_pct"] / full["perimeter_error_pct"] - 1.0) * 100.0),
                "iou_delta_vs_full": float(row["iou"] - full["iou"]),
            }
        )
    effect_frame = pd.DataFrame(effects)
    effect_frame.to_csv(tables / "intervention_effect_vs_full.csv", index=False, encoding="utf-8-sig")

    sensitivity_summary = sensitivity.groupby(["method", "preset"], as_index=False)[
        ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
    ].median()
    sensitivity_summary.to_csv(tables / "intervention_sensitivity_summary.csv", index=False, encoding="utf-8-sig")

    best_boundary = aggregate.loc[aggregate["mean_boundary_distance_pitch_pct"].idxmin(), "method"]
    best_perimeter = aggregate.loc[aggregate["perimeter_error_pct"].idxmin(), "method"]
    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "protocol": "locked R82/R69 36-pillar SEM ACM; translation-only alignment; 12 exposures",
        "primary_rows": len(primary),
        "sensitivity_rows": len(sensitivity),
        "methods": sorted(primary["method"].unique().tolist()),
        "aggregate": aggregate.to_dict(orient="records"),
        "effects_vs_full": effects,
        "best_boundary_method": str(best_boundary),
        "best_perimeter_method": str(best_perimeter),
        "all_finite": bool(np.isfinite(primary[metric_columns].to_numpy(float)).all()),
        "interpretation_boundary": "Interventions share frozen learned controls. Differences isolate renderer usage on the SEM stack, not retrained model capacity.",
    }
    (CONTRACT / "results" / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if len(primary) != 2592 or len(sensitivity) != 1944 or not result["all_finite"]:
        raise RuntimeError("SEM intervention ACM validation failed")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> int:
    prepare()
    run_matlab()
    analyze()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
