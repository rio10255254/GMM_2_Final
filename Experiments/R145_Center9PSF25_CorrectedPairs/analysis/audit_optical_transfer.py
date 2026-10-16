"""Numerically audit the frozen optical cue's FFT transfer and phase origin."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import load, now, save, sha


def main() -> None:
    cp_path = ROOT / "runs/formal_8192/checkpoints/step08192.pth"
    cp = torch.load(cp_path, map_location="cpu", weights_only=False)
    state = cp["model"]
    beta_raw = float(state["refiner.optics.beta"])
    beta_scale = float(state["refiner.optics.beta_scale"])
    beta = min(max(beta_raw, 0), .1) * beta_scale
    reg = float(state["refiner.optics.reg"])
    ratio = float(state["refiner.optics.lowfreq_ratio"])
    receipt = load(ROOT / "results/reconstruction/001804_XY_0/01.json")
    with np.load(ROOT / "calibration/measured_psf_bank.npz", allow_pickle=False) as z:
        bank = z["all_kernels"].astype(np.float64)
    kernel = np.einsum("n,nhw->hw", np.asarray(receipt["PSF_weights"]),
                       bank[receipt["PSF_indices"]])
    assert abs(kernel.sum()-1) < 1e-6
    details = {}
    for label, (h, w) in {"training_half_resolution": (160, 160),
                          "real_half_resolution": (772, 1032)}.items():
        ph, pw = h - 101, w - 101
        pad = ((ph//2, ph-ph//2), (pw//2, pw-pw//2))
        padded = np.pad(kernel, pad)
        center_y, center_x = pad[0][0]+50, pad[1][0]+50
        H = np.fft.rfft2(padded)
        fy = np.fft.fftfreq(h)[:, None]
        fx = np.fft.rfftfreq(w)[None, :]
        mask = (np.sqrt(fy**2+fx**2)/.5) <= ratio
        inverse = np.conj(H)/(np.abs(H)**2+reg+1e-6)
        details[label] = dict(shape=[h, w], kernel_center_in_fft_array=[center_y, center_x],
                              low_frequency_bin_fraction=float(mask.mean()),
                              inverse_DC_magnitude=float(abs(inverse[0, 0])),
                              inverse_mask_median_magnitude=float(np.median(abs(inverse[mask]))),
                              inverse_mask_max_magnitude=float(abs(inverse[mask]).max()),
                              combined_DC_magnitude=float(abs(1-beta+beta*inverse[0, 0])),
                              PSF_phase_first_x_frequency_rad=float(np.angle(H[0, 1])),
                              PSF_phase_first_y_frequency_rad=float(np.angle(H[1, 0])))
        if label == "training_half_resolution":
            yy, xx = np.indices((h, w))
            spot = np.exp(-((xx-80)**2+(yy-80)**2)/(2*12**2))
            spectrum = np.fft.rfft2(spot)
            restored = np.fft.irfft2(spectrum*inverse*mask, s=(h, w))
            corrected = np.roll(padded, (-center_y, -center_x), axis=(0, 1))
            H_aligned = np.fft.rfft2(corrected)
            aligned_inverse = np.conj(H_aligned)/(np.abs(H_aligned)**2+reg+1e-6)
            restored_aligned = np.fft.irfft2(spectrum*aligned_inverse*mask, s=(h, w))
            details[label]["smooth_spot_input_peak"] = [80, 80]
            details[label]["current_optical_restored_peak"] = [int(v) for v in np.unravel_index(np.argmax(restored), restored.shape)]
            details[label]["origin_aligned_restored_peak"] = [int(v) for v in np.unravel_index(np.argmax(restored_aligned), restored_aligned.shape)]
            # Repeat with the exact PyTorch operators used by the model.
            pt = F.pad(torch.from_numpy(kernel.astype(np.float32))[None, None],
                       (pad[1][0], pad[1][1], pad[0][0], pad[0][1]))
            spot_t = torch.from_numpy(spot.astype(np.float32))[None, None]
            mask_t = torch.from_numpy(mask)[None, None]
            torch_peaks = {}
            for key, candidate in (("current", pt),
                                   ("origin_aligned", torch.roll(pt, (-center_y, -center_x), dims=(-2, -1)))):
                ht = torch.fft.rfft2(candidate)
                inverse_t = ht.conj()/(ht.abs().square()+reg+1e-6)
                result_t = torch.fft.irfft2(torch.fft.rfft2(spot_t)*inverse_t*mask_t, s=(h, w))
                torch_peaks[key] = [int(v) for v in divmod(int(result_t.flatten().argmax()), w)]
            details[label]["direct_torch_peaks"] = torch_peaks
            assert torch_peaks["current"] == details[label]["current_optical_restored_peak"]
            assert torch_peaks["origin_aligned"] == details[label]["origin_aligned_restored_peak"]
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, axes = plt.subplots(1, 3, figsize=(10, 3.3), layout="constrained")
            axes[0].imshow(spot, cmap="magma", vmin=0, vmax=1)
            axes[0].set_title("Input spot")
            for ax, values, title in ((axes[1], restored, "Current FFT origin"),
                                      (axes[2], restored_aligned, "Aligned FFT origin")):
                ax.imshow(values, cmap="magma", vmin=0, vmax=.03)
                ax.set_title(title)
            for ax in axes:
                ax.axis("off")
            figure = ROOT / "reports/figures/optical_phase_spot.png"
            figure.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(figure, dpi=180)
            plt.close(fig)
    output = dict(checkpoint_sha256=sha(cp_path), bank_sha256=sha(ROOT / "calibration/measured_psf_bank.npz"),
                  effective_beta=beta, raw_beta=beta_raw, beta_scale=beta_scale,
                  regularization=reg, low_frequency_ratio=ratio,
                  selected_indices=receipt["PSF_indices"], details=details,
                  script_sha256=sha(Path(__file__)), completed_utc=now())
    destination = ROOT / "results/deep_diagnosis/optical_transfer_audit.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    save(destination, output)
    print(output, flush=True)


if __name__ == "__main__":
    main()
