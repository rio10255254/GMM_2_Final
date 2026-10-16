"""Second operator oracle: add center-preserving radiometry actions.

The first bank established that denoising/inverse filtering can modestly improve
profiles but that fixed-center width correction alone lacks the radiometric
reach visible in the truth.  This version preserves the first result and adds
local/global contrast and endpoint-contrast actions without changing geometry.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import cv2
import numpy as np


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("r108_operator_v1", HERE / "02_operator_oracle.py")
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load base operator experiment")
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)

base.RESULT = base.ROOT / "results" / "operator_oracle_radiometry_v2"
base.REPORT = base.ROOT / "reports" / "02B_OPERATOR_ORACLE_RADIOMETRY.md"
base.RESULT.mkdir(parents=True, exist_ok=True)
base.REPORT.parent.mkdir(parents=True, exist_ok=True)


def local_contrast(image: np.ndarray, sigma: float, gain: float) -> np.ndarray:
    background = cv2.GaussianBlur(image, (0, 0), sigma, borderType=cv2.BORDER_REFLECT_101)
    return np.clip(background + gain * (image - background), 0.0, 1.0).astype(np.float32)


def global_contrast(image: np.ndarray, gain: float) -> np.ndarray:
    center = float(np.median(image))
    return np.clip(center + gain * (image - center), 0.0, 1.0).astype(np.float32)


def fixed_center_radiometry(image: np.ndarray, scale: float, distance: float, contrast_gain: float) -> np.ndarray:
    evidence, nx, ny, _ = base.local_evidence(image)
    h, w = image.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    minus = base.remap(image, xx - nx * distance, yy - ny * distance)
    plus = base.remap(image, xx + nx * distance, yy + ny * distance)
    lower = np.minimum(minus, plus)
    upper = np.maximum(minus, plus)
    midpoint = 0.5 * (lower + upper)
    contrast = np.maximum(upper - lower, 1.0 / 255.0)
    probability = np.clip((image - lower) / contrast, 1e-4, 1.0 - 1e-4)
    logits = np.log(probability) - np.log1p(-probability)
    sharpened = 1.0 / (1.0 + np.exp(-np.clip(logits / scale, -30, 30)))
    rendered = midpoint + contrast_gain * contrast * (sharpened - 0.5)
    contrast_support = np.clip((contrast - 4.0 / 255.0) / (20.0 / 255.0), 0.0, 1.0)
    gate = np.clip(evidence * contrast_support, 0.0, 1.0)
    return np.clip(image + gate * (rendered - image), 0.0, 1.0).astype(np.float32)


original_actions = base.actions


def expanded_actions():
    rows = original_actions()
    for sigma in (8.0, 16.0, 32.0):
        for gain in (1.15, 1.30, 1.50):
            rows.append(base.Action(
                f"localcontrast_s{int(sigma)}_g{gain:.2f}",
                "local_contrast",
                lambda x, s=sigma, g=gain: local_contrast(x, s, g),
            ))
    for gain in (1.10, 1.25, 1.40):
        rows.append(base.Action(
            f"globalcontrast_g{gain:.2f}",
            "global_contrast",
            lambda x, g=gain: global_contrast(x, g),
        ))
    for scale in (0.45, 0.60, 0.75):
        for gain in (1.15, 1.30, 1.50):
            rows.append(base.Action(
                f"fixedradiometry_w{scale:.2f}_d4_g{gain:.2f}",
                "fixed_center_radiometry",
                lambda x, s=scale, g=gain: fixed_center_radiometry(x, s, 4.0, g),
            ))
    rows.extend([
        base.Action(
            "illum16a25_localcontrast16g130",
            "combined_radiometry",
            lambda x: local_contrast(base.local_illumination(x, 16.0, 0.25), 16.0, 1.30),
        ),
        base.Action(
            "denoise55_fixedradiometry_w60_g130",
            "combined_radiometry",
            lambda x: fixed_center_radiometry(base.gaussian_denoise(x, 0.55), 0.60, 4.0, 1.30),
        ),
    ])
    return rows


base.actions = expanded_actions


if __name__ == "__main__":
    raise SystemExit(base.main())
