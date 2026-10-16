from __future__ import annotations

import json
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures\20260710_v42_full_validation\synthetic_holdout")
RAW = ROOT / "raw_blurred"
GT = ROOT / "ground_truth"
PRED = ROOT / "reconstructions" / "reconstruct_progress_epoch_120_in_raw_blurred_20260709_202713" / "v42_e120"
TABLE = ROOT / "tables"
FIG = ROOT / "figures"


def binarize(image: np.ndarray, target: np.ndarray) -> np.ndarray:
    _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inv = cv2.bitwise_not(binary)
    def iou(candidate: np.ndarray) -> float:
        a, b = candidate > 0, target > 0
        return float(np.logical_and(a, b).sum() / max(1, np.logical_or(a, b).sum()))
    return binary if iou(binary) >= iou(inv) else inv


def edge_distance_px(pred: np.ndarray, truth: np.ndarray) -> float:
    edge_pred = cv2.Canny(pred, 50, 150) > 0
    edge_truth = cv2.Canny(truth, 50, 150) > 0
    if not edge_pred.any() or not edge_truth.any():
        return float("nan")
    d_truth = cv2.distanceTransform((~edge_truth).astype(np.uint8), cv2.DIST_L2, 3)
    d_pred = cv2.distanceTransform((~edge_pred).astype(np.uint8), cv2.DIST_L2, 3)
    return float(0.5 * (d_truth[edge_pred].mean() + d_pred[edge_truth].mean()))


def measure(image: np.ndarray, truth: np.ndarray) -> tuple[float, float, np.ndarray]:
    binary = binarize(image, truth)
    a, b = binary > 0, truth > 0
    iou = float(np.logical_and(a, b).sum() / max(1, np.logical_or(a, b).sum()))
    return iou, edge_distance_px(binary, truth), binary


def main() -> None:
    TABLE.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    by_file = {row["file"]: row for row in manifest["records"]}
    rows, previews = [], []
    for path in sorted(GT.glob("*.bmp")):
        truth = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        raw = cv2.imread(str(RAW / path.name), cv2.IMREAD_GRAYSCALE)
        pred = cv2.imread(str(PRED / path.name), cv2.IMREAD_GRAYSCALE)
        if truth is None or raw is None or pred is None:
            raise RuntimeError(f"Missing sample {path.name}")
        _, truth_bin = cv2.threshold(truth, 127, 255, cv2.THRESH_BINARY)
        raw_iou, raw_dist, raw_bin = measure(raw, truth_bin)
        pred_iou, pred_dist, pred_bin = measure(pred, truth_bin)
        rows.append({
            **by_file[path.name],
            "raw_iou": raw_iou, "v42_iou": pred_iou,
            "raw_boundary_distance_px": raw_dist, "v42_boundary_distance_px": pred_dist,
            "iou_change": pred_iou - raw_iou,
            "boundary_distance_improvement_px": raw_dist - pred_dist,
        })
        if len(previews) < 6:
            previews.append((path.name, truth, raw, pred, truth_bin, raw_bin, pred_bin))
    df = pd.DataFrame(rows)
    df.to_csv(TABLE / "synthetic_holdout_per_image.csv", index=False, encoding="utf-8-sig", float_format="%.7f")
    summary = pd.DataFrame([{
        "n_images": len(df),
        "raw_mean_iou": df.raw_iou.mean(), "v42_mean_iou": df.v42_iou.mean(),
        "raw_median_iou": df.raw_iou.median(), "v42_median_iou": df.v42_iou.median(),
        "raw_mean_boundary_distance_px": df.raw_boundary_distance_px.mean(),
        "v42_mean_boundary_distance_px": df.v42_boundary_distance_px.mean(),
        "raw_median_boundary_distance_px": df.raw_boundary_distance_px.median(),
        "v42_median_boundary_distance_px": df.v42_boundary_distance_px.median(),
        "iou_improved_count": int((df.iou_change > 0).sum()),
        "boundary_improved_count": int((df.boundary_distance_improvement_px > 0).sum()),
    }])
    summary.to_csv(TABLE / "synthetic_holdout_summary.csv", index=False, encoding="utf-8-sig", float_format="%.7f")
    fig, axes = plt.subplots(len(previews), 4, figsize=(12, 3 * len(previews)), dpi=170)
    for row_ax, (name, truth, raw, pred, truth_bin, raw_bin, pred_bin) in zip(axes, previews):
        for ax, image, title in zip(row_ax, [truth, raw, pred, cv2.absdiff(pred_bin, truth_bin)], ["Ground truth", "Blurred input", "V42 epoch 120", "V42 binary disagreement"]):
            ax.imshow(image, cmap="gray", vmin=0, vmax=255)
            ax.set_title(title, fontsize=9)
            ax.axis("off")
        row_ax[0].set_ylabel(name, fontsize=8)
    fig.suptitle("Held-out synthetic boundary examples", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(FIG / "synthetic_holdout_examples.png", bbox_inches="tight")
    plt.close(fig)
    report = [
        "# Held-out Synthetic Boundary Test",
        "",
        "The shapes and blur settings were generated after training with a fixed new seed; their unblurred edges are the reference.",
        "This is controlled simulation evidence, not a substitute for independent microscope measurements.",
        "",
        summary.to_markdown(index=False, floatfmt=".4f"),
    ]
    (ROOT / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
