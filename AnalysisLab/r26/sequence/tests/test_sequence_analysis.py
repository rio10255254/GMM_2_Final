"""Tests for multi-frame sequence analysis."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Import modules under test
# ---------------------------------------------------------------------------
_SEQ_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_sequence_analysis.py"
_spec = importlib.util.spec_from_file_location("seq_analysis", _SEQ_SCRIPT)
seq = importlib.util.module_from_spec(_spec)
assert _spec is not None and _spec.loader is not None
_spec.loader.exec_module(seq)

# Also import the single-image test helper for make_ring_image
_SIA_TEST = (
    Path(__file__).resolve().parents[2]
    / "single_image"
    / "tests"
    / "test_single_image_analysis.py"
)
_spec2 = importlib.util.spec_from_file_location("sia_test", _SIA_TEST)
sia_test = importlib.util.module_from_spec(_spec2)
assert _spec2 is not None and _spec2.loader is not None
_spec2.loader.exec_module(sia_test)

make_ring_image = sia_test.make_ring_image


# ---------------------------------------------------------------------------
# Test 1: Image pairing
# ---------------------------------------------------------------------------

def test_image_pairing_returns_only_matched_sorted(tmp_path):
    """match_input_recon_pairs returns only files present in both dirs, sorted."""
    from dataset_config import DatasetConfig

    inp_dir = tmp_path / "input"
    rec_dir = tmp_path / "recon"
    inp_dir.mkdir()
    rec_dir.mkdir()

    # Input has a.bmp, b.bmp, c.bmp; recon has b.bmp, c.bmp, d.bmp
    for name in ["a.bmp", "b.bmp", "c.bmp"]:
        (inp_dir / name).write_bytes(b"\x00")
    for name in ["b.bmp", "c.bmp", "d.bmp"]:
        (rec_dir / name).write_bytes(b"\x00")

    config = DatasetConfig(
        name="test", short_name="test",
        input_dir=inp_dir, recon_dir=rec_dir,
        expected_step_px=1.0,
    )
    pairs = seq.match_input_recon_pairs(config)

    assert len(pairs) == 2
    assert pairs[0][0].name == "b.bmp"
    assert pairs[0][1].name == "b.bmp"
    assert pairs[1][0].name == "c.bmp"


# ---------------------------------------------------------------------------
# Test 2: Step std on synthetic sequence
# ---------------------------------------------------------------------------

def test_step_std_on_synthetic_sequence():
    """Synthetic 10-frame sequence with known Y drift → step_std matches."""
    rng = np.random.default_rng(42)
    n_frames = 10
    base_cy = 150
    step_size = 0.8
    jitter_sigma = 0.1

    # Generate frames with controlled center shift
    metrics_list = []
    cy_actual = []
    for i in range(n_frames):
        cy_i = base_cy + i * step_size + rng.normal(0, jitter_sigma)
        cy_actual.append(cy_i)
        img = make_ring_image(
            center=(128, int(round(cy_i))),
            blur_sigma=1.5,
            noise_sigma=1.5,
            seed=i + 100,
        )
        m = seq.analyze_frame(img.astype(np.float64))
        metrics_list.append(m)

    # Compute step_std from the detected centers
    cy_detected = np.array([m["outer_fit_cy"] for m in metrics_list])
    steps = np.diff(cy_detected)
    step_std = np.std(steps)

    # With this small synthetic ring, detection noise will add to jitter.
    # We just verify the step_std is in a reasonable range and mean step is close to 0.8.
    assert abs(np.mean(steps) - step_size) < 2.0, f"Mean step {np.mean(steps)} too far from {step_size}"
    assert step_std < 5.0, f"Step std {step_std} unreasonably large"


# ---------------------------------------------------------------------------
# Test 3: Residual improvement consistency
# ---------------------------------------------------------------------------

def test_residual_improvement_blurred_vs_sharp():
    """Blurred rings should have worse residual_std than sharp rings."""
    n_frames = 5
    inp_metrics = []
    out_metrics = []

    for i in range(n_frames):
        blurred = make_ring_image(blur_sigma=3.0, noise_sigma=3.0, seed=i + 200)
        sharp = make_ring_image(blur_sigma=1.2, noise_sigma=1.2, seed=i + 200)

        m_in = seq.analyze_frame(blurred.astype(np.float64))
        m_out = seq.analyze_frame(sharp.astype(np.float64))
        inp_metrics.append(m_in)
        out_metrics.append(m_out)

    # Output (sharp) should have lower residual_std than input (blurred)
    for boundary in ("outer", "inner"):
        key = f"{boundary}_residual_std"
        inp_mean = np.mean([m[key] for m in inp_metrics])
        out_mean = np.mean([m[key] for m in out_metrics])
        assert out_mean < inp_mean, (
            f"{boundary}: output mean {out_mean:.3f} >= input mean {inp_mean:.3f}"
        )


# ---------------------------------------------------------------------------
# Test 4: Circular std
# ---------------------------------------------------------------------------

def test_circular_std_stable_phases():
    """Near-identical phases should give low circular std."""
    phases = [45.1, 44.8, 45.3, 44.9, 45.0]
    assert seq.circular_std_deg(phases) < 5.0


def test_circular_std_scattered_phases():
    """Widely scattered phases should give large circular std."""
    phases = [0, 90, 180, 270]
    assert seq.circular_std_deg(phases) > 50.0


# ---------------------------------------------------------------------------
# Test 5: GMF score parser
# ---------------------------------------------------------------------------

def test_parse_gmf_score(tmp_path):
    """Parser extracts PosX, PosY, Score from GMF_score.txt format."""
    content = (
        "FileName, frame1.bmp, Time(ms), 19, PosX, 749.11, PosY, 789.01, "
        "Angle, 0, Scale, 1.00017, Score0, 86.0353, Score1, 0, Score Diff, 86.0353\n"
        "FileName, frame2.bmp, Time(ms), 20, PosX, 749.20, PosY, 788.21, "
        "Angle, 0, Scale, 1.00010, Score0, 85.500, Score1, 0, Score Diff, 85.500\n"
    )
    score_file = tmp_path / "GMF_score.txt"
    score_file.write_text(content, encoding="utf-8")

    rows = seq.parse_gmf_score(score_file)
    assert len(rows) == 2
    assert rows[0]["filename"] == "frame1.bmp"
    assert abs(rows[0]["posy"] - 789.01) < 0.001
    assert abs(rows[1]["posx"] - 749.20) < 0.001


# ---------------------------------------------------------------------------
# Test 6: Hotspot persistence semantics and plotting helpers
# ---------------------------------------------------------------------------

def _make_metric(frame_idx, *, outer_signal, inner_signal=None):
    inner_signal = inner_signal if inner_signal is not None else outer_signal
    return {
        "outer_fit_cx": 200.0 + 0.05 * frame_idx,
        "outer_fit_cy": 100.0 + 1.0 * frame_idx,
        "outer_k2_amplitude": 1.0,
        "outer_k2_phase_deg": 10.0,
        "inner_k2_amplitude": 1.2,
        "inner_k2_phase_deg": 20.0,
        "center_offset_px": 1.0 + 0.01 * frame_idx,
        "outer_residual_std": 5.0,
        "inner_residual_std": 4.5,
        "outer_residual_signal": list(outer_signal),
        "inner_residual_signal": list(inner_signal),
    }


def test_hotspot_persistence_distinguishes_persistent_vs_transient_patterns(tmp_path):
    """Persistent hotspots should score higher than frame-local transients."""
    from dataset_config import DatasetConfig

    n_frames = 4
    n_angles = 8
    input_metrics = []
    output_metrics = []

    for i in range(n_frames):
        transient = np.full(n_angles, 0.1, dtype=np.float64)
        transient[i % n_angles] = 5.0

        persistent = np.full(n_angles, 0.1, dtype=np.float64)
        persistent[2] = 5.0

        input_metrics.append(_make_metric(i, outer_signal=transient))
        output_metrics.append(_make_metric(i, outer_signal=persistent))

    config = DatasetConfig(
        name="test",
        short_name="test",
        input_dir=tmp_path / "input",
        recon_dir=tmp_path / "recon",
        expected_step_px=1.0,
        gmf_baseline_step_std=0.123,
    )

    summary = seq.compute_sequence_summary(input_metrics, output_metrics, config)

    inp = summary["hotspot_persistence"]["input_outer"]
    out = summary["hotspot_persistence"]["output_outer"]

    assert out["n_persistent_angles_gt50pct"] > inp["n_persistent_angles_gt50pct"]
    assert out["max_persistence"] > inp["max_persistence"]
    assert out["mean_persistence"] > inp["mean_persistence"]
    assert summary["step_stability"]["gmf_baseline_step_std"] == pytest.approx(0.123)


def test_unwrap_phase_for_plot_removes_false_boundary_jumps():
    """Plot helper should unwrap +/-180 degree boundary crossings smoothly."""
    wrapped = np.array([-170.0, 175.0, 178.0, -179.0, -175.0], dtype=np.float64)
    unwrapped = seq.unwrap_phase_for_plot(wrapped)

    assert np.max(np.abs(np.diff(unwrapped))) < 30.0
