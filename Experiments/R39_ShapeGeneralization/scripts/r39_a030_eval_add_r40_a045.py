"""Follow-up to `r39_a030_microscopy_evaluation.py`: add R40 a045 as a third
candidate alongside COMBO and a030.  Reuses the metric pipeline from the
main script; outputs CSVs plus a markdown fragment that can be merged into
the existing report.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import cv2  # noqa: F401
import numpy as np  # noqa: F401


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R39_ShapeGeneralization"
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import r39_a030_microscopy_evaluation as base  # noqa: E402


R40_A045_RECON_ROOT_ON_R40 = (
    REPO_ROOT
    / "Experiments"
    / "R40_MicroscopyFeatureCoverage"
    / "results"
    / "weight_sweep"
    / "combo_best_low_alpha"
    / "micro_recon"
    / "a045"
)
R40_A045_RECON_ROOT_ON_R39 = (
    EXPERIMENT_ROOT / "results" / "a030_microscopy_eval" / "r40_a045_on_shape"
)


def collect_r40_a045_on_r40(*, profile_dir):
    rows = []
    manifest = json.loads((profile_dir / "manifest.json").read_text(encoding="utf-8"))
    pairs = manifest["pairs"]
    print(f"  [R40 a045] R40 micro_val_unseen {len(pairs)} pairs", flush=True)
    for idx, p in enumerate(pairs):
        if idx % 25 == 0 and idx > 0:
            print(f"    {idx}/{len(pairs)}", flush=True)
        stage = p["stage"]
        inner = base.find_recon_inner_alpha_layout(R40_A045_RECON_ROOT_ON_R40, stage)
        if inner is None:
            continue
        lbl_path = profile_dir / p["package_lbl"]
        pred_path = inner / Path(p["package_lbl"]).name
        if not pred_path.exists():
            continue
        metrics = base.evaluate_pair(lbl_path, pred_path)
        rows.append({
            "model": "R40 a045",
            "dataset": "R40_micro_val_unseen",
            "stage": stage,
            "feature_family": p["feature_family"],
            "frame_id": Path(p["package_lbl"]).stem,
            **metrics,
        })
    return rows


def collect_r40_a045_on_r39(*, profile_dir):
    rows = []
    manifest = json.loads((profile_dir / "manifest.json").read_text(encoding="utf-8"))
    pairs = manifest["pairs"]
    print(f"  [R40 a045] R39 shape_val_unseen {len(pairs)} pairs", flush=True)
    for idx, p in enumerate(pairs):
        if idx % 50 == 0 and idx > 0:
            print(f"    {idx}/{len(pairs)}", flush=True)
        stage = p["stage"]
        inner = base.find_recon_inner_alpha_layout(R40_A045_RECON_ROOT_ON_R39, stage)
        if inner is None:
            continue
        lbl_path = profile_dir / p["package_lbl"]
        pred_path = inner / Path(p["package_lbl"]).name
        if not pred_path.exists():
            continue
        metrics = base.evaluate_pair(lbl_path, pred_path)
        rows.append({
            "model": "R40 a045",
            "dataset": "R39_shape_val_unseen",
            "stage": stage,
            "feature_family": p.get("feature_family", stage.replace("stage_", "").split("_", 1)[-1]),
            "frame_id": Path(p["package_lbl"]).stem,
            **metrics,
        })
    return rows


def _round4(v):
    if v is None:
        return None
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return round(float(v), 4)


def merge_with_existing(r40_a045_rows):
    """Read existing per_pair CSV, drop any old R40 a045 rows, then append the
    fresh ones.  Recompute summary + overall + delta tables to match."""
    output_dir = EXPERIMENT_ROOT / "results" / "a030_microscopy_eval"
    per_pair_csv = output_dir / "per_pair_metrics.csv"
    if not per_pair_csv.exists():
        raise FileNotFoundError(f"missing existing per_pair_metrics: {per_pair_csv}")
    existing = list(csv.DictReader(per_pair_csv.open(encoding="utf-8-sig")))
    existing = [r for r in existing if r.get("model") != "R40 a045"]
    # convert numeric strings back to floats so summarize/_round4 work
    numeric_keys = {
        "psnr", "ssim", "high_frequency_retention", "edge_retention",
        "contrast_retention", "boundary_f_score", "shape_error_score",
        "boundary_density_ratio", "fragmentation_ratio",
        "straight_edge_coverage", "corner_retention",
    }
    for row in existing:
        for k in numeric_keys:
            v = row.get(k)
            row[k] = float(v) if v not in (None, "") else None
    merged = existing + r40_a045_rows
    return merged, output_dir


def write_csv(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields = sorted({k for r in rows for k in r})
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def make_pivot_three(summary_rows, *, key, dataset_filter,
                     models=("COMBO", "a030", "R40 a045")):
    by_stage = defaultdict(dict)
    for r in summary_rows:
        if r["dataset"] != dataset_filter:
            continue
        by_stage[r["stage"]][r["model"]] = r.get(key)
    out = []
    for stage in sorted(by_stage):
        m = by_stage[stage]
        row = {
            "dataset": dataset_filter,
            "stage": stage,
            "metric": key,
            **{model: _round4(m.get(model)) for model in models},
        }
        ref = m.get(models[0])
        for model in models[1:]:
            v = m.get(model)
            row[f"{model} - {models[0]}"] = _round4(v - ref) if (v is not None and ref is not None) else None
        out.append(row)
    return out


def build_overall_three(rows, *, models=("COMBO", "a030", "R40 a045")):
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["model"], r["dataset"])].append(r)
    keys = (
        "psnr", "ssim", "high_frequency_retention", "edge_retention",
        "contrast_retention", "boundary_f_score", "shape_error_score",
    )
    out_summary = []
    for (model, dataset), grp in sorted(grouped.items()):
        row = {"model": model, "dataset": dataset, "count": len(grp)}
        for k in keys:
            vals = [r[k] for r in grp if r[k] is not None and math.isfinite(float(r[k]))]
            row[f"avg_{k}"] = _round4(sum(vals) / len(vals)) if vals else None
        out_summary.append(row)
    return out_summary


def md_pivot_three(rows, *, label, invert=False, models=("COMBO", "a030", "R40 a045")):
    if not rows:
        return f"{label}\n\n(無資料)"
    cols = ["Stage", *models, f"{models[1]} - {models[0]}", f"{models[2]} - {models[0]}"]
    lines = [label, "", "| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        cells = [r["stage"]]
        for model in models:
            v = r.get(model)
            cells.append("" if v is None else f"{v:.4f}")
        for model in models[1:]:
            v = r.get(f"{model} - {models[0]}")
            cells.append("" if v is None else f"{v:+.4f}")
        lines.append("| " + " | ".join(cells) + " |")
    direction = "（負值=該模型比 COMBO 低）" if invert else "（正值=該模型比 COMBO 高）"
    lines.append("")
    lines.append(direction)
    return "\n".join(lines)


def md_overall_three(overall_rows, dataset_filter, *, models=("COMBO", "a030", "R40 a045")):
    keys = [
        ("avg_psnr", "PSNR"),
        ("avg_ssim", "SSIM"),
        ("avg_high_frequency_retention", "HF retention"),
        ("avg_edge_retention", "Edge retention"),
        ("avg_contrast_retention", "Contrast retention"),
        ("avg_boundary_f_score", "邊界 F1"),
        ("avg_shape_error_score", "形狀錯誤"),
    ]
    by_model = {r["model"]: r for r in overall_rows if r["dataset"] == dataset_filter}
    lines = [
        "| 指標 | " + " | ".join(models) + " |",
        "|---|" + "|".join("---:" for _ in models) + "|",
    ]
    for k, label in keys:
        cells = [label]
        for model in models:
            v = by_model.get(model, {}).get(k)
            cells.append("" if v is None else f"{v:.4f}")
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_supplement_markdown(*, summary_rows, overall_rows, output_path):
    """A self-contained Markdown fragment to append to the main report."""
    psnr_r39 = make_pivot_three(summary_rows, key="avg_psnr", dataset_filter="R39_shape_val_unseen")
    psnr_r40 = make_pivot_three(summary_rows, key="avg_psnr", dataset_filter="R40_micro_val_unseen")
    f_r40 = make_pivot_three(summary_rows, key="avg_boundary_f_score", dataset_filter="R40_micro_val_unseen")
    se_r40 = make_pivot_three(summary_rows, key="avg_shape_error_score", dataset_filter="R40_micro_val_unseen")
    se_r39 = make_pivot_three(summary_rows, key="avg_shape_error_score", dataset_filter="R39_shape_val_unseen")

    lines = [
        "## R40 a045 對比拼圖",
        "",
        "把 R40 a045（R40 路線在 alpha=0.45 的權重平均，本地三尺度環形守門過、外部 8 px 退步 +22.80%）",
        "拉進來跟 a030 / COMBO 並列，看「廣譜變強」 vs 「換顯微強度」這個取捨。",
        "",
        "### R39 shape_val_unseen 逐 stage PSNR（訓練分布內）",
        "",
        md_pivot_three(psnr_r39, label="").strip(),
        "",
        "### R39 shape_val_unseen 逐 stage 形狀錯誤分數",
        "",
        md_pivot_three(se_r39, label="", invert=True).strip(),
        "",
        "### R39 shape_val_unseen 整體（7 個 stage 平均）",
        "",
        md_overall_three(overall_rows, "R39_shape_val_unseen"),
        "",
        "### R40 micro_val_unseen 逐 stage PSNR（訓練分布外）",
        "",
        md_pivot_three(psnr_r40, label="").strip(),
        "",
        "### R40 micro_val_unseen 逐 stage 邊界 F1",
        "",
        md_pivot_three(f_r40, label="").strip(),
        "",
        "### R40 micro_val_unseen 逐 stage 形狀錯誤分數",
        "",
        md_pivot_three(se_r40, label="", invert=True).strip(),
        "",
        "### R40 micro_val_unseen 整體（5 個 stage 平均）",
        "",
        md_overall_three(overall_rows, "R40_micro_val_unseen"),
        "",
        "### 觀察",
        "",
    ]

    obs = _build_observations(summary_rows, overall_rows)
    lines.extend(obs)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_observations(summary_rows, overall_rows):
    """Pure observations; no verdict."""
    obs = []

    # R39 shape PSNR delta vs COMBO
    psnr_r39 = make_pivot_three(summary_rows, key="avg_psnr", dataset_filter="R39_shape_val_unseen")
    if psnr_r39:
        # R40 a045 vs COMBO sign
        a045_d = [r["R40 a045 - COMBO"] for r in psnr_r39 if r["R40 a045 - COMBO"] is not None]
        a030_d = [r["a030 - COMBO"] for r in psnr_r39 if r["a030 - COMBO"] is not None]
        if a045_d and a030_d:
            n_a045_pos = sum(1 for d in a045_d if d > 0)
            n_a030_pos = sum(1 for d in a030_d if d > 0)
            obs.append(
                f"- R39 shape_val_unseen 七類 PSNR：a030 對 COMBO 全勝 {n_a030_pos}/{len(a030_d)}；"
                f"R40 a045 對 COMBO 勝出 {n_a045_pos}/{len(a045_d)}。"
            )
            obs.append(
                f"  PSNR 平均差距 vs COMBO：a030 `{sum(a030_d)/len(a030_d):+.4f}` dB、"
                f"R40 a045 `{sum(a045_d)/len(a045_d):+.4f}` dB。"
            )

    # R40 micro PSNR delta vs COMBO
    psnr_r40 = make_pivot_three(summary_rows, key="avg_psnr", dataset_filter="R40_micro_val_unseen")
    if psnr_r40:
        a045_d = [r["R40 a045 - COMBO"] for r in psnr_r40 if r["R40 a045 - COMBO"] is not None]
        a030_d = [r["a030 - COMBO"] for r in psnr_r40 if r["a030 - COMBO"] is not None]
        if a045_d and a030_d:
            n_a045_pos = sum(1 for d in a045_d if d > 0)
            n_a030_pos = sum(1 for d in a030_d if d > 0)
            obs.append(
                f"- R40 micro_val_unseen 五類 PSNR：a030 對 COMBO 勝出 {n_a030_pos}/{len(a030_d)}；"
                f"R40 a045 對 COMBO 勝出 {n_a045_pos}/{len(a045_d)}。"
            )
            obs.append(
                f"  PSNR 平均差距 vs COMBO：a030 `{sum(a030_d)/len(a030_d):+.4f}` dB、"
                f"R40 a045 `{sum(a045_d)/len(a045_d):+.4f}` dB。"
            )

    # R40 shape error vs COMBO (lower is better)
    se_r40 = make_pivot_three(summary_rows, key="avg_shape_error_score", dataset_filter="R40_micro_val_unseen")
    if se_r40:
        a045_d = [r["R40 a045 - COMBO"] for r in se_r40 if r["R40 a045 - COMBO"] is not None]
        a030_d = [r["a030 - COMBO"] for r in se_r40 if r["a030 - COMBO"] is not None]
        if a045_d and a030_d:
            n_a045_better = sum(1 for d in a045_d if d < 0)
            n_a030_better = sum(1 for d in a030_d if d < 0)
            obs.append(
                f"- R40 micro_val_unseen 形狀錯誤（越低越好）：a030 比 COMBO 低的 stage 數 {n_a030_better}/{len(a030_d)}；"
                f"R40 a045 比 COMBO 低的 stage 數 {n_a045_better}/{len(a045_d)}。"
            )

    # cross-dataset pattern note
    obs.append("")
    obs.append("跨資料集對照（R40 a045）：")

    overall_by = {(r["model"], r["dataset"]): r for r in overall_rows}
    r40_a045_r39 = overall_by.get(("R40 a045", "R39_shape_val_unseen"))
    r40_a045_r40 = overall_by.get(("R40 a045", "R40_micro_val_unseen"))
    a030_r39 = overall_by.get(("a030", "R39_shape_val_unseen"))
    a030_r40 = overall_by.get(("a030", "R40_micro_val_unseen"))
    combo_r39 = overall_by.get(("COMBO", "R39_shape_val_unseen"))
    combo_r40 = overall_by.get(("COMBO", "R40_micro_val_unseen"))

    if r40_a045_r39 and a030_r39 and combo_r39:
        obs.append(
            f"- R39 整體 PSNR：COMBO `{combo_r39['avg_psnr']:.4f}`、"
            f"a030 `{a030_r39['avg_psnr']:.4f}`、R40 a045 `{r40_a045_r39['avg_psnr']:.4f}`"
        )
    if r40_a045_r40 and a030_r40 and combo_r40:
        obs.append(
            f"- R40 整體 PSNR：COMBO `{combo_r40['avg_psnr']:.4f}`、"
            f"a030 `{a030_r40['avg_psnr']:.4f}`、R40 a045 `{r40_a045_r40['avg_psnr']:.4f}`"
        )
    if r40_a045_r39 and r40_a045_r40:
        obs.append(
            f"- R40 a045 在訓練分布外（R40）跟分布內（R39）的整體 PSNR 落差："
            f"`{r40_a045_r40['avg_psnr'] - r40_a045_r39['avg_psnr']:+.4f}` dB"
        )

    obs.append("")
    obs.append("外部 GMF 升級門檻方向（已知數字，這次沒重算）：")
    obs.append("- COMBO 是基準。")
    obs.append("- a030 三尺度都在容忍區內：8 px −6.94%、0.8 px +6.42%、0.08 px −15.97%（PASS_TRADEOFF）。")
    obs.append("- R40 a045 8 px 退 +22.80%（超出 3% 升級上限與 7% 替代容忍區），0.8 px +1.33%、0.08 px −2.85%（RESEARCH_CAPACITY_ONLY）。")

    return obs


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=EXPERIMENT_ROOT / "results" / "a030_microscopy_eval")
    parser.add_argument("--supplement-md", type=Path,
                        default=EXPERIMENT_ROOT / "reports" / "R39_A030_MICROSCOPY_EVALUATION_SUPPLEMENT_R40A045.md")
    args = parser.parse_args(argv)

    print("[r40 a045 supplement] R40 micro_val_unseen ...", flush=True)
    r40_profile_dir = base.R40_DATA_ROOT / base.R40_PROFILE
    r40_a045_on_r40 = collect_r40_a045_on_r40(profile_dir=r40_profile_dir)

    print("[r40 a045 supplement] R39 shape_val_unseen ...", flush=True)
    r39_profile_dir = base.R39_DATA_ROOT / base.R39_PROFILE
    r40_a045_on_r39 = collect_r40_a045_on_r39(profile_dir=r39_profile_dir)

    new_rows = r40_a045_on_r40 + r40_a045_on_r39
    print(f"  R40 a045 rows: {len(new_rows)}", flush=True)

    merged, output_dir = merge_with_existing(new_rows)
    summary_rows = base.summarize(merged)
    overall_rows = build_overall_three(merged)

    write_csv(merged, output_dir / "per_pair_metrics.csv")
    write_csv(summary_rows, output_dir / "stage_summary.csv")
    write_csv(overall_rows, output_dir / "overall_summary.csv")

    psnr_r39 = make_pivot_three(summary_rows, key="avg_psnr", dataset_filter="R39_shape_val_unseen")
    psnr_r40 = make_pivot_three(summary_rows, key="avg_psnr", dataset_filter="R40_micro_val_unseen")
    f_r40 = make_pivot_three(summary_rows, key="avg_boundary_f_score", dataset_filter="R40_micro_val_unseen")
    se_r40 = make_pivot_three(summary_rows, key="avg_shape_error_score", dataset_filter="R40_micro_val_unseen")
    se_r39 = make_pivot_three(summary_rows, key="avg_shape_error_score", dataset_filter="R39_shape_val_unseen")
    write_csv(psnr_r39, output_dir / "delta_three_psnr_r39.csv")
    write_csv(psnr_r40, output_dir / "delta_three_psnr_r40.csv")
    write_csv(f_r40, output_dir / "delta_three_boundary_f_r40.csv")
    write_csv(se_r40, output_dir / "delta_three_shape_error_r40.csv")
    write_csv(se_r39, output_dir / "delta_three_shape_error_r39.csv")

    write_supplement_markdown(summary_rows=summary_rows, overall_rows=overall_rows,
                              output_path=args.supplement_md)
    print(f"[r40 a045 supplement] done -> {args.supplement_md}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
