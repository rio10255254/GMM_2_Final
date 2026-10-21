"""Verify the frozen R143 sources, measured bank, data, and final checkpoint."""
from __future__ import annotations

import argparse

import torch

from utils import ROOT, load, model_config, sha, verify_bank_lock


FROZEN = (
    "model.py", "dataset.py", "train.py", "losses.py", "training_policy.py",
    "utils.py", "infer.py", "verify_package.py", "optical/adaptive_psf.py",
    "config/model.json", "config/train.json", "calibration/measured_psf_bank.npz",
    "calibration/BANK_LOCK.json", "data/manifest.json", "scripts/make_data.py",
    "scripts/preflight.py", "scripts/launch_r144.py", "scripts/install_center9_bank.py",
)


def verify_source_lock() -> dict:
    lock = load(ROOT / "config/SOURCE_LOCK.json")
    if set(lock["files"]) != set(FROZEN):
        raise RuntimeError("Frozen source list changed")
    for rel, expected in lock["files"].items():
        if sha(ROOT / rel) != expected:
            raise RuntimeError("Frozen source changed: " + rel)
    return lock


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("structural", "infer-ready"), default="structural")
    args = p.parse_args()
    lock = verify_source_lock()
    bank_lock = verify_bank_lock()
    cfg = model_config()
    manifest = load(ROOT / "data/manifest.json")
    if len(manifest["entries"]) != 768:
        raise RuntimeError("Dataset manifest does not contain 768 parents")
    if manifest["measured_psf_bank_sha256"] != bank_lock["bank_sha256"]:
        raise RuntimeError("Generated pairs use a different PSF bank")
    checkpoint = ROOT / "runs/formal_8192/checkpoints/step08192.pth"
    trained = checkpoint.is_file()
    if trained:
        cp = torch.load(checkpoint, map_location="cpu", weights_only=False)
        if cp["step"] != 8192 or cp["checkpoint_kind"] != "trained_model":
            raise RuntimeError("Checkpoint is not the completed formal model")
        if cp["bank_sha256"] != bank_lock["bank_sha256"] or cp["model_config"] != cfg:
            raise RuntimeError("Checkpoint bank/model identity mismatch")
        if cp["data_manifest_sha256"] != sha(ROOT / "data/manifest.json"):
            raise RuntimeError("Checkpoint trained on different data")
    if args.mode == "infer-ready" and not trained:
        raise RuntimeError("Full 8192-step checkpoint is not present")
    print(dict(package=cfg["model_name"], frozen_files=len(lock["files"]),
               data_parents=len(manifest["entries"]), bank_count=bank_lock["count"],
               full_training_complete=trained, infer_ready=trained))


if __name__ == "__main__":
    main()
