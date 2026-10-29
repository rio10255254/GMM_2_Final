"""Batch run: 4 ablation x 3 pitch inference + 720-angle analysis.

Per ablation:
  Step 1: inference on 3 r26 sequences -> recon BMP under
          Thesis_MOSR_Evidence/method_ablations/_ablation_recon/<TAG>/<pitch>/...
  Step 2: invoke Analyses/AnalysisLab/r26/sequence runner with custom DatasetConfig list
          pointing at the new recon, output to
          Thesis_MOSR_Evidence/method_ablations/_ablation_720angle/<TAG>/

Usage:
    # full run (all 4 ablations x 3 pitches)
    python run_ablation_inference_and_720angle.py

    # one ablation only (for testing)
    python run_ablation_inference_and_720angle.py --tag NO_SEQ

    # one ablation + one pitch only (for fastest test)
    python run_ablation_inference_and_720angle.py --tag NO_SEQ --pitch pitch1um_y_100
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INPUT_ROOT = Path(r"C:/Users/Rio/Downloads/NTU_ImageDataset")

RECON_OUT_ROOT = REPO_ROOT / "Thesis_MOSR_Evidence" / "method_ablations" / "_ablation_recon"
SEQ_OUT_ROOT = REPO_ROOT / "Thesis_MOSR_Evidence" / "method_ablations" / "_ablation_720angle"

ABLATIONS = {
    "NO_SEQ":  "Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r38v2_8px_gate_p95_ABLA_NO_SEQ_20260526_230916",
    "NO_EQ":   "Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r38v2_8px_gate_p95_ABLA_NO_EQ_20260526_235037",
    "NO_EDGE": "Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r38v2_8px_gate_p95_ABLA_NO_EDGE_20260527_003614",
    "NO_FREQ": "Traing_Progress/training_progress_GESR_v1_v5_ST0p8_SWP_r38v2_8px_gate_p95_ABLA_NO_FREQ_20260527_012452",
}

PITCHES = [
    {"folder": "Pitch1um_Y_100",  "short": "pitch1um_y_100",  "expected_step": 8.0,  "gmf_label": "8px"},
    {"folder": "Pitch0.1um_Y_60", "short": "pitch0p1um_y_60", "expected_step": 0.8,  "gmf_label": "0p8px"},
    {"folder": "Pitch0.01um_Y_40","short": "pitch0p01um_y_40","expected_step": 0.08, "gmf_label": "0p08px"},
]

INFER_SCRIPT = REPO_ROOT / "Model" / "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py"


def find_ckpt(tag: str) -> Path | None:
    sub = ABLATIONS.get(tag)
    if not sub:
        return None
    ckpt = REPO_ROOT / sub / "weights" / "best_tradeoff.pth.tar"
    return ckpt if ckpt.exists() else None


def run_inference(tag: str, ckpt: Path, pitch: dict, device: str) -> Path | None:
    """Run inference and return the resulting recon dir."""
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
    # find actual recon dir (inference may add timestamp prefix/suffix)
    candidates = sorted(recon_root.rglob("*.bmp"))
    if not candidates:
        print(f"  [WARN] no BMP found under {recon_root}")
        return None
    # Use parent of first BMP as the recon dir (input is folder of BMPs)
    return candidates[0].parent


def import_sequence_runner():
    """Import Analyses/AnalysisLab/r26/sequence runner + DatasetConfig dynamically."""
    seq_dir = REPO_ROOT / "Analyses" / "AnalysisLab" / "r26" / "sequence" / "scripts"
    cfg_dir = REPO_ROOT / "Analyses" / "AnalysisLab" / "r26" / "sequence" / "configs"
    sys.path.insert(0, str(cfg_dir))
    sys.path.insert(0, str(seq_dir))
    # also single_image for shared helpers
    si_dir = REPO_ROOT / "Analyses" / "AnalysisLab" / "r26" / "single_image" / "scripts"
    sys.path.insert(0, str(si_dir))

    from dataset_config import DatasetConfig
    spec = importlib.util.spec_from_file_location(
        "run_seq_analysis", seq_dir / "run_sequence_analysis.py"
    )
    seq_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seq_mod)
    return seq_mod, DatasetConfig


def run_720angle_for_ablation(tag: str, recon_dirs: dict[str, Path]) -> Path:
    """Invoke r26 sequence runner with custom dataset list for this ablation."""
    seq_mod, DatasetConfig = import_sequence_runner()
    out_root = SEQ_OUT_ROOT / tag
    out_root.mkdir(parents=True, exist_ok=True)

    datasets = []
    for pitch in PITCHES:
        if pitch["short"] not in recon_dirs:
            print(f"  [SKIP] no recon dir for {pitch['short']}")
            continue
        input_dir = INPUT_ROOT / pitch["folder"] / "Cropped_Output"
        datasets.append(DatasetConfig(
            name=pitch["folder"].replace("Pitch", "Pitch").replace("_", " "),
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


def process_ablation(tag: str, device: str, only_pitch: str | None = None):
    ckpt = find_ckpt(tag)
    if ckpt is None:
        print(f"\n[{tag}] ckpt not found, skipping")
        return
    print(f"\n{'='*70}\n[{tag}] ckpt: {ckpt}\n{'='*70}")
    recon_dirs: dict[str, Path] = {}
    for pitch in PITCHES:
        if only_pitch and pitch["short"] != only_pitch:
            continue
        recon_dir = run_inference(tag, ckpt, pitch, device)
        if recon_dir:
            recon_dirs[pitch["short"]] = recon_dir
    if recon_dirs:
        run_720angle_for_ablation(tag, recon_dirs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", choices=list(ABLATIONS) + ["ALL"], default="ALL")
    parser.add_argument("--pitch", default=None,
                        choices=[p["short"] for p in PITCHES] + [None])
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()

    total_start = time.time()
    tags = list(ABLATIONS) if args.tag == "ALL" else [args.tag]
    for tag in tags:
        process_ablation(tag, args.device, args.pitch)
    print(f"\n{'='*70}")
    print(f"All done in {(time.time()-total_start)/60:.1f} min")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
