"""Post-training real 50x x-1um displacement comparison for frozen R89.

The ROI and edge-phase settings are copied without retuning from the thesis
50x_1um Raw run.  Raw and R89 always use the exact same frame pairs.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import convolve2d
from skimage.registration import phase_cross_correlation


ROI_XYWH_MATLAB = (685, 453, 746, 758)
PIXEL_SIZE_UM = 0.069
EXPECTED_STEP_UM = 1.0
UPSAMPLE_FACTOR = 100


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read {path}")
    return image


def edge_phase_input(path: Path) -> np.ndarray:
    image = read_gray(path).astype(np.float64) / 255.0
    x, y, width, height = ROI_XYWH_MATLAB
    image = image[y - 1 : y - 1 + height, x - 1 : x - 1 + width]
    axis = np.arange(-3, 4, dtype=np.float64)
    gaussian = np.exp(-(axis * axis) / 2.0)
    gaussian /= gaussian.sum()
    image = convolve2d(convolve2d(image, gaussian[:, None], mode="same"), gaussian[None, :], mode="same")
    sobel_x = np.asarray([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float64) / 8.0
    sobel_y = sobel_x.T
    edge = np.hypot(convolve2d(image, sobel_x, mode="same"), convolve2d(image, sobel_y, mode="same"))
    edge -= edge.mean()
    scale = edge.std()
    if scale > 1e-9:
        edge /= scale
    return edge * (np.hanning(height)[:, None] * np.hanning(width)[None, :])


def parse_time(name: str) -> datetime:
    match = re.search(r"Image__(\d{4}-\d{2}-\d{2})__(\d{2}-\d{2}-\d{2})", name)
    if match is None:
        raise ValueError(f"Timestamp missing from {name}")
    return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%Y-%m-%d %H-%M-%S")


def measure_sequence(folder: Path) -> tuple[list[Path], list[dict[str, float]]]:
    files = sorted(folder.glob("*.bmp"))
    if len(files) != 50:
        raise RuntimeError(f"Expected 50 BMP frames, got {len(files)} in {folder}")
    previous = edge_phase_input(files[0])
    rows: list[dict[str, float]] = []
    for index, path in enumerate(files[1:], start=1):
        current = edge_phase_input(path)
        shift, error, phase = phase_cross_correlation(
            previous,
            current,
            upsample_factor=UPSAMPLE_FACTOR,
            normalization=None,
        )
        dx, dy = -float(shift[1]), -float(shift[0])
        gap = (parse_time(path.name) - parse_time(files[index - 1].name)).total_seconds()
        rows.append(
            {
                "frame_index": index,
                "ref_filename": files[index - 1].name,
                "filename": path.name,
                "time_gap_s": gap,
                "same_session": gap <= 60.0,
                "regular_cadence": gap <= 10.0,
                "dx_px": dx,
                "dy_px": dy,
                "abs_dx_um": abs(dx) * PIXEL_SIZE_UM,
                "abs_dy_um": abs(dy) * PIXEL_SIZE_UM,
                "abs_error_um": abs(abs(dx) * PIXEL_SIZE_UM - EXPECTED_STEP_UM),
                "registration_error": float(error),
                "phase_difference": float(phase),
            }
        )
        previous = current
    return files, rows


def summarize(rows: list[dict[str, float]], selector: str | None = None) -> dict[str, float]:
    selected = rows if selector is None else [row for row in rows if bool(row[selector])]
    x = np.asarray([row["abs_dx_um"] for row in selected])
    y = np.asarray([row["abs_dy_um"] for row in selected])
    error = np.abs(x - EXPECTED_STEP_UM)
    return {
        "step_count": int(len(selected)),
        "median_abs_dx_um": float(np.median(x)),
        "mean_abs_dx_um": float(np.mean(x)),
        "std_abs_dx_um": float(np.std(x, ddof=1)),
        "mean_magnitude_bias_um": float(np.mean(x) - EXPECTED_STEP_UM),
        "median_abs_error_um": float(np.median(error)),
        "mean_abs_error_um": float(np.mean(error)),
        "p95_abs_error_um": float(np.percentile(error, 95)),
        "median_abs_dy_um": float(np.median(y)),
        "mean_abs_dy_um": float(np.mean(y)),
        "std_abs_dy_um": float(np.std(y, ddof=1)),
    }


def compare_rows(raw: list[dict[str, float]], model: list[dict[str, float]], selector: str | None = None) -> dict[str, float]:
    pairs = list(zip(raw, model))
    if selector is not None:
        pairs = [pair for pair in pairs if bool(pair[0][selector])]
    delta = np.asarray([model_row["abs_dx_um"] - raw_row["abs_dx_um"] for raw_row, model_row in pairs])
    return {
        "pair_count": int(len(pairs)),
        "mean_r89_minus_raw_abs_dx_um": float(np.mean(delta)),
        "median_abs_r89_raw_difference_um": float(np.median(np.abs(delta))),
        "p95_abs_r89_raw_difference_um": float(np.percentile(np.abs(delta), 95)),
        "std_r89_minus_raw_abs_dx_um": float(np.std(delta, ddof=1)),
    }


def visual_metrics(raw_path: Path, model_path: Path) -> dict[str, float]:
    raw = read_gray(raw_path).astype(np.float32)
    model = read_gray(model_path).astype(np.float32)
    difference = model - raw
    absolute = np.abs(difference)
    def edge(image: np.ndarray) -> np.ndarray:
        gx = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3)
        return np.hypot(gx, gy)
    raw_edge, model_edge = edge(raw), edge(model)
    return {
        "mean_signed_change_gray": float(difference.mean()),
        "mean_abs_change_gray": float(absolute.mean()),
        "p95_abs_change_gray": float(np.percentile(absolute, 95)),
        "fraction_changed_over_10_gray": float(np.mean(absolute > 10.0)),
        "mean_edge_strength_ratio": float(model_edge.mean() / raw_edge.mean()),
        "p95_edge_strength_ratio": float(np.percentile(model_edge, 95) / np.percentile(raw_edge, 95)),
    }


def save_montage(raw_path: Path, model_path: Path, output_path: Path) -> None:
    raw = read_gray(raw_path)
    model = read_gray(model_path)
    difference = np.clip(np.abs(model.astype(np.int16) - raw.astype(np.int16)) * 4, 0, 255).astype(np.uint8)
    panels = []
    for image, label in ((raw, "RAW FULL FRAME"), (model, "R89 E100 FULL FRAME"), (difference, "ABS DIFF x4")):
        panel = cv2.resize(image, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        panel = cv2.cvtColor(panel, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(panel, (0, 0), (450, 48), (0, 0, 0), -1)
        cv2.putText(panel, label, (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
        panels.append(panel)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), np.hstack(panels)):
        raise RuntimeError(f"Cannot save {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--reconstructed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-reference-summary", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    raw_files, raw_rows = measure_sequence(args.raw)
    model_files, model_rows = measure_sequence(args.reconstructed)
    if [path.name for path in raw_files] != [path.name for path in model_files]:
        raise RuntimeError("Raw and R89 frame identities differ")

    reference = json.loads(args.raw_reference_summary.read_text(encoding="utf-8"))
    raw_all = summarize(raw_rows)
    reproduction_fields = {
        "median_abs_dx_um_gap30": raw_all["median_abs_dx_um"],
        "mean_abs_dx_um_gap30": raw_all["mean_abs_dx_um"],
        "std_abs_dx_um_gap30": raw_all["std_abs_dx_um"],
        "median_abs_error_um_gap30": raw_all["median_abs_error_um"],
        "median_abs_dy_um_gap30": raw_all["median_abs_dy_um"],
    }
    reproduction_differences = {key: abs(float(value) - float(reference[key])) for key, value in reproduction_fields.items()}

    populations = {
        "all_adjacent": None,
        "same_session_gap_le_60s": "same_session",
        "regular_cadence_gap_le_10s": "regular_cadence",
    }
    summary = {
        "status": "complete",
        "checkpoint_epoch": 100,
        "fixed_roi_matlab_x_y_width_height": list(ROI_XYWH_MATLAB),
        "pixel_size_um": PIXEL_SIZE_UM,
        "expected_step_um": EXPECTED_STEP_UM,
        "upsample_factor": UPSAMPLE_FACTOR,
        "raw_reference_exactly_reproduced": max(reproduction_differences.values()) < 1e-12,
        "raw_reference_absolute_differences": reproduction_differences,
        "populations": {},
        "representative_full_frame": visual_metrics(raw_files[10], model_files[10]),
        "representative_filename": raw_files[10].name,
        "claim_limit": "The commanded 1 um step is not independent position truth; this test measures repeatability and physical consistency.",
    }
    for population, selector in populations.items():
        raw_summary = summarize(raw_rows, selector)
        model_summary = summarize(model_rows, selector)
        summary["populations"][population] = {
            "raw": raw_summary,
            "r89_epoch100": model_summary,
            "paired_change": {
                **compare_rows(raw_rows, model_rows, selector),
                "std_change_percent": 100.0 * (model_summary["std_abs_dx_um"] / raw_summary["std_abs_dx_um"] - 1.0),
                "mean_abs_error_change_um": model_summary["mean_abs_error_um"] - raw_summary["mean_abs_error_um"],
                "median_abs_error_change_um": model_summary["median_abs_error_um"] - raw_summary["median_abs_error_um"],
            },
        }

    with (args.output / "paired_steps.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = list(raw_rows[0].keys()) + [
            "r89_dx_px", "r89_dy_px", "r89_abs_dx_um", "r89_abs_dy_um", "r89_abs_error_um", "r89_minus_raw_abs_dx_um"
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for raw_row, model_row in zip(raw_rows, model_rows):
            row = dict(raw_row)
            row.update(
                r89_dx_px=model_row["dx_px"],
                r89_dy_px=model_row["dy_px"],
                r89_abs_dx_um=model_row["abs_dx_um"],
                r89_abs_dy_um=model_row["abs_dy_um"],
                r89_abs_error_um=model_row["abs_error_um"],
                r89_minus_raw_abs_dx_um=model_row["abs_dx_um"] - raw_row["abs_dx_um"],
            )
            writer.writerow(row)

    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    index = np.arange(1, len(raw_rows) + 1)
    plt.figure(figsize=(12, 5))
    plt.plot(index, [row["abs_dx_um"] for row in raw_rows], "o-", ms=3, lw=1, label="Raw")
    plt.plot(index, [row["abs_dx_um"] for row in model_rows], "o-", ms=3, lw=1, label="R89 epoch 100")
    plt.axhline(EXPECTED_STEP_UM, color="black", ls="--", lw=1, label="Commanded 1 um")
    plt.xlabel("Adjacent frame step")
    plt.ylabel("Measured |dx| (um)")
    plt.title("Fixed-ROI 50x displacement: Raw vs R89 epoch 100")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(args.output / "step_trace.png", dpi=180)
    plt.close()
    save_montage(raw_files[10], model_files[10], args.output / "representative_full_frame_comparison.png")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
