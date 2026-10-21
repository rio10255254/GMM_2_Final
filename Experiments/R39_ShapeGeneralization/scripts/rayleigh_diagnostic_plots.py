"""額外視覺化:讀 per_pair_with_width.csv,出多張不同角度的圖。

每張圖獨立有用,以後做報告 / 簡報 / debug 都可挑用。
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


REPO_ROOT = Path("D:/GMM_2_Final")
DEFAULT_CSV = (
    REPO_ROOT
    / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep"
    / "rayleigh_diagnostic/per_pair_with_width.csv"
)
DEFAULT_OUT = (
    REPO_ROOT
    / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep"
    / "rayleigh_diagnostic/plots"
)

RAYLEIGH_PX = 11.7
MODEL_COLORS = {
    "COMBO": "#888888",
    "a030": "#4477AA",
    "a043": "#CC3311",
    "R39R40_a025": "#228833",
}
MODEL_ORDER = ["COMBO", "a030", "a043", "R39R40_a025"]
CLASSES = ["supra", "mixed", "sub"]


def load_rows(csv_path: Path) -> list[dict]:
    with csv_path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def fnum(v) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def fig1_feature_width_distribution(rows: list[dict], out_path: Path) -> None:
    """直方圖:全部 GT 影像的 stroke width median 分布,按 dataset 分色。"""
    seen: dict[tuple, tuple] = {}
    for r in rows:
        key = (r["dataset"], r["stage"], r["frame_id"])
        if key in seen:
            continue
        sw = fnum(r.get("sw_median_px"))
        if math.isfinite(sw) and sw > 0:
            seen[key] = (r["dataset"], sw)

    by_dataset: dict[str, list[float]] = defaultdict(list)
    for ds, sw in seen.values():
        by_dataset[ds].append(sw)

    fig, ax = plt.subplots(figsize=(10, 5))
    bins = np.logspace(0, 3, 40)
    palette = {
        "R39_shape_val_unseen": "#4477AA",
        "R40_micro_val_unseen": "#EE7733",
    }
    for ds, widths in by_dataset.items():
        ax.hist(
            widths,
            bins=bins,
            alpha=0.6,
            label=f"{ds} (n={len(widths)})",
            color=palette.get(ds, "#666"),
        )
    ax.axvline(RAYLEIGH_PX, color="k", ls="--", lw=1.0, label=f"Rayleigh = {RAYLEIGH_PX} px")
    ax.set_xscale("log")
    ax.set_xlabel("GT median stroke width (px)")
    ax.set_ylabel("Image count")
    ax.set_title("Feature width distribution across validation GT")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def fig2_a043_vs_a025_delta(rows: list[dict], out_path: Path) -> None:
    """4 panel scatter: 每張圖的 a043 - a025 delta,x = sw_median,y = delta。"""
    by_image: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        key = (r["dataset"], r["stage"], r["frame_id"])
        by_image[key][r["model"]] = r

    metrics = [
        ("shape_error_score", "shape_error (lower = better)", True),
        ("corner_retention", "corner_retention (higher = better)", False),
        ("straight_edge_coverage", "straight_edge_coverage", False),
        ("boundary_f_score", "boundary_f_score", False),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for ax, (col, label, inverted) in zip(axes.flat, metrics):
        xs, ys = [], []
        for mdict in by_image.values():
            if "a043" not in mdict or "R39R40_a025" not in mdict:
                continue
            sw = fnum(mdict["a043"].get("sw_median_px"))
            v043 = fnum(mdict["a043"].get(col))
            v025 = fnum(mdict["R39R40_a025"].get(col))
            if math.isfinite(sw) and math.isfinite(v043) and math.isfinite(v025) and sw > 0:
                xs.append(sw)
                ys.append(v025 - v043 if inverted else v043 - v025)
        colors = ["#228833" if y >= 0 else "#CC3311" for y in ys]
        ax.scatter(xs, ys, s=14, alpha=0.55, c=colors, edgecolors="none")
        ax.axhline(0, color="k", ls="-", lw=0.6, alpha=0.6)
        ax.axvline(RAYLEIGH_PX, color="k", ls="--", lw=0.8, alpha=0.6, label=f"Rayleigh = {RAYLEIGH_PX} px")
        ax.set_xscale("log")
        ax.set_xlabel("GT median stroke width (px)")
        ax.set_ylabel(f"a043 advantage over a025 [{col}]")
        ax.set_title(label)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, loc="best")
    fig.suptitle(
        "Per-image: a043 vs a025 delta  (green = a043 better, red = a025 better)"
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def fig3_box_per_class(rows: list[dict], out_path: Path) -> None:
    """4 panel box plot: 每 panel 一指標,x 軸 3 class × 4 model 並列。"""
    metrics = [
        ("shape_error_score", "shape_error_score (↓)"),
        ("corner_retention", "corner_retention (↑)"),
        ("straight_edge_coverage", "straight_edge_coverage (↑)"),
        ("boundary_f_score", "boundary_f_score (↑)"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for ax, (col, label) in zip(axes.flat, metrics):
        groups: dict[tuple[str, str], list[float]] = defaultdict(list)
        for r in rows:
            cls = r.get("rayleigh_class")
            model = r.get("model")
            v = fnum(r.get(col))
            if cls in CLASSES and model in MODEL_ORDER and math.isfinite(v):
                groups[(cls, model)].append(v)
        positions, data, colors = [], [], []
        for ci, cls in enumerate(CLASSES):
            for mi, m in enumerate(MODEL_ORDER):
                pos = ci * 5 + mi
                vals = groups.get((cls, m), [])
                if vals:
                    positions.append(pos)
                    data.append(vals)
                    colors.append(MODEL_COLORS[m])
        bp = ax.boxplot(
            data,
            positions=positions,
            widths=0.7,
            patch_artist=True,
            showfliers=False,
            medianprops={"color": "black", "linewidth": 1.2},
        )
        for patch, c in zip(bp["boxes"], colors):
            patch.set_facecolor(c)
            patch.set_alpha(0.65)
        ax.set_xticks([ci * 5 + 1.5 for ci in range(len(CLASSES))])
        ax.set_xticklabels(CLASSES)
        ax.set_ylabel(label)
        ax.set_title(label)
        ax.grid(True, axis="y", alpha=0.3)
        handles = [
            plt.Rectangle((0, 0), 1, 1, fc=MODEL_COLORS[m], alpha=0.65) for m in MODEL_ORDER
        ]
        ax.legend(handles, MODEL_ORDER, fontsize=8, loc="best")
    fig.suptitle("Distribution per Rayleigh class × model  (box plot, fliers hidden)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def fig4_per_stage_bars(rows: list[dict], out_path: Path) -> None:
    """4 panel × 12 stage: 每 stage 4 model 的 mean 長條。"""
    metrics = [
        ("shape_error_score", "shape_error_score (↓)"),
        ("corner_retention", "corner_retention (↑)"),
        ("straight_edge_coverage", "straight_edge_coverage (↑)"),
        ("boundary_f_score", "boundary_f_score (↑)"),
    ]
    stage_order = sorted(set(r["stage"] for r in rows))
    fig, axes = plt.subplots(4, 1, figsize=(15, 18))
    for ax, (col, label) in zip(axes, metrics):
        accum: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for r in rows:
            v = fnum(r.get(col))
            if math.isfinite(v):
                accum[r["stage"]][r["model"]].append(v)
        x = np.arange(len(stage_order))
        width = 0.2
        for i, m in enumerate(MODEL_ORDER):
            ys = []
            for st in stage_order:
                vals = accum.get(st, {}).get(m, [])
                ys.append(float(np.mean(vals)) if vals else float("nan"))
            ax.bar(
                x + (i - 1.5) * width,
                ys,
                width,
                color=MODEL_COLORS[m],
                label=m,
                alpha=0.85,
            )
        ax.set_xticks(x)
        ax.set_xticklabels(
            [s.replace("stage_", "") for s in stage_order],
            rotation=30,
            ha="right",
            fontsize=8,
        )
        ax.set_ylabel(label)
        ax.set_title(f"{col} mean per stage")
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend(fontsize=7, loc="best")
    fig.suptitle("Per-stage mean metrics by model")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def fig5_a043_minus_a025_per_stage(rows: list[dict], out_path: Path) -> None:
    """2 panel:每個 stage 上 a043 - a025 的 delta(corner_retention 跟 shape_error_score)。"""
    stage_order = sorted(set(r["stage"] for r in rows))
    by_image: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        key = (r["dataset"], r["stage"], r["frame_id"])
        by_image[key][r["model"]] = r

    metrics = [
        ("corner_retention", "corner_retention (a043 − a025)", False),
        ("shape_error_score", "shape_error improvement (a025 − a043)", True),
    ]
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    for ax, (col, label, inverted) in zip(axes, metrics):
        stage_deltas: dict[str, list[float]] = defaultdict(list)
        for mdict in by_image.values():
            if "a043" not in mdict or "R39R40_a025" not in mdict:
                continue
            stage = mdict["a043"]["stage"]
            v043 = fnum(mdict["a043"].get(col))
            v025 = fnum(mdict["R39R40_a025"].get(col))
            if math.isfinite(v043) and math.isfinite(v025):
                d = (v025 - v043) if inverted else (v043 - v025)
                stage_deltas[stage].append(d)
        means, sems = [], []
        for st in stage_order:
            arr = stage_deltas.get(st, [])
            if arr:
                means.append(float(np.mean(arr)))
                sems.append(float(np.std(arr) / np.sqrt(len(arr))))
            else:
                means.append(float("nan"))
                sems.append(0.0)
        x = np.arange(len(stage_order))
        colors = ["#228833" if m > 0 else "#CC3311" for m in means]
        ax.bar(x, means, color=colors, alpha=0.8, yerr=sems, capsize=3, edgecolor="black", linewidth=0.5)
        ax.axhline(0, color="k", ls="-", lw=0.6)
        ax.set_xticks(x)
        ax.set_xticklabels(
            [s.replace("stage_", "") for s in stage_order],
            rotation=30,
            ha="right",
            fontsize=9,
        )
        ax.set_ylabel(label)
        ax.set_title(f"{label}  (green = a043 wins this stage, red = a025 wins)")
        ax.grid(True, axis="y", alpha=0.3)
    fig.suptitle("a043 − a025 delta per stage  (error bars = standard error)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def fig6_corner_retention_distributions(rows: list[dict], out_path: Path) -> None:
    """3 panel:supra / mixed / sub 各畫 corner_retention 的 model histogram 比較。"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
    bins = np.linspace(0, 1, 30)
    for ax, cls in zip(axes, CLASSES):
        for m in MODEL_ORDER:
            vals = [
                fnum(r["corner_retention"])
                for r in rows
                if r["model"] == m and r["rayleigh_class"] == cls
            ]
            vals = [v for v in vals if math.isfinite(v)]
            if not vals:
                continue
            ax.hist(
                vals,
                bins=bins,
                histtype="step",
                color=MODEL_COLORS[m],
                linewidth=2,
                label=f"{m} (n={len(vals)})",
            )
        ax.set_xlabel("corner_retention")
        ax.set_title(f"{cls}-Rayleigh class")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    axes[0].set_ylabel("Image count")
    fig.suptitle(
        "corner_retention distribution per Rayleigh class  (step histogram, 4 models overlaid)"
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def fig7_stage_overview_scatter(rows: list[dict], out_path: Path) -> None:
    """單張總覽:x = 該 stage 平均 stroke width,y = a043 比 a025 在 corner_retention 強多少,size = 該 stage 樣本數。"""
    by_image: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        key = (r["dataset"], r["stage"], r["frame_id"])
        by_image[key][r["model"]] = r

    stage_meta: dict[str, dict] = defaultdict(lambda: {"sw": [], "delta_corner": [], "delta_shape": []})
    for mdict in by_image.values():
        if "a043" not in mdict or "R39R40_a025" not in mdict:
            continue
        stage = mdict["a043"]["stage"]
        sw = fnum(mdict["a043"].get("sw_median_px"))
        v043_corner = fnum(mdict["a043"].get("corner_retention"))
        v025_corner = fnum(mdict["R39R40_a025"].get("corner_retention"))
        v043_shape = fnum(mdict["a043"].get("shape_error_score"))
        v025_shape = fnum(mdict["R39R40_a025"].get("shape_error_score"))
        if math.isfinite(sw):
            stage_meta[stage]["sw"].append(sw)
        if math.isfinite(v043_corner) and math.isfinite(v025_corner):
            stage_meta[stage]["delta_corner"].append(v043_corner - v025_corner)
        if math.isfinite(v043_shape) and math.isfinite(v025_shape):
            stage_meta[stage]["delta_shape"].append(v025_shape - v043_shape)

    fig, ax = plt.subplots(figsize=(12, 7))
    for stage, meta in sorted(stage_meta.items()):
        if not meta["sw"] or not meta["delta_corner"]:
            continue
        x = float(np.mean(meta["sw"]))
        y = float(np.mean(meta["delta_corner"]))
        n = len(meta["delta_corner"])
        color = "#CC3311" if stage.startswith("stage_29") or stage.startswith("stage_30") or stage.startswith("stage_31") or stage.startswith("stage_32") or stage.startswith("stage_33") else "#4477AA"
        ax.scatter(x, y, s=max(50, n * 4), alpha=0.7, color=color, edgecolor="black")
        ax.annotate(
            stage.replace("stage_", ""),
            (x, y),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
        )
    ax.axhline(0, color="k", ls="-", lw=0.6)
    ax.axvline(RAYLEIGH_PX, color="k", ls="--", lw=0.8, alpha=0.7, label=f"Rayleigh = {RAYLEIGH_PX} px")
    ax.set_xscale("log")
    ax.set_xlabel("stage mean GT stroke width (px)")
    ax.set_ylabel("a043 − a025  (corner_retention)")
    ax.set_title(
        "Stage overview: feature size vs a043 advantage  (blue = R39 shape, red = R40 micro)"
    )
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows = load_rows(args.csv)
    print(f"Loaded {len(rows)} rows from {args.csv}")

    figs = [
        ("1_feature_width_distribution.png", fig1_feature_width_distribution),
        ("2_a043_vs_a025_delta_scatter.png", fig2_a043_vs_a025_delta),
        ("3_box_per_class.png", fig3_box_per_class),
        ("4_per_stage_metric_bars.png", fig4_per_stage_bars),
        ("5_a043_minus_a025_per_stage.png", fig5_a043_minus_a025_per_stage),
        ("6_corner_retention_distributions.png", fig6_corner_retention_distributions),
        ("7_stage_overview_scatter.png", fig7_stage_overview_scatter),
    ]
    for name, fn in figs:
        fn(rows, args.out / name)
        print(f"  wrote {name}")
    print(f"Done -> {args.out}")


if __name__ == "__main__":
    main()
