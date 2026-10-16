from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


R81_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import evaluate_model as evaluator  # noqa: E402
from train_model import DEFAULT_PACKAGE  # noqa: E402


def normalized_relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def main() -> None:
    package = DEFAULT_PACKAGE.resolve()
    data_root = package / "training_data"
    source_root = data_root / "src"
    manifest = json.loads((data_root / "manifest.json").read_text(encoding="utf-8"))
    extensions = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
    all_paths = [
        Path(path)
        for path in sorted(
            str(path)
            for path in source_root.rglob("*")
            if path.is_file() and path.suffix.lower() in extensions
        )
    ]
    split_root = data_root / "splits" / "grouped_seed1337_val120"
    train_indices = np.load(split_root / "train_idx.npy").astype(np.int64)
    validation_indices = np.load(split_root / "val_idx.npy").astype(np.int64)
    train_paths = {
        normalized_relative(all_paths[int(index)], data_root) for index in train_indices
    }
    validation_paths = {
        normalized_relative(all_paths[int(index)], data_root) for index in validation_indices
    }

    configuration = json.loads(evaluator.SEQUENCE_CONFIG.read_text(encoding="utf-8"))
    sequence_rows: dict[str, dict[str, object]] = {}
    for sequence, specification in configuration["sequences"].items():
        pairs = evaluator.selected_pairs(sequence, limit_pairs=30)
        selected_frames = sorted(
            set(pairs["start_frame_index"].astype(int))
            | set(pairs["end_frame_index"].astype(int))
        )
        matching_paths: dict[int, list[str]] = {frame: [] for frame in selected_frames}
        for item in manifest["pairs"]:
            if (
                item.get("target_dataset") != specification["dataset"]
                or item.get("target_sequence") != specification["group"]
            ):
                continue
            source_name = str(item.get("source_frame_name", ""))
            if not source_name.startswith("frame_"):
                continue
            frame = int(source_name[6:10])
            if frame in matching_paths:
                matching_paths[frame].append(str(item["package_src"]).replace("\\", "/"))
        unmatched = [frame for frame, paths in matching_paths.items() if not paths]
        row = {
            "selected_unique_frames": len(selected_frames),
            "frames_with_any_training_package_crop": sum(
                bool(paths) for paths in matching_paths.values()
            ),
            "frames_with_train_split_crop": sum(
                any(path in train_paths for path in paths) for paths in matching_paths.values()
            ),
            "frames_with_validation_split_crop": sum(
                any(path in validation_paths for path in paths)
                for paths in matching_paths.values()
            ),
            "unmatched_frames": unmatched,
        }
        if unmatched or row["frames_with_train_split_crop"] != len(selected_frames):
            raise RuntimeError(f"Unexpected formal-frame overlap audit for {sequence}: {row}")
        sequence_rows[sequence] = row

    audit = {
        "meaning_of_external": "architecture provenance only, not an external dataset",
        "blind_external_generalization": False,
        "static_center9_is_psf_and_scale_calibration_region": True,
        "physical_frame_isolation_between_training_and_formal_displacement": False,
        "sequence_audit": sequence_rows,
        "interpretation": (
            "Every formal displacement frame has corresponding crops in the training package; "
            "the benchmark is an in-system controlled reconstruction comparison."
        ),
    }
    output = R81_ROOT / "results" / "training_frame_overlap_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
