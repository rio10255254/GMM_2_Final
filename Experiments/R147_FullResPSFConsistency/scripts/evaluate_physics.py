"""Frozen synthetic holdout diagnostic for native-grid PSF consistency."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dataset import Bank
from losses import objective
from model import Model
from utils import load, model_config, now, save, setup, sha, train_config
from verify_package import verify_source_lock
from evaluation_lock import verify as verify_evaluation_lock


def main() -> None:
    verify_source_lock()
    verify_evaluation_lock()
    cfg = model_config()
    training = train_config()
    cp_path = ROOT / "runs/formal_8192/checkpoints/step08192.pth"
    complete = load(ROOT / "runs/formal_8192/training_complete.json")
    assert complete["updates"] == 8192 and sha(cp_path) == complete["checkpoint"]["sha256"]
    setup(training["model_seed"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = Model(cfg, ROOT).to(device).eval()
    cp = torch.load(cp_path, map_location="cpu", weights_only=False)
    assert cp["psf_mode"] == cfg["psf_mode"] and cp["selector_trained"] is False
    model.load_state_dict(cp["model"], strict=True)
    bank = Bank(training)
    rows = []
    with torch.inference_mode():
        for index in range(32):
            batch = bank.batch("test", index, device)
            on = model(batch["source"])
            on_loss, _ = objective(on, batch)
            model.optical_enabled = False
            off = model(batch["source"])
            off_loss, _ = objective(off, batch)
            model.optical_enabled = True
            lo, hi = batch["core"]
            difference = float((on-off)[..., lo:hi, lo:hi].square().mean().sqrt()*255)
            rows.append(dict(index=index, parent_id=batch["parent_id"],
                             on_objective=float(on_loss), off_objective=float(off_loss),
                             on_off_core_RMS_gray=difference))
    mean_on = float(np.mean([row["on_objective"] for row in rows]))
    mean_off = float(np.mean([row["off_objective"] for row in rows]))
    median_difference = float(np.median([row["on_off_core_RMS_gray"] for row in rows]))
    assert np.isfinite([mean_on, mean_off, median_difference]).all()
    result = dict(model=cfg["model_name"], psf_mode=cfg["psf_mode"],
                  checkpoint_sha256=sha(cp_path), bank_sha256=cp["bank_sha256"],
                  sampled_test_parents=len(rows), mean_on_objective=mean_on,
                  mean_off_objective=mean_off,
                  median_on_off_core_RMS_gray=median_difference,
                  physical_step_strengths=(cfg["optical_step_max"]*torch.sigmoid(model.optical_step_logits)).detach().cpu().tolist(),
                  note="Frozen-model switch only; no retraining or external ground truth",
                  rows=rows, completed_utc=now())
    save(ROOT / "results/physics_evaluation.json", result)
    print("PHYSICS_EVALUATION", mean_on, mean_off, median_difference, flush=True)


if __name__ == "__main__":
    main()
