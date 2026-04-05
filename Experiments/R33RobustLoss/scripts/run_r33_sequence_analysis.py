"""
Run sequence analysis on R33 reconstruction outputs and compare with R30 baseline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "AnalysisLab" / "r26" / "sequence" / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "AnalysisLab" / "r26" / "sequence" / "configs"))

from dataset_config import DatasetConfig
import run_sequence_analysis as seq

_INPUT_ROOT = Path(r"C:\Users\Rio\Downloads\NTU_ImageDataset")
_R33_RECON_ROOT = (
    _REPO_ROOT
    / "Experiments" / "R33RobustLoss" / "results"
    / "reconstruct_progress_best_tradeoff_in_Cropped_Output_20260405_073906"
)
_GMF_ROOT = Path(
    r"D:\GMM_2_Final\Traing_Progress\organized_20260316"
    r"\external_compare_r18_r22_r25_r26\r26_sm035\gmf_results\raw"
)

R33_DATASETS = [
    DatasetConfig(
        name="Pitch1um_Y_100",
        short_name="pitch1um_y_100",
        input_dir=_INPUT_ROOT / "Pitch1um_Y_100" / "Cropped_Output",
        recon_dir=_R33_RECON_ROOT / "pitch1um_y_100_odd",
        expected_step_px=8.0,
        gmf_score_path=_GMF_ROOT / "pitch8px" / "GMF_score.txt",
        gmf_baseline_step_std=0.205193,
    ),
    DatasetConfig(
        name="Pitch0.1um_Y_60",
        short_name="pitch0p1um_y_60",
        input_dir=_INPUT_ROOT / "Pitch0.1um_Y_60" / "Cropped_Output",
        recon_dir=_R33_RECON_ROOT / "pitch0p1um_y_60_odd",
        expected_step_px=0.8,
        gmf_score_path=_GMF_ROOT / "pitch0p8px" / "GMF_score.txt",
        gmf_baseline_step_std=0.167862,
    ),
    DatasetConfig(
        name="Pitch0.01um_Y_40",
        short_name="pitch0p01um_y_40",
        input_dir=_INPUT_ROOT / "Pitch0.01um_Y_40" / "Cropped_Output",
        recon_dir=_R33_RECON_ROOT / "pitch0p01um_y_40_odd",
        expected_step_px=0.08,
        gmf_score_path=_GMF_ROOT / "pitch0p08px" / "GMF_score.txt",
        gmf_baseline_step_std=0.15772,
    ),
]

OUT_ROOT = _REPO_ROOT / "Experiments" / "R33RobustLoss" / "results" / "sequence_analysis"


def main():
    # Check which recon dirs exist
    available = [d for d in R33_DATASETS if d.recon_dir.exists()]
    if not available:
        print("ERROR: No R33 reconstruction outputs found.")
        return

    print(f"Running sequence analysis on {len(available)} datasets...")
    result = seq.main(datasets=available, out_root=OUT_ROOT, verbose=True)

    # Print comparison with R30 baseline
    r30_cross = _REPO_ROOT / "AnalysisLab" / "r26" / "sequence" / "results" / "cross_dataset" / "cross_dataset_comparison.json"
    if r30_cross.exists():
        with open(r30_cross) as f:
            r30_data = json.load(f)
        r30_datasets = r30_data.get("datasets", r30_data)
        print("\n" + "=" * 70)
        print("COMPARISON: R33 vs R30 Baseline")
        print("=" * 70)
        for s in result.get("summaries", []):
            sn = s["short_name"]
            r30_match = [d for d in r30_datasets if d.get("short_name") == sn]
            if not r30_match:
                continue
            r30 = r30_match[0]
            print(f"\n--- {sn} ---")
            for boundary in ("outer", "inner"):
                r33_imp = s["residual_consistency"][boundary]["improvement_mean_pct"]
                r30_imp = r30["residual_consistency"][boundary]["improvement_mean_pct"]
                r33_std = s["residual_consistency"][boundary]["output_mean"]
                r30_std = r30["residual_consistency"][boundary]["output_mean"]
                delta_imp = r33_imp - r30_imp
                delta_std = r33_std - r30_std
                print(f"  {boundary}: residual_std R33={r33_std:.4f} R30={r30_std:.4f} (delta={delta_std:+.4f})")
                print(f"  {boundary}: improvement  R33={r33_imp:.2f}% R30={r30_imp:.2f}% (delta={delta_imp:+.2f}pp)")
            r33_step = s["step_stability"]["output"]["internal_step_std_y"]
            r30_step = r30["step_stability"]["output"]["internal_step_std_y"]
            print(f"  step_std_y: R33={r33_step:.4f} R30={r30_step:.4f} (delta={r33_step - r30_step:+.4f})")


if __name__ == "__main__":
    main()
