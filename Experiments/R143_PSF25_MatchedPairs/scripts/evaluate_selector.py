"""Measure PSF-index selection on held-out synthetic pairs, without promotion."""
from __future__ import annotations

import sys
from collections import Counter
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
    cp_path = ROOT / "runs/formal_8192/checkpoints/step08192.pth"
    complete = load(ROOT / "runs/formal_8192/training_complete.json")
    assert complete["updates"] == 8192 and sha(cp_path) == complete["checkpoint"]["sha256"]
    cp = torch.load(cp_path, map_location="cpu", weights_only=False)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    setup(1309001)
    model = Model(model_config(), ROOT).to(device).eval()
    model.load_state_dict(cp["model"], strict=True)
    bank = Bank(train_config())
    result = {}
    with torch.inference_mode():
        for split, count in (("train", 64), ("dev", 128), ("test", 128)):
            labeled = 0
            top1 = 0
            top4 = 0
            parent_labeled = 0
            parent_top1 = 0
            chosen = Counter()
            objective_values = []
            ablations = []
            for i in range(count):
                batch = bank.batch(split, i, device)
                output = model(batch["source"])
                logits = model.refiner.optics.last_logits
                selected = model.refiner.optics.last_indices
                labels = batch["psf_index"]
                valid = labels >= 0
                if bool(valid.any()):
                    labeled += int(valid.sum())
                    top1 += int((logits.argmax(1)[valid] == labels[valid]).sum())
                    top4 += int((selected[valid] == labels[valid, None]).any(1).sum())
                    parent_labeled += 1
                    parent_top1 += int((logits.argmax(1)[valid] == labels[valid]).all())
                chosen.update(int(v) for v in selected[:, 0].cpu().tolist())
                loss, _ = objective(output, batch)
                objective_values.append(float(loss))
                if split == "test" and i < 16:
                    model.optical_enabled = False
                    bypass = model(batch["source"])
                    model.optical_enabled = True
                    lo, hi = batch["core"]
                    a = (output - bypass)[..., lo:hi, lo:hi]
                    off_loss, _ = objective(bypass, batch)
                    ablations.append(dict(parent_id=batch["parent_id"],
                                          on_off_rms_gray=float(a.square().mean().sqrt() * 255),
                                          on_off_max_gray=float(a.abs().max() * 255),
                                          on_loss=float(loss), off_loss=float(off_loss)))
            result[split] = dict(parents=count, labeled_parents=parent_labeled,
                                 labeled_frames=labeled, top1_correct=top1,
                                 top4_contains_correct=top4,
                                 parent_both_top1_correct=parent_top1,
                                 top1_fraction=top1 / labeled,
                                 top4_fraction=top4 / labeled,
                                 mean_reconstruction_objective=float(np.mean(objective_values)),
                                 selected_top1_distribution=dict(sorted(chosen.items())),
                                 on_off_first16=ablations)
            print("SELECTOR", split, result[split]["top1_fraction"],
                  result[split]["top4_fraction"], flush=True)
    save(ROOT / "results/selector_evaluation.json",
         dict(model=model_config()["model_name"], checkpoint_sha256=sha(cp_path),
              note="dev/test are held-out synthetic parents; real captures have no known PSF index",
              splits=result, completed_utc=now()))


if __name__ == "__main__":
    main()
