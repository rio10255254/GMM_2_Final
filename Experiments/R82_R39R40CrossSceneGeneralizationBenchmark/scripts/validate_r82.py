from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
RECON = RESULTS / "reconstructions"
FIGURES = RESULTS / "figures"
MODELS = list(CONFIG["models"])
METHODS = ["Raw", *MODELS]


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def require_finite_metrics(frame: pd.DataFrame, message: str) -> None:
    metric_columns = [
        "iou", "dice", "mean_boundary_distance_px", "hd95_px",
        "area_error_pct", "perimeter_error_pct", "roughness_abs_error",
    ]
    available = [column for column in metric_columns if column in frame.columns]
    require(bool(available), f"{message}: metric columns missing")
    values = frame[available].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    require(np.isfinite(values).all(), f"{message}: non-finite metric values")


def check_inference() -> dict:
    expected = {
        "real_fov": 301,
        "junhua": 200,
        "R73_novel_shapes": 100,
        "R74_hard_microscopy": 100,
        "sem_acm": 12,
    }
    result = {}
    for dataset, count in expected.items():
        result[dataset] = {}
        for model in MODELS:
            manifest_path = RECON / dataset / model / "inference_manifest.json"
            require(manifest_path.is_file(), f"missing inference manifest: {dataset}/{model}")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            records = manifest.get("records", [])
            require(int(manifest.get("image_count", -1)) == count, f"wrong image count: {dataset}/{model}")
            require(len(records) == count and all(Path(row["output"]).is_file() for row in records), f"incomplete outputs: {dataset}/{model}")
            result[dataset][model] = count
    return result


def check_external_acm() -> dict:
    result = {}
    for suite in CONFIG["external_acm_suites"]:
        root = RESULTS / "acm_external" / suite / "results" / "tables"
        primary = pd.read_csv(root / "primary_contour_metrics.csv")
        sensitivity = pd.read_csv(root / "acm_sensitivity_metrics.csv")
        truth = pd.read_csv(root / "truth_acm_geometry_qa.csv")
        require(len(primary) == 100 * len(METHODS) * 2, f"{suite}: primary row count")
        require(len(sensitivity) == 5 * 3 * 3 * len(METHODS), f"{suite}: sensitivity row count")
        require(len(truth) == 100, f"{suite}: truth QA count")
        require(set(primary["method"]) == set(METHODS), f"{suite}: methods")
        require("acm_success" in primary and "acm_success" in sensitivity, f"{suite}: extraction status missing")
        require_finite_metrics(primary, f"{suite}: primary")
        require_finite_metrics(sensitivity, f"{suite}: sensitivity")
        require((truth["iou"] >= 0.97).all(), f"{suite}: truth ACM QA below 0.97 IoU")
        translated = primary.loc[primary["alignment"] == "translation_only"]
        require(len(translated) == 100 * len(METHODS), f"{suite}: translation pairing")
        require(translated.groupby("image_id")["method"].nunique().eq(len(METHODS)).all(), f"{suite}: image pairing")
        primary_success = primary["acm_success"].astype(str).str.lower().isin({"true", "1"})
        sensitivity_success = sensitivity["acm_success"].astype(str).str.lower().isin({"true", "1"})
        result[suite] = {
            "primary_rows": len(primary),
            "sensitivity_rows": len(sensitivity),
            "truth_min_iou": float(truth["iou"].min()),
            "primary_failure_rows": int((~primary_success).sum()),
            "sensitivity_failure_rows": int((~sensitivity_success).sum()),
        }
    return result


def check_sem() -> dict:
    root = RESULTS / "acm_sem" / "tables"
    primary = pd.read_csv(root / "primary_contour_metrics.csv")
    sensitivity = pd.read_csv(root / "acm_sensitivity_metrics.csv")
    require(len(primary) == 12 * 36 * len(METHODS), "SEM primary row count")
    require(len(sensitivity) == 3 * 3 * 36 * len(METHODS), "SEM sensitivity row count")
    require(set(primary["method"]) == set(METHODS), "SEM method coverage")
    require(primary.groupby(["exposure", "pillar_id"])["method"].nunique().eq(len(METHODS)).all(), "SEM pairing")
    require(not primary.isna().any().any() and not sensitivity.isna().any().any(), "SEM NaN values")
    return {"primary_rows": len(primary), "sensitivity_rows": len(sensitivity), "pillars": int(primary["pillar_id"].nunique()), "exposures": int(primary["exposure"].nunique())}


def check_summaries() -> dict:
    real = pd.read_csv(TABLES / "real_motion_summary.csv")
    junhua = pd.read_csv(TABLES / "junhua_local_summary.csv")
    external = pd.read_csv(TABLES / "external_acm_summary.csv")
    sem = pd.read_csv(TABLES / "sem_acm_summary.csv")
    require(len(real) == 6 * len(MODELS), "real summary coverage")
    require(set(real["method"]) == set(MODELS), "real summary methods")
    require(not real.isna().any().any(), "real summary NaN")
    require(len(junhua) == 3 * len(METHODS), "JunHua summary coverage")
    require(set(junhua["method"]) == set(METHODS), "JunHua summary methods")
    require(not junhua[["valid_fraction", "step_std_px", "median_ecc"]].isna().any().any(), "JunHua summary NaN")
    require(len(external) == 2 * len(METHODS), "external ACM summary coverage")
    require(len(sem) == len(METHODS), "SEM summary coverage")

    primary = pd.read_csv(TABLES / "external_acm_primary_combined.csv")
    primary = primary.loc[primary["alignment"] == "translation_only"]
    for (suite, method), group in primary.groupby(["suite", "method"]):
        stored = external.loc[(external["suite"] == suite) & (external["method"] == method)].iloc[0]
        require(np.isclose(stored["median_iou"], group["iou"].median(), atol=1e-12), f"external summary recompute {suite}/{method}")
        require(np.isclose(stored["median_mean_boundary_distance_px"], group["mean_boundary_distance_px"].median(), atol=1e-12), f"external boundary recompute {suite}/{method}")
    per_pillar = pd.read_csv(TABLES / "sem_acm_per_pillar.csv")
    for method, group in per_pillar.groupby("method"):
        stored = sem.loc[sem["method"] == method].iloc[0]
        require(np.isclose(stored["median_iou"], group["median_iou"].median(), atol=1e-12), f"SEM summary recompute {method}")
    return {"real_rows": len(real), "junhua_rows": len(junhua), "external_rows": len(external), "sem_rows": len(sem)}


def check_parity() -> dict:
    references = {
        "R61": Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/results/inference_runs/reconstruct_progress_best_tradeoff_in_sem_paired_50x_exposure_stack_20260623_200020/r61v16_psfoff_sem_paired_50x')),
        "R79": Path(str(PROJECT_ROOT / 'Experiments/R80_R79E23vsE100GeneralizationValidation/results/reconstructions/sem/R79E23')),
    }
    result = {}
    for model, reference in references.items():
        mean_values = []
        maximum = 0
        for exposure in CONFIG["sem_acm"]["optical_exposures"]:
            current = read_gray(RECON / "sem_acm" / model / f"{exposure}.bmp").astype(np.int16)
            prior = read_gray(reference / f"{exposure}.bmp").astype(np.int16)
            difference = np.abs(current - prior)
            mean_values.append(float(difference.mean()))
            maximum = max(maximum, int(difference.max()))
        require(maximum == 0, f"{model} parity changed")
        result[model] = {"mean_absolute_difference": float(np.mean(mean_values)), "maximum_absolute_difference": maximum}
    (RESULTS / "parity_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def check_artifacts() -> dict:
    report = ROOT / "reports" / "R82_RESULTS_TW.md"
    figures = [
        FIGURES / "01_contour_truth_summary.png",
        FIGURES / "02_real_motion_summary.png",
        FIGURES / "03_junhua_stability.png",
        FIGURES / "04_R74_fixed_contact_sheet.png",
        FIGURES / "05_SEM_paired_exposure18.png",
        FIGURES / "06_real_fixed_contact_sheet.png",
    ]
    require(report.is_file() and report.stat().st_size > 1000, "report missing")
    require(all(path.is_file() and path.stat().st_size > 10000 for path in figures), "one or more figures missing")
    decision = RESULTS / "decision.json"
    require(decision.is_file() and json.loads(decision.read_text(encoding="utf-8")).get("selection"), "decision missing")
    return {"report": str(report), "figures": len(figures), "decision": str(decision)}


def main() -> int:
    FIGURES.mkdir(parents=True, exist_ok=True)
    result = {
        "status": "passed",
        "inference": check_inference(),
        "external_acm": check_external_acm(),
        "sem_acm": check_sem(),
        "summaries": check_summaries(),
        "reference_parity": check_parity(),
        "artifacts": check_artifacts(),
    }
    (RESULTS / "validation_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
