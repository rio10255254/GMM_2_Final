"""Collect and validate completed R63 training runs into one manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import torch


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = EXPERIMENT_ROOT / "results" / "training_runs"
TABLE_ROOT = EXPERIMENT_ROOT / "results" / "tables"
EXCLUSION_PATH = EXPERIMENT_ROOT / "results" / "excluded_training_runs.json"
EXPECTED_VARIANTS = (
    "full_control",
    "no_geometry_anchor",
    "no_motion_consistency",
    "no_geometry_no_motion",
    "no_shape_geometry",
    "no_global_boundary_position",
    "no_identity_boundary_guard",
    "no_region_boundary_teacher",
    "no_sequence_consistency",
    "no_known_shift_motion",
    "no_shift_equivariance",
    "no_boundary_residual_adapter",
    "no_raw_position_anchor",
    "no_quality_gate",
    "shift_safe_matched",
    "standard_upsample_matched",
)
EXPECTED_SEEDS = (1261200, 1261217)


def excluded_run_names() -> set[str]:
    if not EXCLUSION_PATH.is_file():
        return set()
    payload = json.loads(EXCLUSION_PATH.read_text(encoding="utf-8"))
    return {str(name) for name in payload.get("excluded_run_names", [])}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def select_completed_run(variant: str, seed: int, epochs: int) -> Path | None:
    excluded = excluded_run_names()
    candidates = sorted(
        (
            path
            for path in RUN_ROOT.glob(f"training_progress_R63_MOSR_{variant}_s{seed}_*")
            if path.name not in excluded
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    required = f"epoch_{epochs:03d}.pth.tar"
    return next((path for path in candidates if (path / required).is_file()), None)


def checkpoint_for(variant: str, seed: int, epochs: int) -> tuple[str, Path, Path]:
    """Select the best checkpoint across the complete 1..budget trajectory.

    A 40-to-60 continuation is written to a new run directory. Its monitor
    reference is locked to the source run by the launcher, so tradeoff scores
    remain comparable and the original 1..40 best must remain eligible.
    """

    candidates: list[tuple[float, int, Path, Path]] = []
    excluded = excluded_run_names()
    runs = sorted(
        (
            path
            for path in RUN_ROOT.glob(f"training_progress_R63_MOSR_{variant}_s{seed}_*")
            if path.name not in excluded
        ),
        key=lambda path: path.stat().st_mtime,
    )
    for candidate_run in runs:
        has_40 = (candidate_run / "epoch_040.pth.tar").is_file()
        has_budget = (candidate_run / f"epoch_{epochs:03d}.pth.tar").is_file()
        if epochs <= 40:
            eligible_run = has_budget
        else:
            eligible_run = has_40 or has_budget
        if not eligible_run:
            continue
        for checkpoint in (
            candidate_run / "weights" / "best_tradeoff.pth.tar",
            candidate_run / "best_tradeoff.pth.tar",
        ):
            if not checkpoint.is_file():
                continue
            payload = torch.load(checkpoint, map_location="cpu")
            selected_epoch = int(payload.get("epoch", -1))
            score = float(payload.get("tradeoff_score", float("nan")))
            if 0 <= selected_epoch <= epochs and score == score:
                candidates.append((score, -selected_epoch, checkpoint, candidate_run))
                break
    if candidates:
        score, _negative_epoch, checkpoint, selected_run = max(candidates, key=lambda item: (item[0], item[1]))
        _ = score
        return "best_tradeoff_global_budget", checkpoint, selected_run

    completion_run = select_completed_run(variant, seed, epochs)
    if completion_run is None:
        raise FileNotFoundError(f"No completed run for {variant}/seed{seed}/epoch{epochs}")
    final_epoch = completion_run / f"epoch_{epochs:03d}.pth.tar"
    if final_epoch.is_file():
        return "final_epoch", final_epoch, completion_run
    raise FileNotFoundError(f"No usable checkpoint for {variant}/seed{seed}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    config_root = EXPERIMENT_ROOT / "results" / "config_snapshots"
    records: list[dict[str, object]] = []
    missing: list[str] = []
    psf_hashes: set[str] = set()
    split_paths: set[str] = set()
    base_hashes: set[str] = set()

    for seed in EXPECTED_SEEDS:
        for variant in EXPECTED_VARIANTS:
            run = select_completed_run(variant, seed, args.epochs)
            if run is None:
                missing.append(f"{variant}/seed{seed}")
                continue
            meta = json.loads((run / "run_meta.json").read_text(encoding="utf-8"))
            config_path = config_root / f"{variant}_seed{seed}.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            checkpoint_role, checkpoint, checkpoint_run = checkpoint_for(variant, seed, args.epochs)
            checkpoint_payload = torch.load(checkpoint, map_location="cpu")
            psf_path = Path(config["config"]["PSF_FITTED_PATH"])
            split_path = Path(config["config"]["FIXED_SPLIT_DIR"])
            base_path = Path(config["setup"]["base_checkpoint"])
            psf_hash = sha256(psf_path)
            base_hash = sha256(base_path)
            psf_hashes.add(psf_hash)
            base_hashes.add(base_hash)
            split_paths.add(str(split_path.resolve()).lower())
            records.append(
                {
                    "variant": variant,
                    "seed": seed,
                    "epochs": args.epochs,
                    "run_dir": str(checkpoint_run.resolve()),
                    "completion_run_dir": str(run.resolve()),
                    "checkpoint_role": checkpoint_role,
                    "checkpoint": str(checkpoint.resolve()),
                    "checkpoint_sha256": sha256(checkpoint),
                    "selected_epoch": int(checkpoint_payload.get("epoch", -1)),
                    "tradeoff_score": float(checkpoint_payload.get("tradeoff_score", float("nan"))),
                    "best_val_rec": float(checkpoint_payload.get("best_val_rec", float("nan"))),
                    "psf_sha256": psf_hash,
                    "base_checkpoint_sha256": base_hash,
                    "fixed_split": str(split_path.resolve()),
                    "standard_upsample": bool(config["standard_upsample"]),
                    "cuda_deterministic": bool(meta["cudnn_deterministic"]),
                    "tf32_matmul": bool(meta["tf32_matmul"]),
                    "tf32_cudnn": bool(meta["tf32_cudnn"]),
                }
            )

    if len(psf_hashes) > 1:
        raise RuntimeError(f"PSF mismatch across runs: {sorted(psf_hashes)}")
    if len(base_hashes) > 1:
        raise RuntimeError("Starting checkpoint mismatch across runs")
    if len(split_paths) > 1:
        raise RuntimeError(f"Fixed split mismatch across runs: {sorted(split_paths)}")

    TABLE_ROOT.mkdir(parents=True, exist_ok=True)
    csv_path = TABLE_ROOT / "training_runs.csv"
    if records:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    manifest = {
        "round": "R63",
        "complete": not missing,
        "expected_run_count": len(EXPECTED_VARIANTS) * len(EXPECTED_SEEDS),
        "completed_run_count": len(records),
        "missing": missing,
        "psf_sha256": next(iter(psf_hashes), ""),
        "base_checkpoint_sha256": next(iter(base_hashes), ""),
        "fixed_split": next(iter(split_paths), ""),
        "records": records,
    }
    manifest_path = EXPERIMENT_ROOT / "results" / "training_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("complete", "completed_run_count", "missing")}, indent=2))
    print(manifest_path)
    if args.require_complete and missing:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
