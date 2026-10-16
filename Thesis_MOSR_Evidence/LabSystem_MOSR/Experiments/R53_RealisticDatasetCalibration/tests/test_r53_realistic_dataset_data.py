from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "r53_realistic_dataset_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r53_realistic_dataset_data", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_image(path: Path, value: int = 128) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = np.full((48, 48), value, dtype=np.uint8)
    cv2.rectangle(img, (10, 10), (37, 37), min(255, value + 60), -1)
    ok, encoded = cv2.imencode(path.suffix, img)
    assert ok
    path.write_bytes(encoded.tobytes())


def _write_pair(root: Path, stage: str, name: str, value: int = 128) -> None:
    _write_image(root / "Training_Data" / "generated_convolved" / stage / name, max(0, value - 24))
    _write_image(root / "Training_Data" / "generated" / stage / name, value)


def _write_ring_pair(root: Path, name: str) -> None:
    _write_image(root / "Training_Data" / "tra_src_ring" / name, 72)
    _write_image(root / "Training_Data" / "tra_lbl_ring" / name, 196)


def _write_corner_triplet(root: Path, stage: str, name: str, value: int = 160) -> None:
    _write_image(root / "Training_Data" / "generated" / stage / name, value)
    _write_image(root / "Training_Data" / "generated_convolved" / stage / name, 96)
    _write_image(root / "Training_Data" / "generated_convolved_gaussian_control" / stage / name, 108)
    weak_root = (
        root
        / "Experiments"
        / "R50_PSFControlDiagnosis"
        / "results"
        / "psf_control_diagnosis"
        / "generated_controls"
        / "weak_bads_alpha050"
        / stage
    )
    _write_image(weak_root / name, 118)


def _fake_anchor_root(root: Path, train_count: int = 420, val_count: int = 140) -> Path:
    anchor = root / "Training_Data" / "r53_cad_anchor_source"
    records = []
    for split, count in (("train", train_count), ("val", val_count)):
        for idx in range(count):
            name = f"CAD_{split}_{idx:04d}.bmp"
            src_rel = Path(split) / "src" / "cad_anchor" / name
            lbl_rel = Path(split) / "lbl" / "cad_anchor" / name
            mask_rel = Path(split) / "mask" / "cad_anchor" / name
            src = np.full((48, 48), 42 + (idx % 17), dtype=np.uint8)
            lbl = src.copy()
            mask = np.zeros((48, 48), dtype=np.uint8)
            cv2.rectangle(mask, (12, 12), (35, 35), 255, -1)
            lbl[mask > 0] = 220
            for rel, img in ((src_rel, src), (lbl_rel, lbl), (mask_rel, mask)):
                _write_raw(anchor / rel, img)
            records.append(
                {
                    "split": split,
                    "pair_id": f"CAD_{split}_{idx:04d}",
                    "src": src_rel.as_posix(),
                    "lbl": lbl_rel.as_posix(),
                    "mask": mask_rel.as_posix(),
                }
            )
    manifest = {
        "valid_pair_count": 36,
        "split_patch_counts": {"train": train_count, "val": val_count, "test": 0},
        "records": records,
    }
    (anchor / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return anchor


def _write_raw(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    assert ok
    path.write_bytes(encoded.tobytes())


def _required_stage_counts(module) -> dict[str, int]:
    counts: dict[str, int] = {}
    for profile in module.PROFILES.values():
        for stage, quota in profile.shape_quotas.items():
            counts[stage] = max(counts.get(stage, 0), profile.start_offsets.get(stage, 0) + quota)
        for stage, quota in profile.micro_quotas.items():
            counts[stage] = max(counts.get(stage, 0), profile.start_offsets.get(stage, 0) + quota)
        for stage, quota in profile.boundary_quotas.items():
            counts[stage] = max(counts.get(stage, 0), profile.start_offsets.get(stage, 0) + quota)
        for stage, quota in profile.real_bg_quotas.items():
            counts[stage] = max(counts.get(stage, 0), profile.start_offsets.get(stage, 0) + quota)
        if profile.corner_per_stage > 0:
            counts[module.CORNER_STAGE] = max(
                counts.get(module.CORNER_STAGE, 0), profile.corner_start_index + profile.corner_per_stage
            )
    return counts


def _fake_repo(tmp_path: Path, module) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    for idx in range(720):
        _write_ring_pair(root, f"{idx:04d}.bmp")
    for stage, count in _required_stage_counts(module).items():
        for idx in range(count):
            name = f"{idx:04d}.bmp"
            if stage == module.CORNER_STAGE:
                _write_corner_triplet(root, stage, name)
            else:
                _write_pair(root, stage, name)
    return root, _fake_anchor_root(root)


def test_r53_train_plan_is_balanced_and_keeps_mixed_psf_corner_sources(tmp_path: Path):
    module = load_module()
    repo, anchor = _fake_repo(tmp_path, module)

    train = module.build_plan(repo, module.PROFILES["r53_realistic_calibrated_train_6000"], anchor_root=anchor)
    val = module.build_plan(repo, module.PROFILES["r53_realistic_calibrated_val"], anchor_root=anchor)

    assert len(train.pairs) == 6000
    assert train.count_by_role == {
        "ring": 700,
        "shape": 700,
        "micro": 900,
        "corner": 300,
        "boundary": 2050,
        "real_bg": 950,
        "cad_anchor": 400,
    }
    assert train.count_by_corner_source == {
        "formal_bads": 100,
        "gaussian": 100,
        "weak_bads_alpha050": 100,
    }
    assert val.count_by_corner_source == {
        "formal_bads": 40,
        "gaussian": 40,
        "weak_bads_alpha050": 40,
    }
    module.assert_disjoint_plans(train, val)


def test_materialize_plan_writes_geometry_and_cad_masks(tmp_path: Path):
    module = load_module()
    repo, anchor = _fake_repo(tmp_path, module)
    small = module.Profile(
        name="unit_small",
        include_ring=True,
        ring_limit=2,
        shape_quotas={module.SHAPE_STAGES[0]: 1},
        micro_quotas={module.MICRO_STAGES[0]: 1},
        corner_per_stage=6,
        corner_start_index=0,
        boundary_quotas={module.STAGE_49_CHECKBOARD: 2, module.STAGE_53_REAL_CORNER: 1},
        real_bg_quotas={module.STAGE_51_REAL_BG: 1},
        cad_anchor_quota=2,
        start_offsets={},
        description="small unit profile",
    )

    plan = module.build_plan(repo, small, anchor_root=anchor)
    out = tmp_path / "pkg"
    manifest = module.materialize_plan(plan, out, force=False, link_mode="copy")

    assert manifest["profile"] == "unit_small"
    assert manifest["geometry_sidecars"] is True
    assert manifest["geometry_count"] == len(plan.pairs)
    assert manifest["cad_anchor_policy"].startswith("masked real CAD")
    assert manifest["count_by_corner_source"] == {
        "formal_bads": 2,
        "gaussian": 2,
        "weak_bads_alpha050": 2,
    }

    cad_rows = [row for row in manifest["pairs"] if row["role"] == "cad_anchor"]
    assert len(cad_rows) == 2
    first = cad_rows[0]
    assert (out / first["package_mask"]).exists()
    assert (out / first["geometry_boundary"]).exists()
    src = cv2.imread(str(out / first["package_src"]), cv2.IMREAD_GRAYSCALE)
    lbl = cv2.imread(str(out / first["package_lbl"]), cv2.IMREAD_GRAYSCALE)
    mask = cv2.imread(str(out / first["package_mask"]), cv2.IMREAD_GRAYSCALE)
    assert np.array_equal(lbl[mask == 0], src[mask == 0])
    assert np.any(lbl[mask > 0] != src[mask > 0])
