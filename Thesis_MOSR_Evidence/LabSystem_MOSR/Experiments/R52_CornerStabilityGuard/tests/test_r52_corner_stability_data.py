from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "r52_corner_stability_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r52_corner_stability_data", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_image(path: Path, value: int = 128) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = np.full((32, 32), value, dtype=np.uint8)
    cv2.rectangle(img, (8, 8), (23, 23), min(255, value + 60), -1)
    ok, encoded = cv2.imencode(path.suffix, img)
    assert ok
    path.write_bytes(encoded.tobytes())


def _write_ring_pair(root: Path, name: str) -> None:
    _write_image(root / "Training_Data" / "tra_src_ring" / name, 70)
    _write_image(root / "Training_Data" / "tra_lbl_ring" / name, 190)


def _write_stage_pair(root: Path, src_root_name: str, stage: str, name: str, value: int = 120) -> None:
    _write_image(root / "Training_Data" / src_root_name / stage / name, value)
    _write_image(root / "Training_Data" / "generated" / stage / name, min(255, value + 40))


def _write_external_pair(root: Path, rel_root: Path, stage: str, name: str, value: int = 110) -> None:
    _write_image(root / rel_root / stage / name, value)
    _write_image(root / "Training_Data" / "generated" / stage / name, min(255, value + 40))


def _required_stage_counts(module) -> dict[str, int]:
    counts: dict[str, int] = {}
    for profile in module.PROFILES.values():
        for stage, quota in profile.boundary_quotas.items():
            counts[stage] = max(counts.get(stage, 0), profile.start_offsets.get(stage, 0) + quota)
        for stage, quota in profile.real_bg_quotas.items():
            counts[stage] = max(counts.get(stage, 0), profile.start_offsets.get(stage, 0) + quota)
    for stage in module.SHAPE_STAGES:
        counts[stage] = max(counts.get(stage, 0), module.TRAIN_COMMON["shape_per_stage"])
    for stage in module.MICRO_STAGES:
        counts[stage] = max(counts.get(stage, 0), module.TRAIN_COMMON["micro_per_stage"])
    counts[module.CORNER_STAGE] = 500
    return counts


def _fake_repo(tmp_path: Path, module) -> Path:
    root = tmp_path / "repo"
    weak_rel = (
        Path("Experiments")
        / "R50_PSFControlDiagnosis"
        / "results"
        / "psf_control_diagnosis"
        / "generated_controls"
        / "weak_bads_alpha050"
    )
    for idx in range(module.TRAIN_COMMON["ring_limit"]):
        _write_ring_pair(root, f"{idx:04d}.bmp")
    for stage, count in _required_stage_counts(module).items():
        for idx in range(count):
            name = f"{idx:04d}.bmp"
            if stage == module.CORNER_STAGE:
                _write_stage_pair(root, "generated_convolved", stage, name, 96)
                _write_stage_pair(root, "generated_convolved_gaussian_control", stage, name, 104)
                _write_external_pair(root, weak_rel, stage, name, 112)
            else:
                _write_stage_pair(root, "generated_convolved", stage, name, 128)
    return root


def test_r52_formal_train_plan_extends_r51_core_with_r48_corner_stability_sources(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path, module)

    train = module.build_plan(repo, module.PROFILES["r52_corner_stability_train_4000"])
    val = module.build_plan(repo, module.PROFILES["r52_corner_stability_val"])

    assert len(train.pairs) == 4000
    assert train.count_by_role == {
        "ring": 550,
        "shape": 350,
        "micro": 250,
        "corner": 400,
        "boundary": 1800,
        "real_bg": 650,
    }
    assert train.count_by_corner_source == {
        "formal_bads": 134,
        "gaussian": 133,
        "weak_bads_alpha050": 133,
    }
    assert val.count_by_corner_source == {
        "formal_bads": 34,
        "gaussian": 33,
        "weak_bads_alpha050": 33,
    }
    module.assert_disjoint_plans(train, val)


def test_materialize_plan_writes_geometry_sidecars_and_manifest(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path, module)
    small = module.Profile(
        name="unit_small",
        corner_source_mode="mixed_psf",
        include_ring=True,
        ring_limit=2,
        shape_per_stage=1,
        shape_start_index=0,
        micro_per_stage=1,
        micro_start_index=0,
        corner_per_stage=6,
        corner_start_index=0,
        boundary_quotas={module.STAGE_53_REAL_CORNER: 2, module.STAGE_54_LATTICE_INTERSECTIONS: 1},
        real_bg_quotas={module.STAGE_55_REAL_TEXTURE: 2},
        start_offsets={},
        description="small unit profile",
    )

    plan = module.build_plan(repo, small)
    out = tmp_path / "pkg"
    manifest = module.materialize_plan(plan, out, force=False, link_mode="copy")

    assert manifest["profile"] == "unit_small"
    assert manifest["geometry_sidecars"] is True
    assert manifest["geometry_count"] == len(plan.pairs)
    assert manifest["count_by_corner_source"] == {
        "formal_bads": 2,
        "gaussian": 2,
        "weak_bads_alpha050": 2,
    }
    first = manifest["pairs"][0]
    assert (out / first["package_src"]).exists()
    assert (out / first["geometry_boundary"]).exists()
    assert (out / first["geometry_centerline"]).exists()
    assert (out / first["geometry_distance"]).exists()
