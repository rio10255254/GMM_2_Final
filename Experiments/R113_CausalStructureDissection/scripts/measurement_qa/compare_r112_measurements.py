"""Reproducibly compare corrected R113 metrics with the quantized R112 metrics."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[2]
R112 = Path(str(PROJECT_ROOT / 'Experiments/R112_V42R109GMFMechanismDecomposition'))
NEW_DIR = ROOT / "results" / "measurement_qa"
ARMS = ("Raw", "V42 E120", "R109 E48")


def correlation(group: pd.DataFrame, metric: str) -> tuple[float | None, float | None]:
    if group[metric].nunique() < 2:
        return None, None
    rho, p_value = spearmanr(group[metric], group["score_external"])
    return float(rho), float(p_value)


def main() -> int:
    old = pd.read_csv(R112 / "results" / "image_mechanisms" / "frame_features.csv")
    new = pd.read_csv(NEW_DIR / "corrected_frame_metrics.csv", encoding="utf-8-sig")
    merged = new.merge(
        old[
            [
                "arm",
                "frame_name",
                "ring_peak_radius_px",
                "ring_halfmax_width_px",
                "ring_contrast_gray",
                "high_frequency_rms_gray",
                "low_frequency_std_gray",
            ]
        ],
        on=["arm", "frame_name"],
        validate="one_to_one",
        suffixes=("_new", "_old"),
    )
    if len(merged) != 300:
        raise RuntimeError(f"Expected a complete 300-row one-to-one comparison, got {len(merged)}")

    rows: list[dict[str, object]] = []
    for arm in ARMS:
        group = merged.loc[merged["arm"] == arm].copy()
        old_width_rho, old_width_p = correlation(
            group.rename(columns={"ring_halfmax_width_px_old": "metric"}), "metric"
        )
        new_width_rho, new_width_p = correlation(
            group.rename(columns={"ring_halfmax_width_px_new": "metric"}), "metric"
        )
        new_center_rho, new_center_p = correlation(
            group.rename(columns={"ring_halfmax_center_radius_px": "metric"}), "metric"
        )
        rows.append(
            {
                "arm": arm,
                "frames": int(len(group)),
                "old_peak_unique_values": int(group["ring_peak_radius_px_old"].nunique()),
                "new_peak_unique_values": int(group["ring_peak_radius_px_new"].nunique()),
                "old_peak_std_px": float(group["ring_peak_radius_px_old"].std(ddof=1)),
                "new_primary_center_mean_px": float(group["ring_halfmax_center_radius_px"].mean()),
                "new_primary_center_std_px": float(group["ring_halfmax_center_radius_px"].std(ddof=1)),
                "new_primary_center_vs_score_rho": new_center_rho,
                "new_primary_center_vs_score_p_value": new_center_p,
                "new_peak_std_px": float(group["ring_peak_radius_px_new"].std(ddof=1)),
                "old_width_unique_values": int(group["ring_halfmax_width_px_old"].nunique()),
                "new_width_unique_values": int(group["ring_halfmax_width_px_new"].nunique()),
                "old_width_mean_px": float(group["ring_halfmax_width_px_old"].mean()),
                "new_width_mean_px": float(group["ring_halfmax_width_px_new"].mean()),
                "old_width_std_px": float(group["ring_halfmax_width_px_old"].std(ddof=1)),
                "new_width_std_px": float(group["ring_halfmax_width_px_new"].std(ddof=1)),
                "old_width_vs_score_rho": old_width_rho,
                "old_width_vs_score_p_value": old_width_p,
                "new_width_vs_score_rho": new_width_rho,
                "new_width_vs_score_p_value": new_width_p,
                "old_full_crop_high_frequency_rms_median_gray": float(group["high_frequency_rms_gray"].median()),
                "new_full_crop_high_frequency_rms_median_gray": float(group["full_crop_high_frequency_rms_gray"].median()),
                "new_annulus_high_frequency_rms_median_gray": float(group["annulus_high_frequency_rms_gray"].median()),
                "new_full_crop_low_frequency_std_median_gray": float(group["full_crop_low_frequency_std_gray"].median()),
                "new_annulus_low_frequency_std_median_gray": float(group["annulus_low_frequency_std_gray"].median()),
            }
        )
    comparison = pd.DataFrame(rows)
    comparison.to_csv(NEW_DIR / "r112_correction_comparison.csv", index=False, encoding="utf-8-sig", float_format="%.10g")

    result = {
        "status": "complete",
        "generated_local": datetime.now().astimezone().isoformat(),
        "matched_rows": int(len(merged)),
        "per_arm": json.loads(comparison.to_json(orient="records")),
        "quality_findings": [
            {
                "severity": "high",
                "finding": "R112 peak-radius variance was erased by floor-radius quantization.",
                "evidence": "Each arm had one old peak value; the corrected primary half-maximum centre is continuous and has non-zero standard deviation.",
                "impact": "R112 cannot support a claim of invariant ring radius; the brightest local peak is retained only as a diagnostic because broad profiles can have tied maxima.",
            },
            {
                "severity": "high",
                "finding": "R112 made V42 ring width appear perfectly invariant.",
                "evidence": "V42 old width standard deviation was 0 px; corrected standard deviation is non-zero.",
                "impact": "V42 remains the most stable arm here, but not perfectly stable.",
            },
            {
                "severity": "high",
                "finding": "The old width-versus-GMF correlations do not survive continuous native-resolution remeasurement.",
                "evidence": "Corrected width correlations are weak and non-significant for all three arms.",
                "impact": "Ring-width variation is not established as a causal explanation for the external GMF ranking.",
            },
            {
                "severity": "medium",
                "finding": "Texture magnitude depends materially on spatial support.",
                "evidence": "Dynamic half-maximum annulus and full-crop high/low-frequency statistics differ in every frame.",
                "impact": "Annulus and full-crop values must be named and interpreted separately.",
            },
        ],
        "retained_directional_finding": "At native resolution V42 has the lowest high-frequency magnitude and R109 the highest, on both full-crop and true-annulus support.",
    }
    (NEW_DIR / "r112_correction_comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(json.dumps({"status": "complete", "matched_rows": len(merged)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
