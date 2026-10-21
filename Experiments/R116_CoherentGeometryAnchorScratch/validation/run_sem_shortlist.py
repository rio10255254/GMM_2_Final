"""Reconstruct and run the locked 36-pillar, 12-exposure SEM ACM audit."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
import torch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "results" / "detailed_validation" / "04_sem_acm"
RAW_DIR = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\inputs\sem_paired_50x_exposure_stack")
MATLAB_SCRIPT = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\scripts\run_acm_extraction.m")
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
CANDIDATES = {
    "R116E024": ROOT / "runs" / "r116_formal_scratch_20260903_202052" / "weights" / "epoch_024.pth",
    "R116E042": ROOT / "runs" / "r116_formal_scratch_20260903_202052" / "failure_snapshot.pth",
    "R116E048": ROOT / "runs" / "r116_calibration_from_e42_20260903_235500" / "weights" / "epoch_048.pth",
}
BASELINES = {
    "R61v16": Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\results\tables\primary_contour_metrics.csv"),
    "V42E120": Path(r"D:\GMM_2_Final\Experiments\R70_V42ACMContourSEMValidation\results\tables\primary_contour_metrics.csv"),
    "R109_E048": Path(r"D:\GMM_2_Final\Experiments\R109_StagedMidpointWidthScratch\results\posttraining_acm\E048\SEM\results\tables\primary_contour_metrics.csv"),
}
METRICS = {
    "iou": "higher",
    "dice": "higher",
    "mean_boundary_distance_pitch_pct": "lower",
    "hd95_pitch_pct": "lower",
    "area_error_pct": "lower",
    "perimeter_error_pct": "lower",
    "circularity_abs_error": "lower",
}

from inference.tiled import forward_tiled
from model.r116_model import build_model


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(f"Could not read {path}")
    return value


def write_gray(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".bmp", value.astype(np.uint8))
    if not success:
        raise RuntimeError(f"Could not encode {path}")
    encoded.tofile(str(path))


def load_model(checkpoint: Path, device: torch.device):
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if saved.get("scratch") is not True:
        raise RuntimeError(f"Checkpoint is not scratch: {checkpoint}")
    model = build_model().to(device)
    model.load_state_dict(saved["model"], strict=True)
    model.requires_grad_(False)
    return model.eval()


@torch.inference_mode()
def reconstruct_model(name: str, checkpoint: Path, device: torch.device) -> Path:
    destination = OUTPUT / name / "reconstructions"
    model = load_model(checkpoint, device)
    for exposure in range(13, 25):
        source = RAW_DIR / f"{exposure}.bmp"
        raw = read_gray(source)
        tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
        output = forward_tiled(model, tensor, core_size=512, halo=224)
        image = np.rint(output[0, 0].clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)
        write_gray(destination / source.name, image)
        print(json.dumps({"model": name, "exposure": exposure}), flush=True)
    del model
    torch.cuda.empty_cache()
    return destination


def run_acm(name: str, recon_dir: Path) -> tuple[Path, Path]:
    experiment_root = OUTPUT / name
    primary = experiment_root / "results" / "tables" / "primary_contour_metrics.csv"
    sensitivity = experiment_root / "results" / "tables" / "acm_sensitivity_metrics.csv"
    if not (primary.is_file() and sensitivity.is_file()):
        expression = (
            f"addpath('{MATLAB_SCRIPT.parent.as_posix()}'); "
            f"run_acm_extraction('{experiment_root.as_posix()}',"
            f"'{RAW_DIR.as_posix()}',"
            f"'{recon_dir.as_posix()}',"
            f"'{name}');"
        )
        completed = subprocess.run(
            [str(MATLAB), "-batch", expression], cwd=ROOT,
            text=True, capture_output=True, encoding="utf-8", errors="replace",
        )
        (experiment_root / "matlab_stdout.log").write_text(completed.stdout, encoding="utf-8")
        (experiment_root / "matlab_stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(f"{name} MATLAB ACM failed: {completed.stderr[-1200:]}")
    frame = pd.read_csv(primary)
    sensitivity_frame = pd.read_csv(sensitivity)
    if len(frame) != 864 or len(sensitivity_frame) != 648:
        raise RuntimeError(f"{name}: unexpected SEM ACM row counts")
    if set(frame["method"]) != {"Raw", name} or frame.isna().any().any():
        raise RuntimeError(f"{name}: incomplete primary SEM ACM output")
    if set(sensitivity_frame["method"]) != {"Raw", name} or sensitivity_frame.isna().any().any():
        raise RuntimeError(f"{name}: incomplete sensitivity SEM ACM output")
    return primary, sensitivity


def improvement(raw: np.ndarray, model: np.ndarray, direction: str) -> np.ndarray:
    return model - raw if direction == "higher" else raw - model


def summarize_primary(frame: pd.DataFrame, model_name: str, source: str) -> tuple[list[dict], list[dict]]:
    grouped = frame.groupby(["pillar_id", "method"])[list(METRICS)].median().unstack("method")
    metric_rows = []
    rng = np.random.default_rng(116404 + sum(ord(value) for value in model_name))
    for metric, direction in METRICS.items():
        raw = grouped[(metric, "Raw")].to_numpy(float)
        model = grouped[(metric, model_name)].to_numpy(float)
        delta = improvement(raw, model, direction)
        samples = np.median(delta[rng.integers(0, len(delta), size=(20000, len(delta)))], axis=1)
        low, high = np.quantile(samples, [0.025, 0.975])
        try:
            p_value = float(wilcoxon(model, raw, alternative="two-sided", zero_method="wilcox").pvalue)
        except ValueError:
            p_value = 1.0
        metric_rows.append({
            "model": model_name,
            "source": source,
            "metric": metric,
            "direction": direction,
            "independent_pillars": len(raw),
            "raw_median": float(np.median(raw)),
            "model_median": float(np.median(model)),
            "median_improvement": float(np.median(delta)),
            "bootstrap_ci95_low": float(low),
            "bootstrap_ci95_high": float(high),
            "improved_pillars": int(np.sum(delta > 0)),
            "unchanged_pillars": int(np.sum(delta == 0)),
            "worsened_pillars": int(np.sum(delta < 0)),
            "improved_fraction": float(np.mean(delta > 0)),
            "wilcoxon_p": p_value,
        })
    exposure_rows = []
    for exposure, group in frame.groupby("exposure", sort=True):
        pivot = group.pivot(index="pillar_id", columns="method", values="mean_boundary_distance_pitch_pct")
        delta = pivot["Raw"].to_numpy(float) - pivot[model_name].to_numpy(float)
        exposure_rows.append({
            "model": model_name,
            "source": source,
            "exposure": int(exposure),
            "raw_boundary_median_pitch_pct": float(pivot["Raw"].median()),
            "model_boundary_median_pitch_pct": float(pivot[model_name].median()),
            "median_improvement_pitch_pct": float(np.median(delta)),
            "improved_pillars": int(np.sum(delta > 0)),
            "improved_fraction": float(np.mean(delta > 0)),
        })
    return metric_rows, exposure_rows


def summarize_sensitivity(frame: pd.DataFrame, model_name: str) -> list[dict]:
    rows = []
    for (preset, exposure), group in frame.groupby(["preset", "exposure"], sort=False):
        pivot = group.pivot(index="pillar_id", columns="method", values="mean_boundary_distance_pitch_pct")
        delta = pivot["Raw"].to_numpy(float) - pivot[model_name].to_numpy(float)
        rows.append({
            "model": model_name,
            "preset": preset,
            "exposure": int(exposure),
            "median_improvement_pitch_pct": float(np.median(delta)),
            "improved_pillars": int(np.sum(delta > 0)),
            "direction": "improved" if float(np.median(delta)) > 0 else "worsened" if float(np.median(delta)) < 0 else "unchanged",
        })
    return rows


def baseline_method(path: Path) -> str:
    methods = set(pd.read_csv(path, usecols=["method"])["method"])
    methods.discard("Raw")
    if len(methods) != 1:
        raise RuntimeError(f"Could not identify baseline model in {path}")
    return next(iter(methods))


def raw_signature(frame: pd.DataFrame) -> pd.DataFrame:
    metrics = ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "perimeter_error_pct", "circularity_abs_error"]
    return frame.loc[frame.method.eq("Raw"), ["exposure", "pillar_id", *metrics]].sort_values(["exposure", "pillar_id"]).reset_index(drop=True)


def main() -> int:
    if not MATLAB.is_file():
        raise FileNotFoundError(MATLAB)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0")
    metric_rows = []
    exposure_rows = []
    sensitivity_rows = []
    run_records = []
    raw_tables = []
    for name, checkpoint in CANDIDATES.items():
        recon = reconstruct_model(name, checkpoint, device)
        primary_path, sensitivity_path = run_acm(name, recon)
        primary = pd.read_csv(primary_path)
        sensitivity = pd.read_csv(sensitivity_path)
        metrics, exposures = summarize_primary(primary, name, "R116 locked rerun")
        metric_rows.extend(metrics)
        exposure_rows.extend(exposures)
        sensitivity_rows.extend(summarize_sensitivity(sensitivity, name))
        raw_tables.append((name, raw_signature(primary)))
        run_records.append({
            "model": name,
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": sha256(checkpoint),
            "primary_rows": len(primary),
            "sensitivity_rows": len(sensitivity),
            "status": "complete",
        })
        print(json.dumps({"model": name, "status": "acm_complete"}), flush=True)
    for requested_name, path in BASELINES.items():
        primary = pd.read_csv(path)
        actual_name = baseline_method(path)
        metrics, exposures = summarize_primary(primary, actual_name, str(path))
        for row in metrics:
            row["model"] = requested_name
        for row in exposures:
            row["model"] = requested_name
        metric_rows.extend(metrics)
        exposure_rows.extend(exposures)
        raw_tables.append((requested_name, raw_signature(primary)))
    reference = raw_tables[0][1]
    raw_deltas = {}
    for name, table in raw_tables:
        merged = reference.merge(table, on=["exposure", "pillar_id"], suffixes=("_reference", "_candidate"), validate="one_to_one")
        numeric = [column.removesuffix("_reference") for column in merged if column.endswith("_reference")]
        raw_deltas[name] = max(
            float(np.max(np.abs(merged[f"{metric}_reference"] - merged[f"{metric}_candidate"])))
            for metric in numeric
        )
    metric_frame = pd.DataFrame(metric_rows)
    exposure_frame = pd.DataFrame(exposure_rows)
    sensitivity_frame = pd.DataFrame(sensitivity_rows)
    metric_frame.to_csv(OUTPUT / "metric_summary.csv", index=False, encoding="utf-8-sig")
    exposure_frame.to_csv(OUTPUT / "exposure_boundary_summary.csv", index=False, encoding="utf-8-sig")
    sensitivity_frame.to_csv(OUTPUT / "sensitivity_direction_summary.csv", index=False, encoding="utf-8-sig")
    headline = {}
    for model, group in metric_frame.groupby("model", sort=False):
        indexed = group.set_index("metric")
        exposure = exposure_frame[exposure_frame.model.eq(model)].set_index("exposure")
        headline[model] = {
            "boundary_raw_median_pitch_pct": float(indexed.loc["mean_boundary_distance_pitch_pct", "raw_median"]),
            "boundary_model_median_pitch_pct": float(indexed.loc["mean_boundary_distance_pitch_pct", "model_median"]),
            "boundary_median_improvement_pitch_pct": float(indexed.loc["mean_boundary_distance_pitch_pct", "median_improvement"]),
            "boundary_improved_pillars": int(indexed.loc["mean_boundary_distance_pitch_pct", "improved_pillars"]),
            "iou_median_improvement": float(indexed.loc["iou", "median_improvement"]),
            "perimeter_median_improvement_pct": float(indexed.loc["perimeter_error_pct", "median_improvement"]),
            "circularity_median_improvement": float(indexed.loc["circularity_abs_error", "median_improvement"]),
            "normal_exposures_13_22_all_majority_improved": bool((exposure.loc[13:22, "improved_fraction"] >= 0.5).all()),
            "dark_exposure_23_improved_fraction": float(exposure.loc[23, "improved_fraction"]),
            "dark_exposure_24_improved_fraction": float(exposure.loc[24, "improved_fraction"]),
        }
    payload = {
        "status": "complete",
        "independent_unit": "physical_pillar",
        "independent_pillars": 36,
        "repeated_exposures": 12,
        "r116_runs": run_records,
        "raw_baseline_max_metric_delta": raw_deltas,
        "raw_population_comparable": all(value == 0.0 for value in raw_deltas.values()),
        "headline": headline,
        "claim_boundary": "The 432 exposure-pillar observations contain only 36 independent physical pillars; darkest exposures must be reported separately."
    }
    (OUTPUT / "summary.json").write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
