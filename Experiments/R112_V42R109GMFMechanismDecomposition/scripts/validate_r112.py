"""Independent completeness and claim checks for R112."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def main() -> int:
    failures: list[str] = []
    checks: dict[str, object] = {}
    for arm, entry in CONFIG["models"].items():
        score_rows = len(Path(PROJECT_ROOT / entry["score"]).read_text(encoding="utf-8-sig").splitlines())
        image_count = len(list(Path(PROJECT_ROOT / entry["image_dir"]).glob("frame_*.bmp")))
        checks[f"source_{arm}"] = {"score_rows": score_rows, "images": image_count}
        if score_rows != 100 or image_count != 101:
            failures.append(f"{arm} source population mismatch")

    image_features = pd.read_csv(RESULTS / "image_mechanisms" / "frame_features.csv", encoding="utf-8-sig")
    image_summary = json.loads((RESULTS / "image_mechanisms" / "analysis_summary.json").read_text(encoding="utf-8"))
    checks["image_mechanisms"] = {
        "rows": len(image_features),
        "arms": sorted(image_features["arm"].unique().tolist()),
        "surrogate_ranking_valid": image_summary["surrogate_ranking_valid"],
        "counterfactual_count": len(image_summary["counterfactuals"]),
    }
    if len(image_features) != 300 or image_summary["surrogate_ranking_valid"] or len(image_summary["counterfactuals"]) != 0:
        failures.append("Invalid surrogate was not contained")

    component = pd.read_csv(RESULTS / "component_probes" / "component_probe_per_frame.csv", encoding="utf-8-sig")
    internal = pd.read_csv(RESULTS / "component_probes" / "internal_state_per_frame.csv", encoding="utf-8-sig")
    checks["component_probes"] = {
        "rows": len(component),
        "variants": int(component["variant"].nunique()),
        "frames": int(component["frame_index"].nunique()),
        "internal_rows": len(internal),
    }
    if len(component) != 45 or component["variant"].nunique() != 9 or component["frame_index"].nunique() != 5 or len(internal) != 10:
        failures.append("Component probe population mismatch")

    residual = pd.read_csv(RESULTS / "residual_bands" / "residual_band_per_frame.csv", encoding="utf-8-sig")
    dynamics_frame = pd.read_csv(RESULTS / "internal_dynamics" / "internal_state_per_frame.csv", encoding="utf-8-sig")
    dynamics_step = pd.read_csv(RESULTS / "internal_dynamics" / "internal_state_per_step.csv", encoding="utf-8-sig")
    counterfactual = pd.read_csv(RESULTS / "counterfactual_stability" / "counterfactual_stability_summary.csv", encoding="utf-8-sig")
    checks["extended_diagnostics"] = {
        "residual_rows": len(residual),
        "dynamics_frames": len(dynamics_frame),
        "dynamics_steps": len(dynamics_step),
        "counterfactual_variants": len(counterfactual),
    }
    if len(residual) != 200 or len(dynamics_frame) != 100 or len(dynamics_step) != 99 or len(counterfactual) != 7:
        failures.append("Extended diagnostic population mismatch")

    findings = json.loads((RESULTS / "mechanism_findings.json").read_text(encoding="utf-8"))
    v42_low = float(findings["verified"]["v42_output_mechanism"]["low_frequency_residual_fraction_median"])
    r109_low = float(findings["verified"]["r109_output_mechanism"]["low_frequency_residual_fraction_median"])
    surrogate_valid = findings["verified"]["surrogate_failure"]["fixed_template_ranking_valid"]
    design_path = ROOT / "MODEL_IMPROVEMENT_DESIGN.md"
    checks["conclusion"] = {
        "v42_low_frequency_fraction": v42_low,
        "r109_low_frequency_fraction": r109_low,
        "r109_low_frequency_higher": r109_low > v42_low,
        "surrogate_rejected": not surrogate_valid,
        "design_exists": design_path.is_file(),
        "opportunity": findings["model_side_opportunity"]["assessment"],
    }
    if not (r109_low > 10.0 * v42_low and not surrogate_valid and design_path.is_file()):
        failures.append("Mechanism conclusion is not supported by saved evidence")

    result = {
        "status": "pass" if not failures else "fail",
        "validated_local": datetime.now().astimezone().isoformat(),
        "failures": failures,
        "checks": checks,
    }
    (RESULTS / "final_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
