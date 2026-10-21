"""R46 capability eval:對 R46 重建跑 per-pair metrics,合併進 a025 既有 csv。

讀:
- a025 既有 capability_eval/per_pair_metrics.csv(已含 COMBO / a030 / a043 / R39R40_a025 四 model)
- R46 重建 BMP(在 R46/results/shape_recon/r46/ 跟 micro_recon/r46/)

寫:
- R46/results/capability_eval/per_pair_metrics_r46_only.csv(只 R46 五 stage)
- R46/results/capability_eval/per_pair_metrics_combined.csv(R46 + COMBO + a030 + a043 + a025)
- R46/results/capability_eval/stage_summary.csv(逐 stage 平均)
- R46/results/capability_eval/overall_summary.csv(整體平均)

合併後的 csv 可以直接餵給既有的 rayleigh_diagnostic.py /
rayleigh_diagnostic_validate.py / rayleigh_diagnostic_plots.py。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT / "Experiments" / "R39_ShapeGeneralization" / "scripts"))

import r39_a030_microscopy_evaluation as base  # noqa: E402


A025_PER_PAIR_CSV = (
    REPO_ROOT
    / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep"
    / "capability_eval/per_pair_metrics.csv"
)

R39_VAL_PROFILE = REPO_ROOT / "Training_Data/r39_shape_generalization/shape_val_unseen"
R40_VAL_PROFILE = REPO_ROOT / "Training_Data/r40_microscopy_feature_coverage/micro_val_unseen"

R46_EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R46_CornerAwareFineTune"
R46_SHAPE_RECON_BASE = R46_EXPERIMENT_ROOT / "results" / "shape_recon" / "r46"
R46_MICRO_RECON_BASE = R46_EXPERIMENT_ROOT / "results" / "micro_recon" / "r46"
R46_EVAL_OUT = R46_EXPERIMENT_ROOT / "results" / "capability_eval"

R46_MODEL_LABEL = "R46_a025_corner_finetune"
R46_DATASET_R39 = "R39_shape_val_unseen"
R46_DATASET_R40 = "R40_micro_val_unseen"


def _round4(v):
    if v is None:
        return None
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return round(float(v), 4)


def _avg(xs):
    xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
    return sum(xs) / len(xs) if xs else None


def collect_r46_dataset(*, profile_dir: Path, recon_root: Path, dataset_label: str) -> list[dict]:
    rows: list[dict] = []
    manifest = json.loads((profile_dir / "manifest.json").read_text(encoding="utf-8"))
    pairs = manifest["pairs"]
    print(f"  [{R46_MODEL_LABEL}] {dataset_label} {len(pairs)} pairs ...", flush=True)
    for idx, p in enumerate(pairs):
        if idx % 50 == 0 and idx > 0:
            print(f"    {idx}/{len(pairs)}", flush=True)
        stage = p["stage"]
        inner = base.find_recon_inner_alpha_layout(recon_root, stage)
        if inner is None:
            print(f"    [SKIP] {stage}: no reconstruct_progress dir under {recon_root}")
            continue
        lbl_path = profile_dir / p["package_lbl"]
        pred_path = inner / Path(p["package_lbl"]).name
        if not pred_path.exists():
            print(f"    [SKIP] {pred_path.name} missing")
            continue
        metrics = base.evaluate_pair(lbl_path, pred_path)
        rows.append({
            "model": R46_MODEL_LABEL,
            "dataset": dataset_label,
            "stage": stage,
            "feature_family": p.get("feature_family", stage.replace("stage_", "").split("_", 1)[-1]),
            "frame_id": Path(p["package_lbl"]).stem,
            **metrics,
        })
    return rows


def stage_summary(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["model"], r["dataset"], r["stage"])].append(r)
    keys = ("psnr", "ssim", "high_frequency_retention", "edge_retention",
            "contrast_retention", "boundary_f_score", "shape_error_score",
            "corner_retention", "straight_edge_coverage")
    out = []
    for (model, dataset, stage), grp in sorted(grouped.items()):
        row = {"model": model, "dataset": dataset, "stage": stage, "count": len(grp)}
        for k in keys:
            vals = [r.get(k) for r in grp]
            row[f"avg_{k}"] = _round4(_avg(vals))
        out.append(row)
    return out


def overall_summary(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["model"], r["dataset"])].append(r)
    keys = ("psnr", "ssim", "high_frequency_retention", "edge_retention",
            "contrast_retention", "boundary_f_score", "shape_error_score",
            "corner_retention", "straight_edge_coverage")
    out = []
    for (model, dataset), grp in sorted(grouped.items()):
        row = {"model": model, "dataset": dataset, "count": len(grp)}
        for k in keys:
            vals = [r.get(k) for r in grp]
            row[f"avg_{k}"] = _round4(_avg(vals))
        out.append(row)
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields)
        wr.writeheader()
        wr.writerows(rows)


def merge_with_a025_csv(r46_rows: list[dict], combined_out: Path) -> int:
    """讀 a025 per_pair csv,加上 R46 行,寫合併 csv。"""
    if not A025_PER_PAIR_CSV.exists():
        raise FileNotFoundError(f"a025 per_pair csv not found: {A025_PER_PAIR_CSV}")
    with A025_PER_PAIR_CSV.open("r", encoding="utf-8-sig") as fh:
        a025_rows = list(csv.DictReader(fh))
    all_fields: list[str] = []
    for r in a025_rows + r46_rows:
        for k in r:
            if k not in all_fields:
                all_fields.append(k)
    combined = a025_rows + r46_rows
    combined_out.parent.mkdir(parents=True, exist_ok=True)
    with combined_out.open("w", encoding="utf-8-sig", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=all_fields)
        wr.writeheader()
        for r in combined:
            wr.writerow({k: r.get(k, "") for k in all_fields})
    return len(combined)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R46 capability eval")
    parser.add_argument("--shape-recon-root", type=Path, default=R46_SHAPE_RECON_BASE)
    parser.add_argument("--micro-recon-root", type=Path, default=R46_MICRO_RECON_BASE)
    parser.add_argument("--out", type=Path, default=R46_EVAL_OUT)
    parser.add_argument("--skip-r39", action="store_true")
    parser.add_argument("--skip-r40", action="store_true")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    r46_rows: list[dict] = []

    if not args.skip_r39:
        print(f"[R46 eval] collecting R39 shape_val_unseen from {args.shape_recon_root}")
        r46_rows += collect_r46_dataset(
            profile_dir=R39_VAL_PROFILE,
            recon_root=args.shape_recon_root,
            dataset_label=R46_DATASET_R39,
        )

    if not args.skip_r40:
        print(f"[R46 eval] collecting R40 micro_val_unseen from {args.micro_recon_root}")
        r46_rows += collect_r46_dataset(
            profile_dir=R40_VAL_PROFILE,
            recon_root=args.micro_recon_root,
            dataset_label=R46_DATASET_R40,
        )

    write_csv(args.out / "per_pair_metrics_r46_only.csv", r46_rows)
    print(f"  wrote per_pair_metrics_r46_only.csv ({len(r46_rows)} rows)")

    combined_n = merge_with_a025_csv(r46_rows, args.out / "per_pair_metrics_combined.csv")
    print(f"  wrote per_pair_metrics_combined.csv ({combined_n} rows)")

    stages = stage_summary(r46_rows)
    write_csv(args.out / "stage_summary_r46.csv", stages)
    print(f"  wrote stage_summary_r46.csv ({len(stages)} rows)")

    overall = overall_summary(r46_rows)
    write_csv(args.out / "overall_summary_r46.csv", overall)
    print(f"  wrote overall_summary_r46.csv ({len(overall)} rows)")

    print(f"\n[R46 eval] done -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
