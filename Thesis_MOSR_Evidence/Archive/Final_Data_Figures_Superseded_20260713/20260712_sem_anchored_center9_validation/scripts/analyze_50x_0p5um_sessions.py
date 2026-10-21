from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pillar_motion_core import TrackerConfig, track_pillar_grid
from run_center9_displacement import (
    _read_grayscale,
    build_common_pillar_comparison,
    summarize_case_steps,
)


PACKAGE = Path(__file__).resolve().parents[1]
DEFAULT_MAPPING = Path(
    r"D:\GMM_2_Final\20260702_100MG_displacement_analysis\input_mapping.csv"
)
DEFAULT_CONFIG = PACKAGE / "config" / "sequence_center9.json"


def load_acquisition_mapping(path: str | Path, *, group: str) -> pd.DataFrame:
    table = pd.read_csv(path)
    required = {
        "group",
        "index",
        "work_name",
        "original_name",
        "original_path",
        "work_path",
        "timestamp",
    }
    missing = required - set(table)
    if missing:
        raise ValueError(f"mapping is missing columns: {sorted(missing)}")
    selected = table.loc[table["group"].astype(str) == str(group)].copy()
    selected["frame_index"] = pd.to_numeric(selected["index"], errors="raise").astype(int)
    selected["timestamp"] = pd.to_datetime(selected["timestamp"], errors="raise")
    selected = selected.sort_values("frame_index").reset_index(drop=True)
    if selected["frame_index"].tolist() != list(range(51)):
        raise ValueError("50x 0.5 um mapping must contain frame indices 0..50 exactly once")
    if selected["work_name"].tolist() != [f"frame_{index:04d}.bmp" for index in range(51)]:
        raise ValueError("mapping work names do not match the locked frame convention")
    if selected["timestamp"].duplicated().any():
        raise ValueError("acquisition timestamps must be unique")
    return selected


def detect_timestamp_sessions(
    mapping: pd.DataFrame,
    *,
    threshold_seconds: float,
) -> pd.DataFrame:
    threshold = float(threshold_seconds)
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("threshold_seconds must be finite and positive")
    required = {"frame_index", "timestamp"}
    if not required.issubset(mapping):
        raise ValueError("mapping must contain frame_index and timestamp")
    result = mapping.copy()
    result = result.sort_values("frame_index").reset_index(drop=True)
    gaps = result["timestamp"].diff().dt.total_seconds()
    if (gaps.dropna() <= 0).any():
        raise ValueError("timestamps must be strictly increasing")
    result["gap_from_previous_seconds"] = gaps
    result["session_start"] = gaps.isna() | (gaps > threshold)
    result["session_id"] = result["session_start"].cumsum().astype(int)
    return result


def build_pair_audit(sessions: pd.DataFrame) -> pd.DataFrame:
    sessions = sessions.sort_values("frame_index").reset_index(drop=True)
    records: list[dict[str, Any]] = []
    for end_index in range(1, len(sessions)):
        start = sessions.iloc[end_index - 1]
        end = sessions.iloc[end_index]
        included = int(start["session_id"]) == int(end["session_id"])
        records.append(
            {
                "pair_index": end_index,
                "start_frame_index": int(start["frame_index"]),
                "end_frame_index": int(end["frame_index"]),
                "start_timestamp": start["timestamp"].isoformat(sep=" "),
                "end_timestamp": end["timestamp"].isoformat(sep=" "),
                "gap_seconds": float(
                    (end["timestamp"] - start["timestamp"]).total_seconds()
                ),
                "start_session_id": int(start["session_id"]),
                "end_session_id": int(end["session_id"]),
                "included_within_session": bool(included),
                "exclusion_reason": "" if included else "cross_acquisition_session",
            }
        )
    return pd.DataFrame(records)


def _load_sequence_config(path: str | Path) -> dict[str, Any]:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    return config["sequences"]["50x_x_0p5um"]


def _tracker_config(sequence: dict[str, Any]) -> TrackerConfig:
    return TrackerConfig(
        radius_px=float(sequence["radius_px"]),
        pitch_px=float(sequence["pitch_px"]),
        polarity=str(sequence["polarity"]),
        search_radius_px=float(sequence["search_radius_px"]),
        min_valid_pillars=int(sequence["min_valid_pillars"]),
        min_edge_strength=float(sequence["min_edge_strength"]),
    )


def _estimate_absolute_shifts(
    raw_images: list[np.ndarray],
    centers: np.ndarray,
    *,
    expected_step_dx_px: float,
    anchor_frames: tuple[int, ...] = (0, 27, 31),
) -> pd.DataFrame:
    template_half_size = 26
    search_radius = 20
    template_size = (2 * template_half_size + 1,) * 2
    search_size = (2 * (template_half_size + search_radius) + 1,) * 2

    def subpixel_peak(values: np.ndarray, index: int) -> float:
        if index <= 0 or index >= len(values) - 1:
            return float(index)
        left, center, right = (float(value) for value in values[index - 1 : index + 2])
        denominator = left - 2.0 * center + right
        if abs(denominator) < 1e-12:
            return float(index)
        offset = 0.5 * (left - right) / denominator
        return float(index) + float(np.clip(offset, -1.0, 1.0))

    records: list[dict[str, Any]] = []
    for frame_index in anchor_frames:
        coarse_x = float(expected_step_dx_px) * frame_index
        if frame_index == 0:
            offsets = np.zeros((len(centers), 2), dtype=float)
            scores = np.ones(len(centers), dtype=float)
        else:
            local_offsets: list[tuple[float, float]] = []
            local_scores: list[float] = []
            for center in centers:
                template = cv2.getRectSubPix(
                    raw_images[0], template_size, tuple(center.astype(np.float32))
                )
                predicted_center = center + np.asarray([coarse_x, 0.0])
                search = cv2.getRectSubPix(
                    raw_images[frame_index],
                    search_size,
                    tuple(predicted_center.astype(np.float32)),
                )
                match = cv2.matchTemplate(search, template, cv2.TM_CCOEFF_NORMED)
                _, score, _, peak = cv2.minMaxLoc(match)
                refined_x = subpixel_peak(match[peak[1], :], peak[0])
                refined_y = subpixel_peak(match[:, peak[0]], peak[1])
                local_offsets.append(
                    (refined_x - search_radius, refined_y - search_radius)
                )
                local_scores.append(float(score))
            offsets = np.asarray(local_offsets, dtype=float)
            scores = np.asarray(local_scores, dtype=float)
        residual = np.median(offsets, axis=0)
        records.append(
            {
                "frame_index": frame_index,
                "coarse_nominal_x_px": coarse_x,
                "residual_x_px": float(residual[0]),
                "absolute_x_px": coarse_x + float(residual[0]),
                "absolute_y_px": float(residual[1]),
                "anchor_match_score": float(np.median(scores)),
                "minimum_pillar_match_score": float(np.min(scores)),
                "anchor_x_spread_px": float(
                    1.4826 * np.median(np.abs(offsets[:, 0] - residual[0]))
                ),
                "anchor_y_spread_px": float(
                    1.4826 * np.median(np.abs(offsets[:, 1] - residual[1]))
                ),
            }
        )
    shifts = pd.DataFrame(records)
    if (shifts["minimum_pillar_match_score"] < 0.95).any():
        bad = shifts.loc[
            shifts["minimum_pillar_match_score"] < 0.95, "frame_index"
        ].tolist()
        raise ValueError(f"low-confidence session re-anchoring at frames {bad}")
    return shifts


def _plot_timestamp_gaps(
    pairs: pd.DataFrame,
    output_path: Path,
    *,
    threshold_seconds: float,
) -> None:
    colors = np.where(
        pairs["included_within_session"].astype(bool), "#4c78a8", "#d62728"
    )
    fig, axis = plt.subplots(figsize=(11, 5.4), constrained_layout=True)
    axis.bar(pairs["end_frame_index"], pairs["gap_seconds"], color=colors)
    axis.axhline(
        threshold_seconds,
        color="#222222",
        linestyle="--",
        label=f"Session threshold ({threshold_seconds:g} s)",
    )
    axis.set_yscale("log")
    axis.set_xlabel("End frame index")
    axis.set_ylabel("Time from previous frame (s, log scale)")
    axis.set_title("50x 0.5 um acquisition gaps define three sessions")
    axis.legend()
    axis.grid(axis="y", alpha=0.25)
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _plot_absolute_shift(shifts: pd.DataFrame, output_path: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 7.2), sharex=True, constrained_layout=True)
    axes[0].scatter(
        shifts["frame_index"],
        shifts["absolute_x_px"],
        color="#1f77b4",
        s=48,
    )
    axes[0].set_ylabel("Absolute x shift (px)")
    axes[1].scatter(
        shifts["frame_index"],
        shifts["absolute_y_px"],
        color="#d62728",
        s=48,
    )
    axes[1].set_ylabel("Absolute y shift (px)")
    axes[1].set_xlabel("Frame index")
    for axis in axes:
        axis.axvline(27, color="#555555", linestyle="--")
        axis.axvline(31, color="#555555", linestyle="--")
        axis.grid(True, alpha=0.25)
    fig.suptitle("Acquisition-session anchors reveal sample re-positioning")
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def _plot_corrected_steps(steps: pd.DataFrame, output_path: Path) -> None:
    fig, axis = plt.subplots(figsize=(11, 5.6), constrained_layout=True)
    axis.axhline(-0.5, color="#222222", linestyle="--", label="Nominal command (-0.5 um)")
    for session_id, session_steps in steps.groupby("session_id", sort=True):
        axis.plot(
            session_steps["end_frame_index"],
            session_steps["consensus_dx_um_raw"],
            color="#d62728",
            marker="s",
            markersize=3.5,
            label="Raw" if session_id == 1 else None,
        )
        axis.plot(
            session_steps["end_frame_index"],
            session_steps["consensus_dx_um_v42"],
            color="#1f77b4",
            marker="o",
            markersize=3.5,
            label="V42 epoch 120" if session_id == 1 else None,
        )
    for boundary in (27, 31):
        axis.axvspan(boundary - 0.35, boundary + 0.35, color="#d9d9d9", alpha=0.8)
    axis.set_xlabel("Global end frame index")
    axis.set_ylabel("Signed measured step (um)")
    axis.set_title("50x 0.5 um: all 48 within-session steps")
    axis.grid(True, alpha=0.25)
    axis.legend()
    fig.savefig(output_path, dpi=220, facecolor="white")
    plt.close(fig)


def run_session_analysis(
    *,
    output_root: str | Path,
    mapping_path: str | Path = DEFAULT_MAPPING,
    config_path: str | Path = DEFAULT_CONFIG,
    threshold_seconds: float = 60.0,
) -> dict[str, Path]:
    output = Path(output_root)
    tables = output / "tables"
    figures = output / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    mapping = load_acquisition_mapping(mapping_path, group="x_0p5um")
    sessions = detect_timestamp_sessions(mapping, threshold_seconds=threshold_seconds)
    starts = sessions.loc[sessions["session_start"], "frame_index"].tolist()
    if starts != [0, 27, 31]:
        raise ValueError(f"unexpected acquisition-session starts: {starts}")
    pairs = build_pair_audit(sessions)
    if len(pairs) != 50 or int(pairs["included_within_session"].sum()) != 48:
        raise ValueError("pair audit must reconcile to 48 included and two excluded")

    sequence = _load_sequence_config(config_path)
    names = [f"frame_{index:04d}.bmp" for index in range(51)]
    raw_images = [_read_grayscale(Path(sequence["raw_dir"]) / name) for name in names]
    v42_images = [_read_grayscale(Path(sequence["v42_dir"]) / name) for name in names]
    centers = np.asarray(
        [[float(row[1]), float(row[2])] for row in sequence["centers"]], dtype=float
    )
    pillar_ids = [str(int(row[0])) for row in sequence["centers"]]
    shifts = _estimate_absolute_shifts(
        raw_images,
        centers,
        expected_step_dx_px=float(sequence["expected_signed_dx_px"]),
    )
    config = _tracker_config(sequence)

    comparisons: list[pd.DataFrame] = []
    segment_rows: list[dict[str, Any]] = []
    boundaries = [(0, 26), (27, 30), (31, 50)]
    for session_id, (start_frame, end_frame) in enumerate(boundaries, 1):
        start_shift = shifts.loc[shifts["frame_index"] == start_frame].iloc[0]
        shifted_centers = centers + np.asarray(
            [start_shift["absolute_x_px"], start_shift["absolute_y_px"]]
        )
        initial_centers = [
            (pillar_id, float(x_px), float(y_px))
            for pillar_id, (x_px, y_px) in zip(pillar_ids, shifted_centers)
        ]
        raw_result = track_pillar_grid(
            raw_images[start_frame : end_frame + 1],
            initial_centers,
            config=config,
            expected_step_dx_px=float(sequence["expected_signed_dx_px"]),
        )
        v42_result = track_pillar_grid(
            v42_images[start_frame : end_frame + 1],
            initial_centers,
            config=config,
            expected_step_dx_px=float(sequence["expected_signed_dx_px"]),
            shared_prediction_shifts=raw_result.prediction_shifts,
        )
        comparison = build_common_pillar_comparison(
            raw_result.pillar_steps,
            v42_result.pillar_steps,
            frame_count=end_frame - start_frame + 1,
            min_common_pillars=int(sequence["min_valid_pillars"]),
            object_um_per_px=float(sequence["object_um_per_px"]),
        )
        comparison["session_id"] = session_id
        comparison["start_frame_index"] = comparison["step_index"] + start_frame - 1
        comparison["end_frame_index"] = comparison["step_index"] + start_frame
        comparisons.append(comparison)
        segment_rows.append(
            {
                "session_id": session_id,
                "start_frame_index": start_frame,
                "end_frame_index": end_frame,
                "frames": end_frame - start_frame + 1,
                "within_session_pairs": end_frame - start_frame,
                "anchor_absolute_x_px": start_shift["absolute_x_px"],
                "anchor_absolute_y_px": start_shift["absolute_y_px"],
                "anchor_match_score": start_shift["anchor_match_score"],
                "minimum_pillar_match_score": start_shift[
                    "minimum_pillar_match_score"
                ],
                "anchor_x_spread_px": start_shift["anchor_x_spread_px"],
                "anchor_y_spread_px": start_shift["anchor_y_spread_px"],
                "common_valid_pairs": int(comparison["common_valid"].sum()),
                "minimum_common_pillars": int(comparison["common_pillars"].min()),
            }
        )

    corrected = pd.concat(comparisons, ignore_index=True)
    if len(corrected) != 48 or not corrected["common_valid"].all():
        raise RuntimeError("not every within-session pair passed common-pillar validation")
    if not (corrected["common_pillars"] == 9).all():
        raise RuntimeError("corrected result must retain all nine common pillars")

    pair_measurements = pairs.merge(
        corrected.drop(columns=["step_index"]),
        on=["start_frame_index", "end_frame_index"],
        how="left",
        validate="one_to_one",
    )
    included = pair_measurements["included_within_session"].astype(bool)
    if pair_measurements.loc[included, "common_valid"].isna().any():
        raise RuntimeError("an included pair is missing a measurement")
    if pair_measurements.loc[~included, "common_valid"].notna().any():
        raise RuntimeError("a cross-session pair unexpectedly has a measurement")

    summary_rows: list[dict[str, Any]] = []
    for case, suffix in (("Raw", "raw"), ("V42 epoch 120", "v42")):
        case_steps = pd.DataFrame(
            {
                "step_index": np.arange(1, len(corrected) + 1),
                "analysis_valid": corrected["common_valid"].to_numpy(),
                "consensus_dx_px": corrected[f"consensus_dx_px_{suffix}"].to_numpy(),
                "within_grid_disagreement_px": corrected[
                    f"within_grid_disagreement_px_{suffix}"
                ].to_numpy(),
            }
        )
        row = summarize_case_steps(
            case_steps,
            case=case,
            object_um_per_px=float(sequence["object_um_per_px"]),
            nominal_step_um=float(sequence["nominal_step_um"]),
            expected_signed_dx_px=float(sequence["expected_signed_dx_px"]),
        )
        row.update(
            {
                "sequence": "50x_x_0p5um",
                "analysis_population": "all_within_acquisition_session_pairs",
                "excluded_cross_session_pairs": 2,
                "session_count": 3,
            }
        )
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)

    paths = {
        "mapping": tables / "acquisition_frame_timestamps.csv",
        "pair_audit": tables / "all_50_adjacent_pairs_audit.csv",
        "steps": tables / "corrected_48_within_session_steps.csv",
        "segments": tables / "session_summary.csv",
        "summary": tables / "corrected_raw_v42_summary.csv",
        "shifts": tables / "absolute_xy_shift.csv",
        "timestamp_figure": figures / "timestamp_gap_sessions.png",
        "shift_figure": figures / "absolute_xy_session_shift.png",
        "step_figure": figures / "corrected_48_step_trace.png",
        "metadata": output / "metadata.json",
    }
    sessions.to_csv(paths["mapping"], index=False)
    pair_measurements.to_csv(paths["pair_audit"], index=False)
    corrected.to_csv(paths["steps"], index=False)
    pd.DataFrame(segment_rows).to_csv(paths["segments"], index=False)
    summary.to_csv(paths["summary"], index=False)
    shifts.to_csv(paths["shifts"], index=False)
    _plot_timestamp_gaps(
        pairs,
        paths["timestamp_figure"],
        threshold_seconds=threshold_seconds,
    )
    _plot_absolute_shift(shifts, paths["shift_figure"])
    _plot_corrected_steps(corrected, paths["step_figure"])
    metadata = {
        "mapping_source": str(Path(mapping_path).resolve()),
        "config_source": str(Path(config_path).resolve()),
        "session_threshold_seconds": float(threshold_seconds),
        "threshold_sensitivity_seconds": [45, 60, 90, 120, 180],
        "session_starts": [0, 27, 31],
        "session_boundaries": boundaries,
        "total_adjacent_pairs": 50,
        "included_within_session_pairs": 48,
        "excluded_pairs": [
            {
                "start_frame": 26,
                "end_frame": 27,
                "gap_seconds": 1321.0,
                "reason": "cross_acquisition_session",
            },
            {
                "start_frame": 30,
                "end_frame": 31,
                "gap_seconds": 283.0,
                "reason": "cross_acquisition_session",
            },
        ],
        "selection_rule": "timestamps only; image and model results do not define sessions",
        "session_anchor_method": (
            "local 2D normalized template matching for each of the same nine pillars; "
            "median subpixel offset; 20 px search radius below half the grid pitch"
        ),
        "claim_limit": "repeatability within acquisition sessions, not independent stage accuracy",
    }
    paths["metadata"].write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Correct 50x 0.5 um analysis using timestamp-defined acquisition sessions."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PACKAGE / "diagnostics" / "50x_0p5um_sessions",
    )
    args = parser.parse_args()
    outputs = run_session_analysis(output_root=args.output_root)
    print(pd.read_csv(outputs["summary"]).to_string(index=False))
    print(f"\nOutputs: {args.output_root.resolve()}")


if __name__ == "__main__":
    main()
