from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
RESULTS = ROOT / "results"
REPORT = ROOT / "reports" / "R67_RESULTS.md"
SOURCE_SCRIPTS = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/modern_baseline_three_morphology_20260719/source_scripts')
)
SOURCE_MANIFEST = Path(
    str(PROJECT_ROOT / 'Thesis_MOSR_Evidence/Final_Data_Figures/04_V42_NEURAL_NETWORK_RESULTS/modern_baseline_three_morphology_20260719/source_manifest.json')
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def image_files(directory: Path) -> list[Path]:
    return sorted(p for p in directory.glob("frame_*.bmp") if p.is_file())


def validate_inputs() -> tuple[dict, dict]:
    roster = read_json(CONFIG / "model_roster.json")
    scenes = read_json(CONFIG / "phase_a_scenes.json")
    missing: list[str] = []
    for name, item in roster["models"].items():
        checkpoint = Path(PROJECT_ROOT / item["checkpoint"])
        script = Path(PROJECT_ROOT / item.get("inference_script", roster["default_inference_script"]))
        if not checkpoint.is_file():
            missing.append(f"{name} checkpoint: {checkpoint}")
        if not script.is_file():
            missing.append(f"{name} inference: {script}")
    for name, item in scenes["sequences"].items():
        directory = Path(PROJECT_ROOT / item["raw_dir"])
        count = len(image_files(directory))
        if count != int(item["frame_count"]):
            missing.append(f"{name}: expected {item['frame_count']} frames, found {count}")
    if not SOURCE_MANIFEST.is_file():
        missing.append(f"source manifest: {SOURCE_MANIFEST}")
    if missing:
        raise RuntimeError("Input validation failed:\n" + "\n".join(missing))
    return roster, scenes


def newest_complete_leaf(root: Path, expected: int) -> Path:
    candidates = []
    for first in root.rglob("frame_0000.bmp"):
        parent = first.parent
        if len(image_files(parent)) == expected:
            candidates.append(parent)
    if not candidates:
        raise RuntimeError(f"No complete {expected}-frame output found under {root}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def link_outputs(source: Path, destination: Path, expected: int) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for src in image_files(source):
        dst = destination / src.name
        if dst.exists():
            continue
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
    if len(image_files(destination)) != expected:
        raise RuntimeError(f"Canonical output incomplete: {destination}")


def run_reconstruction(model: str, model_info: dict, roster: dict, sequence: str, scene: dict) -> dict:
    expected = int(scene["frame_count"])
    canonical = RESULTS / "reconstructions" / model / sequence
    if len(image_files(canonical)) == expected:
        return {"model": model, "sequence": sequence, "status": "reused", "frames": expected, "output": str(canonical)}
    run_root = RESULTS / "inference_runs" / model / sequence
    run_root.mkdir(parents=True, exist_ok=True)
    script = Path(PROJECT_ROOT / model_info.get("inference_script", roster["default_inference_script"]))
    command = [
        roster["python"], str(script),
        "--weights", str(PROJECT_ROOT / model_info["checkpoint"]),
        "--input-dir", str(PROJECT_ROOT / scene["raw_dir"]),
        "--recon-root", str(run_root),
        "--output-name", sequence,
        "--device", "cuda:0",
        "--select-mode", "all",
        "--psf-from-ckpt",
    ]
    started = time.time()
    log_path = run_root / "inference.log"
    with log_path.open("w", encoding="utf-8") as log:
        completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, text=True)
    if completed.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(f"Inference failed for {model} {sequence}:\n{tail}")
    leaf = newest_complete_leaf(run_root, expected)
    link_outputs(leaf, canonical, expected)
    return {
        "model": model, "sequence": sequence, "status": "completed", "frames": expected,
        "seconds": round(time.time() - started, 3), "source_output": str(leaf), "output": str(canonical),
        "log": str(log_path),
    }


def reconstruct(roster: dict, scenes: dict) -> list[dict]:
    records: list[dict] = []
    for model, model_info in roster["models"].items():
        for sequence, scene in scenes["sequences"].items():
            print(f"[reconstruct] {model} / {sequence}", flush=True)
            record = run_reconstruction(model, model_info, roster, sequence, scene)
            records.append(record)
            print(f"  {record['status']}: {record['frames']} frames", flush=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "run_manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    return records


def build_evaluation_manifest(roster: dict, scenes: dict) -> Path:
    source = read_json(SOURCE_MANIFEST)
    methods = {"Raw": {"kind": "measurement", "sequence_root": ""}}
    mapping = {sequence: {"Raw": sequence} for sequence in scenes["sequences"]}
    for model in roster["models"]:
        methods[model] = {"kind": "frozen_candidate", "sequence_root": str(RESULTS / "reconstructions" / model)}
        for sequence in mapping:
            mapping[sequence][model] = sequence
    manifest = {
        "version": 1,
        "purpose": "R67 frozen-candidate current-domain generalization comparison",
        "claim_scope": "Phase A only; development-domain evidence, not independent universal validation",
        "methods": methods,
        "sequence_name_map": mapping,
        "pillar_config": str(PROJECT_ROOT / source["pillar_config"]),
        "via_config": str(PROJECT_ROOT / source["via_config"]),
        "sem_workbook": str(PROJECT_ROOT / source["sem_workbook"]),
        "top30_selection": str(PROJECT_ROOT / source["top30_selection"]),
        "line_reference": str(PROJECT_ROOT / source["line_reference"]),
    }
    path = CONFIG / "evaluation_manifest.generated.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves postponed annotations through sys.modules while the
    # module body is executing, so register the dynamic module first.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def evaluate_circular_tolerant(module, manifest_path: Path, output_root: Path) -> None:
    """Run the locked circular protocol while preserving per-feature failures as evidence."""
    manifest = read_json(manifest_path)
    methods = list(manifest["methods"])
    rows: list[dict] = []
    failures: list[dict] = []
    for magnification, sequence_name in module.STATIC_SEQUENCES.items():
        sequence, references = module.circular_references(manifest, magnification)
        raw_dir = Path(sequence["raw_dir"])
        um_per_px = float(sequence["object_um_per_px"])
        pitch_px = float(sequence["pitch_px"])
        for method in methods:
            directory = module.method_sequence_dir(manifest, method, sequence_name, raw_dir)
            image_path = directory / str(sequence["first_frame"])
            if not image_path.is_file():
                raise FileNotFoundError(image_path)
            image = module.read_gray(image_path)
            for morphology, centers in references.items():
                polarity = "dark" if morphology == "pillar" else "bright"
                for center in centers:
                    try:
                        measurements = module.measure_radial_feature_sweep(
                            image,
                            (float(center["x"]), float(center["y"])),
                            pitch_px,
                            polarity,
                            module.CONTRAST_FRACTIONS,
                        )
                    except (RuntimeError, ValueError) as error:
                        failures.append({
                            "magnification": magnification,
                            "morphology": morphology,
                            "method": method,
                            "feature_id": center["feature_id"],
                            "reason": str(error),
                            "image_path": str(image_path),
                        })
                        continue
                    for fraction in module.CONTRAST_FRACTIONS:
                        measurement = measurements[float(fraction)]
                        rows.append({
                            "magnification": magnification,
                            "morphology": morphology,
                            "method": method,
                            "feature_id": center["feature_id"],
                            "sem_cell": center["sem_cell"],
                            "sem_cd_nm": center["sem_cd_nm"],
                            "contrast_fraction": float(fraction),
                            "apparent_cd_nm": measurement.cd_px * um_per_px * 1000.0,
                            "angular_mad_nm": measurement.angular_mad_px * um_per_px * 1000.0,
                            "edge_width_nm": measurement.edge_width_px * um_per_px * 1000.0,
                            "ringing_ratio": measurement.ringing_ratio,
                            "core_level": measurement.core_level,
                            "background_level": measurement.background_level,
                            "michelson_contrast": measurement.michelson_contrast,
                            "valid_angle_fraction": measurement.valid_angle_fraction,
                            "image_path": str(image_path),
                        })
            print(f"{magnification} {method}: measured with {sum(f['method'] == method and f['magnification'] == magnification for f in failures)} failure(s)", flush=True)
    detailed = pd.DataFrame(rows)
    intervals = module.interval_summary(detailed)
    summary = module.method_summary(intervals)
    output_root.mkdir(parents=True, exist_ok=True)
    detailed.to_csv(output_root / "circular_feature_threshold_measurements.csv", index=False)
    intervals.to_csv(output_root / "circular_feature_cd_intervals.csv", index=False)
    summary.to_csv(output_root / "circular_feature_method_summary.csv", index=False)
    pd.DataFrame(failures, columns=["magnification", "morphology", "method", "feature_id", "reason", "image_path"]).to_csv(
        output_root / "circular_measurement_failures.csv", index=False
    )
    (output_root / "metadata.json").write_text(json.dumps({
        "purpose": "SEM-referenced circular CD using the locked protocol",
        "failure_policy": "Per-feature protocol failures are retained and count as hard ranking failures",
        "failure_count": len(failures),
    }, indent=2), encoding="utf-8")


def evaluate(roster: dict, scenes: dict) -> None:
    manifest = build_evaluation_manifest(roster, scenes)
    jobs = [
        ("analyze_multimethod_displacement.py", "displacement", "displacement_summary.csv"),
        ("analyze_circular_cd_sharpness.py", "circular", "circular_feature_method_summary.csv"),
        ("analyze_line_multimethod.py", "line", "tables/line_displacement_by_sequence.csv"),
    ]
    for index, (filename, output_name, completion_marker) in enumerate(jobs):
        output_root = (RESULTS / "evaluation" / output_name).resolve()
        if (output_root / completion_marker).is_file():
            print(f"[evaluate] {output_name}: reused completed tables", flush=True)
            continue
        print(f"[evaluate] {output_name}", flush=True)
        module = load_module(SOURCE_SCRIPTS / filename, f"r67_eval_{index}")
        module.MANIFEST_PATH = manifest
        if output_name == "circular":
            evaluate_circular_tolerant(module, manifest, output_root)
        else:
            module.main(output_root, False)


def add_cells(rows: list[dict], table: pd.DataFrame, domain: str, keys: list[str], metrics: list[str], models: list[str]) -> None:
    table = table.loc[table["method"].isin(models)].copy()
    for metric in metrics:
        for key_values, group in table.groupby(keys, dropna=False, sort=False):
            if not isinstance(key_values, tuple):
                key_values = (key_values,)
            values = group.set_index("method")[metric].astype(float)
            values = values[np.isfinite(values) & (values >= 0)]
            if len(values) != len(models):
                continue
            best = float(values.min())
            # Scale excess error by the typical candidate value. This remains
            # finite when the best value is exactly zero, unlike a raw ratio.
            scale = max(float(values.median()), 1e-9)
            scene = "|".join(f"{key}={value}" for key, value in zip(keys, key_values))
            for model, value in values.items():
                rows.append({"domain": domain, "scene": scene, "metric": metric, "model": model, "value": float(value), "best_value": best, "cell_scale": scale, "regret": 1.0 + (float(value) - best) / scale})


def rank(roster: dict) -> pd.DataFrame:
    models = list(roster["models"])
    cells: list[dict] = []
    displacement = pd.read_csv(RESULTS / "evaluation" / "displacement" / "displacement_summary.csv")
    displacement = displacement.loc[displacement["population"].eq("common-valid intersection within Raw-selected top 30")]
    add_cells(cells, displacement, "pillar_via_motion", ["morphology", "sequence"], ["mae_nm", "signed_step_sd_nm", "mean_within_grid_nm"], models)
    circular = pd.read_csv(RESULTS / "evaluation" / "circular" / "circular_feature_method_summary.csv")
    add_cells(cells, circular, "sem_circular_cd", ["magnification", "morphology"], ["midpoint_mae_nm", "mean_distance_from_interval_nm", "mean_angular_mad_nm", "max_ringing_ratio"], models)
    line = pd.read_csv(RESULTS / "evaluation" / "line" / "tables" / "line_displacement_by_sequence.csv")
    add_cells(cells, line, "line_motion", ["sequence"], ["boundary_mae_nm", "profile_mae_nm", "median_within_edge_mad_nm"], models)
    cell_table = pd.DataFrame(cells)
    if cell_table.empty:
        raise RuntimeError("No complete ranking cells were produced")
    expected_models = set(models)
    if set(cell_table["model"]) != expected_models:
        raise RuntimeError("At least one model has no complete ranking cells")
    summaries = []
    failure_path = RESULTS / "evaluation" / "circular" / "circular_measurement_failures.csv"
    failures = pd.read_csv(failure_path) if failure_path.is_file() else pd.DataFrame(columns=["method"])
    availability = pd.read_csv(RESULTS / "evaluation" / "displacement" / "displacement_availability.csv")
    for model in models:
        group = cell_table.loc[cell_table["model"].eq(model)]
        circular_failures = int(failures["method"].eq(model).sum())
        model_availability = availability.loc[availability["method"].eq(model)]
        unavailable_steps = int((model_availability["selected_count"] - model_availability["evaluable_count"]).sum())
        summaries.append({
            "model": model,
            "circular_feature_failures": circular_failures,
            "unavailable_displacement_steps": unavailable_steps,
            "hard_measurement_failures": circular_failures + unavailable_steps,
            "complete_cells": len(group),
            "worst_case_regret": float(group["regret"].max()),
            "p90_regret": float(group["regret"].quantile(0.90)),
            "median_regret": float(group["regret"].median()),
            "mean_regret": float(group["regret"].mean()),
        })
    summary = pd.DataFrame(summaries).sort_values(
        ["hard_measurement_failures", "worst_case_regret", "p90_regret", "median_regret", "mean_regret"], kind="stable"
    ).reset_index(drop=True)
    summary.insert(0, "current_data_rank", np.arange(1, len(summary) + 1))
    summary["phase_a_complete"] = True
    summary["independent_holdout_complete"] = False
    summary["universal_pass"] = False
    ranking_dir = RESULTS / "ranking"
    ranking_dir.mkdir(parents=True, exist_ok=True)
    cell_table.to_csv(ranking_dir / "metric_cell_regrets.csv", index=False)
    summary.to_csv(ranking_dir / "model_ranking.csv", index=False)
    winner = summary.iloc[0]
    decision = {
        "current_data_winner": winner["model"],
        "selection_rule": "zero hard measurement failures, then minimum worst-case normalized regret; p90, median, and mean break ties",
        "universal_model_selected": None,
        "promotion_status": "BLOCKED_PENDING_SEALED_INDEPENDENT_HOLDOUT",
        "reason": "Phase A scenes overlap the model-development domain and motion truth is commanded rather than independently measured",
    }
    (ranking_dir / "decision.json").write_text(json.dumps(decision, indent=2), encoding="utf-8")
    return summary


def write_report(summary: pd.DataFrame) -> None:
    decision = read_json(RESULTS / "ranking" / "decision.json")
    run_records = read_json(RESULTS / "run_manifest.json")
    total_frames = sum(int(row["frames"]) for row in run_records)
    rows = [
        "# R67 Results",
        "",
        "## Outcome",
        "",
        f"- Current-data winner: **{decision['current_data_winner']}**.",
        "- Universal promotion: **not yet allowed**.",
        f"- Reconstruction coverage: {len(run_records)} model-sequence runs, {total_frames} frame outputs checked.",
        "- Reason: the available four sequences overlap the development domain and do not provide independent motion truth.",
        "",
        "## Worst-case-first ranking",
        "",
        "| Rank | Model | Circular failures | Unavailable steps | Worst-case regret | P90 regret | Median regret | Universal pass |",
        "|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for _, row in summary.iterrows():
        rows.append(f"| {int(row['current_data_rank'])} | {row['model']} | {int(row['circular_feature_failures'])} | {int(row['unavailable_displacement_steps'])} | {row['worst_case_regret']:.3f} | {row['p90_regret']:.3f} | {row['median_regret']:.3f} | No |")
    rows += [
        "",
        "A regret of 1.0 is best in that measurement cell. Excess error is scaled by the typical candidate result in the same cell, including cells whose best error is zero. The primary score is the single worst cell, so a model cannot hide a bad scene behind a strong average.",
        "",
        "## Required final gate",
        "",
        "Populate `config/phase_b_holdout.template.json` with sealed new sample lots, fields of view, focus/signal conditions, and independent motion/CD references. Run the same frozen candidates without tuning. Only then can one model receive the universal label.",
        "",
        "## Reproducibility",
        "",
        "The main script validates every checkpoint and input count, resumes complete reconstruction folders, runs the three locked measurement protocols, calculates the ranking, and rewrites this report.",
    ]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["validate", "reconstruct", "evaluate", "rank", "all"], default="all")
    args = parser.parse_args()
    roster, scenes = validate_inputs()
    print("[validate] all checkpoints, scripts, and raw frame counts passed", flush=True)
    if args.stage in {"reconstruct", "all"}:
        reconstruct(roster, scenes)
    if args.stage in {"evaluate", "all"}:
        evaluate(roster, scenes)
    if args.stage in {"rank", "all"}:
        summary = rank(roster)
        write_report(summary)
        print(summary.to_string(index=False), flush=True)
        print(f"[report] {REPORT}", flush=True)


if __name__ == "__main__":
    main()
