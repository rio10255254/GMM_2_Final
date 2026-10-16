"""Quantify the observed-image change while checking unchanged targets."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = Path(r"D:\GMM_2_Final\Experiments\R141_PSF25_AdaptiveTop4_Standalone")
sys.path.insert(0, str(ROOT))
from utils import load, now, save, sha


def main() -> None:
    manifest = load(ROOT / "data/manifest.json")
    rows = defaultdict(list)
    target_mismatches = []
    unchanged_source = []
    for entry in manifest["entries"]:
        with np.load(BASE / "data" / entry["arrays"], allow_pickle=False) as a, \
             np.load(ROOT / "data" / entry["arrays"], allow_pickle=False) as b:
            if not np.array_equal(a["target"], b["target"]):
                target_mismatches.append(entry["parent_id"])
            lo, hi = 128, 256
            diff = (b["source"][:, lo:hi, lo:hi].astype(float) -
                    a["source"][:, lo:hi, lo:hi].astype(float))
            rms = float(np.sqrt(np.mean(diff**2)))
            rows[entry["category"]].append(rms)
            if rms == 0:
                unchanged_source.append(entry["parent_id"])
    assert not target_mismatches
    identity = sum(len(rows[k]) for k in ("clean_identity", "noisy_identity"))
    assert identity == 76
    report = dict(parents=len(manifest["entries"]), clear_target_mismatches=0,
                  exact_unchanged_sources=len(unchanged_source),
                  category_rms_gray={k:dict(n=len(v), median=float(np.median(v)),
                                            maximum=float(np.max(v)), minimum=float(np.min(v)))
                                     for k, v in sorted(rows.items())},
                  old_data_manifest_sha256=sha(BASE / "data/manifest.json"),
                  new_data_manifest_sha256=sha(ROOT / "data/manifest.json"),
                  completed_utc=now())
    save(ROOT / "results/data_effect_audit.json", report)
    print("DATA_EFFECT_AUDIT_PASS", report["parents"], report["clear_target_mismatches"])
    for k, v in report["category_rms_gray"].items():
        print(k, v["n"], round(v["median"], 4))


if __name__ == "__main__":
    main()
