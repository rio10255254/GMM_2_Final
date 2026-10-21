"""Run fixed synthetic calibration fixtures for sequence_metrics."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import cv2
import numpy as np

from sequence_metrics import estimate_position

ROOT = Path(__file__).resolve().parents[1]


def analytic_shape(size=160):
    y, x = np.mgrid[:size, :size].astype(np.float32)
    # A non-circular, fully visible shape exercises both coordinate axes.
    ellipse = ((x - 82) / 31) ** 2 + ((y - 75) / 23) ** 2
    bar = ((x - 44) / 8) ** 2 + ((y - 111) / 18) ** 2
    return np.exp(-3.5 * ellipse) + 0.35 * np.exp(-2.0 * bar)


def shift(image, dx, dy):
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def run():
    ref = analytic_shape()
    roi = (12, 12, 148, 148)
    rows = []
    cases = [("shift_x_pos", 1.0, 0.0), ("shift_x_neg", -1.0, 0.0),
             ("shift_y_pos", 0.0, 1.0), ("shift_y_neg", 0.0, -1.0),
             ("diag_pos", .5, .5), ("diag_neg", -.5, -.5)]
    for name, dx, dy in cases:
        measured = estimate_position(shift(ref, dx, dy), ref, roi)
        rows.append({"case": name, "expected": [dx, dy], "measured": [measured.x_px, measured.y_px],
                     "valid": measured.valid, "reason": measured.reason,
                     "error_px": None if not measured.valid else float(np.hypot(measured.x_px - dx, measured.y_px - dy)),
                     "diagnostics": measured.diagnostics})
    gain_bias = estimate_position(np.clip(ref * 1.2 + .1, 0, 1), ref, roi)
    width = cv2.GaussianBlur(ref, (0, 0), 1.4)
    width_result = estimate_position(width, ref, roi)
    complement = estimate_position(1 - ref, 1 - ref, roi)
    flat = estimate_position(np.full_like(ref, .5), ref, roi)
    cropped = estimate_position(ref[:100, :100], ref, roi)
    controls = {"gain_bias_only": {"valid": gain_bias.valid, "position": [gain_bias.x_px, gain_bias.y_px], "reason": gain_bias.reason},
                "symmetric_width_change": {"valid": width_result.valid, "position": [width_result.x_px, width_result.y_px], "reason": width_result.reason},
                "bright_dark_identity": {"valid": complement.valid, "position": [complement.x_px, complement.y_px], "reason": complement.reason},
                "flat_invalid": {"valid": flat.valid, "position": [flat.x_px, flat.y_px], "reason": flat.reason},
                "cropped_invalid": {"valid": cropped.valid, "position": [cropped.x_px, cropped.y_px], "reason": cropped.reason}}
    tolerance = .08
    passed_shift = all(r["valid"] and r["error_px"] <= tolerance for r in rows)
    controls_pass = (not controls["flat_invalid"]["valid"] and controls["cropped_invalid"]["reason"] == "shape_mismatch")
    result = {"schema_version": 1, "status": "pass" if passed_shift and controls_pass else "blocked",
              "completed_at_utc": datetime.now(timezone.utc).isoformat(), "protocol_id": "r119-fixed-reference-registration-v1",
              "coordinate_convention": "x_right_y_down_native_pixels", "tolerance_px": tolerance,
              "shift_cases": rows, "controls": controls,
              "scientific_meaning": "Calibration validity only; this does not compare models."}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "results/locator_calibration.json")
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
