"""Summarize R39 reconstruction folders against the held-out labels."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_REPO_ROOT / "Model"))

from r39_shape_data import DEFAULT_OUTPUT_ROOT, PROFILES
from run_r39_shape_recon import DEFAULT_RECON_ROOT

from GeoEdgeAlignSR_v1_Infer_v5_NoCoord_return_v2_SimpleTest import (
    compute_psnr,
    compute_ssim,
    normalize_to_01,
    read_image_keep_dtype,
)


def _load_manifest(profile_dir: Path) -> dict:
    manifest_path = profile_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing data package manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _latest_stage_output(recon_root: Path, profile: str, stage: str) -> Path:
    candidates: list[Path] = []
    for run_dir in recon_root.glob(f"reconstruct_progress_*_in_{stage}_*"):
        if not run_dir.is_dir():
            continue
        for child in run_dir.iterdir():
            if child.is_dir() and child.name.startswith(f"{profile}_{stage}_"):
                candidates.append(child)
    if not candidates:
        raise FileNotFoundError(f"no reconstruction output found for {profile}/{stage}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _read01(path: Path):
    raw, dtype = read_image_keep_dtype(path)
    return normalize_to_01(raw, dtype)


def summarize(profile: str, data_root: Path, recon_root: Path) -> dict:
    profile_dir = data_root / profile
    manifest = _load_manifest(profile_dir)
    stages = [stage for stage in manifest["count_by_stage"] if stage != "ring"]

    stage_results = []
    total_count = 0
    total_psnr = 0.0
    total_ssim = 0.0

    for stage in stages:
        out_dir = _latest_stage_output(recon_root, profile, stage)
        gt_dir = profile_dir / "lbl" / stage
        gt_paths = sorted(p for p in gt_dir.iterdir() if p.is_file())
        psnr_sum = 0.0
        ssim_sum = 0.0
        count = 0
        missing = []
        for gt_path in gt_paths:
            pred_path = out_dir / gt_path.name
            if not pred_path.exists():
                missing.append(gt_path.name)
                continue
            pred01 = _read01(pred_path)
            gt01 = _read01(gt_path)
            if pred01.shape != gt01.shape:
                raise RuntimeError(f"shape mismatch for {stage}/{gt_path.name}: pred={pred01.shape}, gt={gt01.shape}")
            psnr_sum += compute_psnr(pred01, gt01)
            ssim_sum += compute_ssim(pred01, gt01)
            count += 1
        if missing:
            raise FileNotFoundError(f"{stage} missing reconstructions: {missing[:5]}")
        if count == 0:
            raise RuntimeError(f"{stage} produced no comparable reconstructions")

        avg_psnr = psnr_sum / count
        avg_ssim = ssim_sum / count
        stage_results.append(
            {
                "stage": stage,
                "count": count,
                "avg_psnr": avg_psnr,
                "avg_ssim": avg_ssim,
                "output_dir": str(out_dir),
            }
        )
        total_count += count
        total_psnr += psnr_sum
        total_ssim += ssim_sum

    return {
        "profile": profile,
        "data_root": str(data_root.resolve()),
        "recon_root": str(recon_root.resolve()),
        "total_count": total_count,
        "overall_avg_psnr": total_psnr / total_count,
        "overall_avg_ssim": total_ssim / total_count,
        "stages": stage_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize R39 shape reconstruction metrics.")
    parser.add_argument("--profile", default="shape_val_unseen", choices=sorted(PROFILES))
    parser.add_argument("--data-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--recon-root", type=Path, default=DEFAULT_RECON_ROOT)
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_RECON_ROOT / "shape_val_unseen_combo_baseline_summary.json",
    )
    args = parser.parse_args(argv)

    summary = summarize(args.profile, args.data_root, args.recon_root)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"[R39] summary written to {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
