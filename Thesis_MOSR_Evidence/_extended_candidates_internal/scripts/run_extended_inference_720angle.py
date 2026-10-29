"""Batch run: 5 extended candidates x 3 pitch inference + 720-angle.

Extended candidates (those without prior 720-angle analysis):
  a030, a025, R40_a045, R42_r41best, R46

This mirrors run_ablation_inference_and_720angle.py but with explicit
full checkpoint paths (since extended candidates' ckpts live across
many experiment subdirs, not under Traing_Progress/...weights/).

Output:
  recon BMP    -> Thesis_MOSR_Evidence/_extended_candidates_internal/_recon/<TAG>/<pitch>/...
  720-angle    -> Thesis_MOSR_Evidence/_extended_candidates_internal/_720angle/<TAG>/<pitch>/...

Usage:
    python run_extended_inference_720angle.py            # all 5 candidates
    python run_extended_inference_720angle.py --tag a030 # one only
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
INPUT_ROOT = Path(r"C:/Users/Rio/Downloads/NTU_ImageDataset")

WORK_ROOT = REPO_ROOT / "Thesis_MOSR_Evidence" / "_extended_candidates_internal"
RECON_OUT_ROOT = WORK_ROOT / "_recon"
SEQ_OUT_ROOT = WORK_ROOT / "_720angle"

# (TAG, full ckpt path)
CANDIDATES = {
    "a030": REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/weight_sweep/checkpoints/a030/best_tradeoff.pth.tar",
    "a025": REPO_ROOT / "Experiments/R39_ShapeGeneralization/results/a030_x_a043_sweep/checkpoints/a025/best_tradeoff.pth.tar",
    "R40_a045": REPO_ROOT / "Experiments/R40_MicroscopyFeatureCoverage/results/weight_sweep/combo_best_low_alpha/checkpoints/a045/best_tradeoff.pth.tar",
    "R42_r41best": REPO_ROOT / "Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r42_boundary_from_r41_20260505_145229/weights/best_tradeoff.pth.tar",
    "R46": REPO_ROOT / "Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r46_a025_corner_finetune_20260514_230359/weights/best_tradeoff.pth.tar",
}

PITCHES = [
    {"folder": "Pitch1um_Y_100",   "short": "pitch1um_y_100",   "expected_step": 8.0,  "gmf_label": "8px"},
    {"folder": "Pitch0.1um_Y_60",  "short": "pitch0p1um_y_60",  "expected_step": 0.8,  "gmf_label": "0p8px"},
    {"folder": "Pitch0.01um_Y_40", "short": "pitch0p01um_y_40", "expected_step": 0.08, "gmf_label": "0p08px"},
]

INFER_SCRIPT = REPO_ROOT / "Model" / "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"


def run_inference(tag: str, ckpt: Path, pitch: dict, device: str) -> Path | None:
    input_dir = INPUT_ROOT / pitch["folder"] / "Cropped_Output"
    if not input_dir.exists():
        print(f"  [ERR] input dir missing: {input_dir}")
        return None
    recon_root = RECON_OUT_ROOT / tag
    recon_root.mkdir(parents=True, exist_ok=True)
    output_name = f"{pitch['short']}_odd"
    print(f"  [INFER] {tag} / {pitch['short']}  -> recon dir leaf: {output_name}")
    t0 = time.time()
    cmd = [
        sys.executable, str(INFER_SCRIPT),
        "--weights", str(ckpt),
        "--input-dir", str(input_dir),
        "--recon-root", str(recon_root),
        "--output-name", output_name,
        "--device", device,
        "--select-mode", "odd",
    ]
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"  [FAIL] inference returned {result.returncode}")
        return None
    print(f"  [OK] {tag}/{pitch['short']} inference in {elapsed:.1f}s")
    candidates = sorted(recon_root.rglob("*.bmp"))
    if not candidates:
        print(f"  [WARN] no BMP found under {recon_root}")
        return None
    return candidates[0].parent


def import_sequence_runner():
    seq_dir = REPO_ROOT / "Analyses" / "AnalysisLab" / "r26" / "sequence" / "scripts"
    cfg_dir = REPO_ROOT / "Analyses" / "AnalysisLab" / "r26" / "sequence" / "configs"
    sys.path.insert(0, str(cfg_dir))
    sys.path.insert(0, str(seq_dir))
    si_dir = REPO_ROOT / "Analyses" / "AnalysisLab" / "r26" / "single_image" / "scripts"
    sys.path.insert(0, str(si_dir))

    from dataset_config import DatasetConfig
    spec = importlib.util.spec_from_file_location(
        "run_seq_analysis", seq_dir / "run_sequence_analysis.py"
    )
    seq_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seq_mod)
    return seq_mod, DatasetConfig


def run_720angle(tag: str, recon_dirs: dict[str, Path]) -> Path:
    seq_mod, DatasetConfig = import_sequence_runner()
    out_root = SEQ_OUT_ROOT / tag
    out_root.mkdir(parents=True, exist_ok=True)

    datasets = []
    for pitch in PITCHES:
        if pitch["short"] not in recon_dirs:
            continue
        input_dir = INPUT_ROOT / pitch["folder"] / "Cropped_Output"
        datasets.append(DatasetConfig(
            name=pitch["folder"],
            short_name=pitch["short"],
            input_dir=input_dir,
            recon_dir=recon_dirs[pitch["short"]],
            expected_step_px=pitch["expected_step"],
            gmf_score_path=None,
            gmf_baseline_step_std=None,
        ))

    if not datasets:
        print(f"  [SKIP] no datasets to analyze for {tag}")
        return out_root
    print(f"  [720ANGLE] {tag}: {len(datasets)} datasets -> {out_root}")
    seq_mod.main(datasets=datasets, out_root=out_root, verbose=False)
    return out_root


def process(tag: str, device: str):
    ckpt = CANDIDATES.get(tag)
    if ckpt is None or not ckpt.exists():
        print(f"\n[{tag}] ckpt not found, skipping  ({ckpt})")
        return
    print(f"\n{'='*70}\n[{tag}] ckpt: {ckpt}\n{'='*70}")
    recon_dirs: dict[str, Path] = {}
    for pitch in PITCHES:
        recon_dir = run_inference(tag, ckpt, pitch, device)
        if recon_dir:
            recon_dirs[pitch["short"]] = recon_dir
    if recon_dirs:
        run_720angle(tag, recon_dirs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", choices=list(CANDIDATES) + ["ALL"], default="ALL")
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()

    total_start = time.time()
    tags = list(CANDIDATES) if args.tag == "ALL" else [args.tag]
    for tag in tags:
        process(tag, args.device)
    print(f"\n{'='*70}")
    print(f"All done in {(time.time()-total_start)/60:.1f} min")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
