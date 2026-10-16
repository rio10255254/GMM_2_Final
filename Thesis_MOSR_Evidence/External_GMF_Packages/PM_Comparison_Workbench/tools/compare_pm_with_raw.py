"""Compare the supplied raw PM result with each model's PM result.

The package's model txt_out files are treated as reconstruction results unless
their names explicitly contain ``raw_``.  The raw reference is never copied or
modified; its path is recorded in the generated report.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path

from analyze_outputs import linear_residual, parse_row


PACKAGE = Path(__file__).resolve().parents[1]
DEFAULT_RAW = PACKAGE / "reference" / "raw" / "PM_score.txt"
TEXT_SUFFIXES = {".txt", ".csv", ".tsv", ".json"}


def rows(path: Path) -> list[dict[str, object]]:
    parsed: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        item = parse_row(line)
        if "x" in item and "y" in item:
            parsed.append(item)
    for order, item in enumerate(parsed):
        item.setdefault("frame_index", order)
    parsed.sort(key=lambda item: int(item["frame_index"]))
    return parsed


def safe_std(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) >= 2 else None


def metrics(items: list[dict[str, object]]) -> dict[str, object]:
    if not items:
        return {"rows": 0}
    xs = [float(item["x"]) for item in items]
    ys = [float(item["y"]) for item in items]
    x_steps = [b - a for a, b in zip(xs, xs[1:])]
    y_steps = [b - a for a, b in zip(ys, ys[1:])]
    scores = [float(item["score0"]) for item in items if "score0" in item]
    result: dict[str, object] = {
        "rows": len(items),
        "first_frame": int(items[0]["frame_index"]),
        "last_frame": int(items[-1]["frame_index"]),
        "x_mean": statistics.fmean(xs),
        "y_mean": statistics.fmean(ys),
        "x_step_mean": statistics.fmean(x_steps) if x_steps else None,
        "x_step_std": safe_std(x_steps),
        "y_step_mean": statistics.fmean(y_steps) if y_steps else None,
        "y_step_std": safe_std(y_steps),
        "x_line_residual_rms": linear_residual([(int(item["frame_index"]), float(item["x"])) for item in items]),
        "y_line_residual_rms": linear_residual([(int(item["frame_index"]), float(item["y"])) for item in items]),
        "total_dx": xs[-1] - xs[0],
        "total_dy": ys[-1] - ys[0],
        "score0_mean": statistics.fmean(scores) if scores else None,
        "score0_std": safe_std(scores),
    }
    return result


def delta(a: object, b: object) -> float | None:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(b) - float(a)
    return None


def compare(raw: list[dict[str, object]], recon: list[dict[str, object]]) -> dict[str, object]:
    raw_by = {int(item["frame_index"]): item for item in raw}
    recon_by = {int(item["frame_index"]): item for item in recon}
    common = sorted(set(raw_by) & set(recon_by))
    raw_metrics = metrics(raw)
    recon_metrics = metrics(recon)
    coordinate_dx = [float(recon_by[index]["x"]) - float(raw_by[index]["x"]) for index in common]
    coordinate_dy = [float(recon_by[index]["y"]) - float(raw_by[index]["y"]) for index in common]
    step_indices = [index for index in common if index + 1 in raw_by and index + 1 in recon_by]
    raw_x_steps = [float(raw_by[index + 1]["x"]) - float(raw_by[index]["x"]) for index in step_indices]
    recon_x_steps = [float(recon_by[index + 1]["x"]) - float(recon_by[index]["x"]) for index in step_indices]
    raw_y_steps = [float(raw_by[index + 1]["y"]) - float(raw_by[index]["y"]) for index in step_indices]
    recon_y_steps = [float(recon_by[index + 1]["y"]) - float(recon_by[index]["y"]) for index in step_indices]
    return {
        "raw": raw_metrics,
        "recon": recon_metrics,
        "delta_recon_minus_raw": {
            "rows_common": len(common),
            "x_step_mean": delta(raw_metrics.get("x_step_mean"), recon_metrics.get("x_step_mean")),
            "x_step_std": delta(raw_metrics.get("x_step_std"), recon_metrics.get("x_step_std")),
            "y_step_mean": delta(raw_metrics.get("y_step_mean"), recon_metrics.get("y_step_mean")),
            "y_step_std": delta(raw_metrics.get("y_step_std"), recon_metrics.get("y_step_std")),
            "x_line_residual_rms": delta(raw_metrics.get("x_line_residual_rms"), recon_metrics.get("x_line_residual_rms")),
            "y_line_residual_rms": delta(raw_metrics.get("y_line_residual_rms"), recon_metrics.get("y_line_residual_rms")),
            "score0_mean": delta(raw_metrics.get("score0_mean"), recon_metrics.get("score0_mean")),
            "score0_std": delta(raw_metrics.get("score0_std"), recon_metrics.get("score0_std")),
            "x_coordinate_bias": statistics.fmean(coordinate_dx) if coordinate_dx else None,
            "x_coordinate_abs_mean": statistics.fmean([abs(value) for value in coordinate_dx]) if coordinate_dx else None,
            "x_coordinate_rmse": math.sqrt(statistics.fmean([value * value for value in coordinate_dx])) if coordinate_dx else None,
            "x_coordinate_std_after_bias": safe_std(coordinate_dx),
            "y_coordinate_bias": statistics.fmean(coordinate_dy) if coordinate_dy else None,
            "y_coordinate_abs_mean": statistics.fmean([abs(value) for value in coordinate_dy]) if coordinate_dy else None,
            "y_coordinate_rmse": math.sqrt(statistics.fmean([value * value for value in coordinate_dy])) if coordinate_dy else None,
            "y_coordinate_std_after_bias": safe_std(coordinate_dy),
            "x_step_rmse": math.sqrt(statistics.fmean([(a - b) ** 2 for a, b in zip(raw_x_steps, recon_x_steps)])) if raw_x_steps else None,
            "y_step_rmse": math.sqrt(statistics.fmean([(a - b) ** 2 for a, b in zip(raw_y_steps, recon_y_steps)])) if raw_y_steps else None,
        },
    }


def choose_result_file(folder: Path) -> Path | None:
    files = sorted(
        (item for item in folder.iterdir() if item.is_file() and item.suffix.lower() in TEXT_SUFFIXES and item.name.lower() != "readme.txt" and item.stat().st_size > 0),
        key=lambda item: item.name.lower(),
    ) if folder.is_dir() else []
    recon_files = [item for item in files if not (item.name.lower().startswith("raw_") or "_raw_" in item.name.lower())]
    return (recon_files or files or [None])[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW, help="raw PM text file")
    parser.add_argument("--package", type=Path, default=PACKAGE, help="comparison package root")
    args = parser.parse_args()
    raw_path = args.raw.resolve()
    package = args.package.resolve()
    if not raw_path.is_file():
        parser.error(f"raw result not found: {raw_path}")
    manifest_path = package / "bundle_manifest.json"
    if not manifest_path.is_file():
        parser.error(f"bundle manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_rows = rows(raw_path)
    entries: list[dict[str, object]] = []
    for entry in manifest.get("models", []):
        model = str(entry["model"])
        folder_value = str(entry["txt_out"])
        folder = Path(folder_value)
        if not folder.is_absolute():
            folder = package / folder
        result_path = choose_result_file(folder)
        if result_path is None:
            entries.append({"model": model, "state": "pending", "txt_out": str(folder)})
            continue
        recon_rows = rows(result_path)
        item = compare(raw_rows, recon_rows)
        item.update({"model": model, "state": "parsed", "result_file": str(result_path)})
        entries.append(item)
    output_dir = package / str(manifest.get("analysis", {}).get("output_directory", "analysis"))
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "analyzed_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "package": str(package),
        "raw_reference": str(raw_path),
        "raw_reference_rows": len(raw_rows),
        "assumption": "Each model's non-empty txt_out result is treated as recon unless its filename contains raw_.",
        "models": entries,
    }
    json_path = output_dir / "pm_raw_vs_recon_comparison.json"
    csv_path = output_dir / "pm_raw_vs_recon_comparison.csv"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["model", "state", "result_file", "raw_rows", "recon_rows", "common_rows", "raw_y_step_mean", "recon_y_step_mean", "delta_y_step_mean", "raw_y_step_std", "recon_y_step_std", "delta_y_step_std", "raw_y_line_rms", "recon_y_line_rms", "delta_y_line_rms", "raw_score_mean", "recon_score_mean", "delta_score_mean", "x_coordinate_bias", "x_coordinate_std_after_bias", "y_coordinate_bias", "y_coordinate_std_after_bias", "x_coordinate_rmse", "y_coordinate_rmse", "x_step_rmse", "y_step_rmse"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in entries:
            if item.get("state") != "parsed":
                writer.writerow({"model": item["model"], "state": item["state"], "result_file": item.get("txt_out")})
                continue
            raw_metrics = item["raw"]
            recon_metrics = item["recon"]
            deltas = item["delta_recon_minus_raw"]
            writer.writerow({
                "model": item["model"],
                "state": item["state"],
                "result_file": item["result_file"],
                "raw_rows": raw_metrics.get("rows"),
                "recon_rows": recon_metrics.get("rows"),
                "common_rows": deltas.get("rows_common"),
                "raw_y_step_mean": raw_metrics.get("y_step_mean"),
                "recon_y_step_mean": recon_metrics.get("y_step_mean"),
                "delta_y_step_mean": deltas.get("y_step_mean"),
                "raw_y_step_std": raw_metrics.get("y_step_std"),
                "recon_y_step_std": recon_metrics.get("y_step_std"),
                "delta_y_step_std": deltas.get("y_step_std"),
                "raw_y_line_rms": raw_metrics.get("y_line_residual_rms"),
                "recon_y_line_rms": recon_metrics.get("y_line_residual_rms"),
                "delta_y_line_rms": deltas.get("y_line_residual_rms"),
                "raw_score_mean": raw_metrics.get("score0_mean"),
                "recon_score_mean": recon_metrics.get("score0_mean"),
                "delta_score_mean": deltas.get("score0_mean"),
                "x_coordinate_bias": deltas.get("x_coordinate_bias"),
                "x_coordinate_std_after_bias": deltas.get("x_coordinate_std_after_bias"),
                "y_coordinate_bias": deltas.get("y_coordinate_bias"),
                "y_coordinate_std_after_bias": deltas.get("y_coordinate_std_after_bias"),
                "x_coordinate_rmse": deltas.get("x_coordinate_rmse"),
                "y_coordinate_rmse": deltas.get("y_coordinate_rmse"),
                "x_step_rmse": deltas.get("x_step_rmse"),
                "y_step_rmse": deltas.get("y_step_rmse"),
            })
    print(f"raw reference: {raw_path}")
    print(f"comparison:    {json_path}")
    print(f"table:         {csv_path}")
    for item in entries:
        if item.get("state") != "parsed":
            print(f"{item['model']:<10} pending")
            continue
        delta_values = item["delta_recon_minus_raw"]
        print(f"{item['model']:<10} rows={item['recon']['rows']:3} y_std={item['recon'].get('y_step_std'):.6f} score={item['recon'].get('score0_mean'):.4f} dy_rmse={delta_values.get('y_coordinate_rmse'):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
