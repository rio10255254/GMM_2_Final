from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


def read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Could not read {path}")
    return image.astype(np.float32)


def load_run(run_root: Path, label: str) -> dict:
    training = json.loads((run_root / "training_summary.json").read_text(encoding="utf-8"))
    methods = pd.read_csv(run_root / "analysis" / "learning_baseline_method_summary.csv")
    base = methods.loc[methods.method == "Base U-Net"]
    if len(base) != 1:
        raise RuntimeError(f"{run_root}: missing Base U-Net method summary")
    base = base.iloc[0]
    edge = pd.read_csv(run_root / "analysis" / "base_unet_edge_width_summary_top30.csv")
    edge = edge.loc[edge.method == "Base U-Net"].set_index("magnification")
    hypothesis = pd.read_csv(
        run_root / "analysis" / "base_unet_smoothing_hypothesis_summary.csv"
    ).set_index("method").loc["Base U-Net"]
    inference = json.loads(
        (run_root / "real_inference" / "inference_manifest.json").read_text(encoding="utf-8")
    )
    static_records = [record for record in inference["records"] if record["kind"] == "static"]
    brightness: dict[str, float] = {}
    for record in static_records:
        source = read_gray(Path(record["source"]))
        output = read_gray(Path(record["output"]))
        key = record["name"]
        brightness[f"{key}_raw_mean"] = float(source.mean())
        brightness[f"{key}_base_mean"] = float(output.mean())
        brightness[f"{key}_base_to_raw_mean_ratio"] = float(output.mean() / source.mean())
        brightness[f"{key}_raw_std"] = float(source.std())
        brightness[f"{key}_base_std"] = float(output.std())
        brightness[f"{key}_base_to_raw_std_ratio"] = float(output.std() / source.std())
    return {
        "run": label,
        "scheduled_epochs": int(training["config"]["epochs"]),
        "best_epoch": int(training["best_epoch"]),
        "validation_loss": float(training["best_validation"]["loss"]),
        "validation_l1": float(training["best_validation"]["l1"]),
        "validation_ssim": float(training["best_validation"]["ssim"]),
        "cd_50x_median_abs_error_nm": float(base.cd_50x_median_abs_error_nm),
        "cd_20x_median_abs_error_nm": float(base.cd_20x_median_abs_error_nm),
        "displacement_reference_mae_nm": float(base.displacement_reference_mae_nm),
        "nine_pillar_inconsistency_mean_nm": float(base.nine_pillar_inconsistency_mean_nm),
        "edge_width_50x_nm": float(edge.loc["50x", "median_transition_width_nm"]),
        "edge_width_20x_nm": float(edge.loc["20x", "median_transition_width_nm"]),
        "within_sequence_width_disagreement_pearson": float(
            hypothesis.within_sequence_pearson
        ),
        "within_sequence_width_disagreement_spearman": float(
            hypothesis.within_sequence_spearman
        ),
        "inference_record_count": int(inference["record_count"]),
        "inference_mode": inference.get("inference_mode", "legacy_full_frame"),
        **brightness,
    }


def compare(run15: Path, run30: Path, output: Path) -> None:
    rows = [load_run(run15, "15-epoch schedule"), load_run(run30, "30-epoch schedule")]
    table = pd.DataFrame(rows)
    if not (table.inference_record_count == 203).all():
        raise RuntimeError("At least one inference run does not contain all 203 images")
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False, encoding="utf-8-sig")
    output.with_suffix(".json").write_text(
        json.dumps(table.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(table.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run15", type=Path, required=True)
    parser.add_argument("--run30", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    compare(arguments.run15.resolve(), arguments.run30.resolve(), arguments.output.resolve())
