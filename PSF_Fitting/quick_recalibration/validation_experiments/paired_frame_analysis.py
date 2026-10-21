from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

PSF_FITTING_ROOT = Path(__file__).resolve().parents[2]
if str(PSF_FITTING_ROOT) not in sys.path:
    sys.path.insert(0, str(PSF_FITTING_ROOT))

from quick_recalibration.validation_experiments.l0_newdata_analysis import json_ready
from quick_recalibration.validation_experiments.l0_newdata_tools import (
    build_circle_edge_mask,
    crop_centered,
    detect_round_grid_centers,
    fill_inner_blocks,
    old_standard_positions,
    split_position_repeats,
)


VALIDATION_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = VALIDATION_DIR / "L1_paired_frame_check"
SUMMARY_MD = OUTPUT_DIR / "paired_frame_summary.md"
SUMMARY_JSON = OUTPUT_DIR / "paired_frame_summary.json"
METRICS_CSV = OUTPUT_DIR / "paired_frame_metrics.csv"
README_TW = OUTPUT_DIR / "README_TW.md"
GT_PATH = PSF_FITTING_ROOT / "Crop_circle_FreqFiltered" / "GT" / "GT_901_with_Block_proc.bmp"

ROUND_NUMBERS = [1, 2, 3]
GRID_ROWS = 11
GRID_COLS = 11
REPEATS_PER_POSITION = 2
CROP_SIZE = 901

METRIC_KEYS = [
    "edge_mean_abs_diff",
    "edge_rms_diff",
    "edge_p95_abs_diff",
    "edge_signed_mean_diff",
    "full_mean_abs_diff",
    "full_rms_diff",
    "full_p95_abs_diff",
    "full_signed_mean_diff",
    "center_shift_px",
]


def paired_output_paths() -> dict[str, Path]:
    return {
        "summary_dir": OUTPUT_DIR,
        "summary_md": SUMMARY_MD,
        "summary_json": SUMMARY_JSON,
        "metrics_csv": METRICS_CSV,
        "readme_tw": README_TW,
    }


def read_gray(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("L"))


def _masked_values(values: np.ndarray, mask: np.ndarray) -> np.ndarray:
    mask = np.asarray(mask, dtype=bool)
    if values.shape != mask.shape:
        raise ValueError(f"Mask shape {mask.shape} does not match image shape {values.shape}")
    selected = values[mask]
    if selected.size == 0:
        raise ValueError("Edge mask is empty")
    return selected


def _rms(values: np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    return float(np.sqrt(np.mean(arr * arr))) if arr.size else 0.0


def compute_pair_metrics(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    *,
    edge_mask: np.ndarray,
    center_a: tuple[float, float],
    center_b: tuple[float, float],
) -> dict[str, float]:
    a = np.asarray(frame_a, dtype=float)
    b = np.asarray(frame_b, dtype=float)
    if a.shape != b.shape:
        raise ValueError(f"Frame shapes do not match: {a.shape} != {b.shape}")

    diff = b - a
    abs_diff = np.abs(diff)
    edge_diff = _masked_values(diff, edge_mask)
    edge_abs = np.abs(edge_diff)

    return {
        "full_mean_abs_diff": float(np.mean(abs_diff)),
        "full_median_abs_diff": float(np.median(abs_diff)),
        "full_p95_abs_diff": float(np.percentile(abs_diff, 95)),
        "full_max_abs_diff": float(np.max(abs_diff)),
        "full_rms_diff": _rms(diff),
        "full_signed_mean_diff": float(np.mean(diff)),
        "edge_mean_abs_diff": float(np.mean(edge_abs)),
        "edge_median_abs_diff": float(np.median(edge_abs)),
        "edge_p95_abs_diff": float(np.percentile(edge_abs, 95)),
        "edge_max_abs_diff": float(np.max(edge_abs)),
        "edge_rms_diff": _rms(edge_diff),
        "edge_signed_mean_diff": float(np.mean(edge_diff)),
        "center_shift_px": float(np.hypot(center_b[0] - center_a[0], center_b[1] - center_a[1])),
    }


def summarize_pair_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"count": len(rows)}
    for key in METRIC_KEYS:
        if not rows:
            summary[f"{key}_median"] = None
            summary[f"{key}_mean"] = None
            summary[f"{key}_p95"] = None
            summary[f"{key}_max"] = None
            continue
        values = np.array([float(row[key]) for row in rows], dtype=float)
        summary[f"{key}_median"] = float(np.median(values))
        summary[f"{key}_mean"] = float(np.mean(values))
        summary[f"{key}_p95"] = float(np.percentile(values, 95))
        summary[f"{key}_max"] = float(np.max(values))
    return summary


def analyze_round_pairs(
    round_number: int,
    *,
    gt_path: Path = GT_PATH,
    grid_rows: int = GRID_ROWS,
    grid_cols: int = GRID_COLS,
    repeats_per_position: int = REPEATS_PER_POSITION,
    crop_size: int = CROP_SIZE,
) -> list[dict[str, Any]]:
    round_name = f"Circle_Round{round_number}"
    round_dir = VALIDATION_DIR / round_name
    files = sorted(round_dir.glob("VisionTop_*.bmp"))
    records = split_position_repeats(
        files,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        repeats_per_position=repeats_per_position,
    )

    gt = read_gray(gt_path)
    edge_mask = build_circle_edge_mask(gt)
    centers_frame_1 = detect_round_grid_centers(
        records,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        frame_index=0,
    )
    centers_frame_2 = detect_round_grid_centers(
        records,
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        frame_index=1,
    )

    rows: list[dict[str, Any]] = []
    for record in records:
        center_1 = tuple(centers_frame_1[record.position_index]["center"])
        center_2 = tuple(centers_frame_2[record.position_index]["center"])
        frame_1 = read_gray(record.frames[0])
        frame_2 = read_gray(record.frames[1])
        crop_1 = crop_centered(frame_1, center_1, crop_size=crop_size)
        crop_2 = crop_centered(frame_2, center_2, crop_size=crop_size)
        crop_1 = fill_inner_blocks(crop_1, gt_image=gt)
        crop_2 = fill_inner_blocks(crop_2, gt_image=gt)
        metrics = compute_pair_metrics(
            crop_1,
            crop_2,
            edge_mask=edge_mask,
            center_a=center_1,
            center_b=center_2,
        )
        rows.append(
            {
                "round_number": round_number,
                "round_name": round_name,
                "position_index": record.position_index,
                "row": record.row,
                "col": record.col,
                "frame_1": str(record.frames[0]),
                "frame_2": str(record.frames[1]),
                **metrics,
            }
        )
    return rows


def _group_by_round(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: list[dict[str, Any]] = []
    round_names = sorted({row["round_name"] for row in rows})
    for round_name in round_names:
        selected = [row for row in rows if row["round_name"] == round_name]
        grouped.append({"round_name": round_name, **summarize_pair_rows(selected)})
    return grouped


def _top_rows(rows: list[dict[str, Any]], key: str, count: int = 10) -> list[dict[str, Any]]:
    selected = sorted(rows, key=lambda row: float(row[key]), reverse=True)[:count]
    keep = [
        "round_name",
        "position_index",
        "row",
        "col",
        "edge_mean_abs_diff",
        "edge_rms_diff",
        "edge_p95_abs_diff",
        "center_shift_px",
    ]
    return [{name: row[name] for name in keep} for row in selected]


def build_paired_summary_payload(
    rows: list[dict[str, Any]],
    *,
    old_standard_positions: list[int],
) -> dict[str, Any]:
    old_set = set(old_standard_positions)
    old_rows = [row for row in rows if int(row["position_index"]) in old_set]
    return {
        "experiment": "paired_frame_image_layer_check",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "method": {
            "analysis_layer": "image_intensity_after_fit_style_crop",
            "psf_fit_status": "not_run_for_frame_2",
            "pair_rule": "within each Circle_Round, compare frame 1 and frame 2 at the same 11x11 grid position",
            "crop_rule": "detect each frame center, crop 901x901, fill center block, then compare full crop and circle-edge mask",
            "fit_relevance": "edge-mask metrics are closest to the circle-boundary target used by the fitter",
        },
        "data_rule": {
            "rounds": [f"Circle_Round{number}" for number in ROUND_NUMBERS],
            "grid": f"{GRID_ROWS}x{GRID_COLS}",
            "positions_per_round": GRID_ROWS * GRID_COLS,
            "frames_per_position": REPEATS_PER_POSITION,
            "old_standard_positions": old_standard_positions,
        },
        "summary": {
            "all_positions": summarize_pair_rows(rows),
            "old_standard_positions": summarize_pair_rows(old_rows),
            "per_round": _group_by_round(rows),
            "worst_edge_rms": _top_rows(rows, "edge_rms_diff"),
            "worst_center_shift": _top_rows(rows, "center_shift_px"),
        },
        "rows": rows,
    }


def write_metrics_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _format_float(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def write_report(payload: dict[str, Any]) -> tuple[Path, Path, Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = payload["rows"]
    SUMMARY_JSON.write_text(json.dumps(json_ready(payload), indent=2, ensure_ascii=False), encoding="utf-8")
    write_metrics_csv(rows, METRICS_CSV)

    all_summary = payload["summary"]["all_positions"]
    old_summary = payload["summary"]["old_standard_positions"]

    lines: list[str] = []
    lines.append("# Paired-Frame Image-Layer Check")
    lines.append("")
    lines.append(f"- Generated: {payload['generated_at']}")
    lines.append("- Scope: frame 1 versus frame 2 at the same position inside each capture round.")
    lines.append("- Layer: image intensity after fit-style crop and center-block fill.")
    lines.append("- Important: frame 2 has not been through the PSF fitter, so this is a supplemental image-layer check.")
    lines.append("")
    lines.append("## Main Readout")
    lines.append("")
    lines.append("| Selection | Pairs | Edge mean abs median | Edge RMS median | Edge p95 median | Center shift median |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    lines.append(
        f"| All 121 positions x 3 rounds "
        f"| {all_summary['count']} "
        f"| {_format_float(all_summary['edge_mean_abs_diff_median'])} "
        f"| {_format_float(all_summary['edge_rms_diff_median'])} "
        f"| {_format_float(all_summary['edge_p95_abs_diff_median'])} "
        f"| {_format_float(all_summary['center_shift_px_median'])} |"
    )
    lines.append(
        f"| Old nine L0/L1 positions "
        f"| {old_summary['count']} "
        f"| {_format_float(old_summary['edge_mean_abs_diff_median'])} "
        f"| {_format_float(old_summary['edge_rms_diff_median'])} "
        f"| {_format_float(old_summary['edge_p95_abs_diff_median'])} "
        f"| {_format_float(old_summary['center_shift_px_median'])} |"
    )
    lines.append("")
    lines.append("## Per Round")
    lines.append("")
    lines.append("| Round | Pairs | Edge mean abs median | Edge RMS median | Edge p95 median | Center shift median |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for row in payload["summary"]["per_round"]:
        lines.append(
            f"| {row['round_name']} "
            f"| {row['count']} "
            f"| {_format_float(row['edge_mean_abs_diff_median'])} "
            f"| {_format_float(row['edge_rms_diff_median'])} "
            f"| {_format_float(row['edge_p95_abs_diff_median'])} "
            f"| {_format_float(row['center_shift_px_median'])} |"
        )
    lines.append("")
    lines.append("## Worst Edge-RMS Pairs")
    lines.append("")
    lines.append("| Round | Position | Row | Col | Edge mean abs | Edge RMS | Edge p95 | Center shift |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in payload["summary"]["worst_edge_rms"]:
        lines.append(
            f"| {row['round_name']} | {row['position_index']} | {row['row']} | {row['col']} "
            f"| {_format_float(row['edge_mean_abs_diff'])} "
            f"| {_format_float(row['edge_rms_diff'])} "
            f"| {_format_float(row['edge_p95_abs_diff'])} "
            f"| {_format_float(row['center_shift_px'])} |"
        )
    lines.append("")
    lines.append("## Worst Center-Shift Pairs")
    lines.append("")
    lines.append("| Round | Position | Row | Col | Center shift | Edge RMS |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for row in payload["summary"]["worst_center_shift"]:
        lines.append(
            f"| {row['round_name']} | {row['position_index']} | {row['row']} | {row['col']} "
            f"| {_format_float(row['center_shift_px'])} "
            f"| {_format_float(row['edge_rms_diff'])} |"
        )
    lines.append("")
    lines.append("## Guardrail")
    lines.append("")
    lines.append("- Use this report to judge short-time same-position image repeatability.")
    lines.append("- Do not read it as PSF-coefficient repeatability unless frame 2 is fitted in a separate long run.")
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")

    tw_lines = [
        "# 同位置兩張影像補充檢查",
        "",
        f"- 產生時間：{payload['generated_at']}",
        "- 這份檢查比較每個位置的第一張和第二張影像。",
        "- 比較方式先做和擬合接近的裁切與中心方塊處理，再看圓形邊界附近的灰階差異。",
        "- 這不是第二張影像的 PSF 擬合結果；第二張影像目前沒有另外跑擬合。",
        f"- 全部 363 組配對的邊界中位差異：{_format_float(all_summary['edge_mean_abs_diff_median'])} 灰階。",
        f"- 舊標準 27 組配對的邊界中位差異：{_format_float(old_summary['edge_mean_abs_diff_median'])} 灰階。",
        f"- 全部配對的中心位移中位數：{_format_float(all_summary['center_shift_px_median'])} px。",
        f"- 舊標準位置的中心位移中位數：{_format_float(old_summary['center_shift_px_median'])} px。",
    ]
    README_TW.write_text("\n".join(tw_lines), encoding="utf-8")
    return SUMMARY_MD, SUMMARY_JSON, METRICS_CSV, README_TW


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare paired frames in Circle_Round captures.")
    parser.add_argument("--rounds", nargs="+", type=int, default=ROUND_NUMBERS)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for round_number in args.rounds:
        round_rows = analyze_round_pairs(round_number)
        rows.extend(round_rows)
        print(f"Circle_Round{round_number}: {len(round_rows)} paired positions analyzed")

    payload = build_paired_summary_payload(
        rows,
        old_standard_positions=old_standard_positions(GRID_ROWS, GRID_COLS),
    )
    summary_md, summary_json, metrics_csv, readme = write_report(payload)
    all_summary = payload["summary"]["all_positions"]
    old_summary = payload["summary"]["old_standard_positions"]
    print(f"All-pair edge mean abs median: {_format_float(all_summary['edge_mean_abs_diff_median'])}")
    print(f"Old-position edge mean abs median: {_format_float(old_summary['edge_mean_abs_diff_median'])}")
    print(f"Report written: {summary_md}")
    print(f"JSON written: {summary_json}")
    print(f"CSV written: {metrics_csv}")
    print(f"README written: {readme}")


if __name__ == "__main__":
    main()
