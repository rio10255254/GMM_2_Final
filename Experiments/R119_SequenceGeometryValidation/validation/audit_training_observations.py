"""Verify deterministic training-observation sidecars without materializing images."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "data/package"
SELECTION = ROOT / "config/selected_scene_ids.json"


def sha(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""): h.update(b)
    return h.hexdigest()


def run():
    base = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8-sig"))
    by_id = {int(r["scene_index"]): r for r in base["records"] if r["split"] == "train"}
    selection = json.loads(SELECTION.read_text(encoding="utf-8-sig"))
    errors, rows = [], []
    for scope, expected, key in (("short", 96, "short_sequence_enrichment_ids"), ("full", 960, "full_sequence_enrichment_ids")):
        path = ROOT / f"data/training_observations/{scope}_manifest.json"
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        ids = [int(r["scene_id"]) for r in data["records"]]
        if data.get("status") != "complete" or data.get("scene_count") != expected or ids != [int(x) for x in selection[key]]:
            errors.append(f"{scope} manifest does not match frozen selection")
        if len(set(ids)) != expected or any(i not in by_id for i in ids): errors.append(f"{scope} IDs invalid")
        strata = {}
        for record in data["records"]:
            strata[(record["family"], int(record["polarity"]))] = strata.get((record["family"], int(record["polarity"])), 0) + 1
            for field in ("target_a", "target_b", "source_a", "source_b", "sdf_a", "sdf_b", "mask_a", "mask_b"):
                if not (PACKAGE / record[field]).is_file(): errors.append(f"{scope} missing base path {field}")
            if record.get("fixed_optics_motion") is not True or record.get("same_latent_pair") is not True or record.get("label_supersample_factor") != 8:
                errors.append(f"{scope} observation contract missing for {record['scene_id']}")
        if len(strata) != 24 or any(v != expected // 24 for v in strata.values()): errors.append(f"{scope} family/polarity imbalance")
        rows.append({"scope": scope, "scene_count": len(ids), "strata": {f"{k[0]}|{k[1]}": v for k, v in strata.items()}, "manifest_sha256": sha(path), "selection_sha256": sha(SELECTION)})
    # Confirm the two enrichment populations overlap only as intentionally nested
    # records, while no development IDs are used as training IDs.
    dev = set(int(x) for x in selection["development_bank_scene_ids"])
    short = set(int(x) for x in selection["short_sequence_enrichment_ids"])
    full = set(int(x) for x in selection["full_sequence_enrichment_ids"])
    if dev & full: errors.append("development and training enrichment overlap")
    if not short <= full: errors.append("short enrichment not nested in full")
    return {"schema_version": 1, "status": "pass" if not errors else "blocked", "created_at_utc": datetime.now(timezone.utc).isoformat(), "errors": errors, "scopes": rows, "real_pixels_in_training": False, "immutable_base_labels": True, "generated_image_sidecars": False, "meaning": "Metadata/generation-contract audit only; trainer behavior remains a later phase."}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, default=ROOT / "results/training_observation_audit.json"); args = parser.parse_args(); result = run()
    if args.output.exists(): raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(result, indent=2), encoding="utf-8"); print(json.dumps(result, indent=2)); return 0 if result["status"] == "pass" else 2


if __name__ == "__main__": raise SystemExit(main())
