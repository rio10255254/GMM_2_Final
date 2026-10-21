"""Read-only loader for the R119 development sequence bank."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class SequenceBank:
    def __init__(self, root: Path | str = ROOT / "data/development_sequences"):
        self.root = Path(root)
        self.manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8-sig"))
        if self.manifest.get("status") != "complete" or self.manifest.get("count") != self.manifest.get("expected_count"):
            raise ValueError("sequence bank incomplete")
        self.records = list(self.manifest["records"])

    def __len__(self): return len(self.records)

    def load(self, record: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        source_path = ROOT / record["source"]
        if sha(source_path) != record["source_sha256"]:
            raise ValueError(f"source hash mismatch: {source_path}")
        source = np.load(source_path)["source"].astype(np.float32) / 255.0
        reference_path = ROOT / record["reference"]
        if sha(reference_path) != record["reference_sha256"]:
            raise ValueError(f"reference hash mismatch: {reference_path}")
        reference = np.load(reference_path).astype(np.float32) / 255.0
        mask = np.load(ROOT / record["mask"]).astype(np.float32) / 255.0
        return source, reference, mask

    def group(self):
        groups = {}
        for record in self.records:
            groups.setdefault((record["sequence_id"], record["protocol"], record["condition_id"]), []).append(record)
        return groups
