"""Model-independent position and sequence summaries for R119.

Coordinates are native pixels, x right and y down. The estimator is deliberately
independent of the reconstruction model: a fixed-reference, subpixel
registration with an explicit rank/flat validity test. It never aligns every
frame to erase the motion being measured.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence

import cv2
import numpy as np


@dataclass(frozen=True)
class Position:
    x_px: float | None
    y_px: float | None
    valid: bool
    reason: str
    diagnostics: dict


def _crop(array: np.ndarray, roi: Sequence[int] | None) -> np.ndarray:
    value = np.asarray(array, dtype=np.float32)
    if value.ndim != 2:
        raise ValueError("images must be two-dimensional")
    if roi is None:
        return value
    if len(roi) != 4:
        raise ValueError("fixed_roi must be (x0,y0,x1,y1)")
    x0, y0, x1, y1 = map(int, roi)
    if not (0 <= x0 < x1 <= value.shape[1] and 0 <= y0 < y1 <= value.shape[0]):
        raise ValueError("fixed_roi is outside the image")
    return value[y0:y1, x0:x1]


def _shift_image(image: np.ndarray, x: float, y: float) -> np.ndarray:
    matrix = np.float32([[1, 0, -x], [0, 1, -y]])
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]),
                          flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def estimate_position(image: np.ndarray, fixed_reference: np.ndarray,
                      fixed_roi: Sequence[int] | None = None,
                      protocol: Mapping | None = None) -> Position:
    """Estimate image displacement from a fixed reference in native pixels.

    `protocol` may specify ``min_gradient_energy``, ``ridge`` and ``iterations``
    but cannot change the coordinate convention or add model-specific tuning.
    Flat/rank-deficient inputs are returned invalid with an explicit reason.
    """
    protocol = dict(protocol or {})
    try:
        image = _crop(image, fixed_roi)
        reference = _crop(fixed_reference, fixed_roi)
    except ValueError as exc:
        if "outside the image" in str(exc):
            return Position(None, None, False, "shape_mismatch", {"error": str(exc)})
        raise
    if image.shape != reference.shape:
        return Position(None, None, False, "shape_mismatch", {"image_shape": image.shape, "reference_shape": reference.shape})
    if not np.isfinite(image).all() or not np.isfinite(reference).all():
        return Position(None, None, False, "nonfinite_input", {})
    image = image.astype(np.float32, copy=False)
    reference = reference.astype(np.float32, copy=False)
    gradient_y, gradient_x = np.gradient(reference)
    energy = float(np.mean(gradient_x * gradient_x + gradient_y * gradient_y))
    min_energy = float(protocol.get("min_gradient_energy", 1e-7))
    input_std = float(np.std(image))
    reference_std = float(np.std(reference))
    if energy < min_energy or reference_std < float(protocol.get("min_std", 1e-5)) or input_std < float(protocol.get("min_std", 1e-5)):
        return Position(None, None, False, "rank_deficient_or_flat", {"gradient_energy": energy, "reference_std": reference_std, "image_std": input_std})
    # Phase correlation is made insensitive to global gain/offset. The raw
    # images are retained for the final local fit and diagnostic reporting.
    # A broad high-pass removes exposure offset and leaves the spatial edge
    # signal used for phase initialization. The local refinement below still
    # sees the original fixed-reference values.
    phase_reference_raw = reference - cv2.GaussianBlur(reference, (0, 0), 3.0)
    phase_image_raw = image - cv2.GaussianBlur(image, (0, 0), 3.0)
    phase_reference = phase_reference_raw / max(float(np.std(phase_reference_raw)), 1e-8)
    phase_image = phase_image_raw / max(float(np.std(phase_image_raw)), 1e-8)
    hanning = cv2.createHanningWindow((reference.shape[1], reference.shape[0]), cv2.CV_32F)
    try:
        initial, response = cv2.phaseCorrelate(phase_reference, phase_image, hanning)
        position = np.asarray(initial, dtype=np.float64)
    except cv2.error:
        return Position(None, None, False, "phase_correlation_failed", {"gradient_energy": energy})
    # Refine against the fixed reference. A robust edge-information mask avoids
    # flat interiors, while the ridge prevents unstable axes from fabricating a
    # coordinate. The update sign is fixed by the synthetic calibration tests.
    threshold = float(protocol.get("gradient_fraction", 0.03)) * max(float(np.max(np.hypot(gradient_x, gradient_y))), 1e-9)
    weight = np.hypot(gradient_x, gradient_y) >= threshold
    weight[:2, :] = weight[-2:, :] = False
    weight[:, :2] = weight[:, -2:] = False
    ridge_factor = float(protocol.get("ridge", 1e-6))
    iterations = int(protocol.get("iterations", 5))
    for _ in range(max(iterations, 1)):
        aligned = _shift_image(image, float(position[0]), float(position[1]))
        # Fit translation after removing a scalar photometric offset. This
        # prevents exposure/gain changes from being reported as motion while
        # retaining shape-width changes as a separate nuisance condition.
        residual = aligned - reference
        wx = weight.astype(np.float64)
        a = np.array([[np.sum(wx * gradient_x * gradient_x), np.sum(wx * gradient_x * gradient_y)],
                      [np.sum(wx * gradient_x * gradient_y), np.sum(wx * gradient_y * gradient_y)]], dtype=np.float64)
        residual = residual - float(np.sum(wx * residual) / max(np.sum(wx), 1.0))
        b = -np.array([np.sum(wx * gradient_x * residual), np.sum(wx * gradient_y * residual)], dtype=np.float64)
        ridge = ridge_factor * max(float(np.trace(a)), 1.0)
        try:
            delta = np.linalg.solve(a + ridge * np.eye(2), b)
        except np.linalg.LinAlgError:
            return Position(None, None, False, "rank_deficient_axis", {"gradient_energy": energy, "response": float(response)})
        if not np.isfinite(delta).all():
            return Position(None, None, False, "nonfinite_update", {"gradient_energy": energy})
        position += delta
        if float(np.linalg.norm(delta)) < float(protocol.get("convergence_px", 1e-4)):
            break
    if not np.isfinite(position).all() or np.max(np.abs(position)) > float(protocol.get("max_displacement_px", 32)):
        return Position(None, None, False, "implausible_displacement", {"estimate": position.tolist(), "response": float(response)})
    return Position(float(position[0]), float(position[1]), True, "ok",
                    {"gradient_energy": energy, "reference_std": float(np.std(reference)), "phase_response": float(response), "iterations": iterations})


def _valid_rows(rows: Iterable[Mapping]) -> list[Mapping]:
    return [row for row in rows if bool(row.get("valid")) and row.get("estimated_x_px") is not None and row.get("estimated_y_px") is not None]


def summarize_sequence(position_rows: Sequence[Mapping]) -> dict:
    """Summarize one sequence; rows must belong to one scene/condition."""
    rows = list(position_rows)
    valid = _valid_rows(rows)
    result = {"valid_count": len(valid), "failure_count": len(rows) - len(valid), "bias_x_px": None,
              "bias_y_px": None, "repeat_sd_x_px": None, "repeat_sd_y_px": None,
              "step_sd_x_px": None, "step_sd_y_px": None, "step_p95_abs_x_px": None,
              "step_p95_abs_y_px": None, "cross_axis_error_px": None, "failure_reasons": {}}
    for row in rows:
        if not row.get("valid"):
            reason = str(row.get("failure_reason") or "invalid")
            result["failure_reasons"][reason] = result["failure_reasons"].get(reason, 0) + 1
    if not valid:
        return result
    errors_x = np.asarray([float(r["estimated_x_px"]) - float(r["true_x_px"]) for r in valid])
    errors_y = np.asarray([float(r["estimated_y_px"]) - float(r["true_y_px"]) for r in valid])
    result["bias_x_px"] = float(np.mean(errors_x)); result["bias_y_px"] = float(np.mean(errors_y))
    protocol = str(valid[0].get("protocol", ""))
    if protocol == "static_repeat":
        result["repeat_sd_x_px"] = float(np.std(errors_x, ddof=1)) if len(errors_x) > 1 else 0.0
        result["repeat_sd_y_px"] = float(np.std(errors_y, ddof=1)) if len(errors_y) > 1 else 0.0
    ordered = sorted(valid, key=lambda r: int(r.get("frame_index", 0)))
    if len(ordered) > 1 and protocol in {"motion_x", "motion_y", "motion_diag"}:
        step_x = np.diff([float(r["estimated_x_px"]) for r in ordered]) - np.diff([float(r["true_x_px"]) for r in ordered])
        step_y = np.diff([float(r["estimated_y_px"]) for r in ordered]) - np.diff([float(r["true_y_px"]) for r in ordered])
        result["step_sd_x_px"] = float(np.std(step_x, ddof=1)) if len(step_x) > 1 else 0.0
        result["step_sd_y_px"] = float(np.std(step_y, ddof=1)) if len(step_y) > 1 else 0.0
        result["step_p95_abs_x_px"] = float(np.percentile(np.abs(step_x), 95))
        result["step_p95_abs_y_px"] = float(np.percentile(np.abs(step_y), 95))
        if protocol == "motion_x":
            result["cross_axis_error_px"] = float(np.sqrt(np.mean(errors_y * errors_y)))
        elif protocol == "motion_y":
            result["cross_axis_error_px"] = float(np.sqrt(np.mean(errors_x * errors_x)))
    return result


def summarize_paired_effects(sequence_summaries: Sequence[Mapping], control_method: str = "Raw") -> list[dict]:
    """Return paired candidate-minus-control rows; never pool scene biases as SD."""
    by_key: dict[tuple, dict[str, Mapping]] = {}
    for row in sequence_summaries:
        key = (row.get("sequence_id"), row.get("estimator", "registration"))
        by_key.setdefault(key, {})[str(row.get("method"))] = row
    effects = []
    for (sequence_id, estimator), methods in sorted(by_key.items(), key=lambda item: str(item[0])):
        control = methods.get(control_method)
        if control is None:
            continue
        for method, candidate in methods.items():
            if method == control_method:
                continue
            effects.append({"sequence_id": sequence_id, "estimator": estimator, "method": method,
                            "control": control_method, "delta_bias_x_px": _delta(candidate, control, "bias_x_px"),
                            "delta_bias_y_px": _delta(candidate, control, "bias_y_px"),
                            "delta_step_sd_x_px": _delta(candidate, control, "step_sd_x_px"),
                            "delta_step_sd_y_px": _delta(candidate, control, "step_sd_y_px"),
                            "candidate_valid_count": candidate.get("valid_count"), "control_valid_count": control.get("valid_count")})
    return effects


def _delta(a: Mapping, b: Mapping, key: str):
    if a.get(key) is None or b.get(key) is None:
        return None
    return float(a[key]) - float(b[key])
