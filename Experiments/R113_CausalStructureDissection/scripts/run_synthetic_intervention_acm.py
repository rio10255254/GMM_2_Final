"""Run locked R73/R74 ACM protocols on frozen R109 interventions."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
RECON = ROOT / "results" / "physical_validation" / "intervention_reconstructions"
OUTPUT = ROOT / "results" / "physical_validation" / "synthetic_acm"
R82_SCRIPTS = Path(str(PROJECT_ROOT / 'Experiments/R82_R39R40CrossSceneGeneralizationBenchmark/scripts'))
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
VARIANTS = ("full", "no_shift", "no_width", "learned_support_only", "smoothed_controls")
SUITES = {
    "R73": {
        "template": Path(str(PROJECT_ROOT / 'Experiments/R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R73_novel_shapes/config/experiment.json')),
        "source_root": Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val')),
    },
    "R74": {
        "template": Path(str(PROJECT_ROOT / 'Experiments/R104_PhotometricInvariantCausalGateScratch/results/posttraining_validation/external_acm/R74_hard_microscopy/config/experiment.json')),
        "source_root": Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val')),
    },
}


def prepare(suite: str, specification: dict[str, Path]) -> tuple[Path, int, int]:
    contract = OUTPUT / f"{suite}_contract"
    config = json.loads(specification["template"].read_text(encoding="utf-8"))
    config["experiment_id"] = f"R113_{suite}_R109Interventions"
    config["dataset"]["root"] = str(specification["source_root"])
    config_path = contract / "config" / "experiment.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    methods = ["Raw", *VARIANTS]
    output_dirs: dict[str, dict[str, str]] = {method: {} for method in methods}
    for family in config["dataset"]["families"]:
        family_name = family["name"]
        stage = family["stage"]
        output_dirs["Raw"][family_name] = str(specification["source_root"] / "src" / stage)
        for variant in VARIANTS:
            output_dirs[variant][family_name] = str(RECON / suite / variant / stage)
    manifest = {"suite": suite, "methods": methods, "output_dirs": output_dirs}
    manifest_path = contract / "results" / "inference_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    expected_primary = int(config["dataset"]["total_images"]) * len(methods) * 2
    expected_sensitivity = len(config["dataset"]["families"]) * len(config["acm"]["sensitivity_filenames"]) * len(config["acm"]["sensitivity_presets"]) * len(methods)
    return contract, expected_primary, expected_sensitivity


def ready(contract: Path, expected_primary: int, expected_sensitivity: int) -> bool:
    tables = contract / "results" / "tables"
    primary = tables / "primary_contour_metrics.csv"
    sensitivity = tables / "acm_sensitivity_metrics.csv"
    return primary.is_file() and sensitivity.is_file() and len(pd.read_csv(primary)) == expected_primary and len(pd.read_csv(sensitivity)) == expected_sensitivity


def run_matlab(contract: Path, expected_primary: int, expected_sensitivity: int) -> None:
    if ready(contract, expected_primary, expected_sensitivity):
        return
    expression = f"addpath('{R82_SCRIPTS.as_posix()}'); run_acm_multimethod('{contract.as_posix()}')"
    completed = subprocess.run([str(MATLAB), "-batch", expression], cwd=contract, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = contract / "logs" / "matlab_acm.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(completed.stdout, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise RuntimeError(f"{contract.name}: MATLAB failed; see {log}")
    if not ready(contract, expected_primary, expected_sensitivity):
        raise RuntimeError(f"{contract.name}: incomplete ACM output")


def analyze_suite(suite: str, contract: Path, expected_primary: int, expected_sensitivity: int) -> dict[str, object]:
    tables = contract / "results" / "tables"
    primary = pd.read_csv(tables / "primary_contour_metrics.csv")
    sensitivity = pd.read_csv(tables / "acm_sensitivity_metrics.csv")
    translated = primary.loc[primary["alignment"].eq("translation_only")].copy()
    metrics = ["iou", "mean_boundary_distance_px", "hd95_px", "area_error_pct", "perimeter_error_pct"]
    overall = translated.groupby("method", as_index=False)[metrics].median()
    family = translated.groupby(["method", "family"], as_index=False)[metrics].median()
    overall.to_csv(tables / "intervention_method_summary.csv", index=False, encoding="utf-8-sig")
    family.to_csv(tables / "intervention_family_summary.csv", index=False, encoding="utf-8-sig")
    full = overall.set_index("method").loc["full"]
    effects = []
    for _, row in overall.iterrows():
        effects.append({
            "method": row["method"],
            "boundary_vs_full_pct": float((row["mean_boundary_distance_px"] / full["mean_boundary_distance_px"] - 1.0) * 100.0),
            "hd95_vs_full_pct": float((row["hd95_px"] / full["hd95_px"] - 1.0) * 100.0),
            "perimeter_vs_full_pct": float((row["perimeter_error_pct"] / full["perimeter_error_pct"] - 1.0) * 100.0),
            "iou_delta_vs_full": float(row["iou"] - full["iou"]),
        })
    pd.DataFrame(effects).to_csv(tables / "intervention_effect_vs_full.csv", index=False, encoding="utf-8-sig")
    failures = primary.groupby("method")["acm_success"].apply(lambda values: int((~values.astype(bool)).sum())).to_dict()
    result = {
        "suite": suite,
        "primary_rows": len(primary),
        "sensitivity_rows": len(sensitivity),
        "translation_rows": len(translated),
        "methods": sorted(primary["method"].unique().tolist()),
        "aggregate": overall.to_dict(orient="records"),
        "effects_vs_full": effects,
        "families": family.to_dict(orient="records"),
        "acm_failures": failures,
        "all_finite": bool(np.isfinite(translated[metrics].to_numpy(float)).all()),
        "expected_primary_rows": expected_primary,
        "expected_sensitivity_rows": expected_sensitivity,
    }
    if len(primary) != expected_primary or len(sensitivity) != expected_sensitivity or not result["all_finite"]:
        raise RuntimeError(f"{suite}: validation failed")
    return result


def main() -> int:
    results = []
    for suite, specification in SUITES.items():
        contract, expected_primary, expected_sensitivity = prepare(suite, specification)
        run_matlab(contract, expected_primary, expected_sensitivity)
        results.append(analyze_suite(suite, contract, expected_primary, expected_sensitivity))
    payload = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "protocol": "locked R73/R74 Chan-Vese ACM with exact geometry truth and translation-only primary comparison",
        "suites": results,
        "interpretation_boundary": "Frozen interventions isolate use of learned R109 controls; they do not test a retrained estimator.",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
