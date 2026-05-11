from __future__ import annotations

import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


def test_build_ring_datasets_uses_latest_recon_run(tmp_path):
    import run_r39_ring_guard as guard

    candidate_root = tmp_path / "r39_shape_mix_safe"
    older = candidate_root / "reconstruct_progress_best_tradeoff_in_Cropped_Output_20260428_100000"
    newer = candidate_root / "reconstruct_progress_best_tradeoff_in_Cropped_Output_20260428_120000"
    for run_root in (older, newer):
        for spec in guard.RING_SPECS:
            (run_root / spec.output_name).mkdir(parents=True)

    datasets = guard.build_ring_datasets("r39_shape_mix_safe", tmp_path)

    assert [d.short_name for d in datasets] == [s.short_name for s in guard.RING_SPECS]
    assert all(str(d.recon_dir).startswith(str(newer)) for d in datasets)
    assert [d.expected_step_px for d in datasets] == [8.0, 0.8, 0.08]


def test_compact_summary_marks_external_gmf_pending_and_compares_combo(tmp_path):
    import run_r39_ring_guard as guard

    combo = {
        "datasets": [
            {
                "short_name": "pitch0p1um_y_60",
                "step_stability": {"output": {"internal_step_std_y": 0.1509}},
                "residual_consistency": {
                    "outer": {"output_mean": 2.329},
                    "inner": {"output_mean": 2.044},
                },
            }
        ]
    }
    combo_path = tmp_path / "combo.json"
    combo_path.write_text(json.dumps(combo), encoding="utf-8")

    result = {
        "summaries": [
            {
                "short_name": "pitch0p1um_y_60",
                "n_frames": 61,
                "step_stability": {
                    "input": {"internal_step_std_y": 2.7964},
                    "output": {"internal_step_std_y": 0.1777},
                },
                "residual_consistency": {
                    "outer": {"output_mean": 2.5},
                    "inner": {"output_mean": 2.2},
                },
            }
        ]
    }

    summary = guard.make_compact_summary(
        candidate="r39_shape_mix_safe",
        result=result,
        combo_cross_json=combo_path,
    )

    row = summary["datasets"][0]
    assert summary["status"] == "local_ring_guard_complete_external_gmf_pending"
    assert summary["external_gmf_required"] is True
    assert row["r39_internal_step_std_y"] == 0.1777
    assert row["combo_internal_step_std_y"] == 0.1509
    assert row["delta_internal_step_std_y"] == 0.0268
    assert row["formal_combo_external_step_std"] == 0.13156
