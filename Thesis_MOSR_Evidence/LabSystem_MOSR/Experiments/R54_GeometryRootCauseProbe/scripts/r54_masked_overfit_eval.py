"""Evaluate R54 masked-overfit reconstructions against masked CAD labels."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import cv2
import numpy as np


EXPERIMENT_ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PACKAGE_DIR = LAB_ROOT / "Training_Data" / "r54_geometry_root_cause_probe" / "r54_masked_small_overfit_train"
DEFAULT_OUTPUT_DIR = EXPERIMENT_ROOT / "results" / "masked_overfit_probe"


def _read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"failed to read image: {path}")
    return image


def _write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise RuntimeError(f"failed to encode image: {path}")
    path.write_bytes(encoded.tobytes())


def _mae(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> float:
    if int(np.count_nonzero(mask)) == 0:
        return math.nan
    diff = np.abs(a.astype(np.float32) - b.astype(np.float32))
    return float(diff[mask].mean())


def _pct_improvement(before: float, after: float) -> float:
    if math.isnan(before) or math.isnan(after) or before <= 1e-12:
        return math.nan
    return float((before - after) / before * 100.0)


def masked_metrics(src: np.ndarray, lbl: np.ndarray, mask: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    if src.shape != lbl.shape or src.shape != mask.shape or src.shape != pred.shape:
        raise ValueError(
            f"shape mismatch: src={src.shape}, lbl={lbl.shape}, mask={mask.shape}, pred={pred.shape}"
        )
    inside = mask > 0
    outside = ~inside
    inside_input = _mae(src, lbl, inside)
    inside_pred = _mae(pred, lbl, inside)
    outside_pred = _mae(pred, src, outside)
    full_pred = float(np.abs(pred.astype(np.float32) - lbl.astype(np.float32)).mean())
    return {
        "inside_mae_input_to_label": inside_input,
        "inside_mae_to_label": inside_pred,
        "inside_improvement_vs_input_pct": _pct_improvement(inside_input, inside_pred),
        "outside_mae_to_source": outside_pred,
        "full_mae_to_label": full_pred,
        "trusted_pixel_count": float(np.count_nonzero(inside)),
        "outside_pixel_count": float(np.count_nonzero(outside)),
    }


def _load_manifest(package_dir: Path) -> dict:
    return json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))


def _mean(values: list[float]) -> float:
    clean = [float(v) for v in values if not math.isnan(float(v))]
    if not clean:
        return math.nan
    return float(np.mean(clean))


def _median(values: list[float]) -> float:
    clean = [float(v) for v in values if not math.isnan(float(v))]
    if not clean:
        return math.nan
    return float(np.median(clean))


def evaluate_case(
    package_dir: Path | str,
    case: str,
    recon_dir: Path | str | None = None,
    *,
    source_as_prediction: bool = False,
) -> dict[str, object]:
    root = Path(package_dir)
    manifest = _load_manifest(root)
    records = list(manifest.get("pairs", []))
    detail_rows: list[dict[str, object]] = []
    missing: list[str] = []
    for record in records:
        src_path = root / str(record["package_src"])
        lbl_path = root / str(record["package_lbl"])
        mask_path = root / str(record["package_mask"])
        src = _read_gray(src_path)
        lbl = _read_gray(lbl_path)
        mask = _read_gray(mask_path)
        if source_as_prediction:
            pred = src
            pred_path = src_path
        else:
            assert recon_dir is not None
            pred_path = Path(recon_dir) / Path(str(record["package_src"])).name
            if not pred_path.exists():
                missing.append(str(pred_path))
                continue
            pred = _read_gray(pred_path)
        metrics = masked_metrics(src, lbl, mask, pred)
        detail_rows.append(
            {
                "case": case,
                "file": Path(str(record["package_src"])).name,
                "pair_id": record.get("pair_id", ""),
                "patch_index": record.get("patch_index", ""),
                "prediction": str(pred_path),
                **metrics,
            }
        )

    summary = {
        "case": case,
        "recon_dir": "" if recon_dir is None else str(Path(recon_dir)),
        "image_count": len(detail_rows),
        "missing_count": len(missing),
        "missing_files": missing[:20],
        "inside_mae_to_label_mean": _mean([float(r["inside_mae_to_label"]) for r in detail_rows]),
        "inside_mae_to_label_median": _median([float(r["inside_mae_to_label"]) for r in detail_rows]),
        "inside_mae_input_to_label_mean": _mean([float(r["inside_mae_input_to_label"]) for r in detail_rows]),
        "inside_improvement_vs_input_pct_mean": _mean(
            [float(r["inside_improvement_vs_input_pct"]) for r in detail_rows]
        ),
        "outside_mae_to_source_mean": _mean([float(r["outside_mae_to_source"]) for r in detail_rows]),
        "full_mae_to_label_mean": _mean([float(r["full_mae_to_label"]) for r in detail_rows]),
        "details": detail_rows,
    }
    return summary


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
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


def _parse_case_arg(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("case must be NAME=PATH")
    name, path = value.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("case name is empty")
    return name, Path(path)


def evaluate_cases(
    package_dir: Path | str,
    cases: list[tuple[str, Path]],
    *,
    include_source: bool = True,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    summaries: list[dict[str, object]] = []
    details: list[dict[str, object]] = []
    if include_source:
        src_summary = evaluate_case(package_dir, "input_source", None, source_as_prediction=True)
        details.extend(src_summary.pop("details"))
        summaries.append(src_summary)
    for case, path in cases:
        summary = evaluate_case(package_dir, case, path)
        details.extend(summary.pop("details"))
        summaries.append(summary)
    return summaries, details


def create_contact_sheet(
    package_dir: Path | str,
    cases: list[tuple[str, Path]],
    output_path: Path | str,
    *,
    max_items: int = 8,
    tile_size: int = 148,
) -> dict[str, object]:
    root = Path(package_dir)
    manifest = _load_manifest(root)
    records = list(manifest.get("pairs", []))[: int(max_items)]
    headers = ["src", "label", "mask", *[name for name, _ in cases]]
    rows = []
    for record in records:
        images = [
            _read_gray(root / str(record["package_src"])),
            _read_gray(root / str(record["package_lbl"])),
            _read_gray(root / str(record["package_mask"])),
        ]
        file_name = Path(str(record["package_src"])).name
        for _, recon_dir in cases:
            images.append(_read_gray(Path(recon_dir) / file_name))
        tiles = []
        for header, img in zip(headers, images):
            tile = cv2.resize(img, (tile_size, tile_size), interpolation=cv2.INTER_AREA)
            tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
            cv2.putText(tile, header[:18], (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1, cv2.LINE_AA)
            tiles.append(tile)
        row = np.concatenate(tiles, axis=1)
        cv2.putText(
            row,
            file_name[:36],
            (5, tile_size - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
        rows.append(row)
    sheet = np.concatenate(rows, axis=0)
    out = Path(output_path)
    _write_image(out, sheet)
    return {"contact_sheet": str(out), "rows": len(rows), "columns": len(headers)}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate R54 masked overfit reconstructions.")
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--case", action="append", type=_parse_case_arg, default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--summary-csv", type=Path, default=None)
    parser.add_argument("--details-csv", type=Path, default=None)
    parser.add_argument("--summary-json", type=Path, default=None)
    parser.add_argument("--contact-sheet", type=Path, default=None)
    parser.add_argument("--max-preview-items", type=int, default=8)
    parser.add_argument("--no-source-case", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    out_dir = Path(args.output_dir)
    summary_csv = args.summary_csv or out_dir / "r54_masked_overfit_eval_summary.csv"
    details_csv = args.details_csv or out_dir / "r54_masked_overfit_eval_details.csv"
    summary_json = args.summary_json or out_dir / "r54_masked_overfit_eval_summary.json"
    contact_sheet = args.contact_sheet or out_dir / "r54_masked_overfit_eval_contact_sheet.png"

    summaries, details = evaluate_cases(args.package_dir, args.case, include_source=not args.no_source_case)
    _write_csv(summary_csv, summaries)
    _write_csv(details_csv, details)
    payload = {"package_dir": str(args.package_dir), "summaries": summaries}
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    summary_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    preview = create_contact_sheet(args.package_dir, args.case, contact_sheet, max_items=args.max_preview_items)

    print(json.dumps({"summary_csv": str(summary_csv), "details_csv": str(details_csv), "summary_json": str(summary_json), **preview, "summaries": summaries}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
