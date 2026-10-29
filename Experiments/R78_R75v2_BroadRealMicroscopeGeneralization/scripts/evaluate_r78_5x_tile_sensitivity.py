from __future__ import annotations

import sys
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_r78 as primary
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def metrics(raw: np.ndarray, model: np.ndarray) -> dict:
    raw_gradient = primary.gradient_magnitude(raw)
    model_gradient = primary.gradient_magnitude(model)
    raw_support = raw_gradient >= np.percentile(raw_gradient, 85)
    distance = cv2.distanceTransform((~raw_support).astype(np.uint8), cv2.DIST_L2, 5)
    model_strong = model_gradient >= np.percentile(model_gradient, 95)
    raw_detail = raw.astype(np.float32) - cv2.GaussianBlur(raw.astype(np.float32), (0, 0), 2.0)
    model_detail = model.astype(np.float32) - cv2.GaussianBlur(model.astype(np.float32), (0, 0), 2.0)
    return {
        "off_source_strong_edge_fraction": float(np.mean(distance[model_strong] > 3)),
        "edge_gain_on_raw_support": float(
            np.median(model_gradient[raw_support]) / max(float(np.median(raw_gradient[raw_support])), 1e-9)
        ),
        "fine_detail_energy_ratio": float(np.std(model_detail) / max(float(np.std(raw_detail)), 1e-9)),
    }


def main() -> None:
    raw_path = Path(
        str(PROJECT_ROOT / '20260704_20x_5x_analysis/raw_inputs/5x_0p5um/bmp/frame_0000.bmp')
    )
    paths = {
        "R75 tile 512 / overlap 64": primary.R75_RECON / "5x_0p5um" / "frame_0000.bmp",
        "R75 tile 768 / overlap 96": ROOT / "results" / "diagnostics" / "5x_tile_sensitivity" / "tile768_overlap96" / "frame_0000.bmp",
        "R75 tile 1024 / overlap 128": ROOT / "results" / "diagnostics" / "5x_tile_sensitivity" / "tile1024_overlap128" / "frame_0000.bmp",
    }
    raw = primary.read_gray(raw_path)
    rows = []
    images = [("Raw", raw)]
    for label, path in paths.items():
        image = primary.read_gray(path)
        rows.append({"setting": label, **metrics(raw, image)})
        images.append((label, image))
    table = pd.DataFrame(rows)
    table.to_csv(primary.TABLES / "followup_5x_tile_sensitivity.csv", index=False)
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    for axis, (label, image) in zip(axes, images):
        lo, hi = np.percentile(image, [0.5, 99.5])
        axis.imshow(image, cmap="gray", vmin=lo, vmax=hi)
        axis.set_title(label, fontsize=9)
        axis.axis("off")
    fig.suptitle("5x tile-size sensitivity: fixed frame 0000")
    fig.tight_layout()
    figure_path = primary.FIGURES / "05_followup_5x_tile_sensitivity.png"
    fig.savefig(figure_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    largest = table.iloc[-1]
    substantially_reduced = bool(
        largest["off_source_strong_edge_fraction"] < 0.05
        and largest["edge_gain_on_raw_support"] >= 0.5
    )
    fine_detail_restored = bool(largest["fine_detail_energy_ratio"] >= 0.9)
    primary.write_json(
        primary.RESULTS / "followup_5x_tile_sensitivity_decision.json",
        {
            "status": "complete",
            "evidence_role": "post_hoc_root_cause_diagnostic",
            "single_fixed_frame": str(raw_path),
            "artifact_substantially_reduced_by_larger_tiles": substantially_reduced,
            "fine_detail_fully_restored": fine_detail_restored,
            "artifact_fully_resolved_by_larger_tiles": bool(
                substantially_reduced and fine_detail_restored
            ),
            "claim_limit": "One frame only; used to distinguish a simple tile-size issue from persistent 5x scale mismatch.",
        },
    )
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
