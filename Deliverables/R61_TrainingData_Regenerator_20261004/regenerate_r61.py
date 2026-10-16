"""Rebuild the locked R61 v16 training dataset and verify every training file."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parent


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.drive:
        raise ValueError(f"Unsafe relative path in the reference: {value}")
    return path


def check_file(root: Path, record: dict):
    path = root / safe_relative(record["path"])
    if not path.is_file():
        return {"path": record["path"], "problem": "missing"}
    if path.stat().st_size != record["bytes"]:
        return {"path": record["path"], "problem": "size"}
    if sha256(path) != record["sha256"]:
        return {"path": record["path"], "problem": "content"}
    return None


def check_index(root: Path, index: Path) -> tuple[int, list]:
    with index.open(encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    with ThreadPoolExecutor(max_workers=4) as pool:
        failures = [result for result in pool.map(lambda row: check_file(root, row), records) if result]
    return len(records), failures


def check_inputs(recipe: dict) -> dict:
    count, failures = check_index(ROOT, ROOT / "reference" / "input_files.jsonl")
    original = ROOT / "original" / "prepare_r61_universal_dataset.py"
    if sha256(original) != recipe["original_generator_sha256"]:
        failures.append({"path": "original/prepare_r61_universal_dataset.py", "problem": "content"})
    result = {"checked_input_files": count, "failures": failures}
    if failures:
        raise RuntimeError("Required source files are missing or changed: " + json.dumps(failures[:5]))
    return result


def normalized_manifest(manifest: dict) -> dict:
    # These two fields describe the time and location of this particular rebuild.
    result = {key: value for key, value in manifest.items() if key not in {"generated_at", "pairs"}}
    result["pairs"] = [
        {key: value for key, value in row.items() if key != "source_package"}
        for row in manifest["pairs"]
    ]
    return result


def verify_dataset(dataset: Path, recipe: dict) -> dict:
    print("Checking every generated training file...", flush=True)
    count, failures = check_index(dataset, ROOT / "reference" / "expected_training_files.jsonl")
    expected = read_json(ROOT / "reference" / "original_v16_manifest.json")
    actual = read_json(dataset / "manifest.json")
    metadata_equal = normalized_manifest(actual) == normalized_manifest(expected)
    expected_paths = {
        json.loads(line)["path"]
        for line in (ROOT / "reference" / "expected_training_files.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    } | {"manifest.json"}
    actual_paths = {path.relative_to(dataset).as_posix() for path in dataset.rglob("*") if path.is_file()}
    unexpected = sorted(actual_paths - expected_paths)
    missing = sorted(expected_paths - actual_paths)
    split = read_json(dataset / "splits" / "grouped_seed1337_val100" / "split_meta.json")
    split_ok = (
        split["train_count"] == recipe["expected_train_count"]
        and split["val_count"] == recipe["expected_validation_count"]
        and split["group_overlap_count"] == 0
    )
    passed = not failures and not unexpected and not missing and metadata_equal and split_ok
    return {
        "status": "pass" if passed else "fail",
        "dataset": str(dataset.resolve()),
        "total_pairs": actual["total_pairs"],
        "role_counts": actual["role_counts"],
        "checked_training_files": count,
        "identical_training_files": count - len(failures),
        "file_failures": failures,
        "unexpected_files": unexpected,
        "missing_files": missing,
        "manifest_metadata_equal_except_generation_time_and_source_location": metadata_equal,
        "train_count": split["train_count"],
        "validation_count": split["val_count"],
        "group_overlap_count": split["group_overlap_count"],
        "fixed_split_counts_match": split_ok,
    }


def copy_pair(source: Path, destination: Path) -> None:
    # Independent copies keep generated outputs separate from frozen source inputs.
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def show_generation_progress(generator) -> None:
    imported = generator._import_legacy_pairs
    synthetic = generator._write_synthetic_pairs
    motion = generator._write_motion_synthetic_pairs

    def import_with_progress(package_dir, package_out, role, limit):
        print(f"Importing {role}: {limit} source pairs", flush=True)
        return imported(package_dir, package_out, role, limit)

    def synthetic_with_progress(package_dir, **options):
        print(f"Generating universal_synthetic: {options['count']} pairs", flush=True)
        return synthetic(package_dir, **options)

    def motion_with_progress(package_dir, **options):
        role = options.get("role", "motion_synthetic")
        print(f"Generating {role}: {2 * options['count']} pairs", flush=True)
        return motion(package_dir, **options)

    generator._import_legacy_pairs = import_with_progress
    generator._write_synthetic_pairs = synthetic_with_progress
    generator._write_motion_synthetic_pairs = motion_with_progress


def import_original_annotations(generator, recipe: dict) -> None:
    rows = read_json(ROOT / recipe["inherited_geometry_index"])
    by_label = {row["package_lbl"]: row["files"] for row in rows}
    if len(by_label) != 3400:
        raise RuntimeError("The original annotations for the 3,400 inherited pairs are incomplete")

    def copy_original_geometry(package_dir: Path, label_relative: Path) -> dict:
        files = by_label[label_relative.as_posix()]
        result = {}
        for item in files:
            source = ROOT / safe_relative(item["source"])
            relative = safe_relative(item["output"])
            copy_pair(source, package_dir / relative)
            result[item["field"]] = relative.as_posix()
        return result

    # Inherited annotations are historical inputs, just like inherited images and labels.
    # Procedural synthetic geometry is still produced by the original generator.
    generator._write_geometry_for_label = copy_original_geometry


def run(args: argparse.Namespace) -> int:
    recipe = read_json(ROOT / "recipe.json")
    inputs = check_inputs(recipe)
    if args.check_inputs:
        print(json.dumps({"status": "pass", **inputs}, indent=2))
        return 0
    if args.verify_only:
        report = verify_dataset(args.verify_only.resolve(), recipe)
    else:
        import cv2
        import numpy as np
        if np.__version__ != recipe["environment"]["numpy"] or cv2.__version__ != recipe["environment"]["opencv"]:
            raise RuntimeError("Use the locked dependencies by running install_dependencies.py in a Python 3.12 virtual environment.")
        from original import prepare_r61_universal_dataset as generator

        output_root = args.output_root.resolve()
        dataset = output_root / recipe["generation"]["package_name"]
        if dataset.exists():
            raise FileExistsError(f"Output already exists; choose a new --output-root: {dataset}")
        for reserved in (ROOT / "source_data", ROOT / "original", ROOT / "reference"):
            if dataset.is_relative_to(reserved.resolve()):
                raise ValueError(f"Output must be outside {reserved}")
        sources = [
            {"role": item["role"], "package_dir": ROOT / item["package_dir"], "limit": item["limit"]}
            for item in recipe["source_inputs"]
        ]
        # Preserve the historical inherited inputs; use unchanged original synthetic and split calculations.
        generator._copy_or_link = copy_pair
        import_original_annotations(generator, recipe)
        show_generation_progress(generator)
        print("Rebuilding all 20,296 R61 v16 pairs. This includes the original three source subsets.", flush=True)
        start = time.perf_counter()
        summary = generator.prepare_package(output_root=output_root, legacy_sources=sources, **recipe["generation"])
        manifest = read_json(dataset / "manifest.json")
        actual_counts = Counter(row["role"] for row in manifest["pairs"])
        if dict(actual_counts) != recipe["expected_role_counts"]:
            raise RuntimeError("The generated role counts do not match the original R61 v16 dataset.")
        generator.prepare_grouped_fixed_split(package_dir=dataset, manifest=manifest, **recipe["split"])
        generation_seconds = time.perf_counter() - start
        print(f"Generation finished in {generation_seconds:.1f} seconds; total pairs: {summary['total_pairs']}", flush=True)
        report = verify_dataset(dataset, recipe)
        report["generation_seconds"] = generation_seconds
        report["generation_and_verification_seconds"] = time.perf_counter() - start
        report["runtime"] = {"python": sys.version, "numpy": np.__version__, "opencv": cv2.__version__}
    report["inputs"] = inputs
    report_path = args.report.resolve() if args.report else Path(report["dataset"]).parent / "R61_REGENERATION_CHECK.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"role_counts", "runtime", "inputs"}}, indent=2, ensure_ascii=False))
    print(f"Verification report: {report_path}")
    return 0 if report["status"] == "pass" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate and check the complete original R61 v16 training data")
    parser.add_argument("--output-root", type=Path, default=ROOT / "generated_training_data")
    parser.add_argument("--check-inputs", action="store_true", help="Check required source files without generating")
    parser.add_argument("--verify-only", type=Path, help="Check an existing regenerated dataset")
    parser.add_argument("--report", type=Path, help="Optional path for the verification report")
    args = parser.parse_args()
    if args.check_inputs and args.verify_only:
        parser.error("Choose either --check-inputs or --verify-only")
    try:
        return run(args)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"R61 regeneration stopped: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
