"""Summarize returned GMF/PM text files without treating missing files as zeros.

The parser intentionally keeps unknown PM formats as ``unparsed`` while still
recording the file and line count.  GMF_score.txt is parsed into frame, X, Y,
score and step statistics when the familiar key/value rows are present.
"""

from __future__ import annotations

import csv
import json
import math
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
MANIFEST = PACKAGE / "bundle_manifest.json"
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
FRAME_RE = re.compile(r"(?:frame|raw|r61v11)[_ -]?(\d{1,6})", re.IGNORECASE)
KEY_VALUE_RE = re.compile(
    rf"(?P<key>FileName|PosX|PosY|CenterX|CenterY|PositionX|PositionY|XPos|YPos|CoordinateX|CoordinateY|Score0|Score1|Score\s*Diff|X|Y)\s*(?:,|=|:|\t|\s+)\s*(?P<value>[^,;\t\s]+)",
    re.IGNORECASE,
)


def resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PACKAGE / path


def number(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_row(line: str) -> dict[str, object]:
    row: dict[str, object] = {}
    for match in KEY_VALUE_RE.finditer(line):
        key = re.sub(r"\s+", "", match.group("key")).lower()
        value = match.group("value").strip().strip('"')
        if key == "filename":
            row["file_name"] = value
            frame_match = FRAME_RE.search(value)
            if frame_match:
                row["frame_index"] = int(frame_match.group(1))
        elif key in {"posx", "centerx", "positionx", "xpos", "coordinatex", "x"} and "x" not in row:
            parsed = number(value)
            if parsed is not None:
                row["x"] = parsed
        elif key in {"posy", "centery", "positiony", "ypos", "coordinatey", "y"} and "y" not in row:
            parsed = number(value)
            if parsed is not None:
                row["y"] = parsed
        elif key in {"score0", "score1", "scorediff"}:
            parsed = number(value)
            if parsed is not None:
                row[key] = parsed
    if "frame_index" not in row:
        frame_match = FRAME_RE.search(line)
        if frame_match:
            row["frame_index"] = int(frame_match.group(1))
    return row


def std(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) >= 2 else None


def linear_residual(values: list[tuple[int, float]]) -> float | None:
    if len(values) < 3:
        return None
    xs = [float(x) for x, _ in values]
    ys = [float(y) for _, y in values]
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
    intercept = mean_y - slope * mean_x
    residuals = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    return math.sqrt(statistics.fmean([v * v for v in residuals]))


def analyze_file(path: Path) -> dict[str, object]:
    lower_name = path.name.lower()
    if lower_name.startswith("raw_") or "_raw_" in lower_name:
        source = "raw"
    elif lower_name.startswith("recon_") or "_recon_" in lower_name:
        source = "recon"
    else:
        source = "unspecified"
    if "pm" in lower_name:
        method = "PM"
    elif "gmf" in lower_name:
        method = "GMF"
    else:
        method = "other"
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError as exc:
        return {"file": path.name, "source": source, "method": method, "state": "unreadable", "error": str(exc)}
    nonempty = [line for line in lines if line.strip()]
    if not nonempty:
        return {"file": path.name, "source": source, "method": method, "state": "empty", "line_count": 0}
    rows = [parse_row(line) for line in nonempty]
    coordinate_rows = [row for row in rows if "x" in row or "y" in row]
    complete_rows = [row for row in coordinate_rows if "x" in row and "y" in row]
    frame_index_inferred = False
    for order, row in enumerate(complete_rows):
        if "frame_index" not in row:
            row["frame_index"] = order
            frame_index_inferred = True
    result: dict[str, object] = {
        "file": path.name,
        "path": str(path),
        "source": source,
        "method": method,
        "state": "parsed" if coordinate_rows else "unparsed",
        "line_count": len(nonempty),
        "coordinate_row_count": len(coordinate_rows),
        "complete_coordinate_row_count": len(complete_rows),
        "frame_index_inferred": frame_index_inferred,
    }
    if complete_rows:
        complete_rows.sort(key=lambda row: int(row["frame_index"]))
        result["frame_indices"] = [row["frame_index"] for row in complete_rows]
        result["duplicate_frame_count"] = len(result["frame_indices"]) - len(set(result["frame_indices"]))
        xs = [float(row["x"]) for row in complete_rows]
        ys = [float(row["y"]) for row in complete_rows]
        result["x_mean"] = statistics.fmean(xs)
        result["y_mean"] = statistics.fmean(ys)
        result["x_step_mean"] = statistics.fmean([b - a for a, b in zip(xs, xs[1:])]) if len(xs) > 1 else None
        result["y_step_mean"] = statistics.fmean([b - a for a, b in zip(ys, ys[1:])]) if len(ys) > 1 else None
        result["x_step_std"] = std([b - a for a, b in zip(xs, xs[1:])]) if len(xs) > 2 else None
        result["y_step_std"] = std([b - a for a, b in zip(ys, ys[1:])]) if len(ys) > 2 else None
        result["x_line_residual_rms"] = linear_residual([(int(row["frame_index"]), float(row["x"])) for row in complete_rows])
        result["y_line_residual_rms"] = linear_residual([(int(row["frame_index"]), float(row["y"])) for row in complete_rows])
    for field in ("score0", "score1", "scorediff"):
        values = [float(row[field]) for row in rows if field in row]
        if values:
            result[f"{field}_mean"] = statistics.fmean(values)
            result[f"{field}_std"] = std(values)
            result[f"{field}_min"] = min(values)
            result[f"{field}_max"] = max(values)
    return result


COMPARISON_METRICS = (
    "complete_coordinate_row_count",
    "x_step_mean",
    "x_step_std",
    "y_step_mean",
    "y_step_std",
    "x_line_residual_rms",
    "y_line_residual_rms",
    "score0_mean",
    "score0_std",
    "scorediff_mean",
)


def build_comparisons(all_models: list[dict[str, object]]) -> list[dict[str, object]]:
    """Pair raw_ and recon_ result files by model and method when both exist."""
    comparisons: list[dict[str, object]] = []
    for model in all_models:
        grouped: dict[str, dict[str, list[dict[str, object]]]] = {}
        for item in model["files"]:
            source = item.get("source")
            if source not in {"raw", "recon"} or item.get("state") in {"empty", "unreadable"}:
                continue
            method = str(item.get("method") or "other")
            grouped.setdefault(method, {"raw": [], "recon": []})[source].append(item)
        for method, sides in sorted(grouped.items()):
            raw_files = sorted(sides["raw"], key=lambda item: str(item.get("file", "")).lower())
            recon_files = sorted(sides["recon"], key=lambda item: str(item.get("file", "")).lower())
            pair_count = min(len(raw_files), len(recon_files))
            if pair_count == 0:
                continue
            for pair_index in range(pair_count):
                raw = raw_files[pair_index]
                recon = recon_files[pair_index]
                comparison: dict[str, object] = {
                    "model": model["model"],
                    "method": method,
                    "pair_index": pair_index,
                    "raw_file": raw.get("file"),
                    "recon_file": recon.get("file"),
                }
                for metric in COMPARISON_METRICS:
                    raw_value = raw.get(metric)
                    recon_value = recon.get(metric)
                    comparison[f"{metric}_raw"] = raw_value
                    comparison[f"{metric}_recon"] = recon_value
                    if isinstance(raw_value, (int, float)) and isinstance(recon_value, (int, float)):
                        comparison[f"{metric}_delta_recon_minus_raw"] = float(recon_value) - float(raw_value)
                    else:
                        comparison[f"{metric}_delta_recon_minus_raw"] = None
                comparisons.append(comparison)
    return comparisons


def main() -> int:
    if not MANIFEST.is_file():
        print(f"missing manifest: {MANIFEST}", file=sys.stderr)
        return 2
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    all_models: list[dict[str, object]] = []
    for entry in manifest.get("models", []):
        model = str(entry["model"])
        folder = resolve(str(entry["txt_out"]))
        files = sorted(
            (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".txt", ".csv", ".tsv", ".json"} and p.name.lower() != "readme.txt"),
            key=lambda p: p.name.lower(),
        ) if folder.is_dir() else []
        analyses = [analyze_file(path) for path in files]
        result_files = [a for a in analyses if a.get("state") not in {"empty", "unreadable"}]
        state = "present" if result_files else "pending"
        all_models.append({"model": model, "txt_out": str(folder), "state": state, "files": analyses})

    comparisons = build_comparisons(all_models)
    report = {
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "package": str(PACKAGE),
        "models": all_models,
        "comparisons": comparisons,
        "interpretation": "pending means no non-empty external result file was found; it is not a zero score.",
    }
    output_dir = PACKAGE / str(manifest.get("analysis", {}).get("output_directory", "analysis"))
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "external_outputs_summary.json"
    csv_path = output_dir / "external_outputs_summary.csv"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["model", "state", "file", "source", "method", "file_state", "line_count", "coordinate_row_count", "complete_coordinate_row_count", "frame_index_inferred", "x_step_mean", "x_step_std", "y_step_mean", "y_step_std", "x_line_residual_rms", "y_line_residual_rms", "score0_mean", "score0_std", "scorediff_mean"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for model in all_models:
            if not model["files"]:
                writer.writerow({"model": model["model"], "state": model["state"]})
            for file_result in model["files"]:
                row = {"model": model["model"], "state": model["state"], "file": file_result.get("file"), "source": file_result.get("source"), "method": file_result.get("method"), "file_state": file_result.get("state")}
                row.update({field: file_result.get(field) for field in fields if field in file_result})
                writer.writerow(row)
    comparison_json_path = output_dir / "external_comparison.json"
    comparison_csv_path = output_dir / "external_comparison.csv"
    comparison_report = {
        "analyzed_at": report["analyzed_at"],
        "package": str(PACKAGE),
        "comparisons": comparisons,
        "interpretation": "delta is recon minus raw; a missing pair is not scored as zero.",
    }
    comparison_json_path.write_text(json.dumps(comparison_report, ensure_ascii=False, indent=2), encoding="utf-8")
    comparison_fields = ["model", "method", "pair_index", "raw_file", "recon_file"]
    for metric in COMPARISON_METRICS:
        comparison_fields.extend([f"{metric}_raw", f"{metric}_recon", f"{metric}_delta_recon_minus_raw"])
    with comparison_csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=comparison_fields)
        writer.writeheader()
        writer.writerows(comparisons)
    print(f"summary: {json_path}")
    print(f"table:   {csv_path}")
    print(f"paired:  {comparison_json_path}")
    for model in all_models:
        files = len(model["files"])
        parsed = sum(1 for item in model["files"] if item.get("state") == "parsed")
        print(f"{model['model']:<10} state={model['state']:<7} files={files} parsed={parsed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
