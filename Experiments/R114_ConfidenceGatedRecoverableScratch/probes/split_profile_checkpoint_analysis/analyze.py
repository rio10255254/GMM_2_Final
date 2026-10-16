"""Read-only stage checkpoint audit for the R114B split-profile probe.

The comparison epochs are fixed by the training design.  In particular, this
tool never substitutes the latest checkpoint for a missing design epoch and
never selects a winning checkpoint.  It only assembles evidence that later
ACM, real-image and displacement tests can use.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import cv2
import torch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXED_STAGE_EPOCHS = (
    (12, "oracle_geometry", "oracle geometry endpoint"),
    (20, "predicted_geometry", "predicted geometry endpoint"),
    (24, "profile", "profile midpoint"),
    (28, "joint_refinement", "joint refinement endpoint"),
)
IDENTITY_WARNING_LEVEL = 1.0e-3
TILE_WARNING_LEVEL = 1.0e-5
PROFILE_ACTIVE_LEVEL = 1.0e-6


@dataclass(frozen=True)
class ArtifactSchedule:
    checkpoint_every: int = 2
    validation_every: int = 4
    preview_every: int = 4


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    os.replace(temporary, path)


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


def _parse_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _read_training_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    parsed: list[dict[str, Any]] = []
    for row in rows:
        clean: dict[str, Any] = dict(row)
        epoch = _parse_number(row.get("epoch"))
        if epoch is None or not float(epoch).is_integer():
            clean["_epoch_valid"] = False
        else:
            clean["epoch"] = int(epoch)
            clean["_epoch_valid"] = True
        parsed.append(clean)
    return parsed


def _matching_numbers(left: Any, right: Any, tolerance: float = 1.0e-10) -> bool:
    left_number = _parse_number(left)
    right_number = _parse_number(right)
    if left_number is None or right_number is None:
        return left is None and right is None
    return math.isclose(left_number, right_number, rel_tol=tolerance, abs_tol=tolerance)


def _expected_epochs(latest_epoch: int, every: int, total_epochs: int) -> list[int]:
    expected = list(range(every, latest_epoch + 1, every))
    if latest_epoch >= total_epochs and total_epochs not in expected:
        expected.append(total_epochs)
    return sorted(set(expected))


def _source_path(project_root: Path, relative: str) -> Path:
    return project_root.joinpath(*relative.replace("\\", "/").split("/"))


def _checkpoint_audit(
    path: Path,
    *,
    epoch: int,
    expected_stage: str,
    run_id: str,
    provenance: dict[str, Any],
    validation_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "nonempty": path.is_file() and path.stat().st_size > 0,
    }
    if not record["nonempty"]:
        record["loadable"] = False
        record["complete"] = False
        return record
    try:
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    except Exception as exc:  # corrupted/incompletely replaced file is evidence
        record.update(loadable=False, complete=False, error=f"{type(exc).__name__}: {exc}")
        return record

    model_state = checkpoint.get("model") if isinstance(checkpoint, dict) else None
    tensors = list(model_state.values()) if isinstance(model_state, dict) else []
    finite = bool(tensors) and all(
        not tensor.is_floating_point() or bool(torch.isfinite(tensor).all())
        for tensor in tensors
        if isinstance(tensor, torch.Tensor)
    )
    metadata_checks = {
        "epoch_matches": checkpoint.get("epoch") == epoch,
        "stage_matches": checkpoint.get("stage") == expected_stage,
        "run_id_matches": checkpoint.get("run_id") == run_id,
        "scratch_true": checkpoint.get("scratch") is True,
        "resume_disabled": checkpoint.get("resume_supported") is False,
        "foreign_checkpoint_false": checkpoint.get("foreign_checkpoint_loaded") is False,
        "initial_state_matches": checkpoint.get("initial_state_sha256")
        == provenance.get("initial_state_sha256"),
        "source_hashes_match": checkpoint.get("source_sha256")
        == provenance.get("source_sha256"),
    }
    checkpoint_validation = checkpoint.get("validation", {})
    validation_matches = validation_summary is not None and all(
        key in checkpoint_validation and _matching_numbers(value, checkpoint_validation[key])
        for key, value in validation_summary.items()
    )
    record.update(
        loadable=True,
        sha256=_sha256(path),
        size_bytes=path.stat().st_size,
        model_tensor_count=len(tensors),
        model_tensors_finite=finite,
        metadata=metadata_checks,
        validation_metadata_matches_json=validation_matches,
    )
    record["complete"] = (
        bool(tensors)
        and finite
        and all(metadata_checks.values())
        and validation_matches
    )
    return record


def _preview_audit(path: Path) -> dict[str, Any]:
    result = {
        "path": str(path),
        "exists": path.is_file(),
        "nonempty": path.is_file() and path.stat().st_size > 0,
    }
    if result["nonempty"]:
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        result["decodable"] = image is not None and image.size > 0
        result["shape"] = list(image.shape) if image is not None else None
    else:
        result["decodable"] = False
        result["shape"] = None
    result["complete"] = bool(result["nonempty"] and result["decodable"])
    return result


def _identity_metrics(row: dict[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    for key, raw in row.items():
        if key.startswith("train_") and "identity" in key:
            number = _parse_number(raw)
            if number is not None:
                values[key] = number
    return values


def _metric(summary: dict[str, Any] | None, name: str) -> float | None:
    return _parse_number(summary.get(name)) if summary else None


def _stage_record(
    *,
    run_dir: Path,
    epoch: int,
    expected_stage: str,
    purpose: str,
    rows_by_epoch: dict[int, list[dict[str, Any]]],
    run_id: str,
    provenance: dict[str, Any],
    latest_epoch: int,
) -> dict[str, Any]:
    rows = rows_by_epoch.get(epoch, [])
    validation_path = run_dir / "validation" / f"epoch_{epoch:03d}.json"
    checkpoint_path = run_dir / "weights" / f"epoch_{epoch:03d}.pth"
    preview_path = run_dir / "previews" / f"epoch_{epoch:03d}.png"
    record: dict[str, Any] = {
        "epoch": epoch,
        "expected_stage": expected_stage,
        "purpose": purpose,
        "availability": "pending" if epoch > latest_epoch else "incomplete",
        "selection_role": "fixed_design_evidence_point",
    }
    if epoch > latest_epoch:
        record["skip_reason"] = f"training has only completed epoch {latest_epoch}"
        return record

    row = rows[0] if len(rows) == 1 else None
    validation: dict[str, Any] | None = None
    validation_error: str | None = None
    if validation_path.is_file():
        try:
            validation = _read_json(validation_path)
        except Exception as exc:
            validation_error = f"{type(exc).__name__}: {exc}"
    summary = validation.get("summary") if isinstance(validation, dict) else None
    if not isinstance(summary, dict):
        summary = None

    checkpoint = _checkpoint_audit(
        checkpoint_path,
        epoch=epoch,
        expected_stage=expected_stage,
        run_id=run_id,
        provenance=provenance,
        validation_summary=summary,
    )
    preview = _preview_audit(preview_path)
    validation_audit = {
        "path": str(validation_path),
        "exists": validation_path.is_file(),
        "parseable": validation is not None,
        "error": validation_error,
        "has_summary": summary is not None,
        "canonical_tile_only": validation.get("canonical_tile_only") is True
        if validation
        else False,
    }
    required_summary = (
        "mae",
        "base_mae",
        "delta_abs",
        "profile_visibility_mean",
        "scenes",
        "canonical_tile_max_abs",
    )
    validation_audit["finite_required_metrics"] = summary is not None and all(
        _metric(summary, name) is not None for name in required_summary
    )
    validation_audit["complete"] = all(
        validation_audit[key]
        for key in ("exists", "parseable", "has_summary", "canonical_tile_only", "finite_required_metrics")
    )

    identity_values = _identity_metrics(row or {})
    identity_worst = max(identity_values.values(), default=None)
    tile = _metric(summary, "canonical_tile_max_abs")
    mae = _metric(summary, "mae")
    base_mae = _metric(summary, "base_mae")
    gain_abs = base_mae - mae if mae is not None and base_mae is not None else None
    gain_relative = gain_abs / base_mae if gain_abs is not None and base_mae else None
    visibility = _metric(summary, "profile_visibility_mean")
    profile_expected_active = epoch >= 24
    measurements = {
        "validation_mae": mae,
        "validation_base_mae": base_mae,
        "validation_gain_abs": gain_abs,
        "validation_gain_relative": gain_relative,
        "validation_delta_abs": _metric(summary, "delta_abs"),
        "profile_visibility_mean": visibility,
        "identity_metrics": identity_values,
        "identity_worst": identity_worst,
        "canonical_tile_max_abs": tile,
    }
    checks = {
        "one_training_row": len(rows) == 1,
        "training_stage_matches": row is not None and row.get("stage") == expected_stage,
        "validation_complete": bool(validation_audit["complete"]),
        "checkpoint_complete": bool(checkpoint.get("complete")),
        "preview_complete": bool(preview.get("complete")),
        "identity_metric_present_and_finite": identity_worst is not None,
        "identity_below_warning_level": identity_worst is not None
        and identity_worst <= IDENTITY_WARNING_LEVEL,
        "tile_metric_present_and_finite": tile is not None,
        "tile_below_warning_level": tile is not None and tile <= TILE_WARNING_LEVEL,
        "profile_visibility_lifecycle_valid": visibility is not None
        and (
            visibility > PROFILE_ACTIVE_LEVEL
            if profile_expected_active
            else visibility <= PROFILE_ACTIVE_LEVEL
        ),
        "profile_validation_gain_nonnegative": gain_abs is not None
        and (gain_abs >= 0.0 if profile_expected_active else True),
    }
    record.update(
        availability="complete" if all(checks.values()) else "review_required",
        training_row_count=len(rows),
        training_row=row,
        validation=validation_audit,
        checkpoint=checkpoint,
        preview=preview,
        measurements=measurements,
        checks=checks,
    )
    return record


def _comparison(stage: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    result = {
        "from_epoch": baseline["epoch"],
        "to_epoch": stage["epoch"],
        "available": stage.get("measurements") is not None
        and baseline.get("measurements") is not None,
    }
    if not result["available"]:
        return result
    for metric in (
        "validation_mae",
        "validation_base_mae",
        "validation_delta_abs",
        "profile_visibility_mean",
        "identity_worst",
        "canonical_tile_max_abs",
    ):
        start = baseline["measurements"].get(metric)
        end = stage["measurements"].get(metric)
        result[f"{metric}_change"] = end - start if start is not None and end is not None else None
    return result


def _full_run_file_audit(
    run_dir: Path,
    rows: list[dict[str, Any]],
    latest_epoch: int,
    total_epochs: int,
    schedule: ArtifactSchedule,
) -> dict[str, Any]:
    valid_epochs = [row["epoch"] for row in rows if row.get("_epoch_valid")]
    counts = {epoch: valid_epochs.count(epoch) for epoch in sorted(set(valid_epochs))}
    expected_rows = list(range(1, latest_epoch + 1))
    checkpoint_epochs = _expected_epochs(latest_epoch, schedule.checkpoint_every, total_epochs)
    validation_epochs = _expected_epochs(latest_epoch, schedule.validation_every, total_epochs)
    preview_epochs = _expected_epochs(latest_epoch, schedule.preview_every, total_epochs)

    def missing(folder: str, epochs: Iterable[int], suffix: str) -> list[int]:
        return [
            epoch
            for epoch in epochs
            if not (run_dir / folder / f"epoch_{epoch:03d}.{suffix}").is_file()
        ]

    result = {
        "latest_completed_epoch": latest_epoch,
        "training_log_missing_epochs": sorted(set(expected_rows) - set(valid_epochs)),
        "training_log_duplicate_epochs": [epoch for epoch, count in counts.items() if count != 1],
        "expected_checkpoint_epochs_through_latest": checkpoint_epochs,
        "missing_checkpoints_through_latest": missing("weights", checkpoint_epochs, "pth"),
        "expected_validation_epochs_through_latest": validation_epochs,
        "missing_validations_through_latest": missing("validation", validation_epochs, "json"),
        "expected_preview_epochs_through_latest": preview_epochs,
        "missing_previews_through_latest": missing("previews", preview_epochs, "png"),
    }
    result["complete_through_latest"] = not any(
        result[key]
        for key in (
            "training_log_missing_epochs",
            "training_log_duplicate_epochs",
            "missing_checkpoints_through_latest",
            "missing_validations_through_latest",
            "missing_previews_through_latest",
        )
    )
    return result


def _provenance_audit(
    project_root: Path,
    run_state: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    source_hashes = provenance.get("source_sha256", {})
    current_sources: dict[str, Any] = {}
    for relative, expected in source_hashes.items():
        path = _source_path(project_root, relative)
        current = _sha256(path) if path.is_file() else None
        current_sources[relative] = {
            "exists": path.is_file(),
            "expected_sha256": expected,
            "current_sha256": current,
            "matches": current == expected,
        }
    checks = {
        "provenance_scratch_true": provenance.get("scratch") is True,
        "provenance_resume_disabled": provenance.get("resume_supported") is False,
        "provenance_foreign_checkpoint_false": provenance.get("foreign_checkpoint_loaded") is False,
        "run_state_scratch_true": run_state.get("scratch") is True,
        "run_state_foreign_checkpoint_false": run_state.get("foreign_checkpoint_loaded") is False,
        "initial_state_matches_run_state": provenance.get("initial_state_sha256")
        == run_state.get("initial_state_sha256"),
        "initial_state_sha256_well_formed": isinstance(
            provenance.get("initial_state_sha256"), str
        )
        and len(provenance["initial_state_sha256"]) == 64,
        "dataset_manifest_sha256_well_formed": isinstance(
            provenance.get("dataset_manifest_sha256"), str
        )
        and len(provenance["dataset_manifest_sha256"]) == 64,
        "all_declared_sources_match_current_workspace": bool(current_sources)
        and all(item["matches"] for item in current_sources.values()),
    }
    return {
        "checks": checks,
        "pass": all(checks.values()),
        "initial_state_sha256": provenance.get("initial_state_sha256"),
        "dataset_manifest_sha256": provenance.get("dataset_manifest_sha256"),
        "source_files": current_sources,
    }


def _findings(report: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not report["provenance"]["pass"]:
        findings.append({"severity": "error", "message": "scratch/provenance contract needs review"})
    if not report["run_file_integrity"]["complete_through_latest"]:
        findings.append({"severity": "error", "message": "one or more artifacts are missing through the latest completed epoch"})
    for stage in report["stages"]:
        if stage["availability"] == "pending":
            findings.append(
                {
                    "severity": "pending",
                    "message": f"E{stage['epoch']:02d} is not available yet and was skipped, not failed",
                }
            )
            continue
        failed = [name for name, passed in stage["checks"].items() if not passed]
        if failed:
            findings.append(
                {
                    "severity": "review",
                    "message": f"E{stage['epoch']:02d} needs review: {', '.join(failed)}",
                }
            )
    if not findings:
        findings.append({"severity": "info", "message": "all currently available fixed-stage evidence checks passed"})
    findings.append(
        {
            "severity": "policy",
            "message": "no checkpoint was selected; locked ACM and deployment validation remain required",
        }
    )
    return findings


def analyze_run(run_dir: Path, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    training_log = run_dir / "training_log.csv"
    run_state_path = run_dir / "run_state.json"
    provenance_path = run_dir / "scratch_provenance.json"
    if not training_log.is_file():
        raise FileNotFoundError(training_log)
    if not run_state_path.is_file():
        raise FileNotFoundError(run_state_path)
    if not provenance_path.is_file():
        raise FileNotFoundError(provenance_path)

    log_hash_before = _sha256(training_log)
    rows = _read_training_rows(training_log)
    run_state = _read_json(run_state_path)
    provenance = _read_json(provenance_path)
    rows_by_epoch: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("_epoch_valid"):
            row = {key: value for key, value in row.items() if key != "_epoch_valid"}
            rows_by_epoch.setdefault(row["epoch"], []).append(row)
    latest_epoch = max(rows_by_epoch, default=0)
    total_epochs = int(run_state.get("epochs", latest_epoch))
    run_id = str(run_state.get("run_id", run_dir.name))
    config = _read_json(project_root / "config" / "split_profile_training.json")
    schedule = ArtifactSchedule(
        checkpoint_every=int(config["checkpoint_every_epochs"]),
        validation_every=int(config["validation_every_epochs"]),
        preview_every=int(config["preview_every_epochs"]),
    )
    stages = [
        _stage_record(
            run_dir=run_dir,
            epoch=epoch,
            expected_stage=stage,
            purpose=purpose,
            rows_by_epoch=rows_by_epoch,
            run_id=run_id,
            provenance=provenance,
            latest_epoch=latest_epoch,
        )
        for epoch, stage, purpose in FIXED_STAGE_EPOCHS
    ]
    baseline = stages[0]
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only_analysis": True,
        "run": {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "reported_status": run_state.get("status"),
            "latest_completed_epoch": latest_epoch,
            "total_epochs": total_epochs,
        },
        "fixed_stage_policy": {
            "epochs": [epoch for epoch, _stage, _purpose in FIXED_STAGE_EPOCHS],
            "missing_epochs_are_skipped": True,
            "latest_checkpoint_substitution": False,
            "automatic_selection_performed": False,
            "selected_epoch": None,
            "selection_requires_external_evidence": [
                "locked R73/R74 ACM",
                "canonical tiled deployment validation",
                "real microscopy review",
                "displacement stability",
            ],
        },
        "thresholds_are_diagnostic_not_selection_rules": {
            "identity_warning_level": IDENTITY_WARNING_LEVEL,
            "canonical_tile_warning_level": TILE_WARNING_LEVEL,
            "profile_active_level": PROFILE_ACTIVE_LEVEL,
        },
        "provenance": _provenance_audit(project_root, run_state, provenance),
        "run_file_integrity": _full_run_file_audit(
            run_dir, rows, latest_epoch, total_epochs, schedule
        ),
        "stages": stages,
        "comparisons_to_fixed_E12": [
            _comparison(stage, baseline) for stage in stages[1:]
        ],
    }
    log_hash_after = _sha256(training_log)
    report["training_log_snapshot"] = {
        "sha256_before": log_hash_before,
        "sha256_after": log_hash_after,
        "changed_during_analysis": log_hash_before != log_hash_after,
    }
    report["findings"] = _findings(report)
    return report


def _format_number(value: Any) -> str:
    return "--" if value is None else f"{float(value):.8g}"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# R114B fixed-stage checkpoint audit",
        "",
        f"Run: `{report['run']['run_id']}`",
        "",
        "This is a read-only comparison of E12/E20/E24/E28. Missing stages are skipped. "
        "The last checkpoint is never selected automatically.",
        "",
        "| Epoch | Stage | Status | MAE | Gain vs base | Identity worst | Tile max | Profile visibility |",
        "|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for stage in report["stages"]:
        metrics = stage.get("measurements", {})
        lines.append(
            "| E{epoch:02d} | {stage_name} | {status} | {mae} | {gain} | {identity} | {tile} | {visibility} |".format(
                epoch=stage["epoch"],
                stage_name=stage["expected_stage"],
                status=stage["availability"],
                mae=_format_number(metrics.get("validation_mae")),
                gain=_format_number(metrics.get("validation_gain_abs")),
                identity=_format_number(metrics.get("identity_worst")),
                tile=_format_number(metrics.get("canonical_tile_max_abs")),
                visibility=_format_number(metrics.get("profile_visibility_mean")),
            )
        )
    lines.extend(["", "## Findings", ""])
    lines.extend(
        f"- **{item['severity']}**: {item['message']}" for item in report["findings"]
    )
    lines.extend(
        [
            "",
            "## Selection policy",
            "",
            "No epoch is selected by this audit. A candidate must still pass locked ACM, "
            "canonical tiled deployment, real microscopy, and displacement tests.",
            "",
        ]
    )
    return "\n".join(lines)


def write_stage_csv(path: Path, report: dict[str, Any]) -> None:
    fields = [
        "epoch",
        "expected_stage",
        "availability",
        "validation_mae",
        "validation_base_mae",
        "validation_gain_abs",
        "validation_gain_relative",
        "identity_worst",
        "canonical_tile_max_abs",
        "profile_visibility_mean",
        "checkpoint_complete",
        "validation_complete",
        "preview_complete",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for stage in report["stages"]:
            measurements = stage.get("measurements", {})
            checks = stage.get("checks", {})
            writer.writerow(
                {
                    "epoch": stage["epoch"],
                    "expected_stage": stage["expected_stage"],
                    "availability": stage["availability"],
                    **{
                        name: measurements.get(name)
                        for name in fields
                        if name in measurements
                    },
                    "checkpoint_complete": checks.get("checkpoint_complete"),
                    "validation_complete": checks.get("validation_complete"),
                    "preview_complete": checks.get("preview_complete"),
                }
            )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="derived-output folder; defaults outside the active run directory",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="analyze and print a compact summary without writing any files",
    )
    args = parser.parse_args()
    report = analyze_run(args.run_dir, args.project_root.resolve())
    if args.no_write:
        print(
            json.dumps(
                {
                    "run": report["run"],
                    "provenance_pass": report["provenance"]["pass"],
                    "file_integrity": report["run_file_integrity"]["complete_through_latest"],
                    "stages": [
                        {
                            "epoch": item["epoch"],
                            "availability": item["availability"],
                            "measurements": item.get("measurements"),
                        }
                        for item in report["stages"]
                    ],
                    "automatic_selection_performed": False,
                    "selected_epoch": None,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    output_dir = args.output_dir or (
        args.project_root
        / "results"
        / "checkpoint_stage_analysis"
        / report["run"]["run_id"]
    )
    _atomic_json(output_dir / "analysis.json", report)
    _atomic_text(output_dir / "analysis.md", render_markdown(report))
    write_stage_csv(output_dir / "stage_metrics.csv", report)
    print(str(output_dir.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
