"""Independent integrity checks and visual QA artifact for the R74 oracle probe."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "geometry_probe" / "E020" / "oracle_gate_probe"
SOURCE = Path(
    str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val')
)
OLD = ROOT / "results" / "geometry_probe" / "E020" / "r74_interventions"
CHECKPOINT = ROOT / "runs" / "r114_geometry_probe_scratch_20260830" / "weights" / "epoch_020.pth"
METHODS = (
    "FullFrozen",
    "OracleShiftGate",
    "OracleWidthGate",
    "OracleSeparateGates",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_gray(path: Path) -> np.ndarray:
    value = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise RuntimeError(path)
    return value


def image_count(root: Path) -> int:
    return len(list(root.rglob("*.bmp")))


def make_montage(records: list[dict]) -> Path:
    chosen = {}
    for row in records:
        chosen.setdefault(row["family"], row)
    columns = (
        "Raw",
        "Target",
        "Full",
        "Shift gate",
        "Width gate",
        "Separate",
        "Shift map",
        "Width map",
    )
    cell_width, image_size, header = 176, 160, 24
    canvas = np.full(
        (header + len(chosen) * (image_size + header), len(columns) * cell_width), 255, np.uint8
    )
    for column, title in enumerate(columns):
        cv2.putText(
            canvas,
            title,
            (column * cell_width + 5, 17),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            0,
            1,
            cv2.LINE_AA,
        )
    for row_index, (family, record) in enumerate(sorted(chosen.items())):
        stage, filename = str(record["stage"]), str(record["filename"])
        paths = (
            Path(record["src"]),
            Path(record["lbl"]),
            OUT / "inputs" / "FullFrozen" / stage / filename,
            OUT / "inputs" / "OracleShiftGate" / stage / filename,
            OUT / "inputs" / "OracleWidthGate" / stage / filename,
            OUT / "inputs" / "OracleSeparateGates" / stage / filename,
            OUT / "gates" / stage / "shift" / filename,
            OUT / "gates" / stage / "width" / filename,
        )
        y0 = header + row_index * (image_size + header)
        cv2.putText(
            canvas,
            family,
            (4, y0 + 17),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            0,
            1,
            cv2.LINE_AA,
        )
        for column, path in enumerate(paths):
            image = cv2.resize(read_gray(path), (image_size, image_size), interpolation=cv2.INTER_AREA)
            x0 = column * cell_width + (cell_width - image_size) // 2
            canvas[y0 + header : y0 + header + image_size, x0 : x0 + image_size] = image
    destination = OUT / "representative_montage.png"
    ok, encoded = cv2.imencode(".png", canvas)
    if not ok:
        raise RuntimeError(destination)
    encoded.tofile(destination)
    return destination


def main() -> int:
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((OUT / "analysis_summary.json").read_text(encoding="utf-8"))
    old_summary = json.loads((OLD / "analysis_summary.json").read_text(encoding="utf-8"))
    contract_tables = OUT / "locked_acm_contract" / "results" / "tables"
    primary = pd.read_csv(contract_tables / "primary_contour_metrics.csv")
    sensitivity = pd.read_csv(contract_tables / "acm_sensitivity_metrics.csv")

    output_counts = {method: image_count(OUT / "inputs" / method) for method in METHODS}
    gate_counts = {
        name: image_count(OUT / "gates") if name == "all" else len(list((OUT / "gates").rglob(f"{name}/*.bmp")))
        for name in ("shift", "width", "boundary_band", "all")
    }
    maximum_difference = 0
    mismatched = 0
    for record in manifest["records"]:
        relative = Path(str(record["stage"])) / str(record["filename"])
        current = read_gray(OUT / "inputs" / "FullFrozen" / relative)
        previous = read_gray(OLD / "inputs" / "Full" / relative)
        difference = int(np.max(np.abs(current.astype(np.int16) - previous.astype(np.int16))))
        maximum_difference = max(maximum_difference, difference)
        mismatched += int(difference != 0)

    old_full = old_summary["models"]["Full"]
    new_full = summary["models"]["FullFrozen"]
    metric_difference = max(
        abs(float(old_full[key]) - float(new_full[key]))
        for key in ("boundary_change_pct", "hd95_change_pct", "iou_delta")
    )
    checks = {
        "summary_complete": summary.get("status") == "complete",
        "record_count_100": len(manifest["records"]) == 100,
        "each_method_has_100_images": all(value == 100 for value in output_counts.values()),
        "each_gate_has_100_images": all(gate_counts[name] == 100 for name in ("shift", "width", "boundary_band")),
        "all_gate_images_300": gate_counts["all"] == 300,
        "primary_rows_1000": len(primary) == 1000,
        "sensitivity_rows_225": len(sensitivity) == 225,
        "zero_acm_failures": bool(primary["acm_success"].astype(bool).all()),
        "exact_full_image_reproduction": maximum_difference == 0 and mismatched == 0,
        "exact_full_metric_reproduction": metric_difference <= 1.0e-12,
        "internal_renderer_reproduction": float(summary["maximum_full_renderer_reproduction_error"]) <= 2.0e-6,
        "checkpoint_hash_matches": summary["checkpoint_sha256"] == sha256(CHECKPOINT),
        "source_manifest_hash_matches": summary["source_manifest_sha256"] == sha256(SOURCE / "manifest.json"),
        "truth_usage_declared_upper_bound": bool(summary["conclusion"]["oracle_upper_bound_only"]),
        "result_declared_not_deployable": bool(summary["conclusion"]["not_deployable"]),
    }
    montage = make_montage(manifest["records"])
    report = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "output_counts": output_counts,
        "gate_counts": gate_counts,
        "primary_rows": len(primary),
        "sensitivity_rows": len(sensitivity),
        "maximum_full_image_difference_gray": maximum_difference,
        "mismatched_full_images": mismatched,
        "maximum_full_metric_difference": metric_difference,
        "montage": str(montage),
    }
    (OUT / "validation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
