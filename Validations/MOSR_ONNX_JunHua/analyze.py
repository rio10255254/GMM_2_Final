from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
SOURCE = Path(r"D:\NTU_ImageDataset\Pitch1um_Y_100\Cropped_Output")
OLD_PACKAGE = Path(
    r"D:\NTU_ImageDataset\Pitch1um_Y_100\external_gmf_r61_v16_psfoff_20260627"
)
RAW = OLD_PACKAGE / "00_raw_input" / "bmp"
R61 = OLD_PACKAGE / "01_r61_v16_best_tradeoff_psfoff" / "bmp"
MOSR = ROOT / "reconstruction"
DEFAULT_TILES = ROOT / "reconstruction_default_tiles"
DELIVERY = Path(r"D:\GMM_2_Final\Deliverables\MOSR_ONNX")
GMF_ROOT = ROOT / "external_gmf"
RESULTS = ROOT / "results"

EXPECTED_FRAMES = 202
EXPECTED_POSITIONS = 101
EXPECTED_STEPS = 100
EXPECTED_DY_PX = -8.0
OBJECT_UM_PER_PX = 0.125
LOCAL_SCALE = 0.5


def bmp_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("*.bmp") if p.is_file())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"Cannot read image: {path}")
    return image


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise OSError(f"Cannot encode image: {path}")
    encoded.tofile(path)


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def stats(values: list[float]) -> dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std_sample": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "p95": float(np.percentile(arr, 95)),
    }


def validate_case(folder: Path, expected_names: list[str]) -> dict[str, object]:
    files = bmp_files(folder)
    names = [p.name for p in files]
    shapes: set[tuple[int, int]] = set()
    dtypes: set[str] = set()
    for path in files:
        image = read_gray(path)
        shapes.add(tuple(int(v) for v in image.shape))
        dtypes.add(str(image.dtype))
    return {
        "folder": str(folder),
        "count": len(files),
        "names_exact": names == expected_names,
        "first": names[0] if names else None,
        "last": names[-1] if names else None,
        "shapes": [list(v) for v in sorted(shapes)],
        "dtypes": sorted(dtypes),
    }


def compare_source_to_raw(source_files: list[Path], raw_files: list[Path]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for source, raw in zip(source_files, raw_files, strict=True):
        source_hash = sha256(source)
        raw_hash = sha256(raw)
        rows.append(
            {
                "filename": source.name,
                "source_sha256": source_hash,
                "old_raw_sha256": raw_hash,
                "exact_match": source_hash == raw_hash,
            }
        )
    return {
        "all_exact": all(bool(row["exact_match"]) for row in rows),
        "checked": len(rows),
        "files": rows,
    }


def ring_center(image: np.ndarray) -> tuple[float, float]:
    threshold = float(np.percentile(image, 94))
    mask = (image >= threshold).astype(np.uint8)
    count, _, statistics, centroids = cv2.connectedComponentsWithStats(mask, 8)
    candidates: list[tuple[int, int]] = []
    for label in range(1, count):
        area = int(statistics[label, cv2.CC_STAT_AREA])
        width = int(statistics[label, cv2.CC_STAT_WIDTH])
        height = int(statistics[label, cv2.CC_STAT_HEIGHT])
        if area > 500 and width > 100 and height > 100:
            candidates.append((area, label))
    if not candidates:
        raise ValueError("Could not isolate the bright ring")
    label = max(candidates)[1]
    return float(centroids[label][0]), float(centroids[label][1])


def centered_crop(image: np.ndarray, center: tuple[float, float], size: int = 1400) -> np.ndarray:
    x, y = center
    half = size // 2
    left = int(round(x - half))
    top = int(round(y - half))
    pad = size
    padded = cv2.copyMakeBorder(image, pad, pad, pad, pad, cv2.BORDER_REFLECT_101)
    return padded[top + pad : top + pad + size, left + pad : left + pad + size]


def ring_representation(
    image: np.ndarray,
    center_override: tuple[float, float] | None = None,
) -> tuple[tuple[float, float], np.ndarray]:
    center = ring_center(image) if center_override is None else center_override
    crop = centered_crop(image.astype(np.float32), center)
    small = cv2.resize(
        crop,
        None,
        fx=LOCAL_SCALE,
        fy=LOCAL_SCALE,
        interpolation=cv2.INTER_AREA,
    )
    blur = cv2.GaussianBlur(small, (0, 0), 1.0)
    gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(gx, gy)
    yy, xx = np.indices(magnitude.shape)
    radius = np.hypot(xx - magnitude.shape[1] / 2.0, yy - magnitude.shape[0] / 2.0)
    annulus = ((radius > 175.0) & (radius < 325.0)).astype(np.float32)
    magnitude *= annulus
    magnitude -= float(np.mean(magnitude))
    std = float(np.std(magnitude))
    if std > 1e-6:
        magnitude /= std
    return center, magnitude


def representation_shift(
    a: tuple[tuple[float, float], np.ndarray],
    b: tuple[tuple[float, float], np.ndarray],
) -> dict[str, float]:
    center_a, edge_a = a
    center_b, edge_b = b
    if edge_a.shape != edge_b.shape:
        raise ValueError(f"Shape mismatch: {edge_a.shape} vs {edge_b.shape}")
    (residual_dx, residual_dy), response = cv2.phaseCorrelate(edge_a, edge_b)
    dx = (center_b[0] - center_a[0]) + residual_dx / LOCAL_SCALE
    dy = (center_b[1] - center_a[1]) + residual_dy / LOCAL_SCALE
    return {"dx_px": float(dx), "dy_px": float(dy), "response": float(response)}


def phase_shift(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    if a.shape != b.shape:
        raise ValueError(f"Shape mismatch: {a.shape} vs {b.shape}")
    (dx, dy), response = cv2.phaseCorrelate(a, b)
    return {
        "dx_px": float(dx / LOCAL_SCALE),
        "dy_px": float(dy / LOCAL_SCALE),
        "response": float(response),
    }


def local_motion(case_id: str, folder: Path) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    files = bmp_files(folder)
    reference_files = bmp_files(RAW)
    if len(files) != EXPECTED_FRAMES:
        raise ValueError(f"{case_id}: expected {EXPECTED_FRAMES} frames, found {len(files)}")

    repeat_rows: list[dict[str, object]] = []
    step_rows: list[dict[str, object]] = []
    previous_position: tuple[tuple[float, float], np.ndarray] | None = None
    for position in range(EXPECTED_POSITIONS):
        first_index = position * 2
        image0 = read_gray(files[first_index])
        image1 = read_gray(files[first_index + 1])
        reference0 = read_gray(reference_files[first_index])
        reference1 = read_gray(reference_files[first_index + 1])
        reference_mean = np.rint(
            (reference0.astype(np.float32) + reference1.astype(np.float32)) / 2.0
        ).astype(np.uint8)
        reference_center = ring_center(reference_mean)
        rep0 = ring_representation(image0, reference_center)
        rep1 = ring_representation(image1, reference_center)
        repeat = representation_shift(rep0, rep1)
        repeat_rows.append(
            {
                "case": case_id,
                "position": position,
                "shot0": files[first_index].name,
                "shot1": files[first_index + 1].name,
                **repeat,
                "distance_px": float(math.hypot(repeat["dx_px"], repeat["dy_px"])),
            }
        )
        mean_image = np.rint(
            (image0.astype(np.float32) + image1.astype(np.float32)) / 2.0
        ).astype(np.uint8)
        position_representation = ring_representation(mean_image, reference_center)
        if previous_position is not None:
            shift = representation_shift(previous_position, position_representation)
            step_rows.append(
                {
                    "case": case_id,
                    "from_position": position - 1,
                    "to_position": position,
                    **shift,
                    "distance_px": float(math.hypot(shift["dx_px"], shift["dy_px"])),
                    "dy_abs_error_px": float(abs(shift["dy_px"] - EXPECTED_DY_PX)),
                }
            )
        previous_position = position_representation

    dx = [float(row["dx_px"]) for row in step_rows]
    dy = [float(row["dy_px"]) for row in step_rows]
    dy_abs_error = [float(row["dy_abs_error_px"]) for row in step_rows]
    repeat_dx = [abs(float(row["dx_px"])) for row in repeat_rows]
    repeat_dy = [abs(float(row["dy_px"])) for row in repeat_rows]
    repeat_dist = [float(row["distance_px"]) for row in repeat_rows]
    responses = [float(row["response"]) for row in step_rows]
    summary = {
        "case": case_id,
        "method": "Raw-anchored, annulus-masked, half-resolution Sobel-edge phase correlation; position image is the mean of the two locked shots; every case uses the same Raw-derived crop centers; no rows removed.",
        "formal_external_gmf": False,
        "frames": len(files),
        "positions": EXPECTED_POSITIONS,
        "steps": len(step_rows),
        "step_dx_px": stats(dx),
        "step_dy_px": stats(dy),
        "step_dy_abs_error_px": stats(dy_abs_error),
        "step_response": stats(responses),
        "cumulative_dx_px": float(sum(dx)),
        "cumulative_dy_px": float(sum(dy)),
        "expected_cumulative_dy_px": EXPECTED_DY_PX * EXPECTED_STEPS,
        "repeat_abs_dx_px": stats(repeat_dx),
        "repeat_abs_dy_px": stats(repeat_dy),
        "repeat_distance_px": stats(repeat_dist),
    }
    return summary, step_rows, repeat_rows


def parse_gmf(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        parts = [part.strip() for part in line.split(",")]
        row: dict[str, object] = {}
        for idx in range(0, len(parts) - 1, 2):
            key = parts[idx]
            value = parts[idx + 1]
            if not key:
                continue
            if key == "FileName":
                row[key] = value
            else:
                try:
                    row[key] = float(value)
                except ValueError:
                    row[key] = value
        if "FileName" in row and "PosX" in row and "PosY" in row:
            rows.append(row)
    return rows


def external_gmf_summary(case_id: str, score_path: Path) -> dict[str, object]:
    rows = parse_gmf(score_path)
    if len(rows) != EXPECTED_FRAMES - 1:
        raise ValueError(f"{case_id}: expected 201 GMF rows, found {len(rows)}")
    grouped: dict[int, list[dict[str, object]]] = {}
    for row_index, row in enumerate(rows, start=2):
        position = (row_index - 1) // 2
        grouped.setdefault(position, []).append(row)
    means: list[dict[str, float]] = []
    repeat_rows: list[dict[str, float]] = []
    for position in range(EXPECTED_POSITIONS):
        group = grouped[position]
        x = [float(row["PosX"]) for row in group]
        y = [float(row["PosY"]) for row in group]
        means.append({"x": float(np.mean(x)), "y": float(np.mean(y))})
        if len(group) == 2:
            repeat_rows.append(
                {
                    "dx": abs(x[1] - x[0]),
                    "dy": abs(y[1] - y[0]),
                    "distance": float(math.hypot(x[1] - x[0], y[1] - y[0])),
                }
            )
    step_dx = [means[i + 1]["x"] - means[i]["x"] for i in range(EXPECTED_STEPS)]
    step_dy = [means[i + 1]["y"] - means[i]["y"] for i in range(EXPECTED_STEPS)]
    step_abs_error = [abs(value - EXPECTED_DY_PX) for value in step_dy]
    position_index = np.arange(EXPECTED_POSITIONS, dtype=np.float64)
    slope_x, intercept_x = np.polyfit(position_index, [m["x"] for m in means], 1)
    slope_y, intercept_y = np.polyfit(position_index, [m["y"] for m in means], 1)
    residual_x = np.asarray([m["x"] for m in means]) - (slope_x * position_index + intercept_x)
    residual_y = np.asarray([m["y"] for m in means]) - (slope_y * position_index + intercept_y)
    residual_distance = np.hypot(residual_x, residual_y)
    return {
        "case": case_id,
        "score_path": str(score_path),
        "rows": len(rows),
        "positions": len(means),
        "steps": len(step_dy),
        "step_dx_px": stats(step_dx),
        "step_dy_px": stats(step_dy),
        "step_dy_abs_error_px": stats(step_abs_error),
        "fit_slope_y_px_per_step": float(slope_y),
        "line_residual_rms_px": float(np.sqrt(np.mean(residual_distance**2))),
        "line_residual_p95_px": float(np.percentile(residual_distance, 95)),
        "line_residual_y_rms_px": float(np.sqrt(np.mean(residual_y**2))),
        "measured_total_x_px": float(means[-1]["x"] - means[0]["x"]),
        "measured_total_y_px": float(means[-1]["y"] - means[0]["y"]),
        "repeat_abs_dx_px": stats([row["dx"] for row in repeat_rows]),
        "repeat_abs_dy_px": stats([row["dy"] for row in repeat_rows]),
        "repeat_distance_px": stats([row["distance"] for row in repeat_rows]),
        "score0": stats([float(row["Score0"]) for row in rows]),
        "scale": stats([float(row["Scale"]) for row in rows]),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def largest_bright_center(image: np.ndarray) -> tuple[int, int]:
    threshold = float(np.percentile(image, 94))
    mask = (image >= threshold).astype(np.uint8)
    count, labels, statistics, centroids = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        return image.shape[1] // 2, image.shape[0] // 2
    candidates = []
    for label in range(1, count):
        area = int(statistics[label, cv2.CC_STAT_AREA])
        width = int(statistics[label, cv2.CC_STAT_WIDTH])
        height = int(statistics[label, cv2.CC_STAT_HEIGHT])
        if area > 500 and width > 100 and height > 100:
            candidates.append((area, label))
    if not candidates:
        label = 1 + int(np.argmax(statistics[1:, cv2.CC_STAT_AREA]))
    else:
        label = max(candidates)[1]
    x, y = centroids[label]
    return int(round(x)), int(round(y))


def crop_square(image: np.ndarray, center: tuple[int, int], size: int = 1050) -> np.ndarray:
    x, y = center
    half = size // 2
    left = min(max(0, x - half), max(0, image.shape[1] - size))
    top = min(max(0, y - half), max(0, image.shape[0] - size))
    return image[top : top + size, left : left + size]


def make_contact_sheet(cases: list[tuple[str, Path]]) -> None:
    positions = [0, 50, 100]
    raw_files = bmp_files(RAW)
    case_files = {name: bmp_files(folder) for name, folder in cases}
    fig, axes = plt.subplots(len(cases), len(positions), figsize=(12, 12), dpi=160)
    for column, position in enumerate(positions):
        raw = read_gray(raw_files[position * 2])
        center = largest_bright_center(raw)
        for row, (case_name, _) in enumerate(cases):
            image = read_gray(case_files[case_name][position * 2])
            axes[row, column].imshow(crop_square(image, center), cmap="gray", vmin=0, vmax=255)
            axes[row, column].set_title(f"{case_name} | position {position}")
            axes[row, column].axis("off")
    fig.suptitle("JunHua 1 um Y sequence: fixed positions and identical crops", fontsize=15)
    fig.tight_layout()
    fig.savefig(RESULTS / "reconstruction_comparison.png", bbox_inches="tight")
    plt.close(fig)


def make_motion_plot(local: list[dict[str, object]]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), dpi=160, sharex=True)
    for summary in local:
        case = str(summary["case"])
        steps_path = RESULTS / f"local_steps_{case}.csv"
        with steps_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        dy = [float(row["dy_px"]) for row in rows]
        error = [float(row["dy_abs_error_px"]) for row in rows]
        axes[0].plot(range(1, len(dy) + 1), dy, linewidth=1, label=case)
        axes[1].plot(range(1, len(error) + 1), error, linewidth=1, label=case)
    axes[0].axhline(EXPECTED_DY_PX, color="black", linestyle="--", linewidth=1, label="expected -8 px")
    axes[0].set_ylabel("Y shift (px)")
    axes[0].legend(ncol=4)
    axes[0].grid(alpha=0.25)
    axes[1].set_ylabel("absolute Y error (px)")
    axes[1].set_xlabel("1 um step number")
    axes[1].grid(alpha=0.25)
    fig.suptitle("Local image-only displacement check (not external GMF)")
    fig.tight_layout()
    fig.savefig(RESULTS / "local_displacement_comparison.png", bbox_inches="tight")
    plt.close(fig)


def make_seam_evidence() -> dict[str, object] | None:
    default_files = bmp_files(DEFAULT_TILES)
    if not default_files:
        return None
    full_path = MOSR / default_files[0].name
    if not full_path.is_file():
        return None
    tiled = read_gray(default_files[0])
    full = read_gray(full_path)
    difference = cv2.absdiff(tiled, full)
    enhanced = np.clip(difference.astype(np.float32) * 12.0, 0, 255).astype(np.uint8)
    fig, axes = plt.subplots(1, 3, figsize=(14, 7), dpi=160)
    for axis, image, title in zip(
        axes,
        [tiled, full, enhanced],
        ["Package default tiles", "Full-frame mode", "Difference x12"],
        strict=True,
    ):
        axis.imshow(image, cmap="gray", vmin=0, vmax=255)
        axis.set_title(title)
        axis.axis("off")
    fig.suptitle(f"Tiling issue evidence: {default_files[0].name}")
    fig.tight_layout()
    fig.savefig(RESULTS / "default_tiling_issue.png", bbox_inches="tight")
    plt.close(fig)
    return {
        "frame": default_files[0].name,
        "default_tiled_count_preserved": len(default_files),
        "mae_vs_fullframe": float(np.mean(difference)),
        "p95_abs_difference": float(np.percentile(difference, 95)),
        "max_abs_difference": int(np.max(difference)),
    }


def prepare_external_gmf() -> dict[str, object]:
    score_root = GMF_ROOT / "scores"
    score_paths = {
        "raw": score_root / "raw" / "GMF_score.txt",
        "r61": score_root / "r61" / "GMF_score.txt",
        "mosr": score_root / "mosr" / "GMF_score.txt",
    }
    for path in score_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    old_scores = {
        "raw": OLD_PACKAGE / "_gmf_scores" / "00_raw_input" / "GMF_score.txt",
        "r61": OLD_PACKAGE / "_gmf_scores" / "01_r61_v16_best_tradeoff_psfoff" / "GMF_score.txt",
    }
    for case, source in old_scores.items():
        shutil.copy2(source, score_paths[case])

    rows = [
        {
            "case": "raw",
            "role": "raw input",
            "image_folder": str(RAW),
            "score_folder": str(score_paths["raw"].parent),
            "image_count": EXPECTED_FRAMES,
            "status": "historical external GMF score copied and verified",
        },
        {
            "case": "r61",
            "role": "R61 v16 PSF-off",
            "image_folder": str(R61),
            "score_folder": str(score_paths["r61"].parent),
            "image_count": EXPECTED_FRAMES,
            "status": "historical external GMF score copied and verified",
        },
        {
            "case": "mosr",
            "role": "clean ONNX delivery model, full-frame mode",
            "image_folder": str(MOSR),
            "score_folder": str(score_paths["mosr"].parent),
            "image_count": EXPECTED_FRAMES,
            "status": "pending external GMF license key",
        },
    ]
    table = GMF_ROOT / "paths_for_gmf_tool.tsv"
    with table.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (score_paths["mosr"].parent / "PLACE_GMF_SCORE_HERE.txt").write_text(
        "When the external GMF license is available, score the 202 BMP files listed in paths_for_gmf_tool.tsv and save the returned file here as GMF_score.txt. Then rerun analyze.py.\n",
        encoding="utf-8",
    )
    return {"table": str(table), "score_paths": {key: str(value) for key, value in score_paths.items()}}


def fmt(value: object, digits: int = 4) -> str:
    if value is None:
        return "pending"
    return f"{float(value):.{digits}f}"


def write_report(payload: dict[str, object]) -> None:
    local = {str(row["case"]): row for row in payload["local_motion"]}
    external = {str(row["case"]): row for row in payload["external_gmf"]}
    lines = [
        "# JunHua 1 um Y Reconstruction Validation",
        "",
        "## Status",
        "",
        f"- Reconstruction: complete, {EXPECTED_FRAMES} of {EXPECTED_FRAMES} frames.",
        "- Sequence interpretation: 101 physical positions, two shots per position, 100 commanded 1 um Y steps.",
        "- Calibration: 0.125 um/px, so each 1 um step is expected to be -8 px in Y.",
        "- External GMF for Raw and R61: historical scores are present and re-parsed.",
        "- External GMF for the ONNX delivery model: pending because the tool currently has no license key.",
        "- Local phase-correlation results below are supplementary and must not be called external GMF.",
        "",
        "## Reconstruction integrity",
        "",
        f"- Source and old Raw package byte-for-byte match: {payload['input_audit']['source_vs_old_raw']['all_exact']}.",
        f"- MOSR output filenames exactly match source: {payload['input_audit']['cases']['mosr']['names_exact']}.",
        f"- Output dimensions and type: {payload['input_audit']['cases']['mosr']['shapes']}, {payload['input_audit']['cases']['mosr']['dtypes']}.",
        "- The package default 1024-pixel tiling produced visible seams on this image size. The complete test therefore used full-frame mode (`tile-size 2200`) with the same model and optical settings.",
        "",
        "## Local image-only displacement check",
        "",
        "| case | mean Y step (px) | Y-step std (px) | mean abs error vs -8 (px) | mean repeat distance (px) |",
        "|---|---:|---:|---:|---:|",
    ]
    for case in ["raw", "r61", "mosr"]:
        row = local[case]
        lines.append(
            f"| {case} | {fmt(row['step_dy_px']['mean'])} | {fmt(row['step_dy_px']['std_sample'])} | "
            f"{fmt(row['step_dy_abs_error_px']['mean'])} | {fmt(row['repeat_distance_px']['mean'])} |"
        )
    raw_std = float(local["raw"]["step_dy_px"]["std_sample"])
    r61_std = float(local["r61"]["step_dy_px"]["std_sample"])
    mosr_std = float(local["mosr"]["step_dy_px"]["std_sample"])
    raw_error = float(local["raw"]["step_dy_abs_error_px"]["mean"])
    r61_error = float(local["r61"]["step_dy_abs_error_px"]["mean"])
    mosr_error = float(local["mosr"]["step_dy_abs_error_px"]["mean"])
    lines.extend(
        [
            "",
            "These values use every locked physical step and every same-position pair; no rows were selected or removed.",
            "",
            "### Preliminary interpretation",
            "",
            f"- MOSR reduced the local Y-step standard deviation by {(raw_std - mosr_std) / raw_std * 100.0:.1f}% versus Raw.",
            f"- MOSR reduced the local mean absolute Y-step error by {(raw_error - mosr_error) / raw_error * 100.0:.1f}% versus Raw.",
            f"- R61 remained better in this local check: MOSR's Y-step standard deviation was {(mosr_std - r61_std) / r61_std * 100.0:.1f}% higher, and its mean absolute error was {(mosr_error - r61_error) / r61_error * 100.0:.1f}% higher.",
            "- This supports a positive direction versus Raw, but it is not enough to claim the delivery model matches or beats R61 without its own external GMF score.",
            "- Visually, MOSR is a mild reconstruction close to Raw, while R61 produces a much harder ring boundary.",
            "- The default tiling seam is a delivery-package blocker and should be fixed before enterprise handoff.",
            "",
            "## External GMF",
            "",
            "| case | mean Y step (px) | Y-step std (px) | mean abs error vs -8 (px) | line residual RMS (px) | status |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for case in ["raw", "r61", "mosr"]:
        row = external.get(case)
        if row is None:
            lines.append(f"| {case} | pending | pending | pending | pending | waiting for license key |")
        else:
            lines.append(
                f"| {case} | {fmt(row['step_dy_px']['mean'])} | {fmt(row['step_dy_px']['std_sample'])} | "
                f"{fmt(row['step_dy_abs_error_px']['mean'])} | {fmt(row['line_residual_rms_px'])} | complete |"
            )
    lines.extend(
        [
            "",
            "## Files to inspect",
            "",
            "- `results/reconstruction_comparison.png`: fixed Raw/R61/MOSR crops at positions 0, 50 and 100.",
            "- `results/local_displacement_comparison.png`: all 100 local Y-step measurements.",
            "- `results/default_tiling_issue.png`: evidence of the current delivery runner's default tiling seam.",
            "- `external_gmf/paths_for_gmf_tool.tsv`: the exact three-case table for the external GMF tool.",
            "- `external_gmf/scores/mosr/`: the folder where the new GMF_score.txt should be placed.",
            "",
        ]
    )
    (ROOT / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    source_files = bmp_files(SOURCE)
    raw_files = bmp_files(RAW)
    expected_names = [path.name for path in source_files]
    if len(source_files) != EXPECTED_FRAMES:
        raise ValueError(f"Expected {EXPECTED_FRAMES} source frames, found {len(source_files)}")
    if [path.name for path in raw_files] != expected_names:
        raise ValueError("Old Raw case does not have the same ordered filenames as the source")

    cases = {"raw": RAW, "r61": R61, "mosr": MOSR}
    case_audit = {case: validate_case(folder, expected_names) for case, folder in cases.items()}
    for case, audit in case_audit.items():
        if audit["count"] != EXPECTED_FRAMES or not audit["names_exact"]:
            raise ValueError(f"{case} failed count/name validation: {audit}")
        if audit["shapes"] != [[2180, 1520]] or audit["dtypes"] != ["uint8"]:
            raise ValueError(f"{case} failed format validation: {audit}")

    source_match = compare_source_to_raw(source_files, raw_files)
    if not source_match["all_exact"]:
        raise ValueError("Source images no longer match the historical Raw GMF package")

    delivery_files = [DELIVERY / name for name in ["model.onnx", "optics.npz", "run.py"]]
    delivery_hashes = {path.name: sha256(path) for path in delivery_files}
    input_audit = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sequence": {
            "frames": EXPECTED_FRAMES,
            "positions": EXPECTED_POSITIONS,
            "shots_per_position": 2,
            "steps": EXPECTED_STEPS,
            "commanded_step_um": 1.0,
            "object_um_per_px": OBJECT_UM_PER_PX,
            "expected_step_y_px": EXPECTED_DY_PX,
        },
        "source_vs_old_raw": source_match,
        "cases": case_audit,
        "delivery_hashes": delivery_hashes,
        "reconstruction_command": {
            "runner": str(DELIVERY / "run.py"),
            "input": str(SOURCE),
            "output": str(MOSR),
            "tile_size": 2200,
            "cpu": True,
            "reason": "Full-frame mode avoids the visible seams produced by the delivery runner's current default 1024-pixel tiling on 1520x2180 images.",
        },
    }
    (RESULTS / "input_audit.json").write_text(
        json.dumps(input_audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    local_summaries: list[dict[str, object]] = []
    for case, folder in cases.items():
        summary, step_rows, repeat_rows = local_motion(case, folder)
        local_summaries.append(summary)
        write_csv(RESULTS / f"local_steps_{case}.csv", step_rows)
        write_csv(RESULTS / f"local_repeats_{case}.csv", repeat_rows)

    gmf_package = prepare_external_gmf()
    external: list[dict[str, object]] = []
    for case, score_text in gmf_package["score_paths"].items():
        score_path = Path(score_text)
        if score_path.is_file():
            external.append(external_gmf_summary(case, score_path))

    make_contact_sheet(list(cases.items()))
    make_motion_plot(local_summaries)
    seam = make_seam_evidence()

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": {
            "reconstruction_complete": True,
            "external_gmf_mosr_complete": any(row["case"] == "mosr" for row in external),
            "external_gmf_blocker": None
            if any(row["case"] == "mosr" for row in external)
            else "External GmmVisionTool license key is not currently available.",
        },
        "input_audit": input_audit,
        "local_motion": local_summaries,
        "external_gmf": external,
        "default_tiling_issue": seam,
        "external_gmf_package": gmf_package,
    }
    (ROOT / "summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_report(payload)
    print(
        json.dumps(
            {
                "reconstruction_frames": case_audit["mosr"]["count"],
                "local_cases": [row["case"] for row in local_summaries],
                "external_gmf_cases": [row["case"] for row in external],
                "report": str(ROOT / "report.md"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
