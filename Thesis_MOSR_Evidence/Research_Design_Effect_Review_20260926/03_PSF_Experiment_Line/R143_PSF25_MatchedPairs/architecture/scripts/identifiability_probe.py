"""Oracle-clear-target PSF discrimination on a small held-out sample.

The clear target is deliberately supplied to this test. Its accuracy is an
optimistic diagnostic, not an attainable single-image model benchmark.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from make_data import convolve_native
from utils import load, now, save, sha


def main() -> None:
    manifest = load(ROOT / "data/manifest.json")
    with np.load(ROOT / "calibration/measured_psf_bank.npz", allow_pickle=False) as z:
        kernels = z["all_kernels"].astype(np.float64)
    kernels /= kernels.sum((1, 2), keepdims=True)
    result = {}
    for split in ("dev", "test"):
        items = [e for e in manifest["entries"] if e["split"] == split and e["category"] not in ("clean_identity", "noisy_identity", "flat_negative")][:32]
        correct, top4, rms_spreads, sigmas, rows = 0, 0, [], [], []
        for entry in items:
            meta = load(ROOT / "data" / entry["metadata"])
            with np.load(ROOT / "data" / entry["arrays"], allow_pickle=False) as z:
                clear, observed = z["target"], z["source"].astype(np.float64) / 255
            lo, hi = 128, 256
            candidates = np.empty((25, 2, hi-lo, hi-lo), dtype=np.float64)
            for k in range(25):
                for view in range(2):
                    candidates[k, view] = convolve_native(clear[view], kernels[k])[lo:hi, lo:hi]
            measured = observed[:, lo:hi, lo:hi]
            residual = ((candidates - measured[None])**2).sum((1, 2, 3))
            rank = np.argsort(residual)
            truth = int(meta["applied_psf_index"])
            correct += int(rank[0] == truth)
            top4 += int(truth in rank[:4])
            rms_spreads.append(float(np.sqrt(np.mean((candidates - candidates.mean(0, keepdims=True))**2))*255))
            sigmas.append(float(meta["noise_sigma_gray"]))
            rows.append(dict(parent_id=entry["parent_id"], truth=truth,
                             oracle_top1=int(rank[0]), oracle_top4=[int(v) for v in rank[:4]],
                             noise_sigma_gray=float(meta["noise_sigma_gray"])))
        result[split] = dict(parents=len(items), oracle_top1_correct=correct,
                             oracle_top4_contains_correct=top4,
                             median_across_psf_rms_gray=float(np.median(rms_spreads)),
                             median_sensor_noise_sigma_gray=float(np.median(sigmas)),
                             note="oracle sees the clear target and tests two related images together",
                             rows=rows)
        print("ORACLE", split, correct, "/", len(items), "top4", top4, flush=True)
    save(ROOT / "results/oracle_psf_identifiability.json",
         dict(bank_sha256=sha(ROOT / "calibration/measured_psf_bank.npz"),
              data_manifest_sha256=sha(ROOT / "data/manifest.json"), splits=result,
              completed_utc=now()))


if __name__ == "__main__":
    main()
