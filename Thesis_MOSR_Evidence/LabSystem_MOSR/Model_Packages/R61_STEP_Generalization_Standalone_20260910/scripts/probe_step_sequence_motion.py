"""Step-sequence local motion probe for the v15 Step guard."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import median

import cv2
import numpy as np


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT
DEFAULT_STEP_ROOT = PACKAGE_ROOT / "step_inputs"
DEFAULT_ANALYSIS_ROOT = PACKAGE_ROOT / "results" / "step_motion_probe"
DEFAULT_SELECTED_MANIFEST = DEFAULT_ANALYSIS_ROOT / "selected_1um_positions.csv"
DEFAULT_OUT_JSON = DEFAULT_ANALYSIS_ROOT / "step_motion_probe_summary.json"
DEFAULT_OUT_CSV = DEFAULT_ANALYSIS_ROOT / "step_motion_probe_pairs.csv"
DEFAULT_OUT_MD = DEFAULT_ANALYSIS_ROOT / "STEP_MOTION_PROBE_SUMMARY.md"


def _as_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _finite(values: list[float]) -> list[float]:
    return [float(v) for v in values if math.isfinite(float(v))]


def _mean(values: list[float]) -> float | None:
    vals = _finite(values)
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def _median(values: list[float]) -> float | None:
    vals = _finite(values)
    if not vals:
        return None
    return float(median(vals))


def _std_pop(values: list[float]) -> float | None:
    vals = _finite(values)
    if not vals:
        return None
    mu = sum(vals) / len(vals)
    return float(math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals)))


def _percentile(values: list[float], q: float) -> float | None:
    vals = _finite(values)
    if not vals:
        return None
    return float(np.percentile(np.asarray(vals, dtype=np.float64), q))


def _normalize(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    arr = image.astype(np.float32)
    arr -= float(np.mean(arr))
    std = float(np.std(arr))
    if std > 1e-6:
        arr /= std
    return arr.astype(np.float32)


def _resolve_image(image_folder: Path, filename: str, fallback_path: str | None = None) -> Path:
    candidate = Path(image_folder) / filename
    if candidate.is_file():
        return candidate
    if fallback_path:
        fallback = Path(fallback_path)
        if fallback.is_file():
            return fallback
    raise FileNotFoundError(f"missing image for Step manifest row: {filename}")


def estimate_pair_shift(image0: np.ndarray, image1: np.ndarray, roi_xyxy: tuple[int, int, int, int] | None = None) -> dict[str, float]:
    if roi_xyxy is not None:
        x1, y1, x2, y2 = roi_xyxy
        image0 = image0[y1:y2, x1:x2]
        image1 = image1[y1:y2, x1:x2]
    a = _normalize(image0)
    b = _normalize(image1)
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch: {a.shape} vs {b.shape}")
    window = cv2.createHanningWindow((a.shape[1], a.shape[0]), cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a * window, b * window)
    return {
        "dx_px": float(dx),
        "dy_px": float(dy),
        "mag_px": float(math.hypot(dx, dy)),
        "response": float(response),
    }


def load_selected_positions(manifest_path: Path) -> list[dict[str, object]]:
    with Path(manifest_path).open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    required = {"position_index", "rep0_file", "rep1_file"}
    missing = required - set(rows[0].keys() if rows else [])
    if missing:
        raise ValueError(f"selected Step manifest missing columns: {sorted(missing)}")
    parsed: list[dict[str, object]] = []
    for idx, row in enumerate(rows):
        parsed.append(
            {
                **row,
                "selected_step_index": int(float(row.get("selected_step_index", idx))),
                "position_index": int(float(row["position_index"])),
                "commanded_um_from_start": _as_float(row.get("commanded_um_from_start")),
            }
        )
    return parsed


def _read_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise OSError(f"failed to read image: {path}")
    return image


def _summarize_prefix(prefix: str, rows: list[dict[str, object]]) -> dict[str, object]:
    dx = [float(row["dx_px"]) for row in rows]
    dy = [float(row["dy_px"]) for row in rows]
    mag = [float(row["mag_px"]) for row in rows]
    response = [float(row["response"]) for row in rows]
    return {
        f"{prefix}_pair_count": len(rows),
        f"{prefix}_mean_dx_px": _mean(dx),
        f"{prefix}_median_dx_px": _median(dx),
        f"{prefix}_std_dx_px": _std_pop(dx),
        f"{prefix}_mean_dy_px": _mean(dy),
        f"{prefix}_median_dy_px": _median(dy),
        f"{prefix}_std_dy_px": _std_pop(dy),
        f"{prefix}_mean_mag_px": _mean(mag),
        f"{prefix}_median_mag_px": _median(mag),
        f"{prefix}_std_mag_px": _std_pop(mag),
        f"{prefix}_p95_mag_px": _percentile(mag, 95),
        f"{prefix}_max_mag_px": max(_finite(mag)) if _finite(mag) else None,
        f"{prefix}_median_response": _median(response),
    }


def compute_step_case_stats(
    case_name: str,
    image_folder: Path,
    manifest_path: Path,
    *,
    roi_xyxy: tuple[int, int, int, int] | None = None,
) -> dict[str, object]:
    positions = load_selected_positions(Path(manifest_path))
    if len(positions) < 2:
        raise ValueError("need at least two selected Step positions")

    repeat_pairs: list[dict[str, object]] = []
    step_pairs: list[dict[str, object]] = []
    cache: dict[Path, np.ndarray] = {}

    def image_for(path: Path) -> np.ndarray:
        if path not in cache:
            cache[path] = _read_image(path)
        return cache[path]

    for row in positions:
        rep0 = _resolve_image(Path(image_folder), str(row["rep0_file"]), str(row.get("rep0_path") or ""))
        rep1 = _resolve_image(Path(image_folder), str(row["rep1_file"]), str(row.get("rep1_path") or ""))
        shift = estimate_pair_shift(image_for(rep0), image_for(rep1), roi_xyxy=roi_xyxy)
        repeat_pairs.append(
            {
                "case": case_name,
                "pair_type": "same_position_repeat",
                "position_index": row["position_index"],
                "replicate": "0_to_1",
                "from_file": rep0.name,
                "to_file": rep1.name,
                **shift,
            }
        )

    for current, nxt in zip(positions[:-1], positions[1:]):
        commanded_delta_um = _as_float(nxt.get("commanded_um_from_start")) - _as_float(current.get("commanded_um_from_start"))
        for replicate in (0, 1):
            key = f"rep{replicate}_file"
            path_key = f"rep{replicate}_path"
            src = _resolve_image(Path(image_folder), str(current[key]), str(current.get(path_key) or ""))
            dst = _resolve_image(Path(image_folder), str(nxt[key]), str(nxt.get(path_key) or ""))
            shift = estimate_pair_shift(image_for(src), image_for(dst), roi_xyxy=roi_xyxy)
            step_pairs.append(
                {
                    "case": case_name,
                    "pair_type": "selected_step",
                    "from_position": current["position_index"],
                    "to_position": nxt["position_index"],
                    "commanded_delta_um": commanded_delta_um,
                    "replicate": str(replicate),
                    "from_file": src.name,
                    "to_file": dst.name,
                    **shift,
                }
            )

    replicate_stats: dict[str, dict[str, object]] = {}
    for replicate in ("0", "1"):
        rows = [row for row in step_pairs if row["replicate"] == replicate]
        replicate_stats[replicate] = _summarize_prefix("step", rows)

    return {
        "case": case_name,
        "image_folder": str(image_folder),
        "selected_manifest": str(manifest_path),
        "selected_position_count": len(positions),
        "first_position": positions[0]["position_index"],
        "last_position": positions[-1]["position_index"],
        **_summarize_prefix("repeat", repeat_pairs),
        **_summarize_prefix("step", step_pairs),
        "replicate_stats": replicate_stats,
        "pairs": repeat_pairs + step_pairs,
    }


def _case_by_name(summary: dict, case_name: str) -> dict:
    for row in summary.get("cases", []):
        if row.get("case") == case_name:
            return row
    raise KeyError(f"case not found in Step summary: {case_name}")


def evaluate_step_gate(
    step_summary: dict,
    *,
    baseline_case: str,
    candidate_case: str,
    metric: str = "step_std_dx_px",
    tolerance_px: float = 0.0,
) -> dict[str, object]:
    baseline_row = _case_by_name(step_summary, baseline_case)
    candidate_row = _case_by_name(step_summary, candidate_case)
    baseline = _as_float(baseline_row.get(metric))
    candidate = _as_float(candidate_row.get(metric))
    passed = math.isfinite(baseline) and math.isfinite(candidate) and candidate <= baseline + float(tolerance_px)
    return {
        "pass": bool(passed),
        "metric": metric,
        "baseline_case": baseline_case,
        "candidate_case": candidate_case,
        "baseline": None if not math.isfinite(baseline) else baseline,
        "candidate": None if not math.isfinite(candidate) else candidate,
        "delta": None if not math.isfinite(baseline) or not math.isfinite(candidate) else candidate - baseline,
        "tolerance_px": float(tolerance_px),
    }


def load_cases_from_tsv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    return [row for row in rows if row.get("case") and row.get("image_folder") and Path(row["image_folder"]).is_dir()]


def write_pairs_csv(path: Path, case_stats: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case",
        "pair_type",
        "position_index",
        "from_position",
        "to_position",
        "commanded_delta_um",
        "replicate",
        "from_file",
        "to_file",
        "dx_px",
        "dy_px",
        "mag_px",
        "response",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for stats in case_stats:
            for row in stats["pairs"]:
                writer.writerow({field: row.get(field, "") for field in fieldnames})


def _fmt(value: object) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.6f}"
    except (TypeError, ValueError):
        return str(value)


def write_markdown(path: Path, payload: dict[str, object]) -> None:
    lines = [
        "# Step Motion Probe",
        "",
        "This is an image-only Step guard. It checks repeat captures and selected position +10 pairs.",
        "",
        "| case | selected positions | repeat median mag px | repeat p95 mag px | step median dx px | step std dx px | step median mag px | step median response |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["cases"]:
        lines.append(
            "| {case} | {n} | {repeat_med} | {repeat_p95} | {step_dx} | {step_std_dx} | {step_mag} | {step_resp} |".format(
                case=row["case"],
                n=row["selected_position_count"],
                repeat_med=_fmt(row["repeat_median_mag_px"]),
                repeat_p95=_fmt(row["repeat_p95_mag_px"]),
                step_dx=_fmt(row["step_median_dx_px"]),
                step_std_dx=_fmt(row["step_std_dx_px"]),
                step_mag=_fmt(row["step_median_mag_px"]),
                step_resp=_fmt(row["step_median_response"]),
            )
        )
    lines.append("")
    lines.append("The selected Step sequence is commanded by position index. The physical pixel scale mismatch remains an open calibration issue.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_roi(text: str | None) -> tuple[int, int, int, int] | None:
    if not text:
        return None
    values = [int(part.strip()) for part in text.split(",")]
    if len(values) != 4:
        raise ValueError("--roi-xyxy must contain x1,y1,x2,y2")
    return tuple(values)  # type: ignore[return-value]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe Step selected 1um motion consistency.")
    parser.add_argument("--paths-tsv", type=Path, help="Optional TSV with case and image_folder columns.")
    parser.add_argument("--case", default="raw_step")
    parser.add_argument("--image-folder", type=Path, default=DEFAULT_STEP_ROOT)
    parser.add_argument("--selected-manifest", type=Path, default=DEFAULT_SELECTED_MANIFEST)
    parser.add_argument("--roi-xyxy", default=None, help="Optional x1,y1,x2,y2 crop.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUT_MD)
    return parser


def run_probe(args: argparse.Namespace) -> dict[str, object]:
    roi_xyxy = _parse_roi(args.roi_xyxy)
    if args.paths_tsv:
        cases = load_cases_from_tsv(Path(args.paths_tsv))
    else:
        cases = [{"case": str(args.case), "image_folder": str(args.image_folder)}]
    stats = [
        compute_step_case_stats(row["case"], Path(row["image_folder"]), Path(args.selected_manifest), roi_xyxy=roi_xyxy)
        for row in cases
    ]
    payload = {
        "scope": "Step selected 1um local image-only motion probe",
        "formal_physical_accuracy_claim": False,
        "method": "OpenCV phase correlation on normalized selected-position pairs",
        "selected_manifest": str(Path(args.selected_manifest)),
        "roi_xyxy": list(roi_xyxy) if roi_xyxy else None,
        "cases": [{key: value for key, value in row.items() if key != "pairs"} for row in stats],
    }
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_pairs_csv(Path(args.output_csv), stats)
    write_markdown(Path(args.output_md), payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = run_probe(args)
    print(json.dumps({"cases": len(payload["cases"]), "output_json": str(args.output_json)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
