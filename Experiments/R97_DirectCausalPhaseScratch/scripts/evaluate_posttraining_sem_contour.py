"""Run the locked central-36 SEM contour validation for the fixed R97 E48 endpoint."""
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
MODEL_PATH = ROOT / "model" / "r97_model.py"
INFERENCE_PATH = ROOT / "inference" / "reconstruct.py"
OUTPUT = ROOT / "results" / "posttraining_validation" / "sem_contour"
RECON = OUTPUT / "reconstructions"
TABLES = OUTPUT / "results" / "tables"
FIGURES = OUTPUT / "figures"
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
SHARED_ACM = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\scripts\run_acm_extraction.m")
PRIOR_TABLES = {
    "R61v16": Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\results\tables"),
    "V42E120": Path(r"D:\GMM_2_Final\Experiments\R70_V42ACMContourSEMValidation\results\tables"),
    "R75v2E100": Path(r"D:\GMM_2_Final\Experiments\R77_R75v2ACMContourSEMValidation\results\epoch100_audit\results\tables"),
    "R96E44": Path(r"D:\GMM_2_Final\Experiments\R96_LocalizedEvidenceProtectedScratch\results\final_validation\sem_contour\results\tables"),
}
METHODS = ["Raw", "R61v16", "V42E120", "R75v2E100", "R96E44", "R97E48"]
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


MODEL = load_module("r97_post_sem_model", MODEL_PATH)
INFERENCE = load_module("r97_post_sem_inference", INFERENCE_PATH)


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


def assert_same_raw(reference: pd.DataFrame, candidate: pd.DataFrame, sensitivity: bool = False) -> None:
    key = ["preset", "exposure", "pillar_id"] if sensitivity else ["exposure", "pillar_id"]
    columns = (
        ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
        if sensitivity else list(METRICS) + ["centroid_alignment_shift_px"]
    )
    a = reference.loc[reference["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    b = candidate.loc[candidate["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    if len(a) != len(b) or not np.allclose(a[columns], b[columns], rtol=0, atol=1e-12):
        raise RuntimeError("Raw ACM extraction does not reproduce the established experiment")


def bootstrap_median_ci(values: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    sampled = values[rng.integers(0, len(values), size=(20000, len(values)))]
    return tuple(float(v) for v in np.quantile(np.median(sampled, axis=1), [0.025, 0.975]))


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


def draw_contour(ax, mask: np.ndarray, color: str, label: str, linestyle: str = "-") -> None:
    for index, contour in enumerate(find_contours(mask.astype(float), 0.5)):
        ax.plot(contour[:, 1], contour[:, 0], color=color, linewidth=1.25, linestyle=linestyle,
                label=label if index == 0 else None)


def reconstruct(protocol: dict) -> dict:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite SEM validation: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sem = protocol["sem_contour_arm"]
    checkpoint_path = Path(protocol["checkpoint"])
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if int(checkpoint["epoch"]) != int(protocol["primary_checkpoint_epoch"]):
        raise RuntimeError("SEM checkpoint epoch mismatch")
    design = read_json(DESIGN_PATH)
    model = MODEL.build_model(base=int(design["architecture"]["model_width"]))
    model.load_state_dict(checkpoint[protocol["checkpoint_state"]], strict=True)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model.eval().to(device)
    raw_dir = Path(sem["raw_input_dir"])
    records: list[dict[str, object]] = []
    for exposure in sem["exposures"]:
        source = raw_dir / f"{exposure}.bmp"
        raw = read_gray(source)
        tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
        started = time.perf_counter()
        with torch.inference_mode():
            prediction = INFERENCE.reconstruct_tensor(model, tensor, core_size=512, halo=192, tile_batch=1)[0, 0]
        destination = RECON / source.name
        write_gray(destination, np.rint(prediction.clamp(0, 1).cpu().numpy() * 255).astype(np.uint8))
        records.append({
            "exposure": exposure,
            "source": str(source),
            "source_sha256": sha256_file(source),
            "output": str(destination),
            "output_sha256": sha256_file(destination),
            "seconds": time.perf_counter() - started,
        })
        print(f"[sem-reconstruct] exposure {exposure}", flush=True)
    pd.DataFrame(records).to_csv(OUTPUT / "reconstruction_manifest.csv", index=False)
    return {
        "checkpoint": str(checkpoint_path),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "state": protocol["checkpoint_state"],
        "run_id": checkpoint["metadata"]["run_id"],
        "images": records,
    }


def run_acm(protocol: dict) -> None:
    raw_dir = Path(protocol["sem_contour_arm"]["raw_input_dir"])
    expression = (
        f"addpath('{SHARED_ACM.parent.as_posix()}'); "
        f"run_acm_extraction('{OUTPUT.as_posix()}','{raw_dir.as_posix()}',"
        f"'{RECON.as_posix()}','R97E48');"
    )
    subprocess.run([str(MATLAB), "-batch", expression], cwd=ROOT, check=True)
    primary = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    sensitivity = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    if len(primary) != 864 or set(primary["method"]) != {"Raw", "R97E48"} or primary.isna().any().any():
        raise RuntimeError("Primary R97 ACM table is incomplete")
    if len(sensitivity) != 648 or set(sensitivity["method"]) != {"Raw", "R97E48"} or sensitivity.isna().any().any():
        raise RuntimeError("Sensitivity R97 ACM table is incomplete")


def analyze(protocol: dict, manifest: dict) -> dict:
    current = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    current_s = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    priors = {name: pd.read_csv(path / "primary_contour_metrics.csv") for name, path in PRIOR_TABLES.items()}
    for candidate in priors.values():
        assert_same_raw(current, candidate)
    r61_s = pd.read_csv(PRIOR_TABLES["R61v16"] / "acm_sensitivity_metrics.csv")
    assert_same_raw(current_s, r61_s, sensitivity=True)
    combined_parts = [current.loc[current["method"].isin(["Raw", "R97E48"])]]
    combined_parts.extend(priors[name].loc[priors[name]["method"] == name] for name in METHODS[1:-1])
    combined = pd.concat(combined_parts, ignore_index=True)
    if len(combined) != 12 * 36 * len(METHODS) or combined.isna().any().any():
        raise RuntimeError("Combined SEM table is incomplete")
    combined.to_csv(TABLES / "six_method_primary_contour_metrics.csv", index=False)
    per_pillar = combined.groupby(["pillar_id", "method"], sort=False)[list(METRICS)].median().unstack("method")
    summaries: list[dict[str, object]] = []
    comparisons: list[dict[str, object]] = []
    for method in METHODS:
        row: dict[str, object] = {"method": method}
        for metric in METRICS:
            row[f"median_{metric}"] = float(np.median(per_pillar[(metric, method)].to_numpy(float)))
        summaries.append(row)
    for source in METHODS[:-1]:
        for metric, direction in METRICS.items():
            source_values = per_pillar[(metric, source)].to_numpy(float)
            target_values = per_pillar[(metric, "R97E48")].to_numpy(float)
            improvement = target_values - source_values if direction == "higher" else source_values - target_values
            low, high = bootstrap_median_ci(improvement, 20260813 + len(comparisons))
            try:
                _, p = wilcoxon(target_values, source_values, alternative="two-sided", zero_method="wilcox")
            except ValueError:
                p = 1.0
            comparisons.append({
                "source": source,
                "target": "R97E48",
                "metric": metric,
                "direction": direction,
                "source_median": float(np.median(source_values)),
                "target_median": float(np.median(target_values)),
                "median_improvement": float(np.median(improvement)),
                "improved_pillars": int(np.sum(improvement > 0)),
                "tied_pillars": int(np.sum(improvement == 0)),
                "improved_fraction": float(np.mean(improvement > 0)),
                "bootstrap_ci95_low": low,
                "bootstrap_ci95_high": high,
                "wilcoxon_p": float(p),
            })
    summary_table = pd.DataFrame(summaries)
    comparison_table = pd.DataFrame(comparisons)
    summary_table.to_csv(TABLES / "six_method_per_pillar_summary.csv", index=False)
    comparison_table.to_csv(TABLES / "r97_paired_comparisons.csv", index=False)
    combined.groupby(["exposure", "method"], sort=False)[list(METRICS)].median().reset_index().to_csv(
        TABLES / "six_method_per_exposure_summary.csv", index=False
    )
    current_s.groupby(["preset", "method"], sort=False)[
        ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
    ].median().reset_index().to_csv(TABLES / "r97_sensitivity_summary.csv", index=False)

    metrics_to_plot = ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "perimeter_error_pct"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    for ax, metric in zip(axes.ravel(), metrics_to_plot):
        arrays = [per_pillar[(metric, method)].to_numpy(float) for method in METHODS]
        for values in zip(*arrays):
            ax.plot(range(len(METHODS)), values, color="#CBD5E1", linewidth=.55)
        ax.plot(range(len(METHODS)), [np.median(v) for v in arrays], color="#111827", marker="o", linewidth=2)
        ax.set_xticks(range(len(METHODS)), ["Raw", "R61", "V42", "R75v2", "R96", "R97"], rotation=15)
        ax.set_title(metric.replace("_", " "))
        ax.grid(alpha=.2)
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGURES / "six_method_paired_comparison.png", dpi=180)
    plt.close(fig)

    masks = loadmat(OUTPUT / "results" / "masks" / "acm_primary_masks.mat", squeeze_me=True)
    truth, raw_masks, r97_masks = masks["truth_masks"], masks["raw_masks"], masks["recon_masks"]
    exposure_index = list(protocol["sem_contour_arm"]["exposures"]).index(18)
    fig, axes = plt.subplots(6, 6, figsize=(12, 12))
    for pillar in range(36):
        ax = axes.ravel()[pillar]
        ax.imshow(masks["truth_cells"][:, :, pillar], cmap="gray")
        draw_contour(ax, truth[:, :, pillar], "#22C55E", "SEM")
        draw_contour(ax, align_to_truth(raw_masks[:, :, pillar, exposure_index], truth[:, :, pillar]), "#F59E0B", "Raw", "--")
        draw_contour(ax, align_to_truth(r97_masks[:, :, pillar, exposure_index], truth[:, :, pillar]), "#DC2626", "R97")
        ax.set_title(str(pillar + 1), fontsize=8)
        ax.axis("off")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3)
    fig.tight_layout(rect=[0, .03, 1, 1])
    fig.savefig(FIGURES / "center36_contour_overlay_exposure18.png", dpi=180)
    plt.close(fig)

    by_metric = {(row["source"], row["metric"]): row for row in comparisons}
    result = {
        "status": "complete",
        "checkpoint": manifest,
        "physical_pillars": 36,
        "exposures": 12,
        "primary_rows": len(current),
        "raw_reproduced_exactly": True,
        "method_summary": summaries,
        "r97_vs_raw": {metric: by_metric[("Raw", metric)] for metric in METRICS},
        "r97_vs_r61": {metric: by_metric[("R61v16", metric)] for metric in METRICS},
        "r97_vs_v42": {metric: by_metric[("V42E120", metric)] for metric in METRICS},
        "r97_vs_r75v2": {metric: by_metric[("R75v2E100", metric)] for metric in METRICS},
        "r97_vs_r96": {metric: by_metric[("R96E44", metric)] for metric in METRICS},
        "claim_boundary": protocol["claim_boundary"],
    }
    write_json(OUTPUT / "summary.json", result)
    return result


def main() -> None:
    protocol = read_json(PROTOCOL_PATH)
    if not protocol.get("locked_before_new_posttraining_outputs") or int(protocol["primary_checkpoint_epoch"]) != 48:
        raise RuntimeError("Fixed R97 endpoint is not locked")
    manifest = reconstruct(protocol)
    write_json(OUTPUT / "input_manifest.json", manifest)
    run_acm(protocol)
    result = analyze(protocol, manifest)
    print(json.dumps({"status": result["status"], "physical_pillars": 36, "exposures": 12}, indent=2), flush=True)


if __name__ == "__main__":
    main()
