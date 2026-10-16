from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from pillar_motion_core import TrackerConfig, track_pillar_grid  # noqa: E402


def render_grid(
    centers: list[tuple[str, float, float]],
    *,
    shape: tuple[int, int],
    radius_px: float,
    shift_x_px: float,
    polarity: str = "dark",
    blur_sigma: float = 1.0,
    noise_sigma: float = 2.0,
    distractors: list[tuple[float, float]] | None = None,
    seed: int = 0,
) -> np.ndarray:
    scale = 4
    height, width = shape
    background, feature = (220, 30) if polarity == "dark" else (30, 220)
    canvas = np.full((height * scale, width * scale), background, dtype=np.uint8)
    for _, x, y in centers:
        cv2.circle(
            canvas,
            (int(round(x * scale)), int(round(y * scale))),
            int(round(radius_px * scale)),
            feature,
            thickness=-1,
            lineType=cv2.LINE_AA,
        )
    for x, y in distractors or []:
        cv2.circle(
            canvas,
            (int(round(x * scale)), int(round(y * scale))),
            int(round(radius_px * scale)),
            feature,
            thickness=-1,
            lineType=cv2.LINE_AA,
        )
    image = cv2.resize(canvas, (width, height), interpolation=cv2.INTER_AREA)
    image = cv2.warpAffine(
        image,
        np.asarray([[1.0, 0.0, shift_x_px], [0.0, 1.0, 0.0]], dtype=np.float32),
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=background,
    )
    if blur_sigma > 0:
        image = cv2.GaussianBlur(image, (0, 0), blur_sigma)
    if noise_sigma > 0:
        rng = np.random.default_rng(seed)
        image = np.clip(
            image.astype(np.float32)
            + rng.normal(0.0, noise_sigma, size=image.shape),
            0,
            255,
        ).astype(np.uint8)
    return image


def initial_grid(*, x0: float, y0: float, pitch: float) -> list[tuple[str, float, float]]:
    return [
        (f"P{row * 3 + col + 1}", x0 + col * pitch, y0 + row * pitch)
        for row in range(3)
        for col in range(3)
    ]


def test_tracker_rejects_search_reaching_half_grid_pitch() -> None:
    with pytest.raises(ValueError, match="half.*pitch"):
        TrackerConfig(
            radius_px=10.0,
            pitch_px=40.0,
            polarity="dark",
            search_radius_px=20.0,
            min_valid_pillars=6,
        )


def test_tracks_51_frame_subpixel_sequence_without_identity_switch() -> None:
    centers = initial_grid(x0=240.0, y0=70.0, pitch=40.0)
    truth_dx = -0.37
    images = [
        render_grid(
            centers,
            shape=(230, 480),
            radius_px=10.0,
            shift_x_px=frame * truth_dx,
            blur_sigma=1.15,
            noise_sigma=2.0,
            seed=frame,
        )
        for frame in range(51)
    ]
    config = TrackerConfig(
        radius_px=10.0,
        pitch_px=40.0,
        polarity="dark",
        search_radius_px=7.0,
        min_valid_pillars=7,
    )

    result = track_pillar_grid(
        images,
        centers,
        config=config,
        expected_step_dx_px=-0.22,
    )

    assert len(result.steps) == 50
    assert result.steps["analysis_valid"].all()
    assert result.steps["consensus_dx_px"].mean() == pytest.approx(truth_dx, abs=0.035)
    assert result.steps["consensus_dx_px"].std(ddof=1) < 0.045
    assert result.frames["identity_window_valid"].all()
    assert result.frames["one_to_one_valid"].all()
    assert result.frames["identity_error_px"].abs().max() < config.pitch_px * 0.5
    assert len(result.pillar_steps) == 50 * 9
    assert {
        "pillar_dx_px",
        "consensus_dx_px",
        "within_grid_residual_px",
    }.issubset(result.pillar_steps.columns)


def test_overlapping_identity_windows_are_rejected() -> None:
    centers = initial_grid(x0=100.0, y0=60.0, pitch=40.0)
    centers[1] = (centers[1][0], centers[0][1] + 5.0, centers[0][2])
    image = render_grid(
        centers,
        shape=(220, 360),
        radius_px=10.0,
        shift_x_px=0.0,
    )
    config = TrackerConfig(
        radius_px=10.0,
        pitch_px=40.0,
        polarity="dark",
        search_radius_px=7.0,
        min_valid_pillars=7,
    )

    with pytest.raises(ValueError, match="overlap"):
        track_pillar_grid(
            [image, image],
            centers,
            config=config,
            expected_step_dx_px=0.0,
        )


def test_one_pitch_distractors_do_not_capture_pillar_identities() -> None:
    centers = initial_grid(x0=190.0, y0=65.0, pitch=36.0)
    truth_dx = -0.42
    distractors = [(x + 36.0, y) for _, x, y in centers if x == 262.0]
    images = [
        render_grid(
            centers,
            shape=(220, 420),
            radius_px=9.0,
            shift_x_px=frame * truth_dx,
            blur_sigma=1.0,
            noise_sigma=2.5,
            distractors=distractors,
            seed=100 + frame,
        )
        for frame in range(51)
    ]
    config = TrackerConfig(
        radius_px=9.0,
        pitch_px=36.0,
        polarity="dark",
        search_radius_px=6.0,
        min_valid_pillars=7,
    )

    result = track_pillar_grid(
        images,
        centers,
        config=config,
        expected_step_dx_px=-0.27,
    )

    assert result.steps["analysis_valid"].all()
    assert result.steps["consensus_dx_px"].mean() == pytest.approx(truth_dx, abs=0.045)
    assert result.frames["identity_error_px"].abs().max() < 4.0


def test_low_resolution_grid_recovers_known_subpixel_motion() -> None:
    centers = initial_grid(x0=90.0, y0=55.0, pitch=8.0)
    truth_dx = -0.28
    images = [
        render_grid(
            centers,
            shape=(140, 220),
            radius_px=2.1,
            shift_x_px=frame * truth_dx,
            blur_sigma=0.65,
            noise_sigma=1.5,
            seed=200 + frame,
        )
        for frame in range(21)
    ]
    config = TrackerConfig(
        radius_px=2.1,
        pitch_px=8.0,
        polarity="dark",
        search_radius_px=2.5,
        min_valid_pillars=6,
    )

    result = track_pillar_grid(
        images,
        centers,
        config=config,
        expected_step_dx_px=-0.18,
    )

    assert result.steps["analysis_valid"].all()
    assert result.steps["consensus_dx_px"].mean() == pytest.approx(truth_dx, abs=0.10)
    assert result.steps["consensus_dx_px"].std(ddof=1) < 0.13


def test_shared_prediction_cannot_jump_by_one_pitch() -> None:
    centers = initial_grid(x0=120.0, y0=60.0, pitch=40.0)
    image = render_grid(
        centers,
        shape=(220, 380),
        radius_px=10.0,
        shift_x_px=0.0,
    )
    config = TrackerConfig(
        radius_px=10.0,
        pitch_px=40.0,
        polarity="dark",
        search_radius_px=7.0,
        min_valid_pillars=7,
    )

    with pytest.raises(ValueError, match="prediction continuity"):
        track_pillar_grid(
            [image, image],
            centers,
            config=config,
            expected_step_dx_px=0.0,
            shared_prediction_shifts=[0.0, 40.0],
        )


def test_expected_step_cannot_reach_half_grid_pitch() -> None:
    centers = initial_grid(x0=120.0, y0=60.0, pitch=40.0)
    image = render_grid(
        centers,
        shape=(220, 380),
        radius_px=10.0,
        shift_x_px=0.0,
    )
    config = TrackerConfig(
        radius_px=10.0,
        pitch_px=40.0,
        polarity="dark",
        search_radius_px=7.0,
        min_valid_pillars=7,
    )

    with pytest.raises(ValueError, match="expected step.*half.*pitch"):
        track_pillar_grid(
            [image, image],
            centers,
            config=config,
            expected_step_dx_px=20.0,
        )


def test_noise_only_frames_are_rejected() -> None:
    centers = initial_grid(x0=120.0, y0=60.0, pitch=40.0)
    rng = np.random.default_rng(99)
    images = [
        np.clip(128 + rng.normal(0, 2.0, size=(220, 380)), 0, 255).astype(np.uint8)
        for _ in range(3)
    ]
    config = TrackerConfig(
        radius_px=10.0,
        pitch_px=40.0,
        polarity="dark",
        search_radius_px=7.0,
        min_valid_pillars=7,
    )

    result = track_pillar_grid(
        images,
        centers,
        config=config,
        expected_step_dx_px=0.0,
    )

    assert not result.steps["analysis_valid"].any()
    assert not result.frames["identity_window_valid"].any()


def test_high_contrast_occluded_frame_invalidates_adjacent_steps() -> None:
    centers = initial_grid(x0=120.0, y0=60.0, pitch=40.0)
    clean = render_grid(
        centers,
        shape=(220, 380),
        radius_px=10.0,
        shift_x_px=0.0,
        noise_sigma=1.0,
    )
    occluded = clean.copy()
    cv2.rectangle(occluded, (95, 35), (230, 165), 0, thickness=-1)
    config = TrackerConfig(
        radius_px=10.0,
        pitch_px=40.0,
        polarity="dark",
        search_radius_px=7.0,
        min_valid_pillars=7,
    )

    result = track_pillar_grid(
        [clean, occluded, clean],
        centers,
        config=config,
        expected_step_dx_px=0.0,
    )

    assert not result.steps["analysis_valid"].any()
    middle = result.frames[result.frames["frame_index"] == 1]
    assert int(middle["identity_window_valid"].sum()) < config.min_valid_pillars


def test_clipped_edge_pillars_are_not_subpixel_fitted_outside_window() -> None:
    centers = initial_grid(x0=3.0, y0=60.0, pitch=40.0)
    images = [
        render_grid(
            centers,
            shape=(220, 180),
            radius_px=10.0,
            shift_x_px=0.0,
            noise_sigma=0.0,
        )
        for _ in range(2)
    ]
    config = TrackerConfig(
        radius_px=10.0,
        pitch_px=40.0,
        polarity="dark",
        search_radius_px=7.0,
        min_valid_pillars=7,
    )

    result = track_pillar_grid(
        images,
        centers,
        config=config,
        expected_step_dx_px=0.0,
    )

    clipped = result.frames[result.frames["pillar_id"].isin(["P1", "P4", "P7"])]
    assert not clipped["identity_window_valid"].any()
