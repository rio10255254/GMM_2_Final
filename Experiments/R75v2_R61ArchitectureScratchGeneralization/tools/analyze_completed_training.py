"""Reproducible post-training analysis for the completed R75-v2 formal run."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from PIL import Image, ImageDraw, ImageFont
from skimage.metrics import structural_similarity


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "r75v2_formal_diverse_primitives"
RUN = ROOT / "runs" / (
    "training_progress_LAB_GESR_v1_v5_R75v2_scratch_formal_seed752031_"
    "diverse_data_e100_20260731_163219"
)
WEIGHTS = ROOT / "weights" / "formal" / "seed_752031" / RUN.name
BEST_CHECKPOINT = WEIGHTS / "best_tradeoff.pth.tar"
FINAL_CHECKPOINT = RUN / "epoch_100.pth.tar"
VAL_LOG = RUN / "LAB_GESR_v1_v5_R75v2_scratch_formal_seed752031_diverse_data_e100_val_log_v5.csv"
BATCH_LOG = RUN / "LAB_GESR_v1_v5_R75v2_scratch_formal_seed752031_diverse_data_e100_batch_log_v5.csv"
STDOUT_LOG = ROOT / "runs" / "launcher_logs" / "r75v2_formal_e100_20260731_163211.out.log"
OUTPUT = ROOT / "results" / "final_analysis"

sys.path.insert(0, str(ROOT / "inference"))
from infer_r75v2 import build_model  # noqa: E402


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def to_boundary(mask: np.ndarray) -> np.ndarray:
    kernel = np.ones((3, 3), np.uint8)
    eroded = cv2.erode(mask.astype(np.uint8), kernel, iterations=1).astype(bool)
    return mask.astype(bool) & ~eroded


def symmetric_boundary_distance(predicted: np.ndarray, truth: np.ndarray) -> float:
    pred_boundary = to_boundary(predicted)
    truth_boundary = to_boundary(truth)
    if not pred_boundary.any() or not truth_boundary.any():
        return float("nan")
    pred_distance = cv2.distanceTransform((~pred_boundary).astype(np.uint8), cv2.DIST_L2, 5)
    truth_distance = cv2.distanceTransform((~truth_boundary).astype(np.uint8), cv2.DIST_L2, 5)
    return float((truth_distance[pred_boundary].mean() + pred_distance[truth_boundary].mean()) / 2.0)


def segment(image: np.ndarray, polarity: str) -> np.ndarray:
    _, thresholded = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = thresholded > 0
    return mask if polarity == "bright" else ~mask


def mask_metrics(image: np.ndarray, truth_mask: np.ndarray, polarity: str) -> dict[str, float]:
    predicted = segment(image, polarity)
    intersection = np.logical_and(predicted, truth_mask).sum()
    union = np.logical_or(predicted, truth_mask).sum()
    truth_area = max(1, int(truth_mask.sum()))
    return {
        "contour_iou": float(intersection / max(1, union)),
        "boundary_distance_px": symmetric_boundary_distance(predicted, truth_mask),
        "area_error_fraction": float(abs(int(predicted.sum()) - truth_area) / truth_area),
    }


def image_metrics(
    source: np.ndarray,
    target: np.ndarray,
    prediction: np.ndarray,
    truth_mask: np.ndarray,
    polarity: str,
) -> dict[str, float]:
    target_float = target.astype(np.float32) / 255.0
    prediction_float = prediction.astype(np.float32) / 255.0
    source_float = source.astype(np.float32) / 255.0
    mse = float(np.mean((prediction_float - target_float) ** 2))
    kernel = np.ones((3, 3), np.uint8)
    band = cv2.dilate(truth_mask.astype(np.uint8), kernel, iterations=5).astype(bool)
    band &= ~cv2.erode(truth_mask.astype(np.uint8), kernel, iterations=5).astype(bool)
    outside = ~cv2.dilate(truth_mask.astype(np.uint8), kernel, iterations=6).astype(bool)
    result = {
        "mae": float(np.mean(np.abs(prediction_float - target_float))),
        "psnr_db": float(99.0 if mse <= 1e-12 else 10.0 * math.log10(1.0 / mse)),
        "ssim": float(structural_similarity(target, prediction, data_range=255)),
        "edge_band_mae": float(np.mean(np.abs(prediction_float[band] - target_float[band]))) if band.any() else 0.0,
        "background_mae": float(np.mean(np.abs(prediction_float[outside] - target_float[outside]))) if outside.any() else 0.0,
        "source_drift_mae": float(np.mean(np.abs(prediction_float - source_float))),
    }
    result.update(mask_metrics(prediction, truth_mask, polarity))
    return result


def infer_batch(model: torch.nn.Module, sources: list[np.ndarray], device: str) -> list[np.ndarray]:
    tensor = torch.from_numpy(np.stack(sources).astype(np.float32) / 255.0)[:, None].to(device)
    use_amp = str(device).lower().startswith("cuda")
    with torch.no_grad(), torch.cuda.amp.autocast(enabled=use_amp):
        output = model(tensor).float().clamp(0.0, 1.0)[:, 0]
    return [np.clip(np.rint(item * 255.0), 0, 255).astype(np.uint8) for item in output.cpu().numpy()]


def evaluate_internal_test(device: str, batch_size: int) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    records = [row for row in manifest["pairs"] if row["split"] == "internal_test"]
    if len(records) != 512:
        raise RuntimeError(f"Expected 512 internal-test images, found {len(records)}")

    checkpoints = {
        "Raw": None,
        "BestE84": BEST_CHECKPOINT,
        "FinalE100": FINAL_CHECKPOINT,
    }
    rows: list[dict[str, object]] = []
    sample_predictions: dict[str, list[np.ndarray]] = {key: [] for key in checkpoints}
    sample_indices: list[int] = []
    seen_roles: set[str] = set()
    for index, record in enumerate(records):
        role = str(record["training_role"])
        if role not in seen_roles:
            sample_indices.append(index)
            seen_roles.add(role)
    sample_records = [records[index] for index in sample_indices]

    source_cache = [read_gray(DATASET / row["package_src"]) for row in records]
    target_cache = [read_gray(DATASET / row["package_lbl"]) for row in records]
    mask_cache = [read_gray(DATASET / row["geometry_mask"]) > 127 for row in records]

    for method, checkpoint in checkpoints.items():
        model = None
        if checkpoint is not None:
            model, _ = build_model(checkpoint, device, use_ema=True)
        for start in range(0, len(records), batch_size):
            batch_records = records[start : start + batch_size]
            batch_sources = source_cache[start : start + batch_size]
            if model is None:
                predictions = batch_sources
            else:
                predictions = infer_batch(model, batch_sources, device)
            for offset, (record, source, prediction) in enumerate(zip(batch_records, batch_sources, predictions)):
                index = start + offset
                metrics = image_metrics(
                    source,
                    target_cache[index],
                    prediction,
                    mask_cache[index],
                    str(record["polarity"]),
                )
                rows.append(
                    {
                        "method": method,
                        "pair_id": record["pair_id"],
                        "geometry_id": record["geometry_id"],
                        "training_role": record["training_role"],
                        "shape_family": record["shape_family"],
                        "exposure_level": record["exposure_level"],
                        "contrast_class": record["contrast_class"],
                        "degradation_family": record["degradation_family"],
                        "identity_mode": record["identity_mode"],
                        "polarity": record["polarity"],
                        **metrics,
                    }
                )
                if index in sample_indices:
                    sample_predictions[method].append(prediction)
        if model is not None:
            del model
            if str(device).lower().startswith("cuda"):
                torch.cuda.empty_cache()

    frame = pd.DataFrame(rows)
    metric_columns = [
        "mae",
        "psnr_db",
        "ssim",
        "contour_iou",
        "boundary_distance_px",
        "area_error_fraction",
        "edge_band_mae",
        "background_mae",
        "source_drift_mae",
    ]
    summary_rows: list[dict[str, object]] = []
    for method, group in frame.groupby("method", sort=False):
        summary_rows.append({"scope": "overall", "group": "all", "method": method, "count": len(group), **{f"median_{col}": float(group[col].median()) for col in metric_columns}})
        for role, role_group in group.groupby("training_role"):
            summary_rows.append({"scope": "training_role", "group": role, "method": method, "count": len(role_group), **{f"median_{col}": float(role_group[col].median()) for col in metric_columns}})
        for exposure, exposure_group in group.groupby("exposure_level"):
            summary_rows.append({"scope": "exposure_level", "group": exposure, "method": method, "count": len(exposure_group), **{f"median_{col}": float(exposure_group[col].median()) for col in metric_columns}})
    summary = pd.DataFrame(summary_rows)

    identity = frame[frame["identity_mode"].isin(["exact", "near"])]
    identity_summary = {
        method: {
            "count": int(len(group)),
            "median_source_drift_mae": float(group["source_drift_mae"].median()),
            "p95_source_drift_mae": float(group["source_drift_mae"].quantile(0.95)),
        }
        for method, group in identity.groupby("method", sort=False)
    }
    make_contact_sheet(
        sample_records,
        [source_cache[index] for index in sample_indices],
        [target_cache[index] for index in sample_indices],
        sample_predictions,
    )
    return frame, summary, identity_summary


def make_contact_sheet(
    records: list[dict[str, object]],
    sources: list[np.ndarray],
    targets: list[np.ndarray],
    predictions: dict[str, list[np.ndarray]],
) -> None:
    labels = ["Source", "Best E84", "Final E100", "Target"]
    tile = 192
    header = 34
    canvas = Image.new("RGB", (len(labels) * tile, len(records) * (tile + header)), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for row, record in enumerate(records):
        images = [sources[row], predictions["BestE84"][row], predictions["FinalE100"][row], targets[row]]
        for col, (label, image) in enumerate(zip(labels, images)):
            x = col * tile
            y = row * (tile + header)
            view = Image.fromarray(image).convert("RGB").resize((tile, tile), Image.Resampling.NEAREST)
            canvas.paste(view, (x, y + header))
            draw.text((x + 5, y + 4), f"{label} | {record['shape_family']}", fill="black", font=font)
            draw.text((x + 5, y + 18), f"{record['exposure_level']} / {record['polarity']}", fill="#475569", font=font)
    canvas.save(OUTPUT / "internal_test_checkpoint_comparison.png")


def analyze_training_history() -> tuple[pd.DataFrame, dict[str, object]]:
    simple_pattern = re.compile(
        r"\[SIMPLETEST\]\[E(\d+)\]\s+Rec=([0-9.eE+-]+).*?"
        r"GradMag=([0-9.eE+-]+).*?EdgeOri=([0-9.eE+-]+).*?"
        r"EqGeom=([0-9.eE+-]+).*?Total=([0-9.eE+-]+)"
    )
    val_pattern = re.compile(
        r"Epoch\s+(\d+)\s+Val Done\.\s+Total=([0-9.eE+-]+)\s+\|\s+"
        r"Rec=([0-9.eE+-]+)\s+\|\s+Edge=([0-9.eE+-]+)\s+\|\s+"
        r"EdgeProf=([0-9.eE+-]+)\s+\|\s+PSNR=([0-9.eE+-]+)\s+\|\s+"
        r"SSIM=([0-9.eE+-]+)\s+\|\s+FFTShape=([0-9.eE+-]+)\s+\|\s+"
        r"CB=([0-9.eE+-]+)\s+\|\s+HF=([0-9.eE+-]+)"
    )
    rows: dict[int, dict[str, float | int]] = {epoch: {"epoch": epoch} for epoch in range(1, 101)}
    guard_epochs: set[int] = set()
    current_epoch = 0
    for line in STDOUT_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("Starting Epoch"):
            match = re.search(r"Starting Epoch\s+(\d+)", line)
            if match:
                current_epoch = int(match.group(1))
        match = simple_pattern.search(line)
        if match:
            epoch = int(match.group(1))
            rows[epoch].update(
                train_rec=float(match.group(2)),
                train_gradmag=float(match.group(3)),
                train_edgeori=float(match.group(4)),
                train_eqgeom=float(match.group(5)),
                train_total=float(match.group(6)),
            )
        match = val_pattern.search(line)
        if match:
            epoch = int(match.group(1))
            names = ["val_total", "val_rec", "val_edge", "val_edge_profile", "val_psnr", "val_ssim", "val_fft_shape", "val_cb", "val_hf_ratio"]
            rows[epoch].update({name: float(value) for name, value in zip(names, match.groups()[1:])})
        if line.startswith("[GUARD][LAP]") and current_epoch:
            guard_epochs.add(current_epoch)
    history = pd.DataFrame([rows[epoch] for epoch in sorted(rows)])
    history["lap_guard"] = history["epoch"].isin(guard_epochs).astype(int)
    measured = history.dropna(subset=["val_total"]).copy()
    best_checkpoint = torch.load(BEST_CHECKPOINT, map_location="cpu")
    best_epoch = int(best_checkpoint["epoch"])
    history_summary = {
        "completed_epochs": int(history["epoch"].max()),
        "validation_measurement_count": int(len(measured)),
        "selected_best_epoch": best_epoch,
        "selected_tradeoff_score": float(best_checkpoint["tradeoff_score"]),
        "lowest_val_total_epoch": int(measured.loc[measured["val_total"].idxmin(), "epoch"]),
        "lowest_val_total": float(measured["val_total"].min()),
        "highest_val_psnr_epoch": int(measured.loc[measured["val_psnr"].idxmax(), "epoch"]),
        "highest_val_psnr_db": float(measured["val_psnr"].max()),
        "highest_val_ssim_epoch": int(measured.loc[measured["val_ssim"].idxmax(), "epoch"]),
        "highest_val_ssim": float(measured["val_ssim"].max()),
        "final_val_total": float(measured.iloc[-1]["val_total"]),
        "final_val_psnr_db": float(measured.iloc[-1]["val_psnr"]),
        "final_val_ssim": float(measured.iloc[-1]["val_ssim"]),
        "gmf_proxy_has_signal": False,
        "lap_guard_fraction": float(history["lap_guard"].mean()),
        "oversmooth_guard_fraction": float(history["lap_guard"].mean()),
        "source_table_alignment_issue": "The generated val CSV is shifted by one field after the prediction statistics; headline validation metrics were re-parsed from the stdout log.",
    }
    make_training_plot(history, best_epoch)
    return history, history_summary


def make_training_plot(history: pd.DataFrame, best_epoch: int) -> None:
    measured = history[history["val_total"] > 0]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    axes[0, 0].plot(history["epoch"], history["train_total"], color="#2563EB", label="Train")
    axes[0, 0].plot(measured["epoch"], measured["val_total"], color="#D97706", label="Validation")
    axes[0, 0].set_title("Total loss")
    axes[0, 0].set_yscale("log")
    axes[0, 0].legend(frameon=False)
    axes[0, 1].plot(measured["epoch"], measured["val_psnr"], color="#2563EB", label="PSNR")
    axes[0, 1].set_title("Validation PSNR")
    axes[1, 0].plot(measured["epoch"], measured["val_ssim"], color="#059669", label="SSIM")
    axes[1, 0].set_title("Validation SSIM")
    axes[1, 1].plot(history["epoch"], history["train_edgeori"], color="#7C3AED", label="Edge orientation")
    axes[1, 1].plot(history["epoch"], history["train_gradmag"], color="#DC2626", label="Gradient magnitude")
    axes[1, 1].set_title("Training edge losses")
    axes[1, 1].set_yscale("log")
    axes[1, 1].legend(frameon=False)
    for ax in axes.ravel():
        ax.axvline(best_epoch, color="#111827", linestyle="--", linewidth=1.2)
        ax.set_xlabel("Epoch")
        ax.grid(alpha=0.25)
    fig.suptitle("R75-v2 formal training diagnostics", fontsize=15, weight="bold")
    fig.savefig(OUTPUT / "training_diagnostics.png", dpi=180, facecolor="white")
    plt.close(fig)


def build_summary(history_summary: dict[str, object], test_summary: pd.DataFrame, identity: dict[str, object]) -> dict[str, object]:
    overall = test_summary[test_summary["scope"] == "overall"].set_index("method")
    best = overall.loc["BestE84"]
    final = overall.loc["FinalE100"]
    raw = overall.loc["Raw"]
    return {
        "status": "complete",
        "history": history_summary,
        "internal_test": {
            "image_count": int(raw["count"]),
            "raw": raw.to_dict(),
            "best_e84": best.to_dict(),
            "final_e100": final.to_dict(),
            "best_e84_vs_raw": {
                "mae_reduction_fraction": float((raw["median_mae"] - best["median_mae"]) / raw["median_mae"]),
                "contour_iou_gain": float(best["median_contour_iou"] - raw["median_contour_iou"]),
                "boundary_distance_reduction_px": float(raw["median_boundary_distance_px"] - best["median_boundary_distance_px"]),
            },
            "final_e100_vs_best_e84": {
                "mae_difference": float(final["median_mae"] - best["median_mae"]),
                "contour_iou_difference": float(final["median_contour_iou"] - best["median_contour_iou"]),
                "boundary_distance_difference_px": float(final["median_boundary_distance_px"] - best["median_boundary_distance_px"]),
            },
            "identity_guard": identity,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for required in [DATASET / "manifest.json", VAL_LOG, BATCH_LOG, STDOUT_LOG, BEST_CHECKPOINT, FINAL_CHECKPOINT]:
        if not required.is_file():
            raise FileNotFoundError(required)

    history, history_summary = analyze_training_history()
    per_image, test_summary, identity = evaluate_internal_test(args.device, args.batch_size)
    summary = build_summary(history_summary, test_summary, identity)
    history.to_csv(OUTPUT / "training_epoch_metrics.csv", index=False)
    per_image.to_csv(OUTPUT / "internal_test_per_image.csv", index=False)
    test_summary.to_csv(OUTPUT / "internal_test_summary.csv", index=False)
    (OUTPUT / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
