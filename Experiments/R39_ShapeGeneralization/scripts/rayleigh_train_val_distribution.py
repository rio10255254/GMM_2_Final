"""對 R39 / R40 train / val 各自算 stroke width 分布,看訓練資料覆蓋是否對齊驗證分布。

對 R46 重要:如果 train 主要在大形狀(supra-Rayleigh)、val 有不少 sub,
那 fine-tune 加新資料時要先補 sub-Rayleigh 樣本。

Profiles:
  - R39 train (safe)
  - R39 train (strong)
  - R39 val (shape_val_unseen)
  - R40 train (r40_micro_capacity_train,只看新加的 stage_29-33)
  - R40 val (micro_val_unseen)

Outputs:
  - feature_width_per_profile.csv  逐影像 sw_median + class
  - profile_summary.csv            每 profile 的 supra/mixed/sub 比例 + median sw
  - distribution_overlay.png       五個 profile 的直方圖疊放
"""
from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path

import cv2
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from skimage.morphology import skeletonize


REPO_ROOT = Path("D:/GMM_2_Final")
RAYLEIGH_PX = 11.7
GT_THRESH = 50

DEFAULT_OUT = (
    REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep"
    / "rayleigh_diagnostic/train_val_distribution"
)

PROFILES = [
    (
        "R39_train_safe",
        REPO_ROOT / "Training_Data/r39_shape_generalization/r39_shape_mix_safe/lbl",
        None,
    ),
    (
        "R39_train_strong",
        REPO_ROOT / "Training_Data/r39_shape_generalization/r39_shape_mix_strong/lbl",
        None,
    ),
    (
        "R39_val_unseen",
        REPO_ROOT / "Training_Data/r39_shape_generalization/shape_val_unseen/lbl",
        None,
    ),
    (
        "R40_train_microscopy",
        REPO_ROOT / "Training_Data/r40_microscopy_feature_coverage/r40_micro_capacity_train/lbl",
        # 只看新加的顯微 stage 29-33,排掉 ring / R39 replay 那段
        {"stage_29_micro_lines_grid", "stage_30_micro_large_regions",
         "stage_31_micro_textures", "stage_32_micro_edge_defects", "stage_33_micro_mixed_fields"},
    ),
    (
        "R40_val_unseen",
        REPO_ROOT / "Training_Data/r40_microscopy_feature_coverage/micro_val_unseen/lbl",
        None,
    ),
]


def compute_widths(lbl_image: np.ndarray) -> dict:
    binary = (lbl_image > GT_THRESH).astype(np.uint8)
    n_fg = int(binary.sum())
    if n_fg == 0:
        return {"sw_median": float("nan"), "sub_frac": float("nan"), "n_fg_px": 0, "n_skel_px": 0}
    padded = np.pad(binary, 1, mode="constant", constant_values=0)
    dt_padded = cv2.distanceTransform(padded, cv2.DIST_L2, 5)
    dt = dt_padded[1:-1, 1:-1]
    skel = skeletonize(binary > 0)
    widths = (dt[skel].astype(np.float64) * 2.0)
    widths = widths[np.isfinite(widths)]
    if widths.size == 0:
        return {"sw_median": float("nan"), "sub_frac": float("nan"), "n_fg_px": n_fg, "n_skel_px": 0}
    return {
        "sw_median": float(np.median(widths)),
        "sub_frac": float((widths <= RAYLEIGH_PX).mean()),
        "n_fg_px": n_fg,
        "n_skel_px": int(widths.size),
    }


def classify(sub_frac: float) -> str:
    if not math.isfinite(sub_frac):
        return "unknown"
    if sub_frac < 0.25:
        return "supra"
    if sub_frac > 0.75:
        return "sub"
    return "mixed"


def scan_profile(base: Path, stage_filter: set | None) -> list[dict]:
    rows: list[dict] = []
    if not base.exists():
        print(f"  WARN: {base} does not exist")
        return rows
    for stage_dir in sorted(base.iterdir()):
        if not stage_dir.is_dir():
            continue
        stage = stage_dir.name
        if stage_filter is not None and stage not in stage_filter:
            continue
        for f in sorted(stage_dir.iterdir()):
            if not f.is_file() or not f.suffix.lower() == ".bmp":
                continue
            img = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)
            if img is None:
                continue
            r = compute_widths(img)
            rows.append({
                "stage": stage,
                "frame_id": f.stem,
                **r,
                "rayleigh_class": classify(r["sub_frac"]),
            })
    return rows


def write_per_profile_csv(out_path: Path, all_rows: dict[str, list[dict]]) -> None:
    fields = ["profile", "stage", "frame_id", "sw_median", "sub_frac",
              "n_fg_px", "n_skel_px", "rayleigh_class"]
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields)
        wr.writeheader()
        for profile, rows in all_rows.items():
            for r in rows:
                out_row = {"profile": profile, **r}
                wr.writerow(out_row)


def write_summary_csv(out_path: Path, all_rows: dict[str, list[dict]]) -> None:
    fields = ["profile", "n", "median_sw_px", "supra_frac", "mixed_frac", "sub_frac",
              "n_supra", "n_mixed", "n_sub"]
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields)
        wr.writeheader()
        for profile, rows in all_rows.items():
            valid = [r for r in rows if math.isfinite(r.get("sw_median", float("nan")))]
            n = len(valid)
            if n == 0:
                continue
            sw_arr = np.array([r["sw_median"] for r in valid])
            cls_counts = {"supra": 0, "mixed": 0, "sub": 0}
            for r in valid:
                cls = r["rayleigh_class"]
                if cls in cls_counts:
                    cls_counts[cls] += 1
            wr.writerow({
                "profile": profile,
                "n": n,
                "median_sw_px": round(float(np.median(sw_arr)), 4),
                "supra_frac": round(cls_counts["supra"] / n, 4),
                "mixed_frac": round(cls_counts["mixed"] / n, 4),
                "sub_frac": round(cls_counts["sub"] / n, 4),
                "n_supra": cls_counts["supra"],
                "n_mixed": cls_counts["mixed"],
                "n_sub": cls_counts["sub"],
            })


def plot_distribution(out_path: Path, all_rows: dict[str, list[dict]]) -> None:
    colors = {
        "R39_train_safe": "#88CCEE",
        "R39_train_strong": "#4477AA",
        "R39_val_unseen": "#332288",
        "R40_train_microscopy": "#EE7733",
        "R40_val_unseen": "#CC3311",
    }
    fig, ax = plt.subplots(figsize=(12, 6))
    bins = np.logspace(0, 3, 50)
    for profile, rows in all_rows.items():
        sw = [r["sw_median"] for r in rows if math.isfinite(r.get("sw_median", float("nan")))]
        if not sw:
            continue
        ax.hist(
            sw, bins=bins, histtype="step", color=colors.get(profile, "#666"),
            linewidth=1.8, label=f"{profile} (n={len(sw)})", density=True,
        )
    ax.axvline(RAYLEIGH_PX, color="k", ls="--", lw=1.2, label=f"Rayleigh = {RAYLEIGH_PX} px")
    ax.set_xscale("log")
    ax.set_xlabel("GT median stroke width (px)")
    ax.set_ylabel("Density (normalised)")
    ax.set_title("Feature width distribution: train vs val per profile")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc="best")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_class_bar(out_path: Path, all_rows: dict[str, list[dict]]) -> None:
    """Stacked bar:supra / mixed / sub 比例 per profile。"""
    profiles = list(all_rows.keys())
    supra_pct, mixed_pct, sub_pct = [], [], []
    for p in profiles:
        rows = [r for r in all_rows[p] if math.isfinite(r.get("sw_median", float("nan")))]
        n = len(rows)
        if n == 0:
            supra_pct.append(0); mixed_pct.append(0); sub_pct.append(0); continue
        ctr = {"supra": 0, "mixed": 0, "sub": 0}
        for r in rows:
            cls = r["rayleigh_class"]
            if cls in ctr:
                ctr[cls] += 1
        supra_pct.append(ctr["supra"] / n * 100)
        mixed_pct.append(ctr["mixed"] / n * 100)
        sub_pct.append(ctr["sub"] / n * 100)
    fig, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(len(profiles))
    ax.bar(x, supra_pct, label="supra-Rayleigh", color="#228833", alpha=0.85)
    ax.bar(x, mixed_pct, bottom=supra_pct, label="mixed", color="#DDCC77", alpha=0.85)
    ax.bar(x, sub_pct,
           bottom=[s + m for s, m in zip(supra_pct, mixed_pct)],
           label="sub-Rayleigh", color="#CC3311", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(profiles, rotation=20, ha="right")
    ax.set_ylabel("Fraction of images (%)")
    ax.set_title("Rayleigh class composition per profile (stacked)")
    ax.legend(loc="best")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    all_rows: dict[str, list[dict]] = {}
    for name, base, stage_filter in PROFILES:
        print(f"scanning {name} -> {base}")
        rows = scan_profile(base, stage_filter)
        print(f"  got {len(rows)} images")
        all_rows[name] = rows

    write_per_profile_csv(args.out / "feature_width_per_profile.csv", all_rows)
    write_summary_csv(args.out / "profile_summary.csv", all_rows)
    plot_distribution(args.out / "distribution_overlay.png", all_rows)
    plot_class_bar(args.out / "class_composition_bar.png", all_rows)
    print(f"Done -> {args.out}")


if __name__ == "__main__":
    main()
