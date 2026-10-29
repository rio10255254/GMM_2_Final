from __future__ import annotations

import argparse
import csv
import copy
import json
import math
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[5]


REPORT_ROOT = Path(__file__).resolve().parents[1] / "reports"
ALGORITHM = "gmf_like_gaussian_template_fixed_thesis_gate"
CASE_ALGORITHM = "gmf_like_gaussian_template_fit"
DEFAULT_CASES = {
    "raw": "raw_inputs/{group}/bmp",
    "r61": "r61_v16_psfoff_{group}/bmp",
    "v7": "r62_v7_seqgeom_noamp_lr3e7_psfoff_{group}/bmp",
}
DATASETS = [
    {
        "dataset": "20260702_100MG",
        "root": Path(str(PROJECT_ROOT / '20260702_100MG_displacement_analysis')),
        "groups": ["x_1um", "x_0p5um"],
        "nominal_um": {"x_1um": 1.0, "x_0p5um": 0.5},
        "object_um_per_px": {"x_1um": 0.069, "x_0p5um": 0.069},
        "roi_label": "top_right_dark_pillar_array",
        "crop": (1080, 40, 820, 700),
        "polarity": "dark",
        "local_radius": 24.0,
        "cluster_radius": 1.5,
    },
    {
        "dataset": "20260704_20x_5x",
        "root": Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis')),
        "groups": ["20x_1um", "20x_0p5um", "5x_1um", "5x_0p5um"],
        "nominal_um": {"20x_1um": 1.0, "20x_0p5um": 0.5, "5x_1um": 1.0, "5x_0p5um": 0.5},
        "object_um_per_px": {"20x_1um": 0.1725, "20x_0p5um": 0.1725, "5x_1um": 0.69, "5x_0p5um": 0.69},
        "roi_label": "gmf_validation_dot_grid",
        "crop": (650, 150, 520, 360),
        "polarity": "bright",
        "local_radius": 10.0,
        "cluster_radius": 1.0,
    },
]


def datasets_for_profile(profile: str) -> list[dict[str, object]]:
    profile = str(profile)
    datasets = copy.deepcopy(DATASETS)
    if profile in {"fixed", "default", "thesis_fixed"}:
        return datasets
    if profile != "shape_aware_square":
        raise ValueError(f"unknown GMF-like profile: {profile}")
    for spec in datasets:
        if spec["dataset"] != "20260704_20x_5x":
            continue
        spec["roi_label_by_group"] = {
            "5x_1um": "shape_aware_square_block_5x",
            "5x_0p5um": "shape_aware_square_block_5x",
        }
        spec["crop_by_group"] = {
            "5x_1um": (985, 395, 185, 115),
            "5x_0p5um": (985, 395, 185, 115),
        }
        spec["signal_mode_by_group"] = {
            "5x_1um": "edge",
            "5x_0p5um": "edge",
        }
        spec["threshold_quantile_by_group"] = {
            "5x_1um": 0.55,
            "5x_0p5um": 0.55,
        }
        spec["min_area_by_group"] = {
            "5x_1um": 4,
            "5x_0p5um": 4,
        }
        spec["local_radius_by_group"] = {
            "5x_1um": 8.0,
            "5x_0p5um": 8.0,
        }
        spec["cluster_radius_by_group"] = {
            "5x_1um": 1.0,
            "5x_0p5um": 1.0,
        }
    return datasets


def group_value(spec: dict[str, object], field: str, group: str, default: object | None = None) -> object:
    by_group = spec.get(f"{field}_by_group")
    if isinstance(by_group, dict) and group in by_group:
        return by_group[group]
    if field in spec:
        return spec[field]
    return default


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"failed to read image: {path}")
    return image


def crop_image(image: np.ndarray, crop: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = [int(v) for v in crop]
    return image[y : y + h, x : x + w]


def feature_signal(image: np.ndarray, *, polarity: str, signal_mode: str, blur_sigma: float) -> np.ndarray:
    gray = image.astype(np.float32)
    if signal_mode == "edge":
        blur = cv2.GaussianBlur(gray, (0, 0), float(max(0.01, blur_sigma)))
        gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
        signal = cv2.magnitude(gx, gy)
    elif signal_mode == "intensity":
        signal = 255.0 - gray if str(polarity).lower() == "dark" else gray
        signal = cv2.GaussianBlur(signal, (0, 0), float(max(0.01, blur_sigma)))
    else:
        raise ValueError(f"unknown signal_mode: {signal_mode}")
    signal -= float(np.nanmin(signal))
    return signal


def cluster_features(features: list[dict[str, float]], *, cluster_radius: float, max_components: int) -> list[dict[str, float]]:
    kept: list[dict[str, float]] = []
    for feature in sorted(features, key=lambda item: item["weight"], reverse=True):
        if all(
            math.hypot(feature["x"] - old["x"], feature["y"] - old["y"]) > float(cluster_radius)
            for old in kept
        ):
            kept.append(feature)
        if len(kept) >= int(max_components):
            break
    return kept


def detect_features(
    image: np.ndarray,
    *,
    polarity: str,
    signal_mode: str = "intensity",
    blur_sigma: float = 0.8,
    threshold_quantile: float = 0.65,
    min_area: int = 20,
    max_components: int = 60,
    cluster_radius: float = 1.5,
) -> list[dict[str, float]]:
    signal = feature_signal(image, polarity=polarity, signal_mode=signal_mode, blur_sigma=blur_sigma)
    threshold = float(np.quantile(signal, float(threshold_quantile)))
    mask = (signal > threshold).astype(np.uint8)
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    features: list[dict[str, float]] = []
    for idx in range(1, count):
        area = int(stats[idx, cv2.CC_STAT_AREA])
        if area < int(min_area):
            continue
        ys, xs = np.where(labels == idx)
        weights = np.maximum(signal[ys, xs] - threshold, 0.0)
        weight_sum = float(weights.sum())
        if weight_sum <= 1e-9:
            weights = signal[ys, xs]
            weight_sum = float(weights.sum())
        if weight_sum <= 1e-9:
            continue
        cx = float(np.sum(xs.astype(np.float32) * weights) / weight_sum)
        cy = float(np.sum(ys.astype(np.float32) * weights) / weight_sum)
        features.append({"x": cx, "y": cy, "weight": weight_sum, "area": float(area)})
    return cluster_features(features, cluster_radius=cluster_radius, max_components=max_components)


def match_step(
    previous: list[dict[str, float]],
    current: list[dict[str, float]],
    *,
    local_radius: float,
) -> tuple[float, float, int, float] | None:
    if not previous or not current:
        return None
    used: set[int] = set()
    dxs: list[float] = []
    dys: list[float] = []
    weights: list[float] = []
    for prev in previous:
        best_idx = -1
        best_dist = float(local_radius)
        for idx, cur in enumerate(current):
            if idx in used:
                continue
            dist = math.hypot(cur["x"] - prev["x"], cur["y"] - prev["y"])
            if dist <= best_dist:
                best_dist = dist
                best_idx = idx
        if best_idx < 0:
            continue
        used.add(best_idx)
        cur = current[best_idx]
        dxs.append(float(cur["x"] - prev["x"]))
        dys.append(float(cur["y"] - prev["y"]))
        weights.append(float(cur["weight"]))
    if not dxs:
        return None
    return float(np.median(dxs)), float(np.median(dys)), len(dxs), float(np.median(weights))


def write_csv(path: Path, rows: Iterable[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def analyze_case(
    input_dir: Path,
    *,
    output_dir: Path,
    dataset: str,
    group: str,
    case: str,
    roi_label: str,
    crop: tuple[int, int, int, int],
    polarity: str,
    nominal_um: float,
    object_um_per_px: float,
    mode: str = "multi",
    signal_mode: str = "intensity",
    blur_sigma: float = 0.8,
    threshold_quantile: float = 0.65,
    min_area: int = 20,
    max_components: int = 60,
    local_radius: float = 24.0,
    cluster_radius: float = 1.5,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    paths = sorted(Path(input_dir).glob("*.bmp"))
    if len(paths) < 2:
        raise FileNotFoundError(f"not enough BMP files in {input_dir}")
    rows: list[dict[str, object]] = []
    previous_features: list[dict[str, float]] | None = None
    cumulative_dx = 0.0
    cumulative_dy = 0.0
    for frame_index, path in enumerate(paths):
        image = crop_image(read_gray(path), crop)
        features = detect_features(
            image,
            polarity=polarity,
            signal_mode=signal_mode,
            blur_sigma=blur_sigma,
            threshold_quantile=threshold_quantile,
            min_area=min_area,
            max_components=max_components,
            cluster_radius=cluster_radius,
        )
        if frame_index == 0:
            row = {
                "frame_index": frame_index,
                "filename": path.name,
                "ref_filename": "",
                "mode": mode,
                "dx_px": 0.0,
                "dy_px": 0.0,
                "cumulative_dx_px": 0.0,
                "cumulative_dy_px": 0.0,
                "feature_count": len(features),
                "tracked_feature_count": "",
                "median_feature_weight": 0.0,
                "status": "reference",
                "message": "",
            }
        else:
            assert previous_features is not None
            matched = match_step(previous_features, features, local_radius=local_radius)
            if matched is None:
                dx = dy = float("nan")
                tracked = 0
                median_weight = float("nan")
                status = "failed"
                message = "no local feature matches"
            else:
                dx, dy, tracked, median_weight = matched
                cumulative_dx += dx
                cumulative_dy += dy
                status = "ok"
                message = ""
            row = {
                "frame_index": frame_index,
                "filename": path.name,
                "ref_filename": paths[frame_index - 1].name,
                "mode": mode,
                "dx_px": dx,
                "dy_px": dy,
                "cumulative_dx_px": cumulative_dx,
                "cumulative_dy_px": cumulative_dy,
                "feature_count": len(features),
                "tracked_feature_count": tracked,
                "median_feature_weight": median_weight,
                "status": status,
                "message": message,
            }
        rows.append(row)
        previous_features = features

    ok_rows = [row for row in rows if row["status"] == "ok"]
    dx_values = np.asarray([float(row["dx_px"]) for row in ok_rows], dtype=np.float64)
    dy_values = np.asarray([float(row["dy_px"]) for row in ok_rows], dtype=np.float64)
    mean_dx = float(np.mean(dx_values)) if dx_values.size else float("nan")
    std_dx = float(np.std(dx_values)) if dx_values.size else float("nan")
    mean_dy = float(np.mean(dy_values)) if dy_values.size else float("nan")
    std_dy = float(np.std(dy_values)) if dy_values.size else float("nan")
    rms_step = float(np.sqrt(np.mean(dx_values * dx_values + dy_values * dy_values))) if dx_values.size else float("nan")
    safe_dataset = str(dataset).replace("/", "_")
    steps_csv = Path(output_dir) / f"{safe_dataset}_{group}_{case}_steps.csv"
    summary_json = Path(output_dir) / f"{safe_dataset}_{group}_{case}_summary.json"
    step_um = abs(mean_dx) * float(object_um_per_px) if math.isfinite(mean_dx) else float("nan")
    summary = {
        "algorithm": CASE_ALGORITHM,
        "input_dir": str(input_dir),
        "image_count": len(paths),
        "crop": list(crop),
        "polarity": polarity,
        "mode": mode,
        "signal_mode": signal_mode,
        "blur_sigma": blur_sigma,
        "threshold_quantile": threshold_quantile,
        "min_area": min_area,
        "max_components": max_components,
        "local_radius": local_radius,
        "cluster_radius": cluster_radius,
        "seed_centers": None,
        "dataset": dataset,
        "group": group,
        "case": case,
        "roi_label": roi_label,
        "nominal_um": float(nominal_um),
        "object_um_per_px": float(object_um_per_px),
        "failed_step_count": len(rows) - 1 - len(ok_rows),
        "valid_step_count": len(ok_rows),
        "mean_dx_px": mean_dx,
        "std_dx_px": std_dx,
        "mean_dy_px": mean_dy,
        "std_dy_px": std_dy,
        "rms_step_px": rms_step,
        "std_um": std_dx * float(object_um_per_px) if math.isfinite(std_dx) else float("nan"),
        "step_um": step_um,
        "step_error_um": abs(step_um - float(nominal_um)) if math.isfinite(step_um) else float("nan"),
        "status": "ok" if ok_rows else "failed",
        "steps_csv": str(steps_csv),
        "summary_json": str(summary_json),
    }
    write_csv(
        steps_csv,
        rows,
        [
            "frame_index",
            "filename",
            "ref_filename",
            "mode",
            "dx_px",
            "dy_px",
            "cumulative_dx_px",
            "cumulative_dy_px",
            "feature_count",
            "tracked_feature_count",
            "median_feature_weight",
            "status",
            "message",
        ],
    )
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary, rows


def result_row_from_summary(summary: dict[str, object]) -> dict[str, object]:
    return {
        "dataset": summary["dataset"],
        "group": summary["group"],
        "case": summary["case"],
        "roi_label": summary["roi_label"],
        "polarity": summary["polarity"],
        "mode": summary["mode"],
        "signal_mode": summary["signal_mode"],
        "nominal_um": summary["nominal_um"],
        "object_um_per_px": summary["object_um_per_px"],
        "valid_step_count": summary["valid_step_count"],
        "failed_step_count": summary["failed_step_count"],
        "mean_dx_px": summary["mean_dx_px"],
        "std_dx_px": summary["std_dx_px"],
        "std_um": summary["std_um"],
        "step_um": summary["step_um"],
        "step_error_um": summary["step_error_um"],
        "status": summary["status"],
        "input_dir": summary["input_dir"],
        "steps_csv": summary["steps_csv"],
        "summary_json": summary["summary_json"],
    }


def parse_cases(values: list[str] | None) -> dict[str, str]:
    if not values:
        return dict(DEFAULT_CASES)
    cases: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"case must be LABEL=TEMPLATE: {value}")
        label, template = value.split("=", 1)
        cases[label.strip()] = template.strip()
    return cases


def resolve_case_dir(root: Path, template: str, group: str) -> Path:
    path = Path(str(template).format(group=group))
    return path if path.is_absolute() else root / path


def run_gate(
    *,
    output_dir: Path,
    cases: dict[str, str],
    candidate_case: str,
    signal_mode: str = "intensity",
    profile: str = "fixed",
    dataset_specs: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_rows: list[dict[str, object]] = []
    active_datasets = dataset_specs if dataset_specs is not None else datasets_for_profile(profile)
    for spec in active_datasets:
        root = Path(spec["root"])
        for group in spec["groups"]:
            for case, template in cases.items():
                input_dir = resolve_case_dir(root, template, str(group))
                crop = tuple(group_value(spec, "crop", str(group)))
                roi_label = str(group_value(spec, "roi_label", str(group)))
                case_signal_mode = str(group_value(spec, "signal_mode", str(group), signal_mode))
                threshold_quantile = float(group_value(spec, "threshold_quantile", str(group), 0.65))
                min_area = int(group_value(spec, "min_area", str(group), 20))
                local_radius = float(group_value(spec, "local_radius", str(group)))
                cluster_radius = float(group_value(spec, "cluster_radius", str(group)))
                summary, _rows = analyze_case(
                    input_dir,
                    output_dir=output_dir,
                    dataset=str(spec["dataset"]),
                    group=str(group),
                    case=str(case),
                    roi_label=roi_label,
                    crop=crop,
                    polarity=str(spec["polarity"]),
                    nominal_um=float(spec["nominal_um"][group]),
                    object_um_per_px=float(spec["object_um_per_px"][group]),
                    signal_mode=case_signal_mode,
                    threshold_quantile=threshold_quantile,
                    min_area=min_area,
                    local_radius=local_radius,
                    cluster_radius=cluster_radius,
                )
                result_rows.append(result_row_from_summary(summary))

    results_csv = output_dir / "gmf_like_thesis_gate_results.csv"
    result_fields = list(result_rows[0].keys())
    write_csv(results_csv, result_rows, result_fields)
    comparison_rows = build_comparison_rows(result_rows, candidate_case=candidate_case)
    comparison_csv = output_dir / "gmf_like_thesis_gate_comparison.csv"
    write_csv(
        comparison_csv,
        comparison_rows,
        [
            "dataset",
            "group",
            "baseline_case",
            "candidate_case",
            "best_case",
            "baseline_std_um",
            "candidate_std_um",
            "candidate_vs_baseline_improvement_pct",
        ],
    )
    selection_summary = {
        "candidate_case": candidate_case,
        "comparison_count": len(comparison_rows),
        "mean_candidate_improvement_pct": float(
            np.mean([float(row["candidate_vs_baseline_improvement_pct"]) for row in comparison_rows])
        )
        if comparison_rows
        else float("nan"),
    }
    selection_path = output_dir / "gmf_like_thesis_gate_selection_summary.json"
    selection_path.write_text(json.dumps(selection_summary, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path = output_dir / "GMF_LIKE_THESIS_GATE_REPORT.md"
    report_path.write_text(build_markdown_report(result_rows, comparison_rows), encoding="utf-8")
    manifest = {
        "algorithm": ALGORITHM,
        "output_dir": str(output_dir),
        "results_csv": str(results_csv),
        "comparison_csv": str(comparison_csv),
        "selection_summary_json": str(selection_path),
        "report": str(report_path),
        "candidate_case": candidate_case,
        "cases": cases,
        "signal_mode_override": signal_mode,
        "profile": profile,
        "case_count": len(result_rows),
        "comparison_count": len(comparison_rows),
    }
    manifest_path = output_dir / "gmf_like_thesis_gate_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def build_comparison_rows(result_rows: list[dict[str, object]], *, candidate_case: str) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in result_rows:
        grouped.setdefault((str(row["dataset"]), str(row["group"])), []).append(row)
    rows: list[dict[str, object]] = []
    for (dataset, group), group_rows in sorted(grouped.items()):
        baseline = next((row for row in group_rows if row["case"] == "raw"), None)
        candidate = next((row for row in group_rows if row["case"] == candidate_case), None)
        if baseline is None or candidate is None:
            continue
        ok_rows = [row for row in group_rows if str(row.get("status")) == "ok"]
        best = min(ok_rows, key=lambda row: float(row["std_um"])) if ok_rows else candidate
        baseline_std = float(baseline["std_um"])
        candidate_std = float(candidate["std_um"])
        improvement = (baseline_std - candidate_std) / baseline_std * 100.0 if baseline_std else float("nan")
        rows.append(
            {
                "dataset": dataset,
                "group": group,
                "baseline_case": "raw",
                "candidate_case": candidate_case,
                "best_case": best["case"],
                "baseline_std_um": baseline_std,
                "candidate_std_um": candidate_std,
                "candidate_vs_baseline_improvement_pct": round(float(improvement), 6),
            }
        )
    return rows


def build_markdown_report(result_rows: list[dict[str, object]], comparison_rows: list[dict[str, object]]) -> str:
    lines = [
        "# GMF-like thesis displacement gate",
        "",
        "This gate uses fixed ROIs and an open local feature fitting tracker.",
        "",
        "## Case Results",
        "",
        "| dataset | group | case | std um | step um | status |",
        "|---|---|---|---:|---:|---|",
    ]
    for row in result_rows:
        lines.append(
            f"| {row['dataset']} | {row['group']} | {row['case']} | "
            f"{float(row['std_um']):.6f} | {float(row['step_um']):.6f} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "## Raw vs Candidate",
            "",
            "| dataset | group | best | candidate improvement vs Raw |",
            "|---|---|---|---:|",
        ]
    )
    for row in comparison_rows:
        lines.append(
            f"| {row['dataset']} | {row['group']} | {row['best_case']} | "
            f"{float(row['candidate_vs_baseline_improvement_pct']):.2f}% |"
        )
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run open GMF-like fixed-ROI displacement gate for thesis datasets.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--case", action="append", help="Case mapping LABEL=TEMPLATE. TEMPLATE may contain {group}.")
    parser.add_argument("--candidate-case", default="v20e1m200")
    parser.add_argument("--signal-mode", choices=("intensity", "edge"), default="intensity")
    parser.add_argument("--profile", choices=("fixed", "thesis_fixed", "shape_aware_square"), default="fixed")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = run_gate(
        output_dir=Path(args.output_dir),
        cases=parse_cases(args.case),
        candidate_case=str(args.candidate_case),
        signal_mode=str(args.signal_mode),
        profile=str(args.profile),
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
