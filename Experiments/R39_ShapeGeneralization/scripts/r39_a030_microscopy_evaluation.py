"""R39 a030 detailed evaluation across diverse microscopy structures.

This script does not run new inference.  It re-uses the existing
reconstructions of `r39_combo_strong_avg_a030`, COMBO, and (where
available) other reference candidates that have already been produced
under R40, R42, and R44.

What it produces
----------------
- Per-pair metrics CSV for R40 `micro_val_unseen` (a030 vs COMBO):
  PSNR, SSIM, HF retention, edge retention, contrast retention,
  boundary F1@1px, shape error score.
- Per-pair metrics CSV for R39 `shape_val_unseen` (a030 vs COMBO) as
  in-distribution reference, same metric set.
- Per-stage summary CSVs for both datasets.
- Cross-dataset headline JSON pulled from the existing summary files
  under R42 and R44.
- Visual contact sheet: 4 representative frames per microscopy stage,
  GT / COMBO / a030 side by side.
- Markdown report that records the observations only; verdicts and
  next-step decisions are left to discussion.
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
R40_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "scripts"
R44_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
for _p in (R40_SCRIPT_DIR, R44_SCRIPT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import r40_micro_metrics as r40m  # noqa: E402
import r44g_boundary_shape_metrics as r44g  # noqa: E402
import r44_motion_metrics as rmm  # noqa: E402


DEFAULT_OUTPUT_DIR = EXPERIMENT_ROOT / "results" / "a030_microscopy_eval"
DEFAULT_VISUAL_DIR = EXPERIMENT_ROOT / "results" / "a030_microscopy_eval" / "visuals"
DEFAULT_REPORT = EXPERIMENT_ROOT / "reports" / "R39_A030_MICROSCOPY_EVALUATION.md"

R40_DATA_ROOT = REPO_ROOT / "Training_Data" / "r40_microscopy_feature_coverage"
R40_RECON_ROOT = REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "results" / "micro_recon"
R40_PROFILE = "micro_val_unseen"

R39_DATA_ROOT = REPO_ROOT / "Training_Data" / "r39_shape_generalization"
R39_RECON_ROOT_A030 = EXPERIMENT_ROOT / "results" / "weight_sweep" / "shape_recon" / "a030"
R39_RECON_ROOT_COMBO = EXPERIMENT_ROOT / "results" / "weight_sweep" / "shape_recon" / "a000"
R39_PROFILE = "shape_val_unseen"

A030_TAG = "20260430_121954"
COMBO_TAG = "20260408_003525"


def _round4(value):
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return round(float(value), 4)


def _json_safe(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


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
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def find_recon_inner(recon_root, stage, tag):
    """Find the inner BMP directory under recon_progress_best_tradeoff_in_<stage>_<tag>."""
    name = f"reconstruct_progress_best_tradeoff_in_{stage}_{tag}"
    outer = recon_root / name
    if not outer.exists():
        return None
    inner = next((p for p in outer.iterdir() if p.is_dir()), None)
    return inner


def find_recon_inner_alpha_layout(recon_root_alpha, stage):
    """For R39 weight_sweep/shape_recon/<alpha>/reconstruct_progress_*_<stage>_*.

    Picks the latest timestamp under the alpha directory.  Each alpha subdir
    contains its own sweep run with its own timestamp; a030 and a000 do not
    share the same timestamp."""
    prefix = f"reconstruct_progress_best_tradeoff_in_{stage}_"
    candidates = [p for p in recon_root_alpha.iterdir() if p.is_dir() and p.name.startswith(prefix)]
    if not candidates:
        return None
    outer = sorted(candidates)[-1]  # latest by name = latest timestamp
    inner = next((p for p in outer.iterdir() if p.is_dir()), None)
    return inner


def evaluate_pair(lbl_path, pred_path, *, target_boundary_fraction=0.03):
    """Return all per-pair metrics for one (lbl, pred) pair.

    Adds boundary-F1 and shape-error on top of R40's standard set. Both GT
    and prediction boundary masks come from `matched_gradient_boundary` at
    the same fraction so they are comparable across datasets that lack a
    pre-baked boundary mask (R40 / R39 don't ship boundary masks; R42 / R44
    do, but we use a uniform method here for cross-dataset consistency)."""
    gt = r40m._read_gray(lbl_path)
    pred = r40m._read_gray(pred_path)

    base = r40m.image_metric_row(pred, gt)

    target_count = int(round(gt.size * target_boundary_fraction))
    gt_boundary = rmm.matched_gradient_boundary(gt, target_count=target_count)
    pred_boundary = rmm.matched_gradient_boundary(pred, target_count=target_count)
    shape_metrics = r44g.boundary_shape_metrics(gt_boundary, pred_boundary)

    return {
        "psnr": _round4(base["psnr"]),
        "ssim": _round4(base["ssim"]),
        "high_frequency_retention": _round4(base.get("high_frequency_retention")),
        "edge_retention": _round4(base.get("edge_retention")),
        "contrast_retention": _round4(base.get("contrast_retention")),
        "boundary_f_score": _round4(shape_metrics["boundary_f_score"]),
        "shape_error_score": _round4(shape_metrics["shape_error_score"]),
        "boundary_density_ratio": _round4(shape_metrics["boundary_density_ratio"]),
        "fragmentation_ratio": _round4(shape_metrics["fragmentation_ratio"]),
        "straight_edge_coverage": _round4(shape_metrics.get("straight_edge_coverage")),
        "corner_retention": _round4(shape_metrics.get("corner_retention")),
    }


def collect_r40(*, profile_dir, recon_root, model_label, recon_tag):
    rows = []
    manifest = json.loads((profile_dir / "manifest.json").read_text(encoding="utf-8"))
    pairs = manifest["pairs"]
    print(f"  [{model_label}] R40 {len(pairs)} pairs", flush=True)
    for idx, p in enumerate(pairs):
        if idx % 25 == 0 and idx > 0:
            print(f"    {idx}/{len(pairs)}", flush=True)
        stage = p["stage"]
        inner = find_recon_inner(recon_root, stage, recon_tag)
        if inner is None:
            continue
        lbl_path = profile_dir / p["package_lbl"]
        pred_path = inner / Path(p["package_lbl"]).name
        if not pred_path.exists():
            continue
        metrics = evaluate_pair(lbl_path, pred_path)
        rows.append({
            "model": model_label,
            "dataset": "R40_micro_val_unseen",
            "stage": stage,
            "feature_family": p["feature_family"],
            "frame_id": Path(p["package_lbl"]).stem,
            **metrics,
        })
    return rows


def collect_r39_shape(*, profile_dir, recon_root_alpha, model_label):
    rows = []
    manifest = json.loads((profile_dir / "manifest.json").read_text(encoding="utf-8"))
    pairs = manifest["pairs"]
    print(f"  [{model_label}] R39 shape {len(pairs)} pairs", flush=True)
    for idx, p in enumerate(pairs):
        if idx % 50 == 0 and idx > 0:
            print(f"    {idx}/{len(pairs)}", flush=True)
        stage = p["stage"]
        inner = find_recon_inner_alpha_layout(recon_root_alpha, stage)
        if inner is None:
            continue
        lbl_path = profile_dir / p["package_lbl"]
        pred_path = inner / Path(p["package_lbl"]).name
        if not pred_path.exists():
            continue
        metrics = evaluate_pair(lbl_path, pred_path)
        rows.append({
            "model": model_label,
            "dataset": "R39_shape_val_unseen",
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
    keys = (
        "psnr", "ssim", "high_frequency_retention", "edge_retention",
        "contrast_retention", "boundary_f_score", "shape_error_score",
        "boundary_density_ratio", "fragmentation_ratio",
        "straight_edge_coverage", "corner_retention",
    )
    for (model, dataset, stage), grp in sorted(grouped.items()):
        row = {
            "model": model,
            "dataset": dataset,
            "stage": stage,
            "count": len(grp),
        }
        for k in keys:
            vals = [r[k] for r in grp if r[k] is not None and math.isfinite(float(r[k]))]
            row[f"avg_{k}"] = _round4(sum(vals) / len(vals)) if vals else None
        out.append(row)
    return out


def overall(rows):
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["model"], r["dataset"])].append(r)
    out = []
    keys = (
        "psnr", "ssim", "high_frequency_retention", "edge_retention",
        "contrast_retention", "boundary_f_score", "shape_error_score",
    )
    for (model, dataset), grp in sorted(grouped.items()):
        row = {"model": model, "dataset": dataset, "count": len(grp)}
        for k in keys:
            vals = [r[k] for r in grp if r[k] is not None and math.isfinite(float(r[k]))]
            row[f"avg_{k}"] = _round4(sum(vals) / len(vals)) if vals else None
        out.append(row)
    return out


def make_delta_table(summary_rows, *, key="avg_psnr"):
    """Pivot to model -> stage -> value, then compute a030 - COMBO delta."""
    by_stage = defaultdict(dict)
    for r in summary_rows:
        by_stage[(r["dataset"], r["stage"])][r["model"]] = r.get(key)
    out = []
    for (dataset, stage), m in sorted(by_stage.items()):
        a030 = m.get("a030")
        combo = m.get("COMBO")
        delta = None
        if a030 is not None and combo is not None:
            delta = _round4(a030 - combo)
        out.append({
            "dataset": dataset,
            "stage": stage,
            "metric": key,
            "COMBO": combo,
            "a030": a030,
            "delta": delta,
        })
    return out


def cross_dataset_headline():
    """Pull a030 / COMBO headlines from existing R40 / R42 / R44 / R39 summary files."""
    rows = []

    # R40 headline
    r40_a030 = json.loads((R40_RECON_ROOT / "a030_micro_summary.json").read_text(encoding="utf-8"))
    r40_combo = json.loads((R40_RECON_ROOT / "combo_micro_summary.json").read_text(encoding="utf-8"))
    rows.append({
        "dataset": "R40 micro_val_unseen",
        "model": "COMBO",
        "metric_psnr": _round4(r40_combo.get("overall_avg_psnr")),
        "metric_ssim": _round4(r40_combo.get("overall_avg_ssim")),
        "metric_hf_retention": _round4(r40_combo.get("overall_high_frequency_retention")),
        "metric_edge_retention": _round4(r40_combo.get("overall_edge_retention")),
        "metric_contrast_retention": _round4(r40_combo.get("overall_contrast_retention")),
    })
    rows.append({
        "dataset": "R40 micro_val_unseen",
        "model": "a030",
        "metric_psnr": _round4(r40_a030.get("overall_avg_psnr")),
        "metric_ssim": _round4(r40_a030.get("overall_avg_ssim")),
        "metric_hf_retention": _round4(r40_a030.get("overall_high_frequency_retention")),
        "metric_edge_retention": _round4(r40_a030.get("overall_edge_retention")),
        "metric_contrast_retention": _round4(r40_a030.get("overall_contrast_retention")),
    })

    # R39 shape headline (from sweep_summary.json).  We pull alpha=0 (COMBO) and alpha=0.30 rows.
    sweep_path = EXPERIMENT_ROOT / "results" / "weight_sweep" / "sweep_summary.json"
    if sweep_path.exists():
        sweep = json.loads(sweep_path.read_text(encoding="utf-8"))
        for row in sweep.get("rows", []):
            if abs(float(row["alpha"]) - 0.0) < 1e-6:
                rows.append({
                    "dataset": "R39 shape_val_unseen",
                    "model": "COMBO",
                    "metric_psnr": _round4(row.get("shape_overall_psnr")),
                    "metric_ssim": _round4(row.get("shape_overall_ssim")),
                    "ring_8px": _round4(row.get("ring_8px_step_std")),
                    "ring_0p8px": _round4(row.get("ring_0p8px_step_std")),
                    "ring_0p08px": _round4(row.get("ring_0p08px_step_std")),
                })
            if abs(float(row["alpha"]) - 0.30) < 1e-6:
                rows.append({
                    "dataset": "R39 shape_val_unseen",
                    "model": "a030",
                    "metric_psnr": _round4(row.get("shape_overall_psnr")),
                    "metric_ssim": _round4(row.get("shape_overall_ssim")),
                    "ring_8px": _round4(row.get("ring_8px_step_std")),
                    "ring_0p8px": _round4(row.get("ring_0p8px_step_std")),
                    "ring_0p08px": _round4(row.get("ring_0p08px_step_std")),
                })

    return rows


def make_contact_sheet(*, profile_dir, r40_rows, output_path, examples_per_stage=4):
    """Per stage, pick examples_per_stage representative pairs and lay out
    GT / COMBO / a030 side by side."""
    # group rows by (stage, frame_id) so we can find COMBO & a030 outputs
    by_stage_frame = defaultdict(dict)
    for r in r40_rows:
        by_stage_frame[(r["stage"], r["frame_id"])][r["model"]] = r

    # pick examples per stage with priority: spread of frame indices
    stages = sorted({k[0] for k in by_stage_frame})
    chosen = []
    for stage in stages:
        frames = sorted({k[1] for k in by_stage_frame if k[0] == stage})
        if not frames:
            continue
        if len(frames) <= examples_per_stage:
            picks = frames
        else:
            step = max(1, len(frames) // examples_per_stage)
            picks = frames[::step][:examples_per_stage]
        for fid in picks:
            chosen.append((stage, fid))

    if not chosen:
        return

    # locate inner dirs once per stage / model
    stage_inner_combo = {s: find_recon_inner(R40_RECON_ROOT, s, COMBO_TAG) for s in stages}
    stage_inner_a030 = {s: find_recon_inner(R40_RECON_ROOT, s, A030_TAG) for s in stages}

    cell_w, cell_h = 200, 220
    label_left = 130
    rows = chosen
    canvas_w = label_left + cell_w * 3 + 12
    canvas_h = 60 + cell_h * len(rows) + 8
    canvas = np.full((canvas_h, canvas_w, 3), 250, dtype=np.uint8)

    def put_text(img, text, xy, scale=0.45, color=(20, 20, 20)):
        cv2.putText(img, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)

    put_text(canvas, "R39 a030 vs COMBO on R40 micro_val_unseen (representative frames)", (12, 24), scale=0.55)
    put_text(canvas, "GT", (label_left + 80, 56))
    put_text(canvas, "COMBO", (label_left + cell_w + 60, 56))
    put_text(canvas, "a030", (label_left + cell_w * 2 + 70, 56))

    for r_idx, (stage, fid) in enumerate(rows):
        y = 70 + r_idx * cell_h
        family_short = stage.replace("stage_", "").replace("_micro_", " ")
        put_text(canvas, f"{family_short}", (8, y + 22))
        put_text(canvas, f"{fid}", (8, y + 42), scale=0.40, color=(80, 80, 80))

        gt_path = profile_dir / f"lbl/{stage}/{fid}.bmp"
        combo_inner = stage_inner_combo.get(stage)
        a030_inner = stage_inner_a030.get(stage)
        combo_path = combo_inner / f"{fid}.bmp" if combo_inner is not None else None
        a030_path = a030_inner / f"{fid}.bmp" if a030_inner is not None else None

        for c_idx, p in enumerate([gt_path, combo_path, a030_path]):
            x = label_left + c_idx * cell_w
            if p is None or not p.exists():
                continue
            img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            target_h, target_w = cell_h - 16, cell_w - 8
            sized = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(sized, cv2.COLOR_GRAY2BGR)
            canvas[y + 8 : y + 8 + target_h, x : x + target_w] = rgb

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), canvas)
    print(f"  contact sheet -> {output_path}", flush=True)


def write_report(*, summary_rows, delta_psnr, delta_shape, delta_f, headline_rows,
                 r39_summary, r40_summary, output_dir, contact_sheet_path, report_path):
    lines = [
        "# R39 a030 在多樣顯微圖形上的詳細評估",
        "",
        "## 摘要",
        "",
        "本評估目的是把 a030（`r39_combo_strong_avg_a030`，COMBO 與 R39_strong 在 alpha=0.30 的權重平均）",
        "在不同類型顯微結構重建上的表現，跟 COMBO 直接對比。所有評估都重用既有重建，沒有跑新的 inference。",
        "",
        "本份報告只忠實紀錄觀察與數字，不下 verdict、不寫推薦。",
        "",
        "## 測試集",
        "",
        "| 資料集 | 場景類型 | 對數 | 重建路徑 |",
        "|---|---|---:|---|",
        "| R39 `shape_val_unseen` | 訓練分布內：純幾何形狀 7 類（三角形、圓、矩形、橢圓、多邊形、簡單混合、複雜混合） | 210 | `results/weight_sweep/shape_recon/{a000\\|a030}` |",
        "| R40 `micro_val_unseen` | 訓練分布外：5 類顯微結構（細線/格、IC 風格大區塊、紋理、邊緣缺陷、混合場景） | 100 | `Experiments/R40_MicroscopyFeatureCoverage/results/micro_recon` |",
        "",
        "兩個資料集都用同一套指標重新計算：PSNR、SSIM、高頻保留比、邊緣能量比、對比保留比、邊界 F1、",
        "形狀錯誤分數（R44G），讓 in-distribution 跟 out-of-distribution 的數字直接可比。",
        "",
        "## R40 micro_val_unseen 逐 stage 數字",
        "",
        "### a030 vs COMBO PSNR",
        "",
        _md_pivot(delta_psnr, "R40_micro_val_unseen"),
        "",
        "### a030 vs COMBO 邊界 F1",
        "",
        _md_pivot(delta_f, "R40_micro_val_unseen"),
        "",
        "### a030 vs COMBO 形狀錯誤分數",
        "",
        _md_pivot(delta_shape, "R40_micro_val_unseen", invert_delta_meaning=True),
        "",
        "### 整體（5 個 stage 平均）",
        "",
        _md_overall_table([r for r in r40_summary if r["dataset"] == "R40_micro_val_unseen"]),
        "",
        "## R39 shape_val_unseen（訓練分布內對照）",
        "",
        "### a030 vs COMBO PSNR",
        "",
        _md_pivot(delta_psnr, "R39_shape_val_unseen"),
        "",
        "### 整體（7 個 stage 平均）",
        "",
        _md_overall_table([r for r in r39_summary if r["dataset"] == "R39_shape_val_unseen"]),
        "",
        "## 跨資料集 headline",
        "",
        _md_headline(headline_rows),
        "",
        "## 視覺對比",
        "",
        f"![a030 vs COMBO 多 stage 代表]({contact_sheet_path.relative_to(EXPERIMENT_ROOT).as_posix()})",
        "",
        "每個 stage 取四個代表性 frame，三聯為 GT、COMBO 重建、a030 重建。",
        "",
        "## 觀察記錄",
        "",
        "（以下為事實描述，依數字與視覺整理；判斷與下一步留給後續決策。）",
        "",
    ]

    obs = _build_observations(r40_summary, r39_summary, delta_psnr, delta_shape, delta_f)
    lines.extend(obs)

    lines.extend([
        "",
        "## 產物",
        "",
        "- `results/a030_microscopy_eval/per_pair_metrics.csv`：所有資料集所有 pair 的逐張指標。",
        "- `results/a030_microscopy_eval/stage_summary.csv`：逐資料集逐 stage 平均。",
        "- `results/a030_microscopy_eval/overall_summary.csv`：每個資料集的整體平均。",
        "- `results/a030_microscopy_eval/cross_dataset_headline.json`：a030 / COMBO 跨資料集 headline。",
        "- `results/a030_microscopy_eval/visuals/contact_sheet_r40.png`：R40 5 個 stage × 4 個 frame 三聯對比。",
        "",
        "## 方法",
        "",
        "- 重建：直接讀取 R40 已有的 a030（`*_20260430_121954`）與 COMBO（`*_20260408_003525`）BMP；",
        "  R39 shape_val_unseen 用 sweep 已存的 `shape_recon/a030` 與 `shape_recon/a000`（即 COMBO）。",
        "- PSNR / SSIM / 高頻保留比 / 邊緣能量比 / 對比保留比：直接用 `r40_micro_metrics.image_metric_row`。",
        "- 邊界 F1 / 形狀錯誤分數：用 `r44_motion_metrics.matched_gradient_boundary` 取每張 GT、預測各自 3% 強梯度像素為邊界遮罩，",
        "  再套 `r44g_boundary_shape_metrics.boundary_shape_metrics`。GT 跟預測用相同方法取 boundary 是為了讓 R39/R40 兩套",
        "  資料集（沒附 boundary mask）跟 R42/R44（有 boundary mask）一致可比。",
        "- Contact sheet：每 stage 等距挑 4 個 frame，BMP 縮放至 192×204 三聯顯示。",
    ])

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _md_pivot(delta_rows, dataset_filter, *, invert_delta_meaning=False):
    rows = [r for r in delta_rows if r["dataset"] == dataset_filter]
    if not rows:
        return "(無資料)"
    lines = ["| Stage | COMBO | a030 | a030 - COMBO |", "|---|---:|---:|---:|"]
    direction_note = "（負值=a030 比 COMBO 低）" if invert_delta_meaning else "（正值=a030 比 COMBO 高）"
    for r in rows:
        c = "" if r["COMBO"] is None else f"{r['COMBO']:.4f}"
        a = "" if r["a030"] is None else f"{r['a030']:.4f}"
        d = "" if r["delta"] is None else f"{r['delta']:+.4f}"
        lines.append(f"| {r['stage']} | {c} | {a} | {d} |")
    lines.append("")
    lines.append(direction_note)
    return "\n".join(lines)


def _md_overall_table(overall_rows):
    if not overall_rows:
        return "(無資料)"
    keys = [
        ("avg_psnr", "PSNR"),
        ("avg_ssim", "SSIM"),
        ("avg_high_frequency_retention", "HF retention"),
        ("avg_edge_retention", "Edge retention"),
        ("avg_contrast_retention", "Contrast retention"),
        ("avg_boundary_f_score", "邊界 F1"),
        ("avg_shape_error_score", "形狀錯誤"),
    ]
    by_model = {r["model"]: r for r in overall_rows}
    lines = ["| 指標 | COMBO | a030 | a030 - COMBO |", "|---|---:|---:|---:|"]
    for k, label in keys:
        c = by_model.get("COMBO", {}).get(k)
        a = by_model.get("a030", {}).get(k)
        d = (a - c) if (a is not None and c is not None) else None
        cs = "" if c is None else f"{c:.4f}"
        as_ = "" if a is None else f"{a:.4f}"
        ds = "" if d is None else f"{d:+.4f}"
        lines.append(f"| {label} | {cs} | {as_} | {ds} |")
    return "\n".join(lines)


def _md_headline(rows):
    if not rows:
        return "(無資料)"
    fields = [
        ("dataset", "資料集"),
        ("model", "模型"),
        ("metric_psnr", "PSNR"),
        ("metric_ssim", "SSIM"),
        ("metric_hf_retention", "HF"),
        ("metric_edge_retention", "Edge"),
        ("metric_contrast_retention", "Contrast"),
        ("ring_8px", "ring 8px"),
        ("ring_0p8px", "ring 0.8px"),
        ("ring_0p08px", "ring 0.08px"),
    ]
    lines = ["| " + " | ".join(label for _, label in fields) + " |",
             "|" + "|".join("---" for _ in fields) + "|"]
    for r in rows:
        cells = []
        for k, _ in fields:
            v = r.get(k)
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.4f}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _build_observations(r40_summary, r39_summary, delta_psnr, delta_shape, delta_f):
    obs = []
    # 1. PSNR delta range on R40
    r40_psnr = [r for r in delta_psnr if r["dataset"] == "R40_micro_val_unseen" and r["delta"] is not None]
    if r40_psnr:
        deltas = [r["delta"] for r in r40_psnr]
        obs.append(f"- R40 微觀資料集上，a030 對 5 個 stage 的 PSNR 變化範圍為 `{min(deltas):+.4f}` 到 `{max(deltas):+.4f}` dB；")
        obs.append(f"  五個 stage 全部 a030 比 COMBO 高的 stage 數：{sum(1 for d in deltas if d > 0)}/{len(deltas)}。")
    r39_psnr = [r for r in delta_psnr if r["dataset"] == "R39_shape_val_unseen" and r["delta"] is not None]
    if r39_psnr:
        deltas = [r["delta"] for r in r39_psnr]
        obs.append(f"- R39 形狀資料集（訓練分布內）上，a030 對 7 個 stage 的 PSNR 變化範圍為 `{min(deltas):+.4f}` 到 `{max(deltas):+.4f}` dB；")
        obs.append(f"  全部 a030 比 COMBO 高的 stage 數：{sum(1 for d in deltas if d > 0)}/{len(deltas)}。")
    # boundary F
    r40_f = [r for r in delta_f if r["dataset"] == "R40_micro_val_unseen" and r["delta"] is not None]
    if r40_f:
        deltas = [r["delta"] for r in r40_f]
        obs.append(f"- R40 邊界 F1：a030 對 COMBO 變化範圍 `{min(deltas):+.4f}` 到 `{max(deltas):+.4f}`；")
        obs.append(f"  a030 較高的 stage 數：{sum(1 for d in deltas if d > 0)}/{len(deltas)}。")
    # shape error
    r40_se = [r for r in delta_shape if r["dataset"] == "R40_micro_val_unseen" and r["delta"] is not None]
    if r40_se:
        deltas = [r["delta"] for r in r40_se]
        obs.append(f"- R40 形狀錯誤分數（越低越好）：a030 對 COMBO 變化範圍 `{min(deltas):+.4f}` 到 `{max(deltas):+.4f}`；")
        obs.append(f"  a030 較低（即較好）的 stage 數：{sum(1 for d in deltas if d < 0)}/{len(deltas)}。")
    obs.append("")
    obs.append("逐 stage 細節見上面三張 PSNR / 邊界 F1 / 形狀錯誤分數對比表。")
    obs.append("")
    obs.append("分布內 vs 分布外對照（PSNR）：")
    obs.append("")
    if r39_psnr:
        avg_r39 = sum(r["delta"] for r in r39_psnr) / len(r39_psnr)
        obs.append(f"- R39 shape_val_unseen 七類平均 PSNR delta：`{avg_r39:+.4f}` dB（訓練分布內）。")
    if r40_psnr:
        avg_r40 = sum(r["delta"] for r in r40_psnr) / len(r40_psnr)
        obs.append(f"- R40 micro_val_unseen 五類平均 PSNR delta：`{avg_r40:+.4f}` dB（訓練分布外）。")
    return obs


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--visual-dir", type=Path, default=DEFAULT_VISUAL_DIR)
    parser.add_argument("--skip-r39", action="store_true", help="Skip R39 shape_val_unseen recompute")
    args = parser.parse_args(argv)
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    args.visual_dir.mkdir(parents=True, exist_ok=True)

    print("[a030 eval] R40 micro_val_unseen ...", flush=True)
    r40_profile_dir = R40_DATA_ROOT / R40_PROFILE
    r40_a030_rows = collect_r40(profile_dir=r40_profile_dir, recon_root=R40_RECON_ROOT,
                                model_label="a030", recon_tag=A030_TAG)
    r40_combo_rows = collect_r40(profile_dir=r40_profile_dir, recon_root=R40_RECON_ROOT,
                                 model_label="COMBO", recon_tag=COMBO_TAG)

    r39_a030_rows = []
    r39_combo_rows = []
    if not args.skip_r39:
        print("[a030 eval] R39 shape_val_unseen ...", flush=True)
        r39_profile_dir = R39_DATA_ROOT / R39_PROFILE
        r39_a030_rows = collect_r39_shape(profile_dir=r39_profile_dir,
                                          recon_root_alpha=R39_RECON_ROOT_A030,
                                          model_label="a030")
        r39_combo_rows = collect_r39_shape(profile_dir=r39_profile_dir,
                                           recon_root_alpha=R39_RECON_ROOT_COMBO,
                                           model_label="COMBO")

    all_rows = r40_a030_rows + r40_combo_rows + r39_a030_rows + r39_combo_rows
    summary_rows = summarize(all_rows)
    overall_rows = overall(all_rows)

    delta_psnr = make_delta_table(summary_rows, key="avg_psnr")
    delta_shape = make_delta_table(summary_rows, key="avg_shape_error_score")
    delta_f = make_delta_table(summary_rows, key="avg_boundary_f_score")

    headline = cross_dataset_headline()

    _write_csv(all_rows, output_dir / "per_pair_metrics.csv")
    _write_csv(summary_rows, output_dir / "stage_summary.csv")
    _write_csv(overall_rows, output_dir / "overall_summary.csv")
    _write_csv(delta_psnr, output_dir / "delta_psnr.csv")
    _write_csv(delta_shape, output_dir / "delta_shape_error.csv")
    _write_csv(delta_f, output_dir / "delta_boundary_f.csv")
    _write_json({"headline": headline}, output_dir / "cross_dataset_headline.json")

    contact_path = args.visual_dir / "contact_sheet_r40.png"
    make_contact_sheet(profile_dir=r40_profile_dir, r40_rows=r40_a030_rows + r40_combo_rows,
                       output_path=contact_path)

    write_report(
        summary_rows=summary_rows,
        delta_psnr=delta_psnr,
        delta_shape=delta_shape,
        delta_f=delta_f,
        headline_rows=headline,
        r39_summary=overall_rows,
        r40_summary=overall_rows,
        output_dir=output_dir,
        contact_sheet_path=contact_path,
        report_path=args.report,
    )

    print(f"[a030 eval] done -> report at {args.report}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
