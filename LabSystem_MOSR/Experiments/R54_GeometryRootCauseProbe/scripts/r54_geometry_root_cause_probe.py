"""R54 geometry root-cause probe for LabSystem_MOSR.

This is a diagnosis round, not a promotable training run. It asks whether the
real checkboard failure is already visible in existing R53 evidence and whether
the strict-rectangle CAD references are safe enough for a small overfit probe.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_R53_SUMMARY = (
    LAB_ROOT
    / "Reconstruct_Progress"
    / "20250605_checkboard_external_gmf_prepare"
    / "corner_geometry_validation_r53_20260616"
    / "corner_metrics_summary.csv"
)
DEFAULT_CAD_ROOT = (
    LAB_ROOT
    / "Reconstruct_Progress"
    / "20260613_checkboard_cad_reference_strict_rect"
)
DEFAULT_OUTPUT_DIR = EXPERIMENT_ROOT / "results" / "root_cause_probe"
DEFAULT_REPORT_PATH = EXPERIMENT_ROOT / "reports" / "R54_DIAGNOSTIC.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _float(value: object, default: float = math.nan) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _median(values: Iterable[float], default: float = math.nan) -> float:
    clean = [float(v) for v in values if not math.isnan(float(v))]
    if not clean:
        return default
    return float(statistics.median(clean))


def _case_map(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["case"]: row for row in rows if row.get("case")}


def diagnose_corner_damage(summary_rows: list[dict[str, str]]) -> dict[str, object]:
    by_case = _case_map(summary_rows)
    raw = by_case["raw_input"]
    raw_median = _float(raw.get("median_corner_peak_shift_px"))
    raw_over5 = _float(raw.get("pct_peak_shift_gt_5px"))

    recon_rows = [row for row in summary_rows if row.get("case") != "raw_input"]
    worst = max(
        recon_rows,
        key=lambda row: (
            _float(row.get("pct_peak_shift_gt_5px"), -1.0),
            _float(row.get("median_corner_peak_shift_px"), -1.0),
        ),
    )
    best_recon = min(
        recon_rows,
        key=lambda row: (
            _float(row.get("pct_peak_shift_gt_5px"), math.inf),
            _float(row.get("median_corner_peak_shift_px"), math.inf),
        ),
    )

    raw_is_best = all(
        raw_over5 <= _float(row.get("pct_peak_shift_gt_5px"), math.inf)
        and raw_median <= _float(row.get("median_corner_peak_shift_px"), math.inf)
        for row in recon_rows
    )
    large_damage_cases = [
        row["case"]
        for row in recon_rows
        if _float(row.get("pct_peak_shift_gt_5px")) >= raw_over5 + 20.0
    ]

    r40 = by_case.get("lab_r40_best_tradeoff", {})
    r53_latest = by_case.get("lab_r53_realistic_latest", {})
    r40_over5 = _float(r40.get("pct_peak_shift_gt_5px"))
    r53_latest_over5 = _float(r53_latest.get("pct_peak_shift_gt_5px"))
    if raw_over5 and not math.isnan(r53_latest_over5):
        r53_latest_multiplier = r53_latest_over5 / raw_over5
    else:
        r53_latest_multiplier = math.nan

    damage_detected = bool(raw_is_best and large_damage_cases)
    return {
        "raw_is_best_geometry_reference": raw_is_best,
        "reconstruction_damage_detected": damage_detected,
        "raw_median_shift_px": raw_median,
        "raw_over5_pct": raw_over5,
        "best_reconstruction_case": best_recon["case"],
        "best_reconstruction_over5_pct": _float(best_recon.get("pct_peak_shift_gt_5px")),
        "worst_case": worst["case"],
        "worst_over5_pct": _float(worst.get("pct_peak_shift_gt_5px")),
        "damage_cases": large_damage_cases,
        "r53_latest_over5_delta_vs_r40_pct": r53_latest_over5 - r40_over5,
        "r53_latest_over5_multiplier_vs_raw": r53_latest_multiplier,
        "recommended_next_gate": (
            "block_long_training_until_small_probe_passes"
            if damage_detected
            else "long_training_gate_not_blocked_by_this_probe"
        ),
    }


def summarize_cad_reference(valid_csv: Path, quality_csv: Path, *, min_probe_pairs: int = 2) -> dict[str, object]:
    valid_rows = [row for row in read_csv(valid_csv) if row.get("valid_for_training") == "yes"]
    quality_rows = read_csv(quality_csv)
    valid_edge_p95 = [_float(row.get("edge_p95_px")) for row in valid_rows]
    valid_within = [_float(row.get("edge_within_2px_ratio")) for row in valid_rows]
    coverage = [_float(row.get("coverage")) for row in quality_rows if _float(row.get("coverage"), 0.0) > 0.0]
    reliable_area = [
        _float(row.get("reliable_area_px"))
        for row in quality_rows
        if _float(row.get("reliable_area_px"), 0.0) > 0.0
    ]
    high_quality_rows = [
        row
        for row in valid_rows
        if _float(row.get("edge_p95_px"), math.inf) <= 2.0
        and _float(row.get("edge_within_2px_ratio"), 0.0) >= 0.95
    ]
    median_coverage = _median(coverage)
    partial_gt_only = bool(not math.isnan(median_coverage) and median_coverage < 0.5)
    high_quality_ratio = len(high_quality_rows) / len(valid_rows) if valid_rows else 0.0
    return {
        "valid_pair_count": len(valid_rows),
        "quality_row_count": len(quality_rows),
        "high_quality_pair_count": len(high_quality_rows),
        "high_quality_pair_ratio": high_quality_ratio,
        "median_coverage": median_coverage,
        "min_coverage": min(coverage) if coverage else math.nan,
        "max_coverage": max(coverage) if coverage else math.nan,
        "median_reliable_area_px": _median(reliable_area),
        "max_edge_p95_px": max(valid_edge_p95) if valid_edge_p95 else math.nan,
        "median_edge_p95_px": _median(valid_edge_p95),
        "median_edge_within_2px_ratio": _median(valid_within),
        "partial_gt_only": partial_gt_only,
        "probe_ready": bool(len(high_quality_rows) >= min_probe_pairs),
        "label_policy_required": (
            "train_only_inside_reliable_mask"
            if partial_gt_only
            else "full_frame_gt_may_be_possible_after_manual_review"
        ),
    }


def select_overfit_probe_pairs(rows: list[dict[str, str]], *, limit: int = 12) -> list[dict[str, str]]:
    candidates = [
        row
        for row in rows
        if row.get("valid_for_training") == "yes"
        and _float(row.get("edge_p95_px"), math.inf) <= 2.0
        and _float(row.get("edge_within_2px_ratio"), 0.0) >= 0.95
    ]
    candidates.sort(
        key=lambda row: (
            _float(row.get("edge_p95_px"), math.inf),
            -_float(row.get("coverage"), 0.0),
            -_float(row.get("component_count"), 0.0),
            -_float(row.get("edge_within_2px_ratio"), 0.0),
            row.get("pair_id", ""),
        )
    )
    return candidates[:limit]


def attach_quality_metrics(
    valid_rows: list[dict[str, str]],
    quality_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    by_name = {row.get("source_name", ""): row for row in quality_rows}
    enriched: list[dict[str, str]] = []
    for row in valid_rows:
        source_name = Path(row.get("source_image", "")).name
        quality = by_name.get(source_name, {})
        combined = dict(row)
        for key in ("coverage", "reliable_area_px"):
            if key in quality:
                combined[key] = quality[key]
        enriched.append(combined)
    return enriched


def build_hypothesis_table(
    corner_diagnosis: dict[str, object],
    cad_summary: dict[str, object],
) -> list[dict[str, object]]:
    return [
        {
            "hypothesis": "H1_reconstruction_itself_damages_real_corners",
            "status": "supported" if corner_diagnosis["reconstruction_damage_detected"] else "not_supported",
            "evidence": (
                f"raw >5px={corner_diagnosis['raw_over5_pct']:.3f}%, "
                f"worst={corner_diagnosis['worst_case']} "
                f"{corner_diagnosis['worst_over5_pct']:.3f}%"
            ),
            "decision": "must gate on real-corner damage before long training",
        },
        {
            "hypothesis": "H2_more_generic_data_is_enough",
            "status": "contradicted",
            "evidence": "R53 used a larger realistic mix but worsened large-corner errors.",
            "decision": "do not repeat another long generic-data run first",
        },
        {
            "hypothesis": "H3_strict_rect_cad_gt_can_support_small_probe",
            "status": "supported" if cad_summary["probe_ready"] else "not_ready",
            "evidence": (
                f"{cad_summary['high_quality_pair_count']}/{cad_summary['valid_pair_count']} "
                "valid CAD pairs pass edge-quality filters"
            ),
            "decision": cad_summary["label_policy_required"],
        },
        {
            "hypothesis": "H4_psf_is_the_only_root_cause",
            "status": "not_proven",
            "evidence": "R51/R52/R53 changed blur/data strategy but large-corner errors remained.",
            "decision": "test PSF only after a masked small-sample probe isolates the geometry target",
        },
    ]


def make_overlay_contact_sheet(selected_rows: list[dict[str, str]], output_path: Path) -> None:
    if not selected_rows:
        return
    thumbs: list[tuple[str, Image.Image]] = []
    for row in selected_rows[:12]:
        overlay = Path(row.get("overlay_check", ""))
        if not overlay.exists():
            continue
        img = Image.open(overlay).convert("RGB")
        img.thumbnail((220, 160))
        canvas = Image.new("RGB", (220, 190), "white")
        canvas.paste(img, ((220 - img.width) // 2, 0))
        draw = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except OSError:
            font = ImageFont.load_default()
        draw.text((6, 164), str(row.get("pair_id", "")), fill="black", font=font)
        draw.text((6, 178), f"edge_p95={_float(row.get('edge_p95_px')):.3f}", fill="black", font=font)
        thumbs.append((str(row.get("pair_id", "")), canvas))
    if not thumbs:
        return
    cols = 3
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 220, rows * 190), "white")
    for idx, (_, canvas) in enumerate(thumbs):
        sheet.paste(canvas, ((idx % cols) * 220, (idx // cols) * 190))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def render_report(
    corner_diagnosis: dict[str, object],
    cad_summary: dict[str, object],
    hypotheses: list[dict[str, object]],
    selected_pairs: list[dict[str, str]],
    output_dir: Path,
) -> str:
    lines = [
        "# R54 Geometry Root-Cause Probe",
        "",
        "## Verdict",
        "",
        "Do not start another long Lab training run yet. Existing evidence already",
        "shows that reconstruction is damaging real checkboard corner geometry, and",
        "the strict-rectangle CAD labels are usable only as masked local supervision.",
        "",
        "## Corner Damage Evidence",
        "",
        f"- Raw input >5 px corner errors: {corner_diagnosis['raw_over5_pct']:.3f}%",
        f"- Best reconstruction by >5 px rate: {corner_diagnosis['best_reconstruction_case']} "
        f"({corner_diagnosis['best_reconstruction_over5_pct']:.3f}%)",
        f"- Worst reconstruction: {corner_diagnosis['worst_case']} "
        f"({corner_diagnosis['worst_over5_pct']:.3f}%)",
        f"- R53 latest minus Lab R40 >5 px rate: "
        f"{corner_diagnosis['r53_latest_over5_delta_vs_r40_pct']:.3f} percentage points",
        f"- Next gate: `{corner_diagnosis['recommended_next_gate']}`",
        "",
        "## CAD GT / Mask Evidence",
        "",
        f"- Valid CAD-reference pairs: {cad_summary['valid_pair_count']}",
        f"- High-quality probe pairs: {cad_summary['high_quality_pair_count']}",
        f"- Median reliable-mask coverage: {cad_summary['median_coverage']:.4f}",
        f"- Max CAD edge p95 error: {cad_summary['max_edge_p95_px']:.3f} px",
        f"- Label policy: `{cad_summary['label_policy_required']}`",
        "",
        "## Hypothesis Table",
        "",
        "| Hypothesis | Status | Evidence | Decision |",
        "|---|---|---|---|",
    ]
    for row in hypotheses:
        lines.append(
            f"| {row['hypothesis']} | {row['status']} | {row['evidence']} | {row['decision']} |"
        )

    lines.extend(
        [
            "",
            "## Selected Small-Probe Pairs",
            "",
            "| Pair | Coverage | Edge p95 px | Edge within 2 px | Components |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in selected_pairs:
        lines.append(
            f"| {row.get('pair_id', '')} | {_float(row.get('coverage'), 0.0):.4f} | "
            f"{_float(row.get('edge_p95_px')):.3f} | "
            f"{_float(row.get('edge_within_2px_ratio')):.3f} | "
            f"{_float(row.get('component_count'), 0.0):.0f} |"
        )

    lines.extend(
        [
            "",
            "## Next Experiment Gate",
            "",
            "The next runnable step should be a very small masked overfit probe. It",
            "passes only if the model can learn the selected real CAD regions without",
            "raising the real-corner >5 px damage rate against the raw input and Lab R40",
            "controls. If that fails, the issue is not data quantity.",
            "",
            "## Artifacts",
            "",
            f"- Diagnosis JSON: `{output_dir / 'r54_root_cause_diagnosis.json'}`",
            f"- Hypothesis table: `{output_dir / 'r54_hypothesis_table.csv'}`",
            f"- Selected probe pairs: `{output_dir / 'r54_small_overfit_probe_pairs.csv'}`",
            f"- Overlay contact sheet: `{output_dir / 'r54_small_probe_overlays.png'}`",
        ]
    )
    return "\n".join(lines) + "\n"


def run_probe(
    *,
    r53_summary: Path = DEFAULT_R53_SUMMARY,
    cad_root: Path = DEFAULT_CAD_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_path: Path = DEFAULT_REPORT_PATH,
    max_overfit_pairs: int = 12,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    corner_rows = read_csv(r53_summary)
    valid_csv = cad_root / "data_pairs_valid.csv"
    quality_csv = cad_root / "quality_summary.csv"
    cad_rows = attach_quality_metrics(read_csv(valid_csv), read_csv(quality_csv))

    corner_diagnosis = diagnose_corner_damage(corner_rows)
    cad_summary = summarize_cad_reference(valid_csv, quality_csv, min_probe_pairs=min(12, max_overfit_pairs))
    selected_pairs = select_overfit_probe_pairs(cad_rows, limit=max_overfit_pairs)
    hypotheses = build_hypothesis_table(corner_diagnosis, cad_summary)

    write_csv(output_dir / "r54_hypothesis_table.csv", hypotheses)
    write_csv(output_dir / "r54_small_overfit_probe_pairs.csv", selected_pairs)
    make_overlay_contact_sheet(selected_pairs, output_dir / "r54_small_probe_overlays.png")

    payload = {
        "corner_summary_source": str(r53_summary),
        "cad_reference_root": str(cad_root),
        "corner_diagnosis": corner_diagnosis,
        "cad_reference_summary": cad_summary,
        "hypotheses": hypotheses,
        "selected_probe_pair_count": len(selected_pairs),
        "selected_probe_pairs": selected_pairs,
    }
    (output_dir / "r54_root_cause_diagnosis.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    report_path.write_text(
        render_report(corner_diagnosis, cad_summary, hypotheses, selected_pairs, output_dir),
        encoding="utf-8",
    )
    return payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the R54 Lab geometry root-cause probe.")
    parser.add_argument("--r53-summary", type=Path, default=DEFAULT_R53_SUMMARY)
    parser.add_argument("--cad-root", type=Path, default=DEFAULT_CAD_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--max-overfit-pairs", type=int, default=12)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = run_probe(
        r53_summary=args.r53_summary,
        cad_root=args.cad_root,
        output_dir=args.output_dir,
        report_path=args.report_path,
        max_overfit_pairs=args.max_overfit_pairs,
    )
    corner = payload["corner_diagnosis"]
    cad = payload["cad_reference_summary"]
    print(f"reconstruction_damage_detected={corner['reconstruction_damage_detected']}")
    print(f"raw_over5_pct={corner['raw_over5_pct']:.3f}")
    print(f"worst_case={corner['worst_case']}:{corner['worst_over5_pct']:.3f}")
    print(f"cad_probe_ready={cad['probe_ready']}")
    print(f"selected_probe_pair_count={payload['selected_probe_pair_count']}")
    print(f"report={args.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
