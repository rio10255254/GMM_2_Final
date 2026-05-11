"""Full capability evaluation for R39R40_avg_a025.

Combines:
- R40 micro_val_unseen detailed metrics (PSNR / SSIM / HF / Edge / Contrast /
  boundary F1 / shape error) — needs alpha=0.25 reconstructions
- R39 shape_val_unseen detailed metrics — needs alpha=0.25 reconstructions
- Visual statistics on existing ring reconstructions (alpha=0.25 vs COMBO)
  using the four-quantity protocol from R39_RESULTS.md
- Combined writeup with COMBO / a030 / a043 / R39R40_avg_a025 four-way table

Re-uses r39_a030_microscopy_evaluation helpers (`evaluate_pair`,
`find_recon_inner_alpha_layout`) so the metric definitions stay consistent
with the existing a030 evaluation.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R39_ShapeGeneralization"
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import r39_a030_microscopy_evaluation as base  # noqa: E402


A025_ROOT = EXPERIMENT_ROOT / "results" / "a030_x_a043_sweep"

# Reconstructions for alpha=0.25
A025_MICRO_RECON = A025_ROOT / "micro_recon" / "a025"
A025_SHAPE_RECON = A025_ROOT / "shape_recon" / "a025"
A025_RING_RECON = A025_ROOT / "external_recon" / "a025"

# Reference reconstruction sources (existing)
R40_RECON_ROOT = REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "results" / "micro_recon"
R40_A045_RECON_ROOT = REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "results" / "weight_sweep" / "combo_best_low_alpha" / "micro_recon" / "a045"
R39_SHAPE_ROOT_A030 = EXPERIMENT_ROOT / "results" / "weight_sweep" / "shape_recon" / "a030"
R39_SHAPE_ROOT_COMBO = EXPERIMENT_ROOT / "results" / "weight_sweep" / "shape_recon" / "a000"
R40_A043_MICRO_ROOT = REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "results" / "weight_sweep" / "combo_best_low_alpha" / "micro_recon" / "a043"
R40_A043_SHAPE_ROOT = A025_ROOT / "shape_recon" / "a043"  # newly produced 2026-05-11

DEFAULT_OUTPUT_DIR = A025_ROOT / "capability_eval"
DEFAULT_REPORT = A025_ROOT / "reports" / "R39R40_AVG_a025_CAPABILITY_EVAL.md"


def _round4(v):
    if v is None:
        return None
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return round(float(v), 4)


def _avg(xs):
    xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return sum(xs) / len(xs) if xs else None


def _write_csv(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields = sorted({k for r in rows for k in r})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _write_json(payload, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_dataset(*, profile_dir, recon_root, model_label, dataset_label,
                    use_alpha_layout=True, recon_tag=None):
    """Generic collector for one (model, dataset) combination."""
    rows = []
    manifest = json.loads((profile_dir / "manifest.json").read_text(encoding="utf-8"))
    pairs = manifest["pairs"]
    print(f"  [{model_label}] {dataset_label} {len(pairs)} pairs ...", flush=True)
    for idx, p in enumerate(pairs):
        if idx % 50 == 0 and idx > 0:
            print(f"    {idx}/{len(pairs)}", flush=True)
        stage = p["stage"]
        if use_alpha_layout:
            inner = base.find_recon_inner_alpha_layout(recon_root, stage)
        else:
            inner = base.find_recon_inner(recon_root, stage, recon_tag)
        if inner is None:
            continue
        lbl_path = profile_dir / p["package_lbl"]
        pred_path = inner / Path(p["package_lbl"]).name
        if not pred_path.exists():
            continue
        metrics = base.evaluate_pair(lbl_path, pred_path)
        rows.append({
            "model": model_label,
            "dataset": dataset_label,
            "stage": stage,
            "feature_family": p.get("feature_family", stage.replace("stage_", "").split("_", 1)[-1]),
            "frame_id": Path(p["package_lbl"]).stem,
            **metrics,
        })
    return rows


def summarize(rows):
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["model"], r["dataset"], r["stage"])].append(r)
    out = []
    keys = ("psnr", "ssim", "high_frequency_retention", "edge_retention",
            "contrast_retention", "boundary_f_score", "shape_error_score")
    for (model, dataset, stage), grp in sorted(grouped.items()):
        row = {"model": model, "dataset": dataset, "stage": stage, "count": len(grp)}
        for k in keys:
            row[f"avg_{k}"] = _round4(_avg(r[k] for r in grp))
        out.append(row)
    return out


def overall_summary(rows):
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["model"], r["dataset"])].append(r)
    keys = ("psnr", "ssim", "high_frequency_retention", "edge_retention",
            "contrast_retention", "boundary_f_score", "shape_error_score")
    out = []
    for (model, dataset), grp in sorted(grouped.items()):
        row = {"model": model, "dataset": dataset, "count": len(grp)}
        for k in keys:
            row[f"avg_{k}"] = _round4(_avg(r[k] for r in grp))
        out.append(row)
    return out


# ---------------------------------------------------------------- Visual stats
# Four quantities from R39_RESULTS.md inline snippet:
# gradient_magnitude_mean, edge_steepness_p95, contrast_std, edge_contrast_p99_minus_p1
# Averaged frame-wise across each pitch directory.

def visual_stats(folder: Path) -> dict:
    accs = {k: 0.0 for k in ("gradient_magnitude_mean", "edge_steepness_p95",
                              "contrast_std", "edge_contrast_p99_minus_p1")}
    n = 0
    for p in sorted(folder.glob("*.bmp")):
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        f = img.astype(np.float32) / 255.0
        gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
        gmag = np.sqrt(gx * gx + gy * gy)
        edge_mask = gmag > np.percentile(gmag, 95)
        accs["gradient_magnitude_mean"] += float(gmag.mean())
        accs["edge_steepness_p95"] += float(gmag[edge_mask].mean()) if edge_mask.any() else 0.0
        accs["contrast_std"] += float(f.std())
        accs["edge_contrast_p99_minus_p1"] += float(np.percentile(f, 99) - np.percentile(f, 1))
        n += 1
    return {k: v / n for k, v in accs.items()} if n else {k: float("nan") for k in accs}


def collect_visual_stats():
    """For each of (COMBO / a030 / a043 / a025), compute visual stats over
    the three pitch ring reconstructions.  Reuses existing R39 sweep ring
    reconstructions for COMBO (a000) and a030; uses external_gmf_a043 BMPs
    for a043; uses a030_x_a043_sweep/external_recon/a025 for a025."""
    ring_sources = {
        "COMBO": EXPERIMENT_ROOT / "results" / "weight_sweep" / "ring_recon" / "a000",
        "a030": EXPERIMENT_ROOT / "results" / "weight_sweep" / "ring_recon" / "a030",
        "a043": REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "results" / "weight_sweep" / "combo_best_low_alpha" / "ring_recon" / "a043",
        "R39R40_a025": A025_RING_RECON,
    }
    pitch_dirs = ("pitch1um_y_100_odd", "pitch0p1um_y_60_odd", "pitch0p01um_y_40_odd")
    out = []
    for model, root in ring_sources.items():
        # find reconstruct_progress_* subdir
        if not root.exists():
            print(f"  visual stats: {model} ring root missing -> {root}", flush=True)
            continue
        candidates = list(root.glob("reconstruct_progress_best_tradeoff_in_Cropped_Output_*"))
        if not candidates:
            print(f"  visual stats: {model} no reconstruct dir under {root}", flush=True)
            continue
        recon_dir = sorted(candidates)[-1]  # latest
        for pd in pitch_dirs:
            folder = recon_dir / pd
            if not folder.exists():
                continue
            stats = visual_stats(folder)
            out.append({
                "model": model,
                "pitch": pd,
                **{k: _round4(v) for k, v in stats.items()}
            })
            print(f"  visual stats: {model} {pd}  done", flush=True)
    return out


def write_report(*, micro_summary, micro_overall, shape_summary, shape_overall,
                 visual_rows, output_dir, report_path):
    lines = [
        "# R39R40 a025 全面能力評估",
        "",
        "## 摘要",
        "",
        "`r39r40_complementary_avg_a025`（R39 a030 與 R40 a043 在 α=0.25 的權重平均）已在外部 GMF 拿到 `PASS_UPGRADE_GUARD`（三尺度都在 ±5.18%）。本評估補上升級為正式替代候選前的四項驗證：",
        "",
        "1. R40 `micro_val_unseen`（顯微特徵 5 類 / 100 對）詳細指標",
        "2. R39 `shape_val_unseen`（純幾何 7 類 / 210 對）詳細指標",
        "3. 視覺四項統計（gradient magnitude / edge steepness / contrast / edge contrast）—— sharp band 還是 soft band",
        "4. 四聯視覺對比 sheet（COMBO / a030 / a043 / a025）",
        "",
        "本份報告只忠實記錄量測事實，升級決策由專案 owner 拍板。",
        "",
        "## R40 micro_val_unseen 整體（5 類平均）",
        "",
        "| 指標 | COMBO | a030 | a043 | R39R40_a025 |",
        "|---|---:|---:|---:|---:|",
    ]

    def get_overall(rows, model, dataset):
        for r in rows:
            if r.get("model") == model and r.get("dataset") == dataset:
                return r
        return {}

    micro_metric_labels = [
        ("avg_psnr", "PSNR"),
        ("avg_ssim", "SSIM"),
        ("avg_high_frequency_retention", "HF retention"),
        ("avg_edge_retention", "Edge retention"),
        ("avg_contrast_retention", "Contrast retention"),
        ("avg_boundary_f_score", "邊界 F1"),
        ("avg_shape_error_score", "形狀錯誤（越低越好）"),
    ]
    for k, label in micro_metric_labels:
        row = [label]
        for model in ("COMBO", "a030", "a043", "R39R40_a025"):
            v = get_overall(micro_overall, model, "R40_micro_val_unseen").get(k)
            row.append(f"`{v:.4f}`" if v is not None else "—")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    lines.extend([
        "## R39 shape_val_unseen 整體（7 類平均）",
        "",
        "| 指標 | COMBO | a030 | a043 | R39R40_a025 |",
        "|---|---:|---:|---:|---:|",
    ])
    for k, label in micro_metric_labels:
        row = [label]
        for model in ("COMBO", "a030", "a043", "R39R40_a025"):
            v = get_overall(shape_overall, model, "R39_shape_val_unseen").get(k)
            row.append(f"`{v:.4f}`" if v is not None else "—")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    lines.extend([
        "## R40 micro_val_unseen 逐 stage（PSNR）",
        "",
        "| stage | COMBO | a030 | a043 | R39R40_a025 |",
        "|---|---:|---:|---:|---:|",
    ])
    stages = sorted({r["stage"] for r in micro_summary if r["dataset"] == "R40_micro_val_unseen"})
    for stage in stages:
        cells = [stage]
        for model in ("COMBO", "a030", "a043", "R39R40_a025"):
            v = next((r["avg_psnr"] for r in micro_summary
                      if r["model"] == model and r["dataset"] == "R40_micro_val_unseen" and r["stage"] == stage),
                     None)
            cells.append(f"`{v:.4f}`" if v is not None else "—")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    lines.extend([
        "## R39 shape_val_unseen 逐 stage（PSNR）",
        "",
        "| stage | COMBO | a030 | a043 | R39R40_a025 |",
        "|---|---:|---:|---:|---:|",
    ])
    stages = sorted({r["stage"] for r in shape_summary if r["dataset"] == "R39_shape_val_unseen"})
    for stage in stages:
        cells = [stage]
        for model in ("COMBO", "a030", "a043", "R39R40_a025"):
            v = next((r["avg_psnr"] for r in shape_summary
                      if r["model"] == model and r["dataset"] == "R39_shape_val_unseen" and r["stage"] == stage),
                     None)
            cells.append(f"`{v:.4f}`" if v is not None else "—")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # Visual stats
    lines.extend([
        "## 視覺四項統計（ring 重建 frame-wise mean）",
        "",
        "依 R39_RESULTS 的 inline 公式計算（灰階 Sobel 梯度幅值 / p95 梯度 / 像素 std / p99−p1）。",
        "",
        "| 模型 | pitch | gradient_magnitude_mean | edge_steepness_p95 | contrast_std | edge_contrast_p99−p1 |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for r in visual_rows:
        lines.append("| " + " | ".join([
            r["model"], r["pitch"],
            f"`{r['gradient_magnitude_mean']:.6f}`" if r.get('gradient_magnitude_mean') is not None else "—",
            f"`{r['edge_steepness_p95']:.6f}`" if r.get('edge_steepness_p95') is not None else "—",
            f"`{r['contrast_std']:.6f}`" if r.get('contrast_std') is not None else "—",
            f"`{r['edge_contrast_p99_minus_p1']:.6f}`" if r.get('edge_contrast_p99_minus_p1') is not None else "—",
        ]) + " |")
    lines.append("")

    # Compute COMBO->a025 delta% averaged over three pitches for the four quantities
    def collect_pitch_values(model, key):
        return [r[key] for r in visual_rows if r["model"] == model and r.get(key) is not None]

    combo_avg = {k: _avg(collect_pitch_values("COMBO", k)) for k in
                 ("gradient_magnitude_mean", "edge_steepness_p95", "contrast_std", "edge_contrast_p99_minus_p1")}
    a025_avg = {k: _avg(collect_pitch_values("R39R40_a025", k)) for k in combo_avg}
    a030_avg = {k: _avg(collect_pitch_values("a030", k)) for k in combo_avg}
    a043_avg = {k: _avg(collect_pitch_values("a043", k)) for k in combo_avg}

    lines.extend([
        "### COMBO 為基準，三 pitch 平均後對比",
        "",
        "| 指標 | COMBO | a030 Δ% | a043 Δ% | R39R40_a025 Δ% |",
        "|---|---:|---:|---:|---:|",
    ])
    def pct(num, base):
        if num is None or base is None or base == 0:
            return None
        return (num - base) / base * 100
    for k in ("gradient_magnitude_mean", "edge_steepness_p95", "contrast_std", "edge_contrast_p99_minus_p1"):
        cells = [k, f"`{combo_avg[k]:.6f}`" if combo_avg[k] is not None else "—"]
        for cand_avg in (a030_avg, a043_avg, a025_avg):
            d = pct(cand_avg[k], combo_avg[k])
            cells.append(f"`{d:+.2f}%`" if d is not None else "—")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.extend([
        "### 視覺帶定位（edge_steepness_p95 對 COMBO 的偏移量）",
        "",
        "依 R39_RESULTS 的視覺帶分類，R30 是 0%、COMBO/R38v2 約 +89.4%、R33 是 −22%（soft band）：",
        "",
    ])
    # Translate edge_steepness deltas to "vs R30" using transitive math
    # COMBO is +89.4% vs R30, so model M vs R30 = (1 + Δ%/100) * 1.894 - 1 in fraction; convert to %
    def vs_r30(delta_pct):
        if delta_pct is None:
            return None
        return ((1 + delta_pct / 100.0) * 1.894 - 1) * 100.0
    for model, cand_avg in (("a030", a030_avg), ("a043", a043_avg), ("R39R40_a025", a025_avg)):
        d = pct(cand_avg["edge_steepness_p95"], combo_avg["edge_steepness_p95"])
        r30_pct = vs_r30(d)
        if d is not None and r30_pct is not None:
            lines.append(f"- {model}: vs COMBO `{d:+.2f}%`、推算 vs R30 約 `{r30_pct:+.1f}%`")
    lines.append("")

    lines.extend([
        "## 產物",
        "",
        f"- 逐張指標：`{output_dir / 'per_pair_metrics.csv'}`",
        f"- 逐 stage 平均：`{output_dir / 'stage_summary.csv'}`",
        f"- 整體平均：`{output_dir / 'overall_summary.csv'}`",
        f"- 視覺四項統計：`{output_dir / 'visual_stats.csv'}`",
        f"- 視覺對比 sheet：`{(A025_ROOT / 'visuals' / 'contact_sheet_a025_four_panel.png').as_posix()}`（由 r39r40_a025_four_panel_contact.py 產生）",
        "",
        "## 方法",
        "",
        "- 顯微/形狀指標：複用 `r39_a030_microscopy_evaluation.evaluate_pair`，含 PSNR / SSIM / HF retention / Edge retention / Contrast retention（R40 micro_metrics）+ 邊界 F1 / 形狀錯誤分數（R44G 邊界遮罩取 3% 強梯度後算）",
        "- 視覺四項：對既有 ring 重建（COMBO 跟 a030 在 weight_sweep/ring_recon、a043 在 combo_best_low_alpha/ring_recon、a025 在 a030_x_a043_sweep/external_recon）逐 frame 用灰階 Sobel + percentile 算",
        "- 推算 vs R30：用 `(1 + Δ%) × 1.894 − 1` 串接 R39_RESULTS 既有的視覺帶錨點（R30=0%、COMBO/R38v2=+89.4%、R33=−22%）",
        "- 沒下 verdict 或推薦；升級判定留給專案 owner",
    ])

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # R40 micro_val_unseen — COMBO / a030 / a043 / a025
    print("[a025 eval] R40 micro_val_unseen ...", flush=True)
    r40_profile_dir = base.R40_DATA_ROOT / base.R40_PROFILE
    micro_rows = []
    micro_rows += base.collect_r40(profile_dir=r40_profile_dir, recon_root=R40_RECON_ROOT,
                                    model_label="COMBO", recon_tag=base.COMBO_TAG)
    micro_rows += base.collect_r40(profile_dir=r40_profile_dir, recon_root=R40_RECON_ROOT,
                                    model_label="a030", recon_tag=base.A030_TAG)
    # a043 in R40 micro
    micro_rows += collect_dataset(profile_dir=r40_profile_dir, recon_root=R40_A043_MICRO_ROOT,
                                   model_label="a043", dataset_label="R40_micro_val_unseen",
                                   use_alpha_layout=True)
    # a025 in R40 micro
    micro_rows += collect_dataset(profile_dir=r40_profile_dir, recon_root=A025_MICRO_RECON,
                                   model_label="R39R40_a025", dataset_label="R40_micro_val_unseen",
                                   use_alpha_layout=True)

    # R39 shape_val_unseen — COMBO / a030 / a025 (a043 on shape lives in r40_a045_on_shape; rename note below)
    print("[a025 eval] R39 shape_val_unseen ...", flush=True)
    r39_profile_dir = base.R39_DATA_ROOT / base.R39_PROFILE
    shape_rows = []
    shape_rows += base.collect_r39_shape(profile_dir=r39_profile_dir,
                                          recon_root_alpha=R39_SHAPE_ROOT_COMBO,
                                          model_label="COMBO")
    shape_rows += base.collect_r39_shape(profile_dir=r39_profile_dir,
                                          recon_root_alpha=R39_SHAPE_ROOT_A030,
                                          model_label="a030")
    # a043 in shape — reuse the directory the previous evaluation script populated
    shape_rows += base.collect_r39_shape(profile_dir=r39_profile_dir,
                                          recon_root_alpha=R40_A043_SHAPE_ROOT,
                                          model_label="a043")
    # a025 in shape
    shape_rows += base.collect_r39_shape(profile_dir=r39_profile_dir,
                                          recon_root_alpha=A025_SHAPE_RECON,
                                          model_label="R39R40_a025")

    all_rows = micro_rows + shape_rows
    micro_stage = summarize(micro_rows)
    shape_stage = summarize(shape_rows)
    micro_over = overall_summary(micro_rows)
    shape_over = overall_summary(shape_rows)

    print("[a025 eval] visual stats ...", flush=True)
    visual_rows = collect_visual_stats()

    _write_csv(all_rows, output_dir / "per_pair_metrics.csv")
    _write_csv(micro_stage + shape_stage, output_dir / "stage_summary.csv")
    _write_csv(micro_over + shape_over, output_dir / "overall_summary.csv")
    _write_csv(visual_rows, output_dir / "visual_stats.csv")
    _write_json({"micro_overall": micro_over, "shape_overall": shape_over, "visual": visual_rows},
                output_dir / "capability_summary.json")

    write_report(
        micro_summary=micro_stage,
        micro_overall=micro_over,
        shape_summary=shape_stage,
        shape_overall=shape_over,
        visual_rows=visual_rows,
        output_dir=output_dir,
        report_path=args.report,
    )
    print(f"[a025 eval] report -> {args.report}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
