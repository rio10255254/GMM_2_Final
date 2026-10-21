from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d


EXPERIMENT = Path(__file__).resolve().parent
EVIDENCE = Path(r"D:\GMM_2_Final\Thesis_MOSR_Evidence\Final_Data_Figures")
CURRENT = EVIDENCE / "01_CURRENT_THESIS_RESULTS_V42_CENTER9"
NETWORK = EVIDENCE / "04_V42_NEURAL_NETWORK_RESULTS"


def read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"Could not read {path}")
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.dtype == np.uint16:
        image = np.rint(image.astype(np.float32) / 257.0).clip(0, 255).astype(np.uint8)
    elif image.dtype != np.uint8:
        image = np.rint(image.astype(np.float32)).clip(0, 255).astype(np.uint8)
    return image


def refine_dark_center(
    image: np.ndarray,
    center_x: float,
    center_y: float,
    radius_px: float,
    search_px: float,
) -> tuple[float, float]:
    extent = int(np.ceil(radius_px * 1.50 + search_px))
    x0 = max(0, int(np.floor(center_x)) - extent)
    x1 = min(image.shape[1], int(np.floor(center_x)) + extent + 1)
    y0 = max(0, int(np.floor(center_y)) - extent)
    y1 = min(image.shape[0], int(np.floor(center_y)) + extent + 1)
    patch = image[y0:y1, x0:x1].astype(np.float32)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    refined_x = float(center_x)
    refined_y = float(center_y)
    for _ in range(3):
        distance = np.hypot(xx - refined_x, yy - refined_y)
        mask = distance <= radius_px * 1.30
        values = patch[mask]
        if values.size == 0:
            return float(center_x), float(center_y)
        core = float(np.percentile(values, 15))
        background = float(np.percentile(values, 85))
        threshold = core + 0.55 * (background - core)
        weights = np.maximum(threshold - patch, 0.0) * mask
        total = float(weights.sum())
        if total <= 1.0e-6:
            return float(center_x), float(center_y)
        refined_x = float((weights * xx).sum() / total)
        refined_y = float((weights * yy).sum() / total)
    if np.hypot(refined_x - center_x, refined_y - center_y) > search_px:
        return float(center_x), float(center_y)
    return refined_x, refined_y


def crossing_radius(profile: np.ndarray, radii: np.ndarray, level: float) -> float:
    indices = np.flatnonzero(profile >= level)
    if len(indices) == 0 or indices[0] == 0:
        return float("nan")
    index = int(indices[0])
    y0 = float(profile[index - 1])
    y1 = float(profile[index])
    if abs(y1 - y0) < 1.0e-12:
        return float(radii[index])
    fraction = (float(level) - y0) / (y1 - y0)
    return float(radii[index - 1] + fraction * (radii[index] - radii[index - 1]))


def radial_edge_metrics(
    image: np.ndarray,
    center_x: float,
    center_y: float,
    pitch_px: float,
    angle_count: int = 360,
) -> dict[str, float | int]:
    radial_step = 0.05
    radii = np.arange(0.0, 0.38 * pitch_px + radial_step * 0.5, radial_step, dtype=np.float32)
    angles = np.linspace(0.0, 2.0 * np.pi, angle_count, endpoint=False, dtype=np.float32)
    sample_x = center_x + np.cos(angles)[:, None] * radii[None, :]
    sample_y = center_y + np.sin(angles)[:, None] * radii[None, :]
    samples = cv2.remap(
        image.astype(np.float32),
        sample_x.astype(np.float32),
        sample_y.astype(np.float32),
        interpolation=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    samples = gaussian_filter1d(samples, sigma=2.15, axis=1, mode="nearest")
    core = float(np.median(samples[:, radii <= 0.07 * pitch_px]))
    background_mask = (radii >= 0.30 * pitch_px) & (radii <= 0.36 * pitch_px)
    background = float(np.median(samples[:, background_mask]))
    contrast = background - core
    if contrast <= 1.0e-6:
        return {
            "valid_angles": 0,
            "transition_width_px": float("nan"),
            "normalized_slope_per_px": float("nan"),
            "signed_contrast_8bit": core - background,
            "core_8bit": core,
            "background_8bit": background,
        }
    level10 = core + 0.10 * contrast
    level90 = core + 0.90 * contrast
    widths: list[float] = []
    for profile in samples:
        r10 = crossing_radius(profile, radii, level10)
        r90 = crossing_radius(profile, radii, level90)
        if np.isfinite(r10) and np.isfinite(r90) and r90 >= r10:
            widths.append(r90 - r10)
    valid = len(widths)
    width = float(np.median(widths)) if valid >= int(np.ceil(0.90 * angle_count)) else float("nan")
    slope = 0.8 / width if np.isfinite(width) and width > 0 else float("nan")
    return {
        "valid_angles": valid,
        "transition_width_px": width,
        "normalized_slope_per_px": slope,
        "signed_contrast_8bit": core - background,
        "core_8bit": core,
        "background_8bit": background,
    }


def truthy(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def analyze(results_root: Path) -> None:
    output = results_root / "analysis"
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads(
        (CURRENT / "config" / "sequence_center9_50x20x.json").read_text(encoding="utf-8")
    )["sequences"]
    selected = pd.read_csv(NETWORK / "tables" / "top30_raw_motion_selection.csv")
    selected = selected.loc[truthy(selected.top30_raw_motion_selected)].copy()
    if len(selected) != 120:
        raise RuntimeError(f"Expected 120 locked steps, found {len(selected)}")
    anchors = pd.read_csv(
        results_root / "displacement_audit" / "tables" / "session_anchor_summary.csv"
    )
    if not truthy(anchors.anchor_success).all():
        raise RuntimeError("At least one session anchor is invalid")

    rows: list[dict] = []
    for sequence_name, sequence_rows in selected.groupby("sequence", sort=False):
        sequence = config[sequence_name]
        centers0 = np.asarray([[row[1], row[2]] for row in sequence["centers"]], dtype=float)
        pillar_ids = [int(row[0]) for row in sequence["centers"]]
        pitch_px = float(sequence["pitch_px"])
        radius_px = float(sequence["radius_px"])
        step_px = float(sequence["expected_signed_dx_px"])
        um_per_px = float(sequence["object_um_per_px"])
        raw_dir = Path(sequence["raw_dir"])
        mosr_dir = Path(sequence["v42_dir"])
        base_dir = results_root / "real_inference" / "sequences" / sequence_name

        for _, selected_row in sequence_rows.sort_values("end_frame_index").iterrows():
            frame_index = int(selected_row.end_frame_index)
            filename = f"frame_{frame_index:04d}.bmp"
            paths = {
                "Raw": raw_dir / filename,
                "Base U-Net": base_dir / filename,
                "MOSR": mosr_dir / filename,
            }
            if not all(path.exists() for path in paths.values()):
                missing = [str(path) for path in paths.values() if not path.exists()]
                raise FileNotFoundError(f"Missing edge-analysis frame(s): {missing}")
            images = {method: read_gray(path) for method, path in paths.items()}
            anchor = anchors.loc[
                (anchors.sequence == sequence_name)
                & (anchors.start_frame_index <= frame_index)
                & (anchors.end_frame_index >= frame_index)
            ]
            if len(anchor) != 1:
                raise RuntimeError(
                    f"{sequence_name} frame {frame_index}: expected one session anchor, found {len(anchor)}"
                )
            anchor = anchor.iloc[0]
            within_session_index = frame_index - int(anchor.start_frame_index)
            predicted = centers0 + np.asarray(
                [
                    float(anchor.anchor_offset_x_px) + within_session_index * step_px,
                    float(anchor.anchor_offset_y_px),
                ]
            )
            refined = np.asarray(
                [
                    refine_dark_center(
                        images["Raw"],
                        center_x,
                        center_y,
                        radius_px,
                        max(2.0, 0.30 * pitch_px),
                    )
                    for center_x, center_y in predicted
                ],
                dtype=float,
            )
            for method, image in images.items():
                for pillar_id, (predicted_x, predicted_y), (center_x, center_y) in zip(
                    pillar_ids, predicted, refined
                ):
                    metrics = radial_edge_metrics(image, center_x, center_y, pitch_px)
                    rows.append(
                        {
                            "sequence": sequence_name,
                            "magnification": sequence["magnification"],
                            "nominal_step_um": float(sequence["nominal_step_um"]),
                            "frame_index": frame_index,
                            "pillar_id": pillar_id,
                            "method": method,
                            "predicted_center_x_px": predicted_x,
                            "predicted_center_y_px": predicted_y,
                            "center_x_px": center_x,
                            "center_y_px": center_y,
                            "raw_refinement_shift_px": float(
                                np.hypot(center_x - predicted_x, center_y - predicted_y)
                            ),
                            "transition_width_px": metrics["transition_width_px"],
                            "transition_width_nm": float(metrics["transition_width_px"])
                            * um_per_px
                            * 1000.0,
                            "normalized_slope_per_px": metrics["normalized_slope_per_px"],
                            "signed_contrast_8bit": metrics["signed_contrast_8bit"],
                            "core_8bit": metrics["core_8bit"],
                            "background_8bit": metrics["background_8bit"],
                            "valid_angles": metrics["valid_angles"],
                        }
                    )

    per_pillar = pd.DataFrame(rows)
    if len(per_pillar) != 120 * 9 * 3:
        raise RuntimeError(f"Unexpected edge row count: {len(per_pillar)}")
    per_pillar.to_csv(
        output / "base_unet_edge_width_per_pillar_top30.csv",
        index=False,
        encoding="utf-8-sig",
    )
    valid_fraction = float(per_pillar.transition_width_nm.notna().mean())
    if valid_fraction < 0.98:
        raise RuntimeError(f"Only {valid_fraction:.3%} edge widths are valid")

    per_step = (
        per_pillar.groupby(
            ["sequence", "magnification", "nominal_step_um", "frame_index", "method"],
            as_index=False,
        )
        .agg(
            median_transition_width_nm=("transition_width_nm", "median"),
            median_normalized_slope_per_px=("normalized_slope_per_px", "median"),
            median_signed_contrast_8bit=("signed_contrast_8bit", "median"),
            valid_pillars=("transition_width_nm", "count"),
        )
    )
    per_step.to_csv(
        output / "base_unet_edge_width_per_step_top30.csv", index=False, encoding="utf-8-sig"
    )
    summary = (
        per_pillar.groupby(["magnification", "method"], as_index=False)
        .agg(
            observation_count=("transition_width_nm", "count"),
            median_transition_width_nm=("transition_width_nm", "median"),
            mean_transition_width_nm=("transition_width_nm", "mean"),
            std_transition_width_nm=("transition_width_nm", "std"),
            median_normalized_slope_per_px=("normalized_slope_per_px", "median"),
            median_signed_contrast_8bit=("signed_contrast_8bit", "median"),
        )
    )
    summary.to_csv(
        output / "base_unet_edge_width_summary_top30.csv", index=False, encoding="utf-8-sig"
    )

    displacement = pd.read_csv(output / "base_unet_displacement_top30_per_step.csv")
    mosr = pd.read_csv(
        NETWORK
        / "source_validation"
        / "wiener_baseline_20260715"
        / "tables"
        / "three_way_displacement_per_step.csv"
    )
    base_metrics = displacement[
        ["sequence", "end_frame_index", "base_unet_within_grid_nm"]
    ].rename(columns={"end_frame_index": "frame_index"})
    raw_mosr = mosr[
        ["sequence", "end_frame_index", "raw_within_grid_nm", "v42_within_grid_nm"]
    ].rename(columns={"end_frame_index": "frame_index"})
    step_wide = per_step.pivot_table(
        index=["sequence", "magnification", "nominal_step_um", "frame_index"],
        columns="method",
        values="median_transition_width_nm",
    ).reset_index()
    step_wide = step_wide.merge(base_metrics, on=["sequence", "frame_index"], validate="one_to_one")
    step_wide = step_wide.merge(raw_mosr, on=["sequence", "frame_index"], validate="one_to_one")
    correlations: list[dict] = []
    sequence_correlations: list[dict] = []
    for method, width_column, disagreement_column in [
        ("Raw", "Raw", "raw_within_grid_nm"),
        ("Base U-Net", "Base U-Net", "base_unet_within_grid_nm"),
        ("MOSR", "MOSR", "v42_within_grid_nm"),
    ]:
        width = step_wide[width_column]
        disagreement = step_wide[disagreement_column]
        width_centered = width - step_wide.groupby("sequence")[width_column].transform("mean")
        disagreement_centered = disagreement - step_wide.groupby("sequence")[
            disagreement_column
        ].transform("mean")
        width_rank = step_wide.groupby("sequence")[width_column].rank(method="average")
        disagreement_rank = step_wide.groupby("sequence")[disagreement_column].rank(
            method="average"
        )
        correlations.append(
            {
                "method": method,
                "step_count": int(len(step_wide)),
                "median_transition_width_nm": float(width.median()),
                "mean_within_grid_nm": float(disagreement.mean()),
                "pearson_width_vs_disagreement": float(width.corr(disagreement, method="pearson")),
                "spearman_width_vs_disagreement": float(width.corr(disagreement, method="spearman")),
                "within_sequence_pearson": float(
                    width_centered.corr(disagreement_centered, method="pearson")
                ),
                "within_sequence_spearman": float(
                    width_rank.corr(disagreement_rank, method="pearson")
                ),
            }
        )
        for sequence_name, group in step_wide.groupby("sequence", sort=False):
            sequence_correlations.append(
                {
                    "method": method,
                    "sequence": sequence_name,
                    "magnification": group.magnification.iloc[0],
                    "nominal_step_um": float(group.nominal_step_um.iloc[0]),
                    "step_count": int(len(group)),
                    "median_transition_width_nm": float(group[width_column].median()),
                    "mean_within_grid_nm": float(group[disagreement_column].mean()),
                    "pearson_width_vs_disagreement": float(
                        group[width_column].corr(group[disagreement_column], method="pearson")
                    ),
                    "spearman_width_vs_disagreement": float(
                        group[width_column].corr(group[disagreement_column], method="spearman")
                    ),
                }
            )
    correlation_table = pd.DataFrame(correlations)
    correlation_table.to_csv(
        output / "base_unet_smoothing_hypothesis_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(sequence_correlations).to_csv(
        output / "base_unet_smoothing_hypothesis_by_sequence.csv",
        index=False,
        encoding="utf-8-sig",
    )
    step_wide.to_csv(
        output / "base_unet_edge_disagreement_per_step.csv", index=False, encoding="utf-8-sig"
    )

    manifest = {
        "purpose": "Test whether Base U-Net displacement stability is explained by edge smoothing",
        "locked_step_count": int(step_wide.shape[0]),
        "pillar_observation_count": int(per_pillar.shape[0]),
        "valid_edge_fraction": valid_fraction,
        "raw_refinement_shift_px": {
            "median": float(per_pillar.raw_refinement_shift_px.median()),
            "p95": float(per_pillar.raw_refinement_shift_px.quantile(0.95)),
            "maximum": float(per_pillar.raw_refinement_shift_px.max()),
        },
        "shared_raw_refined_centers": True,
        "identical_radial_rule_for_all_methods": True,
        "summary": summary.to_dict(orient="records"),
        "smoothing_hypothesis": correlation_table.to_dict(orient="records"),
    }
    (output / "base_unet_edge_stability_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(summary.to_string(index=False))
    print(correlation_table.to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, required=True)
    arguments = parser.parse_args()
    analyze(arguments.results_root.resolve())
