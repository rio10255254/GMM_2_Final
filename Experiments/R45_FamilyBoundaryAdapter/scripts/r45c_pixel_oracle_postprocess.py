"""R45C pixel-residual oracle post-processing.

Reads `r45c_patch_residuals_*.csv` produced by `r45c_region_oracle.py` and
computes the pixel-residual oracle counterpart of the shape oracle.

The shape oracle picks the teacher with lowest `shape_error_score` in each
patch.  The pixel-residual oracle picks the teacher with the largest
`mean_error_reduction` (positive = teacher beats base R44B from R42 in
boundary-band absolute pixel error).  Comparing the two reveals whether
shape and pixel quality move together — R45C found they do not.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT_ROOT = REPO_ROOT / "Experiments" / "R45_FamilyBoundaryAdapter"
DEFAULT_INPUT = EXPERIMENT_ROOT / "results" / "r45c_region_oracle"
DEFAULT_OUTPUT = DEFAULT_INPUT / "r45c_pixel_oracle_summary.json"
BASE_LABEL = "(base R44B from R42)"


def pixel_oracle_for_size(residuals_path: Path) -> dict:
    rows = list(csv.DictReader(residuals_path.open(encoding="utf-8-sig")))
    by_patch: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        by_patch[(row["case_id"], row["patch_id"])].append(row)
    n_total = len(by_patch)
    n_positive = 0
    sum_oracle_gain = 0.0
    pixel_oracle_counts: Counter = Counter()
    by_family_total: dict[str, int] = defaultdict(int)
    by_family_positive: dict[str, int] = defaultdict(int)
    by_family_gain: dict[str, float] = defaultdict(float)
    by_family_counts: dict[str, Counter] = defaultdict(Counter)
    for (_case, _pid), group in by_patch.items():
        family = group[0]["feature_family"]
        by_family_total[family] += 1
        best = max(group, key=lambda g: float(g["mean_error_reduction"]))
        max_red = float(best["mean_error_reduction"])
        if max_red > 0:
            n_positive += 1
            sum_oracle_gain += max_red
            pixel_oracle_counts[best["teacher"]] += 1
            by_family_positive[family] += 1
            by_family_gain[family] += max_red
            by_family_counts[family][best["teacher"]] += 1
        else:
            pixel_oracle_counts[BASE_LABEL] += 1
            by_family_counts[family][BASE_LABEL] += 1

    return {
        "patch_count": n_total,
        "patches_pixel_oracle_improves": n_positive,
        "patches_pixel_oracle_improves_pct": (n_positive / n_total * 100.0) if n_total else float("nan"),
        "patches_base_remains_pixel_best": n_total - n_positive,
        "patches_base_remains_pixel_best_pct": ((n_total - n_positive) / n_total * 100.0) if n_total else float("nan"),
        "avg_pixel_reduction_on_positive": (sum_oracle_gain / n_positive) if n_positive else float("nan"),
        "pixel_oracle_model_counts": dict(pixel_oracle_counts.most_common()),
        "by_family": {
            fam: {
                "patch_count": by_family_total[fam],
                "patches_pixel_oracle_improves": by_family_positive[fam],
                "patches_pixel_oracle_improves_pct": (by_family_positive[fam] / by_family_total[fam] * 100.0) if by_family_total[fam] else float("nan"),
                "avg_pixel_reduction_on_positive": (by_family_gain[fam] / by_family_positive[fam]) if by_family_positive[fam] else float("nan"),
                "pixel_oracle_model_counts": dict(by_family_counts[fam].most_common()),
            }
            for fam in sorted(by_family_total)
        },
    }


def _json_safe(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute pixel-residual oracle from R45C residuals CSVs.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    summary: dict[str, dict] = {}
    for csv_path in sorted(args.input_dir.glob("r45c_patch_residuals_*.csv")):
        size_str = csv_path.stem.rsplit("_", 1)[-1]
        try:
            size = int(size_str)
        except ValueError:
            continue
        summary[f"patch_{size:03d}"] = {"patch_size": size, **pixel_oracle_for_size(csv_path)}

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(_json_safe(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
