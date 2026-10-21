"""Lock the deterministic 1,024-pair procedural adaptation subset before training."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))
COUNTS = {
    "basic_geometry": 160,
    "fine_noncircular": 160,
    "dense_periodic_layout": 160,
    "multiscale_field": 160,
    "identity_guard": 160,
    "boundary_fade_mixed": 224,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    package = Path(CONFIG["data"]["formal_package"])
    manifest_path = package / "manifest.json"
    if sha256(manifest_path) != CONFIG["data"]["formal_manifest_sha256"]:
        raise RuntimeError("Formal procedural manifest changed.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    training = [row for row in manifest["pairs"] if row["split"] == "train"]
    selected = []
    for role, count in COUNTS.items():
        rows = sorted((row for row in training if row["training_role"] == role), key=lambda row: row["pair_id"])
        if len(rows) < count:
            raise RuntimeError(f"Not enough {role} rows: {len(rows)}")
        selected.extend(rows[:count])
    selected = sorted(selected, key=lambda row: row["pair_id"])
    if len(selected) != 1024 or len({row["pair_id"] for row in selected}) != 1024:
        raise RuntimeError("Training subset is not exactly 1,024 unique pairs.")
    lock = {
        "experiment_id": CONFIG["experiment_id"],
        "locked_before_first_training_update": True,
        "source_manifest": str(manifest_path),
        "source_manifest_sha256": CONFIG["data"]["formal_manifest_sha256"],
        "selection_rule": "lexical pair_id prefix within each predeclared role quota",
        "role_counts": COUNTS,
        "pair_count": len(selected),
        "pair_ids": [row["pair_id"] for row in selected],
        "external_or_reserved_data_used": False,
    }
    path = ROOT / "reports" / "R85_TRAINING_SUBSET_LOCK.json"
    path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    print(json.dumps({"path": str(path), "pair_count": len(selected), "role_counts": COUNTS}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
