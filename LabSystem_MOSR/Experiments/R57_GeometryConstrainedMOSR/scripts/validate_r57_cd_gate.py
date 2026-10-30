"""CD gate for R57 100MG candidate reconstructions."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable


DEFAULT_SUMMARY_CSV = (
    Path(__file__).resolve().parents[3]
    / "Reconstruct_Progress"
    / "20260618_100MG_user_recon"
    / "cd_measurement_20260620_basler_ace"
    / "cd_measurement_summary_basler_50x.csv"
)
DEFAULT_REQUIRED_FEATURES = ("圓孔", "圓柱")


def _read_rows(summary_csv: Path) -> list[dict]:
    if not summary_csv.exists():
        raise FileNotFoundError(summary_csv)
    with summary_csv.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _to_float(value: object, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric value for {field}: {value!r}") from exc


def _row_map(rows: list[dict]) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for row in rows:
        image = str(row.get("image", "")).strip()
        feature = str(row.get("feature", "")).strip()
        if image and feature:
            out[(image, feature)] = row
    return out


def evaluate_cd_gate(
    *,
    summary_csv: Path,
    candidate_image: str,
    reference_image: str = "原圖",
    tolerance_nm: float = 0.0,
    required_features: Iterable[str] = DEFAULT_REQUIRED_FEATURES,
    max_abs_radius_error_nm: float | None = None,
    min_count: int = 1,
) -> dict:
    rows = _read_rows(Path(summary_csv))
    by_key = _row_map(rows)
    feature_results: dict[str, dict] = {}
    missing: list[str] = []
    passed = True

    for feature in required_features:
        candidate = by_key.get((candidate_image, feature))
        reference = by_key.get((reference_image, feature))
        if candidate is None or reference is None:
            missing.append(feature)
            passed = False
            continue
        cand_n = int(round(_to_float(candidate.get("n"), "n")))
        ref_n = int(round(_to_float(reference.get("n"), "n")))
        cand_err = _to_float(candidate.get("abs_radius_error_vs_sem_nm"), "abs_radius_error_vs_sem_nm")
        ref_err = _to_float(reference.get("abs_radius_error_vs_sem_nm"), "abs_radius_error_vs_sem_nm")
        no_worse_limit = ref_err + float(tolerance_nm)
        count_ok = cand_n >= int(min_count) and ref_n >= int(min_count)
        no_worse_ok = cand_err <= no_worse_limit
        max_ok = True if max_abs_radius_error_nm is None else cand_err <= float(max_abs_radius_error_nm)
        feature_passed = bool(count_ok and no_worse_ok and max_ok)
        feature_results[feature] = {
            "candidate_abs_radius_error_nm": cand_err,
            "reference_abs_radius_error_nm": ref_err,
            "allowed_abs_radius_error_nm": no_worse_limit,
            "delta_vs_reference_nm": cand_err - ref_err,
            "candidate_n": cand_n,
            "reference_n": ref_n,
            "count_ok": count_ok,
            "no_worse_ok": no_worse_ok,
            "max_ok": max_ok,
            "passed": feature_passed,
        }
        passed = passed and feature_passed

    valid_features = list(feature_results.values())
    candidate_mean = (
        sum(item["candidate_abs_radius_error_nm"] for item in valid_features) / len(valid_features)
        if valid_features
        else float("nan")
    )
    reference_mean = (
        sum(item["reference_abs_radius_error_nm"] for item in valid_features) / len(valid_features)
        if valid_features
        else float("nan")
    )
    return {
        "passed": bool(passed and not missing),
        "summary_csv": str(Path(summary_csv).resolve()),
        "candidate_image": candidate_image,
        "reference_image": reference_image,
        "tolerance_nm": float(tolerance_nm),
        "required_features": list(required_features),
        "missing_features": missing,
        "candidate_mean_abs_radius_error_nm": candidate_mean,
        "reference_mean_abs_radius_error_nm": reference_mean,
        "mean_delta_vs_reference_nm": candidate_mean - reference_mean,
        "feature_results": feature_results,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate an R57 candidate against the 100MG CD gate")
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--candidate-image", required=True)
    parser.add_argument("--reference-image", default="原圖")
    parser.add_argument("--tolerance-nm", type=float, default=0.0)
    parser.add_argument("--max-abs-radius-error-nm", type=float, default=None)
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--required-feature", action="append", dest="required_features", default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--allow-fail", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    result = evaluate_cd_gate(
        summary_csv=args.summary_csv,
        candidate_image=args.candidate_image,
        reference_image=args.reference_image,
        tolerance_nm=args.tolerance_nm,
        required_features=args.required_features or DEFAULT_REQUIRED_FEATURES,
        max_abs_radius_error_nm=args.max_abs_radius_error_nm,
        min_count=args.min_count,
    )
    text = json.dumps(result, indent=2, ensure_ascii=False)
    print(text)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(text + "\n", encoding="utf-8")
    if result["passed"] or args.allow_fail:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

