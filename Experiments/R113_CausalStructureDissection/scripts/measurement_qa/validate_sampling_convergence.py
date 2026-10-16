"""Validate formal 0.25 px / 720-angle metrics against a denser polar grid."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
MEASUREMENT_SCRIPT = Path(__file__).with_name("corrected_ring_measurements.py")
SPEC = importlib.util.spec_from_file_location("corrected_ring_measurements_convergence", MEASUREMENT_SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)

OUTPUT = ROOT / "results" / "measurement_qa"
SAMPLE_INDICES = (1, 25, 50, 75, 100)


def main() -> int:
    formal = pd.read_csv(OUTPUT / "corrected_frame_metrics.csv", encoding="utf-8-sig")
    config = json.loads(module.R112_CONFIG.read_text(encoding="utf-8"))
    radii, map_x, map_y = module.build_polar_maps(
        radial_step_px=0.125,
        angle_samples=1440,
        max_radius_px=module.MAX_RADIUS_PX,
    )
    rows: list[dict[str, object]] = []
    for arm in module.ARM_ORDER:
        coordinates = module.parse_score(Path(config["models"][arm]["score"]), arm)
        image_dir = Path(config["models"][arm]["image_dir"])
        for frame_index in SAMPLE_INDICES:
            coord = coordinates.loc[coordinates["frame_index"] == frame_index].iloc[0]
            image = module.read_gray(image_dir / coord["frame_name"])
            crop = cv2.getRectSubPix(
                image,
                (module.CROP_SIZE, module.CROP_SIZE),
                (float(coord["x_px_external"]), float(coord["y_px_external"])),
            )
            profile = module.radial_profile_subpixel(crop, map_x, map_y)
            dense = module.radial_features_subpixel(radii, profile)
            base = formal.loc[(formal["arm"] == arm) & (formal["frame_index"] == frame_index)].iloc[0]
            dense_center = 0.5 * (dense.inner_halfmax_radius_px + dense.outer_halfmax_radius_px)
            rows.append(
                {
                    "arm": arm,
                    "frame_index": frame_index,
                    "formal_peak_radius_px": float(base["ring_peak_radius_px"]),
                    "dense_peak_radius_px": dense.peak_radius_px,
                    "peak_abs_difference_px": abs(dense.peak_radius_px - float(base["ring_peak_radius_px"])),
                    "formal_center_radius_px": float(base["ring_halfmax_center_radius_px"]),
                    "dense_center_radius_px": dense_center,
                    "center_abs_difference_px": abs(dense_center - float(base["ring_halfmax_center_radius_px"])),
                    "formal_width_px": float(base["ring_halfmax_width_px"]),
                    "dense_width_px": dense.halfmax_width_px,
                    "width_abs_difference_px": abs(dense.halfmax_width_px - float(base["ring_halfmax_width_px"])),
                    "formal_contrast_gray": float(base["ring_contrast_gray"]),
                    "dense_contrast_gray": dense.contrast_gray,
                    "contrast_abs_difference_gray": abs(dense.contrast_gray - float(base["ring_contrast_gray"])),
                }
            )
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "sampling_convergence_per_frame.csv", index=False, encoding="utf-8-sig", float_format="%.10g")
    limits = {
        "center_max_abs_difference_px": 0.15,
        "width_max_abs_difference_px": 0.25,
        "contrast_max_abs_difference_gray": 0.25,
    }
    observed = {
        "center_max_abs_difference_px": float(table["center_abs_difference_px"].max()),
        "peak_max_abs_difference_px": float(table["peak_abs_difference_px"].max()),
        "width_max_abs_difference_px": float(table["width_abs_difference_px"].max()),
        "contrast_max_abs_difference_gray": float(table["contrast_abs_difference_gray"].max()),
        "center_median_abs_difference_px": float(table["center_abs_difference_px"].median()),
        "peak_median_abs_difference_px": float(table["peak_abs_difference_px"].median()),
        "width_median_abs_difference_px": float(table["width_abs_difference_px"].median()),
        "contrast_median_abs_difference_gray": float(table["contrast_abs_difference_gray"].median()),
    }
    passed = all(observed[key] <= limit for key, limit in limits.items())
    result = {
        "status": "pass" if passed else "fail",
        "generated_local": datetime.now().astimezone().isoformat(),
        "sample_frames_per_arm": list(SAMPLE_INDICES),
        "sample_rows": int(len(table)),
        "formal_grid": {"radial_step_px": 0.25, "angle_samples": 720},
        "dense_grid": {"radial_step_px": 0.125, "angle_samples": 1440},
        "limits": limits,
        "observed": observed,
        "diagnostic_note": "Local profile-peak radius is non-gating because broad profiles can switch between nearly equal maxima; the half-maximum midpoint is the primary radius.",
    }
    (OUTPUT / "sampling_convergence.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
