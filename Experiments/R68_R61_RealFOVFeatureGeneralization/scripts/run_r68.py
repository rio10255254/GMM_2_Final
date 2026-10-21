from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "sequences.json"
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
REPORT = ROOT / "reports" / "R68_RESULTS.md"
CAMERA_PIXEL_UM = 3.45


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def image_paths(directory: Path) -> list[Path]:
    return sorted(directory.glob("frame_*.bmp"))


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(path)
    return image


def validate_inputs(config: dict) -> dict:
    checkpoint = Path(config["checkpoint"])
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    audit = {"checkpoint": str(checkpoint), "sequences": {}, "total_frames": 0}
    for name, item in config["sequences"].items():
        raw_dir, recon_dir = Path(item["raw_dir"]), Path(item["recon_dir"])
        raw, recon = image_paths(raw_dir), image_paths(recon_dir)
        expected = int(item["frame_count"])
        if len(raw) != expected or len(recon) != expected:
            raise RuntimeError(f"{name}: expected {expected}; raw={len(raw)}, recon={len(recon)}")
        if [p.name for p in raw] != [p.name for p in recon]:
            raise RuntimeError(f"{name}: Raw and R61 filenames do not match")
        manifest_path = Path(item["source_manifest"])
        manifest = read_json(manifest_path)
        if Path(manifest["weights"]).resolve() != checkpoint.resolve():
            raise RuntimeError(f"{name}: source reconstruction used another checkpoint")
        command = [str(x).lower() for x in manifest.get("command", [])]
        if "--no-psf-from-ckpt" not in command or "--weak-psf-disable" not in command:
            raise RuntimeError(f"{name}: reconstruction is not the locked R61 real-sample mode")
        raw_shape = read_gray(raw[0]).shape
        recon_shape = read_gray(recon[0]).shape
        if raw_shape != recon_shape or raw_shape != (1536, 2048):
            raise RuntimeError(f"{name}: unexpected image shapes {raw_shape} / {recon_shape}")
        audit["sequences"][name] = {
            "raw_dir": str(raw_dir), "recon_dir": str(recon_dir), "frames": expected,
            "shape": list(raw_shape), "source_manifest": str(manifest_path),
            "checkpoint_match": True, "locked_real_sample_mode": True,
        }
        audit["total_frames"] += expected
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "input_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return audit


def mapping_for(item: dict, sequence: str) -> dict[str, datetime]:
    rows = pd.read_csv(item["mapping_csv"], encoding="utf-8-sig")
    possible_groups = {sequence, sequence.replace("50x_", "x_")}
    rows = rows.loc[rows["group"].astype(str).isin(possible_groups)]
    output = {}
    for _, row in rows.iterrows():
        output[str(row["work_name"])] = datetime.strptime(str(row["timestamp"]), "%Y-%m-%d %H:%M:%S")
    return output


def edge_image(image: np.ndarray) -> np.ndarray:
    gray = cv2.GaussianBlur(image.astype(np.float32), (0, 0), 1.0)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edge = cv2.magnitude(gx, gy)
    edge -= float(edge.mean())
    std = float(edge.std())
    return edge / std if std > 1e-6 else edge


def select_tiles(first_raw: np.ndarray, grid: dict) -> list[dict]:
    rows, columns = int(grid["rows"]), int(grid["columns"])
    tile_h, tile_w = first_raw.shape[0] // rows, first_raw.shape[1] // columns
    records = []
    for row in range(rows):
        for column in range(columns):
            y0, x0 = row * tile_h, column * tile_w
            tile = first_raw[y0:y0 + tile_h, x0:x0 + tile_w]
            edge = edge_image(tile)
            records.append({
                "tile_id": f"r{row:02d}_c{column:02d}", "row": row, "column": column,
                "x0": x0, "y0": y0, "width": tile_w, "height": tile_h,
                "edge_score": float(np.mean(np.abs(edge))),
            })
    records.sort(key=lambda x: x["edge_score"], reverse=True)
    return records[: int(grid["selected_tiles"])]


def phase_shift(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    a_edge, b_edge = edge_image(a), edge_image(b)
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a_edge, b_edge, window)
    return float(dx), float(dy), float(response)


def bounded_ecc_shift(a: np.ndarray, b: np.ndarray, initial_dx: float, initial_dy: float) -> tuple[float, float, float]:
    """Refine translation near the Raw estimate, avoiding periodic pitch jumps."""
    a_float = cv2.GaussianBlur(a.astype(np.float32) / 255.0, (0, 0), 1.0)
    b_float = cv2.GaussianBlur(b.astype(np.float32) / 255.0, (0, 0), 1.0)
    warp = np.array([[1.0, 0.0, initial_dx], [0.0, 1.0, initial_dy]], dtype=np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-6)
    correlation, refined = cv2.findTransformECC(
        a_float, b_float, warp, cv2.MOTION_TRANSLATION, criteria, None, 1
    )
    return float(refined[0, 2]), float(refined[1, 2]), float(correlation)


def analyze_sequence(name: str, item: dict, config: dict) -> tuple[list[dict], dict]:
    raw_paths, recon_paths = image_paths(Path(item["raw_dir"])), image_paths(Path(item["recon_dir"]))
    mapping = mapping_for(item, name)
    tiles = select_tiles(read_gray(raw_paths[0]), config["tile_grid"])
    max_gap = float(config["max_time_gap_seconds"])
    min_response = float(config["minimum_phase_response"])
    magnification = float(item["magnification"])
    object_um_per_px = CAMERA_PIXEL_UM / magnification
    nominal_step_um = float(item["nominal_step_um"])
    expected_px = nominal_step_um / object_um_per_px
    rows = []
    used_steps = 0
    for index in range(len(raw_paths) - 1):
        a_name, b_name = raw_paths[index].name, raw_paths[index + 1].name
        gap = None
        if a_name in mapping and b_name in mapping:
            gap = (mapping[b_name] - mapping[a_name]).total_seconds()
            if gap > max_gap:
                continue
        used_steps += 1
        raw_a, raw_b = read_gray(raw_paths[index]), read_gray(raw_paths[index + 1])
        rec_a, rec_b = read_gray(recon_paths[index]), read_gray(recon_paths[index + 1])
        for tile in tiles:
            x0, y0, w, h = tile["x0"], tile["y0"], tile["width"], tile["height"]
            raw_tile_a, raw_tile_b = raw_a[y0:y0+h, x0:x0+w], raw_b[y0:y0+h, x0:x0+w]
            rec_tile_a, rec_tile_b = rec_a[y0:y0+h, x0:x0+w], rec_b[y0:y0+h, x0:x0+w]
            raw_dx, raw_dy, raw_response = phase_shift(raw_tile_a, raw_tile_b)
            phase_dx, phase_dy, rec_response = phase_shift(rec_tile_a, rec_tile_b)
            try:
                rec_dx, rec_dy, ecc = bounded_ecc_shift(rec_tile_a, rec_tile_b, raw_dx, raw_dy)
                ecc_ok = math.isfinite(ecc)
            except cv2.error:
                rec_dx, rec_dy, ecc, ecc_ok = math.nan, math.nan, math.nan, False
            shift_limit = max(12.0, expected_px * 2.5)
            # Lock the analyzable population from Raw only. Periodic arrays can
            # make an unconstrained local phase estimate jump by one pitch; such
            # a tile is not a valid reference and must not count against R61.
            raw_reference_valid = (
                raw_response >= min_response
                and expected_px * 0.50 <= abs(raw_dx) <= expected_px * 1.50
                and abs(raw_dy) <= max(expected_px * 0.50, 0.35)
            )
            r61_evaluable = (
                ecc_ok and ecc >= 0.75
                and abs(rec_dx) <= shift_limit and abs(rec_dy) <= shift_limit
            )
            valid = raw_reference_valid and r61_evaluable
            direction = bool(np.sign(raw_dx) == np.sign(rec_dx)) if valid and abs(raw_dx) > 0.05 and abs(rec_dx) > 0.05 else False
            difference_um = math.hypot(rec_dx - raw_dx, rec_dy - raw_dy) * object_um_per_px if valid else math.nan
            scale = abs(rec_dx) / max(abs(raw_dx), 1e-9) if valid else math.nan
            rows.append({
                "sequence": name, "magnification": magnification, "nominal_step_um": nominal_step_um,
                "object_um_per_px": object_um_per_px, "expected_dx_px": expected_px,
                "step_index": index, "time_gap_s": gap, "tile_id": tile["tile_id"],
                "tile_row": tile["row"], "tile_column": tile["column"], "edge_score": tile["edge_score"],
                "raw_dx_px": raw_dx, "raw_dy_px": raw_dy, "raw_response": raw_response,
                "r61_phase_dx_px": phase_dx, "r61_phase_dy_px": phase_dy, "r61_response": rec_response,
                "r61_dx_px": rec_dx, "r61_dy_px": rec_dy, "r61_ecc": ecc,
                "raw_reference_valid": raw_reference_valid, "r61_evaluable": r61_evaluable,
                "valid": valid, "direction_agreement": direction, "r61_over_raw_abs_dx": scale,
                "r61_raw_vector_difference_um": difference_um,
            })
    table = pd.DataFrame(rows)
    reference = table.loc[table["raw_reference_valid"]].copy()
    valid = table.loc[table["valid"]].copy()
    if reference.empty or valid.empty:
        raise RuntimeError(f"{name}: no valid local measurements")
    response_ratio = valid["r61_response"] / valid["raw_response"].clip(lower=1e-9)
    summary = {
        "sequence": name, "magnification": magnification, "nominal_step_um": nominal_step_um,
        "selected_tiles": len(tiles), "used_steps": used_steps, "tile_measurements": len(table),
        "raw_reference_measurements": len(reference), "raw_reference_fraction": float(table["raw_reference_valid"].mean()),
        "valid_measurements": len(valid), "valid_fraction": float(len(valid) / len(reference)),
        "direction_agreement_fraction": float(valid["direction_agreement"].mean()),
        "median_r61_over_raw_abs_dx": float(valid["r61_over_raw_abs_dx"].median()),
        "median_scale_error_fraction": float(abs(valid["r61_over_raw_abs_dx"].median() - 1.0)),
        "median_vector_difference_um": float(valid["r61_raw_vector_difference_um"].median()),
        "p95_vector_difference_um": float(valid["r61_raw_vector_difference_um"].quantile(0.95)),
        "median_difference_of_step": float(valid["r61_raw_vector_difference_um"].median() / nominal_step_um),
        "p95_difference_of_step": float(valid["r61_raw_vector_difference_um"].quantile(0.95) / nominal_step_um),
        "median_response_ratio": float(response_ratio.median()),
        "median_r61_ecc": float(valid["r61_ecc"].median()),
        "raw_median_abs_dx_um": float(valid["raw_dx_px"].abs().median() * object_um_per_px),
        "r61_median_abs_dx_um": float(valid["r61_dx_px"].abs().median() * object_um_per_px),
    }
    return rows, summary


def apply_gates(summary: pd.DataFrame, gates: dict) -> pd.DataFrame:
    output = summary.copy()
    output["pass_valid_fraction"] = output["valid_fraction"] >= gates["minimum_valid_fraction"]
    output["pass_direction"] = output["direction_agreement_fraction"] >= gates["minimum_direction_agreement"]
    output["pass_scale"] = output["median_scale_error_fraction"] <= gates["maximum_median_scale_error_fraction"]
    output["pass_median_difference"] = output["median_difference_of_step"] <= gates["maximum_median_difference_of_step"]
    output["pass_p95_difference"] = output["p95_difference_of_step"] <= gates["maximum_p95_difference_of_step"]
    output["pass_response"] = output["median_response_ratio"] >= gates["minimum_median_response_ratio"]
    output["pass_ecc"] = output["median_r61_ecc"] >= gates["minimum_median_ecc"]
    checks = [c for c in output.columns if c.startswith("pass_")]
    output["sequence_pass"] = output[checks].all(axis=1)
    return output


def write_report(summary: pd.DataFrame, audit: dict) -> None:
    overall = bool(summary["sequence_pass"].all())
    lines = [
        "# R68 Results", "", "## Outcome", "",
        f"- R61v16 real-FOV pilot result: **{'PASS' if overall else 'FAIL'}**.",
        f"- Validated input coverage: {audit['total_frames']} Raw frames and {audit['total_frames']} matching R61 reconstructions.",
        "- Evidence scope: external to R61v16 training; cross-magnification and cross-field within the available acquisitions.",
        "- Universal cross-sample claim: not made until physical sample identity is confirmed and additional samples are tested.",
        "", "## Sequence results", "",
        "| Sequence | Raw usable | R61 valid | Direction | Motion scale | Median difference | P95 difference | Response | Result |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in summary.iterrows():
        lines.append(
            f"| {row['sequence']} | {row['raw_reference_fraction']:.1%} | {row['valid_fraction']:.1%} | "
            f"{row['direction_agreement_fraction']:.1%} | "
            f"{row['median_r61_over_raw_abs_dx']:.3f} | {row['median_vector_difference_um']*1000:.1f} nm | "
            f"{row['p95_vector_difference_um']*1000:.1f} nm | {row['median_response_ratio']:.3f} | "
            f"{'PASS' if row['sequence_pass'] else 'FAIL'} |"
        )
    failed = summary.loc[~summary["sequence_pass"], "sequence"].tolist()
    lines += [
        "", "## Interpretation", "",
        "Each sequence was evaluated on 24 automatically selected content-rich regions across the full field of view. Long acquisition pauses were excluded. The model is judged against the Raw motion measured from the same region, so periodic patterns and local sample defects cannot be hidden by a single central crop.",
        "",
        "Raw usable is fixed from the Raw images before R61 is judged. Local pairs with ambiguous Raw motion are excluded from the R61-valid denominator; this mainly affects the periodic 50x fields and prevents an ambiguous reference from being mislabeled as either model success or model failure.",
        "",
        ("All six sequences passed every pilot gate." if overall else f"Failed sequence(s): {', '.join(failed)}."),
        "",
        "A pass supports R61v16 as the current cross-magnification candidate. It does not prove all future HS100MG samples will pass.",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_analysis(config: dict, audit: dict) -> pd.DataFrame:
    all_rows, summaries = [], []
    for name, item in config["sequences"].items():
        print(f"[analyze] {name}", flush=True)
        rows, summary = analyze_sequence(name, item, config)
        all_rows.extend(rows)
        summaries.append(summary)
    TABLES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_rows).to_csv(TABLES / "tile_motion_measurements.csv", index=False)
    summary = apply_gates(pd.DataFrame(summaries), config["gates"])
    summary.to_csv(TABLES / "sequence_summary.csv", index=False)
    decision = {
        "model": "R61v16", "pilot_pass": bool(summary["sequence_pass"].all()),
        "passed_sequences": summary.loc[summary["sequence_pass"], "sequence"].tolist(),
        "failed_sequences": summary.loc[~summary["sequence_pass"], "sequence"].tolist(),
        "universal_cross_sample_pass": False,
        "reason_universal_not_claimed": "physical sample identity is not yet recorded and only two acquisition dates are represented",
    }
    (RESULTS / "gate_decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    write_report(summary, audit)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["validate", "analyze", "all"], default="all")
    args = parser.parse_args()
    config = read_json(CONFIG_PATH)
    audit = validate_inputs(config)
    print(f"[validate] {audit['total_frames']} Raw/R61 frame pairs passed", flush=True)
    if args.stage in {"analyze", "all"}:
        summary = run_analysis(config, audit)
        print(summary.to_string(index=False), flush=True)
        print(f"[report] {REPORT}", flush=True)


if __name__ == "__main__":
    main()
