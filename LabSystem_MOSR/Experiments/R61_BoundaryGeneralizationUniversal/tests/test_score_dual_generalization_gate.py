from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "score_dual_generalization_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("score_dual_generalization_gate", SCRIPT_PATH)
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


def test_motion_gate_passes_when_candidate_tail_std_is_not_worse(tmp_path: Path):
    module = load_module()
    summary = {
        "cases": [
            {"case": "baseline", "tail_std_dy_px": 0.270},
            {"case": "candidate", "tail_std_dy_px": 0.269},
        ]
    }

    report = module.evaluate_motion_gate(
        summary,
        baseline_case="baseline",
        candidate_case="candidate",
        tolerance_px=0.0,
    )

    assert report["pass"] is True
    assert report["candidate"] == 0.269
    assert report["delta"] < 0


def test_motion_gate_fails_when_candidate_tail_std_is_worse(tmp_path: Path):
    module = load_module()
    summary = {
        "cases": [
            {"case": "baseline", "tail_std_dy_px": 0.270},
            {"case": "candidate", "tail_std_dy_px": 0.278},
        ]
    }

    report = module.evaluate_motion_gate(
        summary,
        baseline_case="baseline",
        candidate_case="candidate",
        tolerance_px=0.0,
    )

    assert report["pass"] is False
    assert report["delta"] > 0


def test_dual_gate_requires_boundary_and_motion_to_pass(tmp_path: Path):
    module = load_module()
    boundary_path = _write_json(
        tmp_path / "boundary.json",
        {"pass": True, "candidate_name": "candidate", "failures": []},
    )
    motion_path = _write_json(
        tmp_path / "motion.json",
        {
            "cases": [
                {"case": "baseline", "tail_std_dy_px": 0.270},
                {"case": "candidate", "tail_std_dy_px": 0.278},
            ]
        },
    )

    report = module.evaluate_dual_gate(
        boundary_report=json.loads(boundary_path.read_text(encoding="utf-8")),
        motion_summary=json.loads(motion_path.read_text(encoding="utf-8")),
        motion_baseline_case="baseline",
        motion_candidate_case="candidate",
        motion_tolerance_px=0.0,
    )

    assert report["pass"] is False
    assert report["boundary_gate"]["pass"] is True
    assert report["motion_gate"]["pass"] is False


def test_cli_writes_dual_gate_json(tmp_path: Path):
    module = load_module()
    boundary_path = _write_json(tmp_path / "boundary.json", {"pass": True, "failures": []})
    motion_path = _write_json(
        tmp_path / "motion.json",
        {
            "cases": [
                {"case": "baseline", "tail_std_dy_px": 0.270},
                {"case": "candidate", "tail_std_dy_px": 0.269},
            ]
        },
    )
    output_path = tmp_path / "dual.json"

    rc = module.main(
        [
            "--boundary-gate-json",
            str(boundary_path),
            "--motion-summary-json",
            str(motion_path),
            "--motion-baseline-case",
            "baseline",
            "--motion-candidate-case",
            "candidate",
            "--output-json",
            str(output_path),
        ]
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert rc == 0
    assert report["pass"] is True
