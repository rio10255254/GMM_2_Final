"""Measure how much the 25 PSFs change identical synthetic clear scenes."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import fftconvolve

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import load, now, save, sha


def main() -> None:
    with np.load(ROOT / "calibration/measured_psf_bank.npz", allow_pickle=False) as z:
        kernels = z["all_kernels"].astype(np.float64)
    assert kernels.shape == (25, 101, 101)
    manifest = load(ROOT / "data/manifest.json")
    rows = []
    for entry in manifest["entries"]:
        if entry["split"] not in ("dev", "test") or entry["applied_psf_index"] is None:
            continue
        if entry["category"] == "flat_negative":
            continue
        meta = load(ROOT / "data" / entry["metadata"])
        with np.load(ROOT / "data" / entry["arrays"], allow_pickle=False) as z:
            clear = z["target"][0].astype(np.float64)
        padded = np.pad(clear, 50, mode="reflect")
        # Exactly the native-image convolution and 128x128 supervised center.
        blurred = np.stack([
            fftconvolve(padded, kernel, mode="same")[50:-50, 50:-50][128:256, 128:256]
            for kernel in kernels
        ])
        reference = blurred.mean(axis=0)
        rms_gray = np.sqrt(np.mean((blurred - reference)**2, axis=(1, 2))) * 255
        sigma = float(meta["noise_sigma_gray"])
        rows.append(dict(split=entry["split"], parent_id=entry["parent_id"],
                         category=entry["category"], noise_sigma_gray=sigma,
                         median_psf_difference_from_bank_mean_gray=float(np.median(rms_gray)),
                         max_psf_difference_from_bank_mean_gray=float(np.max(rms_gray)),
                         median_difference_to_noise_ratio=float(np.median(rms_gray) / sigma)))
    result = pd.DataFrame(rows)
    out = ROOT / "results/deep_diagnosis"
    out.mkdir(parents=True, exist_ok=True)
    result.to_csv(out / "synthetic_psf_observability.csv", index=False)
    summary = dict(parents=len(result), by_split=result.split.value_counts().to_dict(),
                   median_psf_difference_gray=float(result.median_psf_difference_from_bank_mean_gray.median()),
                   p90_psf_difference_gray=float(result.median_psf_difference_from_bank_mean_gray.quantile(.9)),
                   median_noise_sigma_gray=float(result.noise_sigma_gray.median()),
                   median_difference_to_noise_ratio=float(result.median_difference_to_noise_ratio.median()),
                   p90_difference_to_noise_ratio=float(result.median_difference_to_noise_ratio.quantile(.9)),
                   count_below_noise=int((result.median_difference_to_noise_ratio < 1).sum()),
                   count_below_half_noise=int((result.median_difference_to_noise_ratio < .5).sum()),
                   script_sha256=sha(Path(__file__)), completed_utc=now())
    save(out / "synthetic_psf_observability_summary.json", summary)
    print(summary, flush=True)


if __name__ == "__main__":
    main()
