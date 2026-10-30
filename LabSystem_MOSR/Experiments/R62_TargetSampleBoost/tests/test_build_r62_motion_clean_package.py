from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[4]


SCRIPTS_DIR = Path(
    str(PROJECT_ROOT / 'LabSystem_MOSR/Experiments/R62_TargetSampleBoost/scripts')
)
sys.path.insert(0, str(SCRIPTS_DIR))


def _touch(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _toy_pair(stage: str, name: str, role: str) -> dict[str, object]:
    stem = f"{stage}/{name}"
    return {
        "role": role,
        "package_src": f"src/{stem}.bmp",
        "package_lbl": f"lbl/{stem}.bmp",
        "geometry_boundary": f"geom/boundary/{stem}.bmp",
        "geometry_centerline": f"geom/centerline/{stem}.bmp",
        "geometry_distance": f"geom/distance/{stem}.npy",
        "motion_meta": f"geom/meta/{stem}.json",
    }


def _write_toy_package(root: Path) -> None:
    pairs = [
        _toy_pair("stage_keep", "a", "legacy_shape"),
        _toy_pair("stage_drop", "b", "target_real_motion_pair"),
        _toy_pair("stage_drop", "c", "target_real_selfshift_motion_pair"),
    ]
    for pair in pairs:
        for key in (
            "package_src",
            "package_lbl",
            "geometry_boundary",
            "geometry_centerline",
            "geometry_distance",
            "motion_meta",
        ):
            _touch(root / str(pair[key]), key)
    manifest = {
        "profile": "toy_v3",
        "r61_universal_boundary_training": True,
        "anti_answer_leakage_design": True,
        "geometry_sidecars": True,
        "geometry_count": 3,
        "total_pairs": 3,
        "role_counts": {
            "legacy_shape": 1,
            "target_real_motion_pair": 1,
            "target_real_selfshift_motion_pair": 1,
        },
        "pairs": pairs,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _write_audit_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["manifest_index", "risk_type"])
        writer.writeheader()
        writer.writerow({"manifest_index": 1, "risk_type": "direct_label_conflict"})
        writer.writerow({"manifest_index": 2, "risk_type": "source_texture_only"})


def test_create_clean_package_drops_requested_risk_types_and_copies_sidecars(tmp_path: Path) -> None:
    from build_r62_motion_clean_package import create_clean_package

    source = tmp_path / "source"
    dest = tmp_path / "dest"
    audit_csv = tmp_path / "audit.csv"
    _write_toy_package(source)
    _write_audit_csv(audit_csv)

    summary = create_clean_package(
        source_package=source,
        dest_package=dest,
        affected_pairs_csv=audit_csv,
        new_profile="toy_clean",
        drop_risk_types=("direct_label_conflict", "source_texture_only"),
        link_mode="copy",
    )

    clean_manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    assert summary["kept_pair_count"] == 1
    assert summary["dropped_pair_count"] == 2
    assert clean_manifest["profile"] == "toy_clean"
    assert clean_manifest["total_pairs"] == 1
    assert clean_manifest["role_counts"] == {"legacy_shape": 1}
    assert clean_manifest["r62_motion_quality_filter"]["dropped_by_risk"] == {
        "direct_label_conflict": 1,
        "source_texture_only": 1,
    }
    assert (dest / "src/stage_keep/a.bmp").exists()
    assert not (dest / "src/stage_drop/b.bmp").exists()
    assert (dest / "geom/meta/stage_keep/a.json").exists()
