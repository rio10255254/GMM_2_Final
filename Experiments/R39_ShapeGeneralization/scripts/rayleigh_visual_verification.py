"""Visual verification:挑特定 case 出五聯對比圖(GT / COMBO / a030 / a043 / a025)。

目的:
1. 驗證指標差距 ↔ 視覺感受對應(a043 大贏紋理 case 真的看起來差很多嗎?)
2. 直接回答 user 原始問題(「直角變圓、三角形變一坨」)
3. 驗證 a043 微輸的大形狀 case 是不是「a043 過度銳化」現象

Cases 分四組:
- top_wins_textures:a043 PSNR 贏 a025 最多的紋理 case
- a043_small_losses:a043 微輸的大形狀 case
- rectangles_right_angles:直角(R39 stage_03_rectangles)
- triangles_small:小三角形(stage_01_triangles 中 sw_median 最小)
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import cv2
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 設定中文字型,避免 title / suptitle 變方塊
plt.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "PingFang TC",
    "SimHei",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False


REPO_ROOT = Path(str(PROJECT_ROOT))

R39_RECON_BASE = {
    "COMBO": REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/weight_sweep/shape_recon/a000",
    "a030": REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/weight_sweep/shape_recon/a030",
    "a043": REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/shape_recon/a043",
    "a025": REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/shape_recon/a025",
}
R40_RECON_FLAT = REPO_ROOT / "Experiments/R40_MicroscopyFeatureCoverage/results/micro_recon"
R40_COMBO_TAG = "20260408_003525"
R40_A030_TAG = "20260430_121954"
R40_A043_BASE = REPO_ROOT / "Experiments/R40_MicroscopyFeatureCoverage/results/weight_sweep/combo_best_low_alpha/micro_recon/a043"
R40_A025_BASE = REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/micro_recon/a025"
R39_LBL_BASE = REPO_ROOT / "Training_Data/r39_shape_generalization/shape_val_unseen/lbl"
R40_LBL_BASE = REPO_ROOT / "Training_Data/r40_microscopy_feature_coverage/micro_val_unseen/lbl"
CSV_PATH = (
    REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep"
    / "rayleigh_diagnostic/per_pair_with_width.csv"
)
DEFAULT_OUT = (
    REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep"
    / "rayleigh_diagnostic/visual_verification"
)


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
        # 第二層:`<profile>_<stage>_best_tradeoff.pth/`
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
    out: dict = {k: {} for k in case_keys}
    with CSV_PATH.open("r", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            k = (r["dataset"], r["stage"], r["frame_id"])
            if k not in out:
                continue
            mlabel = "a025" if r["model"] == "R39R40_a025" else r["model"]
            out[k][mlabel] = {
                "psnr": fnum(r.get("psnr")),
                "shape_error_score": fnum(r.get("shape_error_score")),
                "corner_retention": fnum(r.get("corner_retention")),
                "boundary_f_score": fnum(r.get("boundary_f_score")),
                "sw_median_px": fnum(r.get("sw_median_px")),
                "sub_rayleigh_frac": fnum(r.get("sub_rayleigh_frac")),
                "rayleigh_class": r.get("rayleigh_class", ""),
            }
    return out


MODELS_ORDER = ["COMBO", "a030", "a043", "a025"]


def make_contact_sheet(cases: list[tuple], out_path: Path, title: str = "") -> None:
    """Each case = (dataset, stage, frame_id, note).
    Rows = cases. Columns = GT, COMBO, a030, a043, a025, summary.
    """
    case_keys = [(c[0], c[1], c[2]) for c in cases]
    metrics_map = load_metrics(case_keys)
    n_cases = len(cases)
    fig, axes = plt.subplots(n_cases, 6, figsize=(22, 4 * n_cases))
    if n_cases == 1:
        axes = axes.reshape(1, -1)
    for ri, (ds, stage, fid, note) in enumerate(cases):
        mm = metrics_map[(ds, stage, fid)]
        gt_path = resolve_gt(ds, stage, fid)
        gt_img = cv2.imread(str(gt_path), cv2.IMREAD_UNCHANGED) if gt_path.exists() else None
        ax = axes[ri, 0]
        if gt_img is not None:
            ax.imshow(gt_img, cmap="gray", vmin=0, vmax=255)
        sw = mm.get("a025", {}).get("sw_median_px", float("nan"))
        cls = mm.get("a025", {}).get("rayleigh_class", "")
        ax.set_title(f"GT\n{stage}\nframe {fid}\nsw_med={sw:.1f}px [{cls}]\n{note}", fontsize=8)
        ax.axis("off")

        for ci, m in enumerate(MODELS_ORDER, start=1):
            ax = axes[ri, ci]
            p = resolve_recon(m, ds, stage, fid)
            if p is not None and p.exists():
                img = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
                ax.imshow(img, cmap="gray", vmin=0, vmax=255)
                md = mm.get(m, {})
                psnr = md.get("psnr", float("nan"))
                se = md.get("shape_error_score", float("nan"))
                cr = md.get("corner_retention", float("nan"))
                ax.set_title(
                    f"{m}\nPSNR={psnr:.2f} dB\nshape_err={se:.3f}\ncorner_ret={cr:.3f}",
                    fontsize=8,
                )
            else:
                ax.text(
                    0.5, 0.5, f"{m}\nrecon not found", ha="center", va="center", color="red"
                )
                ax.set_title(f"{m}", fontsize=8)
            ax.axis("off")

        # 第 6 欄:summary
        ax = axes[ri, 5]
        m043 = mm.get("a043", {})
        m025 = mm.get("a025", {})
        if m043 and m025:
            dpsnr = m043.get("psnr", 0) - m025.get("psnr", 0)
            dse = m043.get("shape_error_score", 0) - m025.get("shape_error_score", 0)
            dcr = m043.get("corner_retention", 0) - m025.get("corner_retention", 0)
            text = (
                f"a043 - a025\n"
                f"ΔPSNR = {dpsnr:+.2f} dB\n"
                f"Δshape_err = {dse:+.3f}\n"
                f"Δcorner_ret = {dcr:+.3f}"
            )
            color_psnr = "green" if dpsnr > 0 else "red"
            ax.text(0.5, 0.5, text, ha="center", va="center", color=color_psnr, fontsize=10)
        else:
            ax.text(0.5, 0.5, "(no data)", ha="center", va="center")
        ax.axis("off")

    fig.suptitle(title, fontsize=12, y=0.998)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  wrote {out_path.name}")


CASES = {
    "1_top_wins_textures": (
        "a043 大贏 a025 的紋理 case(PSNR 贏 2.5-3.5 dB)",
        [
            ("R40_micro_val_unseen", "stage_31_micro_textures", "0084", "a043 +3.46 dB"),
            ("R40_micro_val_unseen", "stage_31_micro_textures", "0096", "a043 +3.10 dB"),
            ("R40_micro_val_unseen", "stage_31_micro_textures", "0091", "a043 +3.10 dB"),
        ],
    ),
    "2_a043_small_losses_big_shapes": (
        "a043 微輸 a025 的大形狀 case(都不顯著)",
        [
            ("R39_shape_val_unseen", "stage_04_ellipses", "0381", "a043 -0.66 dB(輸最多)"),
            ("R39_shape_val_unseen", "stage_02_circles", "0184", "a043 -0.46 dB"),
            ("R39_shape_val_unseen", "stage_05_polygons", "0475", "a043 -0.31 dB"),
        ],
    ),
    "3_rectangles_right_angles": (
        "矩形直角(user 原始抱怨「直角變圓」)",
        [
            ("R39_shape_val_unseen", "stage_03_rectangles", "0271", "rectangle"),
            ("R39_shape_val_unseen", "stage_03_rectangles", "0275", "rectangle"),
            ("R39_shape_val_unseen", "stage_03_rectangles", "0280", "rectangle"),
        ],
    ),
    "4_triangles_small": (
        "小三角形(user 原始抱怨「三角形變一坨」,挑 sw_median 最小的)",
        [
            ("R39_shape_val_unseen", "stage_01_triangles", "0097", "sw_med=6.0px [sub]"),
            ("R39_shape_val_unseen", "stage_01_triangles", "0085", "sw_med=8.4px [sub]"),
            ("R39_shape_val_unseen", "stage_01_triangles", "0079", "sw_med=10.8px [mixed]"),
            ("R39_shape_val_unseen", "stage_01_triangles", "0095", "sw_med=11.2px [mixed]"),
        ],
    ),
    "5_polygons_corner_test": (
        "多邊形(R39 stage_05,前報告誤以為 a025 在此 stage 贏 a043)",
        [
            ("R39_shape_val_unseen", "stage_05_polygons", "0471", "polygon"),
            ("R39_shape_val_unseen", "stage_05_polygons", "0494", "polygon"),
            ("R39_shape_val_unseen", "stage_05_polygons", "0497", "polygon"),
        ],
    ),
}


def make_zoom_figure(case: tuple, out_path: Path, title: str = "") -> None:
    """單一 case 大圖:1 row × (GT + 4 model + summary),每 cell 占大、字大。"""
    ds, stage, fid, note = case
    metrics_map = load_metrics([(ds, stage, fid)])
    mm = metrics_map[(ds, stage, fid)]

    fig, axes = plt.subplots(1, 6, figsize=(28, 6))
    gt_path = resolve_gt(ds, stage, fid)
    gt_img = cv2.imread(str(gt_path), cv2.IMREAD_UNCHANGED) if gt_path.exists() else None
    ax = axes[0]
    if gt_img is not None:
        ax.imshow(gt_img, cmap="gray", vmin=0, vmax=255)
    sw = mm.get("a025", {}).get("sw_median_px", float("nan"))
    cls = mm.get("a025", {}).get("rayleigh_class", "")
    ax.set_title(
        f"GT(真值)\n{stage}\nframe {fid}\nsw_median = {sw:.1f} px\nRayleigh class: {cls}",
        fontsize=13,
    )
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
                f"{m}\nPSNR = {psnr:.2f} dB\nshape_err = {se:.3f}\n"
                f"corner_ret = {cr:.3f}\nboundary_F = {bf:.3f}",
                fontsize=13,
            )
        else:
            ax.text(0.5, 0.5, f"{m}\n(no recon)", ha="center", va="center", color="red", fontsize=14)
            ax.set_title(f"{m}", fontsize=13)
        ax.axis("off")

    ax = axes[5]
    m043 = mm.get("a043", {})
    m025 = mm.get("a025", {})
    if m043 and m025:
        dpsnr = m043.get("psnr", 0) - m025.get("psnr", 0)
        dse = m043.get("shape_error_score", 0) - m025.get("shape_error_score", 0)
        dcr = m043.get("corner_retention", 0) - m025.get("corner_retention", 0)
        dbf = m043.get("boundary_f_score", 0) - m025.get("boundary_f_score", 0)
        winner = "a043 較佳" if dpsnr > 0 else "a025 較佳"
        color = "green" if dpsnr > 0 else "red"
        text = (
            f"a043 vs a025\n\n"
            f"d_PSNR = {dpsnr:+.2f} dB\n"
            f"d_shape_err = {dse:+.3f}\n"
            f"d_corner_ret = {dcr:+.3f}\n"
            f"d_boundary_F = {dbf:+.3f}\n\n"
            f"({winner})\n\n"
            f"備註:{note}"
        )
        ax.text(0.5, 0.5, text, ha="center", va="center", color=color, fontsize=12,
                bbox=dict(boxstyle="round", facecolor="white", edgecolor=color, linewidth=2))
    ax.axis("off")
    ax.set_title("摘要", fontsize=13)

    fig.suptitle(title, fontsize=15, y=0.995, weight="bold")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path.name}")


ZOOM_CASES = [
    (
        "zoom_1_textures_a043_big_win.png",
        ("R40_micro_val_unseen", "stage_31_micro_textures", "0084", "a043 PSNR 大贏 a025 約 +3.46 dB"),
        "紋理 case:a043 大贏 a025 +3.46 dB(指標差距 vs 視覺感受對應)",
    ),
    (
        "zoom_2_triangle_sub_rayleigh.png",
        ("R39_shape_val_unseen", "stage_01_triangles", "0097", "sw_median = 6.0 px,落在次解析尺度"),
        "小三角形 case:次解析尺度(sw_median 6 px < Rayleigh 11.7 px),物理上限",
    ),
    (
        "zoom_3_rectangle_right_angles.png",
        ("R39_shape_val_unseen", "stage_03_rectangles", "0275", "矩形(user 原始抱怨「直角變圓」)"),
        "矩形直角 case:user 原始抱怨「直角變圓」的視覺直驗",
    ),
    (
        "zoom_4_ellipse_a043_small_loss.png",
        ("R39_shape_val_unseen", "stage_04_ellipses", "0381", "a043 PSNR 微輸 -0.66 dB(統計上 n.s.)"),
        "大橢圓 case:a043 PSNR 微輸 -0.66 dB(看是否有「a043 過銳化」視覺證據)",
    ),
    (
        "zoom_5_large_region_a043_win.png",
        ("R40_micro_val_unseen", "stage_30_micro_large_regions", "0083", "a043 PSNR 贏 +2.68 dB"),
        "大區塊 case:a043 PSNR 贏 a025 +2.68 dB,看大區塊邊界銳度差異",
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    for name, (title, cases) in CASES.items():
        make_contact_sheet(cases, args.out / f"{name}.png", title=title)

    zoom_dir = args.out / "zoom"
    zoom_dir.mkdir(parents=True, exist_ok=True)
    print("--- zoom (single case, high DPI) ---")
    for fname, case, title in ZOOM_CASES:
        make_zoom_figure(case, zoom_dir / fname, title=title)
    print(f"Done -> {args.out}")


if __name__ == "__main__":
    main()
