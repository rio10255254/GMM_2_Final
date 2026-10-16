from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_r78 as primary


def main() -> None:
    config = primary.read_json(primary.CONFIG_PATH)
    followup = primary.read_json(ROOT / "config" / "followup_5x_all_frames.json")
    settings = followup["metrics"]
    rows = []
    for sequence in followup["scope"]:
        item = config["sequences"][sequence]
        raw_paths = primary.image_paths(Path(item["raw_dir"]))
        model_paths = {
            "R61v16": primary.image_paths(Path(item["r61_dir"])),
            "R75v2E100": primary.image_paths(primary.R75_RECON / sequence),
            "R75v2E100_tile1024": primary.image_paths(
                ROOT / "results" / "diagnostics" / "5x_tile1024_full" / sequence
            ),
        }
        if any(len(paths) != len(raw_paths) for paths in model_paths.values()):
            raise RuntimeError(f"{sequence}: follow-up output coverage mismatch")
        for index, raw_path in enumerate(raw_paths):
            raw_image = primary.read_gray(raw_path)
            raw_gradient = primary.gradient_magnitude(raw_image)
            raw_threshold = float(np.percentile(raw_gradient, settings["raw_edge_percentile"]))
            raw_support = raw_gradient >= raw_threshold
            distance = cv2.distanceTransform((~raw_support).astype(np.uint8), cv2.DIST_L2, 5)
            raw_detail = raw_image.astype(np.float32) - cv2.GaussianBlur(
                raw_image.astype(np.float32), (0, 0), 2.0
            )
            for method, paths in model_paths.items():
                model_image = primary.read_gray(paths[index])
                model_gradient = primary.gradient_magnitude(model_image)
                model_threshold = float(np.percentile(model_gradient, settings["model_edge_percentile"]))
                model_strong = model_gradient >= model_threshold
                model_detail = model_image.astype(np.float32) - cv2.GaussianBlur(
                    model_image.astype(np.float32), (0, 0), 2.0
                )
                rows.append(
                    {
                        "sequence": sequence,
                        "frame_index": index,
                        "method": method,
                        "off_source_strong_edge_fraction": float(
                            np.mean(distance[model_strong] > float(settings["distance_px"]))
                        ),
                        "edge_gain_on_raw_support": float(
                            np.median(model_gradient[raw_support])
                            / max(float(np.median(raw_gradient[raw_support])), 1e-9)
                        ),
                        "fine_detail_energy_ratio": float(
                            np.std(model_detail) / max(float(np.std(raw_detail)), 1e-9)
                        ),
                    }
                )
    table = pd.DataFrame(rows)
    output_dir = primary.TABLES
    output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(output_dir / "followup_5x_all_frames.csv", index=False)
    summary_rows = []
    for (sequence, method), group in table.groupby(["sequence", "method"]):
        summary_rows.append(
            {
                "sequence": sequence,
                "method": method,
                "frames": int(len(group)),
                "median_off_source_strong_edge_fraction": float(
                    group["off_source_strong_edge_fraction"].median()
                ),
                "p95_off_source_strong_edge_fraction": float(
                    group["off_source_strong_edge_fraction"].quantile(0.95)
                ),
                "median_edge_gain_on_raw_support": float(
                    group["edge_gain_on_raw_support"].median()
                ),
                "median_fine_detail_energy_ratio": float(
                    group["fine_detail_energy_ratio"].median()
                ),
                "warning_off_source_frame_fraction": float(
                    (group["off_source_strong_edge_fraction"] > settings["warning_off_source_fraction"]).mean()
                ),
                "warning_low_edge_gain_frame_fraction": float(
                    (group["edge_gain_on_raw_support"] < settings["warning_edge_gain"]).mean()
                ),
            }
        )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / "followup_5x_summary.csv", index=False)
    r75 = summary.loc[summary["method"] == "R75v2E100"]
    r75_large = summary.loc[summary["method"] == "R75v2E100_tile1024"]
    decision = {
        "status": "complete",
        "evidence_role": "post_hoc_confirmatory",
        "unique_real_frames_checked": 100,
        "r75v2_5x_anomaly_repeated_in_both_sequences": bool(
            (r75["warning_off_source_frame_fraction"] >= 0.9).all()
            and (r75["warning_low_edge_gain_frame_fraction"] >= 0.9).all()
        ),
        "larger_tiles_reduce_warning_in_both_sequences": bool(
            (r75_large["warning_off_source_frame_fraction"] < 0.1).all()
            and (r75_large["warning_low_edge_gain_frame_fraction"] < 0.1).all()
        ),
        "larger_tiles_fully_restore_fine_detail": bool(
            (r75_large["median_fine_detail_energy_ratio"] >= 0.9).all()
        ),
        "claim_limit": followup["claim_limit"],
    }
    primary.write_json(primary.RESULTS / "followup_5x_decision.json", decision)
    print(summary.to_string(index=False))
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
