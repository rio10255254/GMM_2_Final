"""Run the locked central-36 SEM ACM contour validation for R100 E40."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.io import loadmat
from scipy.ndimage import center_of_mass
from scipy.stats import wilcoxon
from skimage.measure import find_contours
import torch


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "config" / "posttraining_validation_protocol.json"
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
MODEL_PATH = ROOT / "model" / "r100_model.py"
INFERENCE_PATH = ROOT / "inference" / "reconstruct.py"
OUTPUT = ROOT / "results" / "posttraining_validation" / "sem_contour"
RECON = OUTPUT / "reconstructions"
TABLES = OUTPUT / "results" / "tables"
FIGURES = OUTPUT / "figures"
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
SHARED_ACM = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\scripts\run_acm_extraction.m")
METHODS = ["Raw", "R61v16", "V42E120", "R75v2E100", "R96E44", "R97E48", "R100E40"]
METRICS = {
    "iou": "higher",
    "dice": "higher",
    "mean_boundary_distance_pitch_pct": "lower",
    "hd95_pitch_pct": "lower",
    "area_error_pct": "lower",
    "perimeter_error_pct": "lower",
    "circularity_abs_error": "lower",
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODEL = load_module("r100_post_sem_model", MODEL_PATH)
INFERENCE = load_module("r100_post_sem_inference", INFERENCE_PATH)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(path)
    return image


def write_gray(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise RuntimeError(path)
    encoded.tofile(path)


def bootstrap_median_ci(values: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    sampled = values[rng.integers(0, len(values), size=(20000, len(values)))]
    return tuple(float(value) for value in np.quantile(np.median(sampled, axis=1), [0.025, 0.975]))


def matlab_round(values: np.ndarray) -> np.ndarray:
    return np.sign(values) * np.floor(np.abs(values) + 0.5)


def align_to_truth(predicted: np.ndarray, truth: np.ndarray) -> np.ndarray:
    dy, dx = matlab_round(np.asarray(center_of_mass(truth)) - np.asarray(center_of_mass(predicted))).astype(int)
    aligned = np.zeros_like(predicted, dtype=bool)
    sy = slice(max(0, -dy), min(predicted.shape[0], predicted.shape[0] - dy))
    sx = slice(max(0, -dx), min(predicted.shape[1], predicted.shape[1] - dx))
    ty = slice(max(0, dy), min(predicted.shape[0], predicted.shape[0] + dy))
    tx = slice(max(0, dx), min(predicted.shape[1], predicted.shape[1] + dx))
    aligned[ty, tx] = predicted[sy, sx]
    return aligned


def reconstruct(protocol: dict) -> dict:
    arm = protocol["sem_contour_arm"]
    raw_dir = Path(arm["raw_input_dir"])
    checkpoint_path = Path(protocol["checkpoint"])
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(checkpoint["epoch"]) != int(protocol["primary_checkpoint_epoch"]):
        raise RuntimeError("Final checkpoint epoch mismatch")
    design = read_json(DESIGN_PATH)
    model = MODEL.build_model(base=int(design["architecture"]["model_width"]))
    model.load_state_dict(checkpoint[protocol["checkpoint_state"]], strict=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model.eval().to(device)
    records: list[dict[str, object]] = []
    for exposure in arm["exposures"]:
        source_path = raw_dir / f"{exposure}.bmp"
        raw = read_gray(source_path)
        tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
        with torch.inference_mode():
            prediction = INFERENCE.reconstruct_tensor(model, tensor, core_size=512, halo=192, tile_batch=1)[0, 0]
        output = np.rint(prediction.clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)
        destination = RECON / source_path.name
        write_gray(destination, output)
        records.append({
            "exposure": exposure, "source": str(source_path), "source_sha256": sha256_file(source_path),
            "output": str(destination), "output_sha256": sha256_file(destination),
            "mean_abs_change_gray": float(np.mean(np.abs(output.astype(np.float32) - raw.astype(np.float32)))),
            "maximum_abs_change_gray": int(np.max(np.abs(output.astype(np.int16) - raw.astype(np.int16)))),
        })
        print(f"[sem-recon] exposure {exposure}", flush=True)
    pd.DataFrame(records).to_csv(OUTPUT / "reconstruction_manifest.csv", index=False)
    return {
        "checkpoint": str(checkpoint_path), "checkpoint_epoch": int(checkpoint["epoch"]),
        "checkpoint_sha256": sha256_file(checkpoint_path), "checkpoint_state": protocol["checkpoint_state"],
        "records": records,
    }


def run_acm(protocol: dict) -> None:
    arm = protocol["sem_contour_arm"]
    raw_dir = Path(arm["raw_input_dir"])
    sem_dir = Path(arm["sem_dir"])
    mapping = Path(arm["ordering_mapping"])
    for required in (MATLAB, SHARED_ACM, raw_dir, sem_dir, mapping):
        if not required.exists():
            raise FileNotFoundError(required)
    expression = (
        f"addpath('{SHARED_ACM.parent.as_posix()}');"
        f"run_acm_extraction('{OUTPUT.as_posix()}','{raw_dir.as_posix()}',"
        f"'{RECON.as_posix()}','R100E40');"
    )
    subprocess.run([str(MATLAB), "-batch", expression], cwd=ROOT, check=True)
    primary = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    sensitivity = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    if len(primary) != 864 or set(primary["method"]) != {"Raw", "R100E40"} or primary.isna().any().any():
        raise RuntimeError("Primary R100 ACM table is incomplete")
    if len(sensitivity) != 648 or set(sensitivity["method"]) != {"Raw", "R100E40"} or sensitivity.isna().any().any():
        raise RuntimeError("Sensitivity R100 ACM table is incomplete")


def assert_same_raw(prior: pd.DataFrame, current: pd.DataFrame) -> None:
    key = ["exposure", "pillar_id"]
    columns = list(METRICS) + ["centroid_alignment_shift_px"]
    left = prior.loc[prior["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    right = current.loc[current["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    if len(left) != len(right) or not np.allclose(left[columns], right[columns], rtol=0, atol=1e-12):
        raise RuntimeError("Raw ACM extraction did not reproduce the established experiment")


def analyze(protocol: dict, manifest: dict) -> dict:
    arm = protocol["sem_contour_arm"]
    prior_tables = Path(arm["prior_six_method_tables"])
    prior = pd.read_csv(prior_tables / "six_method_primary_contour_metrics.csv")
    current = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    assert_same_raw(prior, current)
    combined = pd.concat([prior, current.loc[current["method"] == "R100E40"]], ignore_index=True)
    if len(combined) != 12 * 36 * len(METHODS) or set(combined["method"]) != set(METHODS) or combined.isna().any().any():
        raise RuntimeError("Seven-method ACM table is incomplete")
    combined.to_csv(TABLES / "seven_method_primary_contour_metrics.csv", index=False)

    per_pillar = combined.groupby(["pillar_id", "method"], sort=False)[list(METRICS)].mean().reset_index()
    per_pillar.to_csv(TABLES / "seven_method_per_pillar_summary.csv", index=False)
    summary_rows: list[dict[str, object]] = []
    for method in METHODS:
        rows = per_pillar.loc[per_pillar["method"] == method]
        for metric in METRICS:
            values = rows[metric].to_numpy(float)
            low, high = bootstrap_median_ci(values, 100000 + METHODS.index(method) * 100 + list(METRICS).index(metric))
            summary_rows.append({"method": method, "metric": metric, "median": float(np.median(values)), "ci95_low": low, "ci95_high": high, "physical_pillars": len(values)})
    summary_table = pd.DataFrame(summary_rows)
    summary_table.to_csv(TABLES / "seven_method_metric_summary.csv", index=False)

    paired_rows: list[dict[str, object]] = []
    target = per_pillar.loc[per_pillar["method"] == "R100E40"].sort_values("pillar_id")
    for source_name in METHODS[:-1]:
        source = per_pillar.loc[per_pillar["method"] == source_name].sort_values("pillar_id")
        for metric, direction in METRICS.items():
            source_values = source[metric].to_numpy(float)
            target_values = target[metric].to_numpy(float)
            delta = target_values - source_values
            low, high = bootstrap_median_ci(delta, 200000 + METHODS.index(source_name) * 100 + list(METRICS).index(metric))
            try:
                statistic, p_value = wilcoxon(target_values, source_values, zero_method="wilcox", alternative="two-sided")
            except ValueError:
                statistic, p_value = 0.0, 1.0
            beneficial = target_values > source_values if direction == "higher" else target_values < source_values
            paired_rows.append({
                "source": source_name, "target": "R100E40", "metric": metric,
                "median_source": float(np.median(source_values)), "median_target": float(np.median(target_values)),
                "median_delta_target_minus_source": float(np.median(delta)), "delta_ci95_low": low, "delta_ci95_high": high,
                "beneficial_pillar_fraction": float(np.mean(beneficial)), "wilcoxon_statistic": float(statistic),
                "wilcoxon_p_two_sided": float(p_value), "independent_units": len(delta),
            })
    paired = pd.DataFrame(paired_rows)
    paired.to_csv(TABLES / "r100_paired_comparisons.csv", index=False)

    prior_sensitivity = pd.read_csv(prior_tables / "acm_sensitivity_metrics.csv")
    current_sensitivity = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    sensitivity = pd.concat([
        prior_sensitivity.loc[prior_sensitivity["method"].isin(["Raw", "R97E48"])],
        current_sensitivity.loc[current_sensitivity["method"] == "R100E40"],
    ], ignore_index=True)
    sensitivity_summary = sensitivity.groupby(["preset", "method"], sort=False)[["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]].median().reset_index()
    sensitivity_summary.to_csv(TABLES / "r100_sensitivity_summary.csv", index=False)

    masks = loadmat(OUTPUT / "results" / "masks" / "acm_primary_masks.mat", squeeze_me=True)
    prior_masks = loadmat(Path(arm["prior_masks"]), squeeze_me=True)
    truth_masks = masks["truth_masks"].astype(bool)
    raw_cells = masks["raw_cells"]
    raw_masks = masks["raw_masks"].astype(bool)
    r100_masks = masks["recon_masks"].astype(bool)
    r97_masks = prior_masks["recon_masks"].astype(bool)
    exposure_index = list(arm["exposures"]).index(18)
    pillars = [0, 8, 20, 35]
    figure, axes = plt.subplots(1, len(pillars), figsize=(13, 3.4))
    for axis, pillar in zip(axes, pillars):
        truth = truth_masks[:, :, pillar]
        axis.imshow(raw_cells[:, :, pillar, exposure_index], cmap="gray", vmin=0, vmax=255)
        for mask, color, label, style in (
            (truth, "white", "SEM truth", "-"),
            (align_to_truth(raw_masks[:, :, pillar, exposure_index], truth), "#22D3EE", "Raw", "--"),
            (align_to_truth(r97_masks[:, :, pillar, exposure_index], truth), "#F59E0B", "R97", ":"),
            (align_to_truth(r100_masks[:, :, pillar, exposure_index], truth), "#EF4444", "R100", "-"),
        ):
            for contour in find_contours(mask.astype(float), 0.5):
                axis.plot(contour[:, 1], contour[:, 0], color=color, linewidth=1.2, linestyle=style, label=label)
                label = "_nolegend_"
        axis.set_title(f"Pillar {pillar + 1}, exposure 18")
        axis.axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=4)
    figure.tight_layout(rect=(0, 0.10, 1, 1))
    FIGURES.mkdir(parents=True, exist_ok=True)
    figure.savefig(FIGURES / "r100_sem_contour_overlay.png", dpi=180)
    plt.close(figure)

    medians = {(row.method, row.metric): row.median for row in summary_table.itertuples()}
    result = {
        "status": "complete", "checkpoint_epoch": manifest["checkpoint_epoch"],
        "physical_pillars": 36, "exposures": 12, "primary_rows": len(combined),
        "raw_reproduced_exactly": True,
        "method_medians": {method: {metric: float(medians[(method, metric)]) for metric in METRICS} for method in METHODS},
        "r100_vs_raw": {row.metric: row._asdict() for row in paired.itertuples() if row.source == "Raw"},
        "r100_vs_r61": {row.metric: row._asdict() for row in paired.itertuples() if row.source == "R61v16"},
        "r100_vs_r97": {row.metric: row._asdict() for row in paired.itertuples() if row.source == "R97E48"},
        "sensitivity": sensitivity_summary.to_dict(orient="records"),
        "notes": [
            "The independent unit is the physical pillar; twelve exposures are repeated observations.",
            "Alignment is translation only. No scale or rotation fitting is used.",
            "Raw was re-extracted and reproduced the established ACM experiment exactly.",
        ],
    }
    write_json(OUTPUT / "summary.json", result)
    return result


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite SEM validation: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    protocol = read_json(PROTOCOL_PATH)
    if not protocol.get("locked_before_new_posttraining_outputs") or int(protocol["primary_checkpoint_epoch"]) != 40:
        raise RuntimeError("Fixed R100 endpoint is not locked")
    started = time.perf_counter()
    manifest = reconstruct(protocol)
    write_json(OUTPUT / "input_manifest.json", manifest)
    run_acm(protocol)
    result = analyze(protocol, manifest)
    result["elapsed_seconds"] = time.perf_counter() - started
    write_json(OUTPUT / "summary.json", result)
    print(json.dumps({"status": result["status"], "physical_pillars": result["physical_pillars"], "exposures": result["exposures"], "elapsed_seconds": result["elapsed_seconds"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
