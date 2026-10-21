"""Summarize R93 dataset diversity without reading or exporting source pixels."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def summarize(package: Path) -> dict[str, Any]:
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((package / "audit.json").read_text(encoding="utf-8"))
    roles: Counter[str] = Counter()
    splits: Counter[str] = Counter()
    degradations: Counter[str] = Counter()
    foreground_textures: Counter[str] = Counter()
    background_textures: Counter[str] = Counter()
    exposures: list[float] = []
    gammas: list[float] = []
    path_positions: list[float] = []
    bundle_spans: list[float] = []
    transition_fractions: list[float] = []
    requested_contrasts_gray: list[float] = []
    measured_contrasts_gray: list[float] = []
    target_mix_repair_count = 0
    bundle_noise_seed_failures = 0
    bundle_parameter_seed_failures = 0

    for record in manifest["records"]:
        roles[str(record["role"])] += 1
        splits[str(record["split"])] += 1
        texture = record["texture"]
        transition_fractions.append(float(texture["physical_boundary_intensity_fraction"]))
        foreground_textures[str(texture["foreground_texture_family"])] += 1
        background_textures[str(texture["background_texture_family"])] += 1
        scene_exposures = []
        for observation in record["observations"]:
            degradations[str(observation["degradation_family"])] += 1
            degradation = observation["degradation"]
            exposures.append(float(degradation["exposure"]))
            gammas.append(float(degradation["gamma"]))
            target_mix_repair_count += int(float(degradation.get("recoverability_repair_fraction", 0.0)) != 0.0)
            if degradation.get("requested_source_contrast_gray") is not None:
                requested_contrasts_gray.append(float(degradation["requested_source_contrast_gray"]))
                measured_contrasts_gray.append(255.0 * float(degradation["p95_p5_contrast"]))
            if degradation.get("exposure_path_position") is not None:
                path_positions.append(float(degradation["exposure_path_position"]))
                scene_exposures.append(float(degradation["exposure"]))
        if record["role"] == "exposure_coherent_bundle":
            bundle_spans.append(max(scene_exposures) - min(scene_exposures))
            if len({int(row["independent_noise_seed"]) for row in record["observations"]}) != 4:
                bundle_noise_seed_failures += 1
            if len({int(row["degradation_parameter_seed"]) for row in record["observations"]}) != 1:
                bundle_parameter_seed_failures += 1

    percentiles = lambda values: {
        name: float(np.percentile(values, percentile))
        for name, percentile in (("p01", 1), ("p10", 10), ("p50", 50), ("p90", 90), ("p99", 99))
    }
    return {
        "experiment_id": manifest["experiment_id"],
        "profile": manifest["profile"],
        "audit_passed": bool(audit["passed"]),
        "full_array_hash_audit": bool(audit["full_array_hash_audit"]),
        "scene_count": int(manifest["scene_count"]),
        "observation_count": int(manifest["total_observations"]),
        "role_counts": dict(sorted(roles.items())),
        "split_counts": dict(sorted(splits.items())),
        "degradation_counts": dict(sorted(degradations.items())),
        "foreground_texture_counts": dict(sorted(foreground_textures.items())),
        "background_texture_counts": dict(sorted(background_textures.items())),
        "exposure_percentiles": percentiles(exposures),
        "gamma_percentiles": percentiles(gammas),
        "exposure_path_position_counts": dict(sorted(Counter(round(value, 3) for value in path_positions).items())),
        "bundle_exposure_span_percentiles": percentiles(bundle_spans),
        "physical_transition_fraction_percentiles": percentiles(transition_fractions),
        "requested_exposure_contrast_gray_percentiles": percentiles(requested_contrasts_gray) if requested_contrasts_gray else {},
        "measured_exposure_contrast_gray_percentiles": percentiles(measured_contrasts_gray) if measured_contrasts_gray else {},
        "target_mix_repair_count": target_mix_repair_count,
        "bundle_independent_noise_seed_failures": bundle_noise_seed_failures,
        "bundle_shared_parameter_seed_failures": bundle_parameter_seed_failures,
        "source_isolation": manifest["source_isolation"],
        "content_sha256": manifest["content_sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("smoke", "formal", "holdout"), default="formal")
    args = parser.parse_args()
    package = ROOT / "data" / {"smoke": "r93_smoke", "formal": "r93_formal", "holdout": "r93_locked_holdout"}[args.profile]
    report = summarize(package)
    output = ROOT / "reports" / f"{args.profile}_dataset_composition.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"passed": report["audit_passed"], "report": str(output), "scenes": report["scene_count"], "observations": report["observation_count"]}, ensure_ascii=False))
    return 0 if report["audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
