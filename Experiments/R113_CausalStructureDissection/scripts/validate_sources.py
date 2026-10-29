"""Freeze and validate every source used by the R113 causal dissection."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "results" / "source_inventory.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_names(folder: Path) -> list[str]:
    suffixes = {".bmp", ".png", ".tif", ".tiff", ".jpg", ".jpeg"}
    return sorted(item.name for item in folder.iterdir() if item.is_file() and item.suffix.lower() in suffixes)


def score_rows(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip())


def main() -> int:
    failures: list[str] = []
    models: dict[str, dict[str, object]] = {}
    for name, spec in CONFIG["models"].items():
        checkpoint = Path(PROJECT_ROOT / spec["checkpoint"])
        exists = checkpoint.is_file()
        actual = sha256(checkpoint) if exists else None
        expected = str(spec["sha256"]).lower()
        if not exists:
            failures.append(f"missing checkpoint: {name}: {checkpoint}")
        elif actual != expected:
            failures.append(f"checkpoint hash mismatch: {name}")
        models[name] = {
            "checkpoint": str(checkpoint),
            "exists": exists,
            "bytes": checkpoint.stat().st_size if exists else None,
            "expected_sha256": expected,
            "actual_sha256": actual,
            "hash_pass": bool(actual == expected),
        }

    r112_root = Path(PROJECT_ROOT / CONFIG["reference_experiments"]["r112"])
    r112_config = json.loads((r112_root / "config" / "experiment.json").read_text(encoding="utf-8"))
    expected_images = [f"frame_{index:04d}.bmp" for index in range(101)]
    gmf_sources: dict[str, dict[str, object]] = {}
    for name, spec in r112_config["models"].items():
        folder = Path(spec["image_dir"])
        score = Path(spec["score"])
        names = image_names(folder) if folder.is_dir() else []
        rows = score_rows(score) if score.is_file() else 0
        filenames_pass = names == expected_images
        rows_pass = rows == 100
        if not filenames_pass:
            failures.append(f"GMF image population mismatch: {name}")
        if not rows_pass:
            failures.append(f"GMF coordinate row mismatch: {name}: {rows}")
        gmf_sources[name] = {
            "image_dir": str(folder),
            "image_count": len(names),
            "filenames_pass": filenames_pass,
            "score": str(score),
            "score_rows": rows,
            "score_sha256": sha256(score) if score.is_file() else None,
            "rows_pass": rows_pass,
        }

    r111_root = Path(PROJECT_ROOT / CONFIG["reference_experiments"]["r111"])
    qualification = json.loads((r111_root / "config" / "qualification.json").read_text(encoding="utf-8"))
    frozen_contract: dict[str, dict[str, object]] = {}
    for name in ("sequence_config", "top30_selection", "raw_lock"):
        path = Path(qualification["frozen_contract"][name])
        expected = str(qualification["frozen_contract"][f"{name}_sha256"]).lower()
        actual = sha256(path) if path.is_file() else None
        if actual != expected:
            failures.append(f"frozen contract mismatch: {name}")
        frozen_contract[name] = {
            "path": str(path),
            "actual_sha256": actual,
            "expected_sha256": expected,
            "hash_pass": bool(actual == expected),
        }

    sem_input = Path(PROJECT_ROOT / CONFIG["reference_experiments"]["r69"]) / "inputs" / "sem_paired_50x_exposure_stack"
    sem_names = image_names(sem_input) if sem_input.is_dir() else []
    if len(sem_names) != 12:
        failures.append(f"SEM optical exposure population expected 12, found {len(sem_names)}")

    r109_root = Path(PROJECT_ROOT / CONFIG["reference_experiments"]["r109"])
    checkpoint_dir = r109_root / "runs" / "r109_formal_scratch_continuous_b8_20260826" / "weights"
    trajectory = sorted(checkpoint_dir.glob("epoch_*.pth"))
    expected_trajectory = [f"epoch_{epoch:03d}.pth" for epoch in range(4, 49, 4)]
    if [item.name for item in trajectory] != expected_trajectory:
        failures.append("R109 checkpoint trajectory is incomplete")

    record = {
        "status": "pass" if not failures else "fail",
        "generated_local": datetime.now().astimezone().isoformat(),
        "experiment": CONFIG["experiment"],
        "models": models,
        "gmf_sources": gmf_sources,
        "frozen_contract": frozen_contract,
        "sem_optical_stack": {"path": str(sem_input), "images": len(sem_names), "names": sem_names},
        "r109_trajectory": {
            "path": str(checkpoint_dir),
            "checkpoints": [str(item) for item in trajectory],
            "epochs": [int(item.stem.split("_")[-1]) for item in trajectory],
        },
        "failures": failures,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": record["status"], "failures": failures, "output": str(OUTPUT)}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
