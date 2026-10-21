"""Verify that every R63 condition changes only its predeclared settings."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_ROOT = EXPERIMENT_ROOT / "results" / "config_snapshots"
LAUNCHER = EXPERIMENT_ROOT / "scripts" / "launch_r63.py"
SEEDS = (1261200, 1261217)
IGNORED_CONFIG_KEYS = {"MODEL_NAME"}
INVARIANT_KEYS = {
    "FIXED_SPLIT_DIR",
    "PSF_FITTED_PATH",
    "PHYS_FORWARD_ENABLE",
    "W_PHYS_MAX",
    "WEAK_PSF_BETA_SCALE_MAX",
}


def load_launcher():
    spec = importlib.util.spec_from_file_location("launch_r63_for_audit", LAUNCHER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {LAUNCHER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalized(value):
    if isinstance(value, tuple):
        return list(value)
    return value


def main() -> None:
    launcher = load_launcher()
    records = []
    failures = []
    for seed in SEEDS:
        full_path = SNAPSHOT_ROOT / f"full_control_seed{seed}.json"
        if not full_path.is_file():
            failures.append(f"missing {full_path}")
            continue
        full_payload = json.loads(full_path.read_text(encoding="utf-8"))
        full = full_payload["config"]
        for variant, declared_overrides in launcher.VARIANTS.items():
            path = SNAPSHOT_ROOT / f"{variant}_seed{seed}.json"
            if not path.is_file():
                failures.append(f"missing {path}")
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            config = payload["config"]
            actual_diff = {
                key: {"full": full.get(key), "candidate": config.get(key)}
                for key in sorted(set(full) | set(config))
                if key not in IGNORED_CONFIG_KEYS and full.get(key) != config.get(key)
            }
            expected_diff = {}
            for key, value in declared_overrides.items():
                if key == "R63_STANDARD_UPSAMPLE":
                    continue
                expected_value = normalized(value)
                if full.get(key) != expected_value:
                    expected_diff[key] = {"full": full.get(key), "candidate": expected_value}
            if actual_diff != expected_diff:
                failures.append(
                    f"{variant}/seed{seed}: actual diff {actual_diff} != expected {expected_diff}"
                )
            if bool(payload.get("standard_upsample")) != (variant == "standard_upsample_matched"):
                failures.append(f"{variant}/seed{seed}: standard-upsample runtime flag mismatch")
            invariant_mismatches = {
                key: {"full": full.get(key), "candidate": config.get(key)}
                for key in sorted(INVARIANT_KEYS)
                if full.get(key) != config.get(key)
            }
            if invariant_mismatches:
                failures.append(f"{variant}/seed{seed}: invariant mismatch {invariant_mismatches}")
            records.append(
                {
                    "variant": variant,
                    "seed": seed,
                    "actual_changed_keys": sorted(actual_diff),
                    "expected_changed_keys": sorted(expected_diff),
                    "passed": actual_diff == expected_diff and not invariant_mismatches,
                }
            )

    result = {
        "passed": not failures,
        "record_count": len(records),
        "failures": failures,
        "records": records,
    }
    output = EXPERIMENT_ROOT / "results" / "config_contrast_audit.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
