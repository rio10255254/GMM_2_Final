from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_diverse_phantom_validation.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_diverse_phantom_validation", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_render_diverse_phantom_contains_multiple_shapes_and_polarities():
    module = load_module()

    phantom = module.render_diverse_phantom(size=256, bias_px=1.5, seed=7001)
    shapes = {region.shape for region in phantom.regions}
    polarities = {region.polarity for region in phantom.regions}

    assert phantom.truth_image.shape == (256, 256)
    assert phantom.input_image.shape == (256, 256)
    assert len(phantom.regions) >= 10
    assert {"circle", "ellipse", "rotated_rect", "polygon", "thin_bar", "annulus"}.issubset(shapes)
    assert polarities == {"bright", "dark"}
    assert not np.array_equal(phantom.truth_image, phantom.input_image)


def test_build_case_plan_crosses_seed_bias_blur_and_noise():
    module = load_module()

    cases = module.build_case_plan(
        seeds=[7001, 7002],
        biases=[0.0, 1.0, 2.0],
        blur_sigmas=[0.9, 1.4],
        noise_sigmas=[1.0, 3.0],
    )

    assert len(cases) == 24
    assert {case.bias_px for case in cases} == {0.0, 1.0, 2.0}
    assert {case.blur_sigma for case in cases} == {0.9, 1.4}
    assert {case.noise_sigma for case in cases} == {1.0, 3.0}
    assert len({case.case_id for case in cases}) == len(cases)


def test_skip_reconstruct_writes_summary_and_metrics(tmp_path: Path):
    module = load_module()

    rc = module.main(
        [
            "--output-root",
            str(tmp_path / "out"),
            "--skip-reconstruct",
            "--seeds",
            "7001",
            "--biases",
            "0.0,1.5",
            "--blur-sigmas",
            "1.0",
            "--noise-sigmas",
            "1.0",
            "--size",
            "192",
        ]
    )

    assert rc == 0
    summary_path = next((tmp_path / "out").rglob("summary.json"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    metrics_path = Path(summary["metrics_csv"])
    case_manifest = Path(summary["case_manifest"])

    assert summary["case_count"] == 2
    assert summary["skip_reconstruct"] is True
    assert metrics_path.exists()
    assert case_manifest.exists()
    assert summary["input_mean_chamfer_px"] >= 0
    assert summary["recon_mean_chamfer_px"] is None


def test_prepare_infer_script_disables_manual_select_mode(tmp_path: Path):
    module = load_module()
    source_script = tmp_path / "infer_source.py"
    source_script.write_text(
        '\n'.join(
            [
                "# fake infer script",
                "SCRIPT_DIR = Path(__file__).resolve().parent",
                'MANUAL_SELECT_MODE = "odd"',
                "print(MANUAL_SELECT_MODE)",
            ]
        ),
        encoding="utf-8",
    )

    patched_script = module._prepare_infer_script(tmp_path / "run", source_script=source_script)
    patched_text = patched_script.read_text(encoding="utf-8")
    command = module._build_reconstruct_command(
        weights=tmp_path / "weights.pth.tar",
        input_dir=tmp_path / "input",
        recon_root=tmp_path / "recon",
        output_name="out",
        device="cpu",
        infer_script=patched_script,
    )

    assert patched_script.exists()
    assert f'SCRIPT_DIR = Path(r"{source_script.parent}")' in patched_text
    assert "MANUAL_SELECT_MODE = None" in patched_text
    assert 'MANUAL_SELECT_MODE = "odd"' not in patched_text
    assert command[2] == str(patched_script)
    assert command[command.index("--select-mode") + 1] == "all"
