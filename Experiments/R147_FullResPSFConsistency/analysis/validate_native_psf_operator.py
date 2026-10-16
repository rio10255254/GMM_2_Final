"""Physics checks before training the native-grid fixed-PSF model."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
from scipy.signal import fftconvolve

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from optical.fullres_psf import FullResPSF
from utils import now, save, sha


def main() -> None:
    operator = FullResPSF(ROOT / "calibration/measured_psf_bank.npz").eval()
    kernel = operator.kernel.numpy()[0, 0]
    assert abs(kernel.sum()-1) < 1e-6
    rng = np.random.default_rng(1471001)
    native = rng.random((320, 320), dtype=np.float32)
    predicted = operator.blur(torch.from_numpy(native)[None, None]).numpy()[0, 0]
    independently = fftconvolve(np.pad(native, 50, mode="reflect"), kernel,
                                mode="same")[50:-50, 50:-50]
    max_scipy_difference = float(np.max(np.abs(predicted-independently)))
    assert max_scipy_difference < 1e-6
    flat = operator.blur(torch.full((1, 1, 320, 320), .43)).numpy()
    flat_error = float(np.max(np.abs(flat-.43)))
    assert flat_error < 1e-6
    impulse = torch.zeros((1, 1, 320, 320))
    impulse[0, 0, 160, 160] = 1
    impulse_output = operator.blur(impulse).numpy()[0, 0]
    peak = np.unravel_index(np.argmax(impulse_output), impulse_output.shape)
    assert peak == (160, 160)
    assert abs(float(impulse_output.sum())-1) < 1e-6

    yy, xx = np.indices((320, 320))
    clear = np.where((xx-160)**2+(yy-160)**2 <= 7.6**2, .25, .65).astype(np.float32)
    truth = torch.from_numpy(clear)[None, None]
    observation = operator.blur(truth)
    initial = observation
    residual, backprojection = operator.consistency(initial, observation)
    advanced = (initial+.3*backprojection).clamp(0, 1)
    before = float((operator.blur(initial)-observation).square().mean())
    after = float((operator.blur(advanced)-observation).square().mean())
    assert after < before, (before, after)
    before_clear = float(torch.abs(initial-truth).mean())
    after_clear = float(torch.abs(advanced-truth).mean())
    assert after_clear <= before_clear

    # The new feature path must remain differentiable through full-resolution FFTs.
    estimate = observation.clone().requires_grad_(True)
    data_error, correction = operator.consistency(estimate, observation)
    loss = data_error.square().mean() + correction.square().mean()
    loss.backward()
    grad_norm = float(estimate.grad.norm())
    assert np.isfinite(grad_norm) and grad_norm > 0
    result = dict(passed=True, psf_bank_sha256=sha(ROOT / "calibration/measured_psf_bank.npz"),
                  operator_source_sha256=sha(ROOT / "optical/fullres_psf.py"),
                  kernel_sum=float(kernel.sum()),
                  max_full_resolution_scipy_difference=max_scipy_difference,
                  constant_image_max_error=flat_error,
                  impulse_peak=[int(peak[0]), int(peak[1])],
                  impulse_energy=float(impulse_output.sum()),
                  known_blur_fidelity_before=before,
                  known_blur_fidelity_after=after,
                  clear_mae_before=before_clear,
                  clear_mae_after=after_clear,
                  differentiable_gradient_norm=grad_norm,
                  script_sha256=sha(Path(__file__)), completed_utc=now())
    save(ROOT / "results/native_psf_operator_validation.json", result)
    print("NATIVE_PSF_OPERATOR_PASS", result, flush=True)


if __name__ == "__main__":
    main()
