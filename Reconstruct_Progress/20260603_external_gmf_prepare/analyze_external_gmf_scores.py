from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PATHS_TSV = ROOT / "paths_for_gmf_tool.tsv"
OUT_JSON = ROOT / "gmf_exploratory_summary.json"
OUT_MD = ROOT / "gmf_exploratory_summary.md"


def parse_gmf_score(path: Path) -> dict[str, dict[str, float]]:
    parsed: dict[str, dict[str, float]] = {}
    with path.open("r", encoding="utf-8-sig") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            tokens = [tok.strip() for tok in line.split(",")]
            if len(tokens) < 4:
                continue
            record: dict[str, str] = {}
            for idx in range(len(tokens) // 2):
                key = tokens[idx * 2]
                val = tokens[idx * 2 + 1]
                if key:
                    record[key] = val
            fname = record.get("FileName")
            pos_y = record.get("PosY")
            if not fname or pos_y is None:
                continue
            try:
                parsed[fname] = {
                    "pos_x": float(record.get("PosX", "nan")),
                    "pos_y": float(pos_y),
                    "score0": float(record.get("Score0", "nan")),
                }
            except ValueError:
                continue
    return parsed


def std_pop(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def finite_mean(values: list[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return None
    return sum(finite) / len(finite)


def compute_stats(parsed: dict[str, dict[str, float]]) -> dict:
    if len(parsed) < 2:
        raise ValueError("Need at least 2 parsed GMF frames.")

    filenames = sorted(parsed.keys())
    pos_y = [parsed[name]["pos_y"] for name in filenames]
    score0 = [parsed[name]["score0"] for name in filenames]
    steps = [pos_y[idx + 1] - pos_y[idx] for idx in range(len(pos_y) - 1)]
    raw_std = std_pop(steps)
    median_step = statistics.median(steps)

    outliers: list[dict] = []
    kept: list[float] = []
    for idx, step in enumerate(steps):
        z = 0.0 if raw_std <= 0 else (step - median_step) / raw_std
        if abs(z) > 5.0:
            outliers.append(
                {
                    "step_index": idx,
                    "frame": f"{filenames[idx]}->{filenames[idx + 1]}",
                    "step": step,
                    "z": z,
                }
            )
        else:
            kept.append(step)

    return {
        "n_frames": len(filenames),
        "n_steps": len(steps),
        "first_filename": filenames[0],
        "last_filename": filenames[-1],
        "median_step": median_step,
        "raw_step_std": raw_std,
        "filtered_step_std": std_pop(kept),
        "n_outliers_removed": len(outliers),
        "outliers": outliers,
        "mean_score0": finite_mean(score0),
    }


def load_cases() -> list[dict[str, str]]:
    with PATHS_TSV.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def write_markdown(payload: dict) -> None:
    lines = [
        "# 20260603 GMF Exploratory Summary",
        "",
        "This is same-sample exploratory evidence only. It is not comparable to the",
        "official three-pitch external GMF baseline numbers.",
        "",
        "| case | frames | raw step std | filtered step std | median step | mean Score0 | missing |",
        "|---|---:|---:|---:|---:|---:|:---:|",
    ]
    for row in payload["cases"]:
        if row["missing_score"]:
            lines.append(
                f"| {row['case']} | - | - | - | - | - | yes |"
            )
            continue
        stats = row["stats"]
        mean_score = stats["mean_score0"]
        mean_score_text = "-" if mean_score is None else f"{mean_score:.3f}"
        lines.append(
            f"| {row['case']} | {stats['n_frames']} | "
            f"{stats['raw_step_std']:.6f} | {stats['filtered_step_std']:.6f} | "
            f"{stats['median_step']:.6f} | {mean_score_text} | no |"
        )
    lines.append("")
    lines.append(
        "Lower step variation can be a useful same-sample signal, but only the "
        "standard pitch-sequence workflow should be used for formal project decisions."
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    cases = []
    missing = []
    for case in load_cases():
        score_path = Path(case["score_folder"]) / "GMF_score.txt"
        row = {
            "case": case["case"],
            "role": case["role"],
            "image_folder": case["image_folder"],
            "score_path": str(score_path),
            "missing_score": not score_path.is_file(),
            "stats": None,
        }
        if row["missing_score"]:
            missing.append(str(score_path))
        else:
            parsed = parse_gmf_score(score_path)
            row["stats"] = compute_stats(parsed)
        cases.append(row)

    payload = {
        "scope": "20260603 same-sample exploratory external GMF analysis",
        "formal_comparable_to_project_baselines": False,
        "method": "step_std over filename-sorted PosY diffs; z > 5 GMF failures removed only if present",
        "cases": cases,
        "missing_scores": missing,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(payload)

    print(json.dumps({
        "summary_json": str(OUT_JSON),
        "summary_md": str(OUT_MD),
        "missing_scores": len(missing),
    }, indent=2, ensure_ascii=False))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
