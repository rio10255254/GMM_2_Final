from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class TrackerConfig:
    radius_px: float
    pitch_px: float
    polarity: str
    search_radius_px: float
    min_valid_pillars: int = 6
    min_edge_strength: float = 2.0
    max_chord_mad_px: float | None = None
    chord_fractions: tuple[float, ...] = (-0.55, -0.275, 0.0, 0.275, 0.55)

    def __post_init__(self) -> None:
        if not np.isfinite(self.radius_px) or self.radius_px <= 0:
            raise ValueError("radius_px must be finite and positive")
        if not np.isfinite(self.pitch_px) or self.pitch_px <= 0:
            raise ValueError("pitch_px must be finite and positive")
        if not np.isfinite(self.search_radius_px) or self.search_radius_px <= 0:
            raise ValueError("search_radius_px must be finite and positive")
        if self.search_radius_px >= self.pitch_px * 0.5:
            raise ValueError("search radius must remain below half the grid pitch")
        if self.polarity not in {"dark", "bright"}:
            raise ValueError("polarity must be 'dark' or 'bright'")
        if not 1 <= int(self.min_valid_pillars) <= 9:
            raise ValueError("min_valid_pillars must be in 1..9")
        if not np.isfinite(self.min_edge_strength) or self.min_edge_strength <= 0:
            raise ValueError("min_edge_strength must be finite and positive")
        if self.max_chord_mad_px is not None and (
            not np.isfinite(self.max_chord_mad_px) or self.max_chord_mad_px <= 0
        ):
            raise ValueError("max_chord_mad_px must be finite and positive")
        if len(self.chord_fractions) < 3:
            raise ValueError("at least three horizontal chords are required")
        if any(abs(value) >= 0.9 for value in self.chord_fractions):
            raise ValueError("chord fractions must stay inside the pillar")


@dataclass(frozen=True)
class PillarMeasurement:
    valid: bool
    x_px: float
    width_px: float
    chord_count: int
    edge_strength: float
    chord_mad_px: float


@dataclass(frozen=True)
class TrackingResult:
    frames: pd.DataFrame
    steps: pd.DataFrame
    pillar_steps: pd.DataFrame
    prediction_shifts: tuple[float, ...]


def _subpixel_peak(values: np.ndarray, index: int) -> float:
    if index <= 0 or index >= len(values) - 1:
        return float(index)
    left = float(values[index - 1])
    center = float(values[index])
    right = float(values[index + 1])
    denominator = left - 2.0 * center + right
    if not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return float(index)
    offset = 0.5 * (left - right) / denominator
    return float(index) + float(np.clip(offset, -1.0, 1.0))


def _sample_horizontal_profile(image: np.ndarray, y_px: float) -> np.ndarray:
    width = image.shape[1]
    x_map = np.arange(width, dtype=np.float32)[None, :]
    y_map = np.full((1, width), float(y_px), dtype=np.float32)
    profile = cv2.remap(
        image.astype(np.float32),
        x_map,
        y_map,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )[0]
    sigma = 0.55 if width < 300 else 0.8
    return cv2.GaussianBlur(profile[None, :], (0, 0), sigmaX=sigma)[0]


def _edge_from_window(
    score: np.ndarray, *, expected_x: float, half_width: float
) -> tuple[float, float] | None:
    start = max(1, int(np.floor(expected_x - half_width)))
    stop = min(len(score) - 1, int(np.ceil(expected_x + half_width)) + 1)
    if stop - start < 3:
        return None
    local = score[start:stop]
    local_index = int(np.argmax(local))
    if local_index == 0 or local_index == len(local) - 1:
        return None
    index = start + local_index
    peak = float(score[index])
    if not np.isfinite(peak) or peak <= 0:
        return None
    refined = _subpixel_peak(score, index)
    if not (float(start) <= refined <= float(stop - 1)):
        return None
    return refined, peak


def measure_pillar_x(
    image: np.ndarray,
    *,
    predicted_x_px: float,
    predicted_y_px: float,
    config: TrackerConfig,
) -> PillarMeasurement:
    array = np.asarray(image, dtype=np.float32)
    if array.ndim != 2:
        raise ValueError("pillar tracker expects a 2D grayscale image")
    height, width = array.shape
    radius = float(config.radius_px)
    if not (0 <= predicted_y_px < height and 0 <= predicted_x_px < width):
        return PillarMeasurement(False, np.nan, np.nan, 0, 0.0, np.nan)

    centers: list[float] = []
    widths: list[float] = []
    strengths: list[float] = []
    edge_half_width = float(config.search_radius_px) + max(1.0, radius * 0.28)
    for fraction in config.chord_fractions:
        y = float(predicted_y_px) + float(fraction) * radius
        if y < 1 or y >= height - 1:
            continue
        profile = _sample_horizontal_profile(array, y)
        gradient = np.gradient(profile.astype(np.float64))
        if config.polarity == "dark":
            left_score = -gradient
            right_score = gradient
        else:
            left_score = gradient
            right_score = -gradient
        half_chord = radius * float(np.sqrt(max(0.0, 1.0 - float(fraction) ** 2)))
        left = _edge_from_window(
            left_score,
            expected_x=float(predicted_x_px) - half_chord,
            half_width=edge_half_width,
        )
        right = _edge_from_window(
            right_score,
            expected_x=float(predicted_x_px) + half_chord,
            half_width=edge_half_width,
        )
        if left is None or right is None:
            continue
        left_x, left_strength = left
        right_x, right_strength = right
        width_px = right_x - left_x
        center_x = (right_x + left_x) * 0.5
        expected_width = 2.0 * half_chord
        if not (radius * 1.15 <= width_px <= radius * 2.65):
            continue
        if abs(width_px - expected_width) > max(radius * 0.75, 1.5):
            continue
        if abs(center_x - float(predicted_x_px)) >= float(config.search_radius_px):
            continue
        centers.append(float(center_x))
        widths.append(float(width_px))
        strengths.append(float(min(left_strength, right_strength)))

    minimum_chords = 2 if radius < 3.0 else 3
    if len(centers) < minimum_chords:
        return PillarMeasurement(False, np.nan, np.nan, len(centers), 0.0, np.nan)
    center_array = np.asarray(centers, dtype=np.float64)
    median_center = float(np.median(center_array))
    chord_mad = float(np.median(np.abs(center_array - median_center)))
    edge_strength = float(np.median(strengths))
    maximum_chord_mad = (
        float(config.max_chord_mad_px)
        if config.max_chord_mad_px is not None
        else max(0.35, radius * 0.15)
    )
    if edge_strength < config.min_edge_strength or chord_mad > maximum_chord_mad:
        return PillarMeasurement(
            False,
            np.nan,
            np.nan,
            len(centers),
            edge_strength,
            chord_mad,
        )
    return PillarMeasurement(
        valid=True,
        x_px=median_center,
        width_px=float(np.median(widths)),
        chord_count=len(centers),
        edge_strength=edge_strength,
        chord_mad_px=chord_mad,
    )


def _validate_initial_centers(
    centers: Sequence[tuple[str, float, float]], config: TrackerConfig
) -> tuple[tuple[str, float, float], ...]:
    normalized = tuple((str(name), float(x), float(y)) for name, x, y in centers)
    if len(normalized) != 9:
        raise ValueError("exactly nine pillar identities are required")
    if len({name for name, _, _ in normalized}) != 9:
        raise ValueError("pillar identities must be unique")
    coordinates = np.asarray([(x, y) for _, x, y in normalized], dtype=np.float64)
    if not np.isfinite(coordinates).all():
        raise ValueError("pillar coordinates must be finite")
    if config.min_valid_pillars > len(normalized):
        raise ValueError("min_valid_pillars exceeds identity count")
    for index, (_, x1, y1) in enumerate(normalized):
        for _, x2, y2 in normalized[index + 1 :]:
            same_horizontal_band = abs(y1 - y2) <= config.radius_px * 2.0
            if same_horizontal_band and abs(x1 - x2) <= config.search_radius_px * 2.0:
                raise ValueError("pillar identity search windows overlap")
    return normalized


def track_pillar_grid(
    images: Sequence[np.ndarray],
    initial_centers: Sequence[tuple[str, float, float]],
    *,
    config: TrackerConfig,
    expected_step_dx_px: float,
    shared_prediction_shifts: Sequence[float] | None = None,
) -> TrackingResult:
    if len(images) < 2:
        raise ValueError("at least two frames are required")
    if not np.isfinite(expected_step_dx_px):
        raise ValueError("expected_step_dx_px must be finite")
    if abs(float(expected_step_dx_px)) >= config.pitch_px * 0.5:
        raise ValueError("expected step must remain below half the grid pitch")
    centers = _validate_initial_centers(initial_centers, config)
    if shared_prediction_shifts is not None and len(shared_prediction_shifts) != len(images):
        raise ValueError("shared_prediction_shifts must match frame count")
    if shared_prediction_shifts is not None:
        shared = np.asarray(shared_prediction_shifts, dtype=np.float64)
        if not np.isfinite(shared).all():
            raise ValueError("shared prediction shifts must be finite")
        if abs(float(shared[0])) >= config.search_radius_px:
            raise ValueError("prediction continuity failed at frame 0")
        continuity_limit = config.pitch_px * 0.5 - config.search_radius_px
        changes = np.diff(shared)
        if np.any(np.abs(changes - float(expected_step_dx_px)) >= continuity_limit):
            raise ValueError("prediction continuity exceeds identity-safe limit")

    frame_records: list[dict[str, object]] = []
    prediction_shifts: list[float] = []
    measured_by_frame: list[dict[str, float]] = []
    previous_absolute_shift = 0.0

    for frame_index, image in enumerate(images):
        if shared_prediction_shifts is None:
            prediction_shift = (
                0.0
                if frame_index == 0
                else previous_absolute_shift + float(expected_step_dx_px)
            )
        else:
            prediction_shift = float(shared_prediction_shifts[frame_index])
        prediction_shifts.append(prediction_shift)
        measured: dict[str, float] = {}
        absolute_offsets: list[float] = []
        for pillar_id, initial_x, initial_y in centers:
            predicted_x = initial_x + prediction_shift
            result = measure_pillar_x(
                np.asarray(image),
                predicted_x_px=predicted_x,
                predicted_y_px=initial_y,
                config=config,
            )
            identity_error = result.x_px - predicted_x if result.valid else np.nan
            window_valid = bool(
                result.valid
                and np.isfinite(identity_error)
                and abs(identity_error) < config.pitch_px * 0.5
            )
            if window_valid:
                measured[pillar_id] = float(result.x_px)
                absolute_offsets.append(float(result.x_px - initial_x))
            frame_records.append(
                {
                    "frame_index": int(frame_index),
                    "pillar_id": pillar_id,
                    "initial_x_px": initial_x,
                    "initial_y_px": initial_y,
                    "prediction_shift_px": prediction_shift,
                    "predicted_x_px": predicted_x,
                    "measured_x_px": result.x_px,
                    "identity_error_px": identity_error,
                    "identity_window_valid": window_valid,
                    "one_to_one_valid": window_valid,
                    "width_px": result.width_px,
                    "chord_count": int(result.chord_count),
                    "edge_strength": result.edge_strength,
                    "chord_mad_px": result.chord_mad_px,
                }
            )
        measured_by_frame.append(measured)
        if shared_prediction_shifts is None and len(absolute_offsets) >= config.min_valid_pillars:
            previous_absolute_shift = float(np.median(absolute_offsets))
        elif shared_prediction_shifts is None:
            previous_absolute_shift = prediction_shift

    step_records: list[dict[str, object]] = []
    pillar_step_records: list[dict[str, object]] = []
    all_ids = [pillar_id for pillar_id, _, _ in centers]
    for frame_index in range(1, len(images)):
        previous = measured_by_frame[frame_index - 1]
        current = measured_by_frame[frame_index]
        common_ids = sorted(set(previous) & set(current))
        displacements = np.asarray(
            [current[pillar_id] - previous[pillar_id] for pillar_id in common_ids],
            dtype=np.float64,
        )
        enough_pillars = bool(len(displacements) >= config.min_valid_pillars)
        if enough_pillars:
            first_consensus = float(np.median(displacements))
            first_residual = displacements - first_consensus
            first_mad = float(np.median(np.abs(first_residual)))
            residual_limit = max(3.0 * 1.4826 * first_mad, config.search_radius_px * 0.45)
            keep = np.abs(first_residual) <= residual_limit
            filtered_ids = [pillar_id for pillar_id, accepted in zip(common_ids, keep) if accepted]
            filtered = displacements[keep]
        else:
            filtered_ids = []
            filtered = np.asarray([], dtype=np.float64)
        continuity_valid = bool(
            len(filtered) >= config.min_valid_pillars
            and abs(float(np.median(filtered)) - float(expected_step_dx_px))
            < config.pitch_px * 0.5
        )
        valid = bool(len(filtered) >= config.min_valid_pillars and continuity_valid)
        if valid:
            consensus = float(np.median(filtered))
            residual = filtered - consensus
            disagreement = float(1.4826 * np.median(np.abs(residual)))
            step_sd = float(np.std(filtered, ddof=1)) if len(filtered) > 1 else 0.0
        else:
            consensus = np.nan
            disagreement = np.nan
            step_sd = np.nan
        step_records.append(
            {
                "step_index": int(frame_index),
                "ref_frame_index": int(frame_index - 1),
                "frame_index": int(frame_index),
                "analysis_valid": valid,
                "valid_pillars": int(len(filtered)),
                "candidate_pillars": int(len(displacements)),
                "prediction_continuity_valid": continuity_valid,
                "consensus_dx_px": consensus,
                "within_grid_disagreement_px": disagreement,
                "pillar_step_sd_px": step_sd,
                "expected_step_dx_px": float(expected_step_dx_px),
            }
        )
        displacement_by_id = {
            pillar_id: current[pillar_id] - previous[pillar_id]
            for pillar_id in common_ids
        }
        for pillar_id in all_ids:
            pillar_dx = float(displacement_by_id.get(pillar_id, np.nan))
            pillar_valid = bool(valid and pillar_id in filtered_ids and np.isfinite(pillar_dx))
            pillar_step_records.append(
                {
                    "step_index": int(frame_index),
                    "ref_frame_index": int(frame_index - 1),
                    "frame_index": int(frame_index),
                    "pillar_id": pillar_id,
                    "pillar_valid": pillar_valid,
                    "pillar_dx_px": pillar_dx,
                    "consensus_dx_px": consensus,
                    "within_grid_residual_px": (
                        pillar_dx - consensus if pillar_valid else np.nan
                    ),
                }
            )

    return TrackingResult(
        frames=pd.DataFrame(frame_records),
        steps=pd.DataFrame(step_records),
        pillar_steps=pd.DataFrame(pillar_step_records),
        prediction_shifts=tuple(prediction_shifts),
    )
