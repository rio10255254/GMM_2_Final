from __future__ import annotations

import csv
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[5]


SCRIPTS_DIR = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments/R62_TargetSampleBoost/scripts')
)
sys.path.insert(0, str(SCRIPTS_DIR))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_parse_frame_index_reads_standard_frame_names() -> None:
    from audit_r62_motion_training_data import parse_frame_index

    assert parse_frame_index("frame_0027.bmp") == 27
    assert parse_frame_index("crop_frame_0004.png") == 4
    assert parse_frame_index("no_number.bmp") is None


def test_expand_bad_steps_marks_previous_current_and_next_frames() -> None:
    from audit_r62_motion_training_data import expand_bad_steps_to_frames

    frames = expand_bad_steps_to_frames([27, 31], neighbor_radius=1)

    assert frames == [26, 27, 28, 30, 31, 32]


def test_detect_bad_steps_from_gmf_csv_uses_dx_error_and_y_drift(tmp_path: Path) -> None:
    from audit_r62_motion_training_data import detect_bad_steps_from_gmf_csv

    steps_csv = tmp_path / "steps.csv"
    _write_csv(
        steps_csv,
        [
            {
                "frame_index": 0,
                "filename": "frame_0000.bmp",
                "dx_px": 0,
                "dy_px": 0,
                "status": "reference",
            },
            {
                "frame_index": 1,
                "filename": "frame_0001.bmp",
                "dx_px": -5,
                "dy_px": 0,
                "status": "ok",
            },
            {
                "frame_index": 2,
                "filename": "frame_0002.bmp",
                "dx_px": -8,
                "dy_px": 0,
                "status": "ok",
            },
            {
                "frame_index": 3,
                "filename": "frame_0003.bmp",
                "dx_px": -5,
                "dy_px": 2,
                "status": "ok",
            },
        ],
    )

    rows = detect_bad_steps_from_gmf_csv(
        steps_csv,
        dataset="toy",
        group="x_0p5um",
        nominal_um=0.5,
        object_um_per_px=0.1,
        dx_error_threshold_um=0.15,
        dy_threshold_um=0.15,
    )

    assert [row.step_index for row in rows] == [2, 3]
    assert rows[0].reason == "dx_error"
    assert rows[1].reason == "y_drift"


def test_audit_manifest_marks_direct_motion_labels_and_selfshift_textures() -> None:
    from audit_r62_motion_training_data import BadStep, audit_manifest_pairs

    manifest = {
        "pairs": [
            {
                "role": "target_real_motion_pair",
                "target_dataset": "20260702_100MG",
                "target_sequence": "x_0p5um",
                "motion_frame": 27,
                "source_frame_name": "frame_0027.bmp",
            },
            {
                "role": "target_real_selfshift_motion_pair",
                "target_dataset": "20260702_100MG",
                "target_sequence": "x_0p5um",
                "motion_frame": 27,
                "source_frame_name": "frame_0027.bmp",
            },
            {
                "role": "target_real_motion_pair",
                "target_dataset": "20260702_100MG",
                "target_sequence": "x_1um",
                "motion_frame": 27,
                "source_frame_name": "frame_0027.bmp",
            },
        ]
    }
    bad_steps = [
        BadStep(
            dataset="20260702_100MG",
            group="x_0p5um",
            step_index=27,
            filename="frame_0027.bmp",
            dx_um=0.86,
            dy_um=0.79,
            dx_error_um=0.36,
            reason="dx_error+y_drift",
        )
    ]

    audit = audit_manifest_pairs(manifest, bad_steps, neighbor_radius=1)

    assert audit.summary["affected_pair_count"] == 2
    assert audit.summary["direct_label_conflict_count"] == 1
    assert audit.summary["source_texture_only_count"] == 1
    assert audit.summary["affected_by_role"] == {
        "target_real_motion_pair": 1,
        "target_real_selfshift_motion_pair": 1,
    }
    assert [row["risk_type"] for row in audit.rows] == [
        "direct_label_conflict",
        "source_texture_only",
    ]


def test_audit_manifest_uses_source_frame_for_selfshift_records() -> None:
    from audit_r62_motion_training_data import BadStep, audit_manifest_pairs

    manifest = {
        "pairs": [
            {
                "role": "target_real_selfshift_motion_pair",
                "target_dataset": "20260702_100MG",
                "target_sequence": "x_0p5um",
                "motion_frame": 0,
                "source_frame_name": "frame_0027.bmp",
            }
        ]
    }
    bad_steps = [
        BadStep(
            dataset="20260702_100MG",
            group="x_0p5um",
            step_index=27,
            filename="frame_0027.bmp",
            dx_um=0.86,
            dy_um=0.79,
            dx_error_um=0.36,
            reason="dx_error+y_drift",
        )
    ]

    audit = audit_manifest_pairs(manifest, bad_steps, neighbor_radius=1)

    assert audit.summary["affected_pair_count"] == 1
    assert audit.rows[0]["motion_frame"] == 27
    assert audit.rows[0]["risk_type"] == "source_texture_only"
