"""Fast edge-based Step displacement stability audit.

This is a focused companion to recalc_clean_step_stability.py for large Step
packages. It keeps the same edge phase-correlation readout, but avoids caching
every transformed 2048 image for every method at once.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import chi2


DEFAULT_CAMERA_PIXEL_UM = 2.5
DEFAULT_MAGNIFICATION = 20.0


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    label: str
    image_dir: Path


@dataclass(frozen=True)
class MethodSpec:
    method_id: str
    label: str
    roi_xyxy: tuple[int, int, int, int] | None


METHODS = [
    MethodSpec("edge_rawmag_full2048", "Sobel edge raw magnitude, full 2048", None),
    MethodSpec("edge_rawmag_center1024", "Sobel edge raw magnitude, center 1024", (512, 512, 1536, 1536)),
]


def read_manifest(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"empty manifest: {path}")
    required = {"selected_step_index", "position_index", "rep0_file", "rep1_file"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"manifest missing columns: {sorted(missing)}")
    parsed = []
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


def recon_bmp_dir(audit_root: Path, preferred: str, pattern: str) -> Path:
    package = audit_root / "clean_recon_package"
    preferred_dir = package / preferred / "bmp"
    if preferred_dir.is_dir():
        return preferred_dir
    matches = sorted(p / "bmp" for p in package.glob(pattern) if (p / "bmp").is_dir())
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return preferred_dir
    raise FileExistsError(f"multiple reconstruction folders match {pattern}: {matches}")


def build_cases(audit_root: Path) -> list[CaseSpec]:
    return [
        CaseSpec("raw", "Raw center crop", audit_root / "center2048_bmp"),
        CaseSpec("r39", "R39 reconstruction", recon_bmp_dir(audit_root, "01_r39_clean_pos10_center2048", "01_r39_*")),
        CaseSpec("v14", "v14 reconstruction", recon_bmp_dir(audit_root, "02_v14_clean_pos10_center2048", "02_v14_*")),
        CaseSpec("v16", "v16 reconstruction", recon_bmp_dir(audit_root, "03_v16_clean_pos10_center2048", "03_v16_*")),
    ]


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise OSError(f"failed to read image: {path}")
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.astype(np.float32)


def edge_feature(path: Path, method: MethodSpec) -> np.ndarray:
    arr = read_gray(path)
    if method.roi_xyxy is not None:
        x1, y1, x2, y2 = method.roi_xyxy
        arr = arr[y1:y2, x1:x2]
    gx = cv2.Sobel(arr, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(arr, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy).astype(np.float32)


class FeatureCache:
    def __init__(self, method: MethodSpec, max_items: int) -> None:
        self.method = method
        self.max_items = max_items
        self.items: OrderedDict[Path, np.ndarray] = OrderedDict()

    def get(self, path: Path) -> np.ndarray:
        if path in self.items:
            value = self.items.pop(path)
            self.items[path] = value
            return value
        value = edge_feature(path, self.method)
        self.items[path] = value
        while len(self.items) > self.max_items:
            self.items.popitem(last=False)
        return value


def finite(values: list[float]) -> list[float]:
    return [float(v) for v in values if math.isfinite(float(v))]


def stat(values: list[float], name: str) -> float | None:
    vals = finite(values)
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


def std_ci95(values: list[float]) -> tuple[float | None, float | None]:
    vals = finite(values)
    if len(vals) < 2:
        return None, None
    arr = np.asarray(vals, dtype=np.float64)
    df = len(arr) - 1
    s = float(np.std(arr, ddof=1))
    low = math.sqrt(df * s * s / chi2.ppf(0.975, df))
    high = math.sqrt(df * s * s / chi2.ppf(0.025, df))
    return float(low), float(high)


def phase_shift(a: np.ndarray, b: np.ndarray, windows: dict[tuple[int, int], np.ndarray]) -> dict[str, float]:
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch: {a.shape} vs {b.shape}")
    key = (a.shape[1], a.shape[0])
    if key not in windows:
        windows[key] = cv2.createHanningWindow(key, cv2.CV_32F)
    (dx, dy), response = cv2.phaseCorrelate(a * windows[key], b * windows[key])
    return {
        "dx_px": float(dx),
        "dy_px": float(dy),
        "mag_px": float(math.hypot(dx, dy)),
        "response": float(response),
    }


def summarize(rows: list[dict[str, object]], expected_dx_px: float, object_pixel_um: float) -> dict[str, object]:
    dx = [float(r["dx_px"]) for r in rows]
    dy = [float(r["dy_px"]) for r in rows]
    mag = [float(r["mag_px"]) for r in rows]
    resp = [float(r["response"]) for r in rows]
    abs_expected_error = [abs(float(r["dx_px"]) - expected_dx_px) for r in rows]
    std_low, std_high = std_ci95(dx)
    dx_std_pop = stat(dx, "std_pop")
    dx_median = stat(dx, "median")
    mag_median = stat(mag, "median")
    p95_abs = stat(abs_expected_error, "p95")
    return {
        "pair_count": len(rows),
        "dx_mean_px": stat(dx, "mean"),
        "dx_median_px": dx_median,
        "dx_std_pop_px": dx_std_pop,
        "dx_std_sample_px": stat(dx, "std_sample"),
        "dx_std_ci95_low_px": std_low,
        "dx_std_ci95_high_px": std_high,
        "dx_mad_sigma_px": stat(dx, "mad_sigma"),
        "dx_p05_px": stat(dx, "p05"),
        "dx_p95_px": stat(dx, "p95"),
        "dy_median_px": stat(dy, "median"),
        "dy_std_pop_px": stat(dy, "std_pop"),
        "mag_median_px": mag_median,
        "mag_p95_px": stat(mag, "p95"),
        "response_median": stat(resp, "median"),
        "response_min": stat(resp, "min"),
        "expected_dx_px": expected_dx_px,
        "median_abs_expected_error_px": stat(abs_expected_error, "median"),
        "p95_abs_expected_error_px": p95_abs,
        "dx_std_pop_um": None if dx_std_pop is None else dx_std_pop * object_pixel_um,
        "dx_median_um": None if dx_median is None else dx_median * object_pixel_um,
        "mag_median_um": None if mag_median is None else mag_median * object_pixel_um,
        "p95_abs_expected_error_um": None if p95_abs is None else p95_abs * object_pixel_um,
    }


def confidence(summary: dict[str, object], pair_type: str) -> str:
    response = float(summary.get("response_median") or 0.0)
    median_error = float(summary.get("median_abs_expected_error_px") or 0.0)
    if pair_type == "repeat":
        if response >= 0.85:
            return "high"
        if response >= 0.35:
            return "medium"
        return "low"
    if response >= 0.85 and median_error <= 0.25:
        return "high"
    if response >= 0.35 and median_error <= 0.25:
        return "medium"
    return "low"


def compute(
    audit_root: Path,
    manifest_path: Path,
    expected_step_um: float,
    camera_pixel_um: float,
    magnification: float,
    cache_items: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    object_pixel_um = camera_pixel_um / magnification
    expected_step_px = expected_step_um / object_pixel_um
    positions = read_manifest(manifest_path)
    cases = build_cases(audit_root)
    for case in cases:
        missing = [
            r[f"rep{rep}_file"]
            for r in positions
            for rep in (0, 1)
            if not (case.image_dir / str(r[f"rep{rep}_file"])).is_file()
        ]
        if missing:
            raise FileNotFoundError(f"{case.case_id} missing {len(missing)} files; first: {missing[0]}")

    pair_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for case in cases:
        for method in METHODS:
            cache = FeatureCache(method, cache_items)
            windows: dict[tuple[int, int], np.ndarray] = {}
            repeat_rows: list[dict[str, object]] = []
            step_rows: list[dict[str, object]] = []
            for idx, row in enumerate(positions):
                p0 = case.image_dir / str(row["rep0_file"])
                p1 = case.image_dir / str(row["rep1_file"])
                shift = phase_shift(cache.get(p0), cache.get(p1), windows)
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
                out["dx_error_um"] = float(out["dx_error_px"]) * object_pixel_um
                out["dx_um"] = float(out["dx_px"]) * object_pixel_um
                out["dy_um"] = float(out["dy_px"]) * object_pixel_um
                out["mag_um"] = float(out["mag_px"]) * object_pixel_um
                repeat_rows.append(out)
                pair_rows.append(out)

                if idx + 1 < len(positions):
                    nxt = positions[idx + 1]
                    for rep in (0, 1):
                        pa = case.image_dir / str(row[f"rep{rep}_file"])
                        pb = case.image_dir / str(nxt[f"rep{rep}_file"])
                        shift = phase_shift(cache.get(pa), cache.get(pb), windows)
                        out = {
                            "case_id": case.case_id,
                            "case_label": case.label,
                            "method_id": method.method_id,
                            "method_label": method.label,
                            "pair_type": "step",
                            "selected_step_index": row["selected_step_index"],
                            "position_index": row["position_index"],
                            "from_position": row["position_index"],
                            "to_position": nxt["position_index"],
                            "replicate": str(rep),
                            "from_file": pa.name,
                            "to_file": pb.name,
                            "expected_dx_px": expected_step_px,
                            **shift,
                        }
                        out["dx_error_px"] = float(out["dx_px"]) - expected_step_px
                        out["dx_error_um"] = float(out["dx_error_px"]) * object_pixel_um
                        out["dx_um"] = float(out["dx_px"]) * object_pixel_um
                        out["dy_um"] = float(out["dy_px"]) * object_pixel_um
                        out["mag_um"] = float(out["mag_px"]) * object_pixel_um
                        step_rows.append(out)
                        pair_rows.append(out)

            for pair_type, rows, expected in (("repeat", repeat_rows, 0.0), ("step", step_rows, expected_step_px)):
                stats = summarize(rows, expected, object_pixel_um)
                summary_rows.append(
                    {
                        "case_id": case.case_id,
                        "case_label": case.label,
                        "method_id": method.method_id,
                        "method_label": method.label,
                        "pair_type": pair_type,
                        "confidence": confidence(stats, pair_type),
                        **stats,
                    }
                )

    raw_main = next(
        r
        for r in summary_rows
        if r["case_id"] == "raw" and r["method_id"] == "edge_rawmag_full2048" and r["pair_type"] == "step"
    )
    raw_std = float(raw_main["dx_std_pop_px"])
    for row in summary_rows:
        if row["pair_type"] == "step" and row["method_id"] == "edge_rawmag_full2048":
            row["stability_improvement_vs_raw_edge"] = raw_std / float(row["dx_std_pop_px"])
        else:
            row["stability_improvement_vs_raw_edge"] = None

    meta = {
        "expected_step_um": expected_step_um,
        "camera_pixel_um": camera_pixel_um,
        "magnification": magnification,
        "object_pixel_um": object_pixel_um,
        "expected_step_px": expected_step_px,
        "position_count": len(positions),
        "case_count": len(cases),
        "method_count": len(METHODS),
    }
    return pair_rows, summary_rows, meta


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path}")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: object, digits: int = 4) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def write_report(out_dir: Path, summary_rows: list[dict[str, object]], meta: dict[str, object]) -> None:
    labels = {
        "raw": "Raw",
        "r39": "R39",
        "v14": "v14",
        "v16": "v16",
    }
    lines: list[str] = []
    lines.append("# Fast Edge Step Stability Report")
    lines.append("")
    lines.append(
        f"Expected step: {fmt(meta['expected_step_um'], 3)} um = {fmt(meta['expected_step_px'], 4)} px "
        f"({fmt(meta['object_pixel_um'], 4)} um/px)."
    )
    lines.append("")
    lines.append("## Main Edge Full 2048 Step Result")
    lines.append("")
    lines.append("| Case | Median dx px | Std px | Std um | P95 abs err um | Response | Confidence | Improvement vs Raw |")
    lines.append("|---|---:|---:|---:|---:|---:|---|---:|")
    for case_id in ("raw", "r39", "v14", "v16"):
        row = next(
            r
            for r in summary_rows
            if r["case_id"] == case_id and r["method_id"] == "edge_rawmag_full2048" and r["pair_type"] == "step"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    labels[case_id],
                    fmt(row["dx_median_px"], 4),
                    fmt(row["dx_std_pop_px"], 4),
                    fmt(row["dx_std_pop_um"], 5),
                    fmt(row["p95_abs_expected_error_um"], 5),
                    fmt(row["response_median"], 4),
                    str(row["confidence"]),
                    "" if row["stability_improvement_vs_raw_edge"] is None else fmt(row["stability_improvement_vs_raw_edge"], 2),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Same Position Repeat Floor")
    lines.append("")
    lines.append("| Case | Median dx px | Std px | Std um | Response | Confidence |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for case_id in ("raw", "r39", "v14", "v16"):
        row = next(
            r
            for r in summary_rows
            if r["case_id"] == case_id and r["method_id"] == "edge_rawmag_full2048" and r["pair_type"] == "repeat"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    labels[case_id],
                    fmt(row["dx_median_px"], 4),
                    fmt(row["dx_std_pop_px"], 4),
                    fmt(row["dx_std_pop_um"], 5),
                    fmt(row["response_median"], 4),
                    str(row["confidence"]),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Center 1024 Check")
    lines.append("")
    lines.append("| Case | Median dx px | Std px | Std um | P95 abs err um | Response | Confidence |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for case_id in ("raw", "r39", "v14", "v16"):
        row = next(
            r
            for r in summary_rows
            if r["case_id"] == case_id and r["method_id"] == "edge_rawmag_center1024" and r["pair_type"] == "step"
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    labels[case_id],
                    fmt(row["dx_median_px"], 4),
                    fmt(row["dx_std_pop_px"], 4),
                    fmt(row["dx_std_pop_um"], 5),
                    fmt(row["p95_abs_expected_error_um"], 5),
                    fmt(row["response_median"], 4),
                    str(row["confidence"]),
                ]
            )
            + " |"
        )
    lines.append("")
    (out_dir / "FAST_EDGE_STEP_STABILITY_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def write_plots(out_dir: Path, pair_rows: list[dict[str, object]], summary_rows: list[dict[str, object]], meta: dict[str, object]) -> None:
    labels = {"raw": "Raw", "r39": "R39", "v14": "v14", "v16": "v16"}
    cases = ["raw", "r39", "v14", "v16"]
    data = [
        [
            float(r["dx_px"])
            for r in pair_rows
            if r["case_id"] == case and r["method_id"] == "edge_rawmag_full2048" and r["pair_type"] == "step"
        ]
        for case in cases
    ]
    plt.figure(figsize=(10, 5))
    plt.boxplot(data, labels=[labels[c] for c in cases], showfliers=True)
    plt.axhline(float(meta["expected_step_px"]), color="crimson", linestyle="--", linewidth=1.2)
    plt.ylabel("dx (px)")
    plt.title(f"0.1um adjacent step dx, expected {float(meta['expected_step_px']):.4f}px")
    plt.tight_layout()
    plt.savefig(out_dir / "fast_edge_step_dx_boxplot.png", dpi=180)
    plt.close()

    std_um = [
        float(
            next(
                r
                for r in summary_rows
                if r["case_id"] == case and r["method_id"] == "edge_rawmag_full2048" and r["pair_type"] == "step"
            )["dx_std_pop_um"]
        )
        for case in cases
    ]
    plt.figure(figsize=(8, 4.5))
    plt.bar([labels[c] for c in cases], std_um)
    plt.ylabel("step dx std (um)")
    plt.title("0.1um step stability, lower is better")
    plt.tight_layout()
    plt.savefig(out_dir / "fast_edge_step_std_um_bar.png", dpi=180)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--selected-manifest", type=Path, required=True)
    parser.add_argument("--expected-step-um", type=float, required=True)
    parser.add_argument("--camera-pixel-um", type=float, default=DEFAULT_CAMERA_PIXEL_UM)
    parser.add_argument("--magnification", type=float, default=DEFAULT_MAGNIFICATION)
    parser.add_argument("--cache-items", type=int, default=8)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    out_dir = args.out_dir or (args.audit_root / f"stability_fast_edge_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    out_dir.mkdir(parents=True, exist_ok=False)
    pair_rows, summary_rows, meta = compute(
        args.audit_root,
        args.selected_manifest,
        args.expected_step_um,
        args.camera_pixel_um,
        args.magnification,
        args.cache_items,
    )
    meta = {**meta, "generated_at": datetime.now().isoformat(timespec="seconds"), "out_dir": str(out_dir)}
    write_csv(out_dir / "fast_edge_step_pairs.csv", pair_rows)
    write_csv(out_dir / "fast_edge_step_summary.csv", summary_rows)
    (out_dir / "fast_edge_step_summary.json").write_text(
        json.dumps({"meta": meta, "summary": summary_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_report(out_dir, summary_rows, meta)
    write_plots(out_dir, pair_rows, summary_rows, meta)
    print(json.dumps({"out_dir": str(out_dir), "meta": meta, "pair_rows": len(pair_rows), "summary_rows": len(summary_rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
