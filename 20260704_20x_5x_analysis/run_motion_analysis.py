from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
PROJECT_ROOT = Path(__file__).resolve().parents[1]


ROOT = Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis'))
OUT = ROOT / "motion_analysis"
OUT.mkdir(parents=True, exist_ok=True)

CAMERA_PIXEL_UM = 3.45
GROUPS = ["20x_1um", "20x_0p5um", "5x_1um", "5x_0p5um"]
LABELS = {"raw": "Raw", "r61_v16_psfoff": "R61 v16 PSF-off"}

METHODS = [
    {
        "method": "primary_grid_area_edge",
        "description": "Large sample-pattern area, excluding the left background/arrows; Sobel-edge phase correlation.",
        "roi": [560, 80, 2020, 1500],
        "primary": True,
    },
    {
        "method": "center_blocks_edge",
        "description": "Central mixed-pattern block; Sobel-edge phase correlation.",
        "roi": [900, 420, 1680, 1160],
        "primary": False,
    },
    {
        "method": "line_grating_edge",
        "description": "Lower line-grating area; Sobel-edge phase correlation.",
        "roi": [520, 860, 1900, 1530],
        "primary": False,
    },
    {
        "method": "dot_array_edge",
        "description": "Upper dot-array area; Sobel-edge phase correlation.",
        "roi": [520, 20, 1900, 860],
        "primary": False,
    },
    {
        "method": "left_unique_edge",
        "description": "Left unique area/background; kept as diagnostic only because it can include arrows/background.",
        "roi": [0, 0, 520, 1530],
        "primary": False,
    },
    {
        "method": "full_frame_edge",
        "description": "Full-frame Sobel-edge phase correlation; stress test.",
        "roi": None,
        "primary": False,
    },
]


def parse_group(group: str) -> tuple[str, float, float, float]:
    magnification_text, step_text = group.split("_", 1)
    magnification = float(magnification_text.replace("x", ""))
    nominal_step_um = 0.5 if "0p5" in step_text else 1.0
    object_um_per_px = CAMERA_PIXEL_UM / magnification
    expected_px = nominal_step_um / object_um_per_px
    return magnification_text, nominal_step_um, object_um_per_px, expected_px


def load_mapping() -> dict[tuple[str, str], dict[str, str]]:
    path = ROOT / "input_mapping.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return {(row["group"], row["work_name"]): row for row in rows}


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"failed to read {path}")
    return image


def crop(image: np.ndarray, roi: list[int] | None) -> np.ndarray:
    if roi is None:
        return image
    x0, y0, x1, y1 = roi
    return image[y0:y1, x0:x1]


def edge_preprocess(image: np.ndarray) -> np.ndarray:
    gray = image.astype(np.float32)
    blur = cv2.GaussianBlur(gray, (0, 0), 1.0)
    gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    arr = cv2.magnitude(gx, gy)
    arr -= float(arr.mean())
    std = float(arr.std())
    if std > 1e-6:
        arr /= std
    return arr.astype(np.float32)


def finite(values: list[object]) -> np.ndarray:
    out = []
    for value in values:
        if value == "":
            continue
        number = float(value)
        if math.isfinite(number):
            out.append(number)
    return np.array(out, dtype=float)


def case_folder(group: str, kind: str) -> Path:
    if kind == "raw":
        return ROOT / "raw_inputs" / group / "bmp"
    return ROOT / f"r61_v16_psfoff_{group}" / "bmp"


def pair_shifts(group: str, kind: str, method: dict[str, object], mapping: dict[tuple[str, str], dict[str, str]]) -> list[dict[str, object]]:
    folder = case_folder(group, kind)
    paths = sorted(folder.glob("*.bmp"))
    if len(paths) < 2:
        raise ValueError(f"not enough BMP files in {folder}")
    magnification, nominal_step_um, object_um_per_px, expected_px = parse_group(group)
    prepped = [edge_preprocess(crop(read_gray(path), method["roi"])) for path in paths]
    window = cv2.createHanningWindow((prepped[0].shape[1], prepped[0].shape[0]), cv2.CV_32F)
    rows: list[dict[str, object]] = []
    for idx, (a, b) in enumerate(zip(prepped, prepped[1:])):
        (dx, dy), response = cv2.phaseCorrelate(a, b, window)
        from_name = paths[idx].name
        to_name = paths[idx + 1].name
        from_map = mapping.get((group, from_name), {})
        to_map = mapping.get((group, to_name), {})
        time_gap_s: float | str = ""
        if from_map.get("timestamp") and to_map.get("timestamp"):
            t0 = datetime.strptime(from_map["timestamp"], "%Y-%m-%d %H:%M:%S")
            t1 = datetime.strptime(to_map["timestamp"], "%Y-%m-%d %H:%M:%S")
            time_gap_s = (t1 - t0).total_seconds()
        rows.append(
            {
                "group": group,
                "magnification": magnification,
                "nominal_step_um": nominal_step_um,
                "object_um_per_px_assumed": object_um_per_px,
                "expected_dx_px_from_command": expected_px,
                "kind": kind,
                "method": method["method"],
                "step_index": idx,
                "from": from_name,
                "to": to_name,
                "original_from": from_map.get("original_name", ""),
                "original_to": to_map.get("original_name", ""),
                "time_gap_s": time_gap_s,
                "dx_px": float(dx),
                "dy_px": float(dy),
                "abs_dx_px": abs(float(dx)),
                "abs_dy_px": abs(float(dy)),
                "response": float(response),
                "primary": bool(method["primary"]),
            }
        )
    return rows


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    keys = sorted({(r["group"], r["kind"], r["method"]) for r in rows})
    out: list[dict[str, object]] = []
    for group, kind, method in keys:
        rs = [r for r in rows if r["group"] == group and r["kind"] == kind and r["method"] == method]
        for subset, subset_rows in [
            ("all_steps", rs),
            ("gap_le_30s", [r for r in rs if r["time_gap_s"] == "" or float(r["time_gap_s"]) <= 30.0]),
        ]:
            if not subset_rows:
                continue
            dx = finite([r["dx_px"] for r in subset_rows])
            dy = finite([r["dy_px"] for r in subset_rows])
            absdx = np.abs(dx)
            absdy = np.abs(dy)
            response = finite([r["response"] for r in subset_rows])
            expected_px = float(subset_rows[0]["expected_dx_px_from_command"])
            nominal_step_um = float(subset_rows[0]["nominal_step_um"])
            inferred_um_per_px = nominal_step_um / float(np.median(absdx)) if float(np.median(absdx)) > 1e-9 else ""
            out.append(
                {
                    "group": group,
                    "magnification": subset_rows[0]["magnification"],
                    "kind": kind,
                    "method": method,
                    "subset": subset,
                    "n_steps": len(subset_rows),
                    "median_dx_px": float(np.median(dx)),
                    "mean_dx_px": float(dx.mean()),
                    "std_dx_px": float(dx.std(ddof=0)),
                    "median_abs_dx_px": float(np.median(absdx)),
                    "mean_abs_dx_px": float(absdx.mean()),
                    "std_abs_dx_px": float(absdx.std(ddof=0)),
                    "median_abs_dy_px": float(np.median(absdy)),
                    "mean_response": float(response.mean()),
                    "nominal_step_um": nominal_step_um,
                    "expected_dx_px_from_command": expected_px,
                    "median_abs_dx_minus_expected_px": float(np.median(absdx)) - expected_px,
                    "median_abs_dx_over_expected": float(np.median(absdx)) / expected_px if expected_px > 1e-9 else "",
                    "inferred_um_per_px_from_median": inferred_um_per_px,
                    "primary": bool(subset_rows[0]["primary"]),
                }
            )
    return out


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def make_plots(rows: list[dict[str, object]], summary: list[dict[str, object]]) -> None:
    colors = {"raw": "#c44e52", "r61_v16_psfoff": "#4c72b0"}
    primary_rows = [r for r in rows if r["method"] == "primary_grid_area_edge"]
    fig, axes = plt.subplots(4, 1, figsize=(10, 11), dpi=150, sharex=True)
    for ax, group in zip(axes, GROUPS):
        expected = parse_group(group)[3]
        for kind in ["raw", "r61_v16_psfoff"]:
            rs = [r for r in primary_rows if r["group"] == group and r["kind"] == kind]
            ax.plot(
                [int(r["step_index"]) for r in rs],
                [abs(float(r["dx_px"])) for r in rs],
                marker="o",
                markersize=2.5,
                linewidth=1.1,
                color=colors[kind],
                label=LABELS[kind],
            )
        ax.axhline(expected, color="#333333", linestyle="--", linewidth=0.8, label="Expected" if group == GROUPS[0] else None)
        ax.set_title(f"{group}: primary ROI |dx| per step")
        ax.set_ylabel("px")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=8)
    axes[-1].set_xlabel("consecutive frame interval")
    fig.tight_layout()
    fig.savefig(OUT / "primary_grid_displacement_steps.png")
    plt.close(fig)

    primary_summary = [
        s for s in summary if s["method"] == "primary_grid_area_edge" and s["subset"] == "gap_le_30s"
    ]
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=150)
    x, vals, err, tick, bar_colors = [], [], [], [], []
    for group in GROUPS:
        for kind in ["raw", "r61_v16_psfoff"]:
            s = next(row for row in primary_summary if row["group"] == group and row["kind"] == kind)
            x.append(len(x))
            vals.append(float(s["median_abs_dx_px"]))
            err.append(float(s["std_abs_dx_px"]))
            tick.append(f"{group}\n{LABELS[kind]}")
            bar_colors.append(colors[kind])
    ax.bar(x, vals, yerr=err, capsize=4, color=bar_colors, alpha=0.85)
    for i, group in enumerate(GROUPS):
        expected = parse_group(group)[3]
        ax.plot([2 * i - 0.45, 2 * i + 1.45], [expected, expected], color="#333333", linestyle="--", linewidth=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(tick)
    ax.set_ylabel("median |dx| px")
    ax.set_title("Primary ROI displacement summary, gaps > 30 s excluded")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "primary_grid_summary_gap_le_30s.png")
    plt.close(fig)

    multi = [s for s in summary if s["subset"] == "gap_le_30s"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=150, sharey=False)
    for ax, group in zip(axes.ravel(), GROUPS):
        expected = parse_group(group)[3]
        methods = [m["method"] for m in METHODS]
        xpos = np.arange(len(methods))
        width = 0.38
        for j, kind in enumerate(["raw", "r61_v16_psfoff"]):
            vals = []
            for method in methods:
                s = next(row for row in multi if row["group"] == group and row["kind"] == kind and row["method"] == method)
                vals.append(float(s["median_abs_dx_px"]))
            ax.bar(xpos + (j - 0.5) * width, vals, width=width, color=colors[kind], alpha=0.82, label=LABELS[kind])
        ax.axhline(expected, color="#333333", linestyle="--", linewidth=0.9)
        ax.set_title(group)
        ax.set_xticks(xpos)
        ax.set_xticklabels([m.replace("_edge", "").replace("_", "\n") for m in methods], fontsize=7)
        ax.set_ylabel("median |dx| px")
        ax.grid(axis="y", alpha=0.2)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "multi_roi_median_displacement.png")
    plt.close(fig)


def make_previews() -> None:
    for group in GROUPS:
        raw_paths = sorted((ROOT / "raw_inputs" / group / "bmp").glob("*.bmp"))
        recon_paths = sorted((ROOT / f"r61_v16_psfoff_{group}" / "bmp").glob("*.bmp"))
        indices = sorted({0, len(raw_paths) // 2, len(raw_paths) - 1})
        tiles = []
        for idx in indices:
            for img, title in [
                (read_gray(raw_paths[idx]), f"{group} Raw frame {idx}"),
                (read_gray(recon_paths[idx]), f"{group} R61 v16 frame {idx}"),
            ]:
                small = cv2.resize(img, (512, 384), interpolation=cv2.INTER_AREA)
                canvas = cv2.cvtColor(small, cv2.COLOR_GRAY2BGR)
                cv2.rectangle(canvas, (0, 0), (512, 28), (255, 255, 255), -1)
                cv2.putText(canvas, title, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 1, cv2.LINE_AA)
                tiles.append(canvas)
        rows = [np.hstack(tiles[i : i + 2]) for i in range(0, len(tiles), 2)]
        cv2.imwrite(str(OUT / f"preview_raw_vs_v16_{group}.png"), np.vstack(rows))


def fmt(value: object, digits: int = 4) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "NA"
    return f"{number:.{digits}f}"


def write_markdown(summary: list[dict[str, object]]) -> None:
    primary = [s for s in summary if s["method"] == "primary_grid_area_edge" and s["subset"] == "gap_le_30s"]
    lines = [
        "# 20260704 20x/5x displacement reconstruction analysis",
        "",
        "Primary readout uses the large sample-pattern ROI, excluding the left background/arrows.",
        "Expected px assumes 3.45 um camera pixels and the folder magnification label.",
        "",
        "## Primary ROI, gaps > 30 s excluded",
        "",
        "| group | image | steps | expected px | median |dx| px | std |dx| px | median dx px | response | measured / expected |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group in GROUPS:
        for kind in ["raw", "r61_v16_psfoff"]:
            row = next(s for s in primary if s["group"] == group and s["kind"] == kind)
            lines.append(
                "| {group} | {label} | {n} | {expected} | {median_abs} | {std_abs} | {median_dx} | {response} | {ratio} |".format(
                    group=group,
                    label=LABELS[kind],
                    n=row["n_steps"],
                    expected=fmt(row["expected_dx_px_from_command"], 4),
                    median_abs=fmt(row["median_abs_dx_px"], 4),
                    std_abs=fmt(row["std_abs_dx_px"], 4),
                    median_dx=fmt(row["median_dx_px"], 4),
                    response=fmt(row["mean_response"], 4),
                    ratio=fmt(row["median_abs_dx_over_expected"], 4),
                )
            )
    lines.extend(
        [
            "",
            "## Multi-ROI cross-check, gaps > 30 s excluded",
            "",
            "| group | method | Raw median |dx| | R61 v16 median |dx| | expected px | note |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    clean = [s for s in summary if s["subset"] == "gap_le_30s"]
    for group in GROUPS:
        expected = parse_group(group)[3]
        for method in [m["method"] for m in METHODS]:
            raw = next(s for s in clean if s["group"] == group and s["kind"] == "raw" and s["method"] == method)
            rec = next(s for s in clean if s["group"] == group and s["kind"] == "r61_v16_psfoff" and s["method"] == method)
            note = "primary" if method == "primary_grid_area_edge" else ""
            if method == "left_unique_edge":
                note = "diagnostic; may include background/arrows"
            lines.append(
                f"| {group} | {method} | {fmt(raw['median_abs_dx_px'], 4)} | {fmt(rec['median_abs_dx_px'], 4)} | {fmt(expected, 4)} | {note} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation Notes",
            "",
            "- 20x/1um is the cleanest set: both Raw and R61 v16 are near the expected 5.80 px shift.",
            "- 20x/0.5um is usable, but ROI choice changes the median by a few tenths of a pixel.",
            "- 5x/1um and 5x/0.5um are subpixel-to-low-pixel measurements, so ROI choice matters much more.",
            "- R61 v16 reconstruction preserves the displacement direction in all four groups; it does not create a gross motion scaling error.",
            "- This is internal phase-correlation analysis, not an external GMF score.",
        ]
    )
    (OUT / "MOTION_ANALYSIS_READOUT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    mapping = load_mapping()
    rows: list[dict[str, object]] = []
    for group in GROUPS:
        for kind in ["raw", "r61_v16_psfoff"]:
            for method in METHODS:
                rows.extend(pair_shifts(group, kind, method, mapping))
    summary = summarize(rows)
    write_csv(OUT / "motion_steps.csv", rows)
    write_csv(OUT / "motion_summary.csv", summary)
    (OUT / "motion_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    make_plots(rows, summary)
    make_previews()
    write_markdown(summary)
    print(json.dumps({"step_rows": len(rows), "summary_rows": len(summary), "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
