"""Evaluate one frozen R114 split-profile checkpoint with the locked R73/R74 ACM.

The default path is the complete sealed evaluation.  ``--smoke`` is an
explicitly non-formal, tiny end-to-end check that keeps the ACM implementation,
parameters, alignments, metrics, and all sensitivity presets unchanged while
using only the first family and first primary image.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Iterable

import cv2
import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validation.r114_split_profile_adapter import (  # noqa: E402
    canonical_tile_config,
    load_model,
    predict_canonical_tiled,
)


MATLAB = Path(r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe")
LOCKED_ACM_SCRIPTS = Path(
    r"D:\GMM_2_Final\Experiments\R82_R39R40CrossSceneGeneralizationBenchmark\scripts"
)
SUITE_SPECS = {
    "R73": {
        "manifest": ROOT / "validation" / "manifests" / "R73.json",
        "template": Path(
            r"D:\GMM_2_Final\Experiments\R104_PhotometricInvariantCausalGateScratch"
            r"\results\posttraining_validation\external_acm\R73_novel_shapes"
            r"\config\experiment.json"
        ),
    },
    "R74": {
        "manifest": ROOT / "validation" / "manifests" / "R74.json",
        "template": Path(
            r"D:\GMM_2_Final\Experiments\R104_PhotometricInvariantCausalGateScratch"
            r"\results\posttraining_validation\external_acm\R74_hard_microscopy"
            r"\config\experiment.json"
        ),
    },
}
SUMMARY_METRICS = (
    "iou",
    "mean_boundary_distance_px",
    "hd95_px",
    "area_error_pct",
    "perimeter_error_pct",
)
REQUIRED_PRIMARY_COLUMNS = {
    "image_id",
    "family",
    "filename",
    "method",
    "alignment",
    *SUMMARY_METRICS,
    "acm_success",
    "acm_error",
}
REQUIRED_SENSITIVITY_COLUMNS = REQUIRED_PRIMARY_COLUMNS | {"preset"}


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def decode_gray(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"cannot read grayscale image: {path}")
    return image


def write_bmp(path: Path, image: np.ndarray) -> None:
    if image.dtype != np.uint8 or image.ndim != 2:
        raise ValueError(f"BMP output must be 2-D uint8, got {image.shape} {image.dtype}")
    ok, encoded = cv2.imencode(".bmp", image)
    if not ok:
        raise RuntimeError(f"cannot encode BMP: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded.tobytes())


def validate_method_name(name: str) -> None:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
        raise ValueError("--method-name must be a MATLAB-safe identifier")
    if name in {"Raw", "TruthACM"}:
        raise ValueError(f"reserved method name: {name}")


def resolve_device(requested: str) -> torch.device:
    selected = "cuda:0" if requested == "auto" and torch.cuda.is_available() else requested
    if selected == "auto":
        selected = "cpu"
    device = torch.device(selected)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    return device


def family_maps(template: dict[str, Any]) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    families = template["dataset"]["families"]
    stages = {str(row["name"]): str(row["stage"]) for row in families}
    specs = {str(row["name"]): row for row in families}
    if len(stages) != len(families):
        raise RuntimeError("locked config contains duplicate family names")
    return stages, specs


def validate_full_manifest(
    suite: str,
    manifest: dict[str, Any],
    template: dict[str, Any],
) -> list[dict[str, Any]]:
    records = manifest.get("records")
    if manifest.get("suite") != suite or not isinstance(records, list):
        raise RuntimeError(f"invalid sealed manifest for {suite}")
    stages, _ = family_maps(template)
    expected_per_family = int(template["dataset"]["images_per_family"])
    expected_total = int(template["dataset"]["total_images"])
    # The shared validation manifest appends one clear identity guard after the
    # 100 sealed ACM records.  It is intentionally not part of MATLAB's locked
    # dataset contract, whose family list contains only the five degraded
    # families.  Accept only that explicit guard as an extra; unknown degraded
    # rows must still fail closed.
    locked_records = [row for row in records if str(row.get("family")) in stages]
    extras = [row for row in records if str(row.get("family")) not in stages]
    invalid_extras = [
        row
        for row in extras
        if str(row.get("role")) != "clear"
        or Path(row.get("source", "")).resolve() != Path(row.get("target", "")).resolve()
    ]
    if invalid_extras:
        raise RuntimeError(f"{suite} manifest contains non-contract degraded extras")
    if len(locked_records) != expected_total:
        raise RuntimeError(
            f"{suite} manifest has {len(locked_records)} locked ACM rows; "
            f"locked config requires {expected_total}"
        )
    counts: dict[str, int] = {name: 0 for name in stages}
    filenames: dict[str, set[str]] = {name: set() for name in stages}
    data_root = Path(template["dataset"]["root"])
    for row in locked_records:
        family = str(row.get("family"))
        if family not in stages:
            raise RuntimeError(f"unknown {suite} family in manifest: {family}")
        source = Path(row["source"])
        target = Path(row["target"])
        filename = source.name
        exact = data_root / "mask" / stages[family] / filename
        if not source.is_file() or not target.is_file() or not exact.is_file():
            raise FileNotFoundError(
                f"incomplete locked sample {suite}/{family}/{filename}: "
                f"source={source.is_file()} target={target.is_file()} mask={exact.is_file()}"
            )
        if filename in filenames[family]:
            raise RuntimeError(f"duplicate sealed sample: {suite}/{family}/{filename}")
        filenames[family].add(filename)
        counts[family] += 1
    if any(value != expected_per_family for value in counts.values()):
        raise RuntimeError(f"{suite} per-family manifest counts differ from locked config: {counts}")
    return locked_records


def selected_records(
    records: list[dict[str, Any]],
    template: dict[str, Any],
    smoke: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return primary records, inference union, and config for one suite."""

    config = copy.deepcopy(template)
    if not smoke:
        return records, records, config

    first_family = str(config["dataset"]["families"][0]["name"])
    family_rows = sorted(
        (row for row in records if str(row["family"]) == first_family),
        key=lambda row: Path(row["source"]).name,
    )
    if not family_rows:
        raise RuntimeError(f"smoke family is absent from manifest: {first_family}")
    primary = [family_rows[0]]
    required_names = {
        Path(primary[0]["source"]).name,
        *map(str, config["acm"]["sensitivity_filenames"]),
    }
    by_name = {Path(row["source"]).name: row for row in family_rows}
    missing = sorted(required_names - set(by_name))
    if missing:
        raise RuntimeError(f"smoke cannot preserve locked sensitivity set; missing {missing}")
    union = [by_name[name] for name in sorted(required_names)]
    family_spec = next(
        row for row in config["dataset"]["families"] if str(row["name"]) == first_family
    )
    config["dataset"]["families"] = [family_spec]
    config["dataset"]["images_per_family"] = 1
    config["dataset"]["total_images"] = 1
    return primary, union, config


def create_smoke_truth_root(
    suite_root: Path,
    template: dict[str, Any],
    records: Iterable[dict[str, Any]],
) -> Path:
    source_root = Path(template["dataset"]["root"])
    stages, _ = family_maps(template)
    destination_root = suite_root / "smoke_dataset"
    for row in records:
        family = str(row["family"])
        filename = Path(row["source"]).name
        stage = stages[family]
        for branch in ("src", "lbl", "mask"):
            source = source_root / branch / stage / filename
            destination = destination_root / branch / stage / filename
            if not source.is_file():
                raise FileNotFoundError(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    return destination_root


@torch.inference_mode()
def reconstruct_inputs(
    model: torch.nn.Module,
    device: torch.device,
    records: list[dict[str, Any]],
    stages: dict[str, str],
    suite_root: Path,
    method_name: str,
    tile_core: int,
) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    roots = {
        "Raw": suite_root / "inputs" / "Raw",
        method_name: suite_root / "inputs" / method_name,
    }
    tile = canonical_tile_config(model, core=tile_core)
    trace: list[dict[str, Any]] = []
    for index, row in enumerate(records, start=1):
        family = str(row["family"])
        stage = stages[family]
        source = Path(row["source"])
        filename = source.name
        raw = decode_gray(source)
        raw_destination = roots["Raw"] / stage / filename
        model_destination = roots[method_name] / stage / filename
        write_bmp(raw_destination, raw)
        tensor = torch.from_numpy(raw.astype(np.float32) / 255.0)[None, None].to(device)
        prediction = predict_canonical_tiled(model, tensor, tile)
        output_float = prediction.output[0, 0].clamp(0, 1).cpu().numpy()
        output = np.rint(output_float * 255.0).astype(np.uint8)
        write_bmp(model_destination, output)
        maps = prediction.maps
        trace.append(
            {
                "id": str(row["id"]),
                "family": family,
                "filename": filename,
                "source": str(source.resolve()),
                "source_sha256": sha256_file(source),
                "raw_output": str(raw_destination.resolve()),
                "raw_output_sha256": sha256_file(raw_destination),
                "model_output": str(model_destination.resolve()),
                "model_output_sha256": sha256_file(model_destination),
                "tile_count": int(prediction.tile_count),
                "mean_abs_change_0_255": float(np.abs(output_float - raw / 255.0).mean() * 255.0),
                "max_abs_change_0_255": float(np.abs(output_float - raw / 255.0).max() * 255.0),
                "width_gate_mean": float(maps["width_gate"].mean().item()),
                "shift_gate_mean": float(maps["shift_gate"].mean().item()),
                "profile_visibility_mean": float(maps["profile_visibility"].mean().item()),
                "all_finite": bool(torch.isfinite(prediction.output).all())
                and all(bool(torch.isfinite(value).all()) for value in maps.values()),
            }
        )
        print(f"  reconstructed {index}/{len(records)} {family}/{filename}", flush=True)
    if not all(row["all_finite"] for row in trace):
        raise RuntimeError("non-finite split-profile output detected")
    return roots, trace


def write_inference_manifest(
    path: Path,
    config: dict[str, Any],
    roots: dict[str, Path],
    method_name: str,
) -> None:
    output_dirs: dict[str, dict[str, str]] = {"Raw": {}, method_name: {}}
    for family in config["dataset"]["families"]:
        name, stage = str(family["name"]), str(family["stage"])
        output_dirs["Raw"][name] = str((roots["Raw"] / stage).resolve())
        output_dirs[method_name][name] = str((roots[method_name] / stage).resolve())
    write_json(
        path,
        {
            "suite": str(config["experiment_id"]),
            "methods": ["Raw", method_name],
            "output_dirs": output_dirs,
        },
    )


def expected_counts(config: dict[str, Any], method_count: int) -> dict[str, int]:
    family_count = len(config["dataset"]["families"])
    primary_images = int(config["dataset"]["total_images"])
    return {
        "primary_rows": primary_images * method_count * 2,
        "truth_rows": primary_images,
        "sensitivity_rows": family_count
        * len(config["acm"]["sensitivity_filenames"])
        * len(config["acm"]["sensitivity_presets"])
        * method_count,
    }


def table_paths(contract: Path) -> dict[str, Path]:
    tables = contract / "results" / "tables"
    return {
        "primary": tables / "primary_contour_metrics.csv",
        "truth": tables / "truth_acm_geometry_qa.csv",
        "sensitivity": tables / "acm_sensitivity_metrics.csv",
        "extraction": tables / "acm_extraction_summary.json",
    }


def tables_structurally_complete(contract: Path, expected: dict[str, int]) -> bool:
    paths = table_paths(contract)
    if not all(path.is_file() for path in paths.values()):
        return False
    try:
        return (
            len(pd.read_csv(paths["primary"])) == expected["primary_rows"]
            and len(pd.read_csv(paths["truth"])) == expected["truth_rows"]
            and len(pd.read_csv(paths["sensitivity"])) == expected["sensitivity_rows"]
        )
    except Exception:
        return False


def run_locked_acm(contract: Path, expected: dict[str, int]) -> None:
    if tables_structurally_complete(contract, expected):
        print(f"  locked ACM tables already complete: {contract}", flush=True)
        return
    if not MATLAB.is_file():
        raise FileNotFoundError(MATLAB)
    if not (LOCKED_ACM_SCRIPTS / "run_acm_multimethod.m").is_file():
        raise FileNotFoundError(LOCKED_ACM_SCRIPTS / "run_acm_multimethod.m")
    expression = (
        f"addpath('{LOCKED_ACM_SCRIPTS.as_posix()}'); "
        f"run_acm_multimethod('{contract.as_posix()}')"
    )
    result = subprocess.run(
        [str(MATLAB), "-batch", expression],
        cwd=contract,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log = contract / "logs" / "matlab_locked_acm.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout, encoding="utf-8", errors="replace")
    if result.returncode != 0 or not tables_structurally_complete(contract, expected):
        raise RuntimeError(f"locked ACM failed; inspect {log}")


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return series.astype(str).str.strip().str.lower().isin({"true", "1"})


def summarize_and_audit(
    suite: str,
    contract: Path,
    config: dict[str, Any],
    locked_template: dict[str, Any],
    method_name: str,
    expected: dict[str, int],
    trace: list[dict[str, Any]],
    smoke: bool,
) -> dict[str, Any]:
    paths = table_paths(contract)
    primary = pd.read_csv(paths["primary"])
    truth = pd.read_csv(paths["truth"])
    sensitivity = pd.read_csv(paths["sensitivity"])
    missing_primary = sorted(REQUIRED_PRIMARY_COLUMNS - set(primary.columns))
    missing_sensitivity = sorted(REQUIRED_SENSITIVITY_COLUMNS - set(sensitivity.columns))
    if missing_primary or missing_sensitivity:
        raise RuntimeError(
            f"locked ACM table schema changed: primary={missing_primary}, "
            f"sensitivity={missing_sensitivity}"
        )
    translated = primary.loc[primary["alignment"].eq("translation_only")].copy()
    method_summary = translated.groupby("method", as_index=False)[list(SUMMARY_METRICS)].median()
    family_summary = translated.groupby(["method", "family"], as_index=False)[
        list(SUMMARY_METRICS)
    ].median()
    summary_dir = contract / "results" / "summaries"
    summary_dir.mkdir(parents=True, exist_ok=True)
    method_summary.to_csv(
        summary_dir / "method_summary.csv", index=False, encoding="utf-8-sig"
    )
    family_summary.to_csv(
        summary_dir / "family_summary.csv", index=False, encoding="utf-8-sig"
    )

    primary_success = bool_series(primary["acm_success"])
    sensitivity_success = bool_series(sensitivity["acm_success"])
    actual_methods = sorted(map(str, primary["method"].unique()))
    expected_methods = sorted(["Raw", method_name])
    expected_families = sorted(str(row["name"]) for row in config["dataset"]["families"])
    checks = {
        "locked_acm_object_unchanged": config["acm"] == locked_template["acm"],
        "locked_acm_hash_unchanged": canonical_json_sha256(config["acm"])
        == canonical_json_sha256(locked_template["acm"]),
        "primary_row_count_exact": len(primary) == expected["primary_rows"],
        "truth_row_count_exact": len(truth) == expected["truth_rows"],
        "sensitivity_row_count_exact": len(sensitivity) == expected["sensitivity_rows"],
        "methods_exact": actual_methods == expected_methods,
        "families_exact": sorted(map(str, primary["family"].unique())) == expected_families,
        "primary_alignments_exact": sorted(map(str, primary["alignment"].unique()))
        == ["fixed_pixel_coordinates", "translation_only"],
        "translated_primary_complete": len(translated)
        == int(config["dataset"]["total_images"]) * len(expected_methods),
        "primary_zero_failures": bool(primary_success.all()),
        "sensitivity_zero_failures": bool(sensitivity_success.all()),
        "all_reconstructions_finite": all(row["all_finite"] for row in trace),
        "method_summary_complete": set(method_summary["method"].astype(str))
        == set(expected_methods),
        "family_summary_complete": len(family_summary)
        == len(expected_methods) * len(expected_families),
    }
    audit = {
        "status": "pass" if all(checks.values()) else "fail",
        "mode": "non_formal_smoke" if smoke else "sealed_full",
        "suite": suite,
        "checks": checks,
        "failure_counts": {
            "primary": int((~primary_success).sum()),
            "sensitivity": int((~sensitivity_success).sum()),
        },
        "rows": {
            "primary": len(primary),
            "truth": len(truth),
            "sensitivity": len(sensitivity),
        },
        "locked_acm_sha256": canonical_json_sha256(locked_template["acm"]),
    }
    write_json(summary_dir / "zero_failure_audit.json", audit)

    indexed = method_summary.set_index("method")
    raw = indexed.loc["Raw"]
    model = indexed.loc[method_name]
    family_index = family_summary.set_index(["method", "family"])
    effects = []
    for family in expected_families:
        before = family_index.loc[("Raw", family)]
        after = family_index.loc[(method_name, family)]
        effects.append(
            {
                "family": family,
                "boundary_change_pct": float(
                    (after["mean_boundary_distance_px"] / before["mean_boundary_distance_px"] - 1)
                    * 100
                ),
                "hd95_change_pct": float((after["hd95_px"] / before["hd95_px"] - 1) * 100),
                "iou_delta": float(after["iou"] - before["iou"]),
            }
        )
    result = {
        "status": "complete" if audit["status"] == "pass" else "failed_audit",
        "mode": audit["mode"],
        "suite": suite,
        "protocol": "locked Chan-Vese ACM; translation-only primary comparison",
        "raw": {key: float(raw[key]) for key in SUMMARY_METRICS},
        "model": {key: float(model[key]) for key in SUMMARY_METRICS},
        "effect": {
            "overall_boundary_change_pct": float(
                (model["mean_boundary_distance_px"] / raw["mean_boundary_distance_px"] - 1)
                * 100
            ),
            "overall_hd95_change_pct": float((model["hd95_px"] / raw["hd95_px"] - 1) * 100),
            "overall_iou_delta": float(model["iou"] - raw["iou"]),
            "families": effects,
        },
        "zero_failure_audit": audit,
    }
    write_json(summary_dir / "analysis_summary.json", result)
    return result


def write_trace(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError("empty reconstruction trace")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prepare_suite(
    suite: str,
    output_root: Path,
    checkpoint: Path,
    checkpoint_sha256: str,
    model: torch.nn.Module,
    device: torch.device,
    method_name: str,
    tile_core: int,
    smoke: bool,
    prepare_only: bool,
) -> dict[str, Any]:
    spec = SUITE_SPECS[suite]
    manifest = read_json(spec["manifest"])
    template = read_json(spec["template"])
    records = validate_full_manifest(suite, manifest, template)
    primary_records, inference_records, config = selected_records(records, template, smoke)
    suite_root = output_root / suite
    if smoke:
        config["dataset"]["root"] = str(
            create_smoke_truth_root(suite_root, template, inference_records).resolve()
        )
    config["experiment_id"] = (
        f"R114_{suite}_SplitProfile_LockedACM_"
        f"{'Smoke' if smoke else 'Full'}_{method_name}"
    )
    stages, _ = family_maps(template)
    roots, trace = reconstruct_inputs(
        model, device, inference_records, stages, suite_root, method_name, tile_core
    )
    write_trace(suite_root / "reconstruction_trace.csv", trace)

    contract = suite_root / "locked_acm_contract"
    write_json(contract / "config" / "experiment.json", config)
    write_inference_manifest(
        contract / "results" / "inference_manifest.json", config, roots, method_name
    )
    expected = expected_counts(config, method_count=2)
    preparation = {
        "status": "prepared" if prepare_only else "running_acm",
        "mode": "non_formal_smoke" if smoke else "sealed_full",
        "suite": suite,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha256,
        "method": method_name,
        "manifest": str(spec["manifest"]),
        "manifest_sha256": sha256_file(spec["manifest"]),
        "locked_template": str(spec["template"]),
        "locked_template_sha256": sha256_file(spec["template"]),
        "locked_acm_sha256": canonical_json_sha256(template["acm"]),
        "locked_acm_preserved": config["acm"] == template["acm"],
        "primary_record_count": len(primary_records),
        "inference_record_count": len(inference_records),
        "expected_tables": expected,
        "contract": str(contract.resolve()),
    }
    write_json(suite_root / "preparation_audit.json", preparation)
    if prepare_only:
        return preparation
    run_locked_acm(contract, expected)
    result = summarize_and_audit(
        suite,
        contract,
        config,
        template,
        method_name,
        expected,
        trace,
        smoke,
    )
    preparation["status"] = result["status"]
    write_json(suite_root / "preparation_audit.json", preparation)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run locked R73/R74 ACM for one frozen R114 split-profile checkpoint"
    )
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--method-name", default="R114SplitProfile")
    parser.add_argument("--suite", nargs="+", choices=sorted(SUITE_SPECS), default=["R73", "R74"])
    parser.add_argument("--device", default="auto", help="auto, cpu, or a torch device such as cuda:0")
    parser.add_argument("--tile-core", type=int, default=768)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="non-formal one-family/one-primary-image end-to-end test",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="reconstruct and write the locked contract without launching MATLAB",
    )
    args = parser.parse_args()

    validate_method_name(args.method_name)
    if args.tile_core <= 0:
        raise ValueError("--tile-core must be positive")
    checkpoint = Path(args.checkpoint).expanduser().resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    output_root = Path(args.output).expanduser().resolve()
    if output_root == ROOT or ROOT in output_root.parents and output_root.name in {"validation", "model"}:
        raise ValueError("refusing to write evaluation artifacts into a source-code directory")
    output_root.mkdir(parents=True, exist_ok=True)
    device = resolve_device(args.device)
    checkpoint_sha256 = sha256_file(checkpoint)

    identity = {
        "schema_version": 1,
        "mode": "non_formal_smoke" if args.smoke else "sealed_full",
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_sha256,
        "method": args.method_name,
        "suites": args.suite,
        "device": str(device),
        "tile_core": args.tile_core,
        "prepare_only": bool(args.prepare_only),
    }
    identity_path = output_root / "run_manifest.json"
    if identity_path.is_file():
        previous = read_json(identity_path)
        identity_fields = (
            "mode",
            "checkpoint_sha256",
            "method",
            "suites",
            "tile_core",
            "prepare_only",
        )
        if any(previous.get(key) != identity.get(key) for key in identity_fields):
            raise RuntimeError(
                "output already belongs to a different evaluation; choose a fresh --output"
            )
    write_json(identity_path, identity)

    print(f"Loading frozen split-profile checkpoint on {device}: {checkpoint}", flush=True)
    model = load_model(str(checkpoint), device)
    results = []
    for suite in args.suite:
        print(f"Preparing {suite} ({identity['mode']})", flush=True)
        results.append(
            prepare_suite(
                suite,
                output_root,
                checkpoint,
                checkpoint_sha256,
                model,
                device,
                args.method_name,
                args.tile_core,
                args.smoke,
                args.prepare_only,
            )
        )
    overall_status = (
        "prepared"
        if args.prepare_only
        else "complete"
        if all(row.get("status") == "complete" for row in results)
        else "failed_audit"
    )
    summary = {**identity, "status": overall_status, "results": results}
    write_json(output_root / "analysis_summary.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    return 0 if overall_status in {"prepared", "complete"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
