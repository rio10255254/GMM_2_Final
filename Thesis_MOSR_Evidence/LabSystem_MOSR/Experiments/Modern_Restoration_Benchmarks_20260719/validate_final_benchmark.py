from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[4]


EXPERIMENT = Path(__file__).resolve().parent
EVALUATION = EXPERIMENT / "evaluation"
EXPECTED_METHODS = ["Raw", "Base U-Net", "NAFNet", "EDSR", "MOSR"]
EXPECTED_SEQUENCES = ["50x_x_0p5um", "50x_x_1um", "20x_0p5um", "20x_1um"]


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    return image


def check(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    failures: list[str] = []
    warnings: list[str] = []
    facts: dict[str, object] = {}

    via_sem = pd.read_csv(EVALUATION / "via_reference" / "via_center9_sem_reference.csv")
    check(len(via_sem) == 9, "Via SEM table must contain nine features", failures)
    check(
        np.allclose(via_sem["sem_diameter_nm"], 2.0 * via_sem["sem_radius_nm"], atol=1e-9),
        "Every via SEM diameter must equal two times its workbook radius",
        failures,
    )
    facts["via_sem_mean_diameter_nm"] = float(via_sem["sem_diameter_nm"].mean())

    detailed = pd.read_csv(
        EVALUATION
        / "circular_cd_sharpness"
        / "circular_feature_threshold_measurements.csv"
    )
    intervals = pd.read_csv(
        EVALUATION / "circular_cd_sharpness" / "circular_feature_cd_intervals.csv"
    )
    circular_summary = pd.read_csv(
        EVALUATION / "circular_cd_sharpness" / "circular_feature_method_summary.csv"
    )
    check(len(detailed) == 1260, f"Expected 1260 circular threshold rows, found {len(detailed)}", failures)
    check(len(intervals) == 180, f"Expected 180 circular interval rows, found {len(intervals)}", failures)
    check(len(circular_summary) == 20, f"Expected 20 circular summaries, found {len(circular_summary)}", failures)
    check(set(detailed["method"]) == set(EXPECTED_METHODS), "Circular analysis method set is incomplete", failures)
    check(set(np.round(detailed["contrast_fraction"], 2)) == set(np.arange(0.35, 0.66, 0.05).round(2)), "Circular threshold sweep is incomplete", failures)
    check(detailed["valid_angle_fraction"].min() >= 0.90, "A circular measurement has fewer than 90% valid angles", failures)
    check(np.isfinite(detailed.select_dtypes(include=[np.number])).all().all(), "Circular analysis contains non-finite values", failures)

    displacement = pd.read_csv(EVALUATION / "displacement" / "displacement_step_measurements.csv")
    availability = pd.read_csv(EVALUATION / "displacement" / "displacement_availability.csv")
    pooled = pd.read_csv(EVALUATION / "displacement" / "displacement_pooled_common_valid.csv")
    check(len(displacement) == 1200, f"Expected 1200 locked displacement rows, found {len(displacement)}", failures)
    check(len(availability) == 40, f"Expected 40 availability rows, found {len(availability)}", failures)
    check(len(pooled) == 10, f"Expected 10 pooled displacement rows, found {len(pooled)}", failures)
    check(set(displacement["method"]) == set(EXPECTED_METHODS), "Displacement method set is incomplete", failures)
    locked_counts = displacement.groupby(["morphology", "sequence", "method"]).size()
    check(locked_counts.eq(30).all(), "Not every morphology/sequence/method uses exactly 30 locked steps", failures)
    if availability["evaluable_fraction"].min() < 0.90:
        warnings.append(
            f"Minimum displacement evaluable fraction is {availability['evaluable_fraction'].min():.1%}"
        )
    facts["minimum_displacement_evaluable_fraction"] = float(
        availability["evaluable_fraction"].min()
    )

    line_root = EVALUATION / "line" / "tables"
    line_frames = pd.read_csv(line_root / "line_frame_metrics.csv")
    line_steps = pd.read_csv(line_root / "line_displacement_per_step.csv")
    line_summary = pd.read_csv(line_root / "line_sharpness_summary.csv")
    check(len(line_frames) == 600, f"Expected 600 line-frame rows, found {len(line_frames)}", failures)
    check(len(line_steps) == 300, f"Expected 300 line-step rows, found {len(line_steps)}", failures)
    check(len(line_summary) == 10, f"Expected 10 line sharpness rows, found {len(line_summary)}", failures)
    check(set(line_steps["method"]) == set(EXPECTED_METHODS), "Line method set is incomplete", failures)
    check(line_frames["valid_edges"].min() >= 10, "A line frame has fewer than ten valid edges", failures)
    check(line_steps["usable_edges"].min() >= 8, "A line step has fewer than eight usable edges", failures)
    check(line_steps[["boundary_step_um", "profile_step_um"]].notna().all().all(), "A line displacement estimate is missing", failures)

    runtime = pd.read_csv(EVALUATION / "runtime" / "computational_performance.csv")
    expected_runtime_methods = set(EXPECTED_METHODS) - {"Raw"}
    check(set(runtime["method"]) == expected_runtime_methods, "Runtime method set is incomplete", failures)
    check(runtime["parameter_count"].between(3_500_000, 4_500_000).all(), "A learned model is not parameter comparable", failures)
    check((runtime[["patch_median_ms", "full_median_ms", "full_peak_gpu_memory_mb"]] > 0).all().all(), "Runtime metrics must be positive", failures)

    crop_manifest = pd.read_csv(EVALUATION / "images" / "crop_manifest.csv")
    check(len(crop_manifest) == 30, f"Expected 30 single-image crop records, found {len(crop_manifest)}", failures)
    check(set(crop_manifest["method"]) == set(EXPECTED_METHODS), "Image crop method set is incomplete", failures)
    for row in crop_manifest.itertuples(index=False):
        native_path = Path(row.output_native)
        scale_path = Path(row.output_scale_bar)
        check(native_path.is_file(), f"Missing native crop: {native_path}", failures)
        check(scale_path.is_file(), f"Missing scale-bar crop: {scale_path}", failures)
        if native_path.is_file():
            source = read_gray(Path(row.source))
            expected = source[row.y : row.y + row.height, row.x : row.x + row.width]
            actual = read_gray(native_path)
            check(np.array_equal(actual, expected), f"Native crop was contrast-modified: {native_path.name}", failures)

    figures = sorted((EVALUATION / "figures_matlab").glob("*.png"))
    check(len(figures) == 22, f"Expected 22 MATLAB figures, found {len(figures)}", failures)
    check(all(path.stat().st_size > 10_000 for path in figures), "At least one MATLAB figure is unexpectedly small", failures)

    manifest = json.loads((EXPERIMENT / "evaluation_manifest.json").read_text(encoding="utf-8"))
    frame_counts = {
        "50x_x_0p5um": 51,
        "50x_x_1um": 50,
        "20x_0p5um": 50,
        "20x_1um": 50,
    }
    for method in ("NAFNet", "EDSR"):
        root = Path(PROJECT_ROOT / manifest["methods"][method]["sequence_root"])
        for sequence, expected_count in frame_counts.items():
            directory = root / manifest["sequence_name_map"][sequence][method]
            files = sorted(directory.glob("frame_*.bmp"))
            check(len(files) == expected_count, f"{method}/{sequence} frame count is {len(files)}", failures)
            if files:
                check(read_gray(files[0]).shape == (1536, 2048), f"{method}/{sequence} frame shape is invalid", failures)

    artifact_paths: list[Path] = []
    for directory in (
        EVALUATION / "via_reference",
        EVALUATION / "circular_cd_sharpness",
        EVALUATION / "displacement",
        EVALUATION / "line" / "tables",
        EVALUATION / "runtime",
        EVALUATION / "figures_matlab",
    ):
        artifact_paths.extend(path for path in directory.glob("*") if path.is_file())
    artifact_paths.extend(path for path in (EVALUATION / "images").glob("*") if path.is_file())
    with (EVALUATION / "artifact_sha256.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256"])
        writer.writeheader()
        for path in sorted(set(artifact_paths), key=lambda item: str(item).lower()):
            writer.writerow(
                {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )

    report = {
        "status": "PASS" if not failures else "FAIL",
        "hard_failures": failures,
        "warnings": warnings,
        "verified_facts": facts,
        "expected_methods": EXPECTED_METHODS,
        "expected_sequences": EXPECTED_SEQUENCES,
    }
    (EVALUATION / "QA_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
