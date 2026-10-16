"""Independently validate generated R73/R74 intervention suites."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results" / "physical_validation" / "intervention_reconstructions"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    state = json.loads((SOURCE / "state.json").read_text(encoding="utf-8"))
    table = pd.read_csv(SOURCE / "output_manifest.csv", encoding="utf-8-sig")
    failures: list[str] = []
    if len(table) != 1000:
        failures.append(f"expected 1000 manifest rows, found {len(table)}")
    if table.duplicated(["suite", "family", "filename", "variant"]).any():
        failures.append("duplicate output key")
    counts = table.groupby(["suite", "variant"]).size()
    if not (counts == 100).all() or len(counts) != 10:
        failures.append(f"unexpected suite/variant counts: {counts.to_dict()}")
    missing = 0
    hash_mismatch = 0
    for row in table.itertuples(index=False):
        path = Path(row.output)
        if not path.is_file():
            missing += 1
        elif sha256(path) != row.output_sha256:
            hash_mismatch += 1
    if missing:
        failures.append(f"missing outputs: {missing}")
    if hash_mismatch:
        failures.append(f"hash mismatches: {hash_mismatch}")
    if int(state["canonical_full_max_gray_difference"]) != 0:
        failures.append("full intervention does not reproduce canonical R109")
    parity_max = max(item["max_gray_difference"] for suite in state["tile_grid_parity"].values() for item in suite.values())
    parity_mean_max = max(item["mean_gray_difference"] for suite in state["tile_grid_parity"].values() for item in suite.values())
    if parity_max > 1 or parity_mean_max > 0.001:
        failures.append(f"tile parity outside one-gray tolerance: max={parity_max}, mean={parity_mean_max}")
    result = {
        "status": "pass" if not failures else "fail",
        "validated_local": datetime.now().astimezone().isoformat(),
        "manifest_rows": len(table),
        "suite_variant_groups": len(counts),
        "missing_outputs": missing,
        "hash_mismatches": hash_mismatch,
        "canonical_full_max_gray_difference": int(state["canonical_full_max_gray_difference"]),
        "alternate_grid_max_gray_difference": int(parity_max),
        "alternate_grid_max_mean_gray_difference": float(parity_mean_max),
        "failures": failures,
    }
    (SOURCE / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
