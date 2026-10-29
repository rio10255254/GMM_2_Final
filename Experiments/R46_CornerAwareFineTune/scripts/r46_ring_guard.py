"""R46 本地三尺度環形守門:對 R46 checkpoint 跑 NTU_ImageDataset 三個 pitch
重建,然後用 720-angle 分析算 step_std,看是否仍在 3% 上限內。

階段:
1. Ring 重建:對 Pitch1um_Y_100、Pitch0.1um_Y_60、Pitch0.01um_Y_40 三個 pitch
   跑 R46 inference,輸出 layout 對齊 R39 weight sweep 既有結構
2. 720-angle 分析:呼叫 Analyses/AnalysisLab/r26/sequence/scripts 算 step_std

輸出:
- results/ring_recon/r46/reconstruct_progress_best_tradeoff_in_Cropped_Output_<timestamp>/
- results/ring_guard/r46_ring_guard_summary.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
R39_SCRIPT_DIR = REPO_ROOT / "Experiments" / "R39_ShapeGeneralization" / "scripts"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(R39_SCRIPT_DIR))
sys.path.insert(0, str(REPO_ROOT / "Model"))


NTU_INPUT_ROOT = Path(r"C:\Users\Rio\Downloads\NTU_ImageDataset")

R46_RING_RECON_BASE = (
    REPO_ROOT / "Experiments" / "R46_CornerAwareFineTune"
    / "results" / "ring_recon"
)
R46_RING_RECON_CANDIDATE_DIR = R46_RING_RECON_BASE / "r46"
R46_ANALYSIS_ROOT = (
    REPO_ROOT / "Experiments" / "R46_CornerAwareFineTune"
    / "results" / "ring_guard"
)

# Pitch metadata 跟 run_r39_ring_guard.RING_SPECS 一致
PITCHES = [
    ("Pitch1um_Y_100", "pitch1um_y_100_odd", 8.0, 0.154515),
    ("Pitch0.1um_Y_60", "pitch0p1um_y_60_odd", 0.8, 0.131560),
    ("Pitch0.01um_Y_40", "pitch0p01um_y_40_odd", 0.08, 0.099891),
]


def run_recon_one_pitch(
    weights: Path,
    input_dir: Path,
    recon_root: Path,
    output_name: str,
    device: str,
) -> None:
    """對單一 pitch 跑 R46 inference,layout 對齊 a000 / a025 sweep 既有。"""
    import GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest as infer

    infer.MANUAL_SELECT_MODE = None
    infer.MANUAL_WEIGHTS_PATH = None
    sys.argv = [
        "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py",
        "--weights", str(weights),
        "--input-dir", str(input_dir),
        "--recon-root", str(recon_root),
        "--output-name", output_name,
        "--device", device,
        "--select-mode", "odd",
    ]
    infer.main()


def do_recon(weights: Path, device: str) -> Path:
    """跑三個 pitch 的重建,回傳 reconstruct_progress 目錄路徑。"""
    R46_RING_RECON_CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    for pitch_dir, output_name, expected_step, _ in PITCHES:
        input_dir = NTU_INPUT_ROOT / pitch_dir / "Cropped_Output"
        if not input_dir.exists():
            raise FileNotFoundError(f"input missing: {input_dir}")
        print(f"\n[RECON] {pitch_dir} -> {output_name}", flush=True)
        run_recon_one_pitch(
            weights=weights,
            input_dir=input_dir,
            recon_root=R46_RING_RECON_CANDIDATE_DIR,
            output_name=output_name,
            device=device,
        )

    # 找最新的 reconstruct_progress 目錄
    runs = sorted(R46_RING_RECON_CANDIDATE_DIR.glob("reconstruct_progress_*"),
                  key=lambda p: p.name)
    if not runs:
        raise RuntimeError("no reconstruct_progress directory produced")
    return runs[-1]


def run_720_analysis(recon_run: Path) -> dict:
    """呼叫 run_r39_ring_guard 內的函式跑 720-angle 分析。"""
    import run_r39_ring_guard as rg

    datasets = rg.build_ring_datasets(
        candidate="r46",
        recon_root=R46_RING_RECON_BASE,
    )
    R46_ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
    candidate_out = R46_ANALYSIS_ROOT / "r46_sequence_analysis"
    import run_sequence_analysis as seq
    result = seq.main(datasets=datasets, out_root=candidate_out, verbose=True)
    compact = rg.make_compact_summary(
        candidate="r46",
        result=result,
    )
    summary_json = R46_ANALYSIS_ROOT / "r46_ring_guard_summary.json"
    summary_json.write_text(json.dumps(compact, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    print(f"\n[ring guard] summary written to {summary_json}")
    return compact


def evaluate_against_thresholds(compact: dict) -> dict:
    """判定三尺度 step_std 是否通過 3% 上限門檻。

    用 COMBO internal step_std(720-angle 算的)當 baseline,因為 R46 也是
    internal step_std,external GMF 數字需要外部 GMF tool 才算得出來。
    """
    verdicts = []
    for row in compact.get("datasets", []):
        short = row["short_name"]
        r46_step = row.get("r39_internal_step_std_y")  # key 沿用 r39 命名
        combo_step_baseline = row.get("combo_internal_step_std_y")
        passed = None
        delta_pct = None
        thr_3pct = None
        if r46_step is not None and combo_step_baseline is not None:
            thr_3pct = combo_step_baseline * 1.03
            delta_pct = (r46_step - combo_step_baseline) / combo_step_baseline * 100
            passed = r46_step <= thr_3pct
        verdicts.append({
            "short_name": short,
            "r46_internal_step_std": r46_step,
            "combo_internal_step_std": combo_step_baseline,
            "delta_pct_vs_combo": delta_pct,
            "threshold_3pct": thr_3pct,
            "passed_3pct_gate": passed,
            "formal_combo_external_step_std": row.get("formal_combo_external_step_std"),
        })
    passed_flags = [v.get("passed_3pct_gate") for v in verdicts]
    all_pass = all(p is True for p in passed_flags) if passed_flags else False
    return {
        "rows": verdicts,
        "all_pass_3pct_gate": all_pass,
        "n_passed": sum(1 for p in passed_flags if p is True),
        "n_total": len(passed_flags),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R46 local ring guard")
    parser.add_argument("--weights", type=Path, required=True,
                        help="R46 best_tradeoff.pth.tar path")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--skip-recon", action="store_true",
                        help="若 ring 重建已產出,跳過直接跑分析")
    args = parser.parse_args(argv)

    weights = args.weights.resolve()
    if not weights.exists():
        raise FileNotFoundError(weights)

    print(f"[R46 ring guard] weights = {weights}", flush=True)
    print(f"[R46 ring guard] device = {args.device}", flush=True)

    if not args.skip_recon:
        print(f"\n=== Step 1: ring reconstruction ({len(PITCHES)} pitches) ===")
        recon_run = do_recon(weights, args.device)
        print(f"  reconstruction dir = {recon_run}")

    print(f"\n=== Step 2: 720-angle analysis ===")
    compact = run_720_analysis(R46_RING_RECON_CANDIDATE_DIR / "dummy")  # not actually used

    print(f"\n=== Step 3: threshold gate evaluation ===")
    verdict = evaluate_against_thresholds(compact)
    verdict_json = R46_ANALYSIS_ROOT / "r46_ring_guard_verdict.json"
    verdict_json.write_text(json.dumps(verdict, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    print(f"\nverdict -> {verdict_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
