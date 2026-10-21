"""Reconstruct the locked optical stack, run ACM, and compare R96 E44 with prior models."""
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
PROTOCOL_PATH = ROOT / "config" / "final_validation_protocol.json"
DESIGN_PATH = ROOT / "config" / "experiment_design.json"
MODEL_PATH = ROOT / "model" / "r96_model.py"
INFERENCE_PATH = ROOT / "inference" / "reconstruct.py"
OUTPUT = ROOT / "results" / "final_validation" / "sem_contour"
RECON = OUTPUT / "reconstructions"
TABLES = OUTPUT / "results" / "tables"
FIGURES = OUTPUT / "figures"
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
SHARED_ACM = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\scripts\run_acm_extraction.m")
R69_TABLES = Path(r"D:\GMM_2_Final\Experiments\R69_ACMContourSEMValidation\results\tables")
R70_TABLES = Path(r"D:\GMM_2_Final\Experiments\R70_V42ACMContourSEMValidation\results\tables")
R77_E100_TABLES = Path(r"D:\GMM_2_Final\Experiments\R77_R75v2ACMContourSEMValidation\results\epoch100_audit\results\tables")
METHODS = ["Raw", "R61v16", "V42E120", "R75v2E100", "R96E44"]
METRICS = {
    "iou": "higher", "dice": "higher", "mean_boundary_distance_pitch_pct": "lower",
    "hd95_pitch_pct": "lower", "area_error_pct": "lower", "perimeter_error_pct": "lower",
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


MODEL = load_module("r96_sem_model", MODEL_PATH)
INFERENCE = load_module("r96_sem_inference", INFERENCE_PATH)


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
    columns = (["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
               if sensitivity else list(METRICS) + ["centroid_alignment_shift_px"])
    a = reference.loc[reference["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    b = candidate.loc[candidate["method"] == "Raw"].sort_values(key).reset_index(drop=True)
    if len(a) != len(b) or not np.allclose(a[columns], b[columns], rtol=0, atol=1e-12):
        raise RuntimeError("Raw ACM extraction is not identical to the established experiments")


def bootstrap_median_ci(values: np.ndarray, seed: int = 20260813) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    sampled = values[rng.integers(0, len(values), size=(20000, len(values)))]
    return tuple(float(v) for v in np.quantile(np.median(sampled, axis=1), [0.025, 0.975]))


def matlab_round(values: np.ndarray) -> np.ndarray:
    return np.sign(values) * np.floor(np.abs(values) + 0.5)


def align_to_truth(predicted: np.ndarray, truth: np.ndarray) -> np.ndarray:
    dy, dx = matlab_round(np.asarray(center_of_mass(truth)) - np.asarray(center_of_mass(predicted))).astype(int)
    aligned = np.zeros_like(predicted, dtype=bool)
    source_y = slice(max(0, -dy), min(predicted.shape[0], predicted.shape[0] - dy))
    source_x = slice(max(0, -dx), min(predicted.shape[1], predicted.shape[1] - dx))
    target_y = slice(max(0, dy), min(predicted.shape[0], predicted.shape[0] + dy))
    target_x = slice(max(0, dx), min(predicted.shape[1], predicted.shape[1] + dx))
    aligned[target_y, target_x] = predicted[source_y, source_x]
    return aligned


def draw_contour(ax, mask: np.ndarray, color: str, label: str, linestyle: str = "-") -> None:
    contours = find_contours(mask.astype(float), 0.5)
    for index, contour in enumerate(contours):
        ax.plot(contour[:, 1], contour[:, 0], color=color, linewidth=1.25, linestyle=linestyle,
                label=label if index == 0 else None)


def reconstruct(protocol: dict) -> dict:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite final SEM validation: {OUTPUT}")
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
        records.append({"exposure": exposure, "source": str(source), "source_sha256": sha256_file(source),
                        "output": str(destination), "output_sha256": sha256_file(destination),
                        "seconds": time.perf_counter() - started})
    pd.DataFrame(records).to_csv(OUTPUT / "reconstruction_manifest.csv", index=False)
    return {"checkpoint": str(checkpoint_path), "checkpoint_epoch": int(checkpoint["epoch"]),
            "checkpoint_sha256": sha256_file(checkpoint_path), "state": protocol["checkpoint_state"],
            "run_id": checkpoint["metadata"]["run_id"], "images": records}


def run_acm(protocol: dict) -> None:
    raw_dir = Path(protocol["sem_contour_arm"]["raw_input_dir"])
    expression = (f"addpath('{SHARED_ACM.parent.as_posix()}'); "
                  f"run_acm_extraction('{OUTPUT.as_posix()}','{raw_dir.as_posix()}',"
                  f"'{RECON.as_posix()}','R96E44');")
    subprocess.run([str(MATLAB), "-batch", expression], cwd=ROOT, check=True)
    primary = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    sensitivity = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    if len(primary) != 864 or set(primary["method"]) != {"Raw", "R96E44"} or primary.isna().any().any():
        raise RuntimeError("Primary R96 ACM table is incomplete")
    if len(sensitivity) != 648 or set(sensitivity["method"]) != {"Raw", "R96E44"} or sensitivity.isna().any().any():
        raise RuntimeError("Sensitivity R96 ACM table is incomplete")


def analyze(protocol: dict, manifest: dict) -> dict:
    r96 = pd.read_csv(TABLES / "primary_contour_metrics.csv")
    r96_s = pd.read_csv(TABLES / "acm_sensitivity_metrics.csv")
    r61 = pd.read_csv(R69_TABLES / "primary_contour_metrics.csv")
    v42 = pd.read_csv(R70_TABLES / "primary_contour_metrics.csv")
    r75 = pd.read_csv(R77_E100_TABLES / "primary_contour_metrics.csv")
    r61_s = pd.read_csv(R69_TABLES / "acm_sensitivity_metrics.csv")
    for candidate in (r61, v42, r75):
        assert_same_raw(r96, candidate)
    assert_same_raw(r96_s, r61_s, sensitivity=True)
    combined = pd.concat([
        r96.loc[r96["method"].isin(["Raw", "R96E44"])],
        r61.loc[r61["method"] == "R61v16"], v42.loc[v42["method"] == "V42E120"],
        r75.loc[r75["method"] == "R75v2E100"],
    ], ignore_index=True)
    if len(combined) != 12 * 36 * len(METHODS) or combined.isna().any().any():
        raise RuntimeError("Combined SEM table is incomplete")
    combined.to_csv(TABLES / "five_method_primary_contour_metrics.csv", index=False)
    per_pillar = combined.groupby(["pillar_id", "method"], sort=False)[list(METRICS)].median().unstack("method")
    summaries: list[dict[str, object]] = []
    comparisons: list[dict[str, object]] = []
    for method in METHODS:
        row: dict[str, object] = {"method": method}
        for metric in METRICS:
            values = per_pillar[(metric, method)].to_numpy(float)
            row[f"median_{metric}"] = float(np.median(values))
        summaries.append(row)
    for source in METHODS[:-1]:
        for metric, direction in METRICS.items():
            source_values = per_pillar[(metric, source)].to_numpy(float)
            target_values = per_pillar[(metric, "R96E44")].to_numpy(float)
            improvement = target_values - source_values if direction == "higher" else source_values - target_values
            low, high = bootstrap_median_ci(improvement, 20260813 + len(comparisons))
            try:
                _, p = wilcoxon(target_values, source_values, alternative="two-sided", zero_method="wilcox")
            except ValueError:
                p = 1.0
            comparisons.append({
                "source": source, "target": "R96E44", "metric": metric, "direction": direction,
                "source_median": float(np.median(source_values)), "target_median": float(np.median(target_values)),
                "median_improvement": float(np.median(improvement)), "improved_pillars": int(np.sum(improvement > 0)),
                "tied_pillars": int(np.sum(improvement == 0)), "improved_fraction": float(np.mean(improvement > 0)),
                "bootstrap_ci95_low": low, "bootstrap_ci95_high": high, "wilcoxon_p": float(p),
            })
    summary_table = pd.DataFrame(summaries)
    comparison_table = pd.DataFrame(comparisons)
    summary_table.to_csv(TABLES / "five_method_per_pillar_summary.csv", index=False)
    comparison_table.to_csv(TABLES / "r96_paired_comparisons.csv", index=False)
    exposure = combined.groupby(["exposure", "method"], sort=False)[list(METRICS)].median().reset_index()
    exposure.to_csv(TABLES / "five_method_per_exposure_summary.csv", index=False)
    sensitivity = r96_s.groupby(["preset", "method"], sort=False)[
        ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "area_error_pct", "circularity_abs_error"]
    ].median().reset_index()
    sensitivity.to_csv(TABLES / "r96_sensitivity_summary.csv", index=False)

    metrics_to_plot = ["iou", "mean_boundary_distance_pitch_pct", "hd95_pitch_pct", "perimeter_error_pct"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    for ax, metric in zip(axes.ravel(), metrics_to_plot):
        arrays = [per_pillar[(metric, method)].to_numpy(float) for method in METHODS]
        for values in zip(*arrays):
            ax.plot(range(len(METHODS)), values, color="#CBD5E1", linewidth=.55)
        ax.plot(range(len(METHODS)), [np.median(v) for v in arrays], color="#111827", marker="o", linewidth=2)
        ax.set_xticks(range(len(METHODS)), ["Raw", "R61", "V42", "R75v2", "R96"], rotation=15)
        ax.set_title(metric.replace("_", " "))
        ax.grid(alpha=.2)
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / "five_method_paired_comparison.png", dpi=180)
    plt.close(fig)

    masks = loadmat(OUTPUT / "results" / "masks" / "acm_primary_masks.mat", squeeze_me=True)
    truth, raw_masks, r96_masks = masks["truth_masks"], masks["raw_masks"], masks["recon_masks"]
    exposure_index = list(protocol["sem_contour_arm"]["exposures"]).index(18)
    fig, axes = plt.subplots(6, 6, figsize=(12, 12))
    for pillar in range(36):
        ax = axes.ravel()[pillar]
        ax.imshow(masks["truth_cells"][:, :, pillar], cmap="gray")
        draw_contour(ax, truth[:, :, pillar], "#22C55E", "SEM")
        draw_contour(ax, align_to_truth(raw_masks[:, :, pillar, exposure_index], truth[:, :, pillar]), "#F59E0B", "Raw", "--")
        draw_contour(ax, align_to_truth(r96_masks[:, :, pillar, exposure_index], truth[:, :, pillar]), "#DC2626", "R96")
        ax.set_title(str(pillar + 1), fontsize=8); ax.axis("off")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3)
    fig.tight_layout(rect=[0, .03, 1, 1])
    fig.savefig(FIGURES / "center36_contour_overlay_exposure18.png", dpi=180)
    plt.close(fig)

    by_metric = {(r["source"], r["metric"]): r for r in comparisons}
    result = {
        "status": "complete", "checkpoint": manifest,
        "physical_pillars": 36, "exposures": 12, "primary_rows": len(r96),
        "raw_reproduced_exactly": True, "method_summary": summaries,
        "r96_vs_raw": {metric: by_metric[("Raw", metric)] for metric in METRICS},
        "r96_vs_r61": {metric: by_metric[("R61v16", metric)] for metric in METRICS},
        "r96_vs_v42": {metric: by_metric[("V42E120", metric)] for metric in METRICS},
        "r96_vs_r75v2": {metric: by_metric[("R75v2E100", metric)] for metric in METRICS},
        "claim_boundary": protocol["claim_boundary"],
    }
    write_json(OUTPUT / "summary.json", result)
    return result


def main() -> None:
    protocol = read_json(PROTOCOL_PATH)
    if not protocol.get("locked_before_epoch44_outputs") or int(protocol["primary_checkpoint_epoch"]) != 44:
        raise RuntimeError("Final endpoint was not locked")
    manifest = reconstruct(protocol)
    write_json(OUTPUT / "input_manifest.json", manifest)
    run_acm(protocol)
    result = analyze(protocol, manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
