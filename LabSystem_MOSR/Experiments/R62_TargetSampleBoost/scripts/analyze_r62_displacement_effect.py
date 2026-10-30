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
PROJECT_ROOT = Path(__file__).resolve().parents[4]


REPORT_ROOT = Path(
    str(PROJECT_ROOT / 'LabSystem_MOSR/Experiments/R62_TargetSampleBoost/reports/r62_v2_targetboost_displacement_eval')
)

DATASETS = [
    {
        "dataset": "20260702_100MG",
        "root": Path(str(PROJECT_ROOT / 'Analyses' / '20260702_100MG_displacement_analysis')),
        "groups": ["x_1um", "x_0p5um"],
        "nominal_um": {"x_1um": 1.0, "x_0p5um": 0.5},
        "methods": [
            {
                "method": "primary_binary_bottom_left_dots",
                "prep": "binary_dark",
                "roi": [0, 780, 1050, 1536],
                "primary": True,
            },
            {
                "method": "full_edge",
                "prep": "edge",
                "roi": None,
                "primary": False,
            },
        ],
        "cases": {
            "raw": "raw_inputs/{group}/bmp",
            "r61": "r61_v16_psfoff_{group}/bmp",
            "r62": "r62_v2_targetboost_psfoff_{group}/bmp",
        },
    },
    {
        "dataset": "20260704_20x_5x",
        "root": Path(str(PROJECT_ROOT / 'Analyses' / '20260704_20x_5x_analysis')),
        "groups": ["20x_1um", "20x_0p5um", "5x_1um", "5x_0p5um"],
        "nominal_um": {"20x_1um": 1.0, "20x_0p5um": 0.5, "5x_1um": 1.0, "5x_0p5um": 0.5},
        "methods": [
            {
                "method": "primary_grid_area_edge",
                "prep": "edge",
                "roi": [560, 80, 2020, 1500],
                "primary": True,
            },
            {
                "method": "center_blocks_edge",
                "prep": "edge",
                "roi": [900, 420, 1680, 1160],
                "primary": False,
            },
            {
                "method": "line_grating_edge",
                "prep": "edge",
                "roi": [520, 860, 1900, 1530],
                "primary": False,
            },
            {
                "method": "dot_array_edge",
                "prep": "edge",
                "roi": [520, 20, 1900, 860],
                "primary": False,
            },
            {
                "method": "full_frame_edge",
                "prep": "edge",
                "roi": None,
                "primary": False,
            },
        ],
        "cases": {
            "raw": "raw_inputs/{group}/bmp",
            "r61": "r61_v16_psfoff_{group}/bmp",
            "r62": "r62_v2_targetboost_psfoff_{group}/bmp",
        },
    },
]

LABELS = {"raw": "Raw", "r61": "R61 v16", "r62": "R62 target-boost"}
COLORS = {"raw": "#c44e52", "r61": "#4c72b0", "r62": "#55a868"}
CAMERA_PIXEL_UM = 3.45


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"failed to read {path}")
    return image


def load_mapping(root: Path) -> dict[tuple[str, str], dict[str, str]]:
    path = root / "input_mapping.csv"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return {(row["group"], row["work_name"]): row for row in csv.DictReader(fh)}


def crop(image: np.ndarray, roi: list[int] | None) -> np.ndarray:
    if roi is None:
        return image
    x0, y0, x1, y1 = roi
    return image[y0:y1, x0:x1]


def preprocess(image: np.ndarray, mode: str) -> np.ndarray:
    if mode == "binary_dark":
        _, out = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        arr = out.astype(np.float32)
    elif mode == "edge":
        gray = image.astype(np.float32)
        blur = cv2.GaussianBlur(gray, (0, 0), 1.0)
        gx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
        arr = cv2.magnitude(gx, gy)
    else:
        raise ValueError(f"unknown prep mode: {mode}")
    arr -= float(arr.mean())
    std = float(arr.std())
    if std > 1e-6:
        arr /= std
    return arr.astype(np.float32)


def case_dir(spec: dict[str, object], group: str, kind: str) -> Path:
    root = Path(spec["root"])
    template = spec["cases"][kind]
    return root / str(template).format(group=group)


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S",):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def object_um_per_px(dataset: str, group: str) -> float | None:
    if dataset != "20260704_20x_5x":
        return None
    mag_text = group.split("_", 1)[0].replace("x", "")
    mag = float(mag_text)
    return CAMERA_PIXEL_UM / mag


def pair_shifts(
    spec: dict[str, object],
    group: str,
    kind: str,
    method: dict[str, object],
    mapping: dict[tuple[str, str], dict[str, str]],
) -> list[dict[str, object]]:
    folder = case_dir(spec, group, kind)
    paths = sorted(folder.glob("*.bmp"))
    if len(paths) < 2:
        raise FileNotFoundError(f"not enough BMP files in {folder}")
    frames = [preprocess(crop(read_gray(path), method["roi"]), str(method["prep"])) for path in paths]
    window = cv2.createHanningWindow((frames[0].shape[1], frames[0].shape[0]), cv2.CV_32F)
    nominal = float(spec["nominal_um"][group])
    scale = object_um_per_px(str(spec["dataset"]), group)
    rows: list[dict[str, object]] = []
    for idx, (a, b) in enumerate(zip(frames, frames[1:])):
        (dx, dy), response = cv2.phaseCorrelate(a, b, window)
        from_name = paths[idx].name
        to_name = paths[idx + 1].name
        from_map = mapping.get((group, from_name), {})
        to_map = mapping.get((group, to_name), {})
        t0 = parse_time(from_map.get("timestamp", ""))
        t1 = parse_time(to_map.get("timestamp", ""))
        time_gap_s: float | str = ""
        if t0 is not None and t1 is not None:
            time_gap_s = (t1 - t0).total_seconds()
        row = {
            "dataset": spec["dataset"],
            "group": group,
            "kind": kind,
            "label": LABELS[kind],
            "method": method["method"],
            "primary": bool(method["primary"]),
            "step_index": idx,
            "from": from_name,
            "to": to_name,
            "time_gap_s": time_gap_s,
            "dx_px": float(dx),
            "dy_px": float(dy),
            "abs_dx_px": abs(float(dx)),
            "abs_dy_px": abs(float(dy)),
            "response": float(response),
            "nominal_step_um": nominal,
            "object_um_per_px": "" if scale is None else scale,
            "abs_dx_um": "" if scale is None else abs(float(dx)) * scale,
        }
        rows.append(row)
    return rows


def finite(values: list[object]) -> np.ndarray:
    out = []
    for value in values:
        if value == "":
            continue
        number = float(value)
        if math.isfinite(number):
            out.append(number)
    return np.array(out, dtype=float)


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    keys = sorted({(r["dataset"], r["group"], r["kind"], r["method"]) for r in rows})
    out: list[dict[str, object]] = []
    for dataset, group, kind, method in keys:
        rs = [r for r in rows if r["dataset"] == dataset and r["group"] == group and r["kind"] == kind and r["method"] == method]
        gap_rows = [r for r in rs if r["time_gap_s"] == "" or float(r["time_gap_s"]) <= 30.0]
        for subset, subset_rows in [("all_steps", rs), ("gap_le_30s", gap_rows)]:
            if not subset_rows:
                continue
            dx = finite([r["dx_px"] for r in subset_rows])
            dy = finite([r["dy_px"] for r in subset_rows])
            absdx = np.abs(dx)
            response = finite([r["response"] for r in subset_rows])
            scale_values = finite([r["object_um_per_px"] for r in subset_rows])
            nominal_um = float(subset_rows[0]["nominal_step_um"])
            scale = float(scale_values[0]) if len(scale_values) else None
            median_abs_um: float | str = ""
            std_abs_um: float | str = ""
            abs_error_um: float | str = ""
            if scale is not None:
                median_abs_um = float(np.median(absdx) * scale)
                std_abs_um = float(np.std(absdx * scale, ddof=0))
                abs_error_um = abs(float(median_abs_um) - nominal_um)
            inferred_scale = nominal_um / float(np.median(absdx)) if float(np.median(absdx)) > 1e-9 else ""
            out.append(
                {
                    "dataset": dataset,
                    "group": group,
                    "kind": kind,
                    "label": LABELS[str(kind)],
                    "method": method,
                    "subset": subset,
                    "n_steps": len(subset_rows),
                    "median_abs_dx_px": float(np.median(absdx)),
                    "std_abs_dx_px": float(absdx.std(ddof=0)),
                    "median_dx_px": float(np.median(dx)),
                    "std_dx_px": float(dx.std(ddof=0)),
                    "median_abs_dy_px": float(np.median(np.abs(dy))),
                    "mean_response": float(response.mean()),
                    "nominal_step_um": nominal_um,
                    "object_um_per_px": "" if scale is None else scale,
                    "median_abs_dx_um": median_abs_um,
                    "std_abs_dx_um": std_abs_um,
                    "abs_error_um": abs_error_um,
                    "inferred_um_per_px_from_command": inferred_scale,
                    "primary": bool(subset_rows[0]["primary"]),
                }
            )
    return out


def add_comparisons(summary: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    keys = sorted({(r["dataset"], r["group"], r["method"], r["subset"]) for r in summary})
    for dataset, group, method, subset in keys:
        trio = {r["kind"]: r for r in summary if r["dataset"] == dataset and r["group"] == group and r["method"] == method and r["subset"] == subset}
        if not {"raw", "r61", "r62"}.issubset(trio):
            continue
        raw = trio["raw"]
        r61 = trio["r61"]
        r62 = trio["r62"]
        def pct(new: float, old: float) -> float | str:
            if abs(old) < 1e-12:
                return ""
            return (new - old) / old * 100.0
        rows.append(
            {
                "dataset": dataset,
                "group": group,
                "method": method,
                "subset": subset,
                "primary": raw["primary"],
                "raw_median_abs_dx_px": raw["median_abs_dx_px"],
                "r61_median_abs_dx_px": r61["median_abs_dx_px"],
                "r62_median_abs_dx_px": r62["median_abs_dx_px"],
                "raw_std_abs_dx_px": raw["std_abs_dx_px"],
                "r61_std_abs_dx_px": r61["std_abs_dx_px"],
                "r62_std_abs_dx_px": r62["std_abs_dx_px"],
                "r61_std_change_vs_raw_pct": pct(float(r61["std_abs_dx_px"]), float(raw["std_abs_dx_px"])),
                "r62_std_change_vs_raw_pct": pct(float(r62["std_abs_dx_px"]), float(raw["std_abs_dx_px"])),
                "r62_std_change_vs_r61_pct": pct(float(r62["std_abs_dx_px"]), float(r61["std_abs_dx_px"])),
                "raw_response": raw["mean_response"],
                "r61_response": r61["mean_response"],
                "r62_response": r62["mean_response"],
                "raw_abs_error_um": raw["abs_error_um"],
                "r61_abs_error_um": r61["abs_error_um"],
                "r62_abs_error_um": r62["abs_error_um"],
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: object, digits: int = 4) -> str:
    if value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return ""
    return f"{number:.{digits}f}"


def make_primary_plots(rows: list[dict[str, object]], summary: list[dict[str, object]]) -> None:
    primary_summary = [s for s in summary if s["primary"] and s["subset"] == "gap_le_30s"]
    for dataset in sorted({s["dataset"] for s in primary_summary}):
        ds = next(spec for spec in DATASETS if spec["dataset"] == dataset)
        groups = list(ds["groups"])
        fig, axes = plt.subplots(len(groups), 1, figsize=(10, 2.6 * len(groups)), dpi=150, sharex=False)
        if len(groups) == 1:
            axes = [axes]
        for ax, group in zip(axes, groups):
            method = next(m["method"] for m in ds["methods"] if m["primary"])
            for kind in ["raw", "r61", "r62"]:
                rs = [
                    r
                    for r in rows
                    if r["dataset"] == dataset and r["group"] == group and r["kind"] == kind and r["method"] == method
                    and (r["time_gap_s"] == "" or float(r["time_gap_s"]) <= 30.0)
                ]
                ax.plot(
                    [int(r["step_index"]) for r in rs],
                    [float(r["abs_dx_px"]) for r in rs],
                    marker="o",
                    markersize=2.4,
                    linewidth=1.0,
                    color=COLORS[kind],
                    label=LABELS[kind],
                )
            ax.set_title(f"{dataset} {group} primary ROI, gap <= 30 s")
            ax.set_ylabel("|dx| px")
            ax.grid(True, alpha=0.25)
            ax.legend(fontsize=8)
        axes[-1].set_xlabel("frame-to-frame step")
        fig.tight_layout()
        fig.savefig(REPORT_ROOT / f"{dataset}_primary_steps_gap_le_30s.png")
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 5.2), dpi=150)
    x: list[int] = []
    vals: list[float] = []
    err: list[float] = []
    colors: list[str] = []
    ticks: list[str] = []
    for dataset in ["20260702_100MG", "20260704_20x_5x"]:
        ds = next(spec for spec in DATASETS if spec["dataset"] == dataset)
        method = next(m["method"] for m in ds["methods"] if m["primary"])
        for group in ds["groups"]:
            for kind in ["raw", "r61", "r62"]:
                row = next(
                    s
                    for s in primary_summary
                    if s["dataset"] == dataset and s["group"] == group and s["kind"] == kind and s["method"] == method
                )
                x.append(len(x))
                vals.append(float(row["std_abs_dx_px"]))
                err.append(0.0)
                colors.append(COLORS[kind])
                ticks.append(f"{group}\n{LABELS[kind]}")
    ax.bar(x, vals, yerr=err, color=colors, alpha=0.88)
    ax.set_xticks(x)
    ax.set_xticklabels(ticks, fontsize=7)
    ax.set_ylabel("std of |dx| (px)")
    ax.set_title("Primary ROI stability, gap <= 30 s")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(REPORT_ROOT / "primary_stability_raw_r61_r62.png")
    plt.close(fig)


def make_previews() -> None:
    for spec in DATASETS:
        dataset = str(spec["dataset"])
        for group in spec["groups"]:
            dirs = [(kind, case_dir(spec, group, kind)) for kind in ["raw", "r61", "r62"]]
            path_lists = [(kind, sorted(folder.glob("*.bmp"))) for kind, folder in dirs]
            if any(not paths for _, paths in path_lists):
                continue
            indices = sorted({0, len(path_lists[0][1]) // 2, len(path_lists[0][1]) - 1})
            rows = []
            for idx in indices:
                tiles = []
                for kind, paths in path_lists:
                    safe_idx = min(idx, len(paths) - 1)
                    img = read_gray(paths[safe_idx])
                    small = cv2.resize(img, (430, 320), interpolation=cv2.INTER_AREA)
                    canvas = cv2.cvtColor(small, cv2.COLOR_GRAY2BGR)
                    cv2.rectangle(canvas, (0, 0), (430, 28), (255, 255, 255), -1)
                    cv2.putText(
                        canvas,
                        f"{group} {LABELS[kind]} f{safe_idx}",
                        (8, 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.48,
                        (0, 0, 0),
                        1,
                        cv2.LINE_AA,
                    )
                    tiles.append(canvas)
                rows.append(np.hstack(tiles))
            preview = np.vstack(rows)
            cv2.imwrite(str(REPORT_ROOT / f"preview_{dataset}_{group}_raw_r61_r62.png"), preview)


def write_markdown(summary: list[dict[str, object]], comparison: list[dict[str, object]]) -> None:
    primary = [c for c in comparison if c["primary"] and c["subset"] == "gap_le_30s"]
    lines = [
        "# R62 target-sample-boost validation readout",
        "",
        "This compares Raw, R61 v16, and R62 target-boost on the same displacement image folders.",
        "The clean table excludes frame intervals with time gaps longer than 30 seconds.",
        "",
        "## Primary stability comparison",
        "",
        "| dataset | group | Raw std px | R61 std px | R62 std px | R62 vs Raw | R62 vs R61 | Raw median px | R61 median px | R62 median px |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in primary:
        lines.append(
            "| {dataset} | {group} | {raw_std} | {r61_std} | {r62_std} | {r62_raw} | {r62_r61} | {raw_med} | {r61_med} | {r62_med} |".format(
                dataset=row["dataset"],
                group=row["group"],
                raw_std=fmt(row["raw_std_abs_dx_px"], 4),
                r61_std=fmt(row["r61_std_abs_dx_px"], 4),
                r62_std=fmt(row["r62_std_abs_dx_px"], 4),
                r62_raw=fmt(row["r62_std_change_vs_raw_pct"], 1) + "%",
                r62_r61=fmt(row["r62_std_change_vs_r61_pct"], 1) + "%",
                raw_med=fmt(row["raw_median_abs_dx_px"], 4),
                r61_med=fmt(row["r61_median_abs_dx_px"], 4),
                r62_med=fmt(row["r62_median_abs_dx_px"], 4),
            )
        )
    lines.extend(
        [
            "",
            "## 20260704 physical-step check",
            "",
            "| group | Raw error um | R61 error um | R62 error um | Raw median um | R61 median um | R62 median um |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    physical = [
        s
        for s in summary
        if s["dataset"] == "20260704_20x_5x" and s["primary"] and s["subset"] == "gap_le_30s"
    ]
    for group in ["20x_1um", "20x_0p5um", "5x_1um", "5x_0p5um"]:
        rows = {s["kind"]: s for s in physical if s["group"] == group}
        lines.append(
            f"| {group} | {fmt(rows['raw']['abs_error_um'], 5)} | {fmt(rows['r61']['abs_error_um'], 5)} | {fmt(rows['r62']['abs_error_um'], 5)} | "
            f"{fmt(rows['raw']['median_abs_dx_um'], 5)} | {fmt(rows['r61']['median_abs_dx_um'], 5)} | {fmt(rows['r62']['median_abs_dx_um'], 5)} |"
        )
    lines.extend(
        [
            "",
            "## Initial interpretation",
            "",
            "- R62 is a target-sample adaptation candidate. It should be judged by whether it helps these real sequences without breaking the old R61 behavior.",
            "- The numbers above are internal image-registration checks, not an external GMF score.",
            "- A lower std means the frame-to-frame measured displacement is more stable.",
            "- The physical-step check is available only for the 20260704 folders because their magnification labels are explicit.",
            "",
            "## Files",
            "",
            "- Full per-step table: `r62_displacement_steps.csv`",
            "- Summary table: `r62_displacement_summary.csv`",
            "- Raw/R61/R62 comparison table: `r62_raw_r61_r62_comparison.csv`",
            "- Main stability plot: `primary_stability_raw_r61_r62.png`",
        ]
    )
    (REPORT_ROOT / "R62_TARGETBOOST_VALIDATION_READOUT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for spec in DATASETS:
        mapping = load_mapping(Path(spec["root"]))
        for group in spec["groups"]:
            for kind in ["raw", "r61", "r62"]:
                for method in spec["methods"]:
                    rows.extend(pair_shifts(spec, str(group), kind, method, mapping))
    summary = summarize(rows)
    comparison = add_comparisons(summary)
    write_csv(REPORT_ROOT / "r62_displacement_steps.csv", rows)
    write_csv(REPORT_ROOT / "r62_displacement_summary.csv", summary)
    write_csv(REPORT_ROOT / "r62_raw_r61_r62_comparison.csv", comparison)
    (REPORT_ROOT / "r62_displacement_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    make_primary_plots(rows, summary)
    make_previews()
    write_markdown(summary, comparison)
    print(json.dumps({"step_rows": len(rows), "summary_rows": len(summary), "comparison_rows": len(comparison), "out": str(REPORT_ROOT)}, indent=2))


if __name__ == "__main__":
    main()
