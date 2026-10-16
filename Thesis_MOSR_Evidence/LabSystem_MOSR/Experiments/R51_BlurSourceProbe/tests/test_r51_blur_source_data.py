from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "r51_blur_source_data.py"


def load_module():
    spec = importlib.util.spec_from_file_location("r51_blur_source_data", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_pair(root: Path, src_root_name: str, stage: str, name: str, payload: str) -> None:
    src = root / "Training_Data" / src_root_name / stage / name
    lbl = root / "Training_Data" / "generated" / stage / name
    src.parent.mkdir(parents=True, exist_ok=True)
    lbl.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(f"src-{payload}", encoding="utf-8")
    lbl.write_text(f"lbl-{stage}-{name}", encoding="utf-8")


def _write_external_pair(root: Path, rel_root: Path, stage: str, name: str, payload: str) -> None:
    src = root / rel_root / stage / name
    lbl = root / "Training_Data" / "generated" / stage / name
    src.parent.mkdir(parents=True, exist_ok=True)
    lbl.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(f"src-{payload}", encoding="utf-8")
    lbl.write_text(f"lbl-{stage}-{name}", encoding="utf-8")


def _write_ring_pair(root: Path, name: str) -> None:
    src = root / "Training_Data" / "tra_src_ring" / name
    lbl = root / "Training_Data" / "tra_lbl_ring" / name
    src.parent.mkdir(parents=True, exist_ok=True)
    lbl.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("src-ring", encoding="utf-8")
    lbl.write_text("lbl-ring", encoding="utf-8")


def _fake_repo(tmp_path: Path) -> Path:
    module = load_module()
    for idx in range(12):
        _write_ring_pair(tmp_path, f"{idx:04d}.bmp")
    for stage in (*module.SHAPE_STAGES, *module.MICRO_STAGES):
        for idx in range(120):
            _write_pair(tmp_path, "generated_convolved", stage, f"{idx:04d}.bmp", f"formal-{stage}-{idx}")
    weak_rel = Path("Experiments") / "R50_PSFControlDiagnosis" / "results" / "psf_control_diagnosis" / "generated_controls" / "weak_bads_alpha050"
    for idx in range(500):
        name = f"{idx:04d}.bmp"
        for root_name in ("generated_convolved", "generated_convolved_gaussian_control"):
            _write_pair(tmp_path, root_name, module.CORNER_STAGE, name, f"{root_name}-{idx}")
        _write_external_pair(tmp_path, weak_rel, module.CORNER_STAGE, name, f"weak-{idx}")
    return tmp_path


def test_profiles_keep_equal_pair_counts_and_isolate_blur_source(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path)

    gaussian = module.build_plan(repo, module.PROFILES["r51_gaussian_corner_probe"])
    weak = module.build_plan(repo, module.PROFILES["r51_weak_bads_corner_probe"])
    mixed = module.build_plan(repo, module.PROFILES["r51_mixed_psf_corner_probe"])

    assert len(gaussian.pairs) == len(weak.pairs) == len(mixed.pairs)
    assert gaussian.count_by_role["corner"] == 400
    assert weak.count_by_role["corner"] == 400
    assert mixed.count_by_role["corner"] == 400
    assert gaussian.count_by_corner_source == {"gaussian": 400}
    assert weak.count_by_corner_source == {"weak_bads_alpha050": 400}
    assert mixed.count_by_corner_source == {"formal_bads": 134, "gaussian": 133, "weak_bads_alpha050": 133}


def test_materialize_plan_records_blur_source_breakdown(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path / "repo")
    out = tmp_path / "pkg"
    plan = module.build_plan(repo, module.PROFILES["r51_mixed_psf_corner_probe"])

    manifest = module.materialize_plan(plan, out, force=False, link_mode="copy")

    assert manifest["profile"] == "r51_mixed_psf_corner_probe"
    assert manifest["count_by_corner_source"] == {"formal_bads": 134, "gaussian": 133, "weak_bads_alpha050": 133}
    corner_rows = [row for row in manifest["pairs"] if row["role"] == "corner"]
    assert len(corner_rows) == 400
    assert {row["corner_source"] for row in corner_rows} == {"formal_bads", "gaussian", "weak_bads_alpha050"}
    first = corner_rows[0]
    assert (out / first["package_src"]).read_text(encoding="utf-8").startswith("src-")
    assert (out / first["package_lbl"]).read_text(encoding="utf-8").startswith("lbl-")


def test_plan_rejects_missing_corner_source(tmp_path: Path):
    module = load_module()
    repo = _fake_repo(tmp_path)
    missing = (
        repo
        / "Training_Data"
        / "generated_convolved_gaussian_control"
        / module.CORNER_STAGE
        / "0000.bmp"
    )
    missing.unlink()

    try:
        module.build_plan(repo, module.PROFILES["r51_gaussian_corner_probe"])
    except ValueError as exc:
        assert "missing corner source" in str(exc)
    else:
        raise AssertionError("missing Gaussian corner source was not rejected")

