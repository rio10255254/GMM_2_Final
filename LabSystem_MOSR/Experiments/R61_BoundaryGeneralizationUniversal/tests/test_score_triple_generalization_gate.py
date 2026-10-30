from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "score_triple_generalization_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("score_triple_generalization_gate", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_triple_gate_requires_boundary_real_motion_and_step_to_pass():
    module = load_module()
    boundary = {"pass": True, "candidate_name": "candidate", "failures": []}
    real_motion = {
        "cases": [
            {"case": "raw", "tail_std_dy_px": 0.270},
            {"case": "candidate", "tail_std_dy_px": 0.269},
        ]
    }
    step_motion = {
        "cases": [
            {"case": "raw", "step_std_dx_px": 0.050, "repeat_median_mag_px": 0.020},
            {"case": "candidate", "step_std_dx_px": 0.080, "repeat_median_mag_px": 0.019},
        ]
    }

    report = module.evaluate_triple_gate(
        boundary_report=boundary,
        real_motion_summary=real_motion,
        real_motion_baseline_case="raw",
        real_motion_candidate_case="candidate",
        step_summary=step_motion,
        step_baseline_case="raw",
        step_candidate_case="candidate",
        step_metric="step_std_dx_px",
    )

    assert report["pass"] is False
    assert report["boundary_gate"]["pass"] is True
    assert report["real_motion_gate"]["pass"] is True
    assert report["step_gate"]["pass"] is False


def test_triple_gate_cli_writes_report(tmp_path: Path):
    module = load_module()
    boundary_path = _write_json(tmp_path / "boundary.json", {"pass": True, "failures": []})
    real_path = _write_json(
        tmp_path / "real.json",
        {
            "cases": [
                {"case": "raw", "tail_std_dy_px": 0.270},
                {"case": "candidate", "tail_std_dy_px": 0.269},
            ]
        },
    )
    step_path = _write_json(
        tmp_path / "step.json",
        {
            "cases": [
                {"case": "raw", "step_std_dx_px": 0.050},
                {"case": "candidate", "step_std_dx_px": 0.049},
            ]
        },
    )
    output = tmp_path / "triple.json"

    rc = module.main(
        [
            "--boundary-gate-json",
            str(boundary_path),
            "--real-motion-summary-json",
            str(real_path),
            "--real-motion-baseline-case",
            "raw",
            "--real-motion-candidate-case",
            "candidate",
            "--step-summary-json",
            str(step_path),
            "--step-baseline-case",
            "raw",
            "--step-candidate-case",
            "candidate",
            "--output-json",
            str(output),
        ]
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert rc == 0
    assert report["pass"] is True
    assert report["step_gate"]["pass"] is True
