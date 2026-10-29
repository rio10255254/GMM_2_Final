"""Materialize the verified R114-balanced 5,000/512 package as hard links.

The source arrays are never rewritten.  This script also creates deterministic
R109-original and R114-balanced short-probe populations so the data change can
be measured before formal scratch training.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random
import shutil
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
DATA = CONFIG["data"]
PACKAGE = ROOT / DATA["package_root"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def hardlink_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.stat().st_size != source.stat().st_size:
            raise RuntimeError(f"existing link size mismatch: {destination}")
        return "existing"
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def normalize_r114_record(row: dict, scene_index: int) -> dict:
    artifact_root = Path(row["artifact_root"])
    local = {}
    for kind in ("target", "mask", "sdf"):
        source = artifact_root / row[kind]
        if not source.is_file():
            raise FileNotFoundError(source)
        suffix = ".npy"
        folder = {"target": "targets", "mask": "masks", "sdf": "sdf"}[kind]
        relative = Path(folder) / f"{scene_index:06d}{suffix}"
        mode = hardlink_or_copy(source, PACKAGE / relative)
        local[kind] = relative.as_posix()
        local[f"{kind}_source_sha256"] = sha256(source)
        local[f"{kind}_storage"] = mode
    return {
        "record_id": row["record_id"],
        "scene_id": row.get("scene_id", row["record_id"]),
        "scene_index": scene_index,
        "logical_index": int(row.get("logical_index", scene_index)),
        "split": row["split"],
        "role": row["role"],
        "family": row["family"],
        "target": local["target"],
        "mask": local["mask"],
        "sdf": local["sdf"],
        "target_width_px": float(row["target_width_px"]),
        "midpoint": float(row["midpoint"]),
        "polarity": float(row["polarity"]),
        "seed": int(row.get("seed", scene_index)),
        "source_storage": row.get("storage", "unknown"),
        "target_source_sha256": local["target_source_sha256"],
        "mask_source_sha256": local["mask_source_sha256"],
        "sdf_source_sha256": local["sdf_source_sha256"],
        "link_modes": {
            "target": local["target_storage"],
            "mask": local["mask_storage"],
            "sdf": local["sdf_storage"],
        },
    }


def stratified_ids(records: list[dict], count: int, seed: int, include_all_supplemental: bool) -> list[str]:
    supplemental = set(DATA["supplemental_families"])
    chosen: list[dict] = []
    remaining = list(records)
    if include_all_supplemental:
        chosen = [row for row in remaining if row["family"] in supplemental]
        remaining = [row for row in remaining if row["family"] not in supplemental]
    if len(chosen) > count:
        raise RuntimeError("supplemental population exceeds requested probe size")
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in remaining:
        groups.setdefault((row["role"], row["family"]), []).append(row)
    rng = random.Random(seed)
    for rows in groups.values():
        rng.shuffle(rows)
    keys = sorted(groups)
    cursor = {key: 0 for key in keys}
    while len(chosen) < count:
        progressed = False
        for key in keys:
            index = cursor[key]
            rows = groups[key]
            if index < len(rows) and len(chosen) < count:
                chosen.append(rows[index])
                cursor[key] += 1
                progressed = True
        if not progressed:
            break
    if len(chosen) != count:
        raise RuntimeError(f"could only choose {len(chosen)} of {count} records")
    rng.shuffle(chosen)
    return [
        str(
            row.get(
                "record_id",
                f"r109_{row.get('split', 'train')}_{int(row['scene_index']):06d}",
            )
        )
        for row in chosen
    ]


def main() -> None:
    r114_manifest_path = Path(PROJECT_ROOT / DATA["r114_manifest"])
    r109_manifest_path = Path(PROJECT_ROOT / DATA["r109_manifest"])
    if sha256(Path(PROJECT_ROOT / DATA["r109_manifest"]).resolve()) != DATA["r114_source_manifest_sha256"]:
        raise RuntimeError("R109/R107 source manifest hash drifted")
    r114 = json.loads(r114_manifest_path.read_text(encoding="utf-8"))
    r109 = json.loads(r109_manifest_path.read_text(encoding="utf-8"))
    source_records = sorted(
        r114["records"],
        key=lambda row: (0 if row["split"] == "train" else 1, int(row.get("logical_index", 0))),
    )
    materialized = [normalize_r114_record(row, index) for index, row in enumerate(source_records)]
    counts = {
        split: sum(row["split"] == split for row in materialized)
        for split in ("train", "validation")
    }
    if counts != {"train": 5000, "validation": 512}:
        raise RuntimeError(f"unexpected split counts: {counts}")
    manifest = {
        "schema_version": 1,
        "status": "complete",
        "source": "R114 balanced replacement manifest",
        "source_manifest": str(r114_manifest_path.resolve()),
        "source_manifest_sha256": sha256(r114_manifest_path),
        "counts": counts,
        "records": materialized,
    }
    write_json(PACKAGE / "manifest.json", manifest)

    train_b = [row for row in materialized if row["split"] == "train"]
    validation_b = [row for row in materialized if row["split"] == "validation"]
    original_records = [row for row in r109["records"] if row["split"] == "train"]
    probe_count = int(DATA["ablation_probe_scenes"])
    a_ids = stratified_ids(original_records, probe_count, CONFIG["seed"] + 1, False)
    b_ids = stratified_ids(train_b, probe_count, CONFIG["seed"] + 2, True)
    common_validation = [
        row["record_id"] for row in validation_b if row["family"] not in set(DATA["supplemental_families"])
    ]
    supplemental_validation = [
        row["record_id"] for row in validation_b if row["family"] in set(DATA["supplemental_families"])
    ]
    write_json(ROOT / "data" / "ablation_a_r109_original.json", {
        "arm": "A_R109_original",
        "source_manifest": str(r109_manifest_path.resolve()),
        "record_ids": a_ids,
    })
    write_json(ROOT / "data" / "ablation_b_r114_balanced.json", {
        "arm": "B_R114_balanced",
        "source_manifest": str((PACKAGE / "manifest.json").resolve()),
        "record_ids": b_ids,
    })
    write_json(ROOT / "data" / "validation_populations.json", {
        "common_record_ids": common_validation,
        "supplemental_record_ids": supplemental_validation,
        "common_count": len(common_validation),
        "supplemental_count": len(supplemental_validation),
    })
    schedule_source = Path(PROJECT_ROOT / DATA["r114_formal_batch_schedule_bs12"])
    schedule_rows = [
        json.loads(line)
        for line in schedule_source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    train_ids = {row["record_id"] for row in train_b}
    scheduled_ids = [record_id for row in schedule_rows for record_id in row["record_ids"]]
    if len(scheduled_ids) != 5000 or set(scheduled_ids) != train_ids:
        raise RuntimeError("formal B12 schedule does not exactly cover R115 train records")
    (ROOT / "data" / "formal_train_bs12.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in schedule_rows) + "\n",
        encoding="utf-8",
    )
    write_json(ROOT / "data" / "preparation_result.json", {
        "status": "complete",
        "counts": counts,
        "probe_a_count": len(a_ids),
        "probe_b_count": len(b_ids),
        "probe_b_supplemental_count": sum(
            row["record_id"] in set(b_ids) and row["family"] in set(DATA["supplemental_families"])
            for row in train_b
        ),
        "common_validation_count": len(common_validation),
        "supplemental_validation_count": len(supplemental_validation),
        "r114_manifest_sha256": sha256(r114_manifest_path),
        "r109_manifest_sha256": sha256(r109_manifest_path),
        "formal_batch_schedule_batches": len(schedule_rows),
        "formal_batch_schedule_scenes": len(scheduled_ids),
    })
    print(ROOT / "data" / "preparation_result.json")


if __name__ == "__main__":
    main()
