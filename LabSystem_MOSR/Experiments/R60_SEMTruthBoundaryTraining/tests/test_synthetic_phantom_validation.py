from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_synthetic_phantom_validation.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_synthetic_phantom_validation", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_render_phantom_has_truth_and_biased_input_boundaries():
    module = load_module()

    phantom = module.render_synthetic_phantom(size=320, bias_px=2.0, blur_sigma=1.2, noise_sigma=0.0, seed=3)

    assert phantom.truth_image.shape == (320, 320)
    assert phantom.input_image.shape == (320, 320)
    assert len(phantom.regions) >= 6
    assert phantom.truth_image.dtype == np.uint8
    assert phantom.input_image.dtype == np.uint8

    input_rows = module.measure_boundary_table(phantom, phantom.input_image, image_label="input")
    assert max(row["chamfer_px"] for row in input_rows) > 0.5


def test_measurement_reports_near_zero_error_for_truth_image():
    module = load_module()
    phantom = module.render_synthetic_phantom(size=256, bias_px=2.0, blur_sigma=1.2, noise_sigma=0.0, seed=4)

    rows = module.measure_boundary_table(phantom, phantom.truth_image, image_label="truth")

    assert rows
    assert max(row["chamfer_px"] for row in rows) <= 0.25


def test_build_reconstruct_command_uses_best_weight_and_disables_psf(tmp_path: Path):
    module = load_module()
    weights = tmp_path / "epoch_005.pth.tar"
    weights.write_bytes(b"fake")

    command = module.build_reconstruct_command(
        weights=weights,
        input_dir=tmp_path / "input",
        recon_root=tmp_path / "recon",
        output_name="phantom_recon",
        device="cpu",
    )

    joined = " ".join(str(part) for part in command)
    assert "--weights" in command
    assert str(weights) in command
    assert "--no-psf-from-ckpt" in command
    assert "--weak-psf-disable" in command
    assert "--psf-phys-alpha" in command
    assert "phantom_recon" in joined
