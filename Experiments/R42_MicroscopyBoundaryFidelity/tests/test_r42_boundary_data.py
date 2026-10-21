from pathlib import Path
import sys

import cv2
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "Experiments" / "R42_MicroscopyBoundaryFidelity" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def test_generate_boundary_dataset_writes_sources_labels_and_geometry(tmp_path):
    import r42_boundary_data

    root = tmp_path / "repo"
    manifest = r42_boundary_data.generate_boundary_dataset(
        clean_root=root / "Training_Data" / "generated",
        source_root=root / "Training_Data" / "generated_convolved",
        geom_root=root / "Training_Data" / "r42_boundary_geometry",
        count_per_stage=2,
        size=64,
        base_seed=4200,
        force=True,
    )

    assert manifest["generator"] == "r42_boundary_v1"
    assert len(manifest["stages"]) == len(r42_boundary_data.BOUNDARY_STAGE_SPECS)

    first_stage = r42_boundary_data.BOUNDARY_STAGE_SPECS[0].name
    label_path = root / "Training_Data" / "generated" / first_stage / "0000.bmp"
    source_path = root / "Training_Data" / "generated_convolved" / first_stage / "0000.bmp"
    boundary_path = root / "Training_Data" / "r42_boundary_geometry" / "boundary" / first_stage / "0000.bmp"
    center_path = root / "Training_Data" / "r42_boundary_geometry" / "centerline" / first_stage / "0000.bmp"
    dist_path = root / "Training_Data" / "r42_boundary_geometry" / "distance" / first_stage / "0000.npy"

    assert label_path.exists()
    assert source_path.exists()
    assert boundary_path.exists()
    assert center_path.exists()
    assert dist_path.exists()

    label = cv2.imread(str(label_path), cv2.IMREAD_GRAYSCALE)
    boundary = cv2.imread(str(boundary_path), cv2.IMREAD_GRAYSCALE)
    distance = np.load(dist_path)

    assert label.shape == (64, 64)
    assert boundary.shape == (64, 64)
    assert distance.shape == (64, 64)
    assert int(boundary.max()) == 255
    assert float(distance.max()) > 0.0


def test_boundary_plan_materializes_geometry_sidecars(tmp_path):
    import r42_boundary_data

    repo = tmp_path / "repo"
    r42_boundary_data.generate_boundary_dataset(
        clean_root=repo / "Training_Data" / "generated",
        source_root=repo / "Training_Data" / "generated_convolved",
        geom_root=repo / "Training_Data" / "r42_boundary_geometry",
        count_per_stage=4,
        size=64,
        base_seed=4201,
        force=True,
    )
    profile = r42_boundary_data.R42Profile(
        name="mini_boundary_val",
        include_ring=False,
        ring_limit=None,
        shape_total=0,
        shape_start_index=0,
        micro_total=0,
        micro_start_index=0,
        boundary_per_stage=2,
        boundary_start_index=2,
        description="mini held-out boundary validation profile",
    )

    plan = r42_boundary_data.build_plan(repo, profile)
    assert len(plan.pairs) == 2 * len(r42_boundary_data.BOUNDARY_STAGE_SPECS)
    assert plan.count_by_role == {"boundary": len(plan.pairs)}

    manifest = r42_boundary_data.materialize_plan_with_geometry(plan, tmp_path / "package")

    assert manifest["total_pairs"] == len(plan.pairs)
    assert manifest["count_by_role"] == {"boundary": len(plan.pairs)}
    sample = manifest["pairs"][0]
    assert (tmp_path / "package" / sample["package_src"]).exists()
    assert (tmp_path / "package" / sample["package_lbl"]).exists()
    assert (tmp_path / "package" / sample["package_boundary"]).exists()
    assert (tmp_path / "package" / sample["package_distance"]).exists()


def test_guarded_kd_probe_profile_is_legacy_weighted():
    import r42_boundary_data

    profile = r42_boundary_data.PROFILES["r42_guarded_kd_probe_train"]
    plan = r42_boundary_data.build_plan(r42_boundary_data.REPO_ROOT, profile)

    assert plan.count_by_role["ring"] == 700
    assert plan.count_by_role["shape"] == 300
    assert plan.count_by_role["micro"] == 250
    assert plan.count_by_role["boundary"] == 40 * len(r42_boundary_data.BOUNDARY_STAGE_SPECS)
    assert plan.count_by_role["ring"] + plan.count_by_role["shape"] > (
        plan.count_by_role["micro"] + plan.count_by_role["boundary"]
    )
