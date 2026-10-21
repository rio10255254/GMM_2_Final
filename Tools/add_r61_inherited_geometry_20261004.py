"""Freeze the original annotations for all inherited R61 source rows."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil

PROJECT = Path(__file__).resolve().parents[1]
PACKAGE = PROJECT / "Deliverables/R61_TrainingData_Regenerator_20261004"
VALIDATION = PROJECT / "Validations/R61_TrainingData_Regenerator_20261004"
DATA = PROJECT / "Thesis_MOSR_Evidence/LabSystem_MOSR/Training_Data/r61_universal_boundary_generalization/hs100mg_basler/r61_universal_boundary_train_motion_texture_step_guard_v16"


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    reference = PACKAGE / "reference"
    for source, destination in (("full_rebuild_check.json", "raw_original_generator_rebuild_check.json"), ("portability_check.json", "raw_original_generator_portability_check.json")):
        target = VALIDATION / destination
        if target.exists():
            raise FileExistsError(target)
        shutil.copy2(VALIDATION / source, target)
    shutil.copy2(VALIDATION / "raw_original_generator_rebuild_check.json", reference / "original_generator_rebuild_check.json")
    recipe = json.loads((PACKAGE / "recipe.json").read_text(encoding="utf-8"))
    manifest = json.loads((reference / "original_v16_manifest.json").read_text(encoding="utf-8"))
    roles = {item["role"]: item["package_dir"] for item in recipe["source_inputs"]}
    expected = {
        item["path"]: item
        for item in (json.loads(line) for line in (reference / "expected_training_files.jsonl").read_text(encoding="utf-8").splitlines())
    }
    old_inputs = [json.loads(line) for line in (reference / "input_files.jsonl").read_text(encoding="utf-8").splitlines()]
    index = []
    operations = []
    for row in manifest["pairs"]:
        if row["role"] not in roles:
            continue
        files = []
        for field in ("geometry_boundary", "geometry_centerline", "geometry_distance"):
            relative = row[field]
            source_relative = roles[row["role"]] + "/r61_geometry/" + relative
            files.append({"field": field, "source": source_relative, "output": relative})
            operations.append((relative, source_relative))
        index.append({"package_lbl": row["package_lbl"], "files": files})
    if len(index) != 3400 or len(operations) != 10200:
        raise RuntimeError("Wrong number of original inherited annotation files")
    def copy_and_check(operation):
        relative, packaged = operation
        destination = PACKAGE / packaged
        if destination.exists():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(DATA / relative, destination)
        row = expected[relative]
        if destination.stat().st_size != row["bytes"] or sha256(destination) != row["sha256"]:
            raise RuntimeError(f"Annotation differs from locked original reference: {relative}")
        return {"path": packaged, "bytes": row["bytes"], "sha256": row["sha256"]}
    print("Copying and checking all 10,200 inherited annotation files...", flush=True)
    added = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for count, row in enumerate(pool.map(copy_and_check, operations), 1):
            added.append(row)
            if count % 2000 == 0:
                print(f"Original inherited annotation files: {count}/10200", flush=True)
    index_path = reference / "inherited_geometry.json"
    write_json(index_path, index)
    old_inputs.extend(added)
    old_inputs.append({"path": index_path.relative_to(PACKAGE).as_posix(), "bytes": index_path.stat().st_size, "sha256": sha256(index_path)})
    with (reference / "input_files.jsonl").open("w", encoding="utf-8") as handle:
        for row in sorted(old_inputs, key=lambda item: item["path"]):
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    recipe["inherited_geometry_index"] = "reference/inherited_geometry.json"
    recipe["inherited_geometry_policy"] = "Import frozen original annotations for all 3400 inherited pairs; regenerate all 16896 synthetic pairs and annotations with the original program"
    write_json(PACKAGE / "recipe.json", recipe)
    provenance = json.loads((reference / "provenance.json").read_text(encoding="utf-8"))
    provenance["inherited_annotation_files"] = 10200
    provenance["original_generator_rebuild"] = "114268 of 114283 files equal; 15 geometry files from 5 inherited SEM rows differ; all image/label files and all synthetic files equal"
    provenance["observed_annotation_non_uniqueness"] = "12 identical original labels for real_via_036 have two different historical geometry variants; original standalone package contains the same variants"
    provenance["wrapper_changes"] = "Explicit local inputs, locked v16 recipe, independent copies, frozen original geometry for all inherited pairs, original synthetic generation and grouped split, refuse existing outputs, automatic exact file verification"
    write_json(reference / "provenance.json", provenance)
    print(json.dumps({"inherited_pairs": len(index), "annotation_files": len(added), "checked_input_files": len(old_inputs), "added_annotation_bytes": sum(row['bytes'] for row in added)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
