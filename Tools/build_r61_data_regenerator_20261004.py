"""Package the original R61 generator, frozen inputs and the historical file checks."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil

PROJECT = Path(__file__).resolve().parents[1]
LAB = PROJECT / "LabSystem_MOSR"
PACKAGE = PROJECT / "Deliverables" / "Data_Regenerators" / "R61_TrainingData_Regenerator_20261004"
DATA = LAB / "Training_Data" / "r61_universal_boundary_generalization" / "hs100mg_basler" / "r61_universal_boundary_train_motion_texture_step_guard_v16"
GENERATOR = LAB / "Experiments" / "R61_BoundaryGeneralizationUniversal" / "scripts" / "prepare_r61_universal_dataset.py"
SOURCE_INPUTS = [
    ("legacy_shape", "r39_shape_mix_strong", "r39_shape_generalization/r39_shape_mix_strong", 800),
    ("sequence_guard", "r58_frac050_train", "r60_full_power/hs100mg_basler/r58_frac050_train", 1200),
    ("sem_truth_anchor", "r60_sem_truth_realcrop_anchor_train", "r60_sem_truth_boundary/hs100mg_basler/r60_sem_truth_realcrop_anchor_train", 1400),
]


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def record(root: Path, relative: str) -> dict:
    path = root / relative
    return {"path": relative, "bytes": path.stat().st_size, "sha256": digest(path)}


def main() -> None:
    for reserved in (PACKAGE / "source_data", PACKAGE / "reference", PACKAGE / "original"):
        if reserved.exists():
            raise FileExistsError(f"Refusing to replace an existing packaged source: {reserved}")
    original = PACKAGE / "original" / GENERATOR.name
    original.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(GENERATOR, original)
    reference = PACKAGE / "reference"
    reference.mkdir(parents=True)
    shutil.copy2(DATA / "manifest.json", reference / "original_v16_manifest.json")
    expected = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    source_info = []
    input_paths = []
    for role, name, relative, limit in SOURCE_INPUTS:
        upstream = LAB / "Training_Data" / relative
        original_manifest = upstream / "manifest.json"
        manifest = json.loads(original_manifest.read_text(encoding="utf-8"))
        pairs = manifest["pairs"][:limit]
        if len(pairs) != limit:
            raise RuntimeError(f"Missing source rows for {role}")
        destination = PACKAGE / "source_data" / name
        for pair in pairs:
            for field in ("package_src", "package_lbl"):
                src = upstream / pair[field]
                dst = destination / pair[field]
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                if digest(src) != digest(dst):
                    raise RuntimeError(f"Source copy differs: {src}")
                input_paths.append(dst.relative_to(PACKAGE).as_posix())
        selected_manifest = {
            "profile": name,
            "total_pairs": limit,
            "snapshot_original_total_pairs": manifest["total_pairs"],
            "selection": "First rows in the original manifest, in the original order",
            "pairs": pairs,
        }
        write_json(destination / "manifest.json", selected_manifest)
        input_paths.append((destination / "manifest.json").relative_to(PACKAGE).as_posix())
        shutil.copy2(original_manifest, reference / f"original_upstream_{name}_manifest.json")
        source_info.append({
            "role": role, "package_dir": f"source_data/{name}", "limit": limit,
            "historical_package": str(upstream),
            "historical_manifest_sha256": digest(original_manifest),
            "original_pair_count": manifest["total_pairs"],
        })
        print(f"Copied and checked {limit} source pairs for {role}", flush=True)
    recipe = {
        "dataset": "R61 v16 motion-texture step guard",
        "original_generator_sha256": digest(GENERATOR),
        "source_inputs": source_info,
        "generation": {
            "package_name": DATA.name,
            "synthetic_count": 4096,
            "motion_count": 2400,
            "motion_texture_count": 2400,
            "step_guard_count": 1600,
            "image_size": 256,
            "seed": 6116,
            "synthetic_bias_profile": "step_guard_v16",
        },
        "split": {"val_ratio": 0.1, "seed": 1337},
        "expected_role_counts": expected["role_counts"],
        "expected_train_count": 18266,
        "expected_validation_count": 2030,
        "environment": {"python": "3.12", "numpy": "1.26.4", "opencv": "4.12.0", "opencv_distribution": "opencv-python==4.12.0.88"},
    }
    # Confirm the recovered seed against every generated geometry identifier.
    for item in expected["pairs"]:
        role = item["role"]
        if role == "universal_synthetic":
            idx = int(Path(item["package_src"]).stem.rsplit("_", 1)[1])
            expected_seed = 6116 + idx // 2
        elif role in {"motion_synthetic", "motion_texture_synthetic", "step_guard_motion_texture_synthetic"}:
            idx = int(item["motion_sequence_id"].rsplit("seq", 1)[1])
            offset = {"motion_synthetic": 0, "motion_texture_synthetic": 17000, "step_guard_motion_texture_synthetic": 23000}[role]
            expected_seed = 6116 + 100000 + offset + idx
        else:
            continue
        if int(item["geometry_id"].rsplit(":", 1)[1]) != expected_seed:
            raise RuntimeError("Recovered seed does not match the historical geometry records")
    write_json(PACKAGE / "recipe.json", recipe)
    with (reference / "input_files.jsonl").open("w", encoding="utf-8") as handle:
        for relative in sorted(set(input_paths)):
            handle.write(json.dumps(record(PACKAGE, relative), ensure_ascii=False) + "\n")
    expected_paths = set()
    for item in expected["pairs"]:
        for field in ("package_src", "package_lbl", "geometry_boundary", "geometry_centerline", "geometry_distance", "motion_meta"):
            if field in item:
                expected_paths.add(item[field])
    split = "splits/grouped_seed1337_val100/"
    expected_paths.update(split + name for name in ("train_idx.npy", "val_idx.npy", "split_meta.json"))
    if len(expected_paths) != 114283:
        raise RuntimeError(f"Unexpected historical file count: {len(expected_paths)}")
    file_counts = Counter()
    byte_count = 0
    print("Hashing all 114,283 original training files...", flush=True)
    with (reference / "expected_training_files.jsonl").open("w", encoding="utf-8") as handle:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for idx, entry in enumerate(pool.map(lambda rel: record(DATA, rel), sorted(expected_paths)), 1):
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
                byte_count += entry["bytes"]
                file_counts[entry["path"].split("/", 1)[0]] += 1
                if idx % 20000 == 0:
                    print(f"Reference hashes: {idx}/114283", flush=True)
    log = LAB / "Experiments/R61_BoundaryGeneralizationUniversal/reports/training_logs/r61_motion_texture_stepguard_v16_full_e8_20260623_200012.out.log"
    (reference / "historical_training_log_excerpt.txt").write_text("\n".join(log.read_text(encoding="utf-8").splitlines()[:55]) + "\n", encoding="utf-8")
    write_json(reference / "provenance.json", {
        "historical_data_directory": str(DATA),
        "historical_generator": str(GENERATOR),
        "original_generator_sha256": digest(GENERATOR),
        "historical_manifest_sha256": digest(DATA / "manifest.json"),
        "reference_file_count": len(expected_paths),
        "reference_file_bytes": byte_count,
        "reference_file_counts": dict(file_counts),
        "source_subset_pair_count": 3400,
        "synthetically_generated_pair_count": 16896,
        "seed_recovery": "6116 verified against every synthetic geometry_id; family offsets checked",
        "full_recipe_counts": "Original v16 manifest and original training log",
        "split_recipe": "Original launch_r61.py prepare_grouped_fixed_split and original split_meta.json",
        "original_script_is_unchanged": digest(GENERATOR) == digest(original),
        "wrapper_changes": "Explicit local input paths, locked v16 recipe, independent file copies, refuse existing outputs, original grouped split, automatic content verification",
    })
    print(json.dumps({"package": str(PACKAGE), "source_pairs": 3400, "reference_files": len(expected_paths), "reference_bytes": byte_count}, indent=2))


if __name__ == "__main__":
    main()
