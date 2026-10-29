"""Lock a deterministic, family-balanced synthetic subset for both arms."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[4]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_key(record: dict) -> str:
    payload = f"{CONFIG['seed']}|{record['split']}|{record['scene_id']}|{record['seed']}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def balanced_select(records: list[dict], count: int) -> list[dict]:
    by_family = defaultdict(list)
    for record in records:
        by_family[record["family"]].append(record)
    families = sorted(by_family)
    base, remainder = divmod(count, len(families))
    selected = []
    for index, family in enumerate(families):
        quota = base + (1 if index < remainder else 0)
        candidates = sorted(by_family[family], key=stable_key)
        if len(candidates) < quota:
            raise RuntimeError(f"Family {family} has {len(candidates)} records, needs {quota}")
        selected.extend(candidates[:quota])
    return sorted(selected, key=lambda row: int(row["scene_index"]))


def main() -> None:
    package = Path(PROJECT_ROOT / CONFIG["data"]["package_root"])
    manifest_path = package / "manifest.json"
    actual_hash = sha256_file(manifest_path)
    expected_hash = CONFIG["data"]["source_manifest_sha256"]
    if actual_hash.lower() != expected_hash.lower():
        raise RuntimeError(f"Source manifest changed: {actual_hash}")
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    if int(source["supersample_factor"]) != int(CONFIG["data"]["supersample_factor"]):
        raise RuntimeError("Supersample factor mismatch")
    output_records = []
    for split, count_key in (("train", "train_count"), ("validation", "validation_count")):
        candidates = [row for row in source["records"] if row["split"] == split]
        selected = balanced_select(candidates, int(CONFIG["data"][count_key]))
        for record in selected:
            copied = dict(record)
            copied["source_file_hashes"] = {
                field: sha256_file(package / record[field]) for field in ("target", "mask", "sdf")
            }
            output_records.append(copied)
    canonical = json.dumps(output_records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload = {
        "status": "locked",
        "source_experiment": source["experiment_id"],
        "source_manifest_sha256": actual_hash,
        "supersample_factor": source["supersample_factor"],
        "canvas_size": source["canvas_size"],
        "selection_seed": CONFIG["seed"],
        "selection_rule": "equal quota per synthetic family, stable SHA256 ordering, no replacement",
        "records_sha256": hashlib.sha256(canonical).hexdigest(),
        "records": output_records,
    }
    destination = ROOT / CONFIG["data"]["selection_file"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    rows = []
    for split in ("train", "validation"):
        chosen = [row for row in output_records if row["split"] == split]
        family_counts = Counter(row["family"] for row in chosen)
        role_counts = Counter(row["role"] for row in chosen)
        for family in sorted(family_counts):
            rows.append({"split": split, "kind": "family", "name": family, "count": family_counts[family]})
        for role in sorted(role_counts):
            rows.append({"split": split, "kind": "role", "name": role, "count": role_counts[role]})
    summary = destination.with_name("selection_summary.csv")
    with summary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["split", "kind", "name", "count"])
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({
        "status": "locked", "records": len(output_records), "records_sha256": payload["records_sha256"],
        "selection": str(destination), "summary": str(summary),
    }, indent=2))


if __name__ == "__main__":
    main()
