"""Independent integrity and arithmetic validation for corrected R113 metrics."""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "results" / "measurement_qa"
FRAME_PATH = RESULT / "corrected_frame_metrics.csv"
SUMMARY_PATH = RESULT / "corrected_arm_summary.csv"
PROFILE_PATH = RESULT / "corrected_radial_profiles.csv.gz"
OUTPUT_PATH = RESULT / "validation.json"
ARMS = ("Raw", "V42 E120", "R109 E48")


def close(left: float, right: float, tolerance: float = 2e-8) -> bool:
    return math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance)


def main() -> int:
    frame = pd.read_csv(FRAME_PATH, encoding="utf-8-sig")
    summary = pd.read_csv(SUMMARY_PATH, encoding="utf-8-sig")
    profile = pd.read_csv(PROFILE_PATH, compression="gzip")
    checks: dict[str, object] = {}

    checks["frame_rows_300"] = len(frame) == 300
    checks["exact_100_frames_per_arm"] = frame.groupby("arm").size().to_dict() == {arm: 100 for arm in ARMS}
    checks["unique_arm_frame_key"] = not frame.duplicated(["arm", "frame_name"]).any()
    checks["exact_frame_index_population"] = all(
        frame.loc[frame["arm"] == arm, "frame_index"].sort_values().tolist() == list(range(1, 101))
        for arm in ARMS
    )
    numeric = frame.select_dtypes(include=[np.number])
    checks["all_numeric_values_finite"] = bool(np.isfinite(numeric.to_numpy()).all())
    checks["positive_ring_geometry"] = bool(
        (frame["ring_inner_halfmax_radius_px"] < frame["ring_peak_radius_px"]).all()
        and (frame["ring_peak_radius_px"] < frame["ring_outer_halfmax_radius_px"]).all()
        and (frame["ring_halfmax_width_px"] > 0).all()
    )
    checks["native_subpixel_values_present"] = bool(
        ((frame["ring_halfmax_center_radius_px"] - frame["ring_halfmax_center_radius_px"].round()).abs() > 1e-3).mean() > 0.95
        and ((frame["ring_halfmax_width_px"] / 4.0 - (frame["ring_halfmax_width_px"] / 4.0).round()).abs() > 1e-3).mean() > 0.95
    )
    checks["annulus_and_full_scope_not_identical"] = bool(
        (frame["annulus_mean_gray"] - frame["full_crop_mean_gray"]).abs().min() > 1e-3
        and (frame["annulus_high_frequency_rms_gray"] - frame["full_crop_high_frequency_rms_gray"]).abs().min() > 1e-3
    )
    radial_rows_per_frame = profile.groupby(["arm", "frame_name"]).size()
    expected_radial_rows = int(round(696.0 / 0.25)) + 1
    checks["radial_profile_population"] = bool(
        len(radial_rows_per_frame) == 300 and (radial_rows_per_frame == expected_radial_rows).all()
    )
    checks["radial_grid_exact"] = bool(
        close(float(profile["radius_px"].min()), 0.0)
        and close(float(profile["radius_px"].max()), 696.0)
        and close(float(np.diff(np.sort(profile["radius_px"].unique())).min()), 0.25)
        and close(float(np.diff(np.sort(profile["radius_px"].unique())).max()), 0.25)
    )

    recomputed: dict[str, dict[str, float]] = {}
    arithmetic_ok = True
    for arm in ARMS:
        group = frame.loc[frame["arm"] == arm]
        claimed = summary.loc[summary["arm"] == arm].iloc[0]
        values = {
            "ring_center_radius_mean_px": float(group["ring_halfmax_center_radius_px"].mean()),
            "ring_center_radius_std_px": float(group["ring_halfmax_center_radius_px"].std(ddof=1)),
            "ring_peak_radius_mean_px": float(group["ring_peak_radius_px"].mean()),
            "ring_peak_radius_std_px": float(group["ring_peak_radius_px"].std(ddof=1)),
            "ring_width_mean_px": float(group["ring_halfmax_width_px"].mean()),
            "ring_width_std_px": float(group["ring_halfmax_width_px"].std(ddof=1)),
            "ring_contrast_mean_gray": float(group["ring_contrast_gray"].mean()),
            "ring_contrast_std_gray": float(group["ring_contrast_gray"].std(ddof=1)),
            "annulus_high_frequency_rms_median_gray": float(group["annulus_high_frequency_rms_gray"].median()),
            "full_crop_high_frequency_rms_median_gray": float(group["full_crop_high_frequency_rms_gray"].median()),
        }
        recomputed[arm] = values
        arithmetic_ok &= all(close(value, claimed[key], tolerance=2e-7) for key, value in values.items())
    checks["summary_arithmetic_recomputed_independently"] = bool(arithmetic_ok)
    checks["old_zero_variance_artifact_absent"] = bool(
        (summary["ring_center_radius_std_px"] > 0.01).all()
        and (summary["ring_width_std_px"] > 0.01).all()
    )

    passed = all(bool(value) for value in checks.values())
    result = {
        "status": "pass" if passed else "fail",
        "generated_local": datetime.now().astimezone().isoformat(),
        "checks": checks,
        "recomputed_key_values": recomputed,
        "frame_rows": int(len(frame)),
        "profile_rows": int(len(profile)),
        "summary_rows": int(len(summary)),
    }
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
