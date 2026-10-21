"""時間軸 5 模型重建:對同一張顯微/邊界輸入影像分別跑 R30 / COMBO / a030 / a043 / a025,
輸出 5 張獨立 BMP 加 PSNR / SSIM 摘要,供 a025 簡報時間軸使用。

預設 case 是 R42 boundary defects stage_39 / 0099.bmp(COMBO vs a025 PSNR 差 +6.03 dB,
是 a025 比 COMBO 強最有 punch 的單張 case)。若要換其他 case,用 --staging-dir 指到
含 input/ 跟 gt/ 子資料夾的 staging folder,並用 --case-tag 命名輸出。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = REPO_ROOT / "Model"
sys.path.insert(0, str(MODEL_DIR))

import GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest as infer  # noqa: E402


MODELS = [
    ("R30",   REPO_ROOT / r"Traing_Progress\organized_20260316\round30\archive\runs\training_progress_GESR_v1_v5_ST0p8_SWP_r30b1dir_20260317_152913\weights\best_tradeoff.pth.tar"),
    ("COMBO", REPO_ROOT / r"Traing_Progress\training_progress_GeoEdgeAlignSR_v1_v5_NoCoord_SimpleTest_20260408_003525\weights\best_tradeoff.pth.tar"),
    ("a030",  REPO_ROOT / r"Experiments\R39_ShapeGeneralization\results\weight_sweep\checkpoints\a030\best_tradeoff.pth.tar"),
    ("a043",  REPO_ROOT / r"Experiments\R40_MicroscopyFeatureCoverage\results\weight_sweep\combo_best_low_alpha\checkpoints\a043\best_tradeoff.pth.tar"),
    ("a025",  REPO_ROOT / r"Experiments\R39_ShapeGeneralization\results\a030_x_a043_sweep\checkpoints\a025\best_tradeoff.pth.tar"),
]

SWEEP_ROOT = REPO_ROOT / "Experiments" / "R39_ShapeGeneralization" / "results" / "a030_x_a043_sweep"
DEFAULT_STAGING = SWEEP_ROOT / "timeline_5model_recon_20260513" / "staging_defects_0099"
DEFAULT_CASE_TAG = "defects_0099"


def _psnr(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float64) / 255.0
    b = b.astype(np.float64) / 255.0
    mse = float(np.mean((a - b) ** 2))
    if mse <= 1e-12:
        return float("inf")
    return float(10.0 * np.log10(1.0 / mse))


def _ssim_simple(a: np.ndarray, b: np.ndarray) -> float:
    # Simple single-window SSIM at the image level. Good enough as a sanity number.
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    mu_a, mu_b = a.mean(), b.mean()
    var_a, var_b = a.var(), b.var()
    cov = ((a - mu_a) * (b - mu_b)).mean()
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    return float(((2 * mu_a * mu_b + c1) * (2 * cov + c2)) /
                 ((mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2)))


def _run_one(label: str, weights: Path, recon_root: Path, input_dir: Path, gt_dir: Path) -> Path:
    print(f"\n========== {label} ==========")
    print(f"weights: {weights}")
    recon_root.mkdir(parents=True, exist_ok=True)

    # Make sure module-level manual overrides don't kick in.
    infer.MANUAL_SELECT_MODE = None
    infer.MANUAL_WEIGHTS_PATH = None

    sys.argv = [
        "GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest.py",
        "--weights", str(weights),
        "--input-dir", str(input_dir),
        "--gt-dir", str(gt_dir),
        "--recon-root", str(recon_root),
        "--output-name", label,
        "--device", "cuda:0",
        "--select-mode", "all",
    ]
    t0 = time.time()
    infer.main()
    print(f"-> {label} inference done in {time.time() - t0:.1f}s")

    # The infer module writes BMPs under recon_root/reconstruct_progress_*_in_*/{label}/.
    bmps = sorted(recon_root.rglob("*.bmp"))
    if not bmps:
        raise RuntimeError(f"No BMP produced for {label} under {recon_root}")
    src_bmps = sorted(input_dir.glob("*.bmp"))
    if len(src_bmps) == 1:
        target_name = src_bmps[0].name
        recon_bmp = next((p for p in bmps if p.name == target_name), bmps[0])
    else:
        recon_bmp = bmps[0]
    print(f"-> recon BMP: {recon_bmp}")
    return recon_bmp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-dir", type=Path, default=DEFAULT_STAGING,
                        help="Folder containing input/ and gt/ subfolders, each with the same single BMP filename")
    parser.add_argument("--case-tag", default=DEFAULT_CASE_TAG,
                        help="Slug for this case; used to name output folder under timeline_5model_recon_20260513/")
    args = parser.parse_args()

    staging_dir = Path(args.staging_dir).resolve()
    input_dir = staging_dir / "input"
    gt_dir = staging_dir / "gt"

    src_bmps = sorted(input_dir.glob("*.bmp"))
    if not src_bmps:
        raise FileNotFoundError(f"no BMP in {input_dir}")
    if len(src_bmps) != 1:
        raise RuntimeError(f"expected exactly 1 BMP in {input_dir}, got {len(src_bmps)}")
    inp_path = src_bmps[0]
    gt_path = gt_dir / inp_path.name
    if not gt_path.exists():
        raise FileNotFoundError(f"GT for {inp_path.name} not in {gt_dir}")

    output_root = SWEEP_ROOT / "timeline_5model_recon_20260513" / args.case_tag
    final_dir = output_root / "final_outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    gt = cv2.imread(str(gt_path), cv2.IMREAD_GRAYSCALE)
    inp = cv2.imread(str(inp_path), cv2.IMREAD_GRAYSCALE)

    summary = {
        "case_tag": args.case_tag,
        "gt": str(gt_path),
        "input": str(inp_path),
        "input_psnr_vs_gt": _psnr(inp, gt),
        "input_ssim_vs_gt": _ssim_simple(inp, gt),
        "models": [],
    }

    for label, weights in MODELS:
        weights = weights.resolve()
        if not weights.exists():
            raise FileNotFoundError(f"weights missing for {label}: {weights}")

        recon_root = output_root / label
        recon_bmp = _run_one(label, weights, recon_root, input_dir, gt_dir)

        # Copy / rename into final_outputs/ so the user gets one BMP per model in one folder.
        final_bmp = final_dir / f"{label}.bmp"
        shutil.copyfile(recon_bmp, final_bmp)

        recon = cv2.imread(str(final_bmp), cv2.IMREAD_GRAYSCALE)
        psnr = _psnr(recon, gt)
        ssim = _ssim_simple(recon, gt)
        print(f"-> {label}: PSNR={psnr:.4f}  SSIM={ssim:.4f}")
        summary["models"].append({
            "label": label,
            "weights": str(weights),
            "recon_bmp_internal": str(recon_bmp),
            "recon_bmp_final": str(final_bmp),
            "psnr_vs_gt": psnr,
            "ssim_vs_gt": ssim,
        })

    # Also copy GT and input to final_dir for one-folder convenience.
    shutil.copyfile(gt_path,  final_dir / "_GT.bmp")
    shutil.copyfile(inp_path, final_dir / "_input.bmp")

    summary_path = output_root / "timeline_5model_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nFinal BMPs:    {final_dir}")
    print(f"Summary JSON:  {summary_path}")


if __name__ == "__main__":
    main()
