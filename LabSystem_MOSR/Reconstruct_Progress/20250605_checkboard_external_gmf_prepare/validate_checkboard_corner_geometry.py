from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


RUN_DIR = Path(__file__).resolve().parent
LAB_ROOT = RUN_DIR.parents[1]
CASES_DIR = RUN_DIR / "gmf_cases"
OUTPUT_DIR = RUN_DIR / "corner_geometry_validation_r46_20260612"
TRAINING_DATA_DIR = LAB_ROOT / "Training_Data"
REPORT_PATH = LAB_ROOT / "Experiments" / "reports" / "LAB_R46_CHECKBOARD_CORNER_VALIDATION_20260612.md"

CASES = [
    ("raw_input", "Raw input"),
    ("lab_r39_latest", "Lab R39 latest"),
    ("lab_r40_latest", "Lab R40 latest"),
    ("lab_r39_best_tradeoff", "Lab R39 tradeoff"),
    ("lab_r40_best_tradeoff", "Lab R40 tradeoff"),
    ("lab_r46_best_tradeoff", "Lab R46 tradeoff"),
    ("lab_r46_best_detail_guarded", "Lab R46 detail"),
    ("lab_r46_latest", "Lab R46 latest"),
]

PATCH_RADIUS = 48
CENTRAL_HARRIS_RADIUS = 28
MAX_CORNERS_PER_FRAME = 25
CHECKER_CONTRAST_MIN = 0.25
FAR_ZONE = (24, 42)


@dataclass(frozen=True)
class RawCorner:
    frame: str
    corner_id: int
    x: int
    y: int
    checker_contrast: float


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return image


def normalize_patch(patch: np.ndarray) -> np.ndarray:
    patch_f = patch.astype(np.float32)
    lo, hi = np.percentile(patch_f, [2, 98])
    scale = max(float(hi - lo), 1.0)
    return np.clip((patch_f - lo) / scale, 0.0, 1.0)


def quadrant_means(arr: np.ndarray, zone: tuple[int, int]) -> dict[str, float]:
    a, b = zone
    r = arr.shape[0] // 2
    return {
        "nw": float(arr[r - b : r - a, r - b : r - a].mean()),
        "ne": float(arr[r - b : r - a, r + a : r + b].mean()),
        "sw": float(arr[r + a : r + b, r - b : r - a].mean()),
        "se": float(arr[r + a : r + b, r + a : r + b].mean()),
    }


def checker_contrast(arr: np.ndarray) -> float:
    means = quadrant_means(arr, FAR_ZONE)
    diag_a = (means["nw"] + means["se"]) / 2.0
    diag_b = (means["ne"] + means["sw"]) / 2.0
    return abs(diag_a - diag_b)


def detect_raw_corners(raw_path: Path) -> list[RawCorner]:
    raw = read_gray(raw_path)
    height, width = raw.shape
    corners = cv2.goodFeaturesToTrack(
        raw,
        maxCorners=120,
        qualityLevel=0.01,
        minDistance=80,
        blockSize=9,
        useHarrisDetector=True,
        k=0.04,
    )
    if corners is None:
        return []

    candidates: list[tuple[float, int, int]] = []
    for x_f, y_f in corners.reshape(-1, 2):
        x = int(round(float(x_f)))
        y = int(round(float(y_f)))
        if not (PATCH_RADIUS < x < width - PATCH_RADIUS and PATCH_RADIUS < y < height - PATCH_RADIUS):
            continue
        patch = raw[y - PATCH_RADIUS : y + PATCH_RADIUS, x - PATCH_RADIUS : x + PATCH_RADIUS]
        contrast = checker_contrast(normalize_patch(patch))
        if contrast < CHECKER_CONTRAST_MIN:
            continue
        candidates.append((contrast, x, y))

    candidates.sort(reverse=True)
    selected = candidates[:MAX_CORNERS_PER_FRAME]
    return [
        RawCorner(raw_path.name, idx, x, y, float(contrast))
        for idx, (contrast, x, y) in enumerate(selected)
    ]


def harris_peak_metrics(arr: np.ndarray) -> tuple[float, float]:
    harris = cv2.cornerHarris(arr.astype(np.float32), blockSize=5, ksize=3, k=0.04)
    r = PATCH_RADIUS
    w = CENTRAL_HARRIS_RADIUS
    sub = harris[r - w : r + w + 1, r - w : r + w + 1]
    iy, ix = np.unravel_index(int(np.argmax(sub)), sub.shape)
    dx = float(ix - w)
    dy = float(iy - w)
    return math.sqrt(dx * dx + dy * dy), float(np.max(sub))


def gradient_metrics(arr: np.ndarray) -> tuple[float, float]:
    gx = cv2.Sobel(arr, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(arr, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(gx * gx + gy * gy)
    lap = cv2.Laplacian(arr, cv2.CV_32F)
    return float(np.percentile(grad, 95)), float(lap.var())


def analyze_corner_images() -> tuple[list[dict[str, object]], list[dict[str, object]], int, int]:
    raw_files = sorted((CASES_DIR / "raw_input").glob("*.bmp"))
    if not raw_files:
        raise FileNotFoundError(f"No raw BMP files found under {CASES_DIR / 'raw_input'}")

    rows: list[dict[str, object]] = []
    corner_records: list[RawCorner] = []
    for raw_path in raw_files:
        corner_records.extend(detect_raw_corners(raw_path))

    for corner in corner_records:
        raw_image = read_gray(CASES_DIR / "raw_input" / corner.frame)
        raw_patch = raw_image[
            corner.y - PATCH_RADIUS : corner.y + PATCH_RADIUS,
            corner.x - PATCH_RADIUS : corner.x + PATCH_RADIUS,
        ]
        raw_norm = normalize_patch(raw_patch)

        for case_name, case_label in CASES:
            image = read_gray(CASES_DIR / case_name / corner.frame)
            patch = image[
                corner.y - PATCH_RADIUS : corner.y + PATCH_RADIUS,
                corner.x - PATCH_RADIUS : corner.x + PATCH_RADIUS,
            ]
            patch_norm = normalize_patch(patch)
            peak_shift, harris_max = harris_peak_metrics(patch_norm)
            grad_p95, lap_var = gradient_metrics(patch_norm)
            mae_vs_raw = 0.0 if case_name == "raw_input" else float(np.mean(np.abs(patch_norm - raw_norm)))
            p95_absdiff_vs_raw = (
                0.0 if case_name == "raw_input" else float(np.percentile(np.abs(patch_norm - raw_norm), 95))
            )
            rows.append(
                {
                    "frame": corner.frame,
                    "corner_id": corner.corner_id,
                    "x": corner.x,
                    "y": corner.y,
                    "raw_checker_contrast": corner.checker_contrast,
                    "case": case_name,
                    "label": case_label,
                    "corner_peak_shift_px": peak_shift,
                    "harris_max": harris_max,
                    "gradient_p95": grad_p95,
                    "laplacian_var": lap_var,
                    "norm_mae_vs_raw": mae_vs_raw,
                    "norm_p95_absdiff_vs_raw": p95_absdiff_vs_raw,
                }
            )

    summaries: list[dict[str, object]] = []
    raw_rows = [row for row in rows if row["case"] == "raw_input"]
    raw_medians = {
        "corner_peak_shift_px": median(raw_rows, "corner_peak_shift_px"),
        "harris_max": median(raw_rows, "harris_max"),
        "gradient_p95": median(raw_rows, "gradient_p95"),
        "laplacian_var": median(raw_rows, "laplacian_var"),
    }

    for case_name, case_label in CASES:
        case_rows = [row for row in rows if row["case"] == case_name]
        summary = {
            "case": case_name,
            "label": case_label,
            "measurements": len(case_rows),
            "median_corner_peak_shift_px": median(case_rows, "corner_peak_shift_px"),
            "p75_corner_peak_shift_px": percentile(case_rows, "corner_peak_shift_px", 75),
            "pct_peak_shift_gt_5px": percentage(case_rows, "corner_peak_shift_px", lambda value: value > 5.0),
            "median_harris_max": median(case_rows, "harris_max"),
            "median_gradient_p95": median(case_rows, "gradient_p95"),
            "median_laplacian_var": median(case_rows, "laplacian_var"),
            "median_norm_mae_vs_raw": median(case_rows, "norm_mae_vs_raw"),
            "p75_norm_mae_vs_raw": percentile(case_rows, "norm_mae_vs_raw", 75),
            "median_norm_p95_absdiff_vs_raw": median(case_rows, "norm_p95_absdiff_vs_raw"),
        }
        summary["delta_peak_shift_vs_raw_median"] = (
            float(summary["median_corner_peak_shift_px"]) - raw_medians["corner_peak_shift_px"]
        )
        summary["delta_gradient_p95_vs_raw_median"] = (
            float(summary["median_gradient_p95"]) - raw_medians["gradient_p95"]
        )
        summary["delta_laplacian_var_vs_raw_median"] = (
            float(summary["median_laplacian_var"]) - raw_medians["laplacian_var"]
        )
        summary["harris_gain_vs_raw_median"] = safe_ratio(float(summary["median_harris_max"]), raw_medians["harris_max"])
        summaries.append(summary)

    return rows, summaries, len(raw_files), len(corner_records)


def median(rows: list[dict[str, object]], key: str) -> float:
    return float(np.median([float(row[key]) for row in rows])) if rows else float("nan")


def percentile(rows: list[dict[str, object]], key: str, pct: float) -> float:
    return float(np.percentile([float(row[key]) for row in rows], pct)) if rows else float("nan")


def percentage(rows: list[dict[str, object]], key: str, predicate) -> float:
    if not rows:
        return float("nan")
    hits = sum(1 for row in rows if predicate(float(row[key])))
    return 100.0 * hits / len(rows)


def safe_ratio(value: float, denom: float) -> float:
    if abs(denom) < 1e-12:
        return float("nan")
    return value / denom


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def analyze_training_coverage() -> list[dict[str, object]]:
    manifests = [
        ("R39 safe training", TRAINING_DATA_DIR / "r39_shape_generalization" / "r39_shape_mix_safe" / "manifest.json"),
        ("R39 strong package", TRAINING_DATA_DIR / "r39_shape_generalization" / "r39_shape_mix_strong" / "manifest.json"),
        ("R39 shape validation", TRAINING_DATA_DIR / "r39_shape_generalization" / "shape_val_unseen" / "manifest.json"),
        (
            "R40 training",
            TRAINING_DATA_DIR / "r40_microscopy_feature_coverage" / "r40_micro_capacity_train" / "manifest.json",
        ),
        (
            "R40 microscopy validation",
            TRAINING_DATA_DIR / "r40_microscopy_feature_coverage" / "micro_val_unseen" / "manifest.json",
        ),
        (
            "R46 corner-aware training",
            TRAINING_DATA_DIR
            / "r46_corner_aware_finetune"
            / "r46_checkboard_corner_train"
            / "manifest.json",
        ),
        (
            "R46 held-out corner validation",
            TRAINING_DATA_DIR
            / "r46_corner_aware_finetune"
            / "checkboard_corner_val_unseen"
            / "manifest.json",
        ),
    ]

    rows: list[dict[str, object]] = []
    for package_label, path in manifests:
        data = json.loads(path.read_text(encoding="utf-8"))
        counts = data.get("count_by_stage", {})
        total = int(data.get("total_pairs", 0))
        rectangle = int(counts.get("stage_03_rectangles", 0))
        micro_grid = int(counts.get("stage_29_micro_lines_grid", 0))
        checker_like = sum(
            int(value)
            for key, value in counts.items()
            if any(token in key.lower() for token in ["checker", "checkboard", "chessboard"])
        )
        rows.append(
            {
                "package": package_label,
                "total_pairs": total,
                "rectangle_pairs": rectangle,
                "rectangle_share_pct": 100.0 * rectangle / total if total else 0.0,
                "micro_grid_pairs": micro_grid,
                "micro_grid_share_pct": 100.0 * micro_grid / total if total else 0.0,
                "checkerboard_specific_pairs": checker_like,
                "checkerboard_specific_share_pct": 100.0 * checker_like / total if total else 0.0,
                "stage_count": len(counts),
            }
        )

    generated_stage_rows = []
    generated_root = TRAINING_DATA_DIR / "generated"
    if generated_root.exists():
        for stage in sorted(path for path in generated_root.iterdir() if path.is_dir()):
            count = len([p for p in stage.iterdir() if p.is_file()])
            generated_stage_rows.append(
                {
                    "package": f"Generated {stage.name}",
                    "total_pairs": count,
                    "rectangle_pairs": count if stage.name == "stage_03_rectangles" else 0,
                    "rectangle_share_pct": 100.0 if stage.name == "stage_03_rectangles" and count else 0.0,
                    "micro_grid_pairs": count if stage.name == "stage_29_micro_lines_grid" else 0,
                    "micro_grid_share_pct": 100.0 if stage.name == "stage_29_micro_lines_grid" and count else 0.0,
                    "checkerboard_specific_pairs": count
                    if any(token in stage.name.lower() for token in ["checker", "checkboard", "chessboard"])
                    else 0,
                    "checkerboard_specific_share_pct": 100.0
                    if any(token in stage.name.lower() for token in ["checker", "checkboard", "chessboard"]) and count
                    else 0.0,
                    "stage_count": 1,
                }
            )
    rows.extend(generated_stage_rows)

    keyword_hits = []
    for dirpath, dirnames, filenames in os.walk(TRAINING_DATA_DIR):
        names = list(dirnames) + list(filenames)
        for name in names:
            lower = name.lower()
            if any(token in lower for token in ["checker", "checkboard", "chessboard"]):
                keyword_hits.append(str(Path(dirpath) / name))
    rows.append(
        {
            "package": "Training_Data keyword audit",
            "total_pairs": len(keyword_hits),
            "rectangle_pairs": 0,
            "rectangle_share_pct": 0.0,
            "micro_grid_pairs": 0,
            "micro_grid_share_pct": 0.0,
            "checkerboard_specific_pairs": len(keyword_hits),
            "checkerboard_specific_share_pct": 100.0 if keyword_hits else 0.0,
            "stage_count": 0,
        }
    )
    return rows


def make_corner_contact_sheet(rows: list[dict[str, object]]) -> None:
    sample_scores: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in rows:
        if row["case"] == "raw_input":
            continue
        sample_scores[(str(row["frame"]), int(row["corner_id"]))].append(float(row["corner_peak_shift_px"]))

    lookup = {(str(row["frame"]), int(row["corner_id"]), str(row["case"])): row for row in rows}
    selected = sorted(
        sample_scores.items(),
        key=lambda item: (float(np.mean(item[1])), max(item[1])),
        reverse=True,
    )[:10]
    if not selected:
        return

    scale = 3
    crop_size = PATCH_RADIUS * 2
    cell_w = crop_size * scale
    label_h = 64
    row_h = label_h + cell_w
    sheet = Image.new("RGB", (cell_w * len(CASES), row_h * len(selected)), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)

    for row_idx, ((frame, corner_id), _) in enumerate(selected):
        raw_row = lookup[(frame, corner_id, "raw_input")]
        x = int(raw_row["x"])
        y = int(raw_row["y"])
        for col_idx, (case_name, case_label) in enumerate(CASES):
            image = read_gray(CASES_DIR / case_name / frame)
            crop = image[y - PATCH_RADIUS : y + PATCH_RADIUS, x - PATCH_RADIUS : x + PATCH_RADIUS]
            rgb = cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)
            rgb = cv2.resize(rgb, (cell_w, cell_w), interpolation=cv2.INTER_NEAREST)
            cv2.drawMarker(
                rgb,
                (PATCH_RADIUS * scale, PATCH_RADIUS * scale),
                (255, 0, 0),
                markerType=cv2.MARKER_CROSS,
                markerSize=28,
                thickness=2,
            )
            xoff = col_idx * cell_w
            yoff = row_idx * row_h
            sheet.paste(Image.fromarray(rgb), (xoff, yoff + label_h))
            metrics = lookup[(frame, corner_id, case_name)]
            draw.text((xoff + 6, yoff + 4), case_label, fill=(0, 0, 0))
            draw.text(
                (xoff + 6, yoff + 24),
                f"shift {float(metrics['corner_peak_shift_px']):.2f}px",
                fill=(0, 0, 0),
            )
            if col_idx == 0:
                draw.text((xoff + 6, yoff + 44), frame.replace("Image__", ""), fill=(0, 0, 0))

    sheet.save(OUTPUT_DIR / "corner_patch_contact_sheet.png")


def make_summary_plot(summaries: list[dict[str, object]]) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return

    labels = [str(row["label"]).replace("Lab ", "") for row in summaries]
    shift = [float(row["median_corner_peak_shift_px"]) for row in summaries]
    mae = [float(row["median_norm_mae_vs_raw"]) for row in summaries]
    grad = [float(row["median_gradient_p95"]) for row in summaries]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    axes[0].bar(labels, shift)
    axes[0].set_title("Median corner peak shift")
    axes[0].set_ylabel("px")
    axes[1].bar(labels, mae)
    axes[1].set_title("Median local change vs raw")
    axes[2].bar(labels, grad)
    axes[2].set_title("Median edge strength")
    for ax in axes:
        ax.tick_params(axis="x", rotation=35)
        ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "corner_metric_summary.png", dpi=160)
    plt.close(fig)


def fmt(value: object, digits: int = 3) -> str:
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def render_report(
    summaries: list[dict[str, object]],
    coverage_rows: list[dict[str, object]],
    frame_count: int,
    raw_corner_count: int,
) -> str:
    package_rows = [row for row in coverage_rows if not str(row["package"]).startswith("Generated ")]
    r39_safe = next(row for row in package_rows if row["package"] == "R39 safe training")
    r40_train = next(row for row in package_rows if row["package"] == "R40 training")
    r46_train = next(row for row in package_rows if row["package"] == "R46 corner-aware training")
    r46_val = next(row for row in package_rows if row["package"] == "R46 held-out corner validation")
    keyword_audit = next(row for row in package_rows if row["package"] == "Training_Data keyword audit")

    lines = [
        "# Lab R46 Checkboard Corner Geometry Validation - 2026-06-12",
        "",
        "## Question",
        "",
        "Does the LabSystem reconstruction preserve real checkboard corners, or does it reshape hard right angles in a way that can explain the weak GMF improvement?",
        "",
        "## Completion Criteria",
        "",
        "- Check more than one frame and more than one corner.",
        "- Compare raw input with R39/R40 latest and tradeoff outputs plus the first R46 candidates.",
        "- Separate corner-geometry evidence from the external GMF score.",
        "- Audit whether the current Lab training packages contain direct checkboard/corner coverage.",
        "",
        "## Image Evidence Scope",
        "",
        f"- Frames checked: {frame_count}",
        f"- Raw checker corners accepted by the detector: {raw_corner_count}",
        f"- Case measurements: {raw_corner_count * len(CASES)}",
        "- Corner detector: raw-image Harris/good-features points filtered for checker-like diagonal contrast.",
        "- Geometry check: compare where the strongest corner response lands inside the same local patch.",
        "",
        "## Corner Geometry Result",
        "",
        "| Case | Median corner-response shift (px) | P75 shift (px) | Corners > 5 px shift | Median local change vs raw | Median edge strength | Harris gain vs raw |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["label"]),
                    fmt(row["median_corner_peak_shift_px"]),
                    fmt(row["p75_corner_peak_shift_px"]),
                    fmt(row["pct_peak_shift_gt_5px"]) + "%",
                    fmt(row["median_norm_mae_vs_raw"]),
                    fmt(row["median_gradient_p95"]),
                    fmt(row["harris_gain_vs_raw_median"], 1) + "x",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "Interpretation:",
            "",
            "- The reconstruction outputs do not merely blur or sharpen the raw image. The key question is whether they move the strongest local corner response away from the raw corner location.",
            "- R46 should be judged against both the raw input and the earlier R39/R40 cases. A useful R46 candidate should reduce the corner-response shift without creating a larger local change from raw.",
            "- In this run, R46 tradeoff and R46 detail tie R40 tradeoff on median shift, but they have many more corners above 5 px shift and a larger local change from raw. R46 latest is worse.",
            "- Stronger-looking edges are not enough. The preferred model must preserve square-corner geometry on this real checkboard sequence.",
            "",
            "## Training Coverage Audit",
            "",
            "| Package | Total pairs | Rectangle pairs | Rectangle share | Micro-grid pairs | Micro-grid share | Checkboard-specific pairs |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in package_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["package"]),
                    str(row["total_pairs"]),
                    str(row["rectangle_pairs"]),
                    fmt(row["rectangle_share_pct"]) + "%",
                    str(row["micro_grid_pairs"]),
                    fmt(row["micro_grid_share_pct"]) + "%",
                    str(row["checkerboard_specific_pairs"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "Coverage interpretation:",
            "",
            f"- R39 safe training uses only {r39_safe['rectangle_pairs']} rectangle pairs out of {r39_safe['total_pairs']} pairs.",
            f"- R40 training uses {r40_train['rectangle_pairs']} rectangle pairs and {r40_train['micro_grid_pairs']} micro-grid pairs out of {r40_train['total_pairs']} pairs.",
            f"- R46 training adds {r46_train['checkerboard_specific_pairs']} synthetic checkboard/corner pairs out of {r46_train['total_pairs']} pairs.",
            f"- R46 held-out validation adds {r46_val['checkerboard_specific_pairs']} synthetic checkboard/corner pairs.",
            f"- Training_Data keyword audit found {keyword_audit['checkerboard_specific_pairs']} checker/checkboard/chessboard-specific paths.",
            "- The new R46 validation set is still synthetic. It is not a real captured Lab checkboard-corner validation set.",
            "",
            "## Root-Cause Assessment",
            "",
            "High confidence: the weak checkboard result is not explained only by the shared abnormal displacement interval.",
            "",
            "The stronger explanation is a remaining target-domain mismatch:",
            "",
            "- R46 was explicitly trained on synthetic checkboard/corner data, but that did not transfer cleanly to the real Lab checkboard capture.",
            "- The model learned to create stronger-looking edges, but not to preserve the exact square-corner geometry needed by this sample.",
            "- The checkpoint choice can therefore look acceptable on synthetic validation while still damaging real captured checkboard corners.",
            "",
            "Medium confidence: the Lab PSF may contribute to the artifact, because an imperfect blur model can teach the model the wrong edge compensation.",
            "",
            "Lower confidence: a basic inference/package mistake, because all cases have matching filenames and frame counts and the distortion repeats systematically.",
            "",
            "## Recommended Next Evidence",
            "",
            "1. Do not treat this R46 run as solving the rounded-corner problem.",
            "2. If an external GMF check is still desired, send R46 tradeoff first because it is the least-bad R46 candidate here.",
            "3. Keep raw input as the reference case and keep R39/R40 as historical controls.",
            "4. Revise the corner/checkboard training package before longer training.",
            "",
            "## Generated Files",
            "",
            f"- Corner metrics table: `{OUTPUT_DIR / 'corner_metrics_per_measurement.csv'}`",
            f"- Corner summary table: `{OUTPUT_DIR / 'corner_metrics_summary.csv'}`",
            f"- Training coverage table: `{OUTPUT_DIR / 'training_data_coverage_summary.csv'}`",
            f"- Visual corner sheet: `{OUTPUT_DIR / 'corner_patch_contact_sheet.png'}`",
            f"- Metric chart: `{OUTPUT_DIR / 'corner_metric_summary.png'}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows, summaries, frame_count, raw_corner_count = analyze_corner_images()
    coverage_rows = analyze_training_coverage()

    write_csv(OUTPUT_DIR / "corner_metrics_per_measurement.csv", rows)
    write_csv(OUTPUT_DIR / "corner_metrics_summary.csv", summaries)
    write_csv(OUTPUT_DIR / "training_data_coverage_summary.csv", coverage_rows)

    summary_payload = {
        "frames_checked": frame_count,
        "raw_corners_checked": raw_corner_count,
        "case_count": len(CASES),
        "summaries": summaries,
        "training_coverage": coverage_rows,
    }
    (OUTPUT_DIR / "corner_validation_summary.json").write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    make_corner_contact_sheet(rows)
    make_summary_plot(summaries)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(summaries, coverage_rows, frame_count, raw_corner_count), encoding="utf-8")

    print(f"frames_checked={frame_count}")
    print(f"raw_corners_checked={raw_corner_count}")
    for row in summaries:
        print(
            f"{row['label']}: median_shift={fmt(row['median_corner_peak_shift_px'])} px, "
            f"pct_gt5={fmt(row['pct_peak_shift_gt_5px'])}%, mae={fmt(row['median_norm_mae_vs_raw'])}"
        )
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
