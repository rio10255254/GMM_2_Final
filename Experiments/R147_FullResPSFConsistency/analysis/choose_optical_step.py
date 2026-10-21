"""Predeclare a conservative full-resolution physical step from synthetic dev data."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from optical.fullres_psf import FullResPSF
from utils import load, now, save, sha


def main() -> None:
    entries = [e for e in load(ROOT / "data/manifest.json")["entries"]
               if e["split"] == "dev" and e["applied_psf_index"] is not None
               and e["category"] != "flat_negative"][:40]
    assert len(entries) == 40
    operator = FullResPSF(ROOT / "calibration/measured_psf_bank.npz").eval()
    candidates = [0.0, .1, .2, .3, .4, .5, .8, 1.0]
    errors = {a: [] for a in candidates}
    with torch.inference_mode():
        for entry in entries:
            with np.load(ROOT / "data" / entry["arrays"], allow_pickle=False) as z:
                source = torch.from_numpy(z["source"][:, None, 32:352, 32:352]
                                          .astype(np.float32)/255)
                target = torch.from_numpy(z["target"][:, None, 32:352, 32:352]
                                          .astype(np.float32))
            for alpha in candidates:
                estimate = source.clone()
                for _ in range(4):
                    if alpha:
                        estimate = (estimate + alpha*operator.consistency(estimate, source)[1]).clamp(0, 1)
                score = float(torch.abs(estimate[..., 96:224, 96:224] -
                                        target[..., 96:224, 96:224]).mean())*255
                errors[alpha].append(score)
    initial = np.asarray(errors[0.0])
    statistics = {str(a): dict(mean_gray_MAE=float(np.mean(scores)),
                               improved_parents=int((np.asarray(scores) < initial).sum()))
                  for a, scores in errors.items()}
    selected = .3
    assert statistics[str(selected)]["improved_parents"] == 40
    assert statistics[str(selected)]["mean_gray_MAE"] < statistics["0.0"]["mean_gray_MAE"]
    result = dict(passed=True, synthetic_dev_parents=40, source="bundled R146-matched dev parents",
                  operator_source_sha256=sha(ROOT / "optical/fullres_psf.py"),
                  candidates=statistics, selected_initial_step=selected,
                  maximum_trainable_step=.8,
                  rationale="Conservative positive improvement on all sampled dev parents; larger values not selected from real PI/SEM scores",
                  script_sha256=sha(Path(__file__)), completed_utc=now())
    save(ROOT / "results/optical_step_preflight.json", result)
    print("STEP_PREFLIGHT_PASS", result, flush=True)


if __name__ == "__main__":
    main()
