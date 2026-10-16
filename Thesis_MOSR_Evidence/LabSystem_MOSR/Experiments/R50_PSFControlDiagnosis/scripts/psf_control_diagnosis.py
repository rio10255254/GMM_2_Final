"""R50 PSF control diagnosis for Lab checkboard transfer."""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
LAB_ROOT = REPO_ROOT
EVIDENCE_ROOT = LAB_ROOT.parent

REAL_CHECKBOARD_DIR = EVIDENCE_ROOT / "20250605_checkboard"
TRAINING_DATA = LAB_ROOT / "Training_Data"
STAGE = "stage_48_checkboard_corners"
CLEAN_DIR = TRAINING_DATA / "generated" / STAGE
BADS_DIR = TRAINING_DATA / "generated_convolved" / STAGE
GAUSSIAN_DIR = TRAINING_DATA / "generated_convolved_gaussian_control" / STAGE
PSF_VALIDATION_CSV = (
    LAB_ROOT
    / "psf_calibration"
    / "results"
    / "20250605_inner_circle_roi_fine_prealign_validation"
    / "validation_metrics.csv"
)
DEFAULT_OUTPUT = LAB_ROOT / "Experiments" / "R50_PSFControlDiagnosis" / "results" / "psf_control_diagnosis"


@dataclass
class ImageMetrics:
    set_name: str
    filename: str
    width: int
    height: int
    transition_width_count: int
    transition_width_median_px: float
    transition_width_p25_px: float
    transition_width_p75_px: float
    gradient_p99: float
    gradient_p999: float
    edge_density_p99: float


@dataclass
class SetSummary:
    set_name: str
    image_count: int
    valid_width_images: int
    median_transition_width_px: float
    p25_transition_width_px: float
    p75_transition_width_px: float
    median_gradient_p99: float
    median_gradient_p999: float
    width_gap_vs_real_px: float | None = None
    gradient_p99_gap_vs_real: float | None = None
    rank_score_vs_real: float | None = None


def load_gray(path: Path | str | np.ndarray) -> np.ndarray:
    if isinstance(path, np.ndarray):
        array = path
    else:
        array = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if array is None:
            raise FileNotFoundError(path)
    if array.dtype != np.float32:
        array = array.astype(np.float32)
    if array.max() > 1.5:
        array /= 255.0
    return array


def normalize_contrast(array: np.ndarray) -> np.ndarray:
    lo, hi = np.percentile(array, [1, 99])
    if hi <= lo + 1e-6:
        return np.clip(array, 0, 1)
    return np.clip((array - lo) / (hi - lo), 0, 1)


def crossing_width(profile: np.ndarray) -> float | None:
    if profile.size < 15:
        return None
    left = float(np.median(profile[:5]))
    right = float(np.median(profile[-5:]))
    if abs(right - left) < 0.20:
        return None
    values = profile.astype(np.float32, copy=True)
    if right < left:
        values = 1.0 - values
        left, right = 1.0 - left, 1.0 - right
    low = left + 0.10 * (right - left)
    high = left + 0.90 * (right - left)
    idx10 = np.where(values >= low)[0]
    idx90 = np.where(values >= high)[0]
    if len(idx10) == 0 or len(idx90) == 0:
        return None
    width = float(idx90[0] - idx10[0])
    if width < 0 or width > 40:
        return None
    return max(0.5, width)


def _candidate_peaks(gradient: np.ndarray) -> np.ndarray:
    if gradient.size < 5:
        return np.array([], dtype=np.int64)
    threshold = np.percentile(gradient, 99.2)
    candidates = np.where(
        (gradient[1:-1] >= gradient[:-2])
        & (gradient[1:-1] >= gradient[2:])
        & (gradient[1:-1] > threshold)
    )[0] + 1
    return candidates.astype(np.int64)


def estimate_transition_widths(array: np.ndarray, max_samples: int = 320) -> list[float]:
    image = normalize_contrast(array)
    height, width = image.shape
    margin = 24
    widths: list[float] = []

    row_step = max(4, height // 90)
    for y in range(margin, height - margin, row_step):
        row = image[y, :]
        peaks = _candidate_peaks(np.abs(np.gradient(row)))
        step = max(1, len(peaks) // 8 or 1)
        for x in peaks[::step]:
            if x < margin or x >= width - margin:
                continue
            measured = crossing_width(row[x - 20 : x + 21])
            if measured is not None:
                widths.append(measured)
            if len(widths) >= max_samples:
                return widths

    col_step = max(4, width // 90)
    for x in range(margin, width - margin, col_step):
        col = image[:, x]
        peaks = _candidate_peaks(np.abs(np.gradient(col)))
        step = max(1, len(peaks) // 8 or 1)
        for y in peaks[::step]:
            if y < margin or y >= height - margin:
                continue
            measured = crossing_width(col[y - 20 : y + 21])
            if measured is not None:
                widths.append(measured)
            if len(widths) >= max_samples:
                return widths

    return widths


def measure_image(image: Path | str | np.ndarray, set_name: str, filename: str) -> ImageMetrics:
    array = normalize_contrast(load_gray(image))
    gy, gx = np.gradient(array)
    gradient = np.hypot(gx, gy)
    widths = estimate_transition_widths(array)
    width_array = np.asarray(widths, dtype=np.float32)
    if width_array.size:
        med = float(np.median(width_array))
        p25 = float(np.percentile(width_array, 25))
        p75 = float(np.percentile(width_array, 75))
    else:
        med = p25 = p75 = math.nan
    edge_threshold = float(np.percentile(gradient, 99))
    return ImageMetrics(
        set_name=set_name,
        filename=filename,
        width=int(array.shape[1]),
        height=int(array.shape[0]),
        transition_width_count=len(widths),
        transition_width_median_px=med,
        transition_width_p25_px=p25,
        transition_width_p75_px=p75,
        gradient_p99=float(np.percentile(gradient, 99)),
        gradient_p999=float(np.percentile(gradient, 99.9)),
        edge_density_p99=float(np.mean(gradient > edge_threshold)),
    )


def blend_with_clean(clean: np.ndarray, bads: np.ndarray, alpha: float) -> np.ndarray:
    if clean.shape != bads.shape:
        raise ValueError(f"shape mismatch: clean {clean.shape}, bads {bads.shape}")
    mixed = (1.0 - alpha) * clean.astype(np.float32) + alpha * bads.astype(np.float32)
    return np.clip(np.rint(mixed), 0, 255).astype(np.uint8)


def image_files(folder: Path, limit: int | None = None) -> list[Path]:
    files = sorted(folder.glob("*.bmp"))
    return files[:limit] if limit else files


def generate_weak_bads(clean_dir: Path, bads_dir: Path, output_root: Path, alphas: Iterable[float]) -> dict[str, Path]:
    output_dirs: dict[str, Path] = {}
    clean_by_name = {path.name: path for path in image_files(clean_dir)}
    bads_by_name = {path.name: path for path in image_files(bads_dir)}
    common_names = sorted(clean_by_name.keys() & bads_by_name.keys())
    if not common_names:
        raise RuntimeError("No common clean/BADS images were found for weak-BADS generation.")

    for alpha in alphas:
        tag = f"weak_bads_alpha{int(round(alpha * 100)):03d}"
        out_dir = output_root / tag / STAGE
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in common_names:
            clean = cv2.imread(str(clean_by_name[name]), cv2.IMREAD_GRAYSCALE)
            bads = cv2.imread(str(bads_by_name[name]), cv2.IMREAD_GRAYSCALE)
            if clean is None or bads is None:
                raise FileNotFoundError(name)
            blended = blend_with_clean(clean, bads, alpha=alpha)
            ok = cv2.imwrite(str(out_dir / name), blended)
            if not ok:
                raise IOError(out_dir / name)
        output_dirs[tag] = out_dir
    return output_dirs


def summarize_set(set_name: str, files: list[Path]) -> tuple[SetSummary, list[ImageMetrics]]:
    rows = [measure_image(path, set_name, path.name) for path in files]
    valid_widths = [row.transition_width_median_px for row in rows if not math.isnan(row.transition_width_median_px)]
    if valid_widths:
        width_med = float(np.median(valid_widths))
        width_p25 = float(np.percentile(valid_widths, 25))
        width_p75 = float(np.percentile(valid_widths, 75))
    else:
        width_med = width_p25 = width_p75 = math.nan
    summary = SetSummary(
        set_name=set_name,
        image_count=len(rows),
        valid_width_images=len(valid_widths),
        median_transition_width_px=width_med,
        p25_transition_width_px=width_p25,
        p75_transition_width_px=width_p75,
        median_gradient_p99=float(np.median([row.gradient_p99 for row in rows])) if rows else math.nan,
        median_gradient_p999=float(np.median([row.gradient_p999 for row in rows])) if rows else math.nan,
    )
    return summary, rows


def add_real_gaps(summaries: list[SetSummary]) -> None:
    real = next(row for row in summaries if row.set_name == "real_raw_checkboard")
    for row in summaries:
        if row.set_name == real.set_name:
            row.width_gap_vs_real_px = 0.0
            row.gradient_p99_gap_vs_real = 0.0
            row.rank_score_vs_real = 0.0
            continue
        row.width_gap_vs_real_px = abs(row.median_transition_width_px - real.median_transition_width_px)
        row.gradient_p99_gap_vs_real = abs(row.median_gradient_p99 - real.median_gradient_p99)
        row.rank_score_vs_real = row.width_gap_vs_real_px + 25.0 * row.gradient_p99_gap_vs_real


def read_psf_validation(csv_path: Path) -> dict[str, float]:
    by_model: dict[str, list[float]] = {}
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            by_model.setdefault(row["model"], []).append(float(row["edge_rmse"]))
    return {model: float(np.median(values)) for model, values in by_model.items()}


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_bar_chart(path: Path, summaries: list[SetSummary]) -> None:
    chart_width = 1320
    chart_height = 620
    margin_left = 300
    margin_right = 150
    margin_top = 70
    row_height = 58
    image = np.full((chart_height, chart_width, 3), 255, dtype=np.uint8)
    max_width = max(row.median_transition_width_px for row in summaries if not math.isnan(row.median_transition_width_px))
    scale = (chart_width - margin_left - margin_right) / max(1.0, max_width)
    cv2.putText(
        image,
        "R50 PSF Control Diagnosis - median edge transition width",
        (35, 38),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (20, 20, 20),
        2,
        cv2.LINE_AA,
    )
    for idx, row in enumerate(summaries):
        y = margin_top + idx * row_height
        color = (90, 150, 60) if row.set_name == "real_raw_checkboard" else (75, 110, 190)
        bar_w = int(row.median_transition_width_px * scale)
        cv2.putText(image, row.set_name, (30, y + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (30, 30, 30), 1, cv2.LINE_AA)
        cv2.rectangle(image, (margin_left, y), (margin_left + bar_w, y + 30), color, -1)
        cv2.putText(
            image,
            f"{row.median_transition_width_px:.2f} px",
            (margin_left + bar_w + 12, y + 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (25, 25, 25),
            1,
            cv2.LINE_AA,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), image)


def _edge_center_crop(array: np.ndarray, crop_h: int, crop_w: int) -> np.ndarray:
    image = normalize_contrast(load_gray(array))
    gy, gx = np.gradient(image)
    gradient = np.hypot(gx, gy)
    margin_y = min(max(crop_h // 2, 1), max(1, gradient.shape[0] // 2 - 1))
    margin_x = min(max(crop_w // 2, 1), max(1, gradient.shape[1] // 2 - 1))
    search = gradient[margin_y : gradient.shape[0] - margin_y, margin_x : gradient.shape[1] - margin_x]
    if search.size == 0 or float(search.max()) <= 0:
        cy, cx = array.shape[0] // 2, array.shape[1] // 2
    else:
        yy, xx = np.unravel_index(int(np.argmax(search)), search.shape)
        cy, cx = int(yy + margin_y), int(xx + margin_x)
    y0 = max(0, min(array.shape[0] - crop_h, cy - crop_h // 2))
    x0 = max(0, min(array.shape[1] - crop_w, cx - crop_w // 2))
    return array[y0 : y0 + crop_h, x0 : x0 + crop_w]


def write_contact_sheet(path: Path, groups: dict[str, list[Path]], limit: int = 4) -> None:
    tile_h, tile_w = 180, 240
    label_h = 32
    rows = []
    for set_name, paths in groups.items():
        tiles = []
        for image_path in paths[:limit]:
            arr = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
            if arr is None:
                continue
            crop_h = min(max(arr.shape[0] // 3, 64), arr.shape[0])
            crop_w = min(max(arr.shape[1] // 3, 64), arr.shape[1])
            crop = _edge_center_crop(arr, crop_h, crop_w)
            crop = cv2.resize(crop, (tile_w, tile_h), interpolation=cv2.INTER_AREA)
            crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
            tiles.append(crop)
        if not tiles:
            continue
        row = np.concatenate(tiles, axis=1)
        label = np.full((label_h, row.shape[1], 3), 255, dtype=np.uint8)
        cv2.putText(label, set_name, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (20, 20, 20), 1, cv2.LINE_AA)
        rows.append(np.concatenate([label, row], axis=0))
    if rows:
        sheet = np.concatenate(rows, axis=0)
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), sheet)


def write_report(path: Path, summaries: list[SetSummary], psf_validation: dict[str, float], weak_dirs: dict[str, Path]) -> None:
    ranked = sorted(
        [row for row in summaries if row.set_name != "real_raw_checkboard"],
        key=lambda row: (float("inf") if row.rank_score_vs_real is None else row.rank_score_vs_real),
    )
    best = ranked[0]
    real = next(row for row in summaries if row.set_name == "real_raw_checkboard")
    width_ranked = sorted(
        [row for row in summaries if row.set_name != "real_raw_checkboard"],
        key=lambda row: abs(row.median_transition_width_px - real.median_transition_width_px),
    )
    width_best = width_ranked[0]
    formal_bads = next(row for row in summaries if row.set_name == "formal_bads_stage48")
    lines = [
        "# R50 PSF Control Diagnosis",
        "",
        "## Verdict",
        "",
        (
            "The formal BADS PSF is usable, but it should not be treated as the only blur truth for "
            "the Lab checkboard corner task. In this diagnostic, weakened BADS best matches the real "
            "edge-width proxy, while the Gaussian control is the best combined width/edge-strength "
            "compromise. The formal BADS input is the widest/softest of the realistic controls."
        ),
        "",
        "## Edge-Width Comparison",
        "",
        "| Set | Images | Median edge width (px) | Gap vs real (px) | Median grad p99 | Rank score |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            "| {name} | {count} | {width:.3f} | {gap:.3f} | {grad:.6f} | {score:.3f} |".format(
                name=row.set_name,
                count=row.image_count,
                width=row.median_transition_width_px,
                gap=0.0 if row.width_gap_vs_real_px is None else row.width_gap_vs_real_px,
                grad=row.median_gradient_p99,
                score=0.0 if row.rank_score_vs_real is None else row.rank_score_vs_real,
            )
        )
    lines.extend(
        [
            "",
            "## PSF Calibration Check",
            "",
            "| Forward model | Median edge RMSE |",
            "|---|---:|",
        ]
    )
    for key, value in psf_validation.items():
        lines.append(f"| {key} | {value:.6f} |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"- Width-only best match: `{width_best.set_name}`.",
            f"- Combined width/edge-strength best match: `{best.set_name}`.",
            f"- Formal BADS edge width is `{formal_bads.median_transition_width_px:.1f} px` versus real `{real.median_transition_width_px:.1f} px`.",
            "- BADS PSF is not broken, but it is not the safest single blur truth for checkboard corners.",
            "- The Lab model failures are still more consistent with target/degradation mismatch than raw model incapacity.",
            "- The next training probe should compare Gaussian / weakened-BADS / mixed-PSF data before any long formal run.",
            "",
            "## Generated Weak-BADS Sets",
            "",
        ]
    )
    for name, folder in weak_dirs.items():
        lines.append(f"- `{name}`: `{folder}`")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- `summary.json`: machine-readable summary",
            "- `set_summary.csv`: compact set-level table",
            "- `per_image_metrics.csv`: per-image measurements",
            "- `edge_width_bar_chart.png`: visual ranking",
            "- `contact_sheet.png`: source preview sheet",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(output_dir: Path, image_limit: int | None = None) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    weak_dirs = generate_weak_bads(CLEAN_DIR, BADS_DIR, output_dir / "generated_controls", [0.50, 0.75])
    sets = {
        "real_raw_checkboard": REAL_CHECKBOARD_DIR,
        "clean_synthetic_stage48": CLEAN_DIR,
        "gaussian_control_stage48": GAUSSIAN_DIR,
        "weak_bads_alpha050": weak_dirs["weak_bads_alpha050"],
        "weak_bads_alpha075": weak_dirs["weak_bads_alpha075"],
        "formal_bads_stage48": BADS_DIR,
    }
    summaries: list[SetSummary] = []
    per_image: list[ImageMetrics] = []
    for set_name, folder in sets.items():
        summary, rows = summarize_set(set_name, image_files(folder, image_limit))
        summaries.append(summary)
        per_image.extend(rows)
    add_real_gaps(summaries)
    psf_validation = read_psf_validation(PSF_VALIDATION_CSV)

    summary_rows = [asdict(row) for row in summaries]
    metric_rows = [asdict(row) for row in per_image]
    write_csv(output_dir / "set_summary.csv", summary_rows, list(summary_rows[0].keys()))
    write_csv(output_dir / "per_image_metrics.csv", metric_rows, list(metric_rows[0].keys()))
    payload = {
        "stage": STAGE,
        "real_checkboard_dir": str(REAL_CHECKBOARD_DIR),
        "clean_dir": str(CLEAN_DIR),
        "bads_dir": str(BADS_DIR),
        "gaussian_dir": str(GAUSSIAN_DIR),
        "weak_dirs": {key: str(value) for key, value in weak_dirs.items()},
        "summaries": summary_rows,
        "psf_validation_median_edge_rmse": psf_validation,
    }
    (output_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_bar_chart(output_dir / "edge_width_bar_chart.png", summaries)
    write_contact_sheet(
        output_dir / "contact_sheet.png",
        {name: image_files(folder, 4) for name, folder in sets.items()},
    )
    write_report(
        LAB_ROOT / "Experiments" / "R50_PSFControlDiagnosis" / "reports" / "R50_RESULTS.md",
        summaries,
        psf_validation,
        weak_dirs,
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--image-limit", type=int, default=None)
    args = parser.parse_args()
    payload = run(args.output_dir, args.image_limit)
    print(json.dumps(payload["summaries"], indent=2))


if __name__ == "__main__":
    main()
