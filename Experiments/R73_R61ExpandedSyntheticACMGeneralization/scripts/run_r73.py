from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(os.environ.get("GMM_ACM_EXPERIMENT_ROOT", Path(__file__).resolve().parents[1]))
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
DATA = Path(CONFIG["dataset"]["root"])
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
RECON_ROOT = RESULTS / "inference_runs"
PYTHON = Path(CONFIG["inference"]["python"])
MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_paths(directory: Path) -> list[Path]:
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    return sorted(path for path in directory.iterdir() if path.suffix.lower() == ".bmp")


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise OSError(f"Cannot read image: {path}")
    return image


def audit_inputs() -> dict:
    manifest_path = DATA / "manifest.json"
    manifest = read_json(manifest_path)
    expected_per = int(CONFIG["dataset"]["images_per_family"])
    expected_total = int(CONFIG["dataset"]["total_images"])
    expected_names = [f"{index:04d}.bmp" for index in range(expected_per)]
    if "difficulty_status" in manifest:
        if manifest.get("difficulty_status") != "frozen_passed_raw_only_gate":
            raise RuntimeError("Raw-only difficulty set is not frozen")
        difficulty_gate = manifest.get("difficulty_gate", {})
        if difficulty_gate.get("uses_r61") or not difficulty_gate.get("passed"):
            raise RuntimeError("Frozen difficulty gate is not a passed Raw-only calibration")
        frozen_files = sorted(
            DATA / kind / family["stage"] / filename
            for kind in ("src", "lbl", "mask")
            for family in CONFIG["dataset"]["families"]
            for filename in expected_names
        )
        frozen_hash = hashlib.sha256(
            "".join(sha256(path) for path in frozen_files).encode("ascii")
        ).hexdigest()
        if len(frozen_files) != int(manifest.get("frozen_file_count", -1)) or frozen_hash != manifest.get("frozen_content_sha256"):
            raise RuntimeError("Frozen difficulty images changed after calibration")
    records = []
    test_files: list[Path] = []
    retry_counts: dict[str, int] = {}
    for family in CONFIG["dataset"]["families"]:
        name, stage = family["name"], family["stage"]
        paths_by_kind = {kind: image_paths(DATA / kind / stage) for kind in ("src", "lbl", "mask")}
        for kind, paths in paths_by_kind.items():
            if [path.name for path in paths] != expected_names:
                raise RuntimeError(f"{stage}/{kind}: filenames do not match the frozen 20-image set")
        for index, filename in enumerate(expected_names):
            images = {kind: read_gray(DATA / kind / stage / filename) for kind in ("src", "lbl", "mask")}
            if any(image.shape != (512, 512) for image in images.values()):
                raise RuntimeError(f"{stage}/{filename}: expected 512 x 512 images")
            mask = images["mask"] > 0
            if set(np.unique(images["mask"]).tolist()) - {0, 255}:
                raise RuntimeError(f"{stage}/{filename}: geometry mask is not binary")
            count, _ = cv2.connectedComponents(mask.astype(np.uint8), 8)
            if count != 2:
                raise RuntimeError(f"{stage}/{filename}: expected one connected object")
            flood = mask.astype(np.uint8).copy()
            contours, hierarchy = cv2.findContours(flood, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
            holes = 0 if hierarchy is None else int(np.count_nonzero(hierarchy[0, :, 3] >= 0))
            if len(contours) != 1 or holes:
                raise RuntimeError(f"{stage}/{filename}: mask is not one simply-connected closed contour")
            records.append({
                "family": name,
                "family_label_tw": family["label_tw"],
                "stage": stage,
                "filename": filename,
                "area_fraction": float(mask.mean()),
                "raw_mean": float(images["src"].mean()),
                "raw_std": float(images["src"].std()),
            })
            test_files.extend((DATA / "src" / stage / filename, DATA / "lbl" / stage / filename))
        retry_counts[name] = sum(
            int(item.get("generation_attempt", 0)) > 0
            for item in manifest["records"] if item["family"] == name
        )
    if len(records) != expected_total or int(manifest["total_images"]) != expected_total:
        raise RuntimeError("Dataset total does not match the frozen experiment configuration")

    checkpoint = Path(CONFIG["model"]["checkpoint"])
    checkpoint_hash = sha256(checkpoint)
    if checkpoint_hash != CONFIG["model"]["checkpoint_sha256"]:
        raise RuntimeError("R61 checkpoint hash changed")
    training_root = Path(CONFIG["model"]["training_profile_root"])
    training_manifest = read_json(Path(CONFIG["model"]["training_manifest"]))
    test_sizes = {path.stat().st_size for path in test_files}
    training_candidates: list[Path] = []
    test_path_tokens = tuple(
        [DATA.name.lower()]
        + [str(family["stage"]).lower() for family in CONFIG["dataset"]["families"]]
    )
    path_reference_hits = 0
    for pair in training_manifest["pairs"]:
        searchable = " ".join(str(value).lower() for value in pair.values() if isinstance(value, str))
        path_reference_hits += int(any(token in searchable for token in test_path_tokens))
        for key in ("package_src", "package_lbl"):
            candidate = training_root / pair[key]
            if candidate.exists() and candidate.stat().st_size in test_sizes:
                training_candidates.append(candidate)
    test_hashes = {sha256(path) for path in test_files}
    training_hashes = {sha256(path) for path in training_candidates}
    overlap = test_hashes & training_hashes
    if path_reference_hits or overlap:
        raise RuntimeError(f"Training overlap detected: paths={path_reference_hits}, hashes={len(overlap)}")

    audit = {
        "experiment_id": CONFIG["experiment_id"],
        "dataset_created_after_checkpoint": bool(manifest["created_after_checkpoint"]),
        "total_images": len(records),
        "family_counts": dict(Counter(row["family"] for row in records)),
        "image_shape": [512, 512],
        "binary_exact_geometry_masks": True,
        "one_closed_connected_object_per_image": True,
        "generator_retry_image_counts": retry_counts,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_hash,
        "r61_training_profile": training_manifest["profile"],
        "r61_training_total_pairs": int(training_manifest["total_pairs"]),
        "training_path_reference_hits": path_reference_hits,
        "same_size_training_files_hashed": len(training_candidates),
        "test_source_and_label_files_hashed": len(test_files),
        "exact_content_overlap_hashes": len(overlap),
        "independent_of_r61_training": True,
        "difficulty_status": manifest.get("difficulty_status", "not_applicable"),
        "difficulty_calibration_uses_r61": bool(manifest.get("difficulty_gate", {}).get("uses_r61", False)),
        "frozen_file_count": int(manifest.get("frozen_file_count", 0)),
        "frozen_content_sha256": manifest.get("frozen_content_sha256"),
        "acm_truth": "exact generator geometry mask",
        "acm_seed_uses_truth_shape": False,
        "scale_fitting": False,
        "rotation_fitting": False,
        "records": records,
    }
    write_json(RESULTS / "input_audit.json", audit)
    print(json.dumps({key: value for key, value in audit.items() if key != "records"}, ensure_ascii=False, indent=2))
    return audit


def output_name(family: str) -> str:
    prefix = CONFIG.get("pipeline", {}).get("output_prefix", "r61v16_psfoff_r73")
    return f"{prefix}_{family}"


def find_output(stage: str, family: str) -> Path | None:
    candidates = []
    for run_dir in RECON_ROOT.glob(f"reconstruct_progress_best_tradeoff_in_{stage}_*"):
        candidate = run_dir / output_name(family)
        if candidate.is_dir():
            candidates.append(candidate)
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def valid_output(path: Path | None, names: list[str]) -> bool:
    if path is None or not path.is_dir():
        return False
    outputs = image_paths(path)
    return [p.name for p in outputs] == names and all(read_gray(p).shape == (512, 512) for p in outputs)


def reconstruct() -> dict:
    audit = read_json(RESULTS / "input_audit.json") if (RESULTS / "input_audit.json").exists() else audit_inputs()
    outputs: dict[str, str] = {}
    commands: list[list[str]] = []
    for family in CONFIG["dataset"]["families"]:
        name, stage = family["name"], family["stage"]
        input_dir, truth_dir = DATA / "src" / stage, DATA / "lbl" / stage
        expected = [path.name for path in image_paths(truth_dir)]
        created = find_output(stage, name)
        if not valid_output(created, expected):
            command = [
                str(PYTHON), CONFIG["inference"]["script"],
                "--weights", CONFIG["model"]["checkpoint"],
                "--input-dir", str(input_dir), "--gt-dir", str(truth_dir),
                "--recon-root", str(RECON_ROOT), "--output-name", output_name(name),
                "--device", CONFIG["inference"]["device"], "--select-mode", "all",
                "--exts", CONFIG["inference"]["extension"],
                "--psf-fitted-path", CONFIG["model"]["psf_fitted_path"],
                "--no-psf-from-ckpt", "--weak-psf-disable",
                "--psf-deconv-reg", "30", "--psf-phys-alpha", "0",
            ]
            print("RUN:", subprocess.list2cmdline(command), flush=True)
            subprocess.run(command, check=True, cwd=ROOT)
            created = find_output(stage, name)
            if not valid_output(created, expected):
                raise RuntimeError(f"Incomplete reconstruction for {name}")
            commands.append(command)
        outputs[name] = str(created)
    result = {
        "model": CONFIG["model"]["name"],
        "checkpoint": audit["checkpoint"],
        "checkpoint_sha256": audit["checkpoint_sha256"],
        "locked_mode": {"psf_from_checkpoint": False, "weak_psf": False, "psf_deconv_reg": 30, "psf_phys_alpha": 0},
        "reconstructed_images": sum(len(image_paths(Path(path))) for path in outputs.values()),
        "output_dirs": outputs,
        "commands_executed_this_run": commands,
    }
    write_json(RESULTS / "inference_manifest.json", result)
    print(json.dumps({key: value for key, value in result.items() if key != "commands_executed_this_run"}, ensure_ascii=False, indent=2))
    return result


def run_acm(force: bool) -> None:
    required = [TABLES / "primary_contour_metrics.csv", TABLES / "truth_acm_geometry_qa.csv", TABLES / "acm_sensitivity_metrics.csv"]
    if not force and all(path.exists() and path.stat().st_size > 0 for path in required):
        print("Reusing complete ACM extraction")
        return
    if not MATLAB.exists():
        raise FileNotFoundError(MATLAB)
    configured_dir = CONFIG.get("pipeline", {}).get("acm_script_dir")
    script_dir = str(Path(configured_dir) if configured_dir else ROOT / "scripts").replace("'", "''")
    experiment_root = str(ROOT).replace("'", "''")
    expression = f"addpath('{script_dir}'); run_acm_extraction('{experiment_root}')"
    subprocess.run([str(MATLAB), "-batch", expression], check=True, cwd=ROOT)


def run_analysis() -> None:
    script_name = CONFIG.get("pipeline", {}).get("analysis_script", "analyze_r73.py")
    subprocess.run([str(PYTHON), str(ROOT / "scripts" / script_name)], check=True, cwd=ROOT)


def run_tests() -> None:
    subprocess.run([str(PYTHON), "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"], check=True, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Run frozen {CONFIG['experiment_id']} ACM contour validation")
    parser.add_argument("--stage", choices=("generate", "audit", "reconstruct", "acm", "analysis", "test", "all"), default="all")
    parser.add_argument("--force-generate", action="store_true")
    parser.add_argument("--force-acm", action="store_true")
    args = parser.parse_args()
    if args.stage in ("generate", "all"):
        command = [str(PYTHON), str(ROOT / "scripts" / "generate_dataset.py")]
        if args.force_generate:
            command.append("--force")
        subprocess.run(command, check=True, cwd=ROOT)
    if args.stage in ("audit", "all"): audit_inputs()
    if args.stage in ("reconstruct", "all"): reconstruct()
    if args.stage in ("acm", "all"): run_acm(args.force_acm)
    if args.stage in ("analysis", "all"): run_analysis()
    if args.stage in ("test", "all"): run_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
