from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


LAB_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_ROOT = LAB_ROOT / "Training_Data" / "r55_source_style_rebuild" / "r53_realistic_dataset_calibration"
DEFAULT_OUTPUT_ROOT = LAB_ROOT / "Training_Data" / "r56_label_core_repair" / "r53_realistic_dataset_calibration"
DEFAULT_PACKAGES = (
    DEFAULT_INPUT_ROOT / "r53_realistic_calibrated_train_6000",
    DEFAULT_INPUT_ROOT / "r53_realistic_calibrated_val",
)


def read_gray(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Could not read image: {path}")
    return img


def write_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".bmp", image)
    if not ok:
        raise ValueError(f"Could not encode image: {path}")
    path.write_bytes(encoded.tobytes())


def _safe_remove_tree(path: Path) -> None:
    resolved = path.resolve()
    text = str(resolved).lower()
    if "r56_label_core_repair" not in text and "label_core" not in resolved.name.lower():
        raise ValueError(f"refusing to remove a non-label-core output directory: {resolved}")
    if resolved.anchor == str(resolved):
        raise ValueError(f"refusing to remove drive root: {resolved}")
    shutil.rmtree(resolved)


def _copy_or_link(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def _as_package_path(value: str) -> Path:
    return Path(str(value).replace("\\", "/"))


def _resolve_package_path(package_dir: Path, value: str) -> Path:
    path = _as_package_path(value)
    if path.is_absolute():
        return path
    return package_dir / path


def _resize_like(img: np.ndarray, ref: np.ndarray, interpolation: int = cv2.INTER_NEAREST) -> np.ndarray:
    if img.shape == ref.shape:
        return img
    return cv2.resize(img, (ref.shape[1], ref.shape[0]), interpolation=interpolation)


def edge_grad_p95(img: np.ndarray, band: np.ndarray | None = None) -> float:
    f = img.astype(np.float32)
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(gx, gy)
    if band is not None and np.count_nonzero(band) >= 16:
        vals = grad[band.astype(bool)]
    else:
        threshold = np.percentile(grad, 90)
        vals = grad[grad >= threshold]
    if vals.size == 0:
        return 0.0
    return float(np.percentile(vals, 95))


def edge_grad_score(img: np.ndarray, band: np.ndarray | None = None) -> float:
    f = img.astype(np.float32)
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
    grad = cv2.magnitude(gx, gy)
    if band is not None and np.count_nonzero(band) >= 16:
        vals = grad[band.astype(bool)]
    else:
        threshold = np.percentile(grad, 90)
        vals = grad[grad >= threshold]
    if vals.size == 0:
        return 0.0
    # Sparse CAD/checkboard edges can occupy much less than 5% of a masked
    # boundary band. The p99 term keeps those real crisp edges visible to QA.
    return float(max(np.percentile(vals, 95), np.percentile(vals, 99)))


def _edge_from_image(img: np.ndarray) -> np.ndarray:
    gray = np.clip(img, 0, 255).astype(np.uint8)
    if int(gray.max()) - int(gray.min()) < 3:
        return np.zeros_like(gray, dtype=np.uint8)
    edges = cv2.Canny(gray, 30, 90)
    if np.count_nonzero(edges) < 8:
        blur = cv2.GaussianBlur(gray, (0, 0), 0.6)
        gx = cv2.Sobel(blur.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(blur.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(gx, gy)
        thr = max(4.0, float(np.percentile(mag, 88)))
        edges = (mag >= thr).astype(np.uint8) * 255
    return edges


def _edge_alpha(
    anchor: np.ndarray,
    current_lbl: np.ndarray,
    src: np.ndarray,
    mask: np.ndarray | None,
    *,
    radius: int,
) -> tuple[np.ndarray, np.ndarray, str]:
    edge = _edge_from_image(anchor)
    source = "anchor"
    if np.count_nonzero(edge) < 8:
        edge = _edge_from_image(current_lbl)
        source = "current_label"
    if np.count_nonzero(edge) < 8:
        edge = _edge_from_image(src)
        source = "source"

    if mask is not None:
        mask8 = _resize_like(mask, src, cv2.INTER_NEAREST)
        keep = cv2.dilate((mask8 > 0).astype(np.uint8), np.ones((7, 7), np.uint8), iterations=1)
        if np.count_nonzero(edge) < 8:
            edge = _edge_from_image(mask8)
            source = "mask"
        edge = np.where(keep > 0, edge, 0).astype(np.uint8)

    if np.count_nonzero(edge) < 8:
        return np.zeros_like(src, dtype=np.float32), edge.astype(bool), source

    k = max(3, int(radius) * 2 + 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    band = cv2.dilate(edge, kernel)
    alpha = cv2.GaussianBlur(band.astype(np.float32) / 255.0, (0, 0), max(0.65, radius / 2.0))
    alpha = np.clip(alpha, 0.0, 0.96)
    return alpha, edge.astype(bool), source


def _otsu_regions(anchor: np.ndarray) -> np.ndarray | None:
    anchor8 = np.clip(anchor, 0, 255).astype(np.uint8)
    if int(anchor8.max()) - int(anchor8.min()) < 8:
        return None
    _, thresh = cv2.threshold(anchor8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    regions = thresh > 0
    frac = float(np.mean(regions))
    if frac < 0.03 or frac > 0.97:
        return None
    return regions


def _side_values(src: np.ndarray, regions: np.ndarray, edge: np.ndarray) -> tuple[float, float] | None:
    edge_u8 = edge.astype(np.uint8)
    near = cv2.dilate(edge_u8, np.ones((19, 19), np.uint8), iterations=1).astype(bool)
    core = cv2.dilate(edge_u8, np.ones((5, 5), np.uint8), iterations=1).astype(bool)
    sample = near & ~core
    if np.count_nonzero(sample) < 20:
        sample = ~core
    fg = sample & regions
    bg = sample & ~regions
    if np.count_nonzero(fg) < 10 or np.count_nonzero(bg) < 10:
        fg = regions
        bg = ~regions
    if np.count_nonzero(fg) < 10 or np.count_nonzero(bg) < 10:
        return None
    fg_val = float(np.median(src[fg]))
    bg_val = float(np.median(src[bg]))
    if abs(fg_val - bg_val) < 6:
        return None
    return fg_val, bg_val


def make_soft_source_style_label_for_test(src: np.ndarray, structure_label: np.ndarray) -> np.ndarray:
    alpha, _, _ = _edge_alpha(structure_label, src, src, None, radius=4)
    blurred = cv2.GaussianBlur(src.astype(np.float32), (0, 0), 1.1)
    weak = src.astype(np.float32) + 0.45 * (src.astype(np.float32) - blurred)
    out = src.astype(np.float32) * (1.0 - alpha) + weak * alpha
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def repair_label_core(
    src: np.ndarray,
    current_lbl: np.ndarray,
    anchor_lbl: np.ndarray,
    mask: np.ndarray | None = None,
    *,
    edge_radius: int = 5,
) -> tuple[np.ndarray, dict[str, Any]]:
    if src.ndim != 2 or current_lbl.ndim != 2 or anchor_lbl.ndim != 2:
        raise ValueError("repair_label_core expects grayscale 2D arrays")
    current_lbl = _resize_like(current_lbl, src, cv2.INTER_LINEAR)
    anchor_lbl = _resize_like(anchor_lbl, src, cv2.INTER_NEAREST)
    if mask is not None:
        mask = _resize_like(mask, src, cv2.INTER_NEAREST)

    alpha, edge, edge_source = _edge_alpha(anchor_lbl, current_lbl, src, mask, radius=edge_radius)
    before_ratio = edge_grad_score(current_lbl, alpha > 0.08) / max(edge_grad_score(src, alpha > 0.08), 1e-6)
    if float(np.max(alpha)) <= 0.0:
        return current_lbl.copy(), {
            "method": "no_edge",
            "edge_source": edge_source,
            "edge_px": int(np.count_nonzero(edge)),
            "grad_ratio_before": float(before_ratio),
            "grad_ratio_after": float(before_ratio),
        }

    src_f = src.astype(np.float32)
    cur_f = current_lbl.astype(np.float32)
    regions = _otsu_regions(anchor_lbl)
    repaired: np.ndarray
    method = "unsharp_core"
    if regions is not None:
        values = _side_values(src, regions, edge)
    else:
        values = None

    blur = cv2.GaussianBlur(cur_f, (0, 0), 0.95)
    unsharp = np.clip(cur_f + 1.85 * (cur_f - blur), 0, 255)
    unsharp_repaired = cur_f * (1.0 - alpha) + unsharp * alpha
    unsharp_u8 = np.clip(np.rint(unsharp_repaired), 0, 255).astype(np.uint8)
    unsharp_ratio = edge_grad_score(unsharp_u8, alpha > 0.08) / max(edge_grad_score(src, alpha > 0.08), 1e-6)

    if regions is not None and values is not None:
        fg_val, bg_val = values
        crisp = np.where(regions, fg_val, bg_val).astype(np.float32)
        low_src = cv2.GaussianBlur(src_f, (0, 0), 7.0)
        low_cur = cv2.GaussianBlur(cur_f, (0, 0), 7.0)
        illumination = np.clip(low_src - float(np.mean(low_src - low_cur)), -18.0, 18.0)
        crisp = np.clip(crisp + 0.18 * (illumination - np.mean(illumination)), 0, 255)
        repaired = cur_f * (1.0 - alpha) + crisp * alpha
        method = "region_core"
    else:
        repaired = unsharp_repaired

    repaired_u8 = np.clip(np.rint(repaired), 0, 255).astype(np.uint8)
    after_ratio = edge_grad_score(repaired_u8, alpha > 0.08) / max(edge_grad_score(src, alpha > 0.08), 1e-6)
    if unsharp_ratio > after_ratio and after_ratio < max(before_ratio, 1.5):
        repaired_u8 = unsharp_u8
        after_ratio = float(unsharp_ratio)
        method = "unsharp_core"
    return repaired_u8, {
        "method": method,
        "edge_source": edge_source,
        "edge_px": int(np.count_nonzero(edge)),
        "grad_ratio_before": float(before_ratio),
        "grad_ratio_after": float(after_ratio),
    }


def _label_metrics(src: np.ndarray, current_lbl: np.ndarray, anchor_lbl: np.ndarray, mask: np.ndarray | None) -> dict[str, Any]:
    alpha, edge, edge_source = _edge_alpha(anchor_lbl, current_lbl, src, mask, radius=5)
    band = alpha > 0.08
    src_grad = edge_grad_score(src, band)
    lbl_grad = edge_grad_score(current_lbl, band)
    return {
        "edge_source": edge_source,
        "edge_px": int(np.count_nonzero(edge)),
        "grad_ratio": float(lbl_grad / max(src_grad, 1e-6)),
        "src_grad_p95": float(src_grad),
        "lbl_grad_p95": float(lbl_grad),
    }


def _should_repair(record: dict[str, Any], metrics: dict[str, Any], *, grad_ratio_threshold: float) -> tuple[bool, str]:
    reason_parts: list[str] = []
    if bool(record.get("repaired")):
        reason_parts.append("r55_repaired_label")
    repair_reason = str(record.get("repair_reason", "") or "")
    if "cad_anchor" in repair_reason:
        reason_parts.append("cad_anchor_label")
    if float(metrics["edge_px"]) > 0 and float(metrics["grad_ratio"]) < float(grad_ratio_threshold):
        reason_parts.append("soft_label_metric")
    return bool(reason_parts), ";".join(reason_parts)


def _pair_rel(record: dict[str, Any], key: str) -> Path:
    value = record.get(key)
    if not value:
        raise ValueError(f"manifest record missing {key}")
    return _as_package_path(str(value))


def _copy_record_without_geometry(record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    for key in ("geometry_boundary", "geometry_centerline", "geometry_distance"):
        out.pop(key, None)
    return out


def repair_package(
    package_dir: Path,
    output_dir: Path,
    *,
    grad_ratio_threshold: float = 1.5,
    emit_preview: bool = True,
) -> dict[str, Any]:
    package_dir = Path(package_dir).resolve()
    output_dir = Path(output_dir).resolve()
    manifest_path = package_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pairs = list(manifest.get("pairs", []))
    if not pairs:
        raise ValueError(f"manifest contains no pairs: {manifest_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_pairs: list[dict[str, Any]] = []
    metrics_rows: list[dict[str, Any]] = []
    link_counts: Counter[str] = Counter()
    previews: list[tuple[Path, dict[str, Any]]] = []

    for idx, record in enumerate(pairs, start=1):
        src_rel = _pair_rel(record, "package_src")
        lbl_rel = _pair_rel(record, "package_lbl")
        src_path = _resolve_package_path(package_dir, str(src_rel))
        current_lbl_path = _resolve_package_path(package_dir, str(lbl_rel))
        anchor_path = Path(str(record.get("lbl", "")))
        if not anchor_path.exists():
            anchor_path = current_lbl_path
        mask_path: Path | None = None
        for key in ("package_mask", "mask"):
            value = str(record.get(key, "") or "")
            if not value:
                continue
            candidate = _resolve_package_path(package_dir, value) if key == "package_mask" else Path(value)
            if candidate.exists():
                mask_path = candidate
                break

        src = read_gray(src_path)
        current_lbl = read_gray(current_lbl_path)
        anchor_lbl = read_gray(anchor_path)
        mask = read_gray(mask_path) if mask_path is not None else None
        metrics = _label_metrics(src, current_lbl, anchor_lbl, mask)
        repair, reason = _should_repair(record, metrics, grad_ratio_threshold=grad_ratio_threshold)

        out_src = output_dir / src_rel
        out_lbl = output_dir / lbl_rel
        link_counts[_copy_or_link(src_path, out_src)] += 1
        out_record = _copy_record_without_geometry(record)
        out_record["package_src"] = src_rel.as_posix()
        out_record["package_lbl"] = lbl_rel.as_posix()

        if repair:
            fixed, info = repair_label_core(src, current_lbl, anchor_lbl, mask)
            write_image(out_lbl, fixed)
            link_counts["core_repaired_label"] += 1
            out_record.update(
                {
                    "core_repaired": True,
                    "core_repair_reason": reason,
                    "core_repair_method": info["method"],
                    "core_edge_source": info["edge_source"],
                    "core_edge_px": int(info["edge_px"]),
                    "core_grad_ratio_before": float(info["grad_ratio_before"]),
                    "core_grad_ratio_after": float(info["grad_ratio_after"]),
                }
            )
            if len(previews) < 48:
                previews.append((output_dir, {**out_record, "anchor_path": str(anchor_path), "input_package_dir": str(package_dir)}))
        else:
            link_counts[_copy_or_link(current_lbl_path, out_lbl)] += 1
            out_record.update(
                {
                    "core_repaired": False,
                    "core_repair_reason": "",
                    "core_repair_method": "copy",
                    "core_edge_source": metrics["edge_source"],
                    "core_edge_px": int(metrics["edge_px"]),
                    "core_grad_ratio_before": float(metrics["grad_ratio"]),
                    "core_grad_ratio_after": float(metrics["grad_ratio"]),
                }
            )

        package_mask = str(record.get("package_mask", "") or "")
        if package_mask:
            src_mask = _resolve_package_path(package_dir, package_mask)
            dst_mask = output_dir / _as_package_path(package_mask)
            if src_mask.exists():
                link_counts[_copy_or_link(src_mask, dst_mask)] += 1

        metrics_rows.append(
            {
                "idx": idx,
                "stage": str(record.get("stage", "")),
                "package_src": src_rel.as_posix(),
                "core_repaired": bool(out_record["core_repaired"]),
                "core_repair_reason": out_record["core_repair_reason"],
                "core_repair_method": out_record["core_repair_method"],
                "edge_source": out_record["core_edge_source"],
                "edge_px": int(out_record["core_edge_px"]),
                "grad_ratio_before": float(out_record["core_grad_ratio_before"]),
                "grad_ratio_after": float(out_record["core_grad_ratio_after"]),
            }
        )
        out_pairs.append(out_record)

        if idx % 500 == 0:
            print(f"[label-core] {package_dir.name}: {idx}/{len(pairs)}")

    out_manifest = dict(manifest)
    out_manifest["generator"] = "repair_source_style_label_core_v1"
    out_manifest["generated_at"] = datetime.now().isoformat(timespec="seconds")
    out_manifest["source_manifest"] = str(manifest_path)
    out_manifest["source_package_dir"] = str(package_dir)
    out_manifest["output_dir"] = str(output_dir)
    out_manifest["total_pairs"] = len(out_pairs)
    out_manifest["repaired_pairs"] = sum(1 for item in out_pairs if item.get("core_repaired"))
    out_manifest["source_repaired_pairs"] = int(manifest.get("repaired_pairs", 0))
    out_manifest["core_repaired_pairs"] = sum(1 for item in out_pairs if item.get("core_repaired"))
    out_manifest["label_policy"] = (
        "Labels keep source-image grayscale style, but weak repaired labels receive a crisp geometry core "
        "inside edge bands using source-derived region intensities; old CAD/label images locate edges only."
    )
    out_manifest["geometry_sidecars"] = False
    out_manifest["geometry_count"] = 0
    out_manifest.pop("geom_dir", None)
    out_manifest.pop("geometry_generator", None)
    out_manifest.pop("geometry_generated_at", None)
    out_manifest["link_counts"] = dict(link_counts)
    out_manifest["pairs"] = out_pairs
    (output_dir / "manifest.json").write_text(json.dumps(out_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    _write_csv(output_dir / "core_repair_pair_metrics.csv", metrics_rows)
    if emit_preview:
        _make_preview(output_dir, previews)

    return {
        "package": package_dir.name,
        "input_dir": str(package_dir),
        "output_dir": str(output_dir),
        "total_pairs": len(out_pairs),
        "core_repaired_pairs": sum(1 for item in out_pairs if item.get("core_repaired")),
        "min_grad_ratio_after_repaired": _min_after(metrics_rows),
        "link_counts": dict(link_counts),
    }


def _min_after(rows: list[dict[str, Any]]) -> float | None:
    vals = [float(row["grad_ratio_after"]) for row in rows if row.get("core_repaired")]
    return float(min(vals)) if vals else None


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _thumb(img: np.ndarray, size: int = 128) -> np.ndarray:
    h, w = img.shape[:2]
    scale = min(size / max(w, 1), size / max(h, 1))
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    small = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.full((size, size), 245, dtype=np.uint8)
    y = (size - new_h) // 2
    x = (size - new_w) // 2
    canvas[y : y + new_h, x : x + new_w] = small
    return canvas


def _make_preview(output_dir: Path, previews: list[tuple[Path, dict[str, Any]]]) -> None:
    panels: list[np.ndarray] = []
    for base, record in previews[:24]:
        try:
            input_package = Path(str(record["input_package_dir"]))
            src = read_gray(base / record["package_src"])
            before = read_gray(input_package / record["package_lbl"])
            fixed = read_gray(base / record["package_lbl"])
            anchor = read_gray(Path(str(record["anchor_path"])))
            diff = np.clip(np.abs(fixed.astype(np.int16) - before.astype(np.int16)) * 3, 0, 255).astype(np.uint8)
            tiles = []
            for name, img in (("src", src), ("before", before), ("fixed", fixed), ("anchor", anchor), ("diff x3", diff)):
                tile = cv2.cvtColor(_thumb(img), cv2.COLOR_GRAY2BGR)
                cv2.putText(tile, name, (5, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 255, 255), 1, cv2.LINE_AA)
                tiles.append(tile)
            panel = np.concatenate(tiles, axis=1)
            caption = np.full((30, panel.shape[1], 3), 245, dtype=np.uint8)
            text = (
                f"{record.get('stage','')[:22]} {record['core_repair_reason'][:36]} "
                f"{record['core_grad_ratio_before']:.2f}->{record['core_grad_ratio_after']:.2f}"
            )
            cv2.putText(caption, text, (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (20, 20, 20), 1, cv2.LINE_AA)
            panels.append(np.concatenate([caption, panel], axis=0))
        except Exception:
            continue
    if panels:
        write_image(output_dir / "core_repair_preview.png", np.concatenate(panels, axis=0))


def _write_summary(output_root: Path, package_rows: list[dict[str, Any]], args: dict[str, Any]) -> None:
    total = sum(int(row["total_pairs"]) for row in package_rows)
    repaired = sum(int(row["core_repaired_pairs"]) for row in package_rows)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_packages": [str(path) for path in args["package_dirs"]],
        "output_root": str(output_root),
        "grad_ratio_threshold": float(args["grad_ratio_threshold"]),
        "total_pairs": total,
        "core_repaired_pairs": repaired,
        "packages": package_rows,
    }
    (output_root / "repair_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [
        "# R56 Label Core Repair Summary",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- output_root: `{output_root}`",
        f"- total_pairs: `{total}`",
        f"- core_repaired_pairs: `{repaired}`",
        f"- grad_ratio_threshold: `{args['grad_ratio_threshold']}`",
        "",
        "## Policy",
        "",
        "Keep the real source grayscale style, but rebuild weak label edge cores from source-derived local intensities.",
        "Old CAD or label images locate edge bands only; they are not copied back as black/white fills.",
        "",
        "## Packages",
        "",
        "| package | pairs | core repaired | min repaired grad ratio |",
        "|---|---:|---:|---:|",
    ]
    for row in package_rows:
        min_ratio = row["min_grad_ratio_after_repaired"]
        min_text = "" if min_ratio is None else f"{float(min_ratio):.3f}"
        lines.append(f"| `{row['package']}` | {row['total_pairs']} | {row['core_repaired_pairs']} | {min_text} |")
    lines.append("")
    (output_root / "REPAIR_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")


def repair_packages(
    *,
    package_dirs: list[Path],
    output_root: Path,
    force: bool = False,
    grad_ratio_threshold: float = 1.5,
    emit_preview: bool = True,
) -> dict[str, Any]:
    output_root = Path(output_root).resolve()
    if output_root.exists():
        if not force:
            raise FileExistsError(output_root)
        _safe_remove_tree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for package_dir in package_dirs:
        package_dir = Path(package_dir).resolve()
        rows.append(
            repair_package(
                package_dir,
                output_root / package_dir.name,
                grad_ratio_threshold=grad_ratio_threshold,
                emit_preview=emit_preview,
            )
        )
    args = {"package_dirs": package_dirs, "grad_ratio_threshold": grad_ratio_threshold}
    _write_summary(output_root, rows, args)
    return {
        "output_root": str(output_root),
        "package_count": len(rows),
        "total_pairs": sum(int(row["total_pairs"]) for row in rows),
        "core_repaired_pairs": sum(int(row["core_repaired_pairs"]) for row in rows),
        "packages": rows,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repair weak source-style label cores in R55-style Lab packages")
    parser.add_argument("--package-dir", type=Path, action="append", default=None)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--grad-ratio-threshold", type=float, default=1.5)
    parser.add_argument("--no-preview", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    package_dirs = list(args.package_dir) if args.package_dir else list(DEFAULT_PACKAGES)
    summary = repair_packages(
        package_dirs=package_dirs,
        output_root=args.output_root,
        force=args.force,
        grad_ratio_threshold=args.grad_ratio_threshold,
        emit_preview=not args.no_preview,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
