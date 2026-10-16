"""R46 external GMF comparison wrapper.

複用 R40 的 external compare helper(`r40_external_compare.py`)的 parsing 跟
step_std 計算邏輯,只改 path/baseline 指向 R46。

執行條件:user 已經把三個尺度的 GMF_score.txt 放到對應位置:
- results/external_gmf/pitch8px/GMF_score.txt
- results/external_gmf/pitch0p8px/GMF_score.txt
- results/external_gmf/pitch0p08px/GMF_score.txt

輸出:
- results/external_gmf/external_compare_summary.json
- reports/R46_EXTERNAL_COMPARE.md(human-readable)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
R40_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R40_MicroscopyFeatureCoverage" / "scripts"
sys.path.insert(0, str(R40_SCRIPT_DIR))

import r40_external_compare as base  # noqa: E402


R46_EXTERNAL_DIR = (
    REPO_ROOT / "Experiments" / "R46_CornerAwareFineTune"
    / "results" / "external_gmf"
)
R46_REPORT_MD = (
    REPO_ROOT / "Experiments" / "R46_CornerAwareFineTune"
    / "reports" / "R46_EXTERNAL_COMPARE.md"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R46 external GMF comparison")
    parser.add_argument("--external-dir", type=Path, default=R46_EXTERNAL_DIR)
    parser.add_argument("--summary-json", type=Path,
                        default=R46_EXTERNAL_DIR / "external_compare_summary.json")
    parser.add_argument("--report-md", type=Path, default=R46_REPORT_MD)
    parser.add_argument("--candidate-name", default="R46 a025_corner_finetune")
    args = parser.parse_args(argv)

    print(f"[R46 external compare] reading from {args.external_dir}")
    if not args.external_dir.is_dir():
        print(f"[FAIL] external_gmf dir missing: {args.external_dir}")
        return 1

    results: dict[str, dict] = {}
    missing_scores: list[str] = []
    for scale_name, sub_dir, expected_step_um in base.SCALE_DIRS:
        score_path = args.external_dir / sub_dir / "GMF_score.txt"
        if not score_path.exists():
            missing_scores.append(str(score_path))
            continue
        parsed = base.parse_gmf_score(score_path)
        if not parsed:
            print(f"  [WARN] {sub_dir}: GMF_score.txt parsed empty")
            continue
        pos_y = base.pos_y_series_sorted(parsed)
        stats = base.compute_step_stats(pos_y)
        combo_step = base.COMBO_EXTERNAL_STEP_STD[scale_name]
        r46_step = stats["filtered_std"]
        delta_abs = r46_step - combo_step
        delta_pct = (r46_step - combo_step) / combo_step * 100 if combo_step > 0 else float("nan")
        verdict = "PASS_UPGRADE" if delta_pct <= 3.0 else ("PASS_TRADEOFF_7PCT" if delta_pct <= 7.0 else "FAIL_OUTSIDE_7PCT")
        results[scale_name] = {
            "scale_name": scale_name,
            "expected_step_um": expected_step_um,
            "score_file": str(score_path),
            "n_pos_samples": stats["n_pos_samples"],
            "n_steps": stats["n_steps"],
            "raw_step_std": stats["raw_std"],
            "step_std_kept": r46_step,
            "kept_n": stats["n_steps"] - stats["n_outliers"],
            "median_step": stats["median_step"],
            "n_outliers_removed": stats["n_outliers"],
            "outliers": stats["outliers"],
            "combo_external_step_std": combo_step,
            "delta_vs_combo_abs": delta_abs,
            "delta_vs_combo_pct": delta_pct,
            "verdict_3pct_gate": verdict,
        }
        print(f"  {scale_name}: R46 step_std={r46_step:.6f}, COMBO={combo_step:.6f}, "
              f"Δ={delta_pct:+.2f}% ({verdict})")

    if missing_scores:
        print(f"\n[WARN] {len(missing_scores)} GMF_score.txt files missing:")
        for p in missing_scores:
            print(f"  - {p}")
        print("  -> 放完 GMF_score.txt 後重跑此腳本。")

    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "candidate": args.candidate_name,
        "results": results,
        "missing_scores": missing_scores,
        "all_three_scales_present": len(missing_scores) == 0,
    }
    if len(missing_scores) == 0:
        all_pass_3pct = all(r["verdict_3pct_gate"] == "PASS_UPGRADE" for r in results.values())
        all_pass_7pct = all(r["verdict_3pct_gate"] in ("PASS_UPGRADE", "PASS_TRADEOFF_7PCT")
                            for r in results.values())
        summary["all_pass_3pct_gate"] = all_pass_3pct
        summary["all_within_7pct_tolerance"] = all_pass_7pct
    args.summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                 encoding="utf-8")
    print(f"\n[summary] wrote {args.summary_json}")
    return 0 if len(missing_scores) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
