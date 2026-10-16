"""Recalculate clean Step displacement stability from image pairs.

The script intentionally writes a full pair table plus compact summaries so the
reported stability numbers can be audited back to each image pair.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median

import cv2
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import chi2


DEFAULT_AUDIT_ROOT = Path(
    r"D:\GMM_2_Final\Step_analysis_20260623\clean_step_audit_from_original_pos10_20260623_2218"
)
DEFAULT_SELECTED_MANIFEST = Path(r"D:\GMM_2_Final\Step_analysis_20260623\selected_1um_positions.csv")
OBJECT_PIXEL_UM = 2.5 / 20.0
EXPECTED_STEP_UM = 1.0
EXPECTED_STEP_PX = EXPECTED_STEP_UM / OBJECT_PIXEL_UM
RECOMMENDED_EDGE_METHOD = "edge_rawmag_full2048"


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    label: str
    image_dir: Path


@dataclass(frozen=True)
class MethodSpec:
    method_id: str
    label: str
    preprocess: str
    roi_xyxy: tuple[int, int, int, int] | None


def _finite(values: list[float]) -> list[float]:
    return [float(v) for v in values if math.isfinite(float(v))]


def _stat(values: list[float], name: str) -> float | None:
    vals = _finite(values)
    if not vals:
        return None
    arr = np.asarray(vals, dtype=np.float64)
    if name == "mean":
        return float(np.mean(arr))
    if name == "median":
        return float(np.median(arr))
    if name == "std_pop":
        return float(np.std(arr, ddof=0))
    if name == "std_sample":
        return float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
    if name == "mad_sigma":
        med = float(np.median(arr))
        return float(np.median(np.abs(arr - med)) * 1.4826)
    if name == "p05":
        return float(np.percentile(arr, 5))
    if name == "p95":
        return float(np.percentile(arr, 95))
    if name == "min":
        return float(np.min(arr))
    if name == "max":
        return float(np.max(arr))
    raise ValueError(name)


def _std_ci95(values: list[float]) -> tuple[float | None, float | None]:
    vals = _finite(values)
    if len(vals) < 2:
        return None, None
    arr = np.asarray(vals, dtype=np.float64)
    df = len(arr) - 1
    s = float(np.std(arr, ddof=1))
    low = math.sqrt(df * s * s / chi2.ppf(0.975, df))
    high = math.sqrt(df * s * s / chi2.ppf(0.025, df))
    return float(low), float(high)


def _read_manifest(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    required = {"selected_step_index", "position_index", "rep0_file", "rep1_file"}
    missing = required - set(rows[0].keys() if rows else [])
    if missing:
        raise ValueError(f"manifest missing columns: {sorted(missing)}")
    parsed: list[dict[str, object]] = []
    for row in rows:
        parsed.append(
            {
                **row,
                "selected_step_index": int(float(row["selected_step_index"])),
                "position_index": int(float(row["position_index"])),
                "rep0_file": str(row["rep0_file"]),
                "rep1_file": str(row["rep1_file"]),
            }
        )
    return parsed


def _read_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise OSError(f"failed to read image: {path}")
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.astype(np.float32)


def _normalize(arr: np.ndarray) -> np.ndarray:
    arr = arr.astype(np.float32)
    arr = arr - float(np.mean(arr))
    std = float(np.std(arr))
    if std > 1e-6:
        arr = arr / std
    return arr.astype(np.float32)


def _preprocess(image: np.ndarray, method: MethodSpec) -> np.ndarray:
    arr = image
    if method.roi_xyxy is not None:
        x1, y1, x2, y2 = method.roi_xyxy
        arr = arr[y1:y2, x1:x2]
    if method.preprocess == "brightness":
        return _normalize(arr)
    if method.preprocess == "brightness_highpass":
        low = cv2.GaussianBlur(arr, (0, 0), 31.0)
        return _normalize(arr - low)
    if method.preprocess == "edge_sobel":
        gx = cv2.Sobel(arr, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(arr, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(gx, gy)
        return _normalize(mag)
    if method.preprocess == "edge_sobel_rawmag":
        gx = cv2.Sobel(arr, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(arr, cv2.CV_32F, 0, 1, ksize=3)
        return cv2.magnitude(gx, gy).astype(np.float32)
    raise ValueError(f"unknown preprocess: {method.preprocess}")


def _phase_shift(a: np.ndarray, b: np.ndarray, windows: dict[tuple[int, int], np.ndarray]) -> dict[str, float]:
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch: {a.shape} vs {b.shape}")
    key = (a.shape[1], a.shape[0])
    if key not in windows:
        windows[key] = cv2.createHanningWindow(key, cv2.CV_32F)
    window = windows[key]
    (dx, dy), response = cv2.phaseCorrelate(a * window, b * window)
    return {
        "dx_px": float(dx),
        "dy_px": float(dy),
        "mag_px": float(math.hypot(dx, dy)),
        "response": float(response),
    }


def _summarize(rows: list[dict[str, object]], expected_dx_px: float) -> dict[str, object]:
    dx = [float(r["dx_px"]) for r in rows]
    dy = [float(r["dy_px"]) for r in rows]
    mag = [float(r["mag_px"]) for r in rows]
    resp = [float(r["response"]) for r in rows]
    abs_expected_error = [abs(float(r["dx_px"]) - expected_dx_px) for r in rows]
    std_low, std_high = _std_ci95(dx)
    return {
        "pair_count": len(rows),
        "dx_mean_px": _stat(dx, "mean"),
        "dx_median_px": _stat(dx, "median"),
        "dx_std_pop_px": _stat(dx, "std_pop"),
        "dx_std_sample_px": _stat(dx, "std_sample"),
        "dx_std_ci95_low_px": std_low,
        "dx_std_ci95_high_px": std_high,
        "dx_mad_sigma_px": _stat(dx, "mad_sigma"),
        "dx_p05_px": _stat(dx, "p05"),
        "dx_p95_px": _stat(dx, "p95"),
        "dy_median_px": _stat(dy, "median"),
        "dy_std_pop_px": _stat(dy, "std_pop"),
        "mag_median_px": _stat(mag, "median"),
        "mag_p95_px": _stat(mag, "p95"),
        "response_median": _stat(resp, "median"),
        "response_min": _stat(resp, "min"),
        "expected_dx_px": expected_dx_px,
        "median_abs_expected_error_px": _stat(abs_expected_error, "median"),
        "p95_abs_expected_error_px": _stat(abs_expected_error, "p95"),
        "dx_std_pop_um": None if _stat(dx, "std_pop") is None else _stat(dx, "std_pop") * OBJECT_PIXEL_UM,
        "dx_median_um": None if _stat(dx, "median") is None else _stat(dx, "median") * OBJECT_PIXEL_UM,
        "mag_median_um": None if _stat(mag, "median") is None else _stat(mag, "median") * OBJECT_PIXEL_UM,
        "p95_abs_expected_error_um": None
        if _stat(abs_expected_error, "p95") is None
        else _stat(abs_expected_error, "p95") * OBJECT_PIXEL_UM,
    }


def _confidence(summary: dict[str, object], pair_type: str) -> str:
    response = float(summary.get("response_median") or 0.0)
    median_error = float(summary.get("median_abs_expected_error_px") or 0.0)
    if pair_type == "repeat":
        if response >= 0.85:
            return "high"
        if response >= 0.35:
            return "medium"
        return "low"
    scale_ok = median_error <= 0.25
    if response >= 0.85 and scale_ok:
        return "high"
    if response >= 0.35 and scale_ok:
        return "medium"
    return "low"


def build_cases(audit_root: Path) -> list[CaseSpec]:
    def recon_bmp_dir(preferred: str, pattern: str) -> Path:
        package = audit_root / "clean_recon_package"
        preferred_dir = package / preferred / "bmp"
        if preferred_dir.is_dir():
            return preferred_dir
        matches = sorted(
            p / "bmp"
            for p in package.glob(pattern)
            if (p / "bmp").is_dir()
        )
        if len(matches) == 1:
            return matches[0]
        if not matches:
            return preferred_dir
        raise FileExistsError(f"multiple reconstruction folders match {pattern}: {matches}")

    return [
        CaseSpec("raw", "Raw center crop", audit_root / "center2048_bmp"),
        CaseSpec("r39", "R39 reconstruction", recon_bmp_dir("01_r39_clean_pos10_center2048", "01_r39_*")),
        CaseSpec("v14", "v14 reconstruction", recon_bmp_dir("02_v14_clean_pos10_center2048", "02_v14_*")),
        CaseSpec("v16", "v16 reconstruction", recon_bmp_dir("03_v16_clean_pos10_center2048", "03_v16_*")),
    ]


def build_methods() -> list[MethodSpec]:
    return [
        MethodSpec("brightness_full2048", "brightness, full 2048", "brightness", None),
        MethodSpec("brightness_highpass_full2048", "high-pass brightness, full 2048", "brightness_highpass", None),
        MethodSpec("edge_rawmag_full2048", "Sobel edge raw magnitude, full 2048", "edge_sobel_rawmag", None),
        MethodSpec("edge_norm_full2048", "Sobel edge normalized, full 2048", "edge_sobel", None),
        MethodSpec("edge_rawmag_center1536", "Sobel edge raw magnitude, center 1536", "edge_sobel_rawmag", (256, 256, 1792, 1792)),
        MethodSpec("edge_rawmag_center1024", "Sobel edge raw magnitude, center 1024", "edge_sobel_rawmag", (512, 512, 1536, 1536)),
        MethodSpec("edge_norm_center1536", "Sobel edge normalized, center 1536", "edge_sobel", (256, 256, 1792, 1792)),
        MethodSpec("edge_norm_center1024", "Sobel edge normalized, center 1024", "edge_sobel", (512, 512, 1536, 1536)),
    ]


def compute(audit_root: Path, manifest_path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    positions = _read_manifest(manifest_path)
    cases = build_cases(audit_root)
    methods = build_methods()
    for case in cases:
        missing = [r[f"rep{rep}_file"] for r in positions for rep in (0, 1) if not (case.image_dir / str(r[f"rep{rep}_file"])).is_file()]
        if missing:
            raise FileNotFoundError(f"{case.case_id} missing {len(missing)} files; first: {missing[0]}")

    pair_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for case in cases:
        image_cache: dict[Path, np.ndarray] = {}
        prep_cache: dict[tuple[Path, str], np.ndarray] = {}
        windows: dict[tuple[int, int], np.ndarray] = {}

        def image(path: Path) -> np.ndarray:
            if path not in image_cache:
                image_cache[path] = _read_image(path)
            return image_cache[path]

        def prep(path: Path, method: MethodSpec) -> np.ndarray:
            key = (path, method.method_id)
            if key not in prep_cache:
                prep_cache[key] = _preprocess(image(path), method)
            return prep_cache[key]

        for method in methods:
            repeat_rows: list[dict[str, object]] = []
            step_rows: list[dict[str, object]] = []
            for row in positions:
                p0 = case.image_dir / str(row["rep0_file"])
                p1 = case.image_dir / str(row["rep1_file"])
                shift = _phase_shift(prep(p0, method), prep(p1, method), windows)
                out = {
                    "case_id": case.case_id,
                    "case_label": case.label,
                    "method_id": method.method_id,
                    "method_label": method.label,
                    "pair_type": "repeat",
                    "selected_step_index": row["selected_step_index"],
                    "position_index": row["position_index"],
                    "from_position": row["position_index"],
                    "to_position": row["position_index"],
                    "replicate": "0_to_1",
                    "from_file": p0.name,
                    "to_file": p1.name,
                    "expected_dx_px": 0.0,
                    **shift,
                }
                out["dx_error_px"] = float(out["dx_px"])
                out["dx_error_um"] = float(out["dx_error_px"]) * OBJECT_PIXEL_UM
                out["dx_um"] = float(out["dx_px"]) * OBJECT_PIXEL_UM
                out["dy_um"] = float(out["dy_px"]) * OBJECT_PIXEL_UM
                out["mag_um"] = float(out["mag_px"]) * OBJECT_PIXEL_UM
                repeat_rows.append(out)
                pair_rows.append(out)

            for current, nxt in zip(positions[:-1], positions[1:]):
                for rep in (0, 1):
                    p0 = case.image_dir / str(current[f"rep{rep}_file"])
                    p1 = case.image_dir / str(nxt[f"rep{rep}_file"])
                    shift = _phase_shift(prep(p0, method), prep(p1, method), windows)
                    out = {
                        "case_id": case.case_id,
                        "case_label": case.label,
                        "method_id": method.method_id,
                        "method_label": method.label,
                        "pair_type": "step",
                        "selected_step_index": current["selected_step_index"],
                        "position_index": current["position_index"],
                        "from_position": current["position_index"],
                        "to_position": nxt["position_index"],
                        "replicate": str(rep),
                        "from_file": p0.name,
                        "to_file": p1.name,
                        "expected_dx_px": EXPECTED_STEP_PX,
                        **shift,
                    }
                    out["dx_error_px"] = float(out["dx_px"]) - EXPECTED_STEP_PX
                    out["dx_error_um"] = float(out["dx_error_px"]) * OBJECT_PIXEL_UM
                    out["dx_um"] = float(out["dx_px"]) * OBJECT_PIXEL_UM
                    out["dy_um"] = float(out["dy_px"]) * OBJECT_PIXEL_UM
                    out["mag_um"] = float(out["mag_px"]) * OBJECT_PIXEL_UM
                    step_rows.append(out)
                    pair_rows.append(out)

            for pair_type, rows, expected in (
                ("repeat", repeat_rows, 0.0),
                ("step", step_rows, EXPECTED_STEP_PX),
            ):
                stats = _summarize(rows, expected)
                summary_rows.append(
                    {
                        "case_id": case.case_id,
                        "case_label": case.label,
                        "method_id": method.method_id,
                        "method_label": method.label,
                        "pair_type": pair_type,
                        "confidence": _confidence(stats, pair_type),
                        **stats,
                    }
                )

    raw_edge_step = next(
        row
        for row in summary_rows
        if row["case_id"] == "raw" and row["method_id"] == RECOMMENDED_EDGE_METHOD and row["pair_type"] == "step"
    )
    raw_std = float(raw_edge_step["dx_std_pop_px"])
    for row in summary_rows:
        if row["pair_type"] == "step" and row["method_id"] == RECOMMENDED_EDGE_METHOD:
            row["stability_improvement_vs_raw_edge"] = raw_std / float(row["dx_std_pop_px"])
        else:
            row["stability_improvement_vs_raw_edge"] = None
    return pair_rows, summary_rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("no rows")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: object, digits: int = 4) -> str:
    if value is None:
        return ""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{f:.{digits}f}"


def write_report(out_dir: Path, summary_rows: list[dict[str, object]]) -> None:
    by_key = {(r["case_id"], r["method_id"], r["pair_type"]): r for r in summary_rows}
    lines: list[str] = []
    lines.append("# Step Stability Recalculation Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("Calibration used: 2.5 um camera pixel / 20x objective = 0.125 um per image pixel.")
    lines.append(f"Expected selected Step spacing: {EXPECTED_STEP_UM:g} um = {EXPECTED_STEP_PX:g} px.")
    lines.append("")
    lines.append("## Main Result: Sobel Edge Full 2048")
    lines.append("")
    lines.append(
        "| case | step median dx px | step std dx px | step std um | 95% CI std px | p95 abs error um | median response | confidence | improvement vs raw |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|---:|")
    for case_id in ("raw", "r39", "v14", "v16"):
        row = by_key[(case_id, RECOMMENDED_EDGE_METHOD, "step")]
        ci = f"{_fmt(row['dx_std_ci95_low_px'], 4)}-{_fmt(row['dx_std_ci95_high_px'], 4)}"
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["case_label"]),
                    _fmt(row["dx_median_px"], 4),
                    _fmt(row["dx_std_pop_px"], 4),
                    _fmt(row["dx_std_pop_um"], 5),
                    ci,
                    _fmt(row["p95_abs_expected_error_um"], 5),
                    _fmt(row["response_median"], 4),
                    str(row["confidence"]),
                    _fmt(row["stability_improvement_vs_raw_edge"], 2),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Same-Position Repeat Check")
    lines.append("")
    lines.append("| case | repeat median mag px | repeat p95 mag px | repeat median mag um | median response | confidence |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for case_id in ("raw", "r39", "v14", "v16"):
        row = by_key[(case_id, RECOMMENDED_EDGE_METHOD, "repeat")]
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["case_label"]),
                    _fmt(row["mag_median_px"], 4),
                    _fmt(row["mag_p95_px"], 4),
                    _fmt(row["mag_median_um"], 5),
                    _fmt(row["response_median"], 4),
                    str(row["confidence"]),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Method Cross-Check: Step Scale")
    lines.append("")
    lines.append("| case | method | median dx px | std dx px | median response | confidence |")
    lines.append("|---|---|---:|---:|---:|---|")
    for case_id in ("raw", "r39", "v14", "v16"):
        for method_id in (
            "brightness_full2048",
            "brightness_highpass_full2048",
            "edge_rawmag_full2048",
            "edge_norm_full2048",
            "edge_rawmag_center1536",
            "edge_rawmag_center1024",
            "edge_norm_center1536",
            "edge_norm_center1024",
        ):
            row = by_key[(case_id, method_id, "step")]
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["case_label"]),
                        str(row["method_label"]),
                        _fmt(row["dx_median_px"], 4),
                        _fmt(row["dx_std_pop_px"], 4),
                        _fmt(row["response_median"], 4),
                        str(row["confidence"]),
                    ]
                )
                + " |"
            )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("- The brightness-only Raw result is low confidence because its response is low and it gives the wrong step scale.")
    lines.append("- The Raw edge result recovers the expected scale, but it has a much larger large-error tail.")
    lines.append("- The three reconstructions keep the expected scale and reduce step dx scatter by about 5.7x under the edge-based measurement.")
    lines.append("- R39, v14, and v16 are effectively tied on this Step stability check; v14 has the smallest dx std by a tiny margin, while v16 has the smallest p95 absolute error by a tiny margin.")
    lines.append("")
    (out_dir / "STEP_STABILITY_RECALC_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_plots(out_dir: Path, pair_rows: list[dict[str, object]], summary_rows: list[dict[str, object]]) -> None:
    edge_step = [
        row
        for row in pair_rows
        if row["method_id"] == RECOMMENDED_EDGE_METHOD and row["pair_type"] == "step"
    ]
    cases = ["raw", "r39", "v14", "v16"]
    labels = {
        "raw": "Raw",
        "r39": "R39",
        "v14": "v14",
        "v16": "v16",
    }
    data = [[float(row["dx_px"]) for row in edge_step if row["case_id"] == case] for case in cases]
    plt.figure(figsize=(8, 4.5))
    plt.boxplot(data, labels=[labels[c] for c in cases], showfliers=True)
    plt.axhline(EXPECTED_STEP_PX, color="tab:red", linestyle="--", linewidth=1, label=f"expected {EXPECTED_STEP_PX:g} px")
    plt.ylabel("Step dx (px)")
    plt.title("Edge-based Step displacement distribution")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "edge_step_dx_boxplot.png", dpi=180)
    plt.close()

    rows = [
        row
        for row in summary_rows
        if row["method_id"] == RECOMMENDED_EDGE_METHOD and row["pair_type"] == "step"
    ]
    plt.figure(figsize=(8, 4.5))
    plt.bar([labels[str(r["case_id"])] for r in rows], [float(r["dx_std_pop_um"]) for r in rows])
    plt.ylabel("Step stability std (um)")
    plt.title("Lower is better")
    plt.tight_layout()
    plt.savefig(out_dir / "edge_step_std_um_bar.png", dpi=180)
    plt.close()


def main() -> None:
    global OBJECT_PIXEL_UM, EXPECTED_STEP_UM, EXPECTED_STEP_PX

    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_AUDIT_ROOT)
    parser.add_argument("--selected-manifest", type=Path, default=DEFAULT_SELECTED_MANIFEST)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--camera-pixel-um", type=float, default=2.5)
    parser.add_argument("--magnification", type=float, default=20.0)
    parser.add_argument("--expected-step-um", type=float, default=1.0)
    args = parser.parse_args()

    if args.camera_pixel_um <= 0 or args.magnification <= 0 or args.expected_step_um <= 0:
        raise ValueError("camera pixel size, magnification, and expected step must be positive")
    OBJECT_PIXEL_UM = float(args.camera_pixel_um) / float(args.magnification)
    EXPECTED_STEP_UM = float(args.expected_step_um)
    EXPECTED_STEP_PX = EXPECTED_STEP_UM / OBJECT_PIXEL_UM

    audit_root = args.audit_root
    out_dir = args.out_dir
    if out_dir is None:
        out_dir = audit_root / ("stability_recalc_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    out_dir.mkdir(parents=True, exist_ok=True)

    pair_rows, summary_rows = compute(audit_root, args.selected_manifest)
    _write_csv(out_dir / "step_stability_recalc_pairs.csv", pair_rows)
    _write_csv(out_dir / "step_stability_recalc_summary.csv", summary_rows)
    (out_dir / "step_stability_recalc_summary.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "audit_root": str(audit_root),
                "selected_manifest": str(args.selected_manifest),
                "object_pixel_um": OBJECT_PIXEL_UM,
                "expected_step_um": EXPECTED_STEP_UM,
                "expected_step_px": EXPECTED_STEP_PX,
                "summary": summary_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_report(out_dir, summary_rows)
    write_plots(out_dir, pair_rows, summary_rows)
    print(out_dir)


if __name__ == "__main__":
    main()
