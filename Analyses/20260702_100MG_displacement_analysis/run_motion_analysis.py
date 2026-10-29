from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "motion_analysis"
OUT.mkdir(parents=True, exist_ok=True)

CASES = [
    {
        "case": "raw_x_1um",
        "dataset": "x_1um",
        "kind": "raw",
        "folder": ROOT / "raw_inputs" / "x_1um" / "bmp",
        "nominal_step_um": 1.0,
    },
    {
        "case": "v16_x_1um",
        "dataset": "x_1um",
        "kind": "r61_v16_psfoff",
        "folder": ROOT / "r61_v16_psfoff_x_1um" / "bmp",
        "nominal_step_um": 1.0,
    },
    {
        "case": "raw_x_0p5um",
        "dataset": "x_0p5um",
        "kind": "raw",
        "folder": ROOT / "raw_inputs" / "x_0p5um" / "bmp",
        "nominal_step_um": 0.5,
    },
    {
        "case": "v16_x_0p5um",
        "dataset": "x_0p5um",
        "kind": "r61_v16_psfoff",
        "folder": ROOT / "r61_v16_psfoff_x_0p5um" / "bmp",
        "nominal_step_um": 0.5,
    },
]

METHODS = [
    {
        "method": "primary_binary_bottom_left_dots",
        "description": "Binarized dark-pattern phase correlation on the bottom-left dot array ROI.",
        "prep": "binary_dark",
        "roi": [0, 780, 1050, 1536],
        "primary": True,
    },
    {
        "method": "full_edge",
        "description": "Full-frame Sobel-edge phase correlation.",
        "prep": "edge",
        "roi": None,
        "primary": False,
    },
]


def load_mapping() -> dict[tuple[str, str], dict[str, str]]:
    path = ROOT / "input_mapping.csv"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return {(row["group"], row["work_name"]): row for row in rows}


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"failed to read {path}")
    return image


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
        raise ValueError(f"unknown preprocess mode: {mode}")
    arr -= float(arr.mean())
    std = float(arr.std())
    if std > 1e-6:
        arr /= std
    return arr.astype(np.float32)


def crop(image: np.ndarray, roi: list[int] | None) -> np.ndarray:
    if roi is None:
        return image
    x0, y0, x1, y1 = roi
    return image[y0:y1, x0:x1]


def pair_shifts(case: dict[str, object], method: dict[str, object], mapping: dict[tuple[str, str], dict[str, str]]) -> list[dict[str, object]]:
    folder = Path(case["folder"])
    paths = sorted(folder.glob("*.bmp"))
    if len(paths) < 2:
        raise ValueError(f"not enough BMP files in {folder}")

    prepped = []
    for path in paths:
        image = crop(read_gray(path), method["roi"])
        prepped.append(preprocess(image, str(method["prep"])))

    window = cv2.createHanningWindow((prepped[0].shape[1], prepped[0].shape[0]), cv2.CV_32F)
    group = str(case["dataset"])
    rows = []
    for idx, (a, b) in enumerate(zip(prepped, prepped[1:])):
        (dx, dy), response = cv2.phaseCorrelate(a, b, window)
        from_name = paths[idx].name
        to_name = paths[idx + 1].name
        from_map = mapping.get((group, from_name), {})
        to_map = mapping.get((group, to_name), {})
        time_gap_s = ""
        if from_map.get("timestamp") and to_map.get("timestamp"):
            from datetime import datetime

            t0 = datetime.strptime(from_map["timestamp"], "%Y-%m-%d %H:%M:%S")
            t1 = datetime.strptime(to_map["timestamp"], "%Y-%m-%d %H:%M:%S")
            time_gap_s = (t1 - t0).total_seconds()
        rows.append(
            {
                "case": case["case"],
                "dataset": case["dataset"],
                "kind": case["kind"],
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
                "response": float(response),
                "nominal_step_um": float(case["nominal_step_um"]),
                "primary": bool(method["primary"]),
            }
        )
    return rows


def finite(values: list[object]) -> np.ndarray:
    return np.array([float(v) for v in values if v != "" and math.isfinite(float(v))], dtype=float)


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    keys = sorted({(r["dataset"], r["kind"], r["method"]) for r in rows})
    out = []
    for dataset, kind, method in keys:
        rs = [r for r in rows if r["dataset"] == dataset and r["kind"] == kind and r["method"] == method]
        for subset_name, subset_rows in [
            ("all_steps", rs),
            ("gap_le_30s", [r for r in rs if r["time_gap_s"] == "" or float(r["time_gap_s"]) <= 30.0]),
        ]:
            dx = finite([r["dx_px"] for r in subset_rows])
            dy = finite([r["dy_px"] for r in subset_rows])
            absdx = np.abs(dx)
            response = finite([r["response"] for r in subset_rows])
            if len(dx) == 0:
                continue
            nominal = float(subset_rows[0]["nominal_step_um"])
            inferred_um_per_px_from_median = nominal / float(np.median(absdx)) if float(np.median(absdx)) > 1e-9 else ""
            out.append(
                {
                    "dataset": dataset,
                    "kind": kind,
                    "method": method,
                    "subset": subset_name,
                    "n_steps": len(subset_rows),
                    "median_dx_px": float(np.median(dx)),
                    "mean_dx_px": float(dx.mean()),
                    "std_dx_px": float(dx.std(ddof=0)),
                    "median_abs_dx_px": float(np.median(absdx)),
                    "mean_abs_dx_px": float(absdx.mean()),
                    "std_abs_dx_px": float(absdx.std(ddof=0)),
                    "median_dy_px": float(np.median(dy)),
                    "std_dy_px": float(dy.std(ddof=0)),
                    "mean_response": float(response.mean()),
                    "move_like_steps_abs_dx_gt_3px": int(np.sum(absdx > 3.0)),
                    "nominal_step_um": nominal,
                    "inferred_um_per_px_from_median": inferred_um_per_px_from_median,
                }
            )
    return out


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def make_motion_plots(rows: list[dict[str, object]], summary: list[dict[str, object]]) -> None:
    primary = [r for r in rows if r["method"] == "primary_binary_bottom_left_dots"]
    colors = {"raw": "#c44e52", "r61_v16_psfoff": "#4c72b0"}
    labels = {"raw": "Raw", "r61_v16_psfoff": "R61 v16"}

    fig, axes = plt.subplots(2, 1, figsize=(9, 7), dpi=150, sharex=False)
    for ax, dataset in zip(axes, ["x_1um", "x_0p5um"]):
        for kind in ["raw", "r61_v16_psfoff"]:
            rs = [r for r in primary if r["dataset"] == dataset and r["kind"] == kind]
            ax.plot(
                [int(r["step_index"]) for r in rs],
                [abs(float(r["dx_px"])) for r in rs],
                marker="o",
                markersize=2.5,
                linewidth=1.1,
                label=labels[kind],
                color=colors[kind],
                alpha=0.9,
            )
        ax.set_title(f"{dataset}: absolute x displacement per frame")
        ax.set_ylabel("px")
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    axes[-1].set_xlabel("consecutive frame interval")
    fig.tight_layout()
    fig.savefig(OUT / "primary_displacement_steps_raw_vs_v16.png")
    plt.close(fig)

    primary_summary = [
        s for s in summary if s["method"] == "primary_binary_bottom_left_dots" and s["subset"] == "all_steps"
    ]
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
    x = []
    vals = []
    err = []
    tick = []
    bar_colors = []
    for dataset in ["x_1um", "x_0p5um"]:
        for kind in ["raw", "r61_v16_psfoff"]:
            s = next(row for row in primary_summary if row["dataset"] == dataset and row["kind"] == kind)
            x.append(len(x))
            vals.append(float(s["median_abs_dx_px"]))
            err.append(float(s["std_abs_dx_px"]))
            tick.append(f"{dataset}\n{labels[kind]}")
            bar_colors.append(colors[kind])
    ax.bar(x, vals, yerr=err, capsize=4, color=bar_colors, alpha=0.85)
    for xi, vi in zip(x, vals):
        ax.text(xi, vi + max(vals) * 0.03, f"{vi:.3f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(tick)
    ax.set_ylabel("median |dx| px")
    ax.set_title("Primary displacement estimate, Raw vs R61 v16")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "primary_displacement_summary_raw_vs_v16.png")
    plt.close(fig)

    clean_summary = [
        s for s in summary if s["method"] == "primary_binary_bottom_left_dots" and s["subset"] == "gap_le_30s"
    ]
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=150)
    x = []
    vals = []
    err = []
    tick = []
    bar_colors = []
    for dataset in ["x_1um", "x_0p5um"]:
        for kind in ["raw", "r61_v16_psfoff"]:
            s = next(row for row in clean_summary if row["dataset"] == dataset and row["kind"] == kind)
            x.append(len(x))
            vals.append(float(s["median_abs_dx_px"]))
            err.append(float(s["std_abs_dx_px"]))
            tick.append(f"{dataset}\n{labels[kind]}")
            bar_colors.append(colors[kind])
    ax.bar(x, vals, yerr=err, capsize=4, color=bar_colors, alpha=0.85)
    for xi, vi in zip(x, vals):
        ax.text(xi, vi + max(vals) * 0.03, f"{vi:.3f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(tick)
    ax.set_ylabel("median |dx| px")
    ax.set_title("Primary displacement estimate, gaps > 30 s excluded")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "primary_displacement_summary_gap_le_30s_raw_vs_v16.png")
    plt.close(fig)


def make_previews() -> None:
    preview_specs = [
        ("x_1um", ROOT / "raw_inputs" / "x_1um" / "bmp", ROOT / "r61_v16_psfoff_x_1um" / "bmp"),
        ("x_0p5um", ROOT / "raw_inputs" / "x_0p5um" / "bmp", ROOT / "r61_v16_psfoff_x_0p5um" / "bmp"),
    ]
    for dataset, raw_dir, recon_dir in preview_specs:
        raw_paths = sorted(raw_dir.glob("*.bmp"))
        recon_paths = sorted(recon_dir.glob("*.bmp"))
        indices = sorted(set([0, len(raw_paths) // 2, len(raw_paths) - 1]))
        tiles = []
        for idx in indices:
            raw = read_gray(raw_paths[idx])
            rec = read_gray(recon_paths[idx])
            for img, title in [(raw, f"{dataset} raw frame {idx}"), (rec, f"{dataset} v16 frame {idx}")]:
                small = cv2.resize(img, (512, 384), interpolation=cv2.INTER_AREA)
                canvas = cv2.cvtColor(small, cv2.COLOR_GRAY2BGR)
                cv2.rectangle(canvas, (0, 0), (512, 28), (255, 255, 255), -1)
                cv2.putText(canvas, title, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
                tiles.append(canvas)
        rows = []
        for i in range(0, len(tiles), 2):
            rows.append(np.hstack(tiles[i:i + 2]))
        sheet = np.vstack(rows)
        cv2.imwrite(str(OUT / f"preview_raw_vs_v16_{dataset}.png"), sheet)


def write_markdown(summary: list[dict[str, object]]) -> None:
    primary = [
        s for s in summary if s["method"] == "primary_binary_bottom_left_dots" and s["subset"] == "all_steps"
    ]
    primary_clean = [
        s for s in summary if s["method"] == "primary_binary_bottom_left_dots" and s["subset"] == "gap_le_30s"
    ]
    edge = [s for s in summary if s["method"] == "full_edge" and s["subset"] == "all_steps"]
    lines = [
        "# 20260702 100MG displacement reconstruction analysis",
        "",
        "Primary result uses the bottom-left dot array and binarized dark-pattern phase correlation.",
        "Full-frame edge matching is included as a stress test of how easy the whole image is to register.",
        "",
        "## Primary displacement result",
        "",
        "| dataset | image | steps | median |dx| px | std |dx| px | median dx px | response | inferred um/px from command |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    label = {"raw": "Raw", "r61_v16_psfoff": "R61 v16 PSF-off"}
    for dataset in ["x_1um", "x_0p5um"]:
        for kind in ["raw", "r61_v16_psfoff"]:
            row = next(s for s in primary if s["dataset"] == dataset and s["kind"] == kind)
            lines.append(
                "| {dataset} | {kind} | {n_steps} | {median_abs:.4f} | {std_abs:.4f} | {median_dx:.4f} | {resp:.4f} | {scale:.5f} |".format(
                    dataset=dataset,
                    kind=label[kind],
                    n_steps=row["n_steps"],
                    median_abs=row["median_abs_dx_px"],
                    std_abs=row["std_abs_dx_px"],
                    median_dx=row["median_dx_px"],
                    resp=row["mean_response"],
                    scale=row["inferred_um_per_px_from_median"],
                )
            )
    lines.extend(
        [
            "",
            "## Primary displacement after excluding intervals with time gap > 30 s",
            "",
            "| dataset | image | steps | median |dx| px | std |dx| px | median dx px | response | inferred um/px from command |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for dataset in ["x_1um", "x_0p5um"]:
        for kind in ["raw", "r61_v16_psfoff"]:
            row = next(s for s in primary_clean if s["dataset"] == dataset and s["kind"] == kind)
            lines.append(
                "| {dataset} | {kind} | {n_steps} | {median_abs:.4f} | {std_abs:.4f} | {median_dx:.4f} | {resp:.4f} | {scale:.5f} |".format(
                    dataset=dataset,
                    kind=label[kind],
                    n_steps=row["n_steps"],
                    median_abs=row["median_abs_dx_px"],
                    std_abs=row["std_abs_dx_px"],
                    median_dx=row["median_dx_px"],
                    resp=row["mean_response"],
                    scale=row["inferred_um_per_px_from_median"],
                )
            )
    lines.extend(
        [
            "",
            "## Full-frame edge stress test",
            "",
            "| dataset | image | move-like steps | median |dx| px | std dx px | response |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for dataset in ["x_1um", "x_0p5um"]:
        for kind in ["raw", "r61_v16_psfoff"]:
            row = next(s for s in edge if s["dataset"] == dataset and s["kind"] == kind)
            lines.append(
                "| {dataset} | {kind} | {moves}/{n_steps} | {median_abs:.4f} | {std_dx:.4f} | {resp:.4f} |".format(
                    dataset=dataset,
                    kind=label[kind],
                    moves=row["move_like_steps_abs_dx_gt_3px"],
                    n_steps=row["n_steps"],
                    median_abs=row["median_abs_dx_px"],
                    std_dx=row["std_dx_px"],
                    resp=row["mean_response"],
                )
            )
    lines.extend(
        [
            "",
            "## Interpretation notes",
            "",
            "- Primary ROI-based measurement says Raw and R61 v16 preserve nearly the same commanded displacement.",
            "- The x_0.5um full-span standard deviation is inflated by long-pause intervals; the gap-filtered table is the cleaner stability view.",
            "- R61 v16 makes full-frame edge registration much more stable, especially when raw intensity/blur causes local matching to collapse.",
            "- These are local image-registration results, not external GMF scores.",
        ]
    )
    (OUT / "MOTION_ANALYSIS_READOUT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    mapping = load_mapping()
    rows: list[dict[str, object]] = []
    for case in CASES:
        for method in METHODS:
            rows.extend(pair_shifts(case, method, mapping))
    summary = summarize(rows)
    write_csv(OUT / "motion_steps.csv", rows)
    write_csv(OUT / "motion_summary.csv", summary)
    (OUT / "motion_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    make_motion_plots(rows, summary)
    make_previews()
    write_markdown(summary)
    print(json.dumps({"rows": len(rows), "summary_rows": len(summary), "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
