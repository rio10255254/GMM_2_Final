"""Independent contract validation for the R113 structural probe artifacts."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "structure"
CONFIG = json.loads((ROOT / "config" / "experiment.json").read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    architecture = json.loads((OUT / "architecture_inventory.json").read_text(encoding="utf-8"))
    summary = json.loads((OUT / "analysis_summary.json").read_text(encoding="utf-8"))
    samples = json.loads((OUT / "sample_manifest.json").read_text(encoding="utf-8"))
    metrics = pd.read_csv(OUT / "per_case_variant_metrics.csv")
    internals = pd.read_csv(OUT / "internal_module_statistics.csv")
    reproductions = pd.read_csv(OUT / "reproduction_checks.csv")
    findings = json.loads((OUT / "structure_findings.json").read_text(encoding="utf-8"))
    sem_validation_path = ROOT / "results" / "structure_probe" / "sem_interventions" / "validation.json"
    sem_validation = json.loads(sem_validation_path.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}

    checks["eight_matched_cases"] = len(samples) == 8 and metrics["case"].nunique() == 8
    checks["three_models_every_case"] = bool((metrics.groupby("case")["model"].nunique() == 3).all())
    checks["all_output_files_exist"] = all(Path(path).is_file() for path in metrics["output_path"])
    checks["all_output_hashes_match"] = all(sha256_file(Path(row.output_path)) == row.output_sha256 for row in metrics.itertuples())
    checks["checkpoint_hashes_match"] = all(
        sha256_file(Path(entry["checkpoint"])) == CONFIG["models"][name]["sha256"]
        for name, entry in architecture["models"].items()
    )
    checks["r61_v42_source_files_identical"] = bool(architecture["source_model_identity"]["files_byte_identical"])
    inheritance = architecture["r61_v42_weight_inheritance"]
    checks["inheritance_accounted"] = inheritance["shared_same_shape_tensors"] >= 135 and inheritance["exact_shared_tensors"] >= 100
    checks["r109_renderer_exact_u8"] = bool(
        (reproductions.loc[reproductions["renderer_reproduction_max_gray"].notna(), "renderer_reproduction_max_gray"] == 0).all()
    )
    checks["canonical_center_reproductions_present"] = reproductions["center_core_mae_gray"].notna().sum() >= 5
    tile_safe = reproductions[
        reproductions["comparison_scope"].eq("crop_inference_vs_full_or_tiled_context")
        & reproductions["model"].isin(["V42_E120", "R109_E48"])
    ]
    r61_crop = reproductions[
        reproductions["comparison_scope"].eq("crop_inference_vs_full_or_tiled_context")
        & reproductions["model"].eq("R61_v16")
    ]
    r61_full = reproductions[
        reproductions["comparison_scope"].eq("full_frame_exact_runtime")
        & reproductions["model"].eq("R61_v16")
    ]
    checks["tile_safe_models_canonical_center_mae_below_one_gray"] = bool(
        len(tile_safe) >= 2 and (tile_safe["center_core_mae_gray"] <= 1.0).all()
    )
    checks["r61_full_frame_runtime_reproduces_canonical"] = bool(
        len(r61_full) == 1 and (r61_full["center_core_mae_gray"] <= 1.0).all()
    )
    checks["r61_crop_context_sensitivity_detected"] = bool(
        len(r61_crop) >= 3 and (r61_crop["center_core_mae_gray"] > 1.0).all()
    )
    numeric = metrics.select_dtypes(include="number")
    required_numeric = [column for column in numeric.columns if not column.startswith("label_")]
    checks["finite_required_metrics"] = all(math.isfinite(float(value)) for column in required_numeric for value in numeric[column].dropna())
    checks["internal_rows_present_all_models"] = {"V42_E120", "R61_v16_checkpoint_native", "R109_E48"}.issubset(set(internals["model"]))
    checks["full_variants_present"] = all(
        ((metrics["model"] == model) & (metrics["variant"] == variant)).sum() == 8
        for model, variant in [("V42_E120", "full"), ("R61_v16", "locked_psf_off_full"), ("R109_E48", "full")]
    )
    checks["summary_complete"] = summary.get("status") == "complete" and summary.get("variant_output_count") == len(metrics)
    checks["structure_findings_complete"] = findings.get("status") == "complete"
    checks["sem_interventions_complete"] = (
        sem_validation.get("status") == "pass"
        and sem_validation.get("output_count") == 60
        and sem_validation.get("variant_names_matlab_field_safe") is True
        and sem_validation.get("full_reproduction_max_abs") == 0.0
    )
    checks = {name: bool(value) for name, value in checks.items()}
    status = "pass" if all(checks.values()) else "fail"
    result = {
        "status": status,
        "generated_local": datetime.now().astimezone().isoformat(),
        "checks": checks,
        "counts": {"samples": len(samples), "variant_outputs": len(metrics), "internal_rows": len(internals), "reproduction_rows": len(reproductions), "sem_intervention_outputs": sem_validation.get("output_count")},
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }
    (OUT / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
