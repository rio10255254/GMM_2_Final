"""Rayleigh-aware diagnostic for a025 vs a043 (vs a030, COMBO).

讀 capability_eval/per_pair_metrics.csv（已含 R44G 風格的邊界形狀指標），
對每張 GT label 影像算「特徵 stroke width」（skeleton + distance transform）作為
該影像主要特徵尺寸的代表，再以 Rayleigh 上限（預設 11.7 px）把每張影像分到
supra / mixed / sub 三類，最後對每個 (model × class) aggregate 既有指標。

目的：判斷 a043 比 a025 強的差距，是落在可解析尺度（fine-tune 可推）還是
次解析尺度（物理上限、fine-tune 救不了）。

Outputs (in --out):
  - per_pair_with_width.csv   per-pair CSV + width columns + class
  - aggregate_by_class.csv    (model, class) × metric pivot
  - rayleigh_summary.md       human-readable summary
  - feature_width_scatter.png 散布圖
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from skimage.morphology import skeletonize
PROJECT_ROOT = Path(__file__).resolve().parents[3]


REPO_ROOT = Path(str(PROJECT_ROOT))
DEFAULT_CSV = (
    REPO_ROOT
    / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep"
    / "capability_eval/per_pair_metrics.csv"
)
DEFAULT_OUT = (
    REPO_ROOT
    / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep"
    / "rayleigh_diagnostic"
)

R39_LBL_BASE = REPO_ROOT / "Training_Data/r39_shape_generalization/shape_val_unseen/lbl"
R40_LBL_BASE = REPO_ROOT / "Training_Data/r40_microscopy_feature_coverage/micro_val_unseen/lbl"

DATASET_LBL = {
    "R39_shape_val_unseen": R39_LBL_BASE,
    "R40_micro_val_unseen": R40_LBL_BASE,
}

RAYLEIGH_PX = 11.7
GT_THRESH = 50

METRIC_COLS = [
    ("shape_error_score", "↓"),
    ("corner_retention", "↑"),
    ("straight_edge_coverage", "↑"),
    ("boundary_f_score", "↑"),
    ("high_frequency_retention", "↑"),
    ("edge_retention", "↑"),
    ("psnr", "↑"),
    ("ssim", "↑"),
]

MODELS_ORDER = ["COMBO", "a030", "a043", "R39R40_a025"]
CLASSES_ORDER = ["supra", "mixed", "sub", "unknown"]


def compute_feature_widths(lbl_image: np.ndarray, thresh: int = GT_THRESH) -> dict:
    binary = (lbl_image > thresh).astype(np.uint8)
    n_fg = int(binary.sum())
    if n_fg == 0:
        return _empty_width_result(0)
    # Pad with zeros so distance transform always has a background reference;
    # otherwise images where every pixel is foreground (大形狀貼滿畫面) return inf.
    padded = np.pad(binary, 1, mode="constant", constant_values=0)
    dt_padded = cv2.distanceTransform(padded, cv2.DIST_L2, 5)
    dt = dt_padded[1:-1, 1:-1]
    skel = skeletonize(binary > 0)
    widths = (dt[skel].astype(np.float64) * 2.0)
    widths = widths[np.isfinite(widths)]
    if widths.size == 0:
        return _empty_width_result(n_fg)
    return {
        "n_fg_px": n_fg,
        "n_skel_px": int(widths.size),
        "sw_median": float(np.median(widths)),
        "sw_p25": float(np.percentile(widths, 25)),
        "sw_p75": float(np.percentile(widths, 75)),
        "sw_max": float(widths.max()),
        "sub_rayleigh_frac": float((widths <= RAYLEIGH_PX).mean()),
    }


def _empty_width_result(n_fg: int) -> dict:
    return {
        "n_fg_px": n_fg,
        "n_skel_px": 0,
        "sw_median": float("nan"),
        "sw_p25": float("nan"),
        "sw_p75": float("nan"),
        "sw_max": float("nan"),
        "sub_rayleigh_frac": float("nan"),
    }


def classify_rayleigh(sub_frac: float) -> str:
    if not math.isfinite(sub_frac):
        return "unknown"
    if sub_frac < 0.25:
        return "supra"
    if sub_frac > 0.75:
        return "sub"
    return "mixed"


def resolve_lbl_path(dataset: str, stage: str, frame_id: str) -> Optional[Path]:
    base = DATASET_LBL.get(dataset)
    if base is None:
        return None
    fname = frame_id if frame_id.endswith(".bmp") else f"{frame_id}.bmp"
    return base / stage / fname


def load_csv_rows(csv_path: Path) -> tuple[list[str], list[dict]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rdr = csv.DictReader(fh)
        rows = list(rdr)
        fields = list(rdr.fieldnames or [])
    return fields, rows


def augment_with_widths(rows: list[dict]) -> dict[tuple[str, str, str], dict]:
    cache: dict[tuple[str, str, str], dict] = {}
    n_missing = 0
    n_unique = 0
    for r in rows:
        key = (r["dataset"], r["stage"], r["frame_id"])
        if key in cache:
            continue
        n_unique += 1
        p = resolve_lbl_path(*key)
        if p is None or not p.exists():
            n_missing += 1
            cache[key] = _empty_width_result(0)
            continue
        lbl = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        cache[key] = compute_feature_widths(lbl)
    if n_missing:
        print(f"WARN: {n_missing} / {n_unique} unique (dataset, stage, frame_id) GT path missing")
    else:
        print(f"All {n_unique} unique GT images resolved")
    return cache


def to_float(value) -> float:
    try:
        f = float(value)
        return f if math.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def write_augmented_csv(
    out_path: Path,
    fields: list[str],
    rows: list[dict],
    widths: dict,
) -> None:
    extra = [
        "sw_median_px",
        "sw_p25_px",
        "sw_p75_px",
        "sw_max_px",
        "sub_rayleigh_frac",
        "rayleigh_class",
        "n_fg_px",
        "n_skel_px",
    ]
    new_fields = list(fields) + extra
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=new_fields)
        wr.writeheader()
        for r in rows:
            w = widths[(r["dataset"], r["stage"], r["frame_id"])]
            out = dict(r)
            out["sw_median_px"] = w["sw_median"]
            out["sw_p25_px"] = w["sw_p25"]
            out["sw_p75_px"] = w["sw_p75"]
            out["sw_max_px"] = w["sw_max"]
            out["sub_rayleigh_frac"] = w["sub_rayleigh_frac"]
            out["rayleigh_class"] = classify_rayleigh(w["sub_rayleigh_frac"])
            out["n_fg_px"] = w["n_fg_px"]
            out["n_skel_px"] = w["n_skel_px"]
            wr.writerow(out)


def aggregate_by_class(rows: list[dict], widths: dict) -> list[dict]:
    bins: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for r in rows:
        w = widths[(r["dataset"], r["stage"], r["frame_id"])]
        cls = classify_rayleigh(w["sub_rayleigh_frac"])
        key = (r["model"], cls)
        counts[key] += 1
        for col, _ in METRIC_COLS:
            v = to_float(r.get(col))
            if math.isfinite(v):
                bins[key][col].append(v)
    out = []
    for (model, cls), metrics in sorted(bins.items()):
        row = {"model": model, "rayleigh_class": cls, "n_images": counts[(model, cls)]}
        for col, _ in METRIC_COLS:
            vals = metrics.get(col, [])
            row[f"{col}_mean"] = float(np.mean(vals)) if vals else float("nan")
            row[f"{col}_median"] = (
                float(np.median(vals)) if vals else float("nan")
            )
            row[f"{col}_n"] = len(vals)
        out.append(row)
    return out


def write_aggregate_csv(out_path: Path, agg: list[dict]) -> None:
    if not agg:
        return
    fields = list(agg[0].keys())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields)
        wr.writeheader()
        for r in agg:
            wr.writerow(r)


def write_summary_md(out_path: Path, agg: list[dict], rayleigh_px: float) -> None:
    by_key: dict[tuple[str, str], dict] = {}
    for r in agg:
        by_key[(r["model"], r["rayleigh_class"])] = r

    lines: list[str] = []
    lines.append("# Rayleigh-aware diagnostic — a025 vs a043 (vs a030 / COMBO)\n")
    lines.append("## 設定\n")
    lines.append(f"- Rayleigh threshold:**{rayleigh_px} px**(=0.61 × 550 nm / NA 0.23 ≈ 1.46 μm @ 125 nm/px)")
    lines.append("- 影像分類:")
    lines.append("  - `supra`:sub_rayleigh_frac < 25%(大部分特徵落在可解析尺度)")
    lines.append("  - `mixed`:25-75%(混合)")
    lines.append("  - `sub`:>75%(大部分特徵落在次解析尺度)")
    lines.append(
        f"- Feature width 演算法:GT 二值化(threshold {GT_THRESH})→ skeletonize → "
        "skeleton pixel 上的 distance transform × 2(stroke width transform)\n"
    )

    lines.append("## 影像分桶分布\n")
    lines.append("| model | supra | mixed | sub | unknown | total |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for m in MODELS_ORDER:
        cells = []
        total = 0
        for c in CLASSES_ORDER:
            n = by_key.get((m, c), {}).get("n_images", 0)
            cells.append(n)
            total += n
        if total == 0:
            continue
        lines.append(
            f"| {m} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {total} |"
        )
    lines.append("")

    for col, direction in METRIC_COLS:
        lines.append(f"## {col} {direction}\n")
        lines.append("| model | supra | mixed | sub |")
        lines.append("|---|---:|---:|---:|")
        for m in MODELS_ORDER:
            cells = []
            for c in ("supra", "mixed", "sub"):
                r = by_key.get((m, c))
                if r is None:
                    cells.append("—")
                else:
                    v = r.get(f"{col}_mean")
                    cells.append(f"{v:.4f}" if math.isfinite(v) else "—")
            lines.append(f"| {m} | {cells[0]} | {cells[1]} | {cells[2]} |")
        lines.append("")

        lines.append("### a043 − a025 delta\n")
        for c in ("supra", "mixed", "sub"):
            a = by_key.get(("a043", c), {}).get(f"{col}_mean", float("nan"))
            b = by_key.get(("R39R40_a025", c), {}).get(f"{col}_mean", float("nan"))
            if math.isfinite(a) and math.isfinite(b):
                lines.append(
                    f"- {c}:a043 = {a:.4f},a025 = {b:.4f},**Δ = {a - b:+.4f}**"
                )
            else:
                lines.append(f"- {c}:—")
        lines.append("")

    lines.append("## 主指標摘要(shape_error_score 越低越好、corner_retention 越高越好)\n")
    se_supra_d = (
        by_key.get(("a043", "supra"), {}).get("shape_error_score_mean", float("nan"))
        - by_key.get(("R39R40_a025", "supra"), {}).get("shape_error_score_mean", float("nan"))
    )
    se_sub_d = (
        by_key.get(("a043", "sub"), {}).get("shape_error_score_mean", float("nan"))
        - by_key.get(("R39R40_a025", "sub"), {}).get("shape_error_score_mean", float("nan"))
    )
    cr_supra_d = (
        by_key.get(("a043", "supra"), {}).get("corner_retention_mean", float("nan"))
        - by_key.get(("R39R40_a025", "supra"), {}).get("corner_retention_mean", float("nan"))
    )
    cr_sub_d = (
        by_key.get(("a043", "sub"), {}).get("corner_retention_mean", float("nan"))
        - by_key.get(("R39R40_a025", "sub"), {}).get("corner_retention_mean", float("nan"))
    )
    lines.append(f"- supra shape_error_score 差(a043 − a025):{se_supra_d:+.4f}")
    lines.append(f"- sub shape_error_score 差(a043 − a025):{se_sub_d:+.4f}")
    lines.append(f"- supra corner_retention 差(a043 − a025):{cr_supra_d:+.4f}")
    lines.append(f"- sub corner_retention 差(a043 − a025):{cr_sub_d:+.4f}")
    lines.append("\n（結論留給人類解讀;本檔只記錄數字。）\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_scatter_plot(
    out_path: Path,
    rows: list[dict],
    widths: dict,
    rayleigh_px: float,
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available; skipping plot")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    panels = [
        ("shape_error_score", "shape_error_score (↓)"),
        ("corner_retention", "corner_retention (↑)"),
        ("straight_edge_coverage", "straight_edge_coverage (↑)"),
        ("boundary_f_score", "boundary_f_score (↑)"),
    ]
    model_colors = {
        "COMBO": "#888888",
        "a030": "#4477AA",
        "a043": "#CC3311",
        "R39R40_a025": "#228833",
    }
    for ax, (col, label) in zip(axes.flat, panels):
        for model, color in model_colors.items():
            xs, ys = [], []
            for r in rows:
                if r["model"] != model:
                    continue
                w = widths[(r["dataset"], r["stage"], r["frame_id"])]
                sw = w.get("sw_median", float("nan"))
                v = to_float(r.get(col))
                if math.isfinite(sw) and math.isfinite(v) and sw > 0:
                    xs.append(sw)
                    ys.append(v)
            ax.scatter(xs, ys, c=color, s=8, alpha=0.4, label=model)
        ax.axvline(
            rayleigh_px,
            color="k",
            ls="--",
            lw=0.8,
            alpha=0.6,
            label=f"Rayleigh = {rayleigh_px} px",
        )
        ax.set_xscale("log")
        ax.set_xlabel("GT median stroke width (px)")
        ax.set_ylabel(label)
        ax.set_title(label)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, loc="best")
    fig.suptitle("Model performance vs GT feature size  (Rayleigh = 11.7 px)")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def main() -> int:
    global RAYLEIGH_PX
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--rayleigh-px", type=float, default=RAYLEIGH_PX)
    args = parser.parse_args()
    RAYLEIGH_PX = float(args.rayleigh_px)

    fields, rows = load_csv_rows(args.csv)
    print(f"Loaded {len(rows)} rows from {args.csv}")

    widths = augment_with_widths(rows)
    print(f"Computed widths for {len(widths)} unique GT images")

    args.out.mkdir(parents=True, exist_ok=True)
    write_augmented_csv(args.out / "per_pair_with_width.csv", fields, rows, widths)
    agg = aggregate_by_class(rows, widths)
    write_aggregate_csv(args.out / "aggregate_by_class.csv", agg)
    write_summary_md(args.out / "rayleigh_summary.md", agg, RAYLEIGH_PX)
    write_scatter_plot(args.out / "feature_width_scatter.png", rows, widths, RAYLEIGH_PX)
    print(f"Wrote outputs to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
