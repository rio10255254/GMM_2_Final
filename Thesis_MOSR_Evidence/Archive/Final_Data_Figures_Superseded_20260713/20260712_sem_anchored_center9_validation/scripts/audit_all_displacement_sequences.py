from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from displacement_audit_core import (
    AnchorResult,
    apply_raw_eligibility,
    classify_nm_difference,
    detect_sessions,
    locate_session_anchor,
    summarize_paired_population,
    track_local_2d,
)
from pillar_motion_core import TrackerConfig, TrackingResult, track_pillar_grid
PROJECT_ROOT = Path(__file__).resolve().parents[5]


PACKAGE = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PACKAGE / "config" / "sequence_center9.json"
MAPPING_50X = Path(str(PROJECT_ROOT / '20260702_100MG_displacement_analysis/input_mapping.csv'))
MAPPING_20X = Path(str(PROJECT_ROOT / '20260704_20x_5x_analysis/input_mapping.csv'))
EDGE_PHASE_REFERENCE = Path(
    str(PROJECT_ROOT / '20260704_20x_5x_analysis/phase_algorithm_final_summary/edge_phase_primary_gap30_summary_um.csv')
)
APPROVED_SEQUENCES = (
    "50x_x_0p5um",
    "50x_x_1um",
    "20x_0p5um",
    "20x_1um",
)
MAPPING_GROUPS = {
    "50x_x_0p5um": (MAPPING_50X, "x_0p5um"),
    "50x_x_1um": (MAPPING_50X, "x_1um"),
    "20x_0p5um": (MAPPING_20X, "20x_0p5um"),
    "20x_1um": (MAPPING_20X, "20x_1um"),
}
TOLERANCES = (0.20, 0.25, 0.30)


def _read_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)
    return image


def _tracker_config(sequence: dict[str, Any]) -> TrackerConfig:
    return TrackerConfig(
        radius_px=float(sequence["radius_px"]),
        pitch_px=float(sequence["pitch_px"]),
        polarity=str(sequence["polarity"]),
        search_radius_px=float(sequence["search_radius_px"]),
        min_valid_pillars=int(sequence["min_valid_pillars"]),
        min_edge_strength=float(sequence["min_edge_strength"]),
    )


def _load_mapping(sequence_name: str) -> pd.DataFrame:
    path, group = MAPPING_GROUPS[sequence_name]
    table = pd.read_csv(path)
    table = table.loc[table["group"] == group].copy()
    table["frame_index"] = pd.to_numeric(table["index"], errors="raise").astype(int)
    table["timestamp"] = pd.to_datetime(table["timestamp"], errors="raise")
    table = table.sort_values("frame_index").reset_index(drop=True)
    expected = list(range(len(table)))
    if table["frame_index"].tolist() != expected:
        raise ValueError(f"{sequence_name} mapping is not contiguous")
    return detect_sessions(table, threshold_seconds=60.0)


def _protected_files(allowed_roots: tuple[Path, ...]) -> dict[str, str]:
    allowed = tuple(root.resolve() for root in allowed_roots)

    def is_allowed(path: Path) -> bool:
        resolved = path.resolve()
        return any(resolved == root or root in resolved.parents for root in allowed)

    files = [
        PACKAGE / "REPORT.md",
        PACKAGE / "manifest.json",
        PACKAGE / "reproducibility_sha256.csv",
    ]
    for root in (PACKAGE / "cd", PACKAGE / "displacement", PACKAGE / "thesis_50x_20x"):
        files.extend(path for path in root.rglob("*") if path.is_file())
    inventory: dict[str, str] = {}
    for path in sorted(set(files), key=lambda item: str(item).lower()):
        if is_allowed(path):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        inventory[str(path.resolve())] = digest
    return inventory


def _inventory_digest(inventory: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, value in sorted(inventory.items()):
        digest.update(path.encode("utf-8"))
        digest.update(value.encode("ascii"))
    return digest.hexdigest()


def _clean_output(path: Path) -> None:
    resolved = path.resolve()
    protected = {
        PACKAGE.resolve(),
        (PACKAGE / "cd").resolve(),
        (PACKAGE / "displacement").resolve(),
    }
    if resolved in protected:
        raise ValueError("refusing to replace a protected audit directory")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _session_bounds(sessions: pd.DataFrame) -> list[tuple[int, int, int]]:
    bounds: list[tuple[int, int, int]] = []
    for session_id, group in sessions.groupby("session_id", sort=True):
        bounds.append(
            (
                int(session_id),
                int(group["frame_index"].min()),
                int(group["frame_index"].max()),
            )
        )
    return bounds


def _anchor_for_session(
    images: list[np.ndarray],
    centers: np.ndarray,
    *,
    pitch_px: float,
    start_frame: int,
) -> AnchorResult:
    if start_frame == 0:
        return AnchorResult(True, 0.0, 0.0, 1.0, 1.0, "")
    return locate_session_anchor(
        images[0], images[start_frame], centers, pitch_px=pitch_px
    )


def _empty_pair_rows(
    sequence_name: str,
    sequence: dict[str, Any],
    sessions: pd.DataFrame,
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    expected_signed_um = float(sequence["expected_signed_dx_px"]) * float(
        sequence["object_um_per_px"]
    )
    for end_frame in range(1, len(sessions)):
        start = sessions.iloc[end_frame - 1]
        end = sessions.iloc[end_frame]
        records.append(
            {
                "sequence": sequence_name,
                "magnification": sequence["magnification"],
                "nominal_step_um": float(sequence["nominal_step_um"]),
                "expected_signed_step_um": expected_signed_um,
                "start_frame_index": int(start["frame_index"]),
                "end_frame_index": int(end["frame_index"]),
                "start_timestamp": start["timestamp"].isoformat(sep=" "),
                "end_timestamp": end["timestamp"].isoformat(sep=" "),
                "gap_seconds": float(
                    (end["timestamp"] - start["timestamp"]).total_seconds()
                ),
                "start_session_id": int(start["session_id"]),
                "end_session_id": int(end["session_id"]),
                "cross_session": int(start["session_id"]) != int(end["session_id"]),
            }
        )
    return pd.DataFrame(records)


def _raw_segment_measurements(
    sequence_name: str,
    sequence: dict[str, Any],
    sessions: pd.DataFrame,
    raw_images: list[np.ndarray],
) -> tuple[pd.DataFrame, dict[int, dict[str, Any]]]:
    centers = np.asarray([[row[1], row[2]] for row in sequence["centers"]], dtype=float)
    pillar_ids = [str(int(row[0])) for row in sequence["centers"]]
    pairs = _empty_pair_rows(sequence_name, sequence, sessions)
    for column, default in (
        ("anchor_success", False),
        ("anchor_offset_x_px", np.nan),
        ("anchor_offset_y_px", np.nan),
        ("anchor_peak_score", np.nan),
        ("anchor_uniqueness_margin", np.nan),
        ("anchor_failure_reason", ""),
        ("raw_boundary_valid", False),
        ("raw_boundary_valid_pillars", 0),
        ("raw_boundary_dx_um", np.nan),
        ("raw_within_grid_nm", np.nan),
        ("raw_local_valid_pillars", 0),
        ("raw_local_min_match_score", np.nan),
        ("raw_local_dx_um", np.nan),
        ("raw_local_dy_um", np.nan),
        ("raw_local_pillar_dx_sd_nm", np.nan),
    ):
        pairs[column] = default

    runtime: dict[int, dict[str, Any]] = {}
    for session_id, start_frame, end_frame in _session_bounds(sessions):
        anchor = _anchor_for_session(
            raw_images,
            centers,
            pitch_px=float(sequence["pitch_px"]),
            start_frame=start_frame,
        )
        session_mask = pairs["end_session_id"] == session_id
        for column, value in (
            ("anchor_success", anchor.success),
            ("anchor_offset_x_px", anchor.offset_x_px),
            ("anchor_offset_y_px", anchor.offset_y_px),
            ("anchor_peak_score", anchor.peak_score),
            ("anchor_uniqueness_margin", anchor.uniqueness_margin),
            ("anchor_failure_reason", anchor.failure_reason),
        ):
            pairs.loc[session_mask, column] = value
        if not anchor.success or end_frame <= start_frame:
            runtime[session_id] = {"anchor": anchor, "raw_result": None}
            continue
        shifted = centers + np.asarray([anchor.offset_x_px, anchor.offset_y_px])
        initial_centers = [
            (pillar_id, float(x_px), float(y_px))
            for pillar_id, (x_px, y_px) in zip(pillar_ids, shifted)
        ]
        segment = raw_images[start_frame : end_frame + 1]
        raw_result = track_pillar_grid(
            segment,
            initial_centers,
            config=_tracker_config(sequence),
            expected_step_dx_px=float(sequence["expected_signed_dx_px"]),
        )
        local = track_local_2d(
            segment,
            shifted,
            radius_px=float(sequence["radius_px"]),
            expected_signed_dx_px=float(sequence["expected_signed_dx_px"]),
            object_um_per_px=float(sequence["object_um_per_px"]),
        )
        runtime[session_id] = {
            "anchor": anchor,
            "shifted_centers": shifted,
            "raw_result": raw_result,
        }
        for local_step in range(1, len(segment)):
            global_end = start_frame + local_step
            row_mask = pairs["end_frame_index"] == global_end
            boundary = raw_result.steps.loc[
                raw_result.steps["step_index"] == local_step
            ].iloc[0]
            local_row = local.loc[local["step_index"] == local_step].iloc[0]
            values = {
                "raw_boundary_valid": bool(boundary["analysis_valid"]),
                "raw_boundary_valid_pillars": int(boundary["valid_pillars"]),
                "raw_boundary_dx_um": float(boundary["consensus_dx_px"])
                * float(sequence["object_um_per_px"]),
                "raw_within_grid_nm": float(boundary["within_grid_disagreement_px"])
                * float(sequence["object_um_per_px"])
                * 1000.0,
                "raw_local_valid_pillars": int(local_row["local_valid_pillars"]),
                "raw_local_min_match_score": float(local_row["local_min_match_score"]),
                "raw_local_dx_um": float(local_row["local_dx_um"]),
                "raw_local_dy_um": float(local_row["local_dy_um"]),
                "raw_local_pillar_dx_sd_nm": float(
                    local_row["local_pillar_dx_sd_nm"]
                ),
            }
            for column, value in values.items():
                pairs.loc[row_mask, column] = value

    for tolerance in TOLERANCES:
        audited = apply_raw_eligibility(pairs, tolerance_fraction=tolerance)
        label = f"{int(round(tolerance * 100))}pct"
        pairs[f"raw_eligible_{label}"] = audited["raw_eligible"]
        pairs[f"raw_exclusion_reasons_{label}"] = audited["raw_exclusion_reasons"]
    return pairs, runtime


def _join_v42(
    raw_pairs: pd.DataFrame,
    sequence: dict[str, Any],
    v42_images: list[np.ndarray],
    runtime: dict[int, dict[str, Any]],
    sessions: pd.DataFrame,
) -> pd.DataFrame:
    result = raw_pairs.copy()
    for column, default in (
        ("v42_evaluable", False),
        ("v42_failure_reason", "cross_acquisition_session"),
        ("v42_boundary_valid", False),
        ("v42_boundary_valid_pillars", 0),
        ("v42_boundary_dx_um", np.nan),
        ("v42_within_grid_nm", np.nan),
        ("v42_local_valid_pillars", 0),
        ("v42_local_min_match_score", np.nan),
        ("v42_local_dx_um", np.nan),
        ("v42_local_dy_um", np.nan),
    ):
        result[column] = default

    pillar_ids = [str(int(row[0])) for row in sequence["centers"]]
    for session_id, start_frame, end_frame in _session_bounds(sessions):
        state = runtime[session_id]
        raw_tracking: TrackingResult | None = state.get("raw_result")
        if raw_tracking is None or end_frame <= start_frame:
            mask = (result["end_session_id"] == session_id) & ~result["cross_session"]
            result.loc[mask, "v42_failure_reason"] = "raw_anchor_or_tracking_unavailable"
            continue
        shifted = np.asarray(state["shifted_centers"], dtype=float)
        initial_centers = [
            (pillar_id, float(x_px), float(y_px))
            for pillar_id, (x_px, y_px) in zip(pillar_ids, shifted)
        ]
        segment = v42_images[start_frame : end_frame + 1]
        v42_tracking = track_pillar_grid(
            segment,
            initial_centers,
            config=_tracker_config(sequence),
            expected_step_dx_px=float(sequence["expected_signed_dx_px"]),
            shared_prediction_shifts=raw_tracking.prediction_shifts,
        )
        local = track_local_2d(
            segment,
            shifted,
            radius_px=float(sequence["radius_px"]),
            expected_signed_dx_px=float(sequence["expected_signed_dx_px"]),
            object_um_per_px=float(sequence["object_um_per_px"]),
        )
        for local_step in range(1, len(segment)):
            global_end = start_frame + local_step
            row_mask = result["end_frame_index"] == global_end
            boundary = v42_tracking.steps.loc[
                v42_tracking.steps["step_index"] == local_step
            ].iloc[0]
            local_row = local.loc[local["step_index"] == local_step].iloc[0]
            valid = bool(
                boundary["analysis_valid"] and int(boundary["valid_pillars"]) == 9
            )
            if valid:
                failure = ""
            elif not bool(boundary["analysis_valid"]):
                failure = "v42_boundary_invalid"
            else:
                failure = "not_all_nine_v42_boundary"
            values = {
                "v42_evaluable": valid,
                "v42_failure_reason": failure,
                "v42_boundary_valid": bool(boundary["analysis_valid"]),
                "v42_boundary_valid_pillars": int(boundary["valid_pillars"]),
                "v42_boundary_dx_um": float(boundary["consensus_dx_px"])
                * float(sequence["object_um_per_px"]),
                "v42_within_grid_nm": float(boundary["within_grid_disagreement_px"])
                * float(sequence["object_um_per_px"])
                * 1000.0,
                "v42_local_valid_pillars": int(local_row["local_valid_pillars"]),
                "v42_local_min_match_score": float(local_row["local_min_match_score"]),
                "v42_local_dx_um": float(local_row["local_dx_um"]),
                "v42_local_dy_um": float(local_row["local_dy_um"]),
            }
            for column, value in values.items():
                result.loc[row_mask, column] = value
    return result


def _reason_counts(values: pd.Series) -> str:
    counter: Counter[str] = Counter()
    for text in values.fillna(""):
        for reason in str(text).split(";"):
            if reason:
                counter[reason] += 1
    return json.dumps(dict(sorted(counter.items())), sort_keys=True)


def _summary_row(
    sequence: str,
    table: pd.DataFrame,
    mask: pd.Series,
    *,
    population: str,
    tolerance_fraction: float | None,
) -> dict[str, Any]:
    selected = table.loc[mask].copy()
    paired = selected.loc[selected["v42_evaluable"].astype(bool)].copy()
    metrics = summarize_paired_population(paired)
    row: dict[str, Any] = {
        "sequence": sequence,
        "magnification": table["magnification"].iloc[0],
        "nominal_step_um": float(table["nominal_step_um"].iloc[0]),
        "population": population,
        "tolerance_fraction": tolerance_fraction,
        "total_adjacent_pairs": len(table),
        "within_session_pairs": int((~table["cross_session"].astype(bool)).sum()),
        "raw_eligible_count": len(selected),
        "v42_evaluable_count_within_raw": int(selected["v42_evaluable"].sum()),
        "paired_comparison_count": len(paired),
        "raw_eligible_coverage_pct": len(selected) / len(table) * 100.0,
        "paired_coverage_within_raw_pct": (
            len(paired) / len(selected) * 100.0 if len(selected) else 0.0
        ),
        "raw_exclusion_reason_counts": _reason_counts(
            table.loc[
                ~mask,
                f"raw_exclusion_reasons_{int(round((tolerance_fraction or 0.25) * 100))}pct",
            ]
        ),
        "v42_failure_reason_counts_within_raw": _reason_counts(
            selected.loc[~selected["v42_evaluable"].astype(bool), "v42_failure_reason"]
        ),
    }
    row.update(metrics)
    row["step_sd_difference_v42_minus_raw_nm"] = (
        float(row["v42_signed_step_sd_nm"]) - float(row["raw_signed_step_sd_nm"])
    )
    row["step_sd_reduction_pct"] = (
        (float(row["raw_signed_step_sd_nm"]) - float(row["v42_signed_step_sd_nm"]))
        / float(row["raw_signed_step_sd_nm"])
        * 100.0
    )
    row["step_sd_direction"] = classify_nm_difference(
        float(row["raw_signed_step_sd_nm"]),
        float(row["v42_signed_step_sd_nm"]),
        tie_margin_nm=1.0,
    )
    row["within_grid_difference_v42_minus_raw_nm"] = (
        float(row["v42_mean_within_grid_nm"]) - float(row["raw_mean_within_grid_nm"])
    )
    row["within_grid_reduction_pct"] = (
        (float(row["raw_mean_within_grid_nm"]) - float(row["v42_mean_within_grid_nm"]))
        / float(row["raw_mean_within_grid_nm"])
        * 100.0
    )
    row["within_grid_direction"] = classify_nm_difference(
        float(row["raw_mean_within_grid_nm"]),
        float(row["v42_mean_within_grid_nm"]),
        tie_margin_nm=1.0,
    )
    return row


def _build_summaries(pairs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidate_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    population_rows: list[dict[str, Any]] = []
    for sequence in APPROVED_SEQUENCES:
        table = pairs.loc[pairs["sequence"] == sequence].copy()
        for tolerance in TOLERANCES:
            label = f"{int(round(tolerance * 100))}pct"
            mask = table[f"raw_eligible_{label}"].astype(bool)
            sensitivity_rows.append(
                _summary_row(
                    sequence,
                    table,
                    mask,
                    population=f"platform_valid_{label}",
                    tolerance_fraction=tolerance,
                )
            )
        primary = table["raw_eligible_25pct"].astype(bool)
        candidate_rows.append(
            _summary_row(
                sequence,
                table,
                primary,
                population="platform_valid_25pct",
                tolerance_fraction=0.25,
            )
        )
        population_rows.append(
            _summary_row(
                sequence,
                table,
                ~table["cross_session"].astype(bool),
                population="all_within_session",
                tolerance_fraction=None,
            )
        )
        population_rows.append(candidate_rows[-1].copy())
        population_rows.append(
            _summary_row(
                sequence,
                table,
                primary & (table["gap_seconds"] <= 10.0),
                population="platform_valid_regular_cadence",
                tolerance_fraction=0.25,
            )
        )
    candidate = pd.DataFrame(candidate_rows)
    sensitivity = pd.DataFrame(sensitivity_rows)
    populations = pd.DataFrame(population_rows)
    for sequence in APPROVED_SEQUENCES:
        rows = sensitivity.loc[sensitivity["sequence"] == sequence]
        for metric in ("step_sd_direction", "within_grid_direction"):
            robust = len(set(rows[metric])) == 1
            sensitivity.loc[rows.index, f"{metric}_robust_across_tolerances"] = robust
            candidate.loc[
                candidate["sequence"] == sequence,
                f"{metric}_robust_across_tolerances",
            ] = robust
    return candidate, sensitivity, populations


def _plot_sequence_trace(table: pd.DataFrame, output_path: Path) -> None:
    sequence = str(table["sequence"].iloc[0])
    fig, axes = plt.subplots(3, 1, figsize=(11.5, 8.4), sharex=True, constrained_layout=True)
    axes[0].bar(table["end_frame_index"], table["gap_seconds"], color="#777777")
    axes[0].axhline(10, color="#222222", linestyle="--", label="Regular cadence (10 s)")
    axes[0].axhline(60, color="#9467bd", linestyle=":", label="Session boundary (60 s)")
    axes[0].set_ylabel("Time gap (s)")
    axes[0].legend(ncol=2)
    axes[1].plot(table["end_frame_index"], table["raw_local_dx_um"], color="#d62728", marker="s", ms=3, label="Raw local 2D x")
    axes[1].axhline(float(table["expected_signed_step_um"].iloc[0]), color="#222222", linestyle="--")
    axes[1].set_ylabel("Raw dx (um)")
    axes[1].legend()
    axes[2].plot(table["end_frame_index"], table["raw_local_dy_um"], color="#2ca02c", marker="o", ms=3, label="Raw local 2D y")
    axes[2].axhline(0, color="#222222", linestyle="--")
    excluded = ~table["raw_eligible_25pct"].astype(bool)
    axes[2].scatter(table.loc[excluded, "end_frame_index"], table.loc[excluded, "raw_local_dy_um"], facecolors="none", edgecolors="#111111", s=75, label="Excluded at 25%")
    axes[2].set_ylabel("Raw dy (um)")
    axes[2].set_xlabel("End frame index")
    axes[2].legend()
    for axis in axes:
        axis.grid(True, alpha=0.2)
    fig.suptitle(f"{sequence}: blind Raw timing and 2D motion audit")
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _plot_selected_trace(table: pd.DataFrame, output_path: Path) -> None:
    selected = table.loc[
        table["raw_eligible_25pct"].astype(bool) & table["v42_evaluable"].astype(bool)
    ]
    fig, axis = plt.subplots(figsize=(11, 5.4), constrained_layout=True)
    axis.axhline(float(table["expected_signed_step_um"].iloc[0]), color="#222222", linestyle="--", label="Nominal command")
    selected = selected.sort_values("end_frame_index").copy()
    selected["run_id"] = (
        selected["end_frame_index"].diff().fillna(1).ne(1)
        | selected["end_session_id"].diff().fillna(0).ne(0)
    ).cumsum()
    first = True
    for _, run in selected.groupby("run_id", sort=True):
        axis.plot(
            run["end_frame_index"],
            run["raw_boundary_dx_um"],
            color="#d62728",
            marker="s",
            ms=4,
            label="Raw" if first else None,
        )
        axis.plot(
            run["end_frame_index"],
            run["v42_boundary_dx_um"],
            color="#1f77b4",
            marker="o",
            ms=4,
            label="V42 epoch 120" if first else None,
        )
        first = False
    axis.set_xlabel("End frame index")
    axis.set_ylabel("Signed measured step (um)")
    axis.set_title(f"{table['sequence'].iloc[0]}: fixed 25% platform-valid population")
    axis.grid(True, alpha=0.25)
    axis.legend()
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _plot_candidate(candidate: pd.DataFrame, output_path: Path, metric: str, title: str, ylabel: str) -> None:
    x = np.arange(len(candidate))
    width = 0.36
    raw_column = f"raw_{metric}"
    v42_column = f"v42_{metric}"
    fig, axis = plt.subplots(figsize=(10.5, 5.8), constrained_layout=True)
    raw = axis.bar(x - width / 2, candidate[raw_column], width, color="#d62728", label="Raw")
    v42 = axis.bar(x + width / 2, candidate[v42_column], width, color="#1f77b4", label="V42 epoch 120")
    axis.bar_label(raw, fmt="%.1f", padding=3)
    axis.bar_label(v42, fmt="%.1f", padding=3)
    axis.set_xticks(x, candidate["sequence"])
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    maximum = max(float(candidate[raw_column].max()), float(candidate[v42_column].max()))
    axis.set_ylim(0, maximum * 1.22 if maximum > 0 else 1)
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _plot_exclusions(pairs: pd.DataFrame, output_path: Path) -> None:
    reasons = [
        "cross_acquisition_session",
        "anchor_failed",
        "raw_boundary_invalid",
        "not_all_nine_raw_boundary",
        "raw_local_invalid",
        "raw_x_command_incomplete",
        "raw_y_cross_axis_excess",
        "raw_cross_method_disagreement",
    ]
    counts = []
    for sequence in APPROVED_SEQUENCES:
        text = pairs.loc[pairs["sequence"] == sequence, "raw_exclusion_reasons_25pct"].fillna("")
        counts.append([int(text.str.contains(reason, regex=False).sum()) for reason in reasons])
    array = np.asarray(counts).T
    unique = [
        int(
            (~pairs.loc[pairs["sequence"] == sequence, "raw_eligible_25pct"].astype(bool)).sum()
        )
        for sequence in APPROVED_SEQUENCES
    ]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8), constrained_layout=True)
    bars = axes[0].bar(APPROVED_SEQUENCES, unique, color="#4c78a8")
    axes[0].bar_label(bars, padding=3)
    axes[0].set_ylabel("Unique excluded steps")
    axes[0].set_title("Actual excluded-step count")
    image = axes[1].imshow(array, cmap="YlOrRd", aspect="auto", vmin=0)
    axes[1].set_xticks(np.arange(len(APPROVED_SEQUENCES)), APPROVED_SEQUENCES)
    axes[1].set_yticks(np.arange(len(reasons)), reasons)
    axes[1].set_title("Reason occurrences (one step may have multiple reasons)")
    for row in range(array.shape[0]):
        for column in range(array.shape[1]):
            axes[1].text(column, row, str(array[row, column]), ha="center", va="center")
    fig.colorbar(image, ax=axes[1], shrink=0.8, label="Occurrences")
    for axis in axes:
        axis.grid(False)
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _write_report(
    candidate: pd.DataFrame,
    populations: pd.DataFrame,
    sensitivity: pd.DataFrame,
    pairs: pd.DataFrame,
    output_path: Path,
) -> None:
    report = """# 四組位移實驗統一盲稽核

## 方法

四組資料固定追蹤同一組具有 SEM 尺寸的中心九顆圓柱。入選名單只使用原始拍攝時間與 Raw 二維運動建立；名單寫入並計算雜湊後才加入 V42。候選主表固定採用 25% 命令容差，沒有依 V42 結果挑選母體。

## 候選主表

| 資料組 | Raw有效/總步 | 配對步 | Raw SD (nm) | V42 SD (nm) | 穩定性 | Raw九圓柱 (nm) | V42九圓柱 (nm) | 局部一致性 |
|---|---:|---:|---:|---:|---|---:|---:|---|
"""
    for row in candidate.to_dict(orient="records"):
        report += (
            f"| {row['sequence']} | {row['raw_eligible_count']}/{row['total_adjacent_pairs']} | "
            f"{row['paired_comparison_count']} | {row['raw_signed_step_sd_nm']:.2f} | "
            f"{row['v42_signed_step_sd_nm']:.2f} | {row['step_sd_direction']} | "
            f"{row['raw_mean_within_grid_nm']:.2f} | {row['v42_mean_within_grid_nm']:.2f} | "
            f"{row['within_grid_direction']} |\n"
        )
    report += """

## 解讀原則

完整批次內母體、25%平台有效母體與正常拍攝節奏母體均保留在表格中。只有固定的25%平台有效母體是候選主表；其他母體不得因結果較漂亮而取代它。20%、25%、30%三個門檻的方向若不一致，報告會標記為不穩健。

平台命令是名義參考，不是獨立位置真值。本稽核只能支持重複性、平台運動合理性與九圓柱局部一致性比較。
"""
    excluded = pairs.loc[~pairs["raw_eligible_25pct"].astype(bool)]
    report += "\n## 固定規則排除明細\n\n"
    for sequence in APPROVED_SEQUENCES:
        rows = excluded.loc[excluded["sequence"] == sequence]
        if rows.empty:
            report += f"- `{sequence}`：無排除步，全部保留。\n"
        else:
            details = ", ".join(
                f"{int(row.end_frame_index)} ({row.raw_exclusion_reasons_25pct})"
                for row in rows.itertuples()
            )
            report += f"- `{sequence}`：{details}。\n"
    report += "\n## 門檻穩健性\n\n"
    for sequence in APPROVED_SEQUENCES:
        rows = sensitivity.loc[sensitivity["sequence"] == sequence]
        counts = "/".join(str(int(value)) for value in rows["raw_eligible_count"])
        sd_directions = ", ".join(rows["step_sd_direction"].astype(str))
        grid_directions = ", ".join(rows["within_grid_direction"].astype(str))
        report += (
            f"- `{sequence}`：20/25/30% 分別保留 {counts} 步；"
            f"位移穩定性方向為 {sd_directions}；九圓柱一致性方向為 {grid_directions}。\n"
        )
    output_path.write_text(report, encoding="utf-8")


def run_unified_audit(
    *,
    output_root: str | Path,
    candidate_root: str | Path | None = None,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Path]:
    output = Path(output_root)
    candidate_output = (
        Path(candidate_root) if candidate_root is not None else output / "candidate"
    )
    allowed_roots = (output, candidate_output)
    before_inventory = _protected_files(allowed_roots)
    before_digest = _inventory_digest(before_inventory)
    _clean_output(output)
    if candidate_output.resolve() != (output / "candidate").resolve():
        _clean_output(candidate_output)
    else:
        candidate_output.mkdir(parents=True, exist_ok=True)
    tables = output / "tables"
    figures = output / "figures"
    per_sequence_figures = figures / "per_sequence"
    tables.mkdir(parents=True, exist_ok=True)
    per_sequence_figures.mkdir(parents=True, exist_ok=True)
    (candidate_output / "tables").mkdir(parents=True, exist_ok=True)
    (candidate_output / "figures").mkdir(parents=True, exist_ok=True)

    configs = json.loads(Path(config_path).read_text(encoding="utf-8"))["sequences"]
    raw_tables: list[pd.DataFrame] = []
    runtime_by_sequence: dict[str, dict[str, Any]] = {}
    for sequence_name in APPROVED_SEQUENCES:
        sequence = configs[sequence_name]
        sessions = _load_mapping(sequence_name)
        raw_images = [
            _read_gray(Path(sequence["raw_dir"]) / f"frame_{index:04d}.bmp")
            for index in range(int(sequence["frame_count"]))
        ]
        raw_pairs, runtime = _raw_segment_measurements(
            sequence_name, sequence, sessions, raw_images
        )
        raw_tables.append(raw_pairs)
        runtime_by_sequence[sequence_name] = {
            "sessions": sessions,
            "runtime": runtime,
        }

    raw_lock = pd.concat(raw_tables, ignore_index=True)
    raw_lock_path = tables / "raw_eligibility_locked_before_v42.csv"
    raw_lock.to_csv(raw_lock_path, index=False)
    raw_lock_digest = hashlib.sha256(raw_lock_path.read_bytes()).hexdigest()
    raw_lock_hash_path = tables / "raw_eligibility_locked_before_v42.sha256"
    raw_lock_hash_path.write_text(
        f"{raw_lock_digest}  {raw_lock_path.name}\n", encoding="ascii"
    )

    joined_tables: list[pd.DataFrame] = []
    for sequence_name in APPROVED_SEQUENCES:
        sequence = configs[sequence_name]
        v42_images = [
            _read_gray(Path(sequence["v42_dir"]) / f"frame_{index:04d}.bmp")
            for index in range(int(sequence["frame_count"]))
        ]
        raw_pairs = raw_lock.loc[raw_lock["sequence"] == sequence_name].copy()
        joined = _join_v42(
            raw_pairs,
            sequence,
            v42_images,
            runtime_by_sequence[sequence_name]["runtime"],
            runtime_by_sequence[sequence_name]["sessions"],
        )
        joined_tables.append(joined)
    pairs = pd.concat(joined_tables, ignore_index=True)
    candidate, sensitivity, populations = _build_summaries(pairs)

    paths = {
        "raw_lock": raw_lock_path,
        "raw_lock_hash": raw_lock_hash_path,
        "pairs": tables / "all_adjacent_pairs_audit.csv",
        "candidate": tables / "candidate_platform_valid_25pct.csv",
        "sensitivity": tables / "tolerance_sensitivity_20_25_30pct.csv",
        "populations": tables / "all_population_comparisons.csv",
        "edge_phase_reference": tables / "predeclared_raw_edge_phase_reference.csv",
        "anchors": tables / "session_anchor_summary.csv",
        "exclusion_figure": figures / "exclusion_reason_counts.png",
        "candidate_sd_figure": figures / "candidate_step_stability.png",
        "candidate_grid_figure": figures / "candidate_nine_pillar_consistency.png",
        "report": output / "UNIFIED_AUDIT_REPORT_TW.md",
        "metadata": output / "metadata.json",
        "candidate_report": candidate_output / "CANDIDATE_READOUT_TW.md",
        "candidate_table": candidate_output / "tables" / "displacement_candidate_25pct.csv",
    }
    pairs.to_csv(paths["pairs"], index=False)
    candidate.to_csv(paths["candidate"], index=False)
    sensitivity.to_csv(paths["sensitivity"], index=False)
    populations.to_csv(paths["populations"], index=False)
    edge_phase = pd.read_csv(EDGE_PHASE_REFERENCE)
    edge_phase.loc[edge_phase["image"] == "Raw"].to_csv(
        paths["edge_phase_reference"], index=False
    )
    anchor_rows: list[dict[str, Any]] = []
    for sequence_name in APPROVED_SEQUENCES:
        sessions = runtime_by_sequence[sequence_name]["sessions"]
        runtime = runtime_by_sequence[sequence_name]["runtime"]
        for session_id, start_frame, end_frame in _session_bounds(sessions):
            anchor: AnchorResult = runtime[session_id]["anchor"]
            anchor_rows.append(
                {
                    "sequence": sequence_name,
                    "session_id": session_id,
                    "start_frame_index": start_frame,
                    "end_frame_index": end_frame,
                    "anchor_success": anchor.success,
                    "anchor_offset_x_px": anchor.offset_x_px,
                    "anchor_offset_y_px": anchor.offset_y_px,
                    "anchor_peak_score": anchor.peak_score,
                    "anchor_uniqueness_margin": anchor.uniqueness_margin,
                    "anchor_failure_reason": anchor.failure_reason,
                }
            )
    pd.DataFrame(anchor_rows).to_csv(paths["anchors"], index=False)
    candidate.to_csv(paths["candidate_table"], index=False)

    for sequence_name in APPROVED_SEQUENCES:
        table = pairs.loc[pairs["sequence"] == sequence_name]
        _plot_sequence_trace(
            table, per_sequence_figures / f"{sequence_name}_raw_motion_audit.png"
        )
        _plot_selected_trace(
            table, per_sequence_figures / f"{sequence_name}_selected_trace.png"
        )
    _plot_exclusions(pairs, paths["exclusion_figure"])
    _plot_candidate(
        candidate,
        paths["candidate_sd_figure"],
        "signed_step_sd_nm",
        "Fixed 25% platform-valid displacement stability",
        "Signed step sample standard deviation (nm)",
    )
    _plot_candidate(
        candidate,
        paths["candidate_grid_figure"],
        "mean_within_grid_nm",
        "Fixed 25% platform-valid nine-pillar consistency",
        "Mean within-grid disagreement (nm)",
    )
    _write_report(candidate, populations, sensitivity, pairs, paths["report"])
    shutil.copy2(paths["report"], paths["candidate_report"])
    for source in (paths["candidate_sd_figure"], paths["candidate_grid_figure"]):
        shutil.copy2(source, candidate_output / "figures" / source.name)

    metadata = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "sequences": list(APPROVED_SEQUENCES),
        "sem_pillar_ids": [22, 23, 24, 28, 29, 30, 34, 35, 36],
        "primary_population": "platform_valid_25pct",
        "tolerance_sensitivity": list(TOLERANCES),
        "session_gap_seconds": 60.0,
        "regular_cadence_seconds": 10.0,
        "raw_lock_sha256": raw_lock_digest,
        "protected_inventory_count": len(before_inventory),
        "protected_inventory_digest_before": before_digest,
        "v42_selection_role": "none; joined only after Raw lock",
        "claim_limit": "repeatability and physical consistency, not independent stage truth",
    }
    paths["metadata"].write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    after_inventory = _protected_files(allowed_roots)
    if before_inventory != after_inventory:
        changed = sorted(
            path
            for path in set(before_inventory) | set(after_inventory)
            if before_inventory.get(path) != after_inventory.get(path)
        )
        raise RuntimeError(f"protected evidence changed: {changed[:10]}")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the four-sequence blind displacement audit.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PACKAGE / "diagnostics" / "unified_displacement_step_audit",
    )
    parser.add_argument(
        "--candidate-root",
        type=Path,
        default=PACKAGE / "thesis_50x_20x" / "displacement_screened_candidate",
    )
    args = parser.parse_args()
    outputs = run_unified_audit(
        output_root=args.output_root, candidate_root=args.candidate_root
    )
    print(pd.read_csv(outputs["candidate"]).to_string(index=False))
    print(f"\nAudit: {args.output_root.resolve()}")
    print(f"Candidate: {args.candidate_root.resolve()}")


if __name__ == "__main__":
    main()
