from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class BadStep:
    dataset: str
    group: str
    step_index: int
    filename: str
    dx_um: float
    dy_um: float
    dx_error_um: float
    reason: str


@dataclass(frozen=True)
class AuditResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]
    excluded_frames: dict[str, dict[str, list[int]]]
    bad_steps: list[BadStep]


def parse_frame_index(name: str | None) -> int | None:
    if not name:
        return None
    matches = re.findall(r"(\d+)", str(name))
    if not matches:
        return None
    return int(matches[-1])


def expand_bad_steps_to_frames(
    step_indices: Iterable[int],
    *,
    neighbor_radius: int = 1,
    min_frame: int = 0,
) -> list[int]:
    frames: set[int] = set()
    radius = max(0, int(neighbor_radius))
    for step in step_indices:
        center = int(step)
        for frame in range(center - radius, center + radius + 1):
            if frame >= min_frame:
                frames.add(frame)
    return sorted(frames)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _reason(dx_bad: bool, dy_bad: bool) -> str:
    if dx_bad and dy_bad:
        return "dx_error+y_drift"
    if dx_bad:
        return "dx_error"
    return "y_drift"


def detect_bad_steps_from_gmf_csv(
    steps_csv: Path,
    *,
    dataset: str,
    group: str,
    nominal_um: float,
    object_um_per_px: float,
    dx_error_threshold_um: float = 0.15,
    dy_threshold_um: float = 0.10,
) -> list[BadStep]:
    bad_steps: list[BadStep] = []
    for row in _read_csv(Path(steps_csv)):
        if row.get("status") != "ok":
            continue
        frame_index = parse_frame_index(row.get("frame_index"))
        if frame_index is None or frame_index <= 0:
            continue
        dx_px = float(row.get("dx_px") or 0.0)
        dy_px = float(row.get("dy_px") or 0.0)
        dx_um = abs(dx_px) * float(object_um_per_px)
        dy_um = abs(dy_px) * float(object_um_per_px)
        dx_error_um = abs(dx_um - float(nominal_um))
        dx_bad = dx_error_um > float(dx_error_threshold_um)
        dy_bad = dy_um > float(dy_threshold_um)
        if not dx_bad and not dy_bad:
            continue
        bad_steps.append(
            BadStep(
                dataset=str(dataset),
                group=str(group),
                step_index=int(frame_index),
                filename=str(row.get("filename") or f"frame_{frame_index:04d}.bmp"),
                dx_um=float(dx_um),
                dy_um=float(dy_um),
                dx_error_um=float(dx_error_um),
                reason=_reason(dx_bad, dy_bad),
            )
        )
    return bad_steps


def detect_bad_steps_from_results_csv(
    results_csv: Path,
    *,
    baseline_case: str = "raw",
    dx_error_threshold_um: float = 0.15,
    dy_threshold_um: float = 0.10,
) -> list[BadStep]:
    bad_steps: list[BadStep] = []
    for row in _read_csv(Path(results_csv)):
        if str(row.get("case", "")) != str(baseline_case):
            continue
        bad_steps.extend(
            detect_bad_steps_from_gmf_csv(
                Path(row["steps_csv"]),
                dataset=str(row["dataset"]),
                group=str(row["group"]),
                nominal_um=float(row["nominal_um"]),
                object_um_per_px=float(row["object_um_per_px"]),
                dx_error_threshold_um=dx_error_threshold_um,
                dy_threshold_um=dy_threshold_um,
            )
        )
    return bad_steps


def _excluded_frame_map(
    bad_steps: Iterable[BadStep],
    *,
    neighbor_radius: int,
) -> dict[tuple[str, str], list[int]]:
    by_key: dict[tuple[str, str], list[int]] = defaultdict(list)
    for step in bad_steps:
        by_key[(step.dataset, step.group)].append(step.step_index)
    return {
        key: expand_bad_steps_to_frames(values, neighbor_radius=neighbor_radius)
        for key, values in by_key.items()
    }


def _pair_frame_index(pair: dict[str, Any]) -> int | None:
    if str(pair.get("role") or "") == "target_real_selfshift_motion_pair":
        return parse_frame_index(str(pair.get("source_frame_name") or ""))
    frame = pair.get("motion_frame")
    if frame is not None:
        try:
            return int(frame)
        except (TypeError, ValueError):
            pass
    return parse_frame_index(str(pair.get("source_frame_name") or ""))


def _risk_type(role: str) -> str:
    if role == "target_real_motion_pair":
        return "direct_label_conflict"
    if role == "target_real_selfshift_motion_pair":
        return "source_texture_only"
    return "affected_context"


def audit_manifest_pairs(
    manifest: dict[str, Any],
    bad_steps: list[BadStep],
    *,
    neighbor_radius: int = 1,
) -> AuditResult:
    excluded = _excluded_frame_map(bad_steps, neighbor_radius=neighbor_radius)
    bad_step_lookup = {
        (step.dataset, step.group, step.step_index): step for step in bad_steps
    }
    rows: list[dict[str, Any]] = []
    for index, pair in enumerate(manifest.get("pairs", [])):
        dataset = str(pair.get("target_dataset") or "")
        group = str(pair.get("target_sequence") or "")
        frame_index = _pair_frame_index(pair)
        if frame_index is None:
            continue
        frames = excluded.get((dataset, group), [])
        if frame_index not in frames:
            continue
        nearest_bad_steps = [
            step
            for step in bad_steps
            if step.dataset == dataset and step.group == group and abs(step.step_index - frame_index) <= neighbor_radius
        ]
        nearest = nearest_bad_steps[0] if nearest_bad_steps else bad_step_lookup.get((dataset, group, frame_index))
        role = str(pair.get("role") or "unknown")
        row = {
            "manifest_index": index,
            "role": role,
            "risk_type": _risk_type(role),
            "target_dataset": dataset,
            "target_sequence": group,
            "motion_frame": frame_index,
            "source_frame_name": str(pair.get("source_frame_name") or ""),
            "source_group": str(pair.get("source_group") or ""),
            "motion_dx_px": pair.get("motion_dx_px"),
            "motion_dy_px": pair.get("motion_dy_px"),
        }
        if nearest is not None:
            row.update(
                {
                    "trigger_step": nearest.step_index,
                    "trigger_dx_um": nearest.dx_um,
                    "trigger_dy_um": nearest.dy_um,
                    "trigger_dx_error_um": nearest.dx_error_um,
                    "trigger_reason": nearest.reason,
                }
            )
        rows.append(row)

    affected_by_role = Counter(str(row["role"]) for row in rows)
    affected_by_risk = Counter(str(row["risk_type"]) for row in rows)
    excluded_frames: dict[str, dict[str, list[int]]] = defaultdict(dict)
    for (dataset, group), frames in excluded.items():
        excluded_frames[dataset][group] = frames
    summary = {
        "bad_step_count": len(bad_steps),
        "affected_pair_count": len(rows),
        "direct_label_conflict_count": affected_by_risk.get("direct_label_conflict", 0),
        "source_texture_only_count": affected_by_risk.get("source_texture_only", 0),
        "affected_context_count": affected_by_risk.get("affected_context", 0),
        "affected_by_role": dict(sorted(affected_by_role.items())),
        "affected_by_risk": dict(sorted(affected_by_risk.items())),
    }
    return AuditResult(
        rows=rows,
        summary=summary,
        excluded_frames={dataset: dict(groups) for dataset, groups in excluded_frames.items()},
        bad_steps=bad_steps,
    )


def _fields(rows: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_fields(rows), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def run_audit(
    *,
    manifest_path: Path,
    results_csv: Path,
    output_dir: Path,
    baseline_case: str = "raw",
    neighbor_radius: int = 1,
    dx_error_threshold_um: float = 0.15,
    dy_threshold_um: float = 0.10,
) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    bad_steps = detect_bad_steps_from_results_csv(
        Path(results_csv),
        baseline_case=baseline_case,
        dx_error_threshold_um=dx_error_threshold_um,
        dy_threshold_um=dy_threshold_um,
    )
    audit = audit_manifest_pairs(manifest, bad_steps, neighbor_radius=neighbor_radius)
    output_dir.mkdir(parents=True, exist_ok=True)
    bad_steps_csv = output_dir / "bad_gmf_steps.csv"
    affected_pairs_csv = output_dir / "affected_training_pairs.csv"
    summary_json = output_dir / "audit_summary.json"
    _write_csv(bad_steps_csv, [asdict(step) for step in bad_steps])
    _write_csv(affected_pairs_csv, audit.rows)
    payload = {
        "manifest_path": str(manifest_path),
        "results_csv": str(results_csv),
        "baseline_case": baseline_case,
        "neighbor_radius": neighbor_radius,
        "dx_error_threshold_um": dx_error_threshold_um,
        "dy_threshold_um": dy_threshold_um,
        "summary": audit.summary,
        "excluded_frames": audit.excluded_frames,
        "bad_steps_csv": str(bad_steps_csv),
        "affected_pairs_csv": str(affected_pairs_csv),
    }
    _write_json(summary_json, payload)
    payload["summary_json"] = str(summary_json)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit R62 real-motion training records against GMF bad steps.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--results-csv", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--baseline-case", default="raw")
    parser.add_argument("--neighbor-radius", type=int, default=1)
    parser.add_argument("--dx-error-threshold-um", type=float, default=0.15)
    parser.add_argument("--dy-threshold-um", type=float, default=0.10)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_audit(
        manifest_path=Path(args.manifest),
        results_csv=Path(args.results_csv),
        output_dir=Path(args.output_dir),
        baseline_case=str(args.baseline_case),
        neighbor_radius=int(args.neighbor_radius),
        dx_error_threshold_um=float(args.dx_error_threshold_um),
        dy_threshold_um=float(args.dy_threshold_um),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
