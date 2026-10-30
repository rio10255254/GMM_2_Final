"""Quick integrity check for the portable R61 standalone package."""
from __future__ import annotations

import json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parent
REQUIRED_FILES = (
    "train_r61.py",
    "infer_r61.py",
    "train_core_r61.py",
    "model_r61.py",
    "utils_r61.py",
    "psf/PSF_fitted_2D_FOVstack.mat",
    "weights/best_tradeoff.pth.tar",
    "weights/base_v14_motion_texture_best_tradeoff.pth.tar",
    "weights/teacher_r39_best_latest_a970.pth.tar",
    "training_data/manifest.json",
    "training_data/src",
    "training_data/lbl",
    "training_data/geom",
    "scripts/launch_r61.py",
    "scripts/prepare_r61_universal_dataset.py",
    "scripts/run_diverse_phantom_validation.py",
    "scripts/score_generalization_gate.py",
    "scripts/score_dual_generalization_gate.py",
    "scripts/score_triple_generalization_gate.py",
)
CORE_FILES = (
    "train_r61.py",
    "infer_r61.py",
    "train_core_r61.py",
    "scripts/launch_r61.py",
    "scripts/launch_r60.py",
    "scripts/run_diverse_phantom_validation.py",
    "scripts/run_synthetic_phantom_validation.py",
    "scripts/prepare_r61_universal_dataset.py",
)
FORBIDDEN_PATH_MARKERS = (
    str(PROJECT_ROOT / 'LabSystem_MOSR'),
    str(PROJECT_ROOT / 'Model'),
    r"C:\Users\Rio\Downloads",
    "__CURRENT_SELECTED_SEED__",
)


def _file_count(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file())


def main() -> int:
    missing = [item for item in REQUIRED_FILES if not (ROOT / item).exists()]
    if missing:
        print(json.dumps({"pass": False, "missing": missing}, indent=2, ensure_ascii=False))
        return 1

    manifest = json.loads((ROOT / "training_data/manifest.json").read_text(encoding="utf-8"))
    expected_roles = {
        "legacy_shape": 800,
        "sequence_guard": 1200,
        "sem_truth_anchor": 1400,
        "universal_synthetic": 4096,
        "motion_synthetic": 4800,
        "motion_texture_synthetic": 4800,
        "step_guard_motion_texture_synthetic": 3200,
    }
    role_counts = {str(k): int(v) for k, v in dict(manifest.get("role_counts", {})).items()}
    checks = {
        "total_pairs": int(manifest.get("total_pairs", -1)) == 20296,
        "role_counts": role_counts == expected_roles,
        "src_files": _file_count(ROOT / "training_data/src") == 20296,
        "lbl_files": _file_count(ROOT / "training_data/lbl") == 20296,
        "geom_files": _file_count(ROOT / "training_data/geom") >= 60000,
    }
    external_markers: list[str] = []
    for relative in CORE_FILES:
        text = (ROOT / relative).read_text(encoding="utf-8", errors="replace")
        for marker in FORBIDDEN_PATH_MARKERS:
            if marker in text:
                external_markers.append(f"{relative}: {marker}")
    checks["no_original_absolute_paths_in_core"] = not external_markers
    checks["all_checks"] = all(checks.values())
    result = {
        "pass": bool(checks["all_checks"]),
        "package_root": str(ROOT),
        "checks": checks,
        "external_markers": external_markers,
        "manifest_total_pairs": manifest.get("total_pairs"),
        "role_counts": role_counts,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
