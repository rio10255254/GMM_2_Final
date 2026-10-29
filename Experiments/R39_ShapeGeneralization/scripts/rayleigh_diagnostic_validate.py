"""Rayleigh diagnostic 驗證腳本:用配對統計檢驗(paired t-test、Wilcoxon)
檢視 a043 vs a025 在各 stage、各 Rayleigh class 上的差距是否統計顯著,
而不是看 mean shift 被少數極端值帶偏。

主要驗證:
1. 前一輪用 per-stage mean delta 看到「a043 在 polygons / lines_grid / large_regions /
   edge_defects 輸給 a025」這個故事——這份檢驗確認那是 noise
2. 前一輪 aggregate 看到「sub-Rayleigh 上 a043 straight_edge_coverage 退 1.91 pp」——
   這份檢驗確認那也是 noise
3. R44G 邊界形狀指標(corner_retention、straight_edge_coverage)在小樣本上的離散性
   特性確認,提醒未來 R46 評估時不能只看 mean

Outputs:
  - paired_tests.csv         逐 (stage / class × metric) 配對檢驗結果
  - revised_expected_gain.csv 用統計顯著的差距加權算 R46 期望增益
  - top_wins_losses.csv      a043 比 a025 PSNR 贏 / 輸最多的 case 排名
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats
PROJECT_ROOT = Path(__file__).resolve().parents[3]


REPO_ROOT = Path(str(PROJECT_ROOT))
DEFAULT_CSV = (
    REPO_ROOT
    / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep"
    / "rayleigh_diagnostic/per_pair_with_width.csv"
)
DEFAULT_OUT = (
    REPO_ROOT
    / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep"
    / "rayleigh_diagnostic/validation"
)

CLASS_WEIGHTS = {"supra": 0.768, "mixed": 0.171, "sub": 0.061}
METRICS = [
    ("psnr", "+"),
    ("ssim", "+"),
    ("boundary_f_score", "+"),
    ("high_frequency_retention", "+"),
    ("edge_retention", "+"),
    ("corner_retention", "+"),
    ("straight_edge_coverage", "+"),
    ("shape_error_score", "-"),
]


def fnum(v) -> float:
    try:
        f = float(v)
        return f if math.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def load_rows(csv_path: Path) -> list[dict]:
    with csv_path.open("r", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_pair_index(rows: list[dict]) -> dict:
    by_key: dict[tuple, dict] = defaultdict(dict)
    for r in rows:
        by_key[(r["dataset"], r["stage"], r["frame_id"])][r["model"]] = r
    return by_key


def paired_tests(by_key: dict, group_key: str, group_values: list[str]) -> list[dict]:
    """For each (group × metric), run paired t-test on a043 vs a025."""
    out = []
    for gv in group_values:
        for col, _ in METRICS:
            deltas = []
            for mdict in by_key.values():
                if "a043" not in mdict or "R39R40_a025" not in mdict:
                    continue
                if mdict["a043"].get(group_key) != gv:
                    continue
                v043 = fnum(mdict["a043"].get(col))
                v025 = fnum(mdict["R39R40_a025"].get(col))
                if math.isfinite(v043) and math.isfinite(v025):
                    deltas.append(v043 - v025)
            arr = np.array(deltas)
            n = len(arr)
            if n < 2:
                continue
            mean_d = float(arr.mean())
            std_d = float(arr.std(ddof=1))
            t_stat, p_t = stats.ttest_1samp(arr, 0)
            # Wilcoxon needs at least 1 non-zero diff
            try:
                w_stat, p_w = stats.wilcoxon(arr) if np.any(arr != 0) else (float("nan"), 1.0)
            except ValueError:
                w_stat, p_w = float("nan"), 1.0
            out.append(
                {
                    group_key: gv,
                    "metric": col,
                    "n": n,
                    "mean_a043_minus_a025": round(mean_d, 6),
                    "std": round(std_d, 6),
                    "t_stat": round(float(t_stat), 4),
                    "t_p_value": float(p_t),
                    "wilcoxon_stat": float(w_stat) if math.isfinite(w_stat) else "",
                    "wilcoxon_p_value": float(p_w),
                    "t_sig_at_05": "yes" if p_t < 0.05 else "no",
                    "wilcoxon_sig_at_05": "yes" if p_w < 0.05 else "no",
                }
            )
    return out


def revised_expected_gain(by_key: dict, weights: dict) -> list[dict]:
    """Per metric, weighted expected gain using only statistically significant class deltas."""
    out = []
    for col, direction in METRICS:
        row = {"metric": col, "direction": direction}
        total_sig = 0.0
        total_naive = 0.0
        for cls, w in weights.items():
            deltas = []
            for mdict in by_key.values():
                if "a043" not in mdict or "R39R40_a025" not in mdict:
                    continue
                if mdict["a043"].get("rayleigh_class") != cls:
                    continue
                v043 = fnum(mdict["a043"].get(col))
                v025 = fnum(mdict["R39R40_a025"].get(col))
                if math.isfinite(v043) and math.isfinite(v025):
                    deltas.append(v043 - v025)
            arr = np.array(deltas)
            if len(arr) < 2:
                continue
            mean_d = float(arr.mean())
            _, p = stats.ttest_1samp(arr, 0)
            credited = mean_d if p < 0.05 else 0.0
            total_sig += w * credited
            total_naive += w * mean_d
            row[f"{cls}_mean"] = round(mean_d, 6)
            row[f"{cls}_p"] = float(p)
            row[f"{cls}_credited"] = round(credited, 6)
            row[f"{cls}_n"] = len(arr)
        row["weighted_sig_only"] = round(total_sig, 6)
        row["weighted_naive_all"] = round(total_naive, 6)
        out.append(row)
    return out


def top_wins_losses(by_key: dict, metric: str = "psnr", top_n: int = 15) -> list[dict]:
    ranked = []
    for k, mdict in by_key.items():
        if "a043" not in mdict or "R39R40_a025" not in mdict:
            continue
        v043 = fnum(mdict["a043"].get(metric))
        v025 = fnum(mdict["R39R40_a025"].get(metric))
        sw = fnum(mdict["a043"].get("sw_median_px"))
        if math.isfinite(v043) and math.isfinite(v025):
            ranked.append(
                {
                    "dataset": k[0],
                    "stage": k[1],
                    "frame_id": k[2],
                    "sw_median_px": round(sw, 4) if math.isfinite(sw) else "",
                    "a043_value": round(v043, 4),
                    "a025_value": round(v025, 4),
                    "delta_a043_minus_a025": round(v043 - v025, 4),
                }
            )
    ranked.sort(key=lambda r: r["delta_a043_minus_a025"], reverse=True)
    out = []
    for r in ranked[:top_n]:
        r["rank_type"] = "top_win"
        out.append(r)
    for r in ranked[-top_n:][::-1]:
        r["rank_type"] = "top_loss"
        out.append(r)
    return out


def write_csv(out_path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields)
        wr.writeheader()
        wr.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows = load_rows(args.csv)
    by_key = build_pair_index(rows)
    print(f"Loaded {len(rows)} rows; {len(by_key)} unique image keys")

    stages = sorted({r["stage"] for r in rows})
    per_stage = paired_tests(by_key, "stage", stages)
    per_class = paired_tests(by_key, "rayleigh_class", ["supra", "mixed", "sub"])
    write_csv(args.out / "paired_tests_per_stage.csv", per_stage)
    write_csv(args.out / "paired_tests_per_class.csv", per_class)
    print(f"  wrote paired_tests_per_stage.csv ({len(per_stage)} rows)")
    print(f"  wrote paired_tests_per_class.csv ({len(per_class)} rows)")

    revised = revised_expected_gain(by_key, CLASS_WEIGHTS)
    write_csv(args.out / "revised_expected_gain.csv", revised)
    print(f"  wrote revised_expected_gain.csv ({len(revised)} rows)")

    twl = top_wins_losses(by_key, metric="psnr", top_n=15)
    write_csv(args.out / "top_wins_losses_psnr.csv", twl)
    print(f"  wrote top_wins_losses_psnr.csv ({len(twl)} rows)")

    print(f"Done -> {args.out}")


if __name__ == "__main__":
    main()
