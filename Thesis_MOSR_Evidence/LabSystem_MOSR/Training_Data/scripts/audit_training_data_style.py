from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import cv2
import numpy as np


IMAGE_EXTS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
SRC_DIR_NAMES = {"src", "source", "input", "lr", "blur"}
LBL_DIR_NAMES = {"lbl", "label", "labels", "gt", "target", "targets", "hr"}
MASK_DIR_NAMES = {"mask", "masks"}


@dataclass(frozen=True)
class PairRecord:
    package: str
    src: Path
    lbl: Path
    mask: Path | None = None
    source: str = "directory"
    role: str = ""
    stage: str = ""


def read_gray(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    return img


def measure_pair_style(src: np.ndarray, lbl: np.ndarray) -> dict[str, float]:
    if src.ndim != 2 or lbl.ndim != 2:
        raise ValueError("measure_pair_style expects 2D grayscale arrays")
    if src.shape != lbl.shape:
        return {
            "shape_match": 0.0,
            "src_mean": float(np.mean(src)),
            "lbl_mean": float(np.mean(lbl)),
            "src_std": float(np.std(src)),
            "lbl_std": float(np.std(lbl)),
            "src_saturation_frac": float(np.mean((src <= 2) | (src >= 253))),
            "lbl_saturation_frac": float(np.mean((lbl <= 2) | (lbl >= 253))),
            "lbl_unique_count": float(len(np.unique(lbl))),
            "mean_abs_diff": math.inf,
            "p95_abs_diff": math.inf,
            "ncc": 0.0,
            "std_ratio": math.inf,
        }

    src_f = src.astype(np.float32)
    lbl_f = lbl.astype(np.float32)
    src_std = float(np.std(src_f))
    lbl_std = float(np.std(lbl_f))
    diff = np.abs(src_f - lbl_f)
    if src_std > 1e-6 and lbl_std > 1e-6:
        ncc = float(np.corrcoef(src_f.reshape(-1), lbl_f.reshape(-1))[0, 1])
    else:
        ncc = 1.0 if float(np.mean(diff)) < 1e-6 else 0.0

    return {
        "shape_match": 1.0,
        "src_mean": float(np.mean(src_f)),
        "lbl_mean": float(np.mean(lbl_f)),
        "src_std": src_std,
        "lbl_std": lbl_std,
        "src_saturation_frac": float(np.mean((src <= 2) | (src >= 253))),
        "lbl_saturation_frac": float(np.mean((lbl <= 2) | (lbl >= 253))),
        "lbl_unique_count": float(len(np.unique(lbl))),
        "mean_abs_diff": float(np.mean(diff)),
        "p95_abs_diff": float(np.percentile(diff, 95)),
        "ncc": ncc,
        "std_ratio": float(lbl_std / max(src_std, 1e-6)),
    }


def classify_pair_style(metrics: dict[str, float]) -> dict[str, Any]:
    flags: list[str] = []
    if metrics["shape_match"] < 0.5:
        flags.append("shape_mismatch")
    if metrics["lbl_saturation_frac"] >= 0.85:
        flags.append("hard_binary_label")
    if metrics["lbl_saturation_frac"] - metrics["src_saturation_frac"] >= 0.35:
        flags.append("label_much_more_saturated_than_src")
    if metrics["ncc"] < 0.25:
        flags.append("low_src_label_correspondence")
    if metrics["mean_abs_diff"] > 55 and metrics["ncc"] < 0.65:
        flags.append("large_src_label_shift")
    if metrics["std_ratio"] > 2.8 or metrics["std_ratio"] < 0.25:
        flags.append("label_contrast_style_jump")

    high_flags = {
        "shape_mismatch",
        "hard_binary_label",
        "low_src_label_correspondence",
        "large_src_label_shift",
    }
    if any(flag in high_flags for flag in flags):
        risk = "high"
    elif flags:
        risk = "medium"
    else:
        risk = "low"
    return {"risk": risk, "flags": flags}


def _iter_images(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
            yield path


def _resolve_path(base: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return base / path


def _first_path(record: dict[str, Any], keys: Iterable[str], base: Path) -> Path | None:
    for key in keys:
        if key in record:
            path = _resolve_path(base, record[key])
            if path is not None:
                return path
    return None


def discover_manifest_pairs(training_root: Path) -> list[PairRecord]:
    records: list[PairRecord] = []
    src_keys = ("package_src", "src", "source", "input", "lr", "blur")
    lbl_keys = ("package_lbl", "lbl", "label", "gt", "target", "hr", "clean")
    mask_keys = ("package_mask", "mask", "reliable_mask")

    for manifest_path in sorted(training_root.rglob("manifest.json")):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        pairs = payload.get("pairs")
        if not isinstance(pairs, list):
            continue
        package = str(manifest_path.parent.relative_to(training_root)).replace("\\", "/")
        for item in pairs:
            if not isinstance(item, dict):
                continue
            src = _first_path(item, src_keys, manifest_path.parent)
            lbl = _first_path(item, lbl_keys, manifest_path.parent)
            if src is None or lbl is None:
                continue
            mask = _first_path(item, mask_keys, manifest_path.parent)
            records.append(
                PairRecord(
                    package=package,
                    src=src,
                    lbl=lbl,
                    mask=mask,
                    source="manifest",
                    role=str(item.get("role", "")),
                    stage=str(item.get("stage", "")),
                )
            )
    return records


def _relative_image_map(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    if not root.exists():
        return result
    for path in _iter_images(root):
        rel = path.relative_to(root)
        key = str(rel.with_suffix("")).replace("\\", "/")
        result[key] = path
    return result


def discover_sibling_pairs(training_root: Path) -> list[PairRecord]:
    records: list[PairRecord] = []
    for src_dir in sorted(p for p in training_root.rglob("*") if p.is_dir() and p.name.lower() in SRC_DIR_NAMES):
        parent = src_dir.parent
        lbl_dir = next(
            (parent / name for name in ("lbl", "label", "labels", "gt", "target", "hr") if (parent / name).is_dir()),
            None,
        )
        if lbl_dir is None:
            continue
        mask_dir = next((parent / name for name in ("mask", "masks") if (parent / name).is_dir()), None)
        src_map = _relative_image_map(src_dir)
        lbl_map = _relative_image_map(lbl_dir)
        mask_map = _relative_image_map(mask_dir) if mask_dir is not None else {}
        package = str(parent.relative_to(training_root)).replace("\\", "/")
        for key, src in src_map.items():
            lbl = lbl_map.get(key)
            if lbl is None:
                continue
            records.append(
                PairRecord(
                    package=package,
                    src=src,
                    lbl=lbl,
                    mask=mask_map.get(key),
                    source="directory",
                    stage=Path(key).parts[0] if len(Path(key).parts) > 1 else "",
                )
            )

    legacy_src = training_root / "tra_src_ring"
    legacy_lbl = training_root / "tra_lbl_ring"
    if legacy_src.is_dir() and legacy_lbl.is_dir():
        src_map = _relative_image_map(legacy_src)
        lbl_map = _relative_image_map(legacy_lbl)
        for key, src in src_map.items():
            lbl = lbl_map.get(key)
            if lbl is not None:
                records.append(PairRecord("tra_ring", src, lbl, source="legacy_ring"))
    return records


def discover_generated_pairs(training_root: Path) -> list[PairRecord]:
    records: list[PairRecord] = []
    clean_root = training_root / "generated"
    for source_name, package_name in (
        ("generated_convolved", "foundation_bads_psf"),
        ("generated_convolved_gaussian_control", "foundation_gaussian_control"),
    ):
        source_root = training_root / source_name
        if not clean_root.is_dir() or not source_root.is_dir():
            continue
        src_map = _relative_image_map(source_root)
        lbl_map = _relative_image_map(clean_root)
        for key, src in src_map.items():
            lbl = lbl_map.get(key)
            if lbl is None:
                continue
            records.append(
                PairRecord(
                    package=package_name,
                    src=src,
                    lbl=lbl,
                    source=source_name,
                    stage=Path(key).parts[0] if len(Path(key).parts) > 1 else "",
                )
            )
    return records


def discover_pairs(training_root: Path) -> list[PairRecord]:
    all_records = (
        discover_manifest_pairs(training_root)
        + discover_sibling_pairs(training_root)
        + discover_generated_pairs(training_root)
    )
    deduped: dict[tuple[str, str, str], PairRecord] = {}
    for record in all_records:
        key = (record.package, str(record.src.resolve()), str(record.lbl.resolve()))
        deduped[key] = record
    return list(deduped.values())


def _sample_records(records: list[PairRecord], max_per_package: int, seed: int) -> list[PairRecord]:
    if max_per_package <= 0:
        return records
    rng = random.Random(seed)
    by_package: dict[str, list[PairRecord]] = {}
    for record in records:
        by_package.setdefault(record.package, []).append(record)
    sampled: list[PairRecord] = []
    for package_records in by_package.values():
        if len(package_records) <= max_per_package:
            sampled.extend(package_records)
        else:
            sampled.extend(rng.sample(package_records, max_per_package))
    return sampled


def audit_records(records: list[PairRecord], max_per_package: int, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sampled = _sample_records(records, max_per_package=max_per_package, seed=seed)
    sample_rows: list[dict[str, Any]] = []
    for record in sampled:
        row: dict[str, Any] = {
            "package": record.package,
            "source": record.source,
            "role": record.role,
            "stage": record.stage,
            "src": str(record.src),
            "lbl": str(record.lbl),
            "mask": str(record.mask) if record.mask else "",
        }
        try:
            src = read_gray(record.src)
            lbl = read_gray(record.lbl)
            metrics = measure_pair_style(src, lbl)
            verdict = classify_pair_style(metrics)
            row.update(metrics)
            row["risk"] = verdict["risk"]
            row["flags"] = ";".join(verdict["flags"])
        except Exception as exc:
            row["shape_match"] = 0.0
            row["risk"] = "high"
            row["flags"] = f"read_error:{exc}"
        sample_rows.append(row)

    package_rows: list[dict[str, Any]] = []
    by_package: dict[str, list[PairRecord]] = {}
    by_package_sample: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_package.setdefault(record.package, []).append(record)
    for row in sample_rows:
        by_package_sample.setdefault(str(row["package"]), []).append(row)

    for package, package_records in sorted(by_package.items()):
        rows = by_package_sample.get(package, [])
        counts = {"high": 0, "medium": 0, "low": 0}
        for row in rows:
            counts[str(row.get("risk", "high"))] = counts.get(str(row.get("risk", "high")), 0) + 1
        numeric_keys = [
            "src_saturation_frac",
            "lbl_saturation_frac",
            "mean_abs_diff",
            "p95_abs_diff",
            "ncc",
            "std_ratio",
            "lbl_unique_count",
        ]
        summary = {
            "package": package,
            "pair_count": len(package_records),
            "sampled_count": len(rows),
            "high_risk_samples": counts["high"],
            "medium_risk_samples": counts["medium"],
            "low_risk_samples": counts["low"],
            "high_risk_frac": counts["high"] / max(len(rows), 1),
            "problem_samples": counts["high"] + counts["medium"],
            "problem_frac": (counts["high"] + counts["medium"]) / max(len(rows), 1),
        }
        for key in numeric_keys:
            vals = [float(row[key]) for row in rows if key in row and math.isfinite(float(row[key]))]
            summary[f"mean_{key}"] = float(np.mean(vals)) if vals else math.nan
        all_flags = sorted({flag for row in rows for flag in str(row.get("flags", "")).split(";") if flag})
        summary["flags"] = ";".join(all_flags)
        package_rows.append(summary)
    return package_rows, sample_rows


def _normalize_for_tile(img: np.ndarray) -> np.ndarray:
    if img.ndim != 2:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_GRAY2BGR)


def make_contact_sheet(sample_rows: list[dict[str, Any]], out_path: Path, limit: int = 24) -> None:
    chosen = sorted(
        sample_rows,
        key=lambda row: (
            0 if row.get("risk") == "high" else 1 if row.get("risk") == "medium" else 2,
            -float(row.get("lbl_saturation_frac", 0) or 0),
            -float(row.get("mean_abs_diff", 0) or 0),
        ),
    )[:limit]
    if not chosen:
        return
    tile_h, tile_w = 160, 160
    label_h = 34
    rows: list[np.ndarray] = []
    for row in chosen:
        try:
            src = read_gray(Path(str(row["src"])))
            lbl = read_gray(Path(str(row["lbl"])))
            if src.shape == lbl.shape:
                diff = np.clip(np.abs(src.astype(np.int16) - lbl.astype(np.int16)), 0, 255).astype(np.uint8)
            else:
                diff = np.zeros_like(src)
            tiles = []
            for name, img in (("src", src), ("lbl", lbl), ("diff", diff)):
                tile = cv2.resize(_normalize_for_tile(img), (tile_w, tile_h), interpolation=cv2.INTER_AREA)
                cv2.putText(tile, name, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
                tiles.append(tile)
            panel = np.concatenate(tiles, axis=1)
            caption = np.full((label_h, panel.shape[1], 3), 245, dtype=np.uint8)
            text = f"{row['risk']} {row['package'][:52]} {str(row.get('flags',''))[:55]}"
            cv2.putText(caption, text, (5, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1, cv2.LINE_AA)
            rows.append(np.concatenate([caption, panel], axis=0))
        except Exception:
            continue
    if rows:
        sheet = np.concatenate(rows, axis=0)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), sheet)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, package_rows: list[dict[str, Any]], sample_rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    high_packages = [row for row in package_rows if float(row["high_risk_frac"]) >= 0.1 or float(row["problem_frac"]) >= 0.25]
    medium_packages = [
        row
        for row in package_rows
        if row not in high_packages and (int(row["high_risk_samples"]) > 0 or int(row["medium_risk_samples"]) > 0)
    ]
    lines = [
        "# Lab Training Data Style Audit",
        "",
        f"- training_root: `{args.training_root}`",
        f"- sample_per_package: `{args.sample_per_package}` (`0` means all pairs)",
        f"- discovered_packages: `{len(package_rows)}`",
        f"- discovered_pairs: `{sum(int(row['pair_count']) for row in package_rows)}`",
        f"- sampled_pairs: `{len(sample_rows)}`",
        "",
        "## Verdict",
        "",
    ]
    if high_packages:
        lines.append("Risky packages exist. These packages should not be used as-is for the next Lab model.")
    else:
        lines.append("No package crossed the risky-package threshold in this audit.")
    lines += [
        "",
        "## High-Risk Packages",
        "",
        "| package | pairs | sampled | high | medium | problem frac | mean lbl saturation | flags |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in sorted(high_packages, key=lambda r: (-float(r["high_risk_frac"]), str(r["package"]))):
        lines.append(
            f"| `{row['package']}` | {row['pair_count']} | {row['sampled_count']} | "
            f"{row['high_risk_samples']} | {row['medium_risk_samples']} | {float(row['problem_frac']):.3f} | "
            f"{float(row['mean_lbl_saturation_frac']):.3f} | `{row['flags']}` |"
        )
    if not high_packages:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 |  |")
    lines += [
        "",
        "## Medium / Mixed Packages",
        "",
        "| package | pairs | sampled | high | medium | low | flags |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in sorted(medium_packages, key=lambda r: (-int(r["high_risk_samples"]), -int(r["medium_risk_samples"]), str(r["package"]))):
        lines.append(
            f"| `{row['package']}` | {row['pair_count']} | {row['sampled_count']} | "
            f"{row['high_risk_samples']} | {row['medium_risk_samples']} | {row['low_risk_samples']} | `{row['flags']}` |"
        )
    if not medium_packages:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 |  |")
    lines += [
        "",
        "## Files",
        "",
        "- package summary: `package_style_summary.csv`",
        "- sampled pair metrics: `pair_style_sample_metrics.csv`",
        "- worst-case visual sheet: `worst_style_contact_sheet.png`",
        "",
        "## Audit Rules",
        "",
        "- High risk: label is hard binary/CAD-like, has very weak source-label correspondence, or shape/read errors.",
        "- Medium risk: label contrast/saturation differs strongly from source, but not enough to prove a broken pair.",
        "- Low risk: label keeps a source-like grayscale style under these checks.",
        "- Package is listed as risky when high-risk samples exceed 10% or high+medium samples exceed 25%.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    here = Path(__file__).resolve()
    default_root = here.parents[1]
    default_out = default_root.parent / "Reconstruct_Progress" / "20260617_training_data_style_audit"
    parser = argparse.ArgumentParser(description="Audit Lab training src/label style and correspondence.")
    parser.add_argument("--training-root", type=Path, default=default_root)
    parser.add_argument("--output-dir", type=Path, default=default_out)
    parser.add_argument("--sample-per-package", type=int, default=160, help="0 means audit every discovered pair.")
    parser.add_argument("--seed", type=int, default=20260617)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    training_root = args.training_root.resolve()
    output_dir = args.output_dir.resolve()
    records = discover_pairs(training_root)
    package_rows, sample_rows = audit_records(records, max_per_package=args.sample_per_package, seed=args.seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "package_style_summary.csv", package_rows)
    write_csv(output_dir / "pair_style_sample_metrics.csv", sample_rows)
    unsafe_rows = [row for row in sample_rows if row.get("risk") != "low"]
    write_csv(output_dir / "unsafe_pair_list.csv", unsafe_rows)
    (output_dir / "package_style_summary.json").write_text(json.dumps(package_rows, indent=2), encoding="utf-8")
    (output_dir / "pair_style_sample_metrics.json").write_text(json.dumps(sample_rows, indent=2), encoding="utf-8")
    (output_dir / "unsafe_pair_list.json").write_text(json.dumps(unsafe_rows, indent=2), encoding="utf-8")
    make_contact_sheet(sample_rows, output_dir / "worst_style_contact_sheet.png")
    write_report(output_dir / "TRAINING_DATA_STYLE_AUDIT.md", package_rows, sample_rows, args)
    print(json.dumps({
        "training_root": str(training_root),
        "output_dir": str(output_dir),
        "packages": len(package_rows),
        "pairs": len(records),
        "sampled_pairs": len(sample_rows),
        "unsafe_pairs": len(unsafe_rows),
        "high_risk_packages": sum(1 for row in package_rows if float(row["high_risk_frac"]) >= 0.5),
    }, indent=2))


if __name__ == "__main__":
    main()
