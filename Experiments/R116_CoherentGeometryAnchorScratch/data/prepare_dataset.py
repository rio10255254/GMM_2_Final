"""Create a local hard-linked copy of the frozen R109 procedural data package."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "experiment.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    source = Path(config["data"]["source_package"]).resolve()
    destination = (ROOT / config["data"]["package_root"]).resolve()
    source_manifest = source / "manifest.json"
    if not source_manifest.is_file():
        raise FileNotFoundError(source_manifest)
    source_hash = sha256(source_manifest)
    if source_hash != config["data"]["source_manifest_sha256"]:
        raise RuntimeError(
            f"source manifest hash mismatch: expected {config['data']['source_manifest_sha256']}, got {source_hash}"
        )
    destination.mkdir(parents=True, exist_ok=True)
    created = 0
    reused = 0
    logical_bytes = 0
    for source_file in sorted(item for item in source.rglob("*") if item.is_file()):
        relative = source_file.relative_to(source)
        target_file = destination / relative
        target_file.parent.mkdir(parents=True, exist_ok=True)
        logical_bytes += source_file.stat().st_size
        if target_file.exists():
            if not os.path.samefile(source_file, target_file):
                raise FileExistsError(f"non-hardlink destination already exists: {target_file}")
            reused += 1
            continue
        os.link(source_file, target_file)
        if not os.path.samefile(source_file, target_file):
            raise RuntimeError(f"hardlink verification failed: {target_file}")
        created += 1
    destination_manifest = destination / "manifest.json"
    manifest = json.loads(destination_manifest.read_text(encoding="utf-8"))
    result = {
        "status": "complete",
        "source": str(source),
        "destination": str(destination),
        "source_manifest_sha256": source_hash,
        "destination_manifest_sha256": sha256(destination_manifest),
        "created_hardlinks": created,
        "reused_hardlinks": reused,
        "total_files": created + reused,
        "logical_bytes": logical_bytes,
        "train_scenes": manifest["counts"]["train"],
        "validation_scenes": manifest["counts"]["validation"],
        "group_overlap_count": manifest["group_overlap_count"],
        "training_uses_real_pixels": manifest["training_uses_real_pixels"],
        "formal_training_authorized": False,
    }
    if result["destination_manifest_sha256"] != source_hash:
        raise RuntimeError("destination manifest differs from frozen source")
    if result["train_scenes"] != config["data"]["train_scenes"]:
        raise RuntimeError("unexpected train count")
    if result["validation_scenes"] != config["data"]["validation_scenes"]:
        raise RuntimeError("unexpected validation count")
    if result["group_overlap_count"] != config["data"]["group_overlap_expected"]:
        raise RuntimeError("train/validation group overlap")
    if bool(result["training_uses_real_pixels"]) != bool(config["data"]["real_pixels_expected"]):
        raise RuntimeError("real-pixel policy mismatch")
    write_json(ROOT / "data" / "preparation_result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
