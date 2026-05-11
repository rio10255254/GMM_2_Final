from pathlib import Path
import sys

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R44_UniversalBoundaryMotionFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def test_generate_motion_dataset_writes_shifted_sequence_and_metadata(tmp_path):
    import r44_motion_data

    root = tmp_path / "repo"
    manifest = r44_motion_data.generate_motion_dataset(
        clean_root=root / "Training_Data" / "generated",
        source_root=root / "Training_Data" / "generated_convolved",
        geom_root=root / "Training_Data" / "r44_motion_geometry",
        count_per_stage=1,
        size=64,
        base_seed=4400,
        force=True,
    )

    assert manifest["generator"] == "r44_motion_v1"
    assert len(manifest["stages"]) == len(r44_motion_data.MOTION_STAGE_SPECS)

    stage = r44_motion_data.MOTION_STAGE_SPECS[0].name
    frame_name = "0000_seq0000_f01.bmp"
    label_path = root / "Training_Data" / "generated" / stage / frame_name
    source_path = root / "Training_Data" / "generated_convolved" / stage / frame_name
    boundary_path = root / "Training_Data" / "r44_motion_geometry" / "boundary" / stage / frame_name
    center_path = root / "Training_Data" / "r44_motion_geometry" / "centerline" / stage / frame_name
    dist_path = root / "Training_Data" / "r44_motion_geometry" / "distance" / stage / "0000_seq0000_f01.npy"
    meta_path = root / "Training_Data" / "r44_motion_geometry" / "meta" / stage / "0000_seq0000_f01.json"

    assert label_path.exists()
    assert source_path.exists()
    assert boundary_path.exists()
    assert center_path.exists()
    assert dist_path.exists()
    assert meta_path.exists()

    label0 = cv2.imread(str(root / "Training_Data" / "generated" / stage / "0000_seq0000_f00.bmp"), cv2.IMREAD_GRAYSCALE)
    label1 = cv2.imread(str(label_path), cv2.IMREAD_GRAYSCALE)
    distance = np.load(dist_path)
    meta = r44_motion_data._load_json(meta_path)

    assert label0.shape == (64, 64)
    assert label1.shape == (64, 64)
    assert int(np.abs(label1.astype(np.int16) - label0.astype(np.int16)).sum()) > 0
    assert distance.shape == (64, 64)
    assert meta["frame_index"] == 1
    assert meta["delta_from_prev_px"] == {"dx": 0.08, "dy": 0.0}


def test_motion_plan_materializes_sequence_sidecars_and_keeps_splits_disjoint(tmp_path):
    import r44_motion_data

    repo = tmp_path / "repo"
    r44_motion_data.generate_motion_dataset(
        clean_root=repo / "Training_Data" / "generated",
        source_root=repo / "Training_Data" / "generated_convolved",
        geom_root=repo / "Training_Data" / "r44_motion_geometry",
        count_per_stage=4,
        size=64,
        base_seed=4401,
        force=True,
    )
    train = r44_motion_data.R44MotionProfile(
        name="mini_train",
        motion_per_stage=2,
        motion_start_index=0,
        description="mini train",
    )
    val = r44_motion_data.R44MotionProfile(
        name="mini_val",
        motion_per_stage=1,
        motion_start_index=2,
        description="mini val",
    )

    train_plan = r44_motion_data.build_motion_plan(repo, train)
    val_plan = r44_motion_data.build_motion_plan(repo, val)
    r44_motion_data.assert_disjoint_motion_plans(train_plan, val_plan)

    manifest = r44_motion_data.materialize_motion_plan(train_plan, tmp_path / "package")

    assert manifest["total_frames"] == len(train_plan.frames)
    assert manifest["count_by_stage"][r44_motion_data.MOTION_STAGE_SPECS[0].name] == 2 * len(r44_motion_data.MOTION_SHIFT_STEPS)
    sample = manifest["frames"][0]
    assert (tmp_path / "package" / sample["package_src"]).exists()
    assert (tmp_path / "package" / sample["package_lbl"]).exists()
    assert (tmp_path / "package" / sample["package_boundary"]).exists()
    assert (tmp_path / "package" / sample["package_meta"]).exists()
