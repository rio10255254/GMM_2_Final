"""R46 視覺驗證:挑特定 case 出六聯對比圖(GT / COMBO / a030 / a043 / a025 / R46)。

跟 rayleigh_visual_verification.py 同設計,但多 R46 一欄。
Case 跟之前一致:紋理大贏、矩形直角、小三角形等。
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
PROJECT_ROOT = Path(__file__).resolve().parents[3]


plt.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei", "Microsoft YaHei", "PingFang TC", "SimHei", "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


REPO_ROOT = Path(str(PROJECT_ROOT))

# R39 / R40 各 model 重建路徑(沿用 rayleigh_visual_verification.py 定義)
R39_RECON_BASE = {
    "COMBO": REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/weight_sweep/shape_recon/a000",
    "a030": REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/weight_sweep/shape_recon/a030",
    "a043": REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/shape_recon/a043",
    "a025": REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/shape_recon/a025",
    "R46": REPO_ROOT / "Experiments/R46_CornerAwareFineTune/results/shape_recon/r46",
}
R40_RECON_FLAT = REPO_ROOT / "Experiments/R40_MicroscopyFeatureCoverage/results/micro_recon"
R40_COMBO_TAG = "20260408_003525"
R40_A030_TAG = "20260430_121954"
R40_A043_BASE = REPO_ROOT / "Experiments/R40_MicroscopyFeatureCoverage/results/weight_sweep/combo_best_low_alpha/micro_recon/a043"
R40_A025_BASE = REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/micro_recon/a025"
R40_R46_BASE = REPO_ROOT / "Experiments/R46_CornerAwareFineTune/results/micro_recon/r46"

R39_LBL_BASE = REPO_ROOT / "Training_Data/r39_shape_generalization/shape_val_unseen/lbl"
R40_LBL_BASE = REPO_ROOT / "Training_Data/r40_microscopy_feature_coverage/micro_val_unseen/lbl"

R46_COMBINED_CSV = (
    REPO_ROOT / "Experiments/R46_CornerAwareFineTune/results"
    / "capability_eval/per_pair_metrics_combined.csv"
)

DEFAULT_OUT = (
    REPO_ROOT / "Experiments/R46_CornerAwareFineTune/results" / "visual_verification"
)

MODELS_ORDER = ["COMBO", "a030", "a043", "a025", "R46"]


def find_recon_in_dir(base: Path, stage: str, frame_id: str, tag: str | None = None) -> Path | None:
    if not base.exists():
        return None
    fname = f"{frame_id}.bmp"
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        if stage not in d.name:
            continue
        if tag is not None and tag not in d.name:
            continue
        for sub in d.iterdir():
            if not sub.is_dir():
                continue
            cand = sub / fname
            if cand.exists():
                return cand
    return None


def resolve_recon(model: str, dataset: str, stage: str, frame_id: str) -> Path | None:
    if dataset == "R39_shape_val_unseen":
        return find_recon_in_dir(R39_RECON_BASE[model], stage, frame_id)
    elif dataset == "R40_micro_val_unseen":
        if model == "COMBO":
            return find_recon_in_dir(R40_RECON_FLAT, stage, frame_id, tag=R40_COMBO_TAG)
        elif model == "a030":
            return find_recon_in_dir(R40_RECON_FLAT, stage, frame_id, tag=R40_A030_TAG)
        elif model == "a043":
            return find_recon_in_dir(R40_A043_BASE, stage, frame_id)
        elif model == "a025":
            return find_recon_in_dir(R40_A025_BASE, stage, frame_id)
        elif model == "R46":
            return find_recon_in_dir(R40_R46_BASE, stage, frame_id)
    return None


def resolve_gt(dataset: str, stage: str, frame_id: str) -> Path:
    if dataset == "R39_shape_val_unseen":
        return R39_LBL_BASE / stage / f"{frame_id}.bmp"
    elif dataset == "R40_micro_val_unseen":
        return R40_LBL_BASE / stage / f"{frame_id}.bmp"
    raise ValueError(f"unknown dataset {dataset}")


def fnum(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load_metrics(case_keys: list[tuple]) -> dict:
    out = {k: {} for k in case_keys}
    if not R46_COMBINED_CSV.exists():
        print(f"WARN: combined csv missing: {R46_COMBINED_CSV}")
        return out
    with R46_COMBINED_CSV.open("r", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            k = (r["dataset"], r["stage"], r["frame_id"])
            if k not in out:
                continue
            m = r["model"]
            if m == "R39R40_a025":
                mlabel = "a025"
            elif m == "R46_a025_corner_finetune":
                mlabel = "R46"
            else:
                mlabel = m
            out[k][mlabel] = {
                "psnr": fnum(r.get("psnr")),
                "shape_error_score": fnum(r.get("shape_error_score")),
                "corner_retention": fnum(r.get("corner_retention")),
                "boundary_f_score": fnum(r.get("boundary_f_score")),
            }
    return out


def make_zoom_figure(case: tuple, out_path: Path, title: str = "") -> None:
    """單 case 大圖:GT + 5 models + summary。"""
    ds, stage, fid, note = case
    metrics_map = load_metrics([(ds, stage, fid)])
    mm = metrics_map[(ds, stage, fid)]

    fig, axes = plt.subplots(1, 7, figsize=(32, 6))

    gt_path = resolve_gt(ds, stage, fid)
    gt_img = cv2.imread(str(gt_path), cv2.IMREAD_UNCHANGED) if gt_path.exists() else None
    ax = axes[0]
    if gt_img is not None:
        ax.imshow(gt_img, cmap="gray", vmin=0, vmax=255)
    ax.set_title(f"GT(真值)\n{stage}\nframe {fid}\n{note}", fontsize=12)
    ax.axis("off")

    for ci, m in enumerate(MODELS_ORDER, start=1):
        ax = axes[ci]
        p = resolve_recon(m, ds, stage, fid)
        if p is not None and p.exists():
            img = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
            ax.imshow(img, cmap="gray", vmin=0, vmax=255)
            md = mm.get(m, {})
            psnr = md.get("psnr", float("nan"))
            se = md.get("shape_error_score", float("nan"))
            cr = md.get("corner_retention", float("nan"))
            bf = md.get("boundary_f_score", float("nan"))
            ax.set_title(
                f"{m}\nPSNR={psnr:.2f} dB\nshape_err={se:.3f}\ncorner_ret={cr:.3f}\nboundary_F={bf:.3f}",
                fontsize=11,
            )
        else:
            ax.text(0.5, 0.5, f"{m}\n(no recon)", ha="center", va="center", color="red", fontsize=14)
            ax.set_title(f"{m}", fontsize=12)
        ax.axis("off")

    ax = axes[6]
    m_r46 = mm.get("R46", {})
    m_a025 = mm.get("a025", {})
    m_a043 = mm.get("a043", {})
    if m_r46 and m_a025:
        dpsnr_r46_a025 = m_r46.get("psnr", 0) - m_a025.get("psnr", 0)
        dpsnr_r46_a043 = m_r46.get("psnr", 0) - m_a043.get("psnr", 0)
        text = (
            f"R46 vs a025:\n"
            f"  d_PSNR = {dpsnr_r46_a025:+.2f} dB\n\n"
            f"R46 vs a043:\n"
            f"  d_PSNR = {dpsnr_r46_a043:+.2f} dB"
        )
        color = "green" if dpsnr_r46_a025 > 0 else "red"
        ax.text(0.5, 0.5, text, ha="center", va="center", color=color, fontsize=11,
                bbox=dict(boxstyle="round", facecolor="white", edgecolor=color, linewidth=2))
    ax.axis("off")
    ax.set_title("R46 對比", fontsize=12)

    fig.suptitle(title, fontsize=14, y=0.995, weight="bold")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path.name}")


ZOOM_CASES = [
    (
        "zoom_1_textures_a043_big_win.png",
        ("R40_micro_val_unseen", "stage_31_micro_textures", "0084", "前一輪 a043 大贏 a025 +3.46 dB"),
        "紋理 case:R46 能不能拿到接近 a043 的水準?",
    ),
    (
        "zoom_2_triangle_sub_rayleigh.png",
        ("R39_shape_val_unseen", "stage_01_triangles", "0097", "sw_median=6.0px,次解析尺度物理上限"),
        "小三角形 case:R46 在次解析尺度能改善嗎?(理論上不能)",
    ),
    (
        "zoom_3_rectangle_right_angles.png",
        ("R39_shape_val_unseen", "stage_03_rectangles", "0275", "矩形直角(user 原始抱怨)"),
        "矩形直角 case:R46 比 a025 更接近物理下限(R=5px)?",
    ),
    (
        "zoom_4_ellipse_a043_small_loss.png",
        ("R39_shape_val_unseen", "stage_04_ellipses", "0381", "前一輪 a043 微輸 -0.66 dB"),
        "大橢圓 case:R46 在已經很容易的 case 上會不會像 a043 一樣微輸?",
    ),
    (
        "zoom_5_large_region_a043_win.png",
        ("R40_micro_val_unseen", "stage_30_micro_large_regions", "0083", "前一輪 a043 贏 +2.68 dB"),
        "大區塊 case:R46 改善幅度?",
    ),
    (
        "zoom_6_polygons.png",
        ("R39_shape_val_unseen", "stage_05_polygons", "0494", "多邊形(前一輪以為 a025 贏 a043,實為雜訊)"),
        "多邊形 case:R46 視覺改善有顯著嗎?",
    ),
]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    zoom_dir = args.out / "zoom"
    zoom_dir.mkdir(parents=True, exist_ok=True)

    print(f"[R46 visual] outputs -> {args.out}")
    for fname, case, title in ZOOM_CASES:
        make_zoom_figure(case, zoom_dir / fname, title=title)
    print(f"[R46 visual] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
