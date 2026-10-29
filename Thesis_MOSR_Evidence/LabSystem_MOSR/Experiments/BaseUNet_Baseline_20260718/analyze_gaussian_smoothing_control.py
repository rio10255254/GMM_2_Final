from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyze_base_unet_edge_stability import (
    CURRENT,
    NETWORK,
    radial_edge_metrics,
    read_gray,
    refine_dark_center,
    truthy,
)
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def analyze(control_root: Path) -> None:
    config = json.loads(
        (CURRENT / "config" / "sequence_center9_50x20x.json").read_text(encoding="utf-8")
    )["sequences"]
    selected = pd.read_csv(NETWORK / "tables" / "top30_raw_motion_selection.csv")
    selected = selected.loc[truthy(selected.top30_raw_motion_selected)].copy()
    displacement = pd.read_csv(control_root / "gaussian_smoothing_displacement_summary.csv")
    if len(selected) != 120:
        raise RuntimeError(f"Expected 120 locked steps, found {len(selected)}")

    rows: list[dict] = []
    for sigma in displacement.sigma_px.tolist():
        sigma_label = str(float(sigma)).replace(".", "p")
        sigma_root = control_root / f"sigma_{sigma_label}"
        anchors = pd.read_csv(
            sigma_root / "displacement_audit" / "tables" / "session_anchor_summary.csv"
        )
        if not truthy(anchors.anchor_success).all():
            raise RuntimeError(f"sigma={sigma}: at least one session anchor is invalid")
        for sequence_name, sequence_rows in selected.groupby("sequence", sort=False):
            sequence = config[sequence_name]
            centers0 = np.asarray([[row[1], row[2]] for row in sequence["centers"]], dtype=float)
            pitch_px = float(sequence["pitch_px"])
            radius_px = float(sequence["radius_px"])
            step_px = float(sequence["expected_signed_dx_px"])
            um_per_px = float(sequence["object_um_per_px"])
            raw_dir = Path(PROJECT_ROOT / sequence["raw_dir"])
            smoothed_dir = sigma_root / "reconstruction" / sequence_name
            for _, selected_row in sequence_rows.sort_values("end_frame_index").iterrows():
                frame_index = int(selected_row.end_frame_index)
                filename = f"frame_{frame_index:04d}.bmp"
                raw_image = read_gray(raw_dir / filename)
                image = read_gray(smoothed_dir / filename)
                anchor = anchors.loc[
                    (anchors.sequence == sequence_name)
                    & (anchors.start_frame_index <= frame_index)
                    & (anchors.end_frame_index >= frame_index)
                ]
                if len(anchor) != 1:
                    raise RuntimeError(
                        f"sigma={sigma}, {sequence_name}, frame={frame_index}: invalid anchor lookup"
                    )
                anchor = anchor.iloc[0]
                within_session_index = frame_index - int(anchor.start_frame_index)
                predicted = centers0 + np.asarray(
                    [
                        float(anchor.anchor_offset_x_px) + within_session_index * step_px,
                        float(anchor.anchor_offset_y_px),
                    ]
                )
                refined = [
                    refine_dark_center(
                        raw_image,
                        center_x,
                        center_y,
                        radius_px,
                        max(2.0, 0.30 * pitch_px),
                    )
                    for center_x, center_y in predicted
                ]
                for center_x, center_y in refined:
                    metrics = radial_edge_metrics(image, center_x, center_y, pitch_px)
                    rows.append(
                        {
                            "sigma_px": sigma,
                            "sequence": sequence_name,
                            "magnification": sequence["magnification"],
                            "frame_index": frame_index,
                            "transition_width_nm": float(metrics["transition_width_px"])
                            * um_per_px
                            * 1000.0,
                            "normalized_slope_per_px": metrics["normalized_slope_per_px"],
                            "signed_contrast_8bit": metrics["signed_contrast_8bit"],
                            "valid_angles": metrics["valid_angles"],
                        }
                    )

    per_pillar = pd.DataFrame(rows)
    expected_rows = len(displacement) * 120 * 9
    if len(per_pillar) != expected_rows:
        raise RuntimeError(f"Expected {expected_rows} rows, found {len(per_pillar)}")
    valid_fraction = float(per_pillar.transition_width_nm.notna().mean())
    if valid_fraction < 0.98:
        raise RuntimeError(f"Only {valid_fraction:.3%} smoothing-control edges are valid")
    per_pillar.to_csv(
        control_root / "gaussian_smoothing_edge_width_per_pillar.csv",
        index=False,
        encoding="utf-8-sig",
    )
    edge = (
        per_pillar.groupby(["sigma_px", "magnification"], as_index=False)
        .agg(
            observation_count=("transition_width_nm", "count"),
            median_transition_width_nm=("transition_width_nm", "median"),
            median_normalized_slope_per_px=("normalized_slope_per_px", "median"),
            median_signed_contrast_8bit=("signed_contrast_8bit", "median"),
        )
    )
    wide = edge.pivot(index="sigma_px", columns="magnification")
    wide.columns = [f"{metric}_{magnification}" for metric, magnification in wide.columns]
    wide = wide.reset_index()
    summary = displacement.merge(wide, on="sigma_px", validate="one_to_one")
    summary.to_csv(
        control_root / "gaussian_smoothing_control_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    manifest = {
        "purpose": "Pair the direct Gaussian-smoothing displacement control with identical 10-90 percent edge-width measurements",
        "valid_edge_fraction": valid_fraction,
        "locked_step_count_per_sigma": 120,
        "pillar_count_per_step": 9,
        "summary": summary.to_dict(orient="records"),
    }
    (control_root / "gaussian_smoothing_edge_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(summary.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-root", type=Path, required=True)
    arguments = parser.parse_args()
    analyze(arguments.control_root.resolve())
